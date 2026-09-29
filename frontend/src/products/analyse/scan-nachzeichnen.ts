/**
 * Reine Rechnung zum Nachzeichnen eines gescannten Plans (AN7, docs/PLAN_AN7_SCAN.md 3.5): Meter je Pixel aus
 * Maßstab und Papiermaß oder aus zwei Punkten mit bekanntem Abstand, Bildpunkte in lokale Meter. Norden gilt als
 * oben wie bei UP15; die Lage folgt später per AN5. Der Server bildet das Polygon aus den Kanten (L5).
 */

import type { LocalPoint } from "../../components/plan/PlanSvg";
import { edgesFromPoints, type ManualEdgeDraft } from "../../site/manual";

/** Bildpunkt: x nach rechts, y nach unten, in Pixeln des gelieferten Bilds. */
export type PixelPoint = readonly [number, number];

/** Höchstens so viele Seiten eines gescannten Plans sind wählbar (`pdfplan.MAX_PAGES`, wie beim vektoriellen PDF). */
export const MAX_SCAN_PAGES = 3;

/** Meter in der Natur je Pixel: Blattbreite in mm × Maßstab ÷ Bildbreite in Pixeln. */
export function metresPerPxFromScale(paperWidthMm: number, scale: number, widthPx: number): number {
  return ((paperWidthMm / 1000) * scale) / widthPx;
}

/** Meter je Pixel aus zwei angeklickten Punkten und der eingetragenen Länge dazwischen; `null` bei gleichen Punkten. */
export function metresPerPxFromPoints(a: PixelPoint, b: PixelPoint, lengthM: number): number | null {
  const px = Math.hypot(b[0] - a[0], b[1] - a[1]);
  return px > 0 && lengthM > 0 ? lengthM / px : null;
}

/** Bildpunkte in lokale Meter (Ost, Nord): y des Bilds zeigt nach unten, Nord nach oben. */
export function pixelsToLocal(points: readonly PixelPoint[], metresPerPx: number): LocalPoint[] {
  return points.map(([x, y]) => [x * metresPerPx, -y * metresPerPx]);
}

/** Kanten für den bekannten Schritt aus Weg E: Länge und Richtung, danach von Hand nach den Maßen im Plan korrigierbar. */
export function edgesFromPixels(points: readonly PixelPoint[], metresPerPx: number): ManualEdgeDraft[] {
  return edgesFromPoints(pixelsToLocal(points, metresPerPx));
}

/** Maßstab als ganze Zahl aus der Eingabe „500“ oder „1:500“; sonst `null`. */
export function parseScale(raw: string): number | null {
  const match = /^\s*(?:1\s*[:/]\s*)?(\d{2,5})\s*$/.exec(raw);
  const value = match ? Number(match[1]) : NaN;
  return value >= 50 && value <= 10_000 ? value : null;
}

/** Länge in Metern aus der Eingabe mit Komma oder Punkt; sonst `null`. */
export function parseLength(raw: string): number | null {
  const value = Number(raw.trim().replace(",", "."));
  return raw.trim() !== "" && Number.isFinite(value) && value > 0 && value <= 10_000 ? value : null;
}
