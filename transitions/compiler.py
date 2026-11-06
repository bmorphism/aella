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
SRFI141_MODES=('balanced','ceiling','floor','round','truncate','euclidean')
SRFI141_PAIRS={mode+'/' for mode in SRFI141_MODES}
SRFI141_NAMES={mode+suffix for mode in SRFI141_MODES for suffix in ('/','-quotient','-remainder')}
NATIVE_OPS={
 'cossack.padic/round-training':('cx-round-training',3),
 'cossack.padic/classification-batch-loss':('cx-classification-batch-loss',2),
 'cossack.padic/classification-batch-slope':('cx-classification-batch-slope',3),
 'cossack.padic/classification-batch-groups':('cx-classification-batch-groups',2),
 'cossack.padic/classification-batch-train-step':('cx-classification-batch-train-step',6),
 'cossack.padic/network-classification-probabilities':('cx-network-classification-probabilities',2),
 'cossack.padic/network-classification-loss':('cx-network-classification-loss',3),
 'cossack.padic/network-classification-slope':('cx-network-classification-slope',4),
 'cossack.padic/network-classification-groups':('cx-network-classification-groups',3),
 'cossack.padic/network-classification-train-step':('cx-network-classification-train-step',7),
 'cossack.padic/classification-probabilities':('cx-classification-probabilities',1),
 'cossack.padic/classification-loss':('cx-classification-loss',2),
 'cossack.padic/classification-slope':('cx-classification-slope',3),
 'cossack.padic/array':('cx-array',4),
 'cossack.padic/array-add':('cx-array-add',2),
 'cossack.padic/array-sub':('cx-array-sub',2),
 'cossack.padic/array-mul':('cx-array-mul',2),
 'cossack.padic/array-neg':('cx-array-neg',1),
 'cossack.padic/array-power':('cx-array-power',2),
 'cossack.padic/neg':('cx-disk-neg',1),
 'cossack.padic/sub':('cx-disk-sub',2),
 'cossack.padic/prime':('cx-disk-prime',1),
 'cossack.padic/center':('cx-disk-center',1),
 'cossack.padic/radius':('cx-disk-radius',1),
 'cossack.padic/point?':('cx-disk-point?',1),
 'cossack.padic/center-norm':('cx-disk-center-norm',1),
 'cossack.padic/seminorm':('cx-disk-seminorm',1),
 'cossack.padic/decompose':('cx-decompose',2),
 'cossack.padic/expansion':('cx-expansion',3),
 'cossack.padic/from-expansion':('cx-from-expansion',2),
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
NATIVE_OPS.update({'srfi.141/'+mode+suffix:(mode+suffix,2)
                  for mode in SRFI141_MODES for suffix in ('/','-quotient','-remainder')})
RESERVED=OPS|set(EXACT_OPS)|set(NATIVE_OPS)|{v[0] for v in NATIVE_OPS.values()}|{'if','let','let*','fn','lambda','inc','dec','true','false','#t','#f',
    'list','call-with-values','nil','def','quote','var','do','try','throw','catch','finally','loop','loop*',
    'recur','new','set!','monitor-enter','monitor-exit','deftype*','reify*','case*',
    'import*','fn*','define','begin','quasiquote','unquote','unquote-splicing',
    'cond','and','or','case','delay','letrec','letrec*','let-values','let*-values',
    'define-syntax','let-syntax','letrec-syntax','syntax-rules'}
# Preserve lexical list-ref bindings accepted before native data access existed.
# Native projections use a private alias to prevent capture by those bindings.
RESERVED.discard('list-ref')
RESERVED.difference_update(SRFI141_NAMES)
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
    serial=0
    def fresh():
        nonlocal serial
        serial+=1
        return 'aella-loop-'+str(serial)
    def identifier(x,loop_label=False):
        if not isinstance(x,Sym) or x.name in RESERVED and not (loop_label and scheme and x.name=='loop') or '/' in x.name or x.name.startswith(('aella-','cx-')):
            raise Unsupported('Expected a non-reserved, unqualified binding name')
        return x.name
    def walk(x,env,tail=False,target=None):
        def value(y,scope=None):return walk(y,env if scope is None else scope,target=target)
        if exact and isinstance(x,Vec):return ('data-list',tuple(value(a) for a in x.items))
        if isinstance(x,Fraction):return ('ratio',x.numerator,x.denominator)
        if isinstance(x,int):return ('int',x)
        if isinstance(x,Sym):
            bools={'#t':True,'#f':False} if scheme else {'true':True,'false':False}
            if x.name in bools:return ('bool',bools[x.name])
            if x.name in env:
                if env[x.name] is not None:raise Unsupported('Named-let recursion points cannot escape as values')
                return ('var',x.name)
            raise Unsupported('Unbound or unsupported symbol: '+x.name)
        if not isinstance(x,tuple) or not x:raise Unsupported('Expected a supported expression')
        head=x[0].name if isinstance(x[0],Sym) else None
        args=x[1:]
        if not scheme and head=='recur':
            if not tail or target is None:raise Unsupported('recur requires tail position in a loop or function')
            if len(args)!=target[1]:raise Unsupported('recur arity does not match its recursion point')
            return ('jump',target[0],tuple(value(a) for a in args))
        if scheme and head in env and env[head] is not None:
            point=env[head]
            if not exact and point!=target:raise Unsupported('Common loops cannot recur across a function or nested loop boundary')
            if not tail:raise Unsupported('Named-let recursive calls require tail position in this subset')
            if len(args)!=point[1]:raise Unsupported('Named-let recursive call has wrong arity')
            return ('jump',point[0],tuple(value(a) for a in args))
        if not scheme and head=='loop' or scheme and head=='let' and args and isinstance(args[0],Sym):
            if scheme:
                if len(args)!=3 or not isinstance(args[1],tuple):raise Unsupported('Named let requires a name, bindings, and one body')
                label=identifier(args[0],loop_label=True);pairs=args[1];body=args[2]
            else:
                if len(args)!=2 or not isinstance(args[0],Vec) or len(args[0].items)%2:raise Unsupported('loop requires binding pairs and one body')
                label=None;pairs=tuple(zip(args[0].items[::2],args[0].items[1::2]));body=args[1]
            bindings=[];scope=dict(env);seen=set();name=fresh()
            for pair in pairs:
                if not isinstance(pair,tuple) or len(pair)!=2:raise Unsupported('Malformed loop binding')
                parameter=identifier(pair[0])
                if parameter in seen:raise Unsupported('Duplicate loop binding')
                seen.add(parameter)
                # Clojure initializers are sequential; Scheme named-let initializers are parallel.
                bindings.append((parameter,value(pair[1],env if scheme else scope)))
                scope[parameter]=None
            point=(name,len(bindings))
            if scheme:
                scope=dict(env);scope[label]=point;scope.update({parameter:None for parameter,_ in bindings})
            return ('loop',name,tuple(bindings),walk(body,scope,tail=True,target=None if scheme and exact else point),not scheme)
        if exact and scheme and head=='list':return ('data-list',tuple(value(a) for a in args))
        if exact and scheme and head=='call-with-values':
            if len(args)!=2:raise Unsupported('call-with-values requires producer and consumer')
            consumer=('list-function',) if args[1]==Sym('list') else value(args[1])
            return ('call-values',value(args[0]),consumer)
        native_ops={v[0]:v for v in NATIVE_OPS.values()} if scheme else NATIVE_OPS
        if exact and head in native_ops and head not in env:
            name,arity=native_ops[head]
            if len(args)!=arity:raise Unsupported('Wrong native operation arity: '+head)
            if name=='list-ref' and (not isinstance(args[1],int) or args[1]<0):
                raise Unsupported('Native data access requires a nonnegative literal integer index')
            kind='native-pair' if not scheme and name in SRFI141_PAIRS else 'native'
            return (kind,name,tuple(value(a) for a in args))
        if head==('let*' if scheme else 'let'):
            if len(args)!=2:raise Unsupported('let requires bindings and one body expression')
            if scheme:
                if not isinstance(args[0],tuple):raise Unsupported('Scheme bindings must be a list')
                pairs=args[0]
            else:
                if not isinstance(args[0],Vec) or len(args[0].items)%2:raise Unsupported('Clojure bindings must be pairs in a vector')
                pairs=tuple(zip(args[0].items[::2],args[0].items[1::2]))
            bindings=[];scope=dict(env)
            for pair in pairs:
                if not isinstance(pair,tuple) or len(pair)!=2:raise Unsupported('Malformed binding')
                name=identifier(pair[0]);bindings.append((name,value(pair[1],scope)));scope[name]=None
            return ('let',tuple(bindings),walk(args[1],scope,tail=tail,target=target))
        if head==('lambda' if scheme else 'fn'):
            if len(args)!=2:raise Unsupported('Function requires parameters and one body')
            ps=args[0] if scheme and isinstance(args[0],tuple) else args[0].items if not scheme and isinstance(args[0],Vec) else None
            if ps is None:raise Unsupported('Invalid parameter list')
            names=tuple(identifier(p) for p in ps)
            if len(set(names))!=len(names):raise Unsupported('Duplicate parameters are outside the common subset')
            scope=dict(env);scope.update({name:None for name in names})
            if exact and not scheme:
                name=fresh()
                return ('rec-fn',name,names,walk(args[1],scope,tail=True,target=(name,len(names))))
            return ('fn',names,walk(args[1],scope,tail=True))
        if head=='if':
            if len(args)!=3:raise Unsupported('if requires test and two branches')
            test=value(args[0])
            if not (test[0]=='bool' or test[0]=='op' and test[1] in {'=','<','<=','>','>=','not'} or test[0]=='native' and test[1]=='cx-disk-point?'):
                raise Unsupported('Cross-Scheme condition must be provably boolean')
            return ('if',test,walk(args[1],env,tail=tail,target=target),walk(args[2],env,tail=tail,target=target))
        if exact and not scheme and head in ('+','-','*','inc','dec'):
            raise Unsupported("Exact native compilation requires promoting arithmetic: +', -', *'; use addition/subtraction by one for inc/dec")
        if head in ('inc','dec') and not scheme:
            if len(args)!=1:raise Unsupported('inc/dec arity')
            return ('op','+' if head=='inc' else '-',(value(args[0]),('int',1)))
        if exact and head in EXACT_OPS:
            if scheme and head!='/':raise Unsupported('Promoting apostrophe operators are Clojure syntax')
            head=EXACT_OPS[head]
        if head in OPS or exact and head=='/':
            if head=='not':
                if len(args)!=1:raise Unsupported('not arity')
                test=value(args[0])
                if not (test[0]=='bool' or test[0]=='op' and test[1] in {'=','<','<=','>','>=','not'} or test[0]=='native' and test[1]=='cx-disk-point?'):raise Unsupported('not requires a provably boolean operand')
                return ('op',head,(test,))
            if len(args)!=2:raise Unsupported('Common arithmetic/comparison currently requires two operands')
            return ('op',head,tuple(value(a) for a in args))
        if head in RESERVED:raise Unsupported('Form is not supported in this source dialect: '+head)
        return ('call',value(x[0]),tuple(value(a) for a in args))
    names=tuple(identifier(Sym(p)) for p in parameters)
    if len(set(names))!=len(names):raise Unsupported('Duplicate runtime parameters')
    if parameters and not exact:raise Unsupported('Runtime parameters require exact native compilation')
    result=walk(read(source,exact=exact,clojure_numbers=not scheme),{name:None for name in names},tail=True)
    if not exact:evaluate(result)
    return result

def evaluate(ir):
    """Certify this closed pure expression's numeric/boolean preconditions."""
    budget=10000
    @dataclass
    class Jump:
        target: str
        values: tuple
    def run(n,env):
        nonlocal budget
        budget-=1
        if budget<0:raise Unsupported('Compile-time verification budget exceeded')
        kind=n[0]
        if kind in ('int','bool'):return n[1]
        if kind=='var':return env[n[1]]
        if kind=='jump':return Jump(n[1],tuple(run(v,env) for v in n[2]))
        if kind=='loop':
            name,bindings,body,sequential=n[1:]
            initial=dict(env)
            values=[]
            for key,value in bindings:
                v=run(value,initial if sequential else env)
                values.append(v);initial[key]=v
            while True:
                scope=dict(env);scope.update(zip((key for key,_ in bindings),values))
                result=run(body,scope)
                if not isinstance(result,Jump):return result
                if result.target!=name:raise Unsupported('Jump crossed its loop boundary')
                values=result.values
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

def free_variables(n, bound=frozenset()):
    """Lexical free variables for the common IR, including initializer scope."""
    kind=n[0]
    if kind=='var':return {n[1]}-bound
    if kind in ('int','bool'):return set()
    if kind=='fn':return free_variables(n[2],bound|set(n[1]))
    if kind in ('let','loop'):
        bindings,body,sequential=(n[1],n[2],True) if kind=='let' else (n[2],n[3],n[4])
        scope=set(bound);result=set()
        for key,value in bindings:
            result|=free_variables(value,scope if sequential else bound)
            scope.add(key)
        return result|free_variables(body,scope)
    children=n[1:] if kind=='if' else (n[1],*n[2]) if kind=='call' else n[2]
    return set().union(*(free_variables(child,bound) for child in children))

def emit(ir,profile, *, exact=False):
    if profile not in PROFILES:raise Unsupported('Unknown target profile')
    scheme=profile=='gambit'
    if exact and profile!='gambit':raise Unsupported('Exact native output currently requires Gambit')
    used=set()
    has_loop=False
    def collect(n):
        nonlocal has_loop
        if isinstance(n,str):used.add(n)
        elif isinstance(n,(tuple,list)):
            if n and n[0]=='loop':has_loop=True
            for value in n:collect(value)
    collect(ir)
    serial=0
    def fresh():
        nonlocal serial
        while True:
            serial+=1
            name='aellaGenerated'+str(serial)
            if name not in used:used.add(name);return name
    labels={}
    def go(n):
        kind=n[0]
        if kind=='rec-fn' and not exact:
            raise Unsupported('Function recursion output requires exact native mode')
        if not exact and kind=='jump':
            temps=[fresh() for _ in n[2]]
            call='('+(labels[n[1]] if scheme else 'recur')+(' ' if temps else '')+' '.join(temps)+')'
            if scheme:
                bindings=' '.join('('+key+' '+go(value)+')' for key,value in zip(temps,n[2]))
                return '(let* ('+bindings+') '+call+')'
            def argument(value):
                expression=go(value)
                if profile=='jank':
                    # A plain let alias still observes a rebound recur slot on
                    # the tested Jank runtime. A function result snapshots it.
                    parameter=fresh()
                    return '((fn ['+parameter+'] '+parameter+') '+expression+')'
                return expression
            bindings=' '.join(key+' '+argument(value) for key,value in zip(temps,n[2]))
            return '(let ['+bindings+'] '+call+')'
        if not exact and kind=='loop':
            name,bindings,body,sequential=n[1:]
            labels[name]=fresh()
            # Fresh temporaries give Scheme's parallel initializers their outer scope.
            keys=[key for key,_ in bindings]
            initial=keys if sequential else [fresh() for _ in bindings]
            if scheme:
                values=' '.join('('+key+' '+go(value)+')' for key,(_,value) in zip(initial,bindings))
                loop_bindings=' '.join('('+key+' '+value+')' for key,value in zip(keys,initial))
                return '(let* ('+values+') (let '+labels[name]+' ('+loop_bindings+') '+go(body)+'))'
            values=' '.join(key+' '+go(value) for key,(_,value) in zip(initial,bindings))
            loop_bindings=' '.join(key+' '+value for key,value in zip(keys,initial))
            return '(let ['+values+'] (loop ['+loop_bindings+'] '+go(body)+'))'
        if kind=='int':return str(n[1])
        if kind=='data-list':return '(list'+(' ' if n[1] else '')+' '.join(go(v) for v in n[1])+')'
        if kind=='list-function':return 'list'
        if kind=='call-values':return '(call-with-values '+go(n[1])+' '+go(n[2])+')'
        if kind=='ratio':return str(n[1])+'/'+str(n[2])
        if kind=='bool':return ('#t' if n[1] else '#f') if scheme else ('true' if n[1] else 'false')
        if kind=='var':return n[1]
        if kind=='jump':
            temporaries=[n[1]+'-arg-'+str(i) for i in range(len(n[2]))]
            bindings=' '.join('('+name+' '+go(value)+')' for name,value in zip(temporaries,n[2]))
            return '(let* ('+bindings+') ('+n[1]+(' ' if temporaries else '')+' '.join(temporaries)+'))'
        if kind=='rec-fn':
            return '(letrec (('+n[1]+' (lambda ('+' '.join(n[2])+') '+go(n[3])+'))) '+n[1]+')'
        if kind=='loop':
            name,bindings,body,sequential=n[1:]
            parameters=[key for key,_ in bindings]
            initial_names=parameters if sequential else [name+'-init-'+str(i) for i in range(len(bindings))]
            initializers=' '.join('('+key+' '+go(value)+')' for key,(_,value) in zip(initial_names,bindings))
            procedure='(letrec (('+name+' (lambda ('+' '.join(parameters)+') '+go(body)+'))) ('+name+(' ' if initial_names else '')+' '.join(initial_names)+'))'
            return '('+('let*' if sequential else 'let')+' ('+initializers+') '+procedure+')'
        if kind=='let':
            bindings=' '.join('('+name+' '+go(v)+')' for name,v in n[1]) if scheme else ' '.join(name+' '+go(v) for name,v in n[1])
            return '(let* ('+bindings+') '+go(n[2])+')' if scheme else '(let ['+bindings+'] '+go(n[2])+')'
        if kind=='fn':
            expression=('(lambda (' if scheme else '(fn [')+' '.join(n[1])+(') ' if scheme else '] ')+go(n[2])+')'
            if profile in ('basilisp','squint') and has_loop:
                captures=sorted(free_variables(n))
                if captures:
                    # Capture current values in a fresh function activation;
                    # These runtimes otherwise retain mutable loop cells.
                    names=' '.join(captures)
                    return '((fn ['+names+'] '+expression+') '+names+')'
            return expression
        if kind=='if':return '(if '+' '.join(go(v) for v in n[1:])+')'
        if kind=='op':return '('+('aella-op '+n[1] if exact and n[1]!='not' else n[1])+' '+' '.join(go(v) for v in n[2])+')'
        if kind in ('native','native-pair'):
            args=' '.join(go(v) for v in n[2])
            name='aella-srfi-'+n[1] if n[1] in SRFI141_NAMES else n[1]
            if kind=='native-pair':return '(call-with-values (lambda () ('+name+' '+args+')) list)'
            if n[1]=='list-ref':return '(aella-data-ref '+args+')'
            if n[1] in ('cx-norm','cx-valuation'):
                return '(aella-padic-'+n[1][3:]+' '+args+')'
            return '('+name+' '+args+')'
        if kind=='call':return '('+go(n[1])+(' ' if n[2] else '')+' '.join(go(v) for v in n[2])+')'
        raise Unsupported('Unknown IR node')
    return go(ir)

def transition(source,source_profile,target_profile):
    return emit(lower(source,source_profile),target_profile)

def native_program(expression, parameters, numeric_library=None, *, prune=True):
    prelude = """(define (aella-exact x)
  (if (and (number? x) (exact? x)) x (error "Expected an exact number")))
(define (aella-op op . args) (apply op (map aella-exact args)))
(define aella-data-ref list-ref)
(define aella-args (map (lambda (s) (aella-exact (string->number s))) (cdr (command-line))))
"""
    for name in sorted(SRFI141_NAMES):
        if '(aella-srfi-'+name+' ' in expression:
            prelude+='(define aella-srfi-'+name+' '+name+')\n'
    for name in ('norm','valuation'):
        if '(aella-padic-'+name+' ' in expression:
            prelude+='(define (aella-padic-'+name+' p x) (if (cx-prime? p) (cx-'+name+' p x) (error "Expected prime base")))\n'
    uses_library=bool(re.search(r'\((?:cx-|aella-padic-)',expression))
    if uses_library and numeric_library is None:
        raise Unsupported('P-adic compilation requires --numeric-library pointing to Cossack gambit/numeric.scm')
    if numeric_library is not None:
        library=Path(numeric_library).resolve(strict=True)
        if uses_library:prelude='(include '+json.dumps(str(library))+')\n'+prelude
    declaration='(declare (optimize-dead-definitions))\n' if prune else ''
    return declaration+prelude+'(if (not (= (length aella-args) '+str(len(parameters))+')) (error "Wrong argument count"))\n'+ '(call-with-values (lambda () (apply (lambda ('+' '.join(parameters)+') '+expression+') aella-args)) (lambda aella-results (write (if (= (length aella-results) 1) (car aella-results) aella-results)))) (newline)\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from',dest='source',required=True,choices=PROFILES)
    p.add_argument('--to',dest='target',required=True,choices=PROFILES)
    p.add_argument('file',type=Path)
    p.add_argument('--compile-to',type=Path,help='Compile Gambit output to an executable using gsc')
    p.add_argument('--gsc',default='gsc')
    p.add_argument('--numeric-library',type=Path,help='Cossack gambit/numeric.scm for native p-adic operations')
    p.add_argument('--exact',action='store_true',help='Compile dynamic exact numeric arithmetic to Gambit')
    p.add_argument('--keep-unused-definitions',action='store_true',help='Preserve all top-level definitions instead of pruning a standalone exact kernel')
    p.add_argument('--parameters',nargs='*',default=[],help='Names of exact numeric executable arguments')
    args=p.parse_args()
    if args.parameters and not args.exact:p.error('--parameters requires --exact')
    if args.keep_unused_definitions and not args.exact:p.error('--keep-unused-definitions requires --exact')
    result=emit(lower(args.file.read_text(),args.source,exact=args.exact,parameters=args.parameters),args.target,exact=args.exact)
    if args.compile_to:
        if args.target!='gambit':p.error('--compile-to requires --to gambit')
        args.compile_to.parent.mkdir(parents=True,exist_ok=True)
        import tempfile
        with tempfile.TemporaryDirectory(prefix='aella-gambit-') as tmp:
            src=Path(tmp)/'program.scm';src.write_text(native_program(result,args.parameters,args.numeric_library,prune=not args.keep_unused_definitions) if args.exact else '(write '+result+') (newline)\n')
            subprocess.run([args.gsc,'-exe','-o',str(args.compile_to.resolve()),str(src)],check=True)
    else:print(native_program(result,args.parameters,args.numeric_library,prune=not args.keep_unused_definitions) if args.exact else result)
if __name__=='__main__':main()
