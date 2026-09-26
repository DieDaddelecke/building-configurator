/** Werte des Baurahmens als kurzer Text. Einheiten: Meter, Quadratmeter, Anteile 0–1, Grad. */

import type { TFunction } from "i18next";

import type { EnvelopeEdgeOut, LimitOut } from "../api/envelope";
import type { RuleOut } from "../api/rules";
import { formatNumber } from "../site/geo";
import { ruleValue } from "../rules/format";

/** Reihenfolge der Zeilen wie im Mockup (Schritt 3): Höhen, Grundfläche, Abstände, Freifläche, Dach, Fassade. */
export const LIMIT_ORDER = [
  "max_height",
  "max_footprint_ratio",
  "footprint_max_m2",
  "max_area",
  "setback_street",
  "setback_side",
  "setback_rear",
  "setback_between_buildings",
  "unsealed_min",
  "unsealed_min_m2",
  "full_soil_min_m2",
  "roof",
  "facade",
  "parking",
  "annex",
  "planting",
  "fence",
  "text_only",
];

export function sortLimits(limits: LimitOut[]): LimitOut[] {
  const building = ["main", "any", "annex", "pool"];
  return [...limits].sort(
    (a, b) =>
      building.indexOf(a.building_kind) - building.indexOf(b.building_kind) ||
      LIMIT_ORDER.indexOf(a.key) - LIMIT_ORDER.indexOf(b.key),
  );
}

/** Wert eines Grenzwerts: abgeleitete Flächen als m², sonst die Parameter der Regel (wie in G2). */
export function limitValue(limit: LimitOut, t: TFunction, language: string): string {
  if (limit.derived_from && limit.value != null) return `${formatNumber(limit.value, language, 0)} m²`;
  if (limit.status === "missing") return t("envelope.value.notDetermined");
  return ruleValue(limit as unknown as RuleOut, t, language);
}

/** Abstand einer Kante: ein Wert, wenn beide Auslegungen gleich sind, sonst die Spanne. */
export function setbackValue(edge: EnvelopeEdgeOut, t: TFunction, language: string): string {
  const { lenient_m: lenient, strict_m: strict } = edge;
  if (lenient == null && strict == null) return t("envelope.value.notDetermined");
  if (lenient != null && strict != null && Math.abs(lenient - strict) < 0.005) {
    return `${formatNumber(lenient, language, 2)} m`;
  }
  const from = lenient == null ? "?" : formatNumber(lenient, language, 2);
  const to = strict == null ? "?" : formatNumber(strict, language, 2);
  return `${from} – ${to} m`;
}

export function edgeLabel(edge: EnvelopeEdgeOut, t: TFunction): string {
  const base = t(`envelope.edge.${edge.kind}`, { seq: edge.seq });
  return edge.street_name ? `${base} · ${edge.street_name}` : base;
}
