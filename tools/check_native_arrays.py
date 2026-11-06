#!/usr/bin/env python3
"""Compile p-adic broadcasting from both supported exact surface syntaxes."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(let [a (cossack.padic/array p [2 1] [x 2] 1/3)
             b (cossack.padic/array p [1 3] [10 20 30] 0)
             out (cossack.padic/array-sub (cossack.padic/array-add a b) b)
             twice (cossack.padic/array-neg (cossack.padic/array-neg out))
             squared (cossack.padic/array-power twice n)
             final (cossack.padic/array-mul squared (cossack.padic/array p [] 1 0))]
         [(nth final 1) (cossack.padic/center (nth (nth final 2) 0))
          (cossack.padic/radius (nth (nth final 2) 0))
          (cossack.padic/center (nth (nth final 2) 5))])'''
scm='''(let* ((a (cx-array p (list 2 1) (list x 2) 1/3))
              (b (cx-array p (list 1 3) (list 10 20 30) 0))
              (out (cx-array-sub (cx-array-add a b) b))
              (twice (cx-array-neg (cx-array-neg out)))
              (squared (cx-array-power twice n))
              (final (cx-array-mul squared (cx-array p (list) 1 0))))
         (list (list-ref final 1) (cx-disk-center (list-ref (list-ref final 2) 0))
               (cx-disk-radius (list-ref (list-ref final 2) 0))
               (cx-disk-center (list-ref (list-ref final 2) 5))))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-arrays-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
    '--exact','--parameters','p','x','n','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
    '--compile-to',str(exe)],check=True,timeout=600)
  for args,expected in [(['3','1','2'],'((2 3) 1 1/3 4)'),
                         (['3','1/3','2'],'((2 3) 1/9 1 4)'),
                         (['3',str(10**60),'0'],'((2 3) 1 0 1)')]:
   actual=subprocess.check_output([str(exe),*args],text=True,timeout=30).strip()
   assert actual==expected,(syntax,args,actual,expected)
   checks+=1
  for args in ([],['4','1','2'],['3','1','-1'],['3','1','1/2'],['3','0.5','2']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled p-adic arrays',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
        'operations':['array','array-add','array-sub','array-mul','array-neg','array-power']}
(ROOT/'results/native-arrays.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
