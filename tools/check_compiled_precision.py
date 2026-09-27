#!/usr/bin/env python3
"""Compile explicit precision projection in both training syntaxes."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
a=p.parse_args()
clj='''(let [seed (cossack.padic/round-training [(cossack.padic/disk 3 0 1) (cossack.padic/disk 3 0 1)] [] bits)
 config (if (= mode 2) [0 0 0 1/100] [mode 1/2 1/2 1/100])]
 (loop [n 0 disks (nth seed 0) state (nth seed 1)]
  (if (< n steps)
   (let [result (cossack.padic/network-classification-train-step [] disks 0 1 config state [[0 0] [0 0]])
         projected (cossack.padic/round-training (nth result 0) (nth result 1) bits)]
    (recur (+' n 1) (nth projected 0) (nth projected 1)))
   (> (nth (cossack.padic/network-classification-probabilities [] disks) 0) 999/1000))))'''
scm='''(let* ((seed (cx-round-training (list (cx-disk 3 0 1) (cx-disk 3 0 1)) (list) bits))
 (config (if (= mode 2) (list 0 0 0 1/100) (list mode 1/2 1/2 1/100))))
 (let loop ((n 0) (disks (list-ref seed 0)) (state (list-ref seed 1)))
  (if (< n steps)
   (let* ((result (cx-network-classification-train-step (list) disks 0 1 config state (list (list 0 0) (list 0 0))))
          (projected (cx-round-training (list-ref result 0) (list-ref result 1) bits)))
    (loop (+ n 1) (list-ref projected 0) (list-ref projected 1)))
   (> (list-ref (cx-network-classification-probabilities (list) disks) 0) 999/1000))))'''
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-precision-') as directory:
 tmp=Path(directory)
 for syntax,source in [('cossack',clj),('gambit',scm)]:
  path=tmp/(syntax+'.src');path.write_text(source);exe=tmp/syntax
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
   '--exact','--parameters','steps','mode','bits','--gsc',a.gsc,'--numeric-library',str(a.numeric_library),
   '--compile-to',str(exe)],check=True,timeout=600)
  for mode in (0,1,2):
   for steps,expected in [(0,'#f'),(40,'#t')]:
    actual=subprocess.check_output([str(exe),str(steps),str(mode),'64'],text=True,timeout=60).strip()
    assert actual==expected,(syntax,mode,steps,actual)
    checks+=1
  for args in ([],['40','0'],['40','3','64'],['0','0','1'],['0','0','2.0']):
   result=subprocess.run([str(exe),*args],text=True,capture_output=True,timeout=30)
   assert result.returncode!=0,(syntax,args,result.stdout)
   invalid+=1
  print('PASS compiled precision',syntax,flush=True)
report={'compiled_programs':2,'runtime_value_checks':checks,'invalid_argument_checks':invalid,
 'training_steps':40,'significant_bits':64,'optimizers':['GD','Momentum','Adam'],'target_probability_min':'999/1000'}
(ROOT/'results/compiled-precision.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
