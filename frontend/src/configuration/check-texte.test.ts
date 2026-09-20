/**
 * Die Texte der Prüfungen stehen doppelt: im Frontend (Konfigurator) und im Backend (Dossier-PDF, Modul V).
 * `tools/sync-check-texts.cjs` gleicht sie ab; dieser Test meldet, wenn es vergessen wurde.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import de from "../i18n/de.json";
import fr from "../i18n/fr.json";

const SECTIONS: [string[], string][] = [
  [["configurator", "check"], "check."],
  [["configurator", "reason"], "check_reason."],
  [["configurator", "orientation"], "check_orientation."],
  [["configurator", "material"], "check_material."],
  [["configurator", "types", "roof"], "check_roof."],
  [["configurator", "edge"], "check_edge."],
  [["configurator", "status"], "check_status."],
  [["configurator", "compass"], "compass."],
  [["configurator", "design", "area"], "area."],
  [["site", "risks", "kind"], "risk.kind."],
  [["site", "risks", "level"], "risk.level."],
];

function expected(source: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [keys, prefix] of SECTIONS) {
    const section = keys.reduce<unknown>((node, key) => (node as Record<string, unknown>)?.[key], source);
    for (const [key, text] of Object.entries(section as Record<string, unknown>)) {
      if (typeof text === "string") result[prefix + key] = text.replace(/\{\{\s*(\w+)\s*\}\}/g, "{$1}");
    }
  }
  return result;
}

describe("Texte der Prüfungen im Backend", () => {
  it.each([
    ["de", de],
    ["fr", fr],
  ] as const)("stimmen für %s mit dem Frontend überein (node tools/sync-check-texts.cjs)", (locale, source) => {
    const backend = JSON.parse(
      // vitest läuft im Ordner frontend (package.json)
      readFileSync(resolve(process.cwd(), `../backend/app/platform/locales/${locale}.json`), "utf8"),
    ) as Record<string, string>;
    const wanted = expected(source);
    const synced = Object.fromEntries(Object.keys(wanted).map((key) => [key, backend[key]]));
    expect(synced).toEqual(wanted);
  });
});
