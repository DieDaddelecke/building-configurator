// Polygon-Offset mit Clipper2 (clipper2-ts, Spike HM0: richtig, ganzzahlig, 17 kB gzip; docs/PLAN_HAUSMODELL.md Kapitel 10).
import { EndType, FillRule, inflatePaths, JoinType, union } from "clipper2-ts";
import type { GeometryErrorCode } from "../codes.ts";
import { counterClockwise, polygonDefect, type Point, type Polygon } from "./polygon.ts";

/** Gehrung bis zum Vierfachen des Abstands: rechte und stumpfe Hausecken bleiben spitz, nur sehr spitze werden gekappt. */
const MITER_LIMIT = 4;

export class GeometryError extends Error {
  readonly code: GeometryErrorCode;

  constructor(code: GeometryErrorCode) {
    super(code);
    this.code = code;
  }
}

function assertSimple(polygon: Polygon): void {
  const defect = polygonDefect(polygon);
  if (defect) {
    throw new GeometryError(defect);
  }
}

function single(paths: readonly (readonly Point[])[], reason: GeometryErrorCode): Polygon {
  if (paths.length !== 1) {
    throw new GeometryError(reason);
  }
  // Clipper2 liefert gelegentlich -0; für Gleichheit und Prüfsummen auf 0 bringen
  return counterClockwise(paths[0]!.map(({ x, y }) => ({ x: x + 0, y: y + 0 })));
}

/**
 * Versatz eines einfachen Polygons um `distance` Einheiten (positiv nach außen) mit Gehrung.
 * So entsteht aus der Bezugskontur die Außenkante einer Schicht (P 6.1).
 */
export function offsetPolygon(polygon: Polygon, distance: number): Polygon {
  assertSimple(polygon);
  if (!Number.isSafeInteger(distance)) {
    throw new GeometryError("distance_not_integer");
  }
  const ring = counterClockwise(polygon).map(({ x, y }) => ({ x, y }));
  return single(inflatePaths([ring], distance, JoinType.Miter, EndType.Polygon, MITER_LIMIT), "offset_not_single");
}

/** Vereinigung einfacher, sich ggf. überlappender Polygone zu genau einem Polygon (z. B. Geschossumrisse zum Fassadenumriss). */
export function unionPolygons(polygons: readonly Polygon[]): Polygon {
  polygons.forEach(assertSimple);
  const rings = polygons.map((p) => counterClockwise(p).map(({ x, y }) => ({ x, y })));
  return single(union(rings, FillRule.NonZero), "union_not_single");
}
