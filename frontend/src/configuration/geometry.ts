/**
 * Rechnen im Browser beim Ziehen des Hauses (Plan H2 4.4, Spez. 8.2): Punkt in der Fläche zulässiger
 * Ursprünge, Einrasten und nächster gültiger Punkt. Die Antwort des Servers ist maßgeblich (L5); dies
 * ist nur die flüssige Vorschau. Alle Koordinaten sind lokale Meter (Ost, Nord).
 */

export type Pt = readonly [number, number];
export type Ring = readonly Pt[];

/** Raster der Verschiebung in Metern (Spez. 5.3.5, Mockup `RASTER_M`). */
export const GRID_M = 0.25;

/** Gerade-ungerade-Regel über alle Ringe: äußere Ringe und Löcher, auch mehrere Teilflächen. */
export function pointInRings(point: Pt, rings: readonly Ring[]): boolean {
  let inside = false;
  for (const ring of rings) {
    if (pointInRing(point, ring)) inside = !inside;
  }
  return inside;
}

function pointInRing([x, y]: Pt, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]!;
    const [xj, yj] = ring[j]!;
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function snap(value: number, step = GRID_M): number {
  return Math.round(value / step) * step;
}

function nearestOnSegment([px, py]: Pt, [ax, ay]: Pt, [bx, by]: Pt): Pt {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  const t = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared));
  return [ax + t * dx, ay + t * dy];
}

/** Nächster Punkt auf dem Rand der Fläche; liegt der Punkt schon darin, bleibt er. `null` bei leerer Fläche. */
export function nearestInside(point: Pt, rings: readonly Ring[]): Pt | null {
  if (rings.length === 0) return null;
  if (pointInRings(point, rings)) return point;
  let best: Pt | null = null;
  let bestDistance = Infinity;
  for (const ring of rings) {
    for (let i = 0; i < ring.length - 1; i++) {
      const candidate = nearestOnSegment(point, ring[i]!, ring[i + 1]!);
      const distance = Math.hypot(candidate[0] - point[0], candidate[1] - point[1]);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = candidate;
      }
    }
  }
  return best;
}

/**
 * Neue Lage beim Ziehen: gerastert, und nur, wenn sie in der Fläche liegt. Sonst der letzte gültige Punkt
 * (das Haus „klebt“ an der Grenze, statt zu springen). Bei leerer Fläche ändert sich nichts.
 */
export function dragTo(target: Pt, last: Pt, rings: readonly Ring[]): Pt {
  if (rings.length === 0) return last;
  const snapped: Pt = [snap(target[0]), snap(target[1])];
  if (pointInRings(snapped, rings)) return snapped;
  // Ein gerasterter Punkt knapp außerhalb: der ungerasterte kann noch innen liegen
  if (pointInRings(target, rings)) return target;
  return nearestInside(target, rings) ?? last;
}

export function translate(ring: Ring, [dx, dy]: Pt): Ring {
  return ring.map(([x, y]) => [x + dx, y + dy] as const);
}

export function centroid(ring: Ring): Pt {
  const points = ring.length > 1 && ring[0]![0] === ring.at(-1)![0] && ring[0]![1] === ring.at(-1)![1] ? ring.slice(0, -1) : ring;
  const sum = points.reduce<[number, number]>(([sx, sy], [x, y]) => [sx + x, sy + y], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}

/**
 * Modellring in die Lage bringen (Spez. 5.3.4): im Uhrzeigersinn um den Modellursprung drehen, dann auf
 * `origin` verschieben. Modellnorden (+Y) zeigt danach nach Azimut `rotationDeg`.
 */
/** Ursprung nach einer Drehung, bei der die Hausmitte an ihrer Stelle bleibt (statt um die Ecke zu schwenken). */
export function originKeepingCentre(modelCentre: Pt, origin: Pt, fromDeg: number, toDeg: number): Pt {
  const before = placeRing([modelCentre], origin, fromDeg)[0]!;
  const after = placeRing([modelCentre], [0, 0], toDeg)[0]!;
  return [before[0] - after[0], before[1] - after[1]];
}

export function placeRing(ring: Ring, origin: Pt, rotationDeg: number): Ring {
  const rad = (rotationDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return ring.map(([x, y]) => [origin[0] + x * cos + y * sin, origin[1] - x * sin + y * cos] as const);
}
