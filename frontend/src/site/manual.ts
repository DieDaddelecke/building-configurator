/**
 * Reine Geometrie für Weg E (freies Zeichnen ohne Kataster, Plan 3.3). Azimut: 0° = Norden, im
 * Uhrzeigersinn, wie im übrigen Modul. Der Server baut aus denselben `n − 1` Kanten (Länge, Azimut)
 * dasselbe Polygon (`app.site.domain.manual.build_manual_polygon`); diese Datei dient nur der Vorschau
 * im Browser (L5: der Server ist maßgeblich, hier wird nichts geprüft).
 */

import type { LocalPoint } from "../components/plan/PlanSvg";

export interface ManualEdgeDraft {
  length_m: number;
  angle_deg: number;
}

export function azimuthDeg(from: LocalPoint, to: LocalPoint): number {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const deg = (Math.atan2(dx, dy) * 180) / Math.PI;
  return (deg + 360) % 360;
}

export function distance(from: LocalPoint, to: LocalPoint): number {
  return Math.hypot(to[0] - from[0], to[1] - from[1]);
}

/** Aus `n` gezeichneten Punkten die ersten `n − 1` Kanten (Länge, Azimut); die letzte schließt
 * serverseitig automatisch (Plan 3.3). Auf einen Dezimalschritt gerundet: Klickkoordinaten ergäben sonst
 * unhandliche Nachkommastellen in einem Feld, das der Nutzer als Nächstes von Hand bearbeitet. */
export function edgesFromPoints(points: readonly LocalPoint[]): ManualEdgeDraft[] {
  const edges: ManualEdgeDraft[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const from = points[i];
    const to = points[i + 1];
    if (!from || !to) continue;
    edges.push({
      length_m: Math.round(distance(from, to) * 10) / 10,
      angle_deg: Math.round(azimuthDeg(from, to) * 10) / 10,
    });
  }
  return edges;
}

/** Baut den Umriss aus den (ggf. bearbeiteten) Kanten neu auf – dieselbe Wanderung wie der Server, nur
 * zur Vorschau; die Schlusskante ergibt sich implizit beim Zeichnen (erster Punkt = letzter). */
export function pointsFromEdges(edges: readonly ManualEdgeDraft[]): LocalPoint[] {
  const points: LocalPoint[] = [[0, 0]];
  let x = 0;
  let y = 0;
  for (const edge of edges) {
    const rad = (edge.angle_deg * Math.PI) / 180;
    x += edge.length_m * Math.sin(rad);
    y += edge.length_m * Math.cos(rad);
    points.push([x, y]);
  }
  return points;
}

/** Fläche nach der Gauß'schen Trapezformel; `points` gilt als geschlossen (erster = letzter Punkt). */
export function polygonArea(points: readonly LocalPoint[]): number {
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    if (!a || !b) continue;
    sum += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(sum) / 2;
}
