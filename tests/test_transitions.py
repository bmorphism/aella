import itertools,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from transitions.compiler import PROFILES,Unsupported,lower,emit,transition,native_program,evaluate

class Transitions(unittest.TestCase):
 def test_every_directed_pair(self):
  programs=['(+ 20 22)','(let [x 7 y (+ x 1)] (* x y))',
            '((fn [x] (if (< x 0) (- 0 x) x)) -17)',
            '(if false 9 42)','(not (= 2 3))',
            '(let [x 3] ((fn [y] (+ x y)) 4))']
  for text in programs:
   ir=lower(text,'clojure')
   for source,target in itertools.permutations(PROFILES,2):
    with self.subTest(source=source,target=target,text=text):
     output=transition(emit(ir,source),source,target)
     self.assertEqual(lower(output,target),ir)
 def test_loop_pairwise_semantics(self):
  from tools.check_transitions import PROGRAMS
  for text in PROGRAMS[8:]:
   ir=lower(text,'clojure');expected=evaluate(ir)
   for source,target in itertools.permutations(PROFILES,2):
    with self.subTest(source=source,target=target,text=text):
     output=transition(emit(ir,source),source,target)
     self.assertEqual(evaluate(lower(output,target)),expected)
 def test_reject_semantic_mismatches(self):
  for source in ['(* 9007199254740991 2)','(= true false)','(if 0 1 2)','(not 0)','9007199254740993','(let [+ 3] +)',
                 '(defn x [] 1)','(slurp "secret")','(fn [x x] x)','(let [x] x)','(+ 1 2) 3',
                 '(let [nil 3] nil)','(let [do (fn [x] (+ x 1))] (do 4))',
                 '(let [begin (fn [x] (+ x 1))] (begin 4))']:
   with self.subTest(source=source),self.assertRaises(Unsupported):lower(source,'clojure')
 def test_scheme_parallel_let_not_silently_sequential(self):
  with self.assertRaises(Unsupported):lower('(let ((x 1)) x)','gambit')
 def test_dynamic_exact_compilation(self):
  ir=lower("(+' (*' x x) 1/3)",'cossack',exact=True,parameters=['x'])
  self.assertIn('aella-op * x x',emit(ir,'gambit',exact=True))
  self.assertIn('string->number',native_program(emit(ir,'gambit',exact=True),['x']))
  self.assertEqual(lower('123456789012345678901234567890N','cossack',exact=True),
                   ('int',123456789012345678901234567890))
 def test_native_contract_rejections(self):
  for text,profile,parameters in [
      ('(+ x 1)','cossack',['x']), ('1N','gambit',[]),
      ('(srfi.141/floor/ 1)','cossack',[]),
      ('(call-with-values (lambda () 1))','gambit',[]),
      ('(let [call-with-values 1] call-with-values)','cossack',[]),
      ('(nth [1 2] 1/2)','cossack',[]), ('(nth [1 2] x)','cossack',['x']),
      ('(list-ref (list 1 2) -1)','gambit',[]),
      ("(+' 1 2)",'gambit',[]), ('(if x 1 2)','cossack',['x']),
      ('x','cossack',['x','x']), ('aella-op','cossack',['aella-op']),
      ('(let [cx-disk 3] cx-disk)','cossack',[])]:
   with self.subTest(text=text),self.assertRaises(Unsupported):
    lower(text,profile,exact=True,parameters=parameters)
  with self.assertRaises(Unsupported):native_program('(cx-disk 3 1 0)',[])
 def test_recursive_contract_rejections(self):
  invalid=[
   ('cossack','(recur 1)'),
   ('cossack',"(loop [n 1] (+' 1 (recur 0)))"),
   ('cossack','(loop [n 1] (recur))'),
   ('cossack','(loop [n 1] [(recur 0)])'),
   ('cossack','(loop [n 1] (let [x (recur 0)] x))'),
   ('cossack','(loop [n 1] (fn [a b] (recur 0)))'),
   ('cossack','(loop [n 1 n 2] n)'),
   ('gambit','(let loop ((n 1)) (+ 1 (loop 0)))'),
   ('gambit','(let loop ((n 1)) (loop))'),
   ('gambit','(let loop ((n 1)) loop)'),
  ]
  for profile,source in invalid:
   with self.subTest(source=source),self.assertRaises(Unsupported):lower(source,profile,exact=True)
  for source,profile in [
   ('(loop [n 0] (recur (+ n 1)))','clojure'),
   ('(loop [n 9007199254740991] (recur (+ n 1)))','clojure'),
   ('(let outer ((n 1)) ((lambda () (outer 0))))','gambit'),
   ('(let outer ((n 1)) (let inner ((m 1)) (outer 0)))','gambit')]:
   with self.subTest(source=source),self.assertRaises(Unsupported):lower(source,profile)
  with self.assertRaises(Unsupported):emit(lower('(fn [n] (recur n))','clojure',exact=True),'clojure')
if __name__=='__main__':unittest.main()
