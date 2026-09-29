import { expect, it } from "vitest";

import { abstandM, drehen, meterJeGrad, tastenSchritt, umrissAufKarte, verschieben, winkel } from "./einpassen";

/** Richtung einer Strecke in Grad im Uhrzeigersinn von Nord, aus Länge/Breite. */
function richtung([lon1, lat1]: number[], [lon2, lat2]: number[]): number {
  const m = meterJeGrad((lat1! + lat2!) / 2);
  return ((Math.atan2((lon2! - lon1!) * m.ost, (lat2! - lat1!) * m.nord) * 180) / Math.PI + 360) % 360;
}

it("dreht im Uhrzeigersinn: Nord wird nach 90° Ost", () => {
  const [x, y] = drehen([0, 1], 90);
  expect(x).toBeCloseTo(1, 12);
  expect(y).toBeCloseTo(0, 12);
  const [x30, y30] = drehen([0, 10], 30);
  expect(x30).toBeCloseTo(5, 9);
  expect(y30).toBeCloseTo(8.660254, 6);
});

it("setzt den Drehpunkt auf die Lage und dreht den Umriss um Δ (Abnahme 1)", () => {
  const rechteck = [[[0, 0], [20, 0], [20, 30], [0, 30]]];
  const zentrum = { lon: -1.6186, lat: 47.3322 };
  const [ring] = umrissAufKarte(rechteck, [10, 15], zentrum, 30);
  expect(ring).toHaveLength(5);
  expect(ring![4]).toEqual(ring![0]);
  // Die Kante, die auf dem Blatt nach Norden lief (20,0)–(20,30), zeigt nach 30°
  expect(richtung(ring![1]!, ring![2]!)).toBeCloseTo(30, 3);
  // Längen bleiben: 30 m und 20 m
  const m = meterJeGrad(zentrum.lat);
  const laenge = (a: number[], b: number[]) => Math.hypot((b[0]! - a[0]!) * m.ost, (b[1]! - a[1]!) * m.nord);
  expect(laenge(ring![1]!, ring![2]!)).toBeCloseTo(30, 3);
  expect(laenge(ring![0]!, ring![1]!)).toBeCloseTo(20, 3);
  // Der Schwerpunkt liegt auf der Lage
  const mitte = [(ring![0]![0]! + ring![2]![0]!) / 2, (ring![0]![1]! + ring![2]![1]!) / 2];
  expect(mitte[0]).toBeCloseTo(zentrum.lon, 9);
  expect(mitte[1]).toBeCloseTo(zentrum.lat, 9);
});

it("verschiebt in Metern und misst den Versatz", () => {
  const start = { lon: -1.6186, lat: 47.3322 };
  const nord = verschieben(start, 0, 1);
  expect(nord.lon).toBe(start.lon);
  expect(nord.lat - start.lat).toBeCloseTo(1 / 111_190, 8);
  expect(abstandM(start, verschieben(start, 3, 4))).toBeCloseTo(5, 5);
});

it("übersetzt Pfeiltasten in 0,1 m und mit Umschalttaste in 1 m", () => {
  expect(tastenSchritt("ArrowUp", false)).toEqual([0, 0.1]);
  expect(tastenSchritt("ArrowLeft", true)).toEqual([-1, 0]);
  expect(tastenSchritt("Enter", false)).toBeNull();
});

it("hält den Winkel auf (−180°, 180°] und 0,1°", () => {
  expect(winkel(181)).toBe(-179);
  expect(winkel(-180)).toBe(180);
  expect(winkel(0.1 + 0.2)).toBe(0.3);
  expect(winkel(-0.04)).toBe(0);
});
