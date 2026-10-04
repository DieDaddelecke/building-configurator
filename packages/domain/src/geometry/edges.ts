// Kanten einer versetzten Kontur den Kanten der Bezugskontur zuordnen (P 6.1: Schichten wieder in Segmente
// zerlegen, gleiche Segment-IDs wie die Referenz). Ganzzahlig in 0,1 mm.
import { signedArea, type Point, type Polygon } from "./polygon.ts";

/** Abweichung, die das Runden schräger Ecken auf ganze Einheiten verursachen kann. */
const TOLERANCE = 2;

export function edgeLength(a: Point, b: Point): number {
  // sqrt ist in IEEE 754 exakt gerundet, das Quadrat ganzzahlig exakt: gleich in jedem Browser (anders als hypot)
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
}

export function perimeter(polygon: Polygon): number {
  let length = 0;
  for (let i = 0; i < polygon.length; i++) {
    length += edgeLength(polygon[i]!, polygon[(i + 1) % polygon.length]!);
  }
  return length;
}

function cross(a: Point, b: Point, c: Point): number {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

/**
 * Für jede Kante `i` der Bezugskontur (gegen den Uhrzeigersinn) die Kante der um `distance` nach außen
 * versetzten Kontur, die auf ihrer Parallelen liegt; −1, wenn sie beim Versatz verschwunden ist.
 */
export function matchEdges(reference: Polygon, outline: Polygon, distance: number): number[] {
  if (signedArea(reference) <= 0 || signedArea(outline) <= 0) throw new Error("matchEdges: gegen den Uhrzeigersinn");
  return reference.map((a, i) => {
    const b = reference[(i + 1) % reference.length]!;
    const length = edgeLength(a, b);
    const ux = (b.x - a.x) / length;
    const uy = (b.y - a.y) / length;
    let best = -1;
    let bestGap = Infinity;
    outline.forEach((c, j) => {
      const d = outline[(j + 1) % outline.length]!;
      if ((d.x - c.x) * ux + (d.y - c.y) * uy <= 0) return;
      // außen liegt rechts der Laufrichtung: Abstand −distance
      if (Math.abs(cross(a, b, c) / length + distance) > TOLERANCE) return;
      if (Math.abs(cross(a, b, d) / length + distance) > TOLERANCE) return;
      const middle = ((c.x + d.x) / 2 - a.x) * ux + ((c.y + d.y) / 2 - a.y) * uy;
      const gap = Math.abs(middle - length / 2);
      if (middle >= -distance - TOLERANCE && middle <= length + distance + TOLERANCE && gap < bestGap) {
        best = j;
        bestGap = gap;
      }
    });
    return best;
  });
}

/** Ring so drehen, dass `first` die erste Kante wird. */
export function rotate<T>(ring: readonly T[], first: number): T[] {
  return first <= 0 ? [...ring] : [...ring.slice(first), ...ring.slice(0, first)];
}
