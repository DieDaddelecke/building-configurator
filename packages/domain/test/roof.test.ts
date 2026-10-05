// Dach: gewichtetes Skelett mit Teilflächen und Dachformen (docs/PLAN_HAUSMODELL.md Ergänzung 11, Kapitel 10).
// Invarianten: jede Teilfläche liegt auf ihrem Profilabschnitt, die Grundrisse der Flächen decken die Kontur genau ab.
// Vergleich mit dem Archicad-Walmdach der Probedatei 2 (Spike HM0).
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { unionPolygons } from "../src/geometry/offset.ts";
import { toMetres, toUnits } from "../src/geometry/polygon.ts";
import { buildRoof, edgeKinds, RoofError, type RoofDesign, type RoofForm, type RoofInput } from "../src/roof/build.ts";
import { signedArea, sloped, vertical, weightedSkeleton, type EdgeProfile, type SkeletonFace, type Vec, type Vec3 } from "../src/roof/skeleton.ts";

const MM = 0.001;
const tan = (deg: number) => Math.tan((deg * Math.PI) / 180);
const cos = (deg: number) => Math.cos((deg * Math.PI) / 180);

const RECT: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }];
// Bezugskontur der Probedatei 2 (Innenseite der Platzhalter-Wände, Ursprung bei 10,6406 / 13,2722)
const L_SHAPE: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 }, { x: 6, y: 4 }, { x: 6, y: 6.5 }, { x: 0, y: 6.5 }];
const T_SHAPE: Vec[] = [{ x: 4, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 4 }, { x: 12, y: 4 }, { x: 12, y: 8 }, { x: 0, y: 8 }, { x: 0, y: 4 }, { x: 4, y: 4 }];
const U_SHAPE: Vec[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 7, y: 8 }, { x: 7, y: 3 }, { x: 3, y: 3 }, { x: 3, y: 8 }, { x: 0, y: 8 }];
const SHAPES: Record<string, Vec[]> = { RECT, L: L_SHAPE, T: T_SHAPE, U: U_SHAPE };
/** Giebel an den Enden der Flügel. */
const GABLE_ENDS: Record<string, readonly number[]> = { RECT: [1, 3], L: [1, 4], T: [0, 3, 5], U: [2, 6] };

const units = (polygon: readonly Vec[]) => polygon.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
const distance3 = (a: Vec3, b: Vec3) => Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2);

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

function expectValid(polygon: readonly Vec[], profiles: readonly EdgeProfile[], faces: readonly SkeletonFace[]) {
  for (let i = 0; i < polygon.length; i++) expect(faces.some((f) => f.edge === i), `Kante ${i}`).toBe(true);
  let covered = 0;
  for (const face of faces) {
    const p = polygon[face.edge]!;
    const q = polygon[(face.edge + 1) % polygon.length]!;
    const length = Math.sqrt((q.x - p.x) ** 2 + (q.y - p.y) ** 2);
    const n = { x: -(q.y - p.y) / length, y: (q.x - p.x) / length };
    const profile = profiles[face.edge]!;
    const from = face.segment === 0 ? 0 : profile[face.segment - 1]!.untilHeight;
    const until = profile[face.segment]!.untilHeight;
    for (const loop of face.loops) {
      for (const v of loop) {
        const distance = n.x * (v.x - p.x) + n.y * (v.y - p.y);
        expect(Math.abs(distance - offsetOf(profile, v.z)), `Kante ${face.edge}/${face.segment}`).toBeLessThan(1e-6);
        expect(v.z).toBeGreaterThan(from - 1e-6);
        expect(v.z).toBeLessThan(until + 1e-6);
      }
      covered += Math.abs(signedArea(loop));
    }
  }
  expect(covered).toBeCloseTo(signedArea(polygon), 9);
}

