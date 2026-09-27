#!/usr/bin/env python3
"""Compile exact probabilities and directional cross-entropy derivatives."""
import argparse,json,math,subprocess,sys,tempfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(let [ds [(cossack.padic/disk p 0 radius) (cossack.padic/disk p 0 1/3)]]
 [(nth (cossack.padic/classification-probabilities ds) 0)
  (cossack.padic/classification-slope ds [1 0] 0)
  (cossack.padic/classification-loss ds 0)])'''
scm='''(let* ((ds (list (cx-disk p 0 radius) (cx-disk p 0 1/3))))
 (list (list-ref (cx-classification-probabilities ds) 0)
       (cx-classification-slope ds (list 1 0) 0)
       (cx-classification-loss ds 0)))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-classification-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
    '--exact','--parameters','p','radius','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
    '--compile-to',str(exe)],check=True,timeout=600)
  for radius in (1,2,10**100,2**4096,Fraction(1,2**100)):
   actual=subprocess.check_output([str(exe),'3',str(radius)],text=True,timeout=30).strip()
   probability,slope,loss=actual[1:-1].split()
   expected=1/(1+3*Fraction(radius))
   assert Fraction(probability)==expected,(syntax,actual)
   assert Fraction(slope)==(1-expected)/radius,(syntax,actual)
   expected_loss=math.log1p(3*float(radius)) if radius<1 else math.log(1+3*radius)
   assert math.isclose(float(loss),expected_loss,rel_tol=1e-14),(syntax,actual)
   checks+=1
  for args in ([],['4','1'],['3','0'],['3','-1'],['3','0.5']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled classification',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
        'temperature':1,'probabilities_and_derivatives':'exact rational','cross_entropy':'binary64'}
(ROOT/'results/native-classification.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
