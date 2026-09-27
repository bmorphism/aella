#!/usr/bin/env python3
"""Run complete stateful p-adic training loops as native executables."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(loop [n 0N disks [(cossack.padic/disk 3 0 1) (cossack.padic/disk 3 0 1)] state []]
  (if (< n steps)
    (let [update (cossack.padic/network-train-step [] disks [23 14] 1 [mode 1/2 1/2 1/100] state [[0 0] [0 0]])]
      (recur (+' n 1) (nth update 0) (nth update 1)))
    (< (cossack.padic/network-loss [] disks [23 14]) 1/1000)))'''
scm='''(let loop ((n 0) (disks (list (cx-disk 3 0 1) (cx-disk 3 0 1))) (state (list)))
  (if (< n steps)
    (let* ((update (cx-network-train-step (list) disks (list 23 14) 1 (list mode 1/2 1/2 1/100) state (list (list 0 0) (list 0 0)))))
      (loop (+ n 1) (list-ref update 0) (list-ref update 1)))
    (< (cx-network-loss (list) disks (list 23 14)) 1/1000)))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-training-loop-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
                 '--exact','--parameters','steps','mode','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
                 '--compile-to',str(exe)],check=True,timeout=600)
  for mode in (0,1):
   for steps,expected in [(0,'#f'),(40,'#t')]:
    actual=subprocess.check_output([str(exe),str(steps),str(mode)],text=True,timeout=30).strip()
    assert actual==expected,(syntax,mode,steps,actual,expected)
    checks+=1
  for args in ([],['40'],['0.5','0'],['40','2']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled 40-step Momentum and Adam',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
        'optimizers':['Momentum','Adam'],'training_steps':40,'loss_threshold':'1/1000',
        'execution':'Whole loop in native executable; no Cossack/Python interpreter needed for evaluation'}
(ROOT/'results/compiled-training-loops.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
