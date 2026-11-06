#!/usr/bin/env python3
"""Compile complete polynomial classification training from both syntaxes."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(let [stages [[[[1 [1]]] [[1 [0]]]]]
             config (if (= mode 2) [0 0 0 1/100] [mode 1/2 1/2 1/100])]
 (loop [n 0 disks [(cossack.padic/disk 3 0 1)] state []]
  (if (< n steps)
    (let [result (cossack.padic/network-classification-train-step stages disks 0 1 config state [[0 0]])]
      (recur (+' n 1) (nth result 0) (nth result 1)))
    (> (nth (cossack.padic/network-classification-probabilities stages disks) 0) 999/1000))))'''
scm='''(let* ((stages (list (list (list (list 1 (list 1))) (list (list 1 (list 0))))))
              (config (if (= mode 2) (list 0 0 0 1/100) (list mode 1/2 1/2 1/100))))
 (let loop ((n 0) (disks (list (cx-disk 3 0 1))) (state (list)))
  (if (< n steps)
    (let* ((result (cx-network-classification-train-step stages disks 0 1 config state (list (list 0 0)))))
      (loop (+ n 1) (list-ref result 0) (list-ref result 1)))
    (> (list-ref (cx-network-classification-probabilities stages disks) 0) 999/1000))))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-classification-training-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
    '--exact','--parameters','steps','mode','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
    '--compile-to',str(exe)],check=True,timeout=600)
  for mode in (0,1,2):
   for steps,expected in [(0,'#f'),(12,'#t')]:
    actual=subprocess.check_output([str(exe),str(steps),str(mode)],text=True,timeout=60).strip()
    assert actual==expected,(syntax,mode,steps,actual)
    checks+=1
  for args in ([],['12'],['12','3'],['12','0.5']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled classification training',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
        'training_steps':12,'optimizers':['GD','Momentum','Adam'],'target_class_probability_threshold':'999/1000'}
(ROOT/'results/compiled-classification-training.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
