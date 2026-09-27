# Aella (Rascal + ANTLR) - Small Clojure-Style Core

This is a minimal, composable implementation that includes:

- **Type modes** (A/B/C/L/S taxonomy)
- **Phase-scoped evaluation** (macro/compile/runtime)
- **S-expression grammar** for ANTLR
- **Rascal semantics sketch** with evaluator and macroexpander

Directory layout:

- `rascal/Aella.rsc` - Rascal grammar + interpreter + phase/model config
- `antlr/Aella.g4`   - ANTLR4 grammar for Aella surface syntax
- `docs/`            - Notes and examples
- `rascal/Aellith.rsc` - Rascal grammar for Aellith conlang
- `antlr/Aellith.g4`   - ANTLR4 grammar for Aellith conlang
- `transitions/`      - [Checked pairwise expression compiler](transitions/README.md) for seven Clojure-family profiles and Gambit

## Features and taxonomy

Type modes define language personality:

- **Type-A**: Simple syntax mapping (no extra semantics)
- **Type-B**: Syntax + extra semantics (macros, phase rules)
- **Type-C**: Clojure-like: vectors, maps, keywords, namespaces
- **Type-L**: Common Lisp-inspired features
- **Type-S**: Scheme-inspired features

`Config` holds active modes and current phase.

## Phase-scoped evaluation

Phases are explicit:

- `PhaseMacro`   – macroexpansion only
- `PhaseCompile` – compile-time evaluation
- `PhaseRuntime` – runtime evaluation

Special forms are gated by phase and mode.

## Minimal usage concept

- Parse with ANTLR (or Rascal grammar) into a tree.
- Convert tree to `Expr`.
- Apply `macroexpand` in macro phase.
- Run `evalExpr` in runtime phase.



Aellith conlang includes compersion (co) as a primitive.

Aellith conlang includes compersion (co) and consent/care/risk/safety/trust/reciprocity primitives.


## Self-hosting

See SELFHOSTING.md for Docker-based static hosting.
