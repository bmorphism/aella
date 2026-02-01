module aella::Aella

// ---------------------------
// Syntax (scannerless style)
// ---------------------------

lexical Integer = [0-9]+;
lexical Symbol  = [a-zA-Z_+*-=!?/<>][a-zA-Z0-9_+*-=!?/<>]*;
lexical Keyword = ':' [a-zA-Z_+*-=!?/<>][a-zA-Z0-9_+*-=!?/<>]*;
lexical String  = '"' (!['"' '\\'] | '\\' .)* '"';

layout Whitespace = [\ \t\n\r]*;

syntax Expr
  = intLit:Integer
  | strLit:String
  | kwLit:Keyword
  | sym:Symbol
  | list:'(' {Expr ws:Whitespace}* ')'
  | vec:'[' {Expr ws:Whitespace}* ']'
  | map:'{' {Expr ws:Whitespace}* '}'
  ;

// ---------------------------
// Core AST
// ---------------------------

data Expr
  = EInt(int value)
  | EStr(str value)
  | EKeyword(str value)
  | ESymbol(str name)
  | EList(list[Expr] items)
  | EVector(list[Expr] items)
  | EMap(map[Expr, Expr] entries)
  ;

// ---------------------------
// Taxonomy and phase model
// ---------------------------

data Mode = TypeA() | TypeB() | TypeC() | TypeL() | TypeS();

data Phase = PhaseMacro() | PhaseCompile() | PhaseRuntime();

data Config = Config(set[Mode] modes, Phase phase);

bool hasMode(Config cfg, Mode m) = m in cfg.modes;

void assertPhase(Config cfg, set[Phase] allowed) {
  if (!(cfg.phase in allowed)) {
    throw "Phase violation: <cfg.phase>";
  }
}

// ---------------------------
// Values
// ---------------------------

data Value
  = VInt(int value)
  | VStr(str value)
  | VBool(bool value)
  | VNil()
  | VKeyword(str value)
  | VList(list[Value] items)
  | VVector(list[Value] items)
  | VMap(map[Value, Value] entries)
  | VClosure(list[str] params, Expr body, map[str, Value] env)
  | VBuiltin(str name)
  ;

// ---------------------------
// Parse -> Expr
// ---------------------------

Expr toExpr(Expr t) = t; // placeholder for typed use

Expr fromTree(Tree t) {
  switch (t) {
    case (intLit)   : return EInt(toInt("<intLit>"));
    case (strLit)   : return EStr(unescapeString("<strLit>"));
    case (kwLit)    : return EKeyword("<kwLit>");
    case (sym)      : return ESymbol("<sym>");
    case (list elems): return EList([ fromTree(e) | e <- elems ]);
    case (vec elems):  return EVector([ fromTree(e) | e <- elems ]);
    case (map elems):  return EMap(mapFromList(elems));
  }
  throw "Unsupported tree";
}

map[Expr, Expr] mapFromList(list[Tree] elems) {
  map[Expr, Expr] m = ();
  int i = 0;
  while (i < size(elems)) {
    Expr k = fromTree(elems[i]);
    Expr v = fromTree(elems[i + 1]);
    m[k] = v;
    i = i + 2;
  }
  return m;
}

// ---------------------------
// Macroexpansion (Type-B/C)
// ---------------------------

Expr macroexpand(Expr e, Config cfg) {
  if (!(hasMode(cfg, TypeB()) || hasMode(cfg, TypeC()))) {
    return e;
  }
  switch (e) {
    case EList([ESymbol("when"), test, EList(body...)]):
      return EList([
        ESymbol("if"),
        test,
        EList([ESymbol("do")] + body),
        ESymbol("nil")
      ]);
    case EList([ESymbol("->"), x, EList(forms...)]):
      return threadFirst(x, forms);
    case EList([ESymbol("->>"), x, EList(forms...)]):
      return threadLast(x, forms);
  }
  return e;
}

Expr threadFirst(Expr x, list[Expr] forms) {
  Expr acc = x;
  for (f <- forms) {
    switch (f) {
      case EList([head, args...]):
        acc = EList([head, acc] + args);
      case _:
        acc = EList([f, acc]);
    }
  }
  return acc;
}

Expr threadLast(Expr x, list[Expr] forms) {
  Expr acc = x;
  for (f <- forms) {
    switch (f) {
      case EList([head, args...]):
        acc = EList([head] + args + [acc]);
      case _:
        acc = EList([f, acc]);
    }
  }
  return acc;
}

// ---------------------------
// Evaluation
// ---------------------------

