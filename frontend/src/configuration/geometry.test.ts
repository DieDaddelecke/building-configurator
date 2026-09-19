import { describe, expect, it } from "vitest";

import {
  centroid,
  dragTo,
  nearestInside,
  originKeepingCentre,
  placeRing,
  pointInRings,
  snap,
  translate,
  type Pt,
  type Ring,
} from "./geometry";

const SQUARE: Ring = [
  [0, 0],
  [10, 0],
  [10, 10],
  [0, 10],
  [0, 0],
];
const HOLE: Ring = [
  [4, 4],
  [6, 4],
  [6, 6],
  [4, 6],
  [4, 4],
];

describe("Fläche zulässiger Ursprünge im Browser", () => {
  it("erkennt Punkte innerhalb und außerhalb", () => {
    expect(pointInRings([5, 5], [SQUARE])).toBe(true);
    expect(pointInRings([11, 5], [SQUARE])).toBe(false);
    expect(pointInRings([-0.1, 5], [SQUARE])).toBe(false);
  });

  it("behandelt Löcher nach der gerade-ungerade-Regel", () => {
    expect(pointInRings([5, 5], [SQUARE, HOLE])).toBe(false);
    expect(pointInRings([2, 2], [SQUARE, HOLE])).toBe(true);
  });

  it("rastert auf Viertelmeter", () => {
    expect(snap(3.13)).toBeCloseTo(3.25);
    expect(snap(3.12)).toBeCloseTo(3.0);
    expect(snap(-0.13)).toBeCloseTo(-0.25);
  });

  it("findet den nächsten Randpunkt", () => {
    expect(nearestInside([12, 5], [SQUARE])).toEqual([10, 5]);
    expect(nearestInside([5, 5], [SQUARE])).toEqual([5, 5]);
    expect(nearestInside([1, 1], [])).toBeNull();
  });

  it("zieht nur innerhalb der Fläche und klebt sonst am Rand", () => {
    expect(dragTo([3.13, 4.9], [1, 1], [SQUARE])).toEqual([3.25, 5.0]);
    expect(dragTo([14, 5], [1, 1], [SQUARE])).toEqual([10, 5]);
    expect(dragTo([14, 5], [1, 1], [])).toEqual([1, 1]);
  });

  it("verschiebt Ringe und bestimmt die Mitte", () => {
    expect(translate(SQUARE, [1, 2])[0]).toEqual([1, 2]);
    expect(centroid(SQUARE)).toEqual([5, 5]);
  });
});

describe("Lage des Hauses", () => {
  const HOUSE: Ring = [
    [0, 0],
    [12, 0],
    [12, 8],
    [0, 8],
    [0, 0],
  ];

  it("dreht im Uhrzeigersinn wie der Server (Spez. 5.3.4)", () => {
    const placed = placeRing(HOUSE, [10, 10], 90);
    const xs = placed.map((p) => p[0]);
    const ys = placed.map((p) => p[1]);
    expect(Math.min(...xs)).toBeCloseTo(10);
    expect(Math.max(...xs)).toBeCloseTo(18);
    expect(Math.min(...ys)).toBeCloseTo(-2);
    expect(Math.max(...ys)).toBeCloseTo(10);
  });

  it("verschiebt bei Drehung 0 nur", () => {
    expect(placeRing(HOUSE, [4, 18], 0)[2]).toEqual([16, 26]);
  });
});

describe("Drehen um die Hausmitte", () => {
  it("hält die Mitte an ihrer Stelle", () => {
    const centre: Pt = [6, 4];
    const origin: Pt = [8, 25];
    const next = originKeepingCentre(centre, origin, 0, 90);
    const before = placeRing([centre], origin, 0)[0]!;
    const after = placeRing([centre], next, 90)[0]!;
    expect(after[0]).toBeCloseTo(before[0]);
    expect(after[1]).toBeCloseTo(before[1]);
  });
});
