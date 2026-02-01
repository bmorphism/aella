module aella::Aellith

// ============================================================================
// Aellith - minimal conlang built from Aella jealousy primitives
// ============================================================================

// --- Lexical ---
lexical Word = [a-z][a-z]+;
lexical Role = "-" [abc];
lexical Primitive = "en" | "in" | "po" | "th" | "co" | "ce" | "ca" | "ri" | "sa" | "tr" | "re";
lexical Evidential = "he" | "na";
lexical Intensity = "ka" | "ke" | "ku";
lexical Parity = "p0" | "p1" | "p2";
lexical Scope = "sA" | "sB" | "sC" | "sX";
lexical Phase = "pm" | "pc" | "pr";

layout Whitespace = [\ \t\n\r]*;

// --- Syntax ---
syntax Entity
  = ent: Word Role
  ;

syntax Clause
  = triad: Scope? Phase? Primitive Entity Entity Entity Intensity? Evidential? Parity?
  | dyad: Scope? Phase? Primitive Entity Entity Intensity? Evidential? Parity?
  | monad: Scope? Phase? Primitive Entity Intensity? Evidential? Parity?
  ;

start syntax AellithDoc
  = Clause ("." Clause)* "."?
  ;

// --- AST ---
data Expr
  = EEntity(str name, str role)
  | EClause(str prim, list[Expr] entities, str intensity, str evidential, str parity, str scope, str phase)
  ;

// --- Tree -> AST ---
Expr toEntity(Tree t) {
  switch (t) {
    case (ent): return EEntity("<Word>", "<Role>");
  }
  throw "Expected Entity";
}

Expr toClause(Tree t) {
  switch (t) {
    case (triad): return EClause(
      "<Primitive>",
      [toEntity("<Entity 0>"), toEntity("<Entity 1>"), toEntity("<Entity 2>")],
      "<Intensity>" == "" ? "ke" : "<Intensity>",
      "<Evidential>" == "" ? "he" : "<Evidential>",
      "<Parity>" == "" ? "p0" : "<Parity>",
      "<Scope>" == "" ? "sX" : "<Scope>",
      "<Phase>" == "" ? "pr" : "<Phase>"
    );
    case (dyad): return EClause(
      "<Primitive>",
      [toEntity("<Entity 0>"), toEntity("<Entity 1>")],
      "<Intensity>" == "" ? "ke" : "<Intensity>",
      "<Evidential>" == "" ? "he" : "<Evidential>",
      "<Parity>" == "" ? "p0" : "<Parity>",
      "<Scope>" == "" ? "sX" : "<Scope>",
      "<Phase>" == "" ? "pr" : "<Phase>"
    );
    case (monad): return EClause(
      "<Primitive>",
      [toEntity("<Entity 0>")],
      "<Intensity>" == "" ? "ke" : "<Intensity>",
      "<Evidential>" == "" ? "he" : "<Evidential>",
      "<Parity>" == "" ? "p0" : "<Parity>",
      "<Scope>" == "" ? "sX" : "<Scope>",
      "<Phase>" == "" ? "pr" : "<Phase>"
    );
  }
  throw "Expected Clause";
}
