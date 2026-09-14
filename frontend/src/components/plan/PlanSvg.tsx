/**
 * Zeichenfläche für Lagepläne in lokalen Metern (Ursprung `site.local_origin`, Achsen Ost/Nord, Spez. 5.3.2).
 * Norden liegt oben: Die API liefert N nach oben, SVG zählt y nach unten. `toSvg` kehrt die y-Achse um
 * (Plan 3.5). Alle Kinder zeichnen in SVG-Koordinaten, also nach `toSvg`.
 */

import type { ReactNode } from "react";

export type LocalPoint = readonly [east: number, north: number];

export const toSvg = ([east, north]: LocalPoint): [number, number] => [east, -north];

export function ringPath(ring: readonly LocalPoint[]): string {
  return (
    ring
      .map((point, i) => {
        const [x, y] = toSvg(point);
        return `${i === 0 ? "M" : "L"}${x.toFixed(3)} ${y.toFixed(3)}`;
      })
      .join("") + "Z"
  );
}

/** Pfad für Polygone mit Löchern (erster Ring außen); mit `fillRule="evenodd"` zeichnen. */
export function polygonPath(rings: readonly (readonly LocalPoint[])[]): string {
  return rings.map(ringPath).join("");
}

export interface Bounds {
  minE: number;
  minN: number;
  maxE: number;
  maxN: number;
}

export function boundsOf(points: readonly LocalPoint[]): Bounds {
  if (points.length === 0) return { minE: 0, minN: 0, maxE: 1, maxN: 1 };
  return points.reduce<Bounds>(
    (b, [e, n]) => ({
      minE: Math.min(b.minE, e),
      minN: Math.min(b.minN, n),
      maxE: Math.max(b.maxE, e),
      maxN: Math.max(b.maxN, n),
    }),
    { minE: Infinity, minN: Infinity, maxE: -Infinity, maxN: -Infinity },
  );
}

interface PlanSvgProps {
  bounds: Bounds;
  /** Rand um die Zeichnung in Metern, Platz für Maßketten und Beschriftung */
  rand?: number;
  label: string;
  children: ReactNode;
}

export function PlanSvg({ bounds, rand = 6, label, children }: PlanSvgProps) {
  const x = bounds.minE - rand;
  const y = -bounds.maxN - rand;
  const w = bounds.maxE - bounds.minE + 2 * rand;
  const h = bounds.maxN - bounds.minN + 2 * rand;
  return (
    <svg viewBox={`${x} ${y} ${w} ${h}`} className="w-full h-auto block select-none" role="img" aria-label={label}>
      {children}
    </svg>
  );
}
