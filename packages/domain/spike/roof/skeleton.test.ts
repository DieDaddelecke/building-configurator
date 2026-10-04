// Spike HM0: Prüfung des gewichteten Skeletts gegen das Archicad-Walmdach der Probedatei 2 und an den klassischen
// Dachformen (docs/PLAN_HAUSMODELL.md Ergänzung 11). Invarianten: jede Fläche liegt auf ihrem Neigungsprofil,
// die Grundrisse der Flächen decken die Kontur genau ab.
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { unionPolygons } from "../../src/geometry/offset.ts";
import { toMetres, toUnits } from "../../src/geometry/polygon.ts";
import { GABLE, plane, signedArea, tan, weightedSkeleton, type EdgeProfile, type RoofFace, type Vec, type Vec3 } from "./skeleton.ts";

const MM = 0.001;

const RECT: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }];
// Bezugskontur der Probedatei 2 (Innenseite der Platzhalter-Wände, Ursprung bei 10,6406 / 13,2722)
const L_SHAPE: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 }, { x: 6, y: 4 }, { x: 6, y: 6.5 }, { x: 0, y: 6.5 }];
const T_SHAPE: Vec[] = [{ x: 4, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 4 }, { x: 12, y: 4 }, { x: 12, y: 8 }, { x: 0, y: 8 }, { x: 0, y: 4 }, { x: 4, y: 4 }];
const U_SHAPE: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 7, y: 8 }, { x: 7, y: 3 }, { x: 3, y: 3 }, { x: 3, y: 8 }, { x: 0, y: 8 }];

/** Giebel an den Enden der Flügel, sonst Neigung. */
const GABLE_ENDS: Record<string, readonly number[]> = { RECT: [1, 3], L: [1, 4], T: [0, 3, 5], U: [2, 6] };
const SHAPES: Record<string, Vec[]> = { RECT, L: L_SHAPE, T: T_SHAPE, U: U_SHAPE };

/** Waagerechter Weg der Kante bis zur Höhe z laut Profil. */
function offsetOf(profile: EdgeProfile, z: number): number {
  let h0 = 0;
  let offset = 0;
  for (const s of profile) {
    const h1 = Math.min(s.untilHeight, z);
    if (h1 > h0 && Number.isFinite(s.slope)) offset += (h1 - h0) / s.slope;
    h0 = s.untilHeight;
    if (h0 >= z) break;
  }
  return offset;
}

function expectValid(polygon: readonly Vec[], profiles: readonly EdgeProfile[], faces: readonly RoofFace[]) {
  expect(faces).toHaveLength(polygon.length);
  let covered = 0;
  for (const face of faces) {
    const p = polygon[face.edge]!;
    const q = polygon[(face.edge + 1) % polygon.length]!;
    const length = Math.hypot(q.x - p.x, q.y - p.y);
    const n = { x: -(q.y - p.y) / length, y: (q.x - p.x) / length };
    for (const v of face.boundary) {
      const distance = n.x * (v.x - p.x) + n.y * (v.y - p.y);
      expect(Math.abs(distance - offsetOf(profiles[face.edge]!, v.z))).toBeLessThan(1e-6);
    }
    const area = signedArea(face.boundary);
    expect(area).toBeGreaterThan(-1e-9);
    covered += area;
  }
  expect(covered).toBeCloseTo(signedArea(polygon), 9);
}

/** Knoten oberhalb des Auflagers, ohne Doppelte. */
function ridgeNodes(faces: readonly RoofFace[]): Vec3[] {
  const out: Vec3[] = [];
  for (const v of faces.flatMap((f) => f.boundary)) {
    if (v.z > 1e-9 && !out.some((w) => Math.hypot(w.x - v.x, w.y - v.y, w.z - v.z) < 1e-6)) out.push(v);
  }
  return out;
}

function expectNodes(actual: readonly Vec3[], expected: readonly Vec3[], tolerance: number) {
  expect(actual).toHaveLength(expected.length);
  for (const e of expected) {
    const best = Math.min(...actual.map((a) => Math.max(Math.abs(a.x - e.x), Math.abs(a.y - e.y), Math.abs(a.z - e.z))));
    expect(best, `Knoten ${JSON.stringify(e)}`).toBeLessThan(tolerance);
  }
}

