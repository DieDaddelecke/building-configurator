// Ausdrücke des Katalogs (P 8.4, E-HM-34): festes Verhalten bei null, Listen und Typfehlern.
import { describe, expect, it } from "vitest";
import { evaluateExpr, type HouseExpr } from "../src/index.ts";

const context = {
  element: { kind: "window", width: 1.2, adjacent_rooms: [{ room_type_id: "living" }, { room_type_id: null }, { room_type_id: "bathroom" }] },
  room: null,
  parameter: { limit: 0.1 },
};
const path = (p: string) => ({ path: p });
const bin = (op: string, left: HouseExpr, right: HouseExpr) => ({ op, left, right }) as HouseExpr;
const logic = (op: string, ...args: HouseExpr[]) => ({ op, args }) as HouseExpr;
const run = (expr: HouseExpr) => evaluateExpr(expr, context);

describe("Pfade", () => {
  it("fehlender Pfad ergibt null, Pfad über eine Liste eine Liste ohne null", () => {
    expect(run(path("element.missing.deeper"))).toBeNull();
    expect(run(path("room.id"))).toBeNull();
    expect(run(path("element.adjacent_rooms.room_type_id"))).toEqual(["living", "bathroom"]);
  });

  it("geerbte Eigenschaften sind keine Pfade", () => {
    expect(run(path("element.kind.length"))).toBeNull();
    expect(run(path("element.constructor"))).toBeNull();
  });
});

describe("Vergleiche", () => {
  it.each([
    [bin("eq", path("element.kind"), "window"), true],
    [bin("neq", path("element.kind"), "door"), true],
    [bin("eq", path("element.missing"), null), true],
    [bin("gt", path("element.width"), 1), true],
    [bin("lte", path("element.width"), 1.2), true],
    [bin("lt", path("element.missing"), 1), false],
    [bin("gt", "2", 1), false],
    [bin("in", path("element.kind"), ["window", "door"]), true],
    [bin("in", path("element.kind"), "window"), false],
    [bin("not_in", path("element.kind"), ["door"]), true],
    [bin("not_in", path("element.kind"), "door"), false],
    [bin("contains", path("element.adjacent_rooms.room_type_id"), "bathroom"), true],
    [bin("contains", path("element.kind"), "w"), false],
    [bin("eq", path("element.adjacent_rooms.room_type_id"), ["living", "bathroom"]), true],
  ])("%j → %s", (expr, expected) => {
    expect(run(expr)).toBe(expected);
  });
});

describe("Rechnen", () => {
  it("nur mit Zahlen, Division durch 0 ergibt null", () => {
    expect(run(bin("mul", path("element.width"), 2))).toBeCloseTo(2.4, 12);
    expect(run(bin("sub", path("parameter.limit"), 0.1))).toBe(0);
    expect(run(bin("add", "1", 1))).toBeNull();
    expect(run(bin("div", 1, 0))).toBeNull();
    expect(run(bin("lt", bin("div", 1, 0), 5))).toBe(false);
  });
});

describe("Logik", () => {
  it("nur true ist wahr", () => {
    expect(run(logic("and", true, bin("eq", path("element.kind"), "window")))).toBe(true);
    expect(run(logic("and", true, path("element.width")))).toBe(false);
    expect(run(logic("or", null, false, true))).toBe(true);
    expect(run(logic("not", path("element.missing")))).toBe(true);
    expect(run(logic("not", true))).toBe(false);
  });

  it("exists: weder null noch leere Liste", () => {
    expect(run(logic("exists", path("element.kind")))).toBe(true);
    expect(run(logic("exists", path("element.missing")))).toBe(false);
    expect(run(logic("exists", path("element.adjacent_rooms.missing")))).toBe(false);
  });

  it("Verfügbarkeit des Bodentiefen Fensters (P 8.4)", () => {
    const notBathroom = logic("not", bin("contains", path("element.adjacent_rooms.room_type_id"), "bathroom"));
    expect(run(notBathroom)).toBe(false);
    expect(evaluateExpr(notBathroom, { element: { adjacent_rooms: [{ room_type_id: "living" }] } })).toBe(true);
    expect(evaluateExpr(notBathroom, { element: { adjacent_rooms: [] } })).toBe(true);
  });
});
