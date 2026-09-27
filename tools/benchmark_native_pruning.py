#!/usr/bin/env python3
"""Paired compilation comparison; measures build time and size, not runtime speed."""
import argparse,hashlib,json,platform,re,subprocess,sys,tempfile,time
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from transitions.compiler import lower,emit,native_program,read
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gsc',required=True)
p.add_argument('--numeric-library',type=Path,required=True)
p.add_argument('--output',type=Path,default=ROOT/'results/native-pruning.json')
a=p.parse_args()
library=a.numeric_library.resolve()
dependencies={}
def collect(path):
 if str(path) in dependencies:return
 content=path.read_bytes();dependencies[str(path)]=hashlib.sha256(content).hexdigest()
 for name in re.findall(r'\(include "([^"]+)"\)',content.decode()):collect((path.parent/name).resolve())
collect(library)
expression=emit(lower('(cossack.padic/expansion 3 x 32)','cossack',exact=True,parameters=['x']),'gambit',exact=True)
programs={prune:native_program(expression,['x'],library,prune=prune) for prune in (False,True)}
assert programs[True]=='(declare (optimize-dead-definitions))\n'+programs[False]
def expected(text):
 x=Fraction(text);n=abs(x.numerator);d=x.denominator;v=0
 if n:
  while n%3==0:n//=3;v+=1
  while d%3==0:d//=3;v-=1
 unit=x/Fraction(3)**v;digits=[]
 for _ in range(32):
  digit=unit.numerator*pow(unit.denominator%3,-1,3)%3
  digits.append(digit);unit=(unit-digit)/3
 return v,tuple(digits)
measurements={}
with tempfile.TemporaryDirectory(prefix='aella-pruning-') as directory:
 tmp=Path(directory)
 for prune in (False,True):
  label='pruned' if prune else 'unpruned';source=tmp/(label+'.scm');exe=tmp/label
  source.write_text(programs[prune])
  start=time.perf_counter()
  subprocess.run([a.gsc,'-exe','-o',str(exe),str(source)],check=True,timeout=600)
  seconds=time.perf_counter()-start
  for value in ('0','-1','1/6','7/9'):
   actual=subprocess.check_output([str(exe),value],text=True,timeout=10)
   assert read(actual,exact=True,clojure_numbers=False)==expected(value),(label,value,actual)
  measurements[label]={'compile_seconds':seconds,'executable_bytes':exe.stat().st_size,
                       'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'checked_inputs':4}
  print(label,measurements[label],flush=True)
report={'kernel':'32-digit exact rational p-adic expansion','measurements':measurements,
        'compile_time_ratio':measurements['unpruned']['compile_seconds']/measurements['pruned']['compile_seconds'],
        'executable_size_ratio':measurements['unpruned']['executable_bytes']/measurements['pruned']['executable_bytes'],
        'platform':platform.platform(),'gsc':str(Path(a.gsc).resolve()),'library_dependencies':dependencies,
        'method':'One paired build on a shared host; identical sources except declaration. Dynamic library size excluded. No runtime throughput comparison.'}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS paired build comparison',flush=True)
