import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { unionPolygons } from "./offset.ts";
import { MAX_COORDINATE, polygonDefect, type Polygon } from "./polygon.ts";

const P = (...points: [number, number][]): Polygon => points.map(([x, y]) => ({ x, y }));

describe("polygonDefect", () => {
  it.each([
    ["L-Form", P([0, 0], [100, 0], [100, 40], [60, 40], [60, 65], [0, 65])],
    ["Ecke auf gerader Linie", P([0, 0], [50, 0], [100, 0], [100, 10], [0, 10])],
    ["Uhrzeigersinn", P([0, 0], [0, 10], [10, 10], [10, 0])],
    ["Dreieck", P([0, 0], [10, 0], [0, 10])],
  ])("nimmt an: %s", (_name, polygon) => {
    expect(polygonDefect(polygon)).toBeNull();
  });

  it.each([
    ["zwei Ecken", P([0, 0], [10, 0]), "too_few_vertices"],
    ["Kommazahl", P([0, 0], [10.5, 0], [10, 10]), "coordinates_not_integer"],
    ["zu weit", P([0, 0], [MAX_COORDINATE + 1, 0], [0, 10]), "coordinates_out_of_range"],
    ["doppelter Punkt", P([0, 0], [10, 0], [10, 0], [10, 10]), "zero_length_edge"],
    ["Schleife", P([0, 0], [10, 10], [10, 0], [0, 10]), "self_intersecting"],
    // Rücklauf auf einer Linie: hier hängt clipper2-ts (Spike HM0)
    ["Rücklauf", P([0, 0], [100, 0], [90, 0], [89, 5], [11, 5], [10, 0], [5, 0]), "self_intersecting"],
    ["Rücklauf über den Ringanfang", P([5, 0], [0, 0], [10, 0], [10, 10]), "self_intersecting"],
    ["Berührung in einer Ecke", P([0, 0], [10, 0], [10, 10], [20, 10], [20, 20], [10, 20], [10, 10], [0, 10]), "self_intersecting"],
    ["Ecke auf fremder Kante", P([0, 0], [20, 0], [20, 10], [10, 0], [0, 10]), "self_intersecting"],
    ["Linie", P([0, 0], [10, 0], [20, 0]), "self_intersecting"],
  ])("lehnt ab: %s", (_name, polygon, defect) => {
    expect(polygonDefect(polygon)).toBe(defect);
  });

  it("hält Vereinigungen aus Rechtecken für einfach", () => {
    const rect = fc.record({ x: fc.integer({ min: 0, max: 20 }), y: fc.integer({ min: 0, max: 20 }), w: fc.integer({ min: 1, max: 10 }), h: fc.integer({ min: 1, max: 10 }) });
    fc.assert(
      fc.property(fc.array(rect, { minLength: 1, maxLength: 4 }), (rects) => {
        let union: Polygon;
        try {
          union = unionPolygons(rects.map(({ x, y, w, h }) => P([x, y], [x + w, y], [x + w, y + h], [x, y + h])));
        } catch {
          return; // getrennte Teile oder Löcher
        }
        expect(polygonDefect(union)).toBeNull();
      }),
    );
  });
});
