// Ausdrücke des Katalogs (P 8.4, E-HM-34): kein ausführbarer Code, festes Verhalten bei null und Typfehlern.
//
// - Ein fehlender Pfad ergibt null; ein Pfad über eine Liste ergibt eine Liste (null-Einträge fallen weg).
// - eq/neq vergleichen Werte (Listen elementweise); gt/gte/lt/lte nur Zahl mit Zahl, sonst false.
// - in/not_in: rechts eine Liste, sonst false; contains: links eine Liste, sonst false.
// - add/sub/mul/div nur mit Zahlen, sonst null; Division durch 0 ergibt null.
// - and/or/not werten nur true als wahr: not(null) ist true. exists: weder null noch leere Liste.
// - Eine Regel trifft nur zu, wenn `when` genau true ergibt; ein Wert ist nur verfügbar, wenn `available_when`
//   null ist oder genau true ergibt.
import type { HouseBinaryExpr, HouseExpr, HouseLiteral, HouseLogicExpr } from "./contract.gen.ts";

export type ExprContext = Readonly<Record<string, unknown>>;

function lookup(context: unknown, parts: readonly string[]): unknown {
  let current: unknown = context;
  for (const part of parts) {
    if (Array.isArray(current)) {
      current = current
        .map((item) => lookup(item, [part]))
        .flatMap((value) => (Array.isArray(value) ? value : [value]))
        .filter((value) => value !== null);
    } else if (current !== null && typeof current === "object") {
      current = Object.hasOwn(current, part) ? (current as Record<string, unknown>)[part] : null;
    } else {
      return null;
    }
  }
  return current === undefined ? null : current;
}

function equal(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, i) => equal(item, b[i]));
  }
  return a === b;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function arithmetic(op: string, a: unknown, b: unknown): number | null {
  if (!isNumber(a) || !isNumber(b)) return null;
  const result = op === "add" ? a + b : op === "sub" ? a - b : op === "mul" ? a * b : b === 0 ? null : a / b;
  return result !== null && Number.isFinite(result) ? result : null;
}

function isList(expr: HouseExpr): expr is readonly HouseLiteral[] {
  return Array.isArray(expr);
}

function logic(expr: HouseLogicExpr, context: ExprContext): boolean {
  const values = expr.args.map((arg) => evaluateExpr(arg, context));
  switch (expr.op) {
    case "and":
      return values.every((value) => value === true);
    case "or":
      return values.some((value) => value === true);
    case "not":
      return values[0] !== true;
    case "exists":
      return values[0] !== null && !(Array.isArray(values[0]) && values[0].length === 0);
  }
}

function binary(expr: HouseBinaryExpr, context: ExprContext): unknown {
  const left = evaluateExpr(expr.left, context);
  const right = evaluateExpr(expr.right, context);
  switch (expr.op) {
    case "eq":
      return equal(left, right);
    case "neq":
      return !equal(left, right);
    case "gt":
      return isNumber(left) && isNumber(right) && left > right;
    case "gte":
      return isNumber(left) && isNumber(right) && left >= right;
    case "lt":
      return isNumber(left) && isNumber(right) && left < right;
    case "lte":
      return isNumber(left) && isNumber(right) && left <= right;
    case "in":
      return Array.isArray(right) && right.some((item) => equal(left, item));
    case "not_in":
      return Array.isArray(right) && !right.some((item) => equal(left, item));
    case "contains":
      return Array.isArray(left) && left.some((item) => equal(item, right));
    default:
      return arithmetic(expr.op, left, right);
  }
}

export function evaluateExpr(expr: HouseExpr, context: ExprContext): unknown {
  if (expr === null || typeof expr !== "object") return expr;
  if (isList(expr)) return [...expr];
  if ("path" in expr) return lookup(context, expr.path.split("."));
  return "args" in expr ? logic(expr, context) : binary(expr, context);
}

/** Bedingung: `null` gilt als erfüllt (z. B. `available_when` fehlt), sonst nur genau true. */
export function holds(expr: HouseExpr, context: ExprContext): boolean {
  return expr === null || evaluateExpr(expr, context) === true;
}

/** Regel trifft zu: nur, wenn `when` genau true ergibt; `null` trifft nie zu. */
export function applies(expr: HouseExpr, context: ExprContext): boolean {
  return expr !== null && evaluateExpr(expr, context) === true;
}
