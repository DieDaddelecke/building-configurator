#!/usr/bin/env node
/**
 * Übernimmt die Texte der Prüfungen aus dem Frontend in die Übersetzungen des Backends, damit das
 * Dossier-PDF (Modul V, docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.2) dieselben Sätze zeigt wie der Konfigurator.
 * Ebenso die Werte der Regeln (`rules/format.ts` ↔ `app/rules/format.py`) für Steckbrief und Bericht (AN5).
 *
 * Quelle: frontend/src/i18n/{de,fr}.json (verschachtelt, `{{param}}`).
 * Ziel:   backend/app/platform/locales/{de,fr}.json (flach, `{param}`), Schlüssel mit den Präfixen unten.
 * Aufruf: node tools/sync-check-texts.cjs            (schreibt)
 *         node tools/sync-check-texts.cjs --check    (meldet Abweichungen, Exitcode 1)
 * Der Frontend-Test `check-texte.test.ts` prüft denselben Abgleich.
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

/** Abschnitt im Frontend → Präfix im Backend. */
const SECTIONS = [
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
  [["rules", "value"], "rule_value."],
  [["rules", "basis"], "rule_basis."],
  [["rules", "roofForm"], "rule_roof_form."],
  [["rules", "flatRoof"], "rule_flat_roof."],
  [["rules", "material"], "rule_material."],
  [["rules", "color"], "rule_color."],
  [["rules", "status"], "rule_status."],
  [["rules", "reason"], "rule_reason."],
];

function expected(locale) {
  const source = JSON.parse(fs.readFileSync(path.join(ROOT, "frontend/src/i18n", `${locale}.json`), "utf8"));
  const result = {};
  for (const [keys, prefix] of SECTIONS) {
    const section = keys.reduce((node, key) => node?.[key], source);
    if (!section || typeof section !== "object") throw new Error(`${locale}: Abschnitt ${keys.join(".")} fehlt`);
    for (const [key, text] of Object.entries(section)) {
      if (typeof text !== "string") continue;
      result[prefix + key] = text.replace(/\{\{\s*(\w+)\s*\}\}/g, "{$1}");
    }
  }
  return result;
}

const PREFIXES = SECTIONS.map(([, prefix]) => prefix);
const check = process.argv.includes("--check");
let differences = 0;

for (const locale of ["de", "fr"]) {
  const file = path.join(ROOT, "backend/app/platform/locales", `${locale}.json`);
  const current = JSON.parse(fs.readFileSync(file, "utf8"));
  const wanted = expected(locale);
  const kept = Object.fromEntries(Object.entries(current).filter(([key]) => !PREFIXES.some((p) => key.startsWith(p))));
  const next = { ...kept, ...wanted };
  const stale = Object.keys(current).filter((key) => PREFIXES.some((p) => key.startsWith(p)) && !(key in wanted));
  const changed = Object.keys(wanted).filter((key) => current[key] !== wanted[key]);
  differences += stale.length + changed.length;
  if (check) {
    for (const key of changed) console.log(`${locale}: ${key} weicht ab oder fehlt`);
    for (const key of stale) console.log(`${locale}: ${key} gibt es im Frontend nicht mehr`);
  } else {
    fs.writeFileSync(file, JSON.stringify(next, null, 2) + "\n");
    console.log(`${locale}: ${Object.keys(wanted).length} Texte übernommen (${changed.length} neu oder geändert, ${stale.length} entfernt)`);
  }
}

if (check && differences > 0) process.exit(1);
