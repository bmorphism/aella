# Skills loaded: SICP, SDF, SRFI

This project aligns the small Aella interpreter with:

- **SICP**: metacircular eval/apply, environment model, special forms.
- **SDF**: generic procedures and compositional design, phase gating as additive extensions.
- **SRFI**: portable Scheme features to map onto Aella modes.

## Mapping into Aella

- **SICP (Ch4/Ch5)**: informs `evalExpr` + `apply` separation, lexical scoping model.
- **SDF (Ch1/Ch3/Ch5/Ch9)**: encourages generic dispatch extension points for builtins.
- **SRFI**: optional library layer for Type-S mode (Scheme-inspired). Suggested SRFIs:
  - SRFI-1 (list library)
  - SRFI-9 (record types)
  - SRFI-64 (tests)
  - SRFI-204 (pattern matching)

## Phase-scoped evaluation

Macro/compile/runtime phases are modeled after SICP’s metacircular evaluators and SDF’s additive programming: new behavior is added by registering phase-gated forms rather than modifying core evaluation.

