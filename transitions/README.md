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
bounded arithmetic/comparison vocabulary, plus finite `loop/recur` and Scheme
named-let iteration. It verifies the closed expression
before emitting it, with a 10,000-step evaluation budget. All numeric operands
and intermediate results must be exact integers between ±(2^53−1). Functions
must eventually return an integer or boolean. This is deliberately stricter
than each individual runtime.

Scheme `let*` corresponds to Clojure `let`; unnamed parallel `let` is rejected.
Named-let initializers retain their parallel scope, while Clojure loop
initializers remain sequential. Tail calls have checked arity and cannot cross
a function or nested-loop boundary in the common contract. Function-level
`recur` remains part of the separate exact-native contract. Infinite loops and
loops that exceed the verification budget or integer range are rejected.

The target emitters preserve simultaneous recur rebinding and iteration-local
closure capture. On the tested Jank runtime, even plain `let` aliases in a
variable swap observe rebinding; the emitter materializes argument values
through identity calls. Basilisp and Squint closures use explicit factory
calls to capture current values instead of changing loop cells. Generated
names avoid all source names. These adaptations add overhead; no speed claim
is made. The source profiles use these stated Clojure lexical invariants,
including where a raw host runtime differs.
Tests must be recognizably boolean because Scheme and Clojure truthiness differ.
Namespaces, definitions, macros, reader extensions, foreign interop, effects,
collection values, general recursive programs, and the full numeric tower are outside
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
are reported as unverified, never as passing. `--require-all` turns any missing
runtime or native compiler into a failing check. All eight profiles now have
execution adapters and pass the checked-in fixture suite: 952 executions across
56 ordered pairs. This is evidence for the admitted subset, not full dialect
conformance.

Basilisp 0.5.1 and Squint 0.14.210 were tested using Python 3.12.8 and Node
24.11.0. Their dependency manifests are pinned under `runtime-deps/`. Install
them locally without changing global toolchains:

```sh
uv venv --python 3.12 target/basilisp-env
uv pip install --python target/basilisp-env/bin/python \
  -r transitions/runtime-deps/basilisp-requirements.txt
mkdir -p target/squint
cp transitions/runtime-deps/package*.json target/squint/
npm ci --prefix target/squint --ignore-scripts
```

