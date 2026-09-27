#!/usr/bin/env python3
"""Checked common-expression compiler for Clojure dialects and Gambit Scheme.

Numeric contract: exact integer operands/results in the signed 53-bit safe range.
This is a syntax compiler, not a claim that arbitrary dialect programs interoperate.
"""
import argparse
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re
import subprocess

PROFILES=('clojure','babashka','jank','cossack','clojurescript-nbb','basilisp','squint','gambit')
OPS={'+','-','*','=','<','<=','>','>=','not'}
EXACT_OPS={"+'":'+',"-'":'-',"*'":'*','/':'/'}
NATIVE_OPS={
 'cossack.padic/network-groups':('cx-network-groups',3),
 'cossack.padic/network-train-step':('cx-network-train-step',7),
 'nth':('list-ref',2),
 'cossack.padic/network-optimizer-step':('cx-network-optimizer-step',8),
 'cossack.padic/network-coordinate-step':('cx-network-coordinate-step',5),
 'cossack.number/complex':('make-rectangular',2),
 'cossack.number/real-part':('real-part',1),
 'cossack.number/imag-part':('imag-part',1),
 'cossack.padic/network-loss':('cx-network-loss',3),
 'cossack.padic/network-slope':('cx-network-slope',4),
 'cossack.padic/polynomial':('cx-polynomial',2),
 'cossack.padic/polynomial-slope':('cx-polynomial-slope',3),
 'cossack.padic/disk':('cx-disk',3),
 'cossack.padic/add':('cx-disk-add',2),
 'cossack.padic/mul':('cx-disk-mul',2),
 'cossack.padic/power':('cx-power',2),
 'cossack.padic/distance':('cx-distance',2),
 'cossack.padic/geodesic':('cx-geodesic',3),
 'cossack.padic/direct-loss-step':('cx-direct-loss-step',3),
 'cossack.padic/direct-loss-slope':('cx-direct-loss-slope',3),
 'cossack.padic/norm':('cx-norm',2),
 'cossack.padic/valuation':('cx-valuation',2),
}
RESERVED=OPS|set(EXACT_OPS)|set(NATIVE_OPS)|{v[0] for v in NATIVE_OPS.values()}|{'if','let','let*','fn','lambda','inc','dec','true','false','#t','#f',
    'list','nil','def','quote','var','do','try','throw','catch','finally','loop','loop*',
    'recur','new','set!','monitor-enter','monitor-exit','deftype*','reify*','case*',
    'import*','fn*','define','begin','quasiquote','unquote','unquote-splicing',
    'cond','and','or','case','delay','letrec','letrec*','let-values','let*-values',
    'define-syntax','let-syntax','letrec-syntax','syntax-rules'}
class Unsupported(ValueError): pass
@dataclass(frozen=True)
class Sym:
    name:str
@dataclass(frozen=True)
class Vec:
    items:tuple

def read(source, exact=False, clojure_numbers=True):
    tokens=re.findall(r';[^\n]*|[()\[\]]|[^\s,()\[\]]+',source)
    tokens=[t for t in tokens if not t.startswith(';')]
    pos=0
    def form():
        nonlocal pos
        if pos==len(tokens):raise Unsupported('Unexpected EOF')
        token=tokens[pos];pos+=1
        if token in ('(','['):
            end=')' if token=='(' else ']';items=[]
            while pos<len(tokens) and tokens[pos]!=end:items.append(form())
            if pos==len(tokens):raise Unsupported('Unclosed collection')
            pos+=1
            return tuple(items) if token=='(' else Vec(tuple(items))
        if token in (')',']'):raise Unsupported('Unexpected closing delimiter')
        if exact and re.fullmatch(r'[+-]?[0-9]+/[0-9]+',token):
            try:return Fraction(token)
            except ZeroDivisionError as error:raise Unsupported('Zero ratio denominator') from error
        if exact and re.fullmatch(r'[+-]?[0-9]+N',token):
            if not clojure_numbers:raise Unsupported('N suffix is not Gambit syntax')
            token=token[:-1]
        if re.fullmatch(r'[+-]?[0-9]+',token):
            value=int(token)
            if not exact and abs(value)>2**53-1:raise Unsupported('Integer literal exceeds the common exact range')
            return value
        if token not in EXACT_OPS and token not in NATIVE_OPS and not re.fullmatch(r'[A-Za-z_+*<>=!?/-][A-Za-z0-9_+*<>=!?/-]*|#t|#f',token):
            raise Unsupported('Unsupported token: '+token)
        return Sym(token)
    expr=form()
    if pos!=len(tokens):raise Unsupported('Expected one expression')
    return expr