/** Knoten oberhalb der Kontur, ohne Doppelte. */
function ridgeNodes(faces: readonly SkeletonFace[]): Vec3[] {
  const out: Vec3[] = [];
  for (const v of faces.flatMap((f) => f.loops.flat())) {
    if (v.z > 1e-9 && !out.some((w) => distance3(v, w) < 1e-6)) out.push(v);
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

const design = (form: RoofForm, extra: Partial<RoofDesign> = {}): RoofDesign => ({
  form,
  pitchDeg: form === "mansard" || form === "mansard_gable" ? 70 : 35,
  upperPitchDeg: form === "half_hip" ? 55 : form === "mansard" || form === "mansard_gable" ? 25 : null,
  breakHeight: form === "half_hip" ? 1.5 : form === "mansard" || form === "mansard_gable" ? 2.2 : null,
  rotation: 0,
  ...extra,
});

const input = (contour: readonly Vec[], d: RoofDesign, extra: Partial<RoofInput> = {}): RoofInput => ({
  contour: units(contour),
  bearing: 3,
  wallThickness: 0.4,
  eaveOverhang: 0.5,
  vergeOverhang: 0.3,
  design: d,
  thickness: 0.3,
  ...extra,
});

describe("Skelett: Walmdach der Probedatei 2", () => {
  // Knoten aus Archicad (IfcRoof „TOITURE“, Weltkoordinaten, auf 0,1 mm gerundet)
  const origin = { x: 10.6406, y: 13.2722 };
  const ifcUnderside: Vec3[] = [
    { x: 13.6406, y: 16.2722, z: 4.8619 },
    { x: 13.6406, y: 16.7722, z: 4.8619 },
    { x: 14.6406, y: 15.2722, z: 4.4979 },
    { x: 18.6406, y: 15.2722, z: 4.4979 },
  ];
  const ifcEaves = [
    [9.8406, 12.4722], [21.4406, 12.4722], [21.4406, 18.0722], [17.4406, 18.0722], [17.4406, 20.5722], [9.8406, 20.5722],
  ] as const;
  const ifcAll: Vec3[] = [
    ...ifcUnderside,
    ...ifcUnderside.map((v) => ({ ...v, z: v.z === 4.8619 ? 5.1812 : 4.8172 })),
    ...ifcEaves.flatMap(([x, y]) => [{ x, y, z: 3.4788 }, { x, y, z: 3.7981 }]),
  ];

  it("trifft die Firstknoten der Dachunterseite auf der Bezugskontur", () => {
    const profiles = L_SHAPE.map(() => [sloped(20)]);
    const faces = weightedSkeleton(L_SHAPE, profiles);
    expectValid(L_SHAPE, profiles, faces);
    const nodes = ridgeNodes(faces).map((v) => ({ x: v.x + origin.x, y: v.y + origin.y, z: v.z + 3.77 }));
    expectNodes(nodes, ifcUnderside, MM);
  });

  it("baut alle 20 Knoten aus Traufkontur (Überstand 0,8 m) und Dicke nach", () => {
    const eaves = ifcEaves.map(([x, y]) => ({ x: x - origin.x, y: y - origin.y }));
    const profiles = eaves.map(() => [sloped(20)]);
    const faces = weightedSkeleton(eaves, profiles);
    expectValid(eaves, profiles, faces);
    const base = 3.77 - 0.8 * tan(20);
    const thickness = 0.3 / cos(20);
    const underside = [...eaves.map((v) => ({ ...v, z: 0 })), ...ridgeNodes(faces)].map((v) => ({ x: v.x + origin.x, y: v.y + origin.y, z: v.z + base }));
    expectNodes([...underside, ...underside.map((v) => ({ ...v, z: v.z + thickness }))], ifcAll, MM);
  });

  it("buildRoof erzeugt dasselbe Dach aus Form und Parametern", () => {
    const roof = buildRoof(input(L_SHAPE, design("hip", { pitchDeg: 20 }), { bearing: 3.77, wallThickness: 0.3, eaveOverhang: 0.5, vergeOverhang: 0.5 }));
    const lift = 0.3 / cos(20);
    const nodes: Vec3[] = [];
    for (const v of roof.faces.flatMap((f) => f.polygon)) {
      const w = { x: v.x + origin.x, y: v.y + origin.y, z: v.z };
      if (!nodes.some((u) => distance3(u, w) < 1e-6)) nodes.push(w);
    }
    expectNodes([...nodes, ...nodes.map((v) => ({ ...v, z: v.z + lift }))], ifcAll, MM);
    expect(roof.top).toBeCloseTo(5.1812, 3);
    expect(roof.eave).toBeCloseTo(3.7981, 3);
    expect(roof.ridgeAzimuthDeg).toBeCloseTo(90, 9);
  });
});

describe("Skelett: Teilflächen je Profilabschnitt", () => {
  it("Satteldach: First über die ganze Länge, Giebel senkrecht", () => {
    const profiles = [[sloped(35)], [vertical()], [sloped(35)], [vertical()]];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    const h = 4 * tan(35);
    expectNodes(ridgeNodes(faces), [{ x: 0, y: 4, z: h }, { x: 10, y: 4, z: h }], 1e-9);
  });

  it("Krüppelwalm: Giebel bis 2 m, darüber Walm; der Giebel hat zwei Teilflächen", () => {
    const halfHip: EdgeProfile = [vertical(2), sloped(50)];
    const profiles = [[sloped(40)], halfHip, [sloped(40)], halfHip];
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    expect(faces.filter((f) => f.edge === 1).map((f) => f.segment)).toEqual([0, 1]);
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

  it("Mansardwalmdach: Knick bei 2,2 m teilt jede Fläche", () => {
    const mansard: EdgeProfile = [sloped(70, 2.2), sloped(30)];
    const profiles = RECT.map(() => mansard);
    const faces = weightedSkeleton(RECT, profiles);
    expectValid(RECT, profiles, faces);
    expect(faces).toHaveLength(8);
    const step = 2.2 / tan(70);
    const h = 2.2 + (4 - step) * tan(30);
    const nodes = ridgeNodes(faces);
    expect(nodes.filter((v) => Math.abs(v.z - 2.2) < 1e-9)).toHaveLength(4);
    expectNodes(nodes.filter((v) => v.z > 2.3), [{ x: 4, y: 4, z: h }, { x: 6, y: 4, z: h }], 1e-9);
  });

  const forms: Record<string, (polygon: readonly Vec[], name: string) => EdgeProfile[]> = {
    Walm: (p) => p.map(() => [sloped(35)]),
    Sattel: (p, name) => p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? [vertical()] : [sloped(35)])),
    Krüppelwalm: (p, name) => p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? [vertical(1.5), sloped(55)] : [sloped(35)])),
    Mansarde: (p) => p.map(() => [sloped(72, 2.2), sloped(25)]),
    Mansardsattel: (p, name) => p.map((_, i) => (GABLE_ENDS[name]!.includes(i) ? [vertical()] : [sloped(72, 2.2), sloped(25)])),
  };
  const cases = Object.keys(forms).flatMap((form) => Object.keys(SHAPES).map((shape) => [form, shape] as const));

  it.each(cases)("%s auf %s: Flächen auf ihrem Profil, Grundriss vollständig", (form, shape) => {
    const polygon = SHAPES[shape]!;
    const profiles = forms[form]!(polygon, shape);
    expectValid(polygon, profiles, weightedSkeleton(polygon, profiles));
  });
});

