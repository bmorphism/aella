import itertools,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from transitions.compiler import PROFILES,Unsupported,lower,emit,transition

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
 def test_reject_semantic_mismatches(self):
  for source in ['(* 9007199254740991 2)','(= true false)','(if 0 1 2)','(not 0)','9007199254740993','(let [+ 3] +)',
                 '(defn x [] 1)','(slurp "secret")','(fn [x x] x)','(let [x] x)','(+ 1 2) 3',
                 '(let [nil 3] nil)','(let [do (fn [x] (+ x 1))] (do 4))',
                 '(let [begin (fn [x] (+ x 1))] (begin 4))']:
   with self.subTest(source=source),self.assertRaises(Unsupported):lower(source,'clojure')
 def test_scheme_parallel_let_not_silently_sequential(self):
  with self.assertRaises(Unsupported):lower('(let ((x 1)) x)','gambit')
if __name__=='__main__':unittest.main()
