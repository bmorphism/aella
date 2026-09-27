#!/usr/bin/env python3
"""Compile tail loops and compare pure Clojure cases against the JVM."""
import argparse,json,math,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--clojure',default='clojure')
a=p.parse_args()
fixtures=[
 ('promotion',"(loop [n 9223372036854775807 i 0] (if (= i 0) (recur (+' n x) 1) n))",
  '(let loop ((n 9223372036854775807) (i 0)) (if (= i 0) (loop (+ n x) 1) n))',[(1,2**63),(10**60,2**63-1+10**60)]),
 ('sum',"(loop [n x acc 0N] (if (= n 0) acc (recur (-' n 1) (+' acc n))))",
  '(let loop ((n x) (acc 0)) (if (= n 0) acc (loop (- n 1) (+ acc n))))',[(0,0),(100000,5000050000)]),
 ('swap',"(loop [n x a 0N b 1N] (if (= n 0) (-' a b) (recur (-' n 1) b a)))",
  '(let loop ((n x) (a 0) (b 1)) (if (= n 0) (- a b) (loop (- n 1) b a)))',[(10,-1),(11,1)]),
 ('factorial',"(loop [n x acc 1N] (if (= n 0) acc (recur (-' n 1) (*' acc n))))",
  '(let loop ((n x) (acc 1)) (if (= n 0) acc (loop (- n 1) (* acc n))))',[(0,1),(100,math.factorial(100))]),
 ('nested',"(loop [n x acc 0N] (if (= n 0) acc (let [s (loop [j n a 0N] (if (= j 0) a (recur (-' j 1) (+' a j))))] (recur (-' n 1) (+' acc s)))))",
  '(let outer ((n x) (acc 0)) (if (= n 0) acc (let* ((s (let inner ((j n) (a 0)) (if (= j 0) a (inner (- j 1) (+ a j)))))) (outer (- n 1) (+ acc s)))))',[(3,10),(100,171700)]),
 ('fn-recur',"((fn [n acc] (if (= n 0) acc (recur (-' n 1) (+' acc n)))) x 0N)",
  '(let loop ((n x) (acc 0)) (if (= n 0) acc (loop (- n 1) (+ acc n))))',[(0,0),(100000,5000050000)]),
 ('fn-boundary',"(loop [i x] ((fn [n] (if (= n 0) i (recur (-' n 1)))) 3N))",
  '(let outer ((i x)) (let inner ((n 3)) (if (= n 0) i (inner (- n 1)))))',[(7,7),(42,42)]),
 ('closure-snapshot',"(loop [i 0N previous (fn [] (-' x 1))] (if (= i x) (previous) (recur (+' i 1) (fn [] i))))",
  '(let loop ((i 0) (previous (lambda () (- x 1)))) (if (= i x) (previous) (loop (+ i 1) (lambda () i))))',[(0,-1),(20,19)]),
 ('initializers',"(let [n x] (loop [n 1N y n] y))",
  '(let* ((n x)) (let loop ((n 1) (y n)) y))',[(7,{'cossack':1,'gambit':7}),(42,{'cossack':1,'gambit':42})]),
 ('shadow',"(loop [n x] (let [again (fn [v] (+' v 1))] (again n)))",
  '(let again ((n x)) (let* ((again (lambda (v) (+ v 1)))) (again n)))',[(7,8),(42,43)]),
]
compiled=0;checks=0;jvm=0
with tempfile.TemporaryDirectory(prefix='aella-loops-') as directory:
 tmp=Path(directory)
 # One JVM launch supplies an independent Clojure evaluation of every case.
 oracle=[]
 for _,clj,_,cases in fixtures:
  for value,_ in cases:oracle.append('(println (let [x '+str(value)+'N] '+clj+'))')
 references=subprocess.check_output([a.clojure,'-M','-e',' '.join(oracle)],text=True,timeout=60).splitlines()
 assert len(references)==len(oracle)
 for name,clj,scm,cases in fixtures:
  for value,want in cases:
   expected=want['cossack'] if isinstance(want,dict) else want
   assert int(references[jvm].rstrip("N"))==expected,(name,value,references[jvm],expected)
   jvm+=1
  for syntax,source in [('cossack',clj),('gambit',scm)]:
   path=tmp/(name+'.'+syntax);path.write_text(source);exe=tmp/(name+'-'+syntax)
   subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
                  '--exact','--parameters','x','--gsc',a.gsc,'--compile-to',str(exe)],check=True,timeout=60)
   compiled+=1
   for value,want in cases:
    expected=want[syntax] if isinstance(want,dict) else want
    actual=subprocess.check_output([str(exe),str(value)],text=True,timeout=20).strip()
    assert actual==str(expected),(name,syntax,value,actual,expected)
    checks+=1
   print('PASS',name,syntax,flush=True)
report={'compiled_programs':compiled,'runtime_value_checks':checks,'jvm_reference_checks':jvm,
        'largest_iteration_count':100000,'initializers':'Clojure sequential; Scheme parallel',
        'checks':'tail calls, simultaneous rebinding, closures, nested and function recursion, lexical shadowing'}
(ROOT/'results/native-loops.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