describe("Walmdach der Probedatei 2", () => {
  // Knoten aus Archicad (IfcRoof „TOITURE“, Weltkoordinaten, auf 0,1 mm gerundet)
  const origin = { x: 10.6406, y: 13.2722 };
  const slope = tan(20);
  const thickness = 0.3 / Math.cos((20 * Math.PI) / 180);
  const ifcUnderside: Vec3[] = [
    { x: 13.6406, y: 16.2722, z: 4.8619 },
    { x: 13.6406, y: 16.7722, z: 4.8619 },
    { x: 14.6406, y: 15.2722, z: 4.4979 },
    { x: 18.6406, y: 15.2722, z: 4.4979 },
  ];
  const ifcEaves = [
    [9.8406, 12.4722], [21.4406, 12.4722], [21.4406, 18.0722], [17.4406, 18.0722], [17.4406, 20.5722], [9.8406, 20.5722],
  ] as const;

  it("trifft die Firstknoten der Dachunterseite auf der Bezugskontur", () => {
    const profiles = L_SHAPE.map(() => plane(20));
    const faces = weightedSkeleton(L_SHAPE, profiles);
    expectValid(L_SHAPE, profiles, faces);
    const h0 = 3.77;
    const nodes = ridgeNodes(faces).map((v) => ({ x: v.x + origin.x, y: v.y + origin.y, z: v.z + h0 }));
    expectNodes(nodes, ifcUnderside, MM);
  });

  it("baut alle 20 Knoten aus Traufkontur (Überstand 0,8 m) und Dicke nach", () => {
    const eaves = ifcEaves.map(([x, y]) => ({ x: x - origin.x, y: y - origin.y }));
    const profiles = eaves.map(() => plane(20));
    const faces = weightedSkeleton(eaves, profiles);
    expectValid(eaves, profiles, faces);
    const base = 3.77 - 0.8 * slope;
    const underside = [...eaves.map((v) => ({ ...v, z: 0 })), ...ridgeNodes(faces)].map((v) => ({ x: v.x + origin.x, y: v.y + origin.y, z: v.z + base }));
    const top = underside.map((v) => ({ ...v, z: v.z + thickness }));
    const ifcAll: Vec3[] = [
      ...ifcUnderside,
      ...ifcUnderside.map((v) => ({ ...v, z: v.z === 4.8619 ? 5.1812 : 4.8172 })),
      ...ifcEaves.flatMap(([x, y]) => [{ x, y, z: 3.4788 }, { x, y, z: 3.7981 }]),
    ];
    expectNodes([...underside, ...top], ifcAll, MM);
  });
});

describe("klassische Dachformen", () => {
  it("Satteldach: First über die ganze Länge, Giebel senkrecht", () => {
    const profiles = [plane(35), GABLE, plane(35), GABLE];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    const h = 4 * tan(35);
    expectNodes(ridgeNodes(faces), [{ x: 0, y: 4, z: h }, { x: 10, y: 4, z: h }], 1e-9);
    expect(signedArea(faces[1]!.boundary)).toBeCloseTo(0, 12);
  });

  it("Pultdach: eine Fläche bis zur hohen Wand", () => {
    const profiles = [plane(15), GABLE, GABLE, GABLE];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    expect(signedArea(faces[0]!.boundary)).toBeCloseTo(80, 9);
    expectNodes(ridgeNodes(faces), [{ x: 0, y: 8, z: 8 * tan(15) }, { x: 10, y: 8, z: 8 * tan(15) }], 1e-9);
  });

  it("Walmdach mit steileren Walmen", () => {
    const profiles = [plane(30), plane(45), plane(30), plane(45)];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    const h = 4 * tan(30);
    const inset = h / tan(45);
    expectNodes(ridgeNodes(faces), [{ x: inset, y: 4, z: h }, { x: 10 - inset, y: 4, z: h }], 1e-9);
  });

  it("Krüppelwalm: Giebel bis 2 m, darüber Walm", () => {
    const halfHip: EdgeProfile = [{ slope: Infinity, untilHeight: 2 }, { slope: tan(50), untilHeight: Infinity }];
    const profiles = [plane(40), halfHip, plane(40), halfHip];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    const h = 4 * tan(40);
    const inset = (h - 2) / tan(50);
    const atBreak = 2 / tan(40);
    expectNodes(
      ridgeNodes(faces),
      [
        { x: 0, y: atBreak, z: 2 }, { x: 0, y: 8 - atBreak, z: 2 }, { x: 10, y: atBreak, z: 2 }, { x: 10, y: 8 - atBreak, z: 2 },
        { x: inset, y: 4, z: h }, { x: 10 - inset, y: 4, z: h },
      ],
      1e-9,
    );
  });

  it("Mansardwalmdach: Knick bei 2,2 m", () => {
    const mansard: EdgeProfile = [{ slope: tan(70), untilHeight: 2.2 }, { slope: tan(30), untilHeight: Infinity }];
    const profiles = RECT.map(() => mansard);
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    const step = 2.2 / tan(70);
    const h = 2.2 + (4 - step) * tan(30);
    const nodes = ridgeNodes(faces);
    expect(nodes.filter((v) => Math.abs(v.z - 2.2) < 1e-9)).toHaveLength(4);
    expectNodes(nodes.filter((v) => v.z > 2.3), [{ x: 4, y: 4, z: h }, { x: 6, y: 4, z: h }], 1e-9);
  });

  const forms: Record<string, (polygon: readonly Vec[], name: string) => EdgeProfile[]> = {
    Walm: (p) => p.map(() => plane(35)),
    Sattel: (p, name) => p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? GABLE : plane(35))),
    Krüppelwalm: (p, name) =>
      p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? [{ slope: Infinity, untilHeight: 1.5 }, { slope: tan(55), untilHeight: Infinity }] : plane(35))),
    Mansarde: (p) => p.map(() => [{ slope: tan(72), untilHeight: 2.2 }, { slope: tan(25), untilHeight: Infinity }]),
    Mansardsattel: (p, name) =>
      p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? GABLE : [{ slope: tan(72), untilHeight: 2.2 }, { slope: tan(25), untilHeight: Infinity }])),
  };
  const cases = Object.keys(forms).flatMap((form) => Object.keys(SHAPES).map((shape) => [form, shape] as const));

  it.each(cases)("%s auf %s: Flächen auf ihrem Profil, Grundriss vollständig", (form, shape) => {
    const polygon = SHAPES[shape]!;
    const profiles = forms[form]!(polygon, shape);
    expectValid(polygon, profiles, weightedSkeleton(polygon, profiles));
  });
});

