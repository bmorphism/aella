# Aellith-Quantum (heuristic design)

Goal: maximize learnability and compressibility under a Solomonoff-style prior
while remaining robust to noisy classical/quantum channels. This is a design
heuristic, not a proven optimum.

## Phonetic codebook

- Use short CV/CVC forms with high edit distance between primitives.
- Keep consonants distinct in place/manner to reduce confusion.
- Prefer reversible, prefix-safe tokens for easy parsing.

Primitive phonetics (ASCII guide):
- en /en/  envy
- in /in/  insecurity
- po /po/  possessiveness
- th /t-h/ threat detection (aspirated t)
- co /ko/  compersion
- ce /tse/ consent
- ca /ka/  care
- ri /ri/  risk
- sa /sa/  safety
- tr /tr/  trust
- re /re/  reciprocity

## Role marking

- Entities are tagged with role suffixes: -a (experiencer), -b (rival/other), -c (bond/context).
- Role suffixes make arguments explicit, aiding algorithmic inference.

## Channel robustness

- Optional intensity markers (ka/ke/ku) provide coarse confidence coding.
- Optional evidential markers (he/na) encode hedging or negation.
- Tokens are short, low-entropy, and compositional for fast Bayesian updates.

## Grammar summary

Clause forms:
- monad: prim entity [intensity] [evidential]
- dyad:  prim entity entity [intensity] [evidential]
- triad: prim entity entity entity [intensity] [evidential]

Examples:
- en mia-a rau-b ke
- in mia-a lin-c he
- po mia-a rau-b lin-c
- ce mia-a lin-c ke
- co mia-a lin-c ka
- ri mia-a evt-c ku na

## Solomonoff rationale (informal)

- Small token set reduces model complexity.
- Explicit role tags reduce latent-variable ambiguity.
- Optional markers encode uncertainty without new syntax.
- Short tokens make descriptions concise and predictable.

## Parity markers

- Optional p0/p1/p2 suffix adds a lightweight checksum bit for noisy channels.