describe("Skelett: Zufallsgrundrisse", () => {
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

  it("jede Dachform: gültiges Dach oder RoofError, nie ein anderer Fehler", () => {
    const forms: RoofForm[] = ["mono_pitch", "gable", "hip", "half_hip", "mansard", "mansard_gable"];
    fc.assert(
      fc.property(
        fc.array(rect, { minLength: 1, maxLength: 4 }),
        fc.constantFrom(...forms),
        fc.constantFrom(0, 90, 180, 270),
        fc.integer({ min: -3, max: 3 }),
        (rects, form, rotation, skew) => {
          const polygon = outline(rects, skew);
          if (!polygon) return;
          let roof;
          try {
            roof = buildRoof(input(polygon, design(form, { rotation: rotation as RoofDesign["rotation"] })));
          } catch (error) {
            expect(error).toBeInstanceOf(RoofError);
            return;
          }
          expect(roof.faces.reduce((s, f) => s + f.planArea, 0)).toBeCloseTo(signedArea(roof.outline), 6);
          expect(roof.top).toBeGreaterThan(roof.eave);
        },
      ),
      { numRuns: 300 },
    );
  });

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
            mode === 0 ? [sloped(35)]
            : mode === 1 ? [sloped(s(i))]
            : [sloped(70, 1 + (s(i) % 3) * 0.1), sloped(s(i))],
          );
          expectValid(polygon, profiles, weightedSkeleton(polygon, profiles));
        },
      ),
      { numRuns: 300 },
    );
  });
});

