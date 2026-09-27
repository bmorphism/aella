# Checked pairwise expression transitions

`compiler.py` translates a closed, pure expression subset between eight named
profiles: Clojure, Babashka, Jank, Cossack, ClojureScript through nbb, Basilisp,
Squint, and Gambit Scheme. Every ordered pair is accepted by the same pipeline:
parse source → checked IR → emit target. That gives 42 Clojure-family pairs and
14 additional pairs involving Gambit. These profiles are an explicit inventory,
not an assertion that every dialect or library used elsewhere is covered.

The implementation is Python 3, separate from Aella's Rascal semantics sketch.
It supports integer literals, booleans, sequential lexical bindings, closures,
single-arity anonymous functions, application, boolean conditionals, and a
bounded arithmetic/comparison vocabulary. It verifies the closed expression
before emitting it, with a 10,000-step evaluation budget. All numeric operands
and intermediate results must be exact integers between ±(2^53−1). Functions
must eventually return an integer or boolean. This is deliberately stricter
than each individual runtime.

Scheme `let*` corresponds to Clojure `let`; Scheme parallel `let` is rejected.
Tests must be recognizably boolean because Scheme and Clojure truthiness differ.
Namespaces, definitions, macros, reader extensions, foreign interop, effects,
collection values, recursive programs, and the full numeric tower are outside
this subset and are rejected. This does not translate arbitrary applications.

```sh
python3 transitions/compiler.py --from clojure --to gambit expression.clj
python3 transitions/compiler.py --from clojure --to gambit expression.clj \
  --compile-to target/expression --gsc /path/to/gsc
python3 -m unittest discover -s tests -v
python3 tools/check_transitions.py --cossack /path/to/cossack \
  --gsi /path/to/gsi --gsc /path/to/gsc
```

The compile option emits Scheme, invokes Gambit's native compiler, and produces
an executable that prints the result. Both Gambit and Clojure surface inputs
use this compilation path. The runtime checker checks actual output separately
from IR roundtrips, and writes `results/transitions.json`. Unavailable runtimes
are reported as unverified, never as passing. Basilisp and Squint currently
have syntax profiles only; their execution adapters remain to be implemented.

## Categorical interpretation and its limits

The operational objects here are dialect-indexed sets of accepted expressions;
morphisms are partial translations preserving the checked result. Composition
through the IR preserves that result on the admitted domain. A parameterized
translation can carry a profile, numeric contract, and compiler configuration;
a feedback path can return counterexamples from a target runtime to refine that
contract. These are useful design constraints for a Para/Optic account.

This implementation does **not** define the double category Cat#, prove a
geometric morphism, or construct Optic(Para(Cat#)). Those claims require explicit
objects, horizontal and vertical maps, cells, a monoidal action, and laws. The
roundtrip and execution checks establish finite observations, not those proofs.
