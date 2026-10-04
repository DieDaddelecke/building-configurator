import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { GeometryError, offsetPolygon, unionPolygons } from "./offset.ts";
import { areaSquareMetres, perimeterMetres, signedArea, toUnits, type Polygon } from "./polygon.ts";

const m = (x: number, y: number) => ({ x: toUnits(x), y: toUnits(y) });

// Bezugskontur der Probedatei 2 (Innenkante der Außenwände, relativ zur Ecke), docs/PLAN_HAUSMODELL.md Kapitel 10
const L_SHAPE: Polygon = [m(0, 0), m(10, 0), m(10, 4), m(6, 4), m(6, 6.5), m(0, 6.5)];

describe("offsetPolygon", () => {
  it("ergibt die Außenkontur der Probedatei 2 bei 0,30 m Wand", () => {
    const outline = offsetPolygon(L_SHAPE, toUnits(0.3));
    expect(areaSquareMetres(L_SHAPE)).toBeCloseTo(55.0, 10);
    expect(areaSquareMetres(outline)).toBeCloseTo(65.26, 10);
    expect(outline).toHaveLength(6);
    expect(outline).toEqual(expect.arrayContaining([m(-0.3, -0.3), m(10.3, -0.3), m(10.3, 4.3), m(6.3, 4.3), m(6.3, 6.8), m(-0.3, 6.8)]));
    expect(signedArea(outline)).toBeGreaterThan(0);
  });

  it("nimmt die Ausrichtung im Uhrzeigersinn an", () => {
    expect(offsetPolygon([...L_SHAPE].reverse(), toUnits(0.3))).toEqual(offsetPolygon(L_SHAPE, toUnits(0.3)));
  });

  it("lehnt Kommazahlen ab", () => {
    expect(() => offsetPolygon([{ x: 0.5, y: 0 }, m(1, 0), m(1, 1)], 100)).toThrow(GeometryError);
  });

  // Rechtwinklige Hülle: Umfang der Mittellinie einer Schicht mit Abstand d = Innenumfang + 8·d (P 7)
  it("hält die Umfangsformel für Rechtecke und L-Formen ein", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 30_000, max: 200_000 }),
        fc.integer({ min: 30_000, max: 200_000 }),
        fc.integer({ min: 1, max: 6_000 }),
        (a, b, d) => {
          const rect: Polygon = [{ x: 0, y: 0 }, { x: a, y: 0 }, { x: a, y: b }, { x: 0, y: b }];
          const outline = offsetPolygon(rect, d);
          expect(perimeterMetres(outline)).toBeCloseTo(perimeterMetres(rect) + (8 * d) / 10_000, 6);
          expect(offsetPolygon(outline, -d)).toEqual(expect.arrayContaining([...rect]));
        },
      ),
    );
  });
});

describe("unionPolygons", () => {
  it("vereinigt überlappende Umrisse zu einem", () => {
    const a: Polygon = [m(0, 0), m(10, 0), m(10, 4), m(0, 4)];
    const b: Polygon = [m(0, 0), m(6, 0), m(6, 6.5), m(0, 6.5)];
    expect(areaSquareMetres(unionPolygons([a, b]))).toBeCloseTo(55.0, 10);
  });

  it("meldet getrennte Teile", () => {
    const a: Polygon = [m(0, 0), m(1, 0), m(1, 1), m(0, 1)];
    const b: Polygon = [m(5, 0), m(6, 0), m(6, 1), m(5, 1)];
    expect(() => unionPolygons([a, b])).toThrow("union_not_single");
  });
});
