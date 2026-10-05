/**
 * Kern im Browser (L5): Er rechnet die gespeicherten Auswertungen des Demohauses genau so, wie sie `engine` für die
 * Python-Tests liefert; die Auswahl bleibt ohne stille Werte (P 2.1 Nr. 9).
 */

import { RULE_CODES } from "@emprise/domain";
import { describe, expect, it } from "vitest";

import de from "../i18n/de.json";
import fr from "../i18n/fr.json";
import { DOCS, EVALUATIONS } from "./__fixtures__/haus";
import { gewaehlt, gleich, kandidaten, mitWert, rechne } from "./kern";

describe("Kern im Browser", () => {
  it.each(Object.entries(EVALUATIONS))("rechnet %s wie die gespeicherte Auswertung", (_name, { configuration, evaluation }) => {
    expect(JSON.parse(JSON.stringify(rechne(DOCS, configuration)))).toEqual(evaluation);
  });

  it("entfernt die Wahl, wenn der Standard gewählt wird", () => {
    const brick = mitWert(DOCS, { selections: {} }, "wall_profile", "wall.brick");
    expect(gleich(brick, EVALUATIONS.brick.configuration)).toBe(true);
    expect(gewaehlt(DOCS, brick, "wall_profile")).toBe("wall.brick");
    expect(mitWert(DOCS, brick, "wall_profile", "wall.standard")).toEqual({ selections: {} });
    expect(gewaehlt(DOCS, { selections: {} }, "roof_type")).toBe("roof.flat");
  });

  it("nennt die Preisdifferenz der Kandidaten zur aktuellen Wahl", () => {
    const standard = kandidaten(DOCS, { selections: {} }, "wall_profile");
    expect(standard.map((c) => c.option_value_id)).toEqual(["wall.standard", "wall.brick", "wall.wood"]);
    expect(standard[0]!.price_delta).toBe(0);
    expect(standard[1]!.price_delta).toBeCloseTo(6961.12, 2);
    const fromBrick = kandidaten(DOCS, EVALUATIONS.brick.configuration, "wall_profile");
    expect(fromBrick[0]!.price_delta).toBeCloseTo(-6961.12, 2);
  });

  it("vergleicht Auswahlen unabhängig von der Reihenfolge der Schlüssel", () => {
    const a = mitWert(DOCS, mitWert(DOCS, { selections: {} }, "wall_profile", "wall.wood"), "roof_type", "roof.green");
    const b = mitWert(DOCS, mitWert(DOCS, { selections: {} }, "roof_type", "roof.green"), "wall_profile", "wall.wood");
    expect(gleich(a, b)).toBe(true);
    expect(gleich(a, EVALUATIONS.wood.configuration)).toBe(false);
  });
});

describe("Texte der Regelergebnisse", () => {
  it.each([
    ["de", de],
    ["fr", fr],
  ] as const)("hat für %s einen Text je Code des Kerns (E-HM-33)", (_locale, source) => {
    expect(Object.keys(source.houseConfigurator.rule).sort()).toEqual([...RULE_CODES].sort());
  });
});
