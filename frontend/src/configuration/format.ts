/** Texte der Prüfungen und Kennwerte des Konfigurators (Plan H2 4.4, H3 4.4). Die API liefert nur stabile Codes. */

import type { TFunction } from "i18next";

import type { CheckOut, EdgeMeasureOut } from "../api/configuration";
import { formatNumber } from "../site/geo";

/** Kantenart und Nummer, z. B. „Straße (3)“. */
export function edgeName(kind: string, seq: number, t: TFunction): string {
  return t(`configurator.edge.${["street", "side", "rear"].includes(kind) ? kind : "other"}`, { seq });
}

function roofForms(value: string | number | null | undefined, t: TFunction): string {
  return String(value ?? "")
    .split(",")
    .filter(Boolean)
    .map((form) => t(`configurator.types.roof.${form}`, { defaultValue: form }))
    .join(", ");
}

/** Materialklassen einer Regel als Text, z. B. „Holz, Ziegel“. */
function materials(value: string | number | null | undefined, t: TFunction): string {
  return String(value ?? "")
    .split(",")
    .filter(Boolean)
    .map((material) => t(`configurator.material.${material}`, { defaultValue: material }))
    .join(", ");
}

const AREA_CHECKS = new Set(["footprint", "footprint_total", "unsealed_min", "annex_footprint"]);
const MATERIAL_CHECKS = new Set(["facade_material", "roof_material"]);

/**
 * Text einer Prüfung mit Messwert und Grenze. Unbekannte Codes erscheinen als Code, nie leer. `names` übersetzt
 * die Slugs von Optionen und Linien (`params.subject`) in ihre Bezeichnung.
 */
export function checkText(check: CheckOut, t: TFunction, lng: string, names: Record<string, string> = {}): string {
  const number = (value: string | number | null | undefined, digits = 2) =>
    typeof value === "number" ? formatNumber(value, lng, digits) : String(value ?? "");
  const isForm = check.code === "roof_form" || check.code === "roof_flat";
  const areas = AREA_CHECKS.has(check.code);
  const isMaterial = MATERIAL_CHECKS.has(check.code);
  const orientation = typeof check.params?.orientation === "string" ? check.params.orientation : "";
  const slug = typeof check.params?.subject === "string" ? check.params.subject : "";
  // Ein Carport oder eine Terrasse ohne Platz meldet dieselbe Ursache wie ein Haus, hat aber einen eigenen Text
  const key = check.code === "no_valid_position" && slug ? "no_valid_position_option" : check.code;
  return t(`configurator.check.${key}`, {
    measured: isForm ? roofForms(check.measured, t) : isMaterial ? materials(check.measured, t) : number(check.measured, areas ? 1 : 2),
    limit: isForm ? roofForms(check.limit, t) : isMaterial ? materials(check.limit, t) : number(check.limit, areas ? 1 : 2),
    orientation: orientation ? t(`configurator.orientation.${orientation}`, { defaultValue: orientation }) : "",
    reason: check.reason ? t(`configurator.reason.${check.reason}`, { defaultValue: check.reason }) : "",
    subject: names[slug] ?? slug,
    defaultValue: check.code,
  });
}

/** Abstand einer Kante: gemessen und gefordert. */
export function requiredText(edge: EdgeMeasureOut, t: TFunction, lng: string): string {
  if (edge.on_boundary) return t("configurator.placement.onBoundary");
  if (edge.required_m == null) return t("configurator.placement.unknownRule");
  return `${formatNumber(edge.required_m, lng, 2)} m`;
}

export const STATUS_TONE: Record<CheckOut["status"], string> = {
  pass: "t-ink",
  fail: "t-alert",
  hint: "t-warn",
  unknown: "t-warn",
  not_applicable: "t-mute",
};

/**
 * Abweichungen für die Übergabe (V 3.4): bindende Verstöße aus Zulässigkeit, Lage und Auswahl, jede einmal –
 * dieselbe Regel wie `deviations` in `backend/app/configuration/review.py`.
 */
export function deviationsOf(configuration: {
  fit?: { reasons: readonly CheckOut[] } | null;
  evaluation?: { checks: readonly CheckOut[] } | null;
  compliance?: { checks: readonly CheckOut[] } | null;
}): CheckOut[] {
  const seen = new Set<string>();
  const result: CheckOut[] = [];
  const all = [...(configuration.fit?.reasons ?? []), ...(configuration.evaluation?.checks ?? []), ...(configuration.compliance?.checks ?? [])];
  for (const check of all) {
    const key = [check.code, check.zone_code ?? "", check.edge_seq ?? "", String(check.params?.subject ?? "")].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    if (check.binding && check.status === "fail") result.push(check);
  }
  return result;
}

/** Verstöße zuerst, dann Hinweise und Unbekanntes, dann Bestandenes. */
export function sortChecks(checks: readonly CheckOut[]): CheckOut[] {
  const order: Record<CheckOut["status"], number> = { fail: 0, unknown: 1, hint: 2, not_applicable: 3, pass: 4 };
  return [...checks].sort((a, b) => order[a.status] - order[b.status]);
}

/** Betrag in Cent als „384.000 €“ (ohne Nachkommastellen; Anzeige nur gerundet oder als Einzelposten). */
export function money(cents: number, lng: string): string {
  return `${formatNumber(Math.round(cents / 100), lng, 0)} €`;
}

/** Bezeichnung nach Sprache: Deutsch oder Französisch, bei anderer Sprache Französisch (führend, D7). */
export function localLabel(item: { label_de: string | null; label_fr: string | null }, lng: string): string {
  return (lng.startsWith("de") ? item.label_de : item.label_fr) ?? item.label_fr ?? item.label_de ?? "";
}

const COMPASS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"] as const;

/** Himmelsrichtung eines Azimuts (0° = Norden, im Uhrzeigersinn) als Schlüssel `n` … `nw`. */
export function compassKey(azimuthDeg: number): (typeof COMPASS)[number] {
  return COMPASS[Math.round((((azimuthDeg % 360) + 360) % 360) / 45) % 8]!;
}
