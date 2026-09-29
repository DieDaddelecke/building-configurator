import { expect, it } from "vitest";

import { pointsFromEdges, polygonArea } from "../../site/manual";
import {
  edgesFromPixels,
  metresPerPxFromPoints,
  metresPerPxFromScale,
  parseLength,
  parseScale,
  pixelsToLocal,
  type PixelPoint,
} from "./scan-nachzeichnen";

// Katasterauszug A5 quer (210 × 148 mm) mit 200 dpi, Maßstab 1:500: Rechteck 60 × 40 mm = 30 × 20 m in der Natur,
// wie im Test des Servers (`test_site_upload.scanned_plan`). Ecken so ungenau geklickt, wie es mit der Maus geht.
const PX_PER_MM = 200 / 25.4;
const WIDTH_PX = Math.round(210 * PX_PER_MM);
const ecke = (xMm: number, yMm: number, fehlerPx = 0): PixelPoint => [xMm * PX_PER_MM + fehlerPx, yMm * PX_PER_MM - fehlerPx];
const ECKEN: PixelPoint[] = [ecke(40, 60, 2), ecke(100, 60, -1), ecke(100, 100, 2), ecke(40, 100, -2)];

function flaeche(points: readonly PixelPoint[], metresPerPx: number): number {
  return polygonArea(pointsFromEdges(edgesFromPixels(points, metresPerPx)));
}

it("rechnet aus Maßstab und Papiermaß Meter je Pixel (Abnahme 5)", () => {
  const m = metresPerPxFromScale(210, 500, WIDTH_PX);
  expect(m * WIDTH_PX).toBeCloseTo(105, 6);
  expect(Math.abs(flaeche(ECKEN, m) - 600) / 600).toBeLessThan(0.02);
});

it("kalibriert über zwei Punkte mit bekanntem Abstand, auch bei vergrößerter Kopie", () => {
  // Kopie mit 141 %: Das Papiermaß stimmt nicht mehr, die Bezugslänge schon
  const vergroessert = ECKEN.map(([x, y]) => [x * 1.41, y * 1.41] as const);
  const m = metresPerPxFromPoints(vergroessert[0]!, vergroessert[1]!, 30);
  expect(m).not.toBeNull();
  expect(Math.abs(flaeche(vergroessert, m!) - 600) / 600).toBeLessThan(0.02);
  expect(metresPerPxFromPoints([5, 5], [5, 5], 30)).toBeNull();
  expect(metresPerPxFromPoints([0, 0], [10, 0], 0)).toBeNull();
});

it("dreht die Bildachse: unten im Bild ist Süden", () => {
  expect(pixelsToLocal([[10, 20]], 0.5)).toEqual([[5, -10]]);
  // Erste Kante des Rechtecks läuft nach Osten, die zweite nach Süden
  const [ost, sued] = edgesFromPixels([ecke(40, 60), ecke(100, 60), ecke(100, 100)], 0.0635);
  expect(ost!.angle_deg).toBeCloseTo(90, 0);
  expect(sued!.angle_deg).toBeCloseTo(180, 0);
});

it("liest Maßstab und Länge aus der Eingabe", () => {
  expect(parseScale("500")).toBe(500);
  expect(parseScale("1:500")).toBe(500);
  expect(parseScale(" 1/1000 ")).toBe(1000);
  expect(parseScale("1:5")).toBeNull();
  expect(parseScale("abc")).toBeNull();
  expect(parseLength("30,5")).toBe(30.5);
  expect(parseLength("12.25")).toBe(12.25);
  expect(parseLength("")).toBeNull();
  expect(parseLength("-3")).toBeNull();
});
