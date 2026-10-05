/**
 * Texte der Importbefunde (E-HM-33): Jeder Code, den das Backend meldet (`FINDING_CODES`, in der OpenAPI unter
 * `x-codes`), hat einen Text in beiden Sprachen, und beide Sprachen haben dieselben Schlüssel.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import i18n from "../../i18n";
import de from "../../i18n/de.json";
import fr from "../../i18n/fr.json";
import { findingText, formatParams } from "./Befunde";

// vitest läuft im Ordner frontend (package.json)
const openapi = JSON.parse(readFileSync(resolve(process.cwd(), "../backend/openapi.json"), "utf8")) as {
  components: { schemas: { HouseImportFinding: { properties: { code: { "x-codes": string[] } } } } };
};
const CODES = openapi.components.schemas.HouseImportFinding.properties.code["x-codes"];

function keys(node: unknown, prefix = ""): string[] {
  if (typeof node !== "object" || node === null) return [prefix];
  return Object.entries(node).flatMap(([key, value]) => keys(value, prefix ? `${prefix}.${key}` : key));
}

describe("Texte der Importbefunde", () => {
  it("kennt die Codes des Backends", () => {
    expect(CODES.length).toBeGreaterThan(40);
  });

  it.each([
    ["de", de],
    ["fr", fr],
  ] as const)("hat für %s genau einen Text je Code", (_locale, source) => {
    expect(Object.keys(source.house.finding).sort()).toEqual([...CODES].sort());
  });

  it("hat in beiden Sprachen dieselben Schlüssel", () => {
    expect(keys(fr.house)).toEqual(keys(de.house));
  });

  it("schreibt Anteile in Prozent und setzt für fehlende Werte einen Strich", () => {
    const params = formatParams({ share: 0.425, area: 12.345, slopes: "", detail: null }, "de");
    expect(params.share).toMatch(/^42,5\s%$/);
    expect(params).toMatchObject({ area: "12,35", slopes: "–", detail: "–" });
    const t = i18n.getFixedT("fr");
    const text = findingText(t, { code: "reader_failed", severity: "error", element_id: null, ifc_guid: null, params: {} }, "fr");
    expect(text).toBe("La lecture du fichier a échoué : –");
    const unknown = { code: "neu_im_backend", severity: "info" as const, element_id: null, ifc_guid: null, params: {} };
    expect(findingText(t, unknown, "fr")).toBe("neu_im_backend");
  });

  it("übersetzt Grund und Ablehnung eines nicht erkannten Dachs und die gesetzte Form (E-HM-65)", () => {
    const t = i18n.getFixedT("de");
    const finding = (params: Record<string, string | number>) =>
      ({ code: "roof_form_not_recognized", severity: "open", element_id: null, ifc_guid: null, params }) as const;
    expect(findingText(t, finding({ reason: "shape_differs", distance: 0.2, slopes: "37.5°" }), "de")).toBe(
      "Die Dachform wurde nicht erkannt: die Form weicht um 0,2 m vom erzeugten Dach ab. Geneigte Flächen: 37,5°. Bitte das Dach im Entwurf festlegen.",
    );
    expect(findingText(t, finding({ reason: "not_constructible", refusal: "gables_adjacent", slopes: "45°" }), "de")).toContain(
      "der Kern erzeugt diese Form nicht (zwei Giebel stießen aneinander)",
    );
    const set = { code: "roof_set_by_office", severity: "info", element_id: null, ifc_guid: null, params: { form: "half_hip" } } as const;
    expect(findingText(t, set, "de")).toContain("(Krüppelwalmdach)");
  });
});
