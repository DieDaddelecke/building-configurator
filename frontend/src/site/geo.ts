/** Reine Hilfsfunktionen für Grundstücksdarstellungen. Azimut: 0° = Norden, im Uhrzeigersinn. */

import type { EdgeKind, SiteOut } from "../api/site";
import type { Bounds, LocalPoint } from "../components/plan/PlanSvg";

export const COMPASS_KEYS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"] as const;
export type CompassKey = (typeof COMPASS_KEYS)[number];

/** Achtteilige Himmelsrichtung; Sektoren sind 45° breit und um die Hauptrichtung zentriert. */
export function compass(azimuthDeg: number): CompassKey {
  const normalized = ((azimuthDeg % 360) + 360) % 360;
  return COMPASS_KEYS[Math.round(normalized / 45) % 8] ?? "n";
}

export const EDGE_COLORS: Record<EdgeKind, string> = {
  street: "var(--accent)",
  side: "var(--ink)",
  rear: "var(--warn)",
  other: "var(--faint)",
};

export function formatNumber(value: number, language: string, digits = 1): string {
  return new Intl.NumberFormat(language === "de" ? "de-DE" : "fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function siteBounds(site: Pick<SiteOut, "outline_local">): Bounds {
  const points = site.outline_local.flat() as unknown as LocalPoint[];
  return points.reduce<Bounds>(
    (b, [e, n]) => ({ minE: Math.min(b.minE, e), minN: Math.min(b.minN, n), maxE: Math.max(b.maxE, e), maxN: Math.max(b.maxN, n) }),
    { minE: Infinity, minN: Infinity, maxE: -Infinity, maxN: -Infinity },
  );
}

/** Mittelpunkt einer Polylinie nach Länge (für Beschriftungen). */
export function midpoint(coords: readonly LocalPoint[]): LocalPoint {
  const first = coords[0] ?? [0, 0];
  const segments = coords.slice(1).map((end, i) => {
    const start = coords[i] ?? end;
    return { start, end, length: Math.hypot(end[0] - start[0], end[1] - start[1]) };
  });
  let remaining = segments.reduce((sum, s) => sum + s.length, 0) / 2;
  for (const { start, end, length } of segments) {
    if (remaining <= length && length > 0) {
      const t = remaining / length;
      return [start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])];
    }
    remaining -= length;
  }
  return first;
}

/** Warnungen, die der Kunde sieht; interne Hinweise (z. B. Prüfbedarf) bleiben dem Büro. */
export const CUSTOMER_WARNINGS = new Set([
  "corner_lot",
  "flag_lot",
  "no_street_edge",
  "no_neighbour_data",
  "neighbour_data_incomplete",
  "area_mismatch",
  "customer_corrections_unconfirmed",
]);

/** Erste Koordinate einer GeoJSON-Geometrie beliebiger Schachtelung (WGS84: Länge, Breite). */
export function firstPosition(geometry: unknown): [number, number] | null {
  let value: unknown = (geometry as { coordinates?: unknown } | null)?.coordinates;
  while (Array.isArray(value) && Array.isArray(value[0])) value = value[0];
  return Array.isArray(value) && typeof value[0] === "number" && typeof value[1] === "number" ? [value[0], value[1]] : null;
}

/** Mittelpunkt des umschließenden Rechtecks des äußeren Rings (WGS84), für den Kartenausschnitt. */
export function centerOf(geometry: unknown): [number, number] | null {
  let ring: unknown = (geometry as { coordinates?: unknown } | null)?.coordinates;
  while (Array.isArray(ring) && Array.isArray(ring[0]) && Array.isArray(ring[0][0])) ring = ring[0];
  if (!Array.isArray(ring)) return null;
  const points = ring.filter((p): p is [number, number] => Array.isArray(p) && typeof p[0] === "number" && typeof p[1] === "number");
  if (points.length === 0) return null;
  const lons = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}

/** Gemeinsame Ausdehnung mehrerer Rechtecke `[west, süd, ost, nord]`, z. B. aller Gemeinden des Einzugsgebiets. */
export function unionBbox(boxes: readonly (readonly number[])[]): [number, number, number, number] | null {
  if (boxes.length === 0) return null;
  return [
    Math.min(...boxes.map((b) => b[0]!)),
    Math.min(...boxes.map((b) => b[1]!)),
    Math.max(...boxes.map((b) => b[2]!)),
    Math.max(...boxes.map((b) => b[3]!)),
  ];
}