def lower(source, profile, *, exact=False, parameters=()):
    if profile not in PROFILES:raise Unsupported('Unknown source profile')
    if exact and profile not in ('clojure','cossack','gambit'):raise Unsupported('Exact native compilation supports Clojure, Cossack, and Gambit inputs')
    scheme=profile=='gambit'
    def identifier(x):
        if not isinstance(x,Sym) or x.name in RESERVED or '/' in x.name or x.name.startswith(('aella-','cx-')):
            raise Unsupported('Expected a non-reserved, unqualified binding name')
        return x.name
    def walk(x,env):
        if exact and isinstance(x,Vec):return ('data-list',tuple(walk(a,env) for a in x.items))
        if isinstance(x,Fraction):return ('ratio',x.numerator,x.denominator)
        if isinstance(x,int):return ('int',x)
        if isinstance(x,Sym):
            bools={'#t':True,'#f':False} if scheme else {'true':True,'false':False}
            if x.name in bools:return ('bool',bools[x.name])
            if x.name in env:return ('var',x.name)
            raise Unsupported('Unbound or unsupported symbol: '+x.name)
        if not isinstance(x,tuple) or not x:raise Unsupported('Expected a supported expression')
        head=x[0].name if isinstance(x[0],Sym) else None
        args=x[1:]
        if exact and scheme and head=='list':return ('data-list',tuple(walk(a,env) for a in args))
        native_ops={v[0]:v for v in NATIVE_OPS.values()} if scheme else NATIVE_OPS
        if exact and head in native_ops:
            name,arity=native_ops[head]
            if len(args)!=arity:raise Unsupported('Wrong native operation arity: '+head)
            if name=='list-ref' and (not isinstance(args[1],int) or args[1]<0):
                raise Unsupported('Native data access requires a nonnegative literal integer index')
            return ('native',name,tuple(walk(a,env) for a in args))
        if head==('let*' if scheme else 'let'):
            if len(args)!=2:raise Unsupported('let requires bindings and one body expression')
            if scheme:
                if not isinstance(args[0],tuple):raise Unsupported('Scheme bindings must be a list')
                pairs=args[0]
            else:
                if not isinstance(args[0],Vec) or len(args[0].items)%2:raise Unsupported('Clojure bindings must be pairs in a vector')
                pairs=tuple(zip(args[0].items[::2],args[0].items[1::2]))
            bindings=[];scope=set(env)
            for pair in pairs:
                if not isinstance(pair,tuple) or len(pair)!=2:raise Unsupported('Malformed binding')
                name=identifier(pair[0]);bindings.append((name,walk(pair[1],scope)));scope.add(name)
            return ('let',tuple(bindings),walk(args[1],scope))
        if head==('lambda' if scheme else 'fn'):
            if len(args)!=2:raise Unsupported('Function requires parameters and one body')
            ps=args[0] if scheme and isinstance(args[0],tuple) else args[0].items if not scheme and isinstance(args[0],Vec) else None
            if ps is None:raise Unsupported('Invalid parameter list')
            names=tuple(identifier(p) for p in ps)
            if len(set(names))!=len(names):raise Unsupported('Duplicate parameters are outside the common subset')
            return ('fn',names,walk(args[1],set(env)|set(names)))
        if head=='if':
            if len(args)!=3:raise Unsupported('if requires test and two branches')
            test=walk(args[0],env)
            if not (test[0]=='bool' or test[0]=='op' and test[1] in {'=','<','<=','>','>=','not'}):
                raise Unsupported('Cross-Scheme condition must be provably boolean')
            return ('if',test,walk(args[1],env),walk(args[2],env))
        if exact and not scheme and head in ('+','-','*','inc','dec'):
            raise Unsupported("Exact native compilation requires promoting arithmetic: +', -', *'; use addition/subtraction by one for inc/dec")
        if head in ('inc','dec') and not scheme:
            if len(args)!=1:raise Unsupported('inc/dec arity')
            return ('op','+' if head=='inc' else '-',(walk(args[0],env),('int',1)))
        if exact and head in EXACT_OPS:
            if scheme and head!='/':raise Unsupported('Promoting apostrophe operators are Clojure syntax')
            head=EXACT_OPS[head]
        if head in OPS or exact and head=='/':
            if head=='not':
                if len(args)!=1:raise Unsupported('not arity')
                test=walk(args[0],env)
                if not (test[0]=='bool' or test[0]=='op' and test[1] in {'=','<','<=','>','>=','not'}):raise Unsupported('not requires a provably boolean operand')
                return ('op',head,(test,))
            if len(args)!=2:raise Unsupported('Common arithmetic/comparison currently requires two operands')
            return ('op',head,tuple(walk(a,env) for a in args))
        if head in RESERVED:raise Unsupported('Form is not supported in this source dialect: '+head)
        return ('call',walk(x[0],env),tuple(walk(a,env) for a in args))
    names=tuple(identifier(Sym(p)) for p in parameters)
    if len(set(names))!=len(names):raise Unsupported('Duplicate runtime parameters')
    if parameters and not exact:raise Unsupported('Runtime parameters require exact native compilation')
    result=walk(read(source,exact=exact,clojure_numbers=not scheme),set(names))
    if not exact:evaluate(result)
    return result

