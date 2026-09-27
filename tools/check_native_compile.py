#!/usr/bin/env python3
"""Compile both surface syntaxes and execute with values unavailable at compile time."""
import argparse,json,random,subprocess,sys,tempfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
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
 ('norm','(cossack.padic/norm 3 x)','(cx-norm 3 x)',[('5/9','9'),('81','1/81')]),
]
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
(ROOT/'results/native-compilation.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
