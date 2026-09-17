import { describe, expect, it } from "vitest";

import { azimuthDeg, distance, edgesFromPoints, pointsFromEdges, polygonArea } from "./manual";

describe("Azimut und Länge", () => {
  it("0° = Norden, im Uhrzeigersinn", () => {
    expect(azimuthDeg([0, 0], [0, 10])).toBeCloseTo(0);
    expect(azimuthDeg([0, 0], [10, 0])).toBeCloseTo(90);
    expect(azimuthDeg([0, 0], [0, -10])).toBeCloseTo(180);
    expect(azimuthDeg([0, 0], [-10, 0])).toBeCloseTo(270);
    expect(distance([0, 0], [3, 4])).toBeCloseTo(5);
  });
});

describe("Kanten aus gezeichneten Punkten", () => {
  it("liefert n − 1 Kanten für n Punkte; die Schlusskante bleibt aus", () => {
    const points: [number, number][] = [[0, 0], [10, 0], [10, 20]];
    const edges = edgesFromPoints(points);
    expect(edges).toHaveLength(2);
    expect(edges[0]).toEqual({ length_m: 10, angle_deg: 90 });
    expect(edges[1]).toEqual({ length_m: 20, angle_deg: 0 });
  });

  it("baut aus denselben Kanten dieselben Punkte zurück (Hin- und Rückweg)", () => {
    const points: [number, number][] = [[0, 0], [10, 0], [10, 20], [-5, 20]];
    const rebuilt = pointsFromEdges(edgesFromPoints(points));
    for (const [i, point] of points.entries()) {
      expect(rebuilt[i]?.[0]).toBeCloseTo(point[0]);
      expect(rebuilt[i]?.[1]).toBeCloseTo(point[1]);
    }
  });
});

describe("Fläche", () => {
  it("misst ein 20 × 10 m Rechteck unabhängig vom Drehsinn", () => {
    const ccw: [number, number][] = [[0, 0], [20, 0], [20, 10], [0, 10]];
    const cw = [...ccw].reverse() as [number, number][];
    expect(polygonArea(ccw)).toBeCloseTo(200);
    expect(polygonArea(cw)).toBeCloseTo(200);
  });
});
