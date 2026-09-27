#!/usr/bin/env python3
"""Checked common-expression compiler for Clojure dialects and Gambit Scheme.

Numeric contract: exact integer operands/results in the signed 53-bit safe range.
This is a syntax compiler, not a claim that arbitrary dialect programs interoperate.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

PROFILES=('clojure','babashka','jank','cossack','clojurescript-nbb','basilisp','squint','gambit')
OPS={'+','-','*','=','<','<=','>','>=','not'}
RESERVED=OPS|{'if','let','let*','fn','lambda','inc','dec','true','false','#t','#f',
    'nil','def','quote','var','do','try','throw','catch','finally','loop','loop*',
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

def read(source):
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
        if re.fullmatch(r'[+-]?[0-9]+',token):
            value=int(token)
            if abs(value)>2**53-1:raise Unsupported('Integer literal exceeds the common exact range')
            return value
        if not re.fullmatch(r'[A-Za-z_+*<>=!?/-][A-Za-z0-9_+*<>=!?/-]*|#t|#f',token):
            raise Unsupported('Unsupported token: '+token)
        return Sym(token)
    expr=form()
    if pos!=len(tokens):raise Unsupported('Expected one expression')
    return expr

def lower(source, profile):
    if profile not in PROFILES:raise Unsupported('Unknown source profile')
    scheme=profile=='gambit'
    def identifier(x):
        if not isinstance(x,Sym) or x.name in RESERVED or '/' in x.name:
            raise Unsupported('Expected a non-reserved, unqualified binding name')
        return x.name
    def walk(x,env):
        if isinstance(x,int):return ('int',x)
        if isinstance(x,Sym):
            bools={'#t':True,'#f':False} if scheme else {'true':True,'false':False}
            if x.name in bools:return ('bool',bools[x.name])
            if x.name in env:return ('var',x.name)
            raise Unsupported('Unbound or unsupported symbol: '+x.name)
        if not isinstance(x,tuple) or not x:raise Unsupported('Expected a supported expression')
        head=x[0].name if isinstance(x[0],Sym) else None
        args=x[1:]
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
        if head in ('inc','dec') and not scheme:
            if len(args)!=1:raise Unsupported('inc/dec arity')
            return ('op','+' if head=='inc' else '-',(walk(args[0],env),('int',1)))
        if head in OPS:
            if head=='not':
                if len(args)!=1:raise Unsupported('not arity')
                test=walk(args[0],env)
                if not (test[0]=='bool' or test[0]=='op' and test[1] in {'=','<','<=','>','>=','not'}):raise Unsupported('not requires a provably boolean operand')
                return ('op',head,(test,))
            if len(args)!=2:raise Unsupported('Common arithmetic/comparison currently requires two operands')
            return ('op',head,tuple(walk(a,env) for a in args))
        if head in RESERVED:raise Unsupported('Form is not supported in this source dialect: '+head)
        return ('call',walk(x[0],env),tuple(walk(a,env) for a in args))
    result=walk(read(source),set())
    evaluate(result)
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

def emit(ir,profile):
    if profile not in PROFILES:raise Unsupported('Unknown target profile')
    scheme=profile=='gambit'
    def go(n):
        kind=n[0]
        if kind=='int':return str(n[1])
        if kind=='bool':return ('#t' if n[1] else '#f') if scheme else ('true' if n[1] else 'false')
        if kind=='var':return n[1]
        if kind=='let':
            bindings=' '.join('('+name+' '+go(v)+')' for name,v in n[1]) if scheme else ' '.join(name+' '+go(v) for name,v in n[1])
            return '(let* ('+bindings+') '+go(n[2])+')' if scheme else '(let ['+bindings+'] '+go(n[2])+')'
        if kind=='fn':return ('(lambda (' if scheme else '(fn [')+' '.join(n[1])+(') ' if scheme else '] ')+go(n[2])+')'
        if kind=='if':return '(if '+' '.join(go(v) for v in n[1:])+')'
        if kind=='op':return '('+n[1]+' '+' '.join(go(v) for v in n[2])+')'
        if kind=='call':return '('+go(n[1])+(' ' if n[2] else '')+' '.join(go(v) for v in n[2])+')'
        raise Unsupported('Unknown IR node')
    return go(ir)

def transition(source,source_profile,target_profile):
    return emit(lower(source,source_profile),target_profile)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from',dest='source',required=True,choices=PROFILES)
    p.add_argument('--to',dest='target',required=True,choices=PROFILES)
    p.add_argument('file',type=Path)
    p.add_argument('--compile-to',type=Path,help='Compile Gambit output to an executable using gsc')
    p.add_argument('--gsc',default='gsc')
    args=p.parse_args()
    result=transition(args.file.read_text(),args.source,args.target)
    if args.compile_to:
        if args.target!='gambit':p.error('--compile-to requires --to gambit')
        args.compile_to.parent.mkdir(parents=True,exist_ok=True)
        import tempfile
        with tempfile.TemporaryDirectory(prefix='aella-gambit-') as tmp:
            src=Path(tmp)/'program.scm';src.write_text('(write '+result+') (newline)\n')
            subprocess.run([args.gsc,'-exe','-o',str(args.compile_to.resolve()),str(src)],check=True)
    else:print(result)
if __name__=='__main__':main()
