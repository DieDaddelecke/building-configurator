/**
 * Texte der Kompatibilitätsbefunde (E-HM-33): Jeder Code, den der Kern melden kann (`COMPATIBILITY_CODES`, auch die
 * Ablehnung durch `engine`, E-HM-45), hat einen Text in beiden Sprachen.
 */

import { describe, expect, it } from "vitest";

// Direkt aus dem Kern ohne Paketabhängigkeit: codes.ts hat keine Importe
import { COMPATIBILITY_CODES } from "../../../../../packages/domain/src/codes";
import de from "../../../i18n/de.json";
import fr from "../../../i18n/fr.json";

describe("Texte der Kompatibilitätsbefunde", () => {
  it("kennt die Codes des Kerns", () => {
    expect(COMPATIBILITY_CODES.length).toBeGreaterThan(60);
  });

  it.each([
    ["de", de],
    ["fr", fr],
  ] as const)("hat für %s genau einen Text je Code", (_locale, source) => {
    expect(Object.keys(source.house.check.issue).sort()).toEqual([...COMPATIBILITY_CODES]);
  });
});
