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

## Dynamic native numeric compilation

`--exact` selects a separate native compilation contract for Clojure, Cossack,
or Gambit input, targeting Gambit. It admits arbitrary exact integers, ratios,
complex operations, and Cossack's p-adic operations. `--parameters x y` declares
runtime executable arguments. These expressions are not evaluated during
compilation, and their inputs are not restricted to 53-bit integers.

For Clojure/Cossack input, use the promoting binary operators `+'`, `-'`, and
`*'`; `/` performs exact division. Ordinary checked-long arithmetic is rejected
in this mode because unbounded Scheme arithmetic would change its semantics.
Gambit input uses its ordinary exact numeric operators. Native arguments use
Scheme numeric spelling (including ratios and rectangular complex numbers),
are parsed with `string->number`, and must be exact numbers. Executables print
Scheme representations. Invalid arguments or counts fail at runtime.

```sh
python3 transitions/compiler.py --from cossack --to gambit kernel.clj \
  --exact --parameters x --compile-to target/kernel --gsc /path/to/gsc \
  --numeric-library /path/to/cossack-lisp/gambit/numeric.scm
python3 tools/check_native_compile.py --gsc /path/to/gsc \
  --numeric-library /path/to/cossack-lisp/gambit/numeric.scm
```

The optional numeric-library argument includes Cossack's actual Scheme numeric
implementation; it is required for p-adic operations. This shares disk geometry
with the interpreter instead of substituting a finite residue approximation.
Compilation checks exercise both surface syntaxes with large runtime inputs,
lexical capture, exact complex multiplication, and p-adic power/distance.
This mode does not claim arbitrary namespace, macro, effect, or recursive-program
support, and does not expand the common contract of the other dialect pairs.

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
