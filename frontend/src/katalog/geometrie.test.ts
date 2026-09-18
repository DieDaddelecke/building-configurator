import { describe, expect, it } from "vitest";

import { edgesOf, pointOnEdge, readPlacement, ringArea, suggestRoles } from "./geometrie";

// 12 × 8 m, gegen den Uhrzeigersinn, Y nach Norden: Kante 0 unten (Süd), 1 rechts (Ost), 2 oben (Nord), 3 links (West)
const RECHTECK = [
  [0, 0],
  [12, 0],
  [12, 8],
  [0, 8],
];

describe("Umriss des Typs", () => {
  it("berechnet Kanten mit Länge und Außennormale", () => {
    const [south, east] = edgesOf(RECHTECK);
    expect(south!.length).toBe(12);
    expect(south!.normal).toEqual([0, -1]);
    expect(east!.normal[0]).toBeCloseTo(1);
    expect(east!.normal[1]).toBeCloseTo(0);
  });

  it("legt Punkte auf Kanten", () => {
    expect(pointOnEdge(edgesOf(RECHTECK)[0]!, 0.25)).toEqual([3, 0]);
  });

  it("schlägt für ein Rechteck Straße an der langen Seite, Garten gegenüber und Seiten vor", () => {
    // längste Kante 0 (Süd) ist die Straße; Blick nach Norden, links ist Westen (Kante 3)
    expect(suggestRoles(RECHTECK)).toEqual({ 0: "street", 2: "garden", 3: "side_left", 1: "side_right" });
  });

  it("lässt Kanten ohne eindeutige Lage ohne Rolle", () => {
    // L-Form: die Versätze innen liegen parallel zu Straße oder Seite und bekommen ebenfalls eine Rolle,
    // eine schräge Kante bleibt leer
    const schraeg = [
      [0, 0],
      [12, 0],
      [12, 5],
      [8, 8],
      [0, 8],
    ];
    const roles = suggestRoles(schraeg);
    expect(roles[0]).toBe("street");
    expect(roles[2]).toBeUndefined();
  });

  it("gibt jeder Kante gegenüber der Straße die Rolle Garten, auch bei einem Versatz", () => {
    // L-Form 16,5 × 8 m mit Einschnitt oben links: zwei Kanten zeigen nach Norden
    const lForm = [
      [0, 0],
      [16.5, 0],
      [16.5, 8],
      [6, 8],
      [6, 5],
      [0, 5],
    ];
    expect(suggestRoles(lForm)).toEqual({
      0: "street",
      1: "side_right",
      2: "garden",
      3: "side_left",
      4: "garden",
      5: "side_left",
    });
  });

  it("gibt bei zu wenigen Punkten nichts vor", () => {
    expect(suggestRoles([[0, 0], [1, 1]])).toEqual({});
  });

  it("liest die Platzierung nur in der erwarteten Form", () => {
    expect(readPlacement({ edge: 2, position: 0.5 })).toEqual({ edge: 2, position: 0.5 });
    expect(readPlacement({ x: 1 })).toBeNull();
    expect(readPlacement(null)).toBeNull();
  });

  it("stimmt in der Fläche mit dem Serverwert überein", () => {
    expect(ringArea(RECHTECK)).toBe(96);
  });
});
