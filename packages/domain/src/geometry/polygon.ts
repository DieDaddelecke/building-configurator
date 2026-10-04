// Ganzzahlige Geometrie in 0,1 mm (P 4, docs/PLAN_HAUSMODELL.md 3.2): gleiche Ergebnisse in Browser und engine.
import type { PolygonDefect } from "../codes.ts";

export type { PolygonDefect };

export const UNITS_PER_METRE = 10_000;

export interface Point {
  readonly x: number;
  readonly y: number;
}

/** Geschlossener Ring ohne wiederholten ersten Punkt. */
export type Polygon = readonly Point[];

export function toUnits(metres: number): number {
  return Math.round(metres * UNITS_PER_METRE);
}

export function toMetres(units: number): number {
  return units / UNITS_PER_METRE;
}

/** Vorzeichenbehaftete Fläche in Einheiten²; positiv gegen den Uhrzeigersinn. */
export function signedArea(polygon: Polygon): number {
  let twice = 0;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i]!;
    const b = polygon[(i + 1) % polygon.length]!;
    twice += a.x * b.y - b.x * a.y;
  }
  return twice / 2;
}

/** Fläche in m². */
export function areaSquareMetres(polygon: Polygon): number {
  return Math.abs(signedArea(polygon)) / (UNITS_PER_METRE * UNITS_PER_METRE);
}

/** Umfang in m. */
export function perimeterMetres(polygon: Polygon): number {
  let length = 0;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i]!;
    const b = polygon[(i + 1) % polygon.length]!;
    // sqrt statt hypot: sqrt ist in IEEE 754 exakt gerundet, also in jedem Browser gleich
    length += Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
  }
  return length / UNITS_PER_METRE;
}

export function isInteger(polygon: Polygon): boolean {
  return polygon.every((p) => Number.isSafeInteger(p.x) && Number.isSafeInteger(p.y));
}

/** Gegen den Uhrzeigersinn ausgerichtet (Innenseite links), wie die Bezugskontur im Template. */
export function counterClockwise(polygon: Polygon): Polygon {
  return signedArea(polygon) >= 0 ? polygon : [...polygon].reverse();
}

/** Größter Betrag einer Koordinate (1 km): Kreuzprodukte bleiben unter 2^53 und damit exakt. */
export const MAX_COORDINATE = 10_000_000;

/** Lage von c zur Geraden a→b: positiv links, 0 auf der Geraden (exakt bei Koordinaten bis MAX_COORDINATE). */
function orient(a: Point, b: Point, c: Point): number {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

/** c liegt auf der Geraden durch a und b; liegt es auch zwischen ihnen? */
function within(a: Point, b: Point, c: Point): boolean {
  return Math.min(a.x, b.x) <= c.x && c.x <= Math.max(a.x, b.x) && Math.min(a.y, b.y) <= c.y && c.y <= Math.max(a.y, b.y);
}

function segmentsTouch(a: Point, b: Point, c: Point, d: Point): boolean {
  const o1 = Math.sign(orient(a, b, c));
  const o2 = Math.sign(orient(a, b, d));
  const o3 = Math.sign(orient(c, d, a));
  const o4 = Math.sign(orient(c, d, b));
  if (o1 * o2 < 0 && o3 * o4 < 0) return true;
  return (o1 === 0 && within(a, b, c)) || (o2 === 0 && within(a, b, d)) || (o3 === 0 && within(c, d, a)) || (o4 === 0 && within(c, d, b));
}

/**
 * Prüft, ob der Ring ein einfaches Polygon ist: ganzzahlig, im Wertebereich, ohne doppelte Punkte, ohne
 * Berührung zweier Kanten außer der gemeinsamen Ecke von Nachbarn, ohne Rücklauf auf einer Linie, mit Fläche.
 * Clipper2 setzt einfache Ringe voraus; clipper2-ts hängt bei Rückläufen (Spike HM0, Kapitel 10).
 */
export function polygonDefect(polygon: Polygon): PolygonDefect | null {
  const n = polygon.length;
  if (n < 3) return "too_few_vertices";
  if (!isInteger(polygon)) return "coordinates_not_integer";
  if (polygon.some((p) => Math.abs(p.x) > MAX_COORDINATE || Math.abs(p.y) > MAX_COORDINATE)) return "coordinates_out_of_range";
  for (let i = 0; i < n; i++) {
    const a = polygon[i]!;
    const b = polygon[(i + 1) % n]!;
    if (a.x === b.x && a.y === b.y) return "zero_length_edge";
  }
  for (let i = 0; i < n; i++) {
    const a = polygon[i]!;
    const b = polygon[(i + 1) % n]!;
    for (let j = i + 1; j < n; j++) {
      const c = polygon[j]!;
      const d = polygon[(j + 1) % n]!;
      if (j === i + 1 || (i === 0 && j === n - 1)) {
        // Nachbarn teilen genau eine Ecke; auf einer Linie nur in gleicher Richtung
        const [p, q, r] = j === i + 1 ? [a, b, d] : [c, a, b];
        if (orient(p, q, r) === 0 && (q.x - p.x) * (r.x - q.x) + (q.y - p.y) * (r.y - q.y) < 0) return "self_intersecting";
        continue;
      }
      if (segmentsTouch(a, b, c, d)) return "self_intersecting";
    }
  }
  return signedArea(polygon) === 0 ? "zero_area" : null;
}
