import { describe, expect, it } from "vitest";

import { centerOf, compass, firstPosition, midpoint, siteBounds, unionBbox } from "./geo";

describe("Himmelsrichtung", () => {
  it("ordnet 45°-Sektoren um die Hauptrichtungen zu", () => {
    expect(compass(0)).toBe("n");
    expect(compass(22.4)).toBe("n");
    expect(compass(22.6)).toBe("ne");
    expect(compass(209.6)).toBe("sw");
    expect(compass(359)).toBe("n");
    expect(compass(-90)).toBe("w");
  });
});

describe("Planhilfen", () => {
  it("findet die Mitte einer Polylinie nach Länge", () => {
    expect(midpoint([[0, 0], [10, 0], [10, 10]])).toEqual([10, 0]);
    expect(midpoint([[0, 0], [4, 0]])).toEqual([2, 0]);
  });

  it("berechnet die Ausdehnung aller Ringe", () => {
    const bounds = siteBounds({ outline_local: [[[1, 2], [21, 2], [21, 33], [1, 2]]] });
    expect(bounds).toEqual({ minE: 1, minN: 2, maxE: 21, maxN: 33 });
  });
});

describe("Kartenausschnitt", () => {
  it("nimmt die Mitte des äußeren Rings, auch bei MultiPolygon", () => {
    const ring = [[0, 0], [2, 0], [2, 4], [0, 4], [0, 0]];
    expect(centerOf({ type: "Polygon", coordinates: [ring] })).toEqual([1, 2]);
    expect(centerOf({ type: "MultiPolygon", coordinates: [[ring]] })).toEqual([1, 2]);
    expect(firstPosition({ type: "Polygon", coordinates: [ring] })).toEqual([0, 0]);
    expect(centerOf(null)).toBeNull();
  });
});

describe("Gemeinsame Ausdehnung", () => {
  it("umfasst alle Gemeinden und ist ohne Gemeinde leer", () => {
    expect(unionBbox([])).toBeNull();
    expect(
      unionBbox([
        [-1.7, 47.3, -1.6, 47.4],
        [2.29, 48.84, 2.33, 48.86],
      ]),
    ).toEqual([-1.7, 47.3, 2.33, 48.86]);
  });
});
