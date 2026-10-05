// Zweigeschossiges Demohaus (R+1, Ergänzung 5, E-HM-63) mit Satteldach 35° (Ergänzung 11). Erwartungswerte von
// Hand: Bezugskontur 10 × 8 m in beiden Geschossen, Putzprofil 0,36 m (Beton 0,20 + Dämmung 0,16), Obergeschoss auf
// 2,80 m mit Decke 0,22 m, Auflager 5,80 m auf der Bezugskontur, Traufüberstand 0,50 m, Ortgang 0,30 m, Ziegeldach
// 0,28 m. Der First liegt längs der längeren Seite (x): Traufen im Süden und Norden, Giebel im Westen und Osten.
import { describe, expect, it } from "vitest";
import { checkCompatibility, deriveModel, evaluate, toUnits, type HouseEvaluation, type HouseTemplate } from "../src/index.ts";
import { catalog, configuration, templateR1 as template } from "./demo-house.ts";

type Selections = NonNullable<Parameters<typeof configuration>[0]>;

const tan = (deg: number) => Math.tan((deg * Math.PI) / 180);
const cos = (deg: number) => Math.cos((deg * Math.PI) / 180);

function run(selections: Selections = {}, house: HouseTemplate = template) {
  return evaluate({ template: house, catalog, configuration: configuration(selections) });
}

function quantity(evaluation: HouseEvaluation, key: string, ref: string | null = null): number {
  const found = evaluation.quantities.filter((q) => q.key === key && q.ref_id === ref);
  expect(found, `${key}:${ref}`).toHaveLength(1);
  return found[0]!.value;
}

/** Decken über den Öffnungen in m über dem Fußboden ihres Geschosses. */
function ceilings(selections: Selections = {}): Record<string, number> {
  const model = deriveModel({ template, catalog, configuration: configuration(selections) });
  return Object.fromEntries(model.openings.map((o) => [o.id, o.ceiling / 10_000]));
}

const BEARING = 5.8;
const LIFT = 0.28 / cos(35);
const base = run();
const R1_EAVE_WINDOWS = ["win-r1-bed1", "win-r1-bed2", "win-r1-bath", "win-r1-bed3"];

describe("R+1 mit Satteldach", () => {
  it("ist mit dem Katalog verträglich und ohne Befund", () => {
    expect(checkCompatibility({ template, catalog })).toEqual({ domain_version: base.domain_version, supported: true, issues: [] });
    expect(base.status).toBe("valid");
    expect(base.rule_results).toEqual([]);
    expect(base.notes).toEqual([]);
  });

  it("Hausbeschreibung: Geschosse, Dachform, Höhen, Umrisse", () => {
    expect(base.facts).toMatchObject({ storeys: 2, roof_shape: "gable", roof_slopes_deg: [35, 35], ridge_azimuth_deg: 90 });
    // Traufe: Unterseite am Rand des Überstands (0,36 + 0,50 m vor der Bezugskontur) plus lotrechter Aufbau
    expect(base.facts.eave_height).toBeCloseTo(BEARING - 0.86 * tan(35) + LIFT, 9);
    expect(base.facts.top_height).toBeCloseTo(BEARING + 4 * tan(35) + LIFT, 9);
    const xs = (points: readonly { x: number }[]) => [Math.min(...points.map((p) => p.x)), Math.max(...points.map((p) => p.x))];
    const ys = (points: readonly { y: number }[]) => [Math.min(...points.map((p) => p.y)), Math.max(...points.map((p) => p.y))];
    expect(xs(base.facts.facade_outline)).toEqual([-0.36, 10.36]);
    expect(ys(base.facts.facade_outline)).toEqual([-0.36, 8.36]);
    // Projektion: Ortgang 0,30 m an den Giebeln, Traufe 0,50 m an den Längsseiten
    expect(xs(base.facts.projection_outline)).toEqual([-0.66, 10.66]);
    expect(ys(base.facts.projection_outline)).toEqual([-0.86, 8.86]);
  });

  it("Dachmengen je Fläche und Linie", () => {
    // Zwei Flächen, je 11,32 m lang (10 + 2 × 0,66) und im Grundriss 4,86 m tief (4 + 0,36 + 0,50)
    expect(quantity(base, "roof.area", "roof.tiles")).toBeCloseTo((2 * 11.32 * 4.86) / cos(35), 9);
    expect(quantity(base, "roof.ridge.length", "roof.tiles")).toBeCloseTo(11.32, 9);
    expect(quantity(base, "roof.eave.length", "roof.tiles")).toBeCloseTo(2 * 11.32, 9);
    expect(quantity(base, "roof.verge.length", "roof.tiles")).toBeCloseTo((4 * 4.86) / cos(35), 9);
    // Giebeldreiecke über dem Auflager auf der Bezugskontur: 2 × ½ × 8 × 4 tan 35°
    expect(quantity(base, "gable.area")).toBeCloseTo(32 * tan(35), 9);
    expect(quantity(base, "footprint.area")).toBeCloseTo(10.72 * 8.72, 9);
    expect(base.quantities.some((q) => q.key === "roof.hip.length" || q.key === "roof.valley.length")).toBe(false);
  });

  it("Wandflächen über beide Geschosse bis unter das Dach", () => {
    // Je Schicht auf ihrer Mittellinie (Abstand d): Erdgeschoss −0,20…2,80 m, Obergeschoss ab 2,80 m bis zur
    // Unterseite des Dachs. Traufseiten: 3,00 − d tan 35°; Giebelseiten: 3,00 + |y| tan 35° bis zum First, y ab −d.
    const layer = (d: number) => {
      const long = 10 + 2 * d;
      const short = 8 + 2 * d;
      const ground = 2 * (long + short) * 3;
      const eaves = 2 * long * (3 - d * tan(35));
      const gables = 2 * (short * 3 + tan(35) * (16 - d * d));
      return ground + eaves + gables - 19.38;
    };
    expect(quantity(base, "opening.area")).toBeCloseTo(9 * 1.2 * 1.6 + 1 * 2.1, 9);
    expect(quantity(base, "wall.layer.area", "layer.concrete_20")).toBeCloseTo(layer(0.1), 9);
    expect(quantity(base, "wall.layer.area", "layer.insulation_16")).toBeCloseTo(layer(0.28), 9);
  });

  it("Fassadenflächen je Himmelsrichtung auf der Außenkante", () => {
    const share = (direction: string) => base.energy.window_shares.find((s) => s.direction === direction)!;
    expect(share("n").facade_area).toBeCloseTo(10.72 * (6 - 0.36 * tan(35)), 9);
    expect(share("e").facade_area).toBeCloseTo(8.72 * 6 + tan(35) * (16 - 0.36 * 0.36), 9);
    expect(share("n").window_area).toBeCloseTo(4 * 1.92, 9);
    expect(share("w").window_area).toBeCloseTo(2 * 1.92, 9);
  });

  it("Decken: Geschossdecke unten, oben die tiefste Unterseite innen und außen an der Wand", () => {
    const c = ceilings();
    expect(c["win-rdc-living-south"]).toBeCloseTo(2.8 - 0.22, 9);
    expect(c["door-entrance"]).toBeCloseTo(2.58, 9);
    // Traufseite: außen an der Fassade liegt das Dach um 0,36 tan 35° tiefer als auf der Bezugskontur
    for (const id of R1_EAVE_WINDOWS) expect(c[id]).toBeCloseTo(3 - 0.36 * tan(35), 9);
    // Giebelfenster bei y 5,65…6,85 unter der Nordfläche: tiefster Punkt bei y = 6,85
    expect(c["win-r1-bed3-gable"]).toBeCloseTo(3 + (8 - 6.85) * tan(35), 9);
    // Innenwand: Unterseite über der Wandachse, nicht tiefer als am Auflager
    expect(c["door-r1-bed1"]).toBeGreaterThan(3);
  });

  it("Neigung 45° mit Ziegelfassade (0,48 m) passt noch unter das Dach", () => {
    const steep = { roof_pitch: { value: 45 }, wall_profile: { value: "wall.brick" } };
    expect(run(steep).status).toBe("valid");
    for (const id of R1_EAVE_WINDOWS) expect(ceilings(steep)[id]).toBeCloseTo(3 - 0.48, 9);
  });

  it("Mansarde: das steile Dach läge außen unter den Stürzen des Obergeschosses", () => {
    const mansard = run({ roof_shape: { value: "shape.mansard" } });
    expect(mansard.status).toBe("blocked");
    expect(mansard.rule_results.map((r) => [r.code, r.element_ids])).toEqual(
      [...R1_EAVE_WINDOWS, "win-r1-bed3-gable"].map((id) => ["opening_above_ceiling", [id]]),
    );
    const c = ceilings({ roof_shape: { value: "shape.mansard" } });
    for (const id of R1_EAVE_WINDOWS) expect(c[id]).toBeCloseTo(3 - 0.36 * tan(70), 9);
  });
});

