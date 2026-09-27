#!/usr/bin/env python3
"""Execute every emitted pair on installed runtimes; report missing runtimes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transitions.compiler import PROFILES, lower, emit, transition, evaluate

PROGRAMS = [
    '(+ 20 22)', '(let [x 7 y (+ x 1)] (* x y))',
    '((fn [x] (if (< x 0) (- 0 x) x)) -17)',
    '(if false 9 42)', '(not (= 2 3))',
    '(let [x 3] ((fn [y] (+ x y)) 4))',
    '(let [x 2 f (fn [y] (+ x y)) x 9] (f 3))',
    '(+ 9007199254740990 1)',
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cossack', default=os.environ.get('COSSACK', 'cossack'))
    parser.add_argument('--gsi', default='gsi')
    parser.add_argument('--gsc', default='gsc')
    parser.add_argument('--basilisp', default='basilisp')
    parser.add_argument('--squint', default='squint')
    parser.add_argument('--squint-project',type=Path,default=ROOT,
                        help='Project directory with squint-cljs installed for Node module resolution')
    parser.add_argument('--output', type=Path, default=ROOT/'results/transitions.json')
    parser.add_argument('--require-all',action='store_true',help='Fail if any runtime or Gambit compilation is unverified')
    args = parser.parse_args()
    binaries = {'clojure':'clojure', 'babashka':'bb', 'jank':'jank',
                'cossack':args.cossack, 'clojurescript-nbb':'nbb', 'gambit':args.gsi,
                'basilisp':args.basilisp,'squint':args.squint}
    report = {'fixtures':len(PROGRAMS), 'profiles':list(PROFILES),
              'ordered_pairs':len(PROFILES)*(len(PROFILES)-1), 'runtimes':{}}
    with tempfile.TemporaryDirectory(prefix='aella-check-') as tmp:
        tmp = Path(tmp)
        for target in PROFILES:
            binary = shutil.which(binaries.get(target, ''))
            if not binary:
                report['runtimes'][target] = {'status':'unverified', 'reason':'No configured executable'}
                continue
            binary=str(Path(binary).resolve())
            forms, expected = [], []
            for source in PROFILES:
                if source == target: continue
                for program in PROGRAMS:
                    ir = lower(program, 'clojure')
                    forms.append(transition(emit(ir,source),source,target))
                    value = evaluate(ir)
                    expected.append(('true' if value else 'false') if type(value) is bool else str(value))
            if target == 'gambit':
                code = '\n'.join('(write '+form+') (newline)' for form in forms)
                file = tmp/'suite.scm'; file.write_text(code+'\n')
                command = [binary, str(file)]
            else:
                code = '(do '+' '.join('(println '+form+')' for form in forms)+')'
                file = tmp/'suite.clj'; file.write_text(code+'\n')
                if target == 'jank':command = [binary,'run',str(file)]
                elif target == 'cossack':command = [binary,'eval',code]
                elif target == 'clojure':command = [binary,'-M',str(file)]
                elif target == 'basilisp':command = [binary,'run',str(file)]
                elif target == 'squint':command = [binary,'eval',code]
                else:command = [binary,str(file)]
            result = subprocess.run(command,text=True,capture_output=True,timeout=180,
                                    cwd=args.squint_project.resolve() if target=='squint' else ROOT)
            actual = result.stdout.strip().splitlines()
            if target == 'cossack' and actual and actual[-1]=='nil':actual.pop()
            if target == 'gambit':actual=[{'#t':'true','#f':'false'}.get(x,x) for x in actual]
            if result.returncode or actual != expected:
                raise RuntimeError(f'{target}: exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}')
            report['runtimes'][target] = {'status':'passed', 'executable':Path(binary).name, 'expressions':len(forms)}
            if target=='basilisp':
                report['runtimes'][target]['version']=subprocess.check_output([binary,'version'],text=True).strip()
            if target=='squint':
                manifest=args.squint_project/'node_modules/squint-cljs/package.json'
                report['runtimes'][target]['runtime_package_version']=json.loads(manifest.read_text())['version']
            print(f'PASS {target}: {len(forms)} expressions',flush=True)
        gsc=shutil.which(args.gsc)
        report['gambit_compilation']={'status':'unverified'}
        if gsc:
            # Exercise the public CLI from both actual surface syntaxes.
            for profile in ('clojure','gambit'):
                ir=lower(PROGRAMS[2],'clojure')
                source=tmp/(profile+'.src');source.write_text(emit(ir,profile))
                exe=tmp/(profile+'-compiled')
                subprocess.run([sys.executable,str(ROOT/'transitions/compiler.py'),
                    '--from',profile,'--to','gambit',str(source),'--gsc',gsc,
                    '--compile-to',str(exe)],check=True,timeout=180)
                result=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=30)
                assert result.stdout.strip()=='17',result
            report['gambit_compilation']={'status':'passed','frontends':['clojure','gambit']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    if args.require_all and (any(r['status']!='passed' for r in report['runtimes'].values())
                             or report['gambit_compilation']['status']!='passed'):
        raise SystemExit('Required runtime coverage is incomplete; see '+str(args.output))
    print(args.output)

if __name__=='__main__':main()