describe("Dachformen", () => {
  const ALL: RoofForm[] = ["mono_pitch", "gable", "hip", "half_hip", "mansard", "mansard_gable"];
  const kindsOf = (shape: Vec[], d: RoofDesign) => edgeKinds(shape, d).flatMap((k, i) => (k === "gable" ? [i] : []));

  it.each(Object.keys(SHAPES))("Giebel an den Flügelenden von %s, First längs der längeren Seite", (shape) => {
    expect(kindsOf(SHAPES[shape]!, design("gable"))).toEqual(GABLE_ENDS[shape]);
  });

  it("Drehung um 90°: Giebel an den langen Seiten; beim L stießen zwei Giebel aneinander", () => {
    expect(kindsOf(RECT, design("gable", { rotation: 90 }))).toEqual([0, 2]);
    expect(kindsOf(RECT, design("gable", { rotation: 180 }))).toEqual([1, 3]);
    expect(() => edgeKinds(L_SHAPE, design("gable", { rotation: 90 }))).toThrow(RoofError);
  });

  it("quadratischer Grundriss: Giebel quer zur x-Achse, gedreht quer zur y-Achse", () => {
    const square = [{ x: 0, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 8 }, { x: 0, y: 8 }];
    expect(kindsOf(square, design("gable"))).toEqual([1, 3]);
    expect(kindsOf(square, design("gable", { rotation: 270 }))).toEqual([0, 2]);
  });

  it("Pultdach: Traufe an der längsten Kante, Drehung gegen den Uhrzeigersinn", () => {
    const eaveOf = (rotation: RoofDesign["rotation"]) => edgeKinds(RECT, design("mono_pitch", { rotation })).indexOf("eave");
    expect([0, 90, 180, 270].map((r) => eaveOf(r as RoofDesign["rotation"]))).toEqual([0, 1, 2, 3]);
    const roof = buildRoof(input(RECT, design("mono_pitch", { pitchDeg: 15 })));
    expect(roof.faces).toHaveLength(1);
    const count = (kind: string) => roof.lines.filter((l) => l.kind === kind).length;
    expect([count("eave"), count("ridge"), count("verge"), count("hip"), count("valley")]).toEqual([1, 1, 2, 0, 0]);
    // Oberkante am hohen Rand: Traufkontur 0,9 m vor der Bezugskontur, hohe Seite 0,7 m dahinter
    const h0 = 3 - 0.9 * tan(15);
    expect(roof.top).toBeCloseTo(h0 + (8 + 0.9 + 0.7) * tan(15) + 0.3 / cos(15), 9);
    expect(roof.eave).toBeCloseTo(h0 + 0.3 / cos(15), 9);
    expect(roof.ridgeAzimuthDeg).toBeCloseTo(90, 9);
  });

  it("Satteldach: Linien, Flächen und Giebel", () => {
    const roof = buildRoof(input(RECT, design("gable")));
    const length = (kind: string) => roof.lines.filter((l) => l.kind === kind).reduce((s, l) => s + l.length, 0);
    expect(length("ridge")).toBeCloseTo(10 + 2 * 0.7, 9);
    expect(length("eave")).toBeCloseTo(2 * (10 + 2 * 0.7), 9);
    const run = 4 + 0.9;
    expect(length("verge")).toBeCloseTo((4 * run) / cos(35), 9);
    expect(length("hip") + length("valley")).toBe(0);
    expect(roof.faces.reduce((s, f) => s + f.area, 0)).toBeCloseTo((2 * run * (10 + 1.4)) / cos(35), 9);
    // Zwei Giebeldreiecke über dem Auflager, Breite der Bezugskontur
    expect(roof.gableArea).toBeCloseTo(2 * 4 * 4 * tan(35), 9);
    // Unterseite über der Giebelwand auf der Bezugskontur: Auflager plus Dreieck
    expect(roof.undersideIntegral({ x: 0, y: 0 }, { x: 0, y: 8 })).toBeCloseTo(8 * 3 + 16 * tan(35), 9);
    expect(roof.undersideIntegral({ x: -5, y: 0 }, { x: -5, y: 8 })).toBeNull();
  });

  it("Walmdach auf dem Rechteck: ein First, vier Grate", () => {
    const roof = buildRoof(input(RECT, design("hip")));
    const count = (kind: string) => roof.lines.filter((l) => l.kind === kind).length;
    expect([count("ridge"), count("hip"), count("eave"), count("verge"), count("valley")]).toEqual([1, 4, 4, 0, 0]);
    expect(roof.gableArea).toBe(0);
  });

  it("Mansarde: Knicklinien rundum, Grate unten und oben", () => {
    const roof = buildRoof(input(RECT, design("mansard")));
    const count = (kind: string) => roof.lines.filter((l) => l.kind === kind).length;
    expect([count("break"), count("hip"), count("ridge"), count("eave")]).toEqual([4, 8, 1, 4]);
    const breaks = roof.lines.filter((l) => l.kind === "break");
    for (const l of breaks) expect(l.a.z).toBeCloseTo(3 + 2.2, 9);
  });

  it("Krüppelwalm: kleine Traufe am Walm auf der Ortganglinie", () => {
    const roof = buildRoof(input(RECT, design("half_hip")));
    const eaves = roof.lines.filter((l) => l.kind === "eave");
    expect(eaves).toHaveLength(4);
    const kink = 3 + 1.5 - 0.7 * tan(55);
    expect(eaves.filter((l) => Math.abs(l.a.z - kink) < 1e-9)).toHaveLength(2);
    // Krüppelhöhe 0,1 m: der Walm begänne auf der Ortganglinie unter der Traufe
    expect(() => buildRoof(input(RECT, design("half_hip", { breakHeight: 0.1 })))).toThrow(RoofError);
    // Krüppelhöhe über dem First (2,8 m über dem Auflager, auf der Ortganglinie 1 m tiefer): kein Walm
    expect(() => buildRoof(input(RECT, design("half_hip", { breakHeight: 4 })))).toThrow(RoofError);
  });

  it("unvollständiger Entwurf und zu schmaler Rücksprung", () => {
    expect(() => buildRoof(input(RECT, design("gable", { pitchDeg: null })))).toThrow(RoofError);
    // Rücksprung 0,4 m breit: die Traufkontur überschneidet sich
    const notch = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 5.2, y: 8 }, { x: 5.2, y: 6 }, { x: 4.8, y: 6 }, { x: 4.8, y: 8 }, { x: 0, y: 8 }];
    expect(() => buildRoof(input(notch, design("hip")))).toThrow(RoofError);
  });

  const cases = ALL.flatMap((form) => Object.keys(SHAPES).map((shape) => [form, shape] as const));
  it.each(cases)("%s auf %s: Flächen eben, Traufkontur ganz bedeckt, jede innere Linie einmal", (form, shape) => {
    const roof = buildRoof(input(SHAPES[shape]!, design(form)));
    const outlineArea = signedArea(roof.outline);
    expect(roof.faces.reduce((s, f) => s + f.planArea, 0)).toBeCloseTo(outlineArea, 6);
    for (const face of roof.faces) {
      expect(face.planArea).toBeGreaterThan(0);
      expect(face.area).toBeGreaterThanOrEqual(face.planArea);
    }
    // Traufe und Ortgang zusammen umlaufen die Traufkontur
    let perimeter = 0;
    roof.outline.forEach((p, i) => {
      const q = roof.outline[(i + 1) % roof.outline.length]!;
      perimeter += Math.sqrt((q.x - p.x) ** 2 + (q.y - p.y) ** 2);
    });
    const onOutline = roof.lines.filter((l) => l.kind === "eave" || l.kind === "verge" || (form === "mono_pitch" && l.kind === "ridge"));
    const planLength = (l: { a: Vec3; b: Vec3 }) => Math.sqrt((l.b.x - l.a.x) ** 2 + (l.b.y - l.a.y) ** 2);
    expect(onOutline.reduce((s, l) => s + planLength(l), 0)).toBeCloseTo(perimeter, 6);
    expect(roof.top).toBeGreaterThan(roof.eave);
  });
});