describe("Geschosse", () => {
  const r1 = template.envelope[1]!;
  const issues = (change: Partial<HouseTemplate>) => checkCompatibility({ template: { ...template, ...change }, catalog }).issues.map((i) => i.code);

  it("verschiedene Bezugskonturen", () => {
    const shifted = { ...r1, inner_polygon: r1.inner_polygon.map((p) => ({ x: p.x === 10 ? 10.01 : p.x, y: p.y })) };
    expect(issues({ envelope: [template.envelope[0]!, shifted] })).toEqual(["storey_outlines_differ"]);
    // Bis 1 mm gilt die Kontur als gleich
    const close = { ...r1, inner_polygon: r1.inner_polygon.map((p) => ({ x: p.x === 10 ? 10.0009 : p.x, y: p.y })) };
    expect(issues({ envelope: [template.envelope[0]!, close] })).toEqual([]);
  });

  it("Geschoss ohne Hülle und fehlende Geschossdecke", () => {
    expect(issues({ envelope: [template.envelope[0]!], openings: template.openings.filter((o) => !o.host_id.startsWith("seg-r1")) })).toEqual([
      "storey_envelope_mismatch",
    ]);
    expect(issues({ slabs: template.slabs.filter((s) => s.kind !== "floor") })).toEqual(["floor_slab_missing"]);
  });

  it("Fassade des Geschosses mit der dicksten Wand umschließt die anderen", () => {
    // Ziegel nur im Obergeschoss ist kein gemischtes Profil: Profile gelten je Geschoss
    const perElement = { ...catalog, slots: catalog.slots.map((s) => (s.id === "wall_profile" ? { ...s, granularity: "per_element" as const } : s)) };
    const segments = r1.segments.map((s) => s.id);
    const config = configuration({ wall_profile: { elements: Object.fromEntries(segments.map((id) => [id, "wall.brick"])) } });
    const model = deriveModel({ template, catalog: perElement, configuration: config });
    expect(model.facadeLoop).toBe(1);
    expect(model.loops.map((loop) => loop.wallThickness)).toEqual([toUnits(0.36), toUnits(0.48)]);
    // Das Obergeschoss braucht wegen des Profilwechsels ein eigenes Auflager
    expect(model.loops.map((loop) => loop.bearingLength !== null)).toEqual([false, true]);
  });
});
