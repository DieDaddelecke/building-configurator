/**
 * Kundenpreise (E-HM-2): Die Rundung ist dieselbe wie im Server; die Tabelle entspricht `test_round_amount` in
 * `backend/tests/unit/test_house_site_check.py`. Die Beträge des Demohauses sind die, die der Server zeigt.
 */

import { describe, expect, it } from "vitest";

import { EVALUATIONS } from "./__fixtures__/haus";
import { aufpreis, euro, euroDelta, kundenpreis, rundeBetrag } from "./preis";

describe("Rundung der Kundenpreise", () => {
  it.each([
    [515_194.2144, 1000, 515_000],
    [523_547.5584, 1000, 524_000],
    [500, 1000, 1000],
    [499.99, 1000, 0],
    [8_353.344, 100, 8_400],
    [9_741.864, 100, 9_700],
    [-777.6, 100, -800],
    [-50, 100, -100],
    [-49.99, 100, 0],
    [0, 100, 0],
  ])("rundet %d auf %d € zu %d", (value, step, rounded) => {
    expect(rundeBetrag(value, step)).toBe(rounded);
  });

  it("gibt nie eine negative Null", () => {
    expect(Object.is(rundeBetrag(-49.99, 100), 0)).toBe(true);
  });

  it("rechnet Aufpreise brutto", () => {
    expect(aufpreis(6961.12, 0.2)).toBe(8400);
    expect(aufpreis(-6961.12, 0.2)).toBe(-8400);
  });

  it("zeigt für das Demohaus dieselben Beträge wie der Server", () => {
    expect(kundenpreis(EVALUATIONS.standard.evaluation.price)).toEqual({ gesamt: 515_000, aufpreise: {} });
    expect(kundenpreis(EVALUATIONS.brick.evaluation.price)).toEqual({ gesamt: 524_000, aufpreise: { wall_profile: 8_400 } });
    expect(kundenpreis(EVALUATIONS.wood.evaluation.price)).toEqual({ gesamt: 525_000, aufpreise: { wall_profile: 9_700 } });
    expect(kundenpreis(EVALUATIONS.green_roof.evaluation.price)).toEqual({ gesamt: 526_000, aufpreise: { roof_type: 10_600 } });
  });

  it("schreibt Beträge mit Vorzeichen", () => {
    expect(euro(515_000, "de")).toBe("515.000 €");
    expect(euroDelta(8_400, "de")).toBe("+8.400 €");
    expect(euroDelta(-800, "de")).toBe("−800 €");
    expect(euroDelta(0, "de")).toBe("±0 €");
  });
});
