#!/usr/bin/env python3
"""Compile SRFI 141 from both surfaces and check an independent integer oracle."""
import argparse,json,random,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from transitions.compiler import SRFI141_MODES,read
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--gsi',required=True)
a=p.parse_args()

def divide(mode,n,d):
 q=n//d
 if mode=='ceiling':q=-((-n)//d)
 elif mode=='truncate':q=(abs(n)//abs(d))*(-1 if (n<0)!=(d<0) else 1)
 elif mode=='round':
  twice=2*abs(n-d*q)
  if twice>abs(d) or twice==abs(d) and q%2:q+=1
 elif mode in ('euclidean','balanced'):
  q=n//d if d>0 else -((-n)//d)
  if mode=='balanced' and 2*(n-d*q)>=abs(d):q+=1 if d>0 else -1
 r=n-d*q
 assert n==d*q+r and abs(r)<abs(d)
 return q,r

rows=[(n,d) for n in (-2**130-7,-8,-7,-6,-2,-1,0,1,2,6,7,8,2**130+7)
      for d in (-4,-3,3,4)]
rows += [(sign*(2**4096+123),d) for sign in (-1,1) for d in (-2**129-3,2**129+3)]
rng=random.Random(141)
rows += [(rng.randrange(-2**200,2**200),rng.choice((-1,1))*rng.randrange(1,2**100)) for _ in range(32)]
clj='['+' '.join(f'[(srfi.141/{m}/ x y) (srfi.141/{m}-quotient x y) (srfi.141/{m}-remainder x y)]' for m in SRFI141_MODES)+']'
scm='(list '+' '.join(f'(call-with-values (lambda () ({m}/ x y)) (lambda (q r) (list (list q r) ({m}-quotient x y) ({m}-remainder x y))))' for m in SRFI141_MODES)+')'
checks=0;invalid=0
with tempfile.TemporaryDirectory(prefix='aella-srfi141-') as directory:
 tmp=Path(directory)
 oracle=tmp/'reference.scm'
 oracle.write_text('\n'.join(f'(let ((x {n}) (y {d})) (write {scm}) (newline))' for n,d in rows))
 reference=subprocess.check_output([a.gsi,str(oracle)],text=True,timeout=20).splitlines()
 expected=[]
 for (n,d),line in zip(rows,reference):
  value=tuple((divide(m,n,d),*divide(m,n,d)) for m in SRFI141_MODES)
  assert read(line,exact=True,clojure_numbers=False)==value,(n,d,line,value)
  expected.append(value)
 assert len(reference)==len(rows)
 for name,syntax,source,pairs_only in [('all-cossack','cossack',clj,False),('all-gambit','gambit',scm,False),
     ('pair-cossack','cossack','(srfi.141/round/ x y)',True),('pair-gambit','gambit','(round/ x y)',True)]:
  path=tmp/(name+'.src');path.write_text(source);exe=tmp/name
  subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),'--from',syntax,'--to','gambit',str(path),
                 '--exact','--parameters','x','y','--gsc',a.gsc,'--compile-to',str(exe)],check=True,timeout=60)
  for (n,d),value in zip(rows,expected):
   actual=subprocess.check_output([str(exe),str(n),str(d)],text=True,timeout=10).strip()
   want=divide('round',n,d) if pairs_only else value
   assert read(actual,exact=True,clojure_numbers=False)==want,(name,n,d,actual,want)
   checks+=1 if pairs_only else 18
  for bad in ([],['1'],['1','0'],['1/2','3'],['3','1/2'],['1+2i','3'],['0.5','3'],['(exit 9)','3']):
   result=subprocess.run([str(exe),*bad],text=True,capture_output=True,timeout=10)
   assert result.returncode!=0,(name,bad,result.stdout)
   invalid+=1
  print('PASS',name,flush=True)
report={'compiled_programs':4,'procedures':18,'division_cases':len(rows),
        'compiled_result_comparisons':checks,'direct_gambit_oracle_comparisons':len(rows)*18,
        'invalid_argument_checks':invalid,'largest_input_bits':4097,
        'frontends':['cossack','gambit'],'multiple_values':'Scheme preserved; Cossack pairs collected'}
(ROOT/'results/native-srfi141.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