tuple[Value, map[str, Value]] evalExpr(Expr e, map[str, Value] env, Config cfg) {
  switch (e) {
    case EInt(i): return <VInt(i), env>;
    case EStr(s): return <VStr(s), env>;
    case EKeyword(k): return <VKeyword(k), env>;
    case ESymbol("nil"): return <VNil(), env>;
    case ESymbol("true"): return <VBool(true), env>;
    case ESymbol("false"): return <VBool(false), env>;
    case ESymbol(name):
      if (name in env) return <env[name], env>;
      throw "Unbound symbol: <name>";
    case EVector(items):
      list[Value] vals = [];
      map[str, Value] env1 = env;
      for (it <- items) {
        <Value v, map[str, Value] env2> = evalExpr(it, env1, cfg);
        vals = vals + [v];
        env1 = env2;
      }
      return <VVector(vals), env1>;
    case EList([ESymbol("quote"), v]):
      return <quoteValue(v), env>;
    case EList([ESymbol("if"), test, tbranch, fbranch]):
      <Value tv, map[str, Value] env1> = evalExpr(test, env, cfg);
      if (truthy(tv)) return evalExpr(tbranch, env1, cfg);
      return evalExpr(fbranch, env1, cfg);
    case EList([ESymbol("do"), body...]):
      return evalSeq(body, env, cfg);
    case EList([ESymbol("let"), EVector(bindings...), body]):
      return evalLet(bindings, body, env, cfg);
    case EList([ESymbol("fn"), EVector(params...), body]):
      list[str] ps = [ symbolName(p) | p <- params ];
      return <VClosure(ps, body, env), env>;
    case EList([ESymbol("def"), ESymbol(name), expr]):
      assertPhase(cfg, {PhaseCompile(), PhaseRuntime()});
      <Value v, map[str, Value] env1> = evalExpr(expr, env, cfg);
      env1[name] = v;
      return <v, env1>;
    case EList([ESymbol("recur"), args...]):
      assertPhase(cfg, {PhaseRuntime()});
      throw "recur not implemented in this sketch";
    case EList([head, args...]):
      <Value fv, map[str, Value] env1> = evalExpr(head, env, cfg);
      list[Value] avs = [];
      map[str, Value] env2 = env1;
      for (a <- args) {
        <Value v, map[str, Value] env3> = evalExpr(a, env2, cfg);
        avs = avs + [v];
        env2 = env3;
      }
      return apply(fv, avs, env2, cfg);
  }
  throw "Unknown expression";
}

Value quoteValue(Expr e) {
  switch (e) {
    case EInt(i): return VInt(i);
    case EStr(s): return VStr(s);
    case EKeyword(k): return VKeyword(k);
    case ESymbol(s): return VStr(s);
    case EList(items): return VList([ quoteValue(x) | x <- items ]);
    case EVector(items): return VVector([ quoteValue(x) | x <- items ]);
    case EMap(m):
      map[Value, Value] mm = ();
      for (<k, v> <- m) mm[quoteValue(k)] = quoteValue(v);
      return VMap(mm);
  }
}

bool truthy(Value v) {
  switch (v) {
    case VNil(): return false;
    case VBool(false): return false;
  }
  return true;
}

str symbolName(Expr e) {
  switch (e) {
    case ESymbol(s): return s;
  }
  throw "Expected symbol";
}

// ---------------------------
// Application and builtins
// ---------------------------

tuple[Value, map[str, Value]] apply(Value f, list[Value] args, map[str, Value] env, Config cfg) {
  switch (f) {
    case VBuiltin(name): return <applyBuiltin(name, args), env>;
    case VClosure(params, body, cenv):
      if (size(params) != size(args)) {
        throw "Arity mismatch";
      }
      map[str, Value] env1 = cenv;
      int i = 0;
      while (i < size(params)) {
        env1[params[i]] = args[i];
        i = i + 1;
      }
      return evalExpr(body, env1, cfg);
  }
  throw "Not callable";
}

Value applyBuiltin(str name, list[Value] args) {
  switch (name) {
    case "+": return VInt(sumInts(args));
    case "-": return VInt(subInts(args));
    case "*": return VInt(mulInts(args));
    case "/": return VInt(divInts(args));
    case "=": return VBool(args[0] == args[1]);
  }
  throw "Unknown builtin: <name>";
}

int sumInts(list[Value] args) {
  int s = 0;
  for (a <- args) s = s + valueInt(a);
  return s;
}

int subInts(list[Value] args) {
  int s = valueInt(args[0]);
  int i = 1;
  while (i < size(args)) { s = s - valueInt(args[i]); i = i + 1; }
  return s;
}

int mulInts(list[Value] args) {
  int s = 1;
  for (a <- args) s = s * valueInt(a);
  return s;
}

int divInts(list[Value] args) {
  int s = valueInt(args[0]);
  int i = 1;
  while (i < size(args)) { s = s / valueInt(args[i]); i = i + 1; }
  return s;
}

int valueInt(Value v) {
  switch (v) {
    case VInt(i): return i;
  }
  throw "Expected int";
}

// ---------------------------
// Sequence evaluation
// ---------------------------

tuple[Value, map[str, Value]] evalSeq(list[Expr] body, map[str, Value] env, Config cfg) {
  Value last = VNil();
  map[str, Value] env1 = env;
  for (e <- body) {
    <Value v, map[str, Value] env2> = evalExpr(e, env1, cfg);
    last = v;
    env1 = env2;
  }
  return <last, env1>;
}

tuple[Value, map[str, Value]] evalLet(list[Expr] bindings, Expr body, map[str, Value] env, Config cfg) {
  if (size(bindings) % 2 != 0) throw "let binding count must be even";
  map[str, Value] env1 = env;
  int i = 0;
  while (i < size(bindings)) {
    str name = symbolName(bindings[i]);
    <Value v, map[str, Value] env2> = evalExpr(bindings[i + 1], env1, cfg);
    env1[name] = v;
    i = i + 2;
  }
  return evalExpr(body, env1, cfg);
}

// ---------------------------
// Default environment
// ---------------------------

map[str, Value] defaultEnv() {
  return (
    "+" : VBuiltin("+"),
    "-" : VBuiltin("-"),
    "*" : VBuiltin("*"),
    "/" : VBuiltin("/"),
    "=" : VBuiltin("=")
  );
}

