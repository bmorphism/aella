#!/usr/bin/env python3
"""Compile weighted minibatch training and all four public batch operations."""
import argparse,json,math,subprocess,sys,tempfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(let [stages [[[[1 [1]]] [[1 [0]]]]]
             batch [[stages 0 weight] [stages 1 1]]
             initial [(cossack.padic/disk 3 0 1)]
             config (if (= mode 2) [0 0 0 1/100] [mode 1/2 1/2 1/100])
             loss (cossack.padic/classification-batch-loss batch initial)
             groups (cossack.padic/classification-batch-groups batch initial)
             slope (cossack.padic/classification-batch-slope batch initial [1])]
 (loop [n 0 disks initial state []]
  (if (< n steps)
    (let [result (cossack.padic/classification-batch-train-step batch disks 1 config state [[0 0]])]
      (recur (+' n 1) (nth result 0) (nth result 1)))
    [loss groups slope (= (nth (cossack.padic/network-classification-probabilities stages disks) 0) (/ weight (+' weight 1)))])))'''
scm='''(let* ((stages (list (list (list (list 1 (list 1))) (list (list 1 (list 0))))))
              (batch (list (list stages 0 weight) (list stages 1 1)))
              (initial (list (cx-disk 3 0 1)))
              (config (if (= mode 2) (list 0 0 0 1/100) (list mode 1/2 1/2 1/100)))
              (loss (cx-classification-batch-loss batch initial))
              (groups (cx-classification-batch-groups batch initial))
              (slope (cx-classification-batch-slope batch initial (list 1))))
 (let loop ((n 0) (disks initial) (state (list)))
  (if (< n steps)
    (let* ((result (cx-classification-batch-train-step batch disks 1 config state (list (list 0 0)))))
      (loop (+ n 1) (list-ref result 0) (list-ref result 1)))
    (list loss groups slope (= (list-ref (cx-network-classification-probabilities stages disks) 0) (/ weight (+ weight 1)))))))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-classification-batch-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
    '--exact','--parameters','steps','mode','weight','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
    '--compile-to',str(exe)],check=True,timeout=600)
  for mode in (0,1,2):
   for steps,weight,expected in [(0,3,'#f'),(12,3,'#t'),(12,1,'#t')]:
    actual=subprocess.check_output([str(exe),str(steps),str(mode),str(weight)],text=True,timeout=60).strip()
    loss,groups,slope,recovered=actual[1:-1].split()
    assert math.isclose(float(loss),math.log(2),rel_tol=1e-14),(syntax,actual)
    assert groups=='((0))' and Fraction(slope)==Fraction(weight-1,2*(weight+1)),(syntax,actual)
    assert recovered==expected,(syntax,mode,steps,weight,actual)
    checks+=1
  for args in ([],['12','0'],['12','3','3'],['12','0','-1'],['12','0','0.5']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled classification minibatch',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
        'training_steps':12,'optimizers':['GD','Momentum','Adam'],'weighted_frequencies':['3/4','1/2']}
(ROOT/'results/compiled-classification-batch.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