describe("Zufallsgrundrisse", () => {
  // Vereinigung aus bis zu vier Rechtecken im 0,5-m-Raster, geschert; HM0 lief damit 20 000 Fälle (Kapitel 10)
  const rect = fc.record({ x: fc.integer({ min: 0, max: 14 }), y: fc.integer({ min: 0, max: 14 }), w: fc.integer({ min: 3, max: 10 }), h: fc.integer({ min: 3, max: 10 }) });
  const outline = (rects: { x: number; y: number; w: number; h: number }[], skew: number): Vec[] | null => {
    const half = (v: number) => toUnits(v / 2);
    let union;
    try {
      union = unionPolygons(rects.map(({ x, y, w, h }) => [{ x: half(x), y: half(y) }, { x: half(x + w), y: half(y) }, { x: half(x + w), y: half(y + h) }, { x: half(x), y: half(y + h) }]));
    } catch {
      return null; // getrennte Teile oder Löcher
    }
    const sheared = union.map((p) => ({ x: toMetres(p.x) + (toMetres(p.y) * skew) / 10, y: toMetres(p.y) }));
    return sheared.filter((p, i) => {
      const a = sheared[(i - 1 + sheared.length) % sheared.length]!;
      const b = sheared[(i + 1) % sheared.length]!;
      return Math.abs((p.x - a.x) * (b.y - p.y) - (p.y - a.y) * (b.x - p.x)) > 1e-12;
    });
  };

  it("halten die Invarianten bei verschiedenen Neigungen und Knicken", () => {
    fc.assert(
      fc.property(
        fc.array(rect, { minLength: 1, maxLength: 4 }),
        fc.array(fc.integer({ min: 15, max: 60 }), { minLength: 40, maxLength: 40 }),
        fc.integer({ min: 0, max: 2 }),
        fc.integer({ min: -3, max: 3 }),
        (rects, slopes, mode, skew) => {
          const polygon = outline(rects, skew);
          if (!polygon) return;
          const s = (i: number) => slopes[i % slopes.length]!;
          const profiles: EdgeProfile[] = polygon.map((_, i) =>
            mode === 0 ? plane(35)
            : mode === 1 ? plane(s(i))
            : [{ slope: tan(70), untilHeight: 1 + (s(i) % 3) * 0.1 }, { slope: tan(s(i)), untilHeight: Infinity }],
          );
          expectValid(polygon, profiles, weightedSkeleton(polygon, profiles));
        },
      ),
      { numRuns: 300 },
    );
  });
});
