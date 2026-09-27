#!/usr/bin/env python3
"""Compile both surface syntaxes and execute with values unavailable at compile time."""
import argparse,json,random,subprocess,sys,tempfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--gsc',required=True)
p.add_argument('--only',help='Comma-separated fixture names; requires --output')
p.add_argument('--output',type=Path)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
if a.only and not a.output:p.error("--only requires --output to keep partial results separate")
fixtures=[
 ('square',"(let [f (fn [y] (*' y y))] (+' (f x) 1/3))",
  '(let* ((f (lambda (y) (* y y)))) (+ (f x) 1/3))',
  [(str(x),str(Fraction(x*x)+Fraction(1,3))) for x in [0,-7,10**100, -(10**77+9)]]),
 ('closure',"(let [list-ref x f (fn [y] (+' list-ref y)) list-ref 999N] (f 7N))",
  '(let* ((list-ref x) (f (lambda (y) (+ list-ref y))) (list-ref 999)) (f 7))', [('123456789012345678901234567890','123456789012345678901234567897')]),
 ('complex',"(cossack.number/imag-part (*' x (cossack.number/complex 3 -4)))",
  '(imag-part (* x (make-rectangular 3 -4)))',[('1+2i','2'),('1/3+2/5i','-2/15')]),
 ('disk',"(cossack.padic/distance (cossack.padic/power (cossack.padic/disk 2 1 x) 2) (cossack.padic/disk 2 1 0))",
  '(cx-distance (cx-power (cx-disk 2 1 x) 2) (cx-disk 2 1 0))',[('1/2','1/4'),('1/4','1/8')]),
 ('geodesic','(cossack.padic/distance (cossack.padic/disk 3 0 0) (cossack.padic/geodesic (cossack.padic/disk 3 0 0) (cossack.padic/disk 3 1 0) x))',
  '(cx-distance (cx-disk 3 0 0) (cx-geodesic (cx-disk 3 0 0) (cx-disk 3 1 0) x))',[('1/2','1/2'),('3/2','3/2')]),
 ('proximal','(cossack.padic/distance (cossack.padic/direct-loss-step (cossack.padic/disk 3 0 0) (cossack.padic/disk 3 1 0) x) (cossack.padic/disk 3 1 0))',
  '(cx-distance (cx-direct-loss-step (cx-disk 3 0 0) (cx-disk 3 1 0) x) (cx-disk 3 1 0))',[('1','3/2'),('10','0')]),
 ('slope','(cossack.padic/direct-loss-slope (cossack.padic/disk 3 0 1) (cossack.padic/disk 3 0 0) (cossack.padic/disk 3 x 0))',
  '(cx-direct-loss-slope (cx-disk 3 0 1) (cx-disk 3 0 0) (cx-disk 3 x 0))',[('0','-1/2'),('1','1/2')]),
 ('polynomial',"(cossack.padic/distance (cossack.padic/polynomial [[1 [0 0]] [1 [1 0]] [-1/2 [0 2]]] [(cossack.padic/disk 2 0 x) (cossack.padic/disk 2 0 1/2)]) (cossack.padic/disk 2 1 0))",
  '(cx-distance (cx-polynomial (list (list 1 (list 0 0)) (list 1 (list 1 0)) (list -1/2 (list 0 2))) (list (cx-disk 2 0 x) (cx-disk 2 0 1/2))) (cx-disk 2 1 0))',[('1/4','1/2'),('1','1')]),
 ('polynomial-slope',"(cossack.padic/polynomial-slope [[1 [0 0]] [1 [1 0]] [-1/2 [0 2]]] [(cossack.padic/disk 2 0 1/2) (cossack.padic/disk 2 0 1/2)] [x -1])",
  '(cx-polynomial-slope (list (list 1 (list 0 0)) (list 1 (list 1 0)) (list -1/2 (list 0 2))) (list (cx-disk 2 0 1/2) (cx-disk 2 0 1/2)) (list x -1))',[('-3','-2'),('1','1')]),
 ('network-loss','(cossack.padic/network-loss [[[[1 [2]]]]] [(cossack.padic/disk 3 0 x)] [1])',
  '(cx-network-loss (list (list (list (list 1 (list 2))))) (list (cx-disk 3 0 x)) (list 1))',[('1/3','17/18'),('1','1/2')]),
 ('network-slope','(cossack.padic/network-slope [[[[1 [2]]]]] [(cossack.padic/disk 3 0 1/3)] [x] [1])',
  '(cx-network-slope (list (list (list (list 1 (list 2))))) (list (cx-disk 3 0 1/3)) (list x) (list 1))',[('1','-1/3'),('-1','1/3')]),
 ('norm','(cossack.padic/norm 3 x)','(cx-norm 3 x)',[('5/9','9'),('81','1/81')]),
]
if a.only:
 names=set(a.only.split(','))
 if not names <= {f[0] for f in fixtures}:p.error('Unknown fixture name')
 fixtures=[f for f in fixtures if f[0] in names]
executions=0
with tempfile.TemporaryDirectory(prefix='aella-native-') as tmp:
 tmp=Path(tmp)
 for name,clj,scm,cases in fixtures:
  for syntax,source in [('cossack',clj),('gambit',scm)]:
   path=tmp/(name+'.'+syntax);path.write_text(source)
   exe=tmp/(name+'-'+syntax)
   subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),'--exact','--parameters','x','--compile-to',str(exe),'--gsc',a.gsc,'--numeric-library',str(a.numeric_library)],check=True,timeout=90)
   for arg,expected in cases:
    actual=subprocess.check_output([str(exe),arg],text=True,timeout=10).strip()
    assert actual==expected,(name,syntax,arg,expected,actual)
    executions+=1
   for bad in [[],['0.5'],['(exit 9)']]:
    result=subprocess.run([str(exe),*bad],capture_output=True,text=True,timeout=10)
    assert result.returncode!=0,(name,syntax,bad,result.stdout)
   print('PASS',name,syntax,flush=True)
report={'compiled_programs':len(fixtures)*2,'runtime_value_checks':executions,'invalid_argument_checks':len(fixtures)*6,'frontends':['cossack','gambit'],'numbers':'exact integers, rationals, complex; shared Cossack p-adic library'}
(a.output or ROOT/'results/native-compilation.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