Pass `--basilisp target/basilisp-env/bin/basilisp`,
`--squint target/squint/node_modules/.bin/squint`, and
`--squint-project target/squint` to the runtime checker, together with the
Cossack and Gambit executable paths shown above. Squint needs a project with
its runtime dependency available for Node's module resolution.

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
The shared p-adic calls also include unit-speed geodesics, the direct-loss
directional derivative, and a scalar direct-loss proximal update. These are
tested with runtime parameters from both source syntaxes; they do not implement
general model backpropagation or the paper's multi-parameter optimizers.
Sparse multivariate polynomial stages and their radial directional derivatives
also compile through the shared library. In exact native mode, Clojure vector
literals and Scheme `(list ...)` supply the nested numeric data for these APIs;
this is data transport, not a general collection or callable-vector compiler.
Polynomial stages can be composed into networks with `network-loss` and
`network-slope`, using the shared library's forward directional differentiation
and summed direct loss. Stagewise dependency bounds remain explicit; this is
not arbitrary analytic reverse-mode differentiation.
`network-coordinate-step` also compiles: it selects the least directional slope
for one explicit coordinate and clips the update at the next vertex. The
selected radius must be positive. This API returns the updated disk.
`network-optimizer-step` additionally carries Momentum/Adam state using the
shared backend's appendix G.1 recurrences and an explicit tie draw. It returns
the updated disk and next state. Exact-mode `nth` / Scheme `list-ref` access this
numeric data at nonnegative literal integer indices, allowing a compiled
kernel to reuse the state across updates without relying on dialect-specific
numeric index coercions.
`network-groups` and `network-train-step` compile the grouped scheduler too:
affine active-term groups, conservative general polynomial groups, persistent
awaiting-turn marks, explicit draws, and simultaneous first-vertex clipping.
Joint direction selection and minimal nonlinear coupling groups remain unfinished.
Disk negation, independent subtraction, representation accessors, a zero-radius
predicate, center norms, and hull seminorms also compile. Exact rational
decomposition and digit expansions preserve arbitrary precision; reconstruction
returns a rational approximation with an explicit p-adic error bound. See the
shared backend's `GAMBIT.md` for the distinction between representative data
and hull invariants. The zero-radius predicate is accepted in native conditions.
Unused p-adic code is not included in purely numeric executables.
Standalone exact programs also enable Gambit's `optimize-dead-definitions`,
so importing the shared numeric library need not retain every uncalled helper.
The admitted programs are closed and the shared library's top-level definitions
are procedures. Use `--keep-unused-definitions` when a custom library relies on
otherwise-unused definition initializers or definitions consumed elsewhere.
`tools/benchmark_native_pruning.py` compares identical expansion kernels with
and without this declaration, checking results while recording compilation
time and executable size. It does not measure runtime throughput.
The recorded [paired run](../results/native-pruning.json) compiled a 32-digit
expansion kernel in 215.98 seconds without pruning and 4.45 seconds with it;
executable size was 833,048 versus 103,736 bytes. This is one run on a shared
host, with dynamically linked library size excluded. Checked norm/valuation
wrappers preserve prime validation without retaining the whole dispatcher.
All 18 SRFI 141 division procedures also compile directly to Gambit's built-ins.
The Clojure surface uses `srfi.141/<name>`; Scheme uses the original unqualified
names. Cossack's pair-returning forms become numeric data, while Scheme's
`<mode>/` procedures retain multiple values. Scheme `call-with-values` supports
lambda consumers and `list`; the executable boundary prints a sole result
directly and multiple results as a Scheme list. This preserves the distinction
between a Cossack pair and Scheme multiple values inside the compiled program.
These division calls retain the integer-argument and nonzero-divisor contract.
`tools/check_native_srfi141.py` checks all procedures against an independent
integer oracle and direct Gambit, including rounding ties, negative divisors,
and integers exceeding 4,096 bits. No p-adic library is needed for these calls.
The exact-native compiler exposes `cossack.padic/classification-probabilities`,
`classification-loss`, and `classification-slope`, with Scheme names prefixed
`cx-`. These temperature-one heads take class disks; loss adds a class label,
and slope takes radial velocities before the label. Probabilities and
cross-entropy directional derivatives remain exact rationals. The loss itself
uses a floating logarithm and is therefore inexact; it can be returned directly
but cannot be passed to this compiler's exact-only arithmetic operators.
Zero seminorms are rejected as singular. `tools/check_native_classification.py`
checks both source syntaxes with runtime parameters, including 4,097-bit radii and losses near zero.

Exact-native mode also compiles shaped p-adic arrays through the shared
library: `cossack.padic/array`, `array-add`, `array-sub`, `array-mul`,
`array-neg`, and `array-power` (Scheme names `cx-array`, etc.). Construction
uses `prime shape centers radii`; the result is `(prime shape disks)` in
Scheme numeric-data notation. Fields are scalars or flat row-major lists of
the shape's size. Binary operations use trailing-axis broadcasting, retain
empty axes, and require equal primes. Rank-zero arrays provide scalar operands.
Powers use the correlated scalar disk rule rather than repeated independent
multiplication. `tools/check_native_arrays.py` exercises all six operations
from both syntaxes with runtime numeric parameters and invalid inputs.

Exact-native mode supports Clojure `loop/recur` and function-level `recur`, plus
tail-recursive Scheme named `let`. Recursion points have checked arity and
tail position. Recur arguments are evaluated before simultaneous rebinding;
closures retain their captured iteration values. Nested functions establish
their own Clojure recursion point. Clojure loop initializers are sequential;
Scheme named-let initializers use the surrounding environment in parallel.
Generated recursion names are private and cannot capture source bindings.
Named-let functions cannot escape as values in this subset, and calls to them
must be in tail position. Destructuring and named/multi-arity Clojure functions
remain unsupported. Native loops execute at runtime, without the common-mode
compile-time evaluation budget.

`tools/check_native_loops.py` checks compiled arithmetic loops and JVM Clojure
references, including 100,000 iterations and arbitrary-precision factorials.
`tools/check_compiled_training.py` compiles the entire state-carrying training
loop from both syntaxes and runs 40-step Momentum and Adam trajectories in the
resulting executables.

This mode does not claim arbitrary namespaces, macros, effects, general
recursion, or application translation, and extends beyond the bounded common-loop contract
of the other dialect pairs.

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