def evaluate(ir):
    """Certify this closed pure expression's numeric/boolean preconditions."""
    budget=10000
    def run(n,env):
        nonlocal budget
        budget-=1
        if budget<0:raise Unsupported('Compile-time verification budget exceeded')
        kind=n[0]
        if kind in ('int','bool'):return n[1]
        if kind=='var':return env[n[1]]
        if kind=='fn':return (n[1],n[2],dict(env))
        if kind=='let':
            scope=dict(env)
            for name,value in n[1]:scope[name]=run(value,scope)
            return run(n[2],scope)
        if kind=='if':return run(n[2] if run(n[1],env) else n[3],env)
        if kind=='call':
            fn=run(n[1],env);args=[run(v,env) for v in n[2]]
            if not isinstance(fn,tuple) or len(args)!=len(fn[0]):raise Unsupported('Invalid function call')
            scope=dict(fn[2]);scope.update(zip(fn[0],args));return run(fn[1],scope)
        args=[run(v,env) for v in n[2]];op=n[1]
        if op=='not':
            if type(args[0]) is not bool:raise Unsupported('Expected boolean')
            return not args[0]
        if any(type(v) is not int for v in args):raise Unsupported('Numeric operator requires integer operands')
        a,b=args
        if op in ('+','-','*'):
            value=a+b if op=='+' else a-b if op=='-' else a*b
            if abs(value)>2**53-1:raise Unsupported('Intermediate value exceeds common exact range')
            return value
        return {'=':a==b,'<':a<b,'<=':a<=b,'>':a>b,'>=':a>=b}[op]
    try:result=run(ir,{})
    except RecursionError as error:raise Unsupported('Verification recursion limit exceeded') from error
    if type(result) not in (int,bool):raise Unsupported('Common expression must return an integer or boolean')
    return result

def emit(ir,profile, *, exact=False):
    if profile not in PROFILES:raise Unsupported('Unknown target profile')
    scheme=profile=='gambit'
    if exact and profile!='gambit':raise Unsupported('Exact native output currently requires Gambit')
    def go(n):
        kind=n[0]
        if kind=='int':return str(n[1])
        if kind=='data-list':return '(list'+(' ' if n[1] else '')+' '.join(go(v) for v in n[1])+')'
        if kind=='ratio':return str(n[1])+'/'+str(n[2])
        if kind=='bool':return ('#t' if n[1] else '#f') if scheme else ('true' if n[1] else 'false')
        if kind=='var':return n[1]
        if kind=='let':
            bindings=' '.join('('+name+' '+go(v)+')' for name,v in n[1]) if scheme else ' '.join(name+' '+go(v) for name,v in n[1])
            return '(let* ('+bindings+') '+go(n[2])+')' if scheme else '(let ['+bindings+'] '+go(n[2])+')'
        if kind=='fn':return ('(lambda (' if scheme else '(fn [')+' '.join(n[1])+(') ' if scheme else '] ')+go(n[2])+')'
        if kind=='if':return '(if '+' '.join(go(v) for v in n[1:])+')'
        if kind=='op':return '('+('aella-op '+n[1] if exact and n[1]!='not' else n[1])+' '+' '.join(go(v) for v in n[2])+')'
        if kind=='native':
            args=' '.join(go(v) for v in n[2])
            if n[1] in ('cx-norm','cx-valuation'):
                return "(cx-dispatch (list '"+n[1][3:]+' '+args+'))'
            return '('+n[1]+' '+args+')'
        if kind=='call':return '('+go(n[1])+(' ' if n[2] else '')+' '.join(go(v) for v in n[2])+')'
        raise Unsupported('Unknown IR node')
    return go(ir)

def transition(source,source_profile,target_profile):
    return emit(lower(source,source_profile),target_profile)

def native_program(expression, parameters, numeric_library=None):
    prelude = """(define (aella-exact x)
  (if (and (number? x) (exact? x)) x (error "Expected an exact number")))
(define (aella-op op . args) (apply op (map aella-exact args)))
(define aella-args (map (lambda (s) (aella-exact (string->number s))) (cdr (command-line))))
"""
    uses_library=bool(re.search(r'\(cx-',expression))
    if uses_library and numeric_library is None:
        raise Unsupported('P-adic compilation requires --numeric-library pointing to Cossack gambit/numeric.scm')
    if numeric_library is not None:
        library=Path(numeric_library).resolve(strict=True)
        if uses_library:prelude='(include '+json.dumps(str(library))+')\n'+prelude
    return prelude+'(if (not (= (length aella-args) '+str(len(parameters))+')) (error "Wrong argument count"))\n'+ '(write (apply (lambda ('+' '.join(parameters)+') '+expression+') aella-args)) (newline)\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from',dest='source',required=True,choices=PROFILES)
    p.add_argument('--to',dest='target',required=True,choices=PROFILES)
    p.add_argument('file',type=Path)
    p.add_argument('--compile-to',type=Path,help='Compile Gambit output to an executable using gsc')
    p.add_argument('--gsc',default='gsc')
    p.add_argument('--numeric-library',type=Path,help='Cossack gambit/numeric.scm for native p-adic operations')
    p.add_argument('--exact',action='store_true',help='Compile dynamic exact numeric arithmetic to Gambit')
    p.add_argument('--parameters',nargs='*',default=[],help='Names of exact numeric executable arguments')
    args=p.parse_args()
    if args.parameters and not args.exact:p.error('--parameters requires --exact')
    result=emit(lower(args.file.read_text(),args.source,exact=args.exact,parameters=args.parameters),args.target,exact=args.exact)
    if args.compile_to:
        if args.target!='gambit':p.error('--compile-to requires --to gambit')
        args.compile_to.parent.mkdir(parents=True,exist_ok=True)
        import tempfile
        with tempfile.TemporaryDirectory(prefix='aella-gambit-') as tmp:
            src=Path(tmp)/'program.scm';src.write_text(native_program(result,args.parameters,args.numeric_library) if args.exact else '(write '+result+') (newline)\n')
            subprocess.run([args.gsc,'-exe','-o',str(args.compile_to.resolve()),str(src)],check=True)
    else:print(native_program(result,args.parameters,args.numeric_library) if args.exact else result)
if __name__=='__main__':main()
