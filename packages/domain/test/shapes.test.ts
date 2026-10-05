// Dachformen als Slots (Ergänzung 4 und 11): Form, Neigung und Drehung, das wirksame Dach aus Template und
// Katalogform, der Dachaufbau passend zur Form und die Rücknahme einer Wahl, mit der das Dach nicht entsteht
// (E-HM-60). Höhen und Mengen von Hand auf dem R+1 (Bezugskontur 10 × 8 m, Wand 0,36 m, Auflager 5,80 m,
// Überstände des Templates 0,50/0,30 m, Ziegeldach 0,28 m).
import { describe, expect, it } from "vitest";
import {
  checkCompatibility,
  deriveModel,
  evaluate,
  ModelError,
  roofPitchRange,
  type HouseCatalog,
  type HouseEvaluation,
  type HouseOpening,
  type HouseTemplate,
} from "../src/index.ts";
import { catalog, configuration, template as flatHouse, templateR1 } from "./demo-house.ts";

type Selections = NonNullable<Parameters<typeof configuration>[0]>;

const tan = (deg: number) => Math.tan((deg * Math.PI) / 180);
const cos = (deg: number) => Math.cos((deg * Math.PI) / 180);
const lift = (deg: number) => 0.28 / cos(deg);

function run(house: HouseTemplate, selections: Selections = {}, options: { catalog?: HouseCatalog; candidates?: string } = {}) {
  return evaluate({
    template: house,
    catalog: options.catalog ?? catalog,
    configuration: configuration(selections),
    candidates: options.candidates ? { slot_id: options.candidates, element_id: null } : null,
  });
}

function quantity(evaluation: HouseEvaluation, key: string, ref: string | null = null): number {
  const found = evaluation.quantities.filter((q) => q.key === key && q.ref_id === ref);
  expect(found, `${key}:${ref}`).toHaveLength(1);
  return found[0]!.value;
}

const shape = (id: string, rotation?: number): Selections => ({
  roof_shape: { value: id },
  ...(rotation === undefined ? {} : { roof_rotation: { value: rotation } }),
});

// L-Grundriss der Probedatei 2 mit Flachdach; Auflager 3,40 m, damit die Fenster unter den üblichen Formen bleiben
const L = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 }, { x: 6, y: 4 }, { x: 6, y: 6.5 }, { x: 0, y: 6.5 }];
const ROLES = ["street", "side_right", "garden", "side_right", "garden", "side_left"] as const;
const opening = (id: string, kind: "door" | "window", offset: number): HouseOpening => ({
  id,
  source_ifc_guid: null,
  kind,
  host_kind: "envelope_segment",
  host_id: "seg-0",
  offset_along_host: offset,
  adjacent_room_ids: ["room-living"],
});
const lShape: HouseTemplate = {
  ...flatHouse,
  envelope: [{ level_id: "rdc", inner_polygon: L, segments: L.map((_, i) => ({ id: `seg-${i}`, source_ifc_guid: null, facade_role: ROLES[i]! })) }],
  interior_walls: [],
  rooms: [{ ...flatHouse.rooms[0]!, polygon: L }],
  openings: [opening("door-entrance", "door", 2), opening("win-south", "window", 7)],
  roof: { ...flatHouse.roof, bearing_height: 3.4 },
};

describe("Formen auf dem R+1", () => {
  // [Form, Drehung, Azimut des Firsts, Traufe, Oberkante, Status]
  const cases: [string, number, number | null, number, number, string][] = [
    ["flat", 0, null, 5.8 + 0.2 + 0.4, 5.8 + 0.2 + 0.4, "valid"],
    // Pultdach: Traufe im Süden, die Ebene steigt bis zum Ortgang im Norden (8 + 0,36 + 0,30 m)
    ["mono_pitch", 0, 90, 5.8 - 0.86 * tan(15) + lift(15), 5.8 + 8.66 * tan(15) + lift(15), "valid"],
    ["mono_pitch", 90, 0, 5.8 - 0.86 * tan(15) + lift(15), 5.8 + 10.66 * tan(15) + lift(15), "valid"],
    ["gable", 0, 90, 5.8 - 0.86 * tan(35) + lift(35), 5.8 + 4 * tan(35) + lift(35), "valid"],
    ["gable", 90, 0, 5.8 - 0.86 * tan(35) + lift(35), 5.8 + 5 * tan(35) + lift(35), "valid"],
    // Walm: Traufüberstand des Templates an allen Kanten; Drehen ändert nichts
    ["hip", 0, 90, 5.8 - 0.86 * tan(30) + lift(30), 5.8 + 4 * tan(30) + lift(30), "valid"],
    ["hip", 90, 90, 5.8 - 0.86 * tan(30) + lift(30), 5.8 + 4 * tan(30) + lift(30), "valid"],
    ["half_hip", 0, 90, 5.8 - 0.86 * tan(40) + lift(40), 5.8 + 4 * tan(40) + lift(40), "valid"],
    ["half_hip", 90, 0, 5.8 - 0.86 * tan(40) + lift(40), 5.8 + 5 * tan(40) + lift(40), "valid"],
    // Mansarde: 70° bis 2,20 m über dem Auflager (0,80 m tief), darüber 25°; die Fenster liegen außen unter dem Dach
    ["mansard", 0, 90, 5.8 - 0.86 * tan(70) + lift(70), 5.8 + 2.2 + (4 - 2.2 / tan(70)) * tan(25) + lift(25), "blocked"],
    ["mansard_gable", 90, 0, 5.8 - 0.86 * tan(70) + lift(70), 5.8 + 2.2 + (5 - 2.2 / tan(70)) * tan(25) + lift(25), "blocked"],
  ];

  it.each(cases)("%s, gedreht %i°", (form, rotation, azimuth, eave, top, status) => {
    const evaluation = run(templateR1, shape(`shape.${form}`, rotation));
    expect(evaluation.facts.roof_shape).toBe(form);
    expect(evaluation.facts.ridge_azimuth_deg).toBe(azimuth);
    expect(evaluation.facts.eave_height).toBeCloseTo(eave, 9);
    expect(evaluation.facts.top_height).toBeCloseTo(top, 9);
    expect(evaluation.status).toBe(status);
  });

  it("Neigungen je Dachfläche", () => {
    const slopes = (form: string) => run(templateR1, shape(`shape.${form}`)).facts.roof_slopes_deg;
    expect(slopes("flat")).toEqual([]);
    expect(slopes("mono_pitch")).toEqual([15]);
    expect(slopes("hip")).toEqual([30, 30, 30, 30]);
    expect([...slopes("half_hip")].sort()).toEqual([40, 40, 60, 60]);
    expect(new Set(slopes("mansard"))).toEqual(new Set([25, 70]));
  });

  it("Walmdach: Fläche, First, Grate, Traufe; kein Giebel", () => {
    const hip = run(templateR1, shape("shape.hip"));
    // Traufkontur 11,72 × 9,72 m; Grate über 4,86 m im Grundriss diagonal
    expect(quantity(hip, "roof.area", "roof.tiles")).toBeCloseTo((11.72 * 9.72) / cos(30), 9);
    expect(quantity(hip, "roof.ridge.length", "roof.tiles")).toBeCloseTo(2, 9);
    expect(quantity(hip, "roof.hip.length", "roof.tiles")).toBeCloseTo(4 * Math.sqrt(2 * 4.86 ** 2 + (4.86 * tan(30)) ** 2), 9);
    expect(quantity(hip, "roof.eave.length", "roof.tiles")).toBeCloseTo(2 * (11.72 + 9.72), 9);
    expect(hip.quantities.some((q) => q.key === "gable.area" || q.key === "roof.verge.length")).toBe(false);
  });

  it("Pultdach: Giebelwände auf der Bezugskontur, die hohe Seite ganz", () => {
    const mono = run(templateR1, shape("shape.mono_pitch"));
    expect(quantity(mono, "roof.area", "roof.tiles")).toBeCloseTo((11.32 * 9.52) / cos(15), 9);
    expect(quantity(mono, "roof.verge.length", "roof.tiles")).toBeCloseTo((2 * 9.52) / cos(15), 9);
    // Nordwand 10 × 8 tan 15°, die Seiten je ½ × 8 × 8 tan 15°
    expect(quantity(mono, "gable.area")).toBeCloseTo(144 * tan(15), 9);
  });

  it("Krüppelwalm und Mansardsattel: Giebelwand bis zur Unterseite auf der Bezugskontur", () => {
    // Krüppelwalm: Trapez bis zur Krüppelhöhe 2 m, die Traufebenen erreichen sie 2 / tan 40° von der Ecke
    expect(quantity(run(templateR1, shape("shape.half_hip")), "gable.area")).toBeCloseTo(2 * (16 - (2 * 2) / tan(40)), 6);
    // Mansardsattel: unten 70° bis 2,20 m, darüber 25° bis zum First in der Mitte
    const deep = 2.2 / tan(70);
    const side = 2 * ((deep * 2.2) / 2 + (4 - deep) * 2.2 + ((4 - deep) ** 2 * tan(25)) / 2);
    expect(quantity(run(templateR1, shape("shape.mansard_gable")), "gable.area")).toBeCloseTo(2 * side, 9);
  });

  it("Drehung gilt nur für Formen mit First oder Traufseite", () => {
    const hip = run(templateR1, shape("shape.hip", 90));
    expect(hip.resolved.some((r) => r.slot_id === "roof_rotation")).toBe(false);
    expect(hip.notes).toEqual([]);
    expect(hip.price.net_amount).toBeCloseTo(run(templateR1, shape("shape.hip")).price.net_amount, 9);
    for (const form of ["mono_pitch", "gable", "half_hip", "mansard_gable"]) {
      expect(run(templateR1, shape(`shape.${form}`, 90)).resolved.find((r) => r.slot_id === "roof_rotation")).toMatchObject({ number: 90, source: "global" });
    }
  });

  it("Kandidaten der Form: alle entstehen, die Mansarden sperren die Fenster", () => {
    const evaluation = run(templateR1, {}, { candidates: "roof_shape" });
    const status = Object.fromEntries(evaluation.candidates!.map((c) => [c.option_value_id, [c.available_count, c.status]]));
    expect(status).toEqual({
      "shape.flat": [1, "valid"],
      "shape.mono_pitch": [1, "valid"],
      "shape.gable": [1, "valid"],
      "shape.hip": [1, "valid"],
      "shape.half_hip": [1, "valid"],
      "shape.mansard": [1, "blocked"],
      "shape.mansard_gable": [1, "blocked"],
    });
    expect(evaluation.candidates!.find((c) => c.option_value_id === "shape.gable")!.price_delta).toBe(0);
  });

  it("Flachdach auf dem geneigten Template: Dachdecke und Attika der Form", () => {
    const flat = run(templateR1, shape("shape.flat"));
    expect(quantity(flat, "roof.area", "roof.flat")).toBeCloseTo(10.72 * 8.72, 9);
    const model = deriveModel({ template: templateR1, catalog, configuration: configuration(shape("shape.flat")) });
    expect(model.roof.flat).toMatchObject({ slabThickness: 2000, parapetTop: 64000 });
    expect(model.facadeHeight).toBe(2000 + 64000);
  });
});

describe("Neigung", () => {
  it("in der Spanne gilt sie, außerhalb gilt der Standard mit Notiz", () => {
    const steep = run(templateR1, { roof_pitch: { value: 40 } });
    expect(steep.facts.roof_slopes_deg).toEqual([40, 40]);
    expect(steep.notes).toEqual([]);
    expect(run(templateR1, { roof_pitch: { value: 25 } }).facts.roof_slopes_deg).toEqual([25, 25]);
    const outside = run(templateR1, { roof_pitch: { value: 60 } });
    expect(outside.facts.roof_slopes_deg).toEqual([35, 35]);
    expect(outside.notes).toEqual([
      {
        slot_id: "roof_pitch",
        element_id: "roof",
        skipped_level: "global",
        skipped_value_ids: [],
        skipped_number: 60,
        applied_value_id: null,
        applied_number: 35,
        code: "out_of_range",
        reason: null,
      },
    ]);
  });

  it("Spanne der Katalogform, für die Form des Templates bis zu dessen Neigung erweitert", () => {
    const range = (house: HouseTemplate, selections: Selections = {}) => roofPitchRange({ template: house, catalog, configuration: configuration(selections) });
    expect(range(templateR1)).toEqual({ min: 25, max: 45, default: 35 });
    expect(range(templateR1, shape("shape.hip"))).toEqual({ min: 20, max: 45, default: 30 });
    expect(range(templateR1, shape("shape.flat"))).toBeNull();
    expect(range(flatHouse)).toBeNull();
    const fifty = { ...templateR1, roof: { ...templateR1.roof, design: { ...templateR1.roof.design, pitch_deg: 50 } } };
    expect(range(fifty)).toEqual({ min: 25, max: 50, default: 50 });
    expect(run(fifty).facts.roof_slopes_deg).toEqual([50, 50]);
  });

  it("gilt nicht beim Flachdach; die Wahl bleibt gespeichert", () => {
    const flat = run(templateR1, { roof_pitch: { value: 40 }, ...shape("shape.flat") });
    expect(flat.resolved.some((r) => r.slot_id === "roof_pitch")).toBe(false);
    expect(flat.notes.map((n) => n.code)).toEqual(["default_replaced"]);
    expect(flat.price.deltas.roof_pitch).toBe(0);
  });

  it("Schiefer unter 25° warnt", () => {
    const slate = { roof_type: { value: "roof.slate" }, ...shape("shape.mono_pitch") };
    expect(run(templateR1, slate)).toMatchObject({ status: "valid_with_warnings", rule_results: [expect.objectContaining({ rule_id: "slate_min_pitch" })] });
    expect(run(templateR1, { ...slate, roof_pitch: { value: 25 } }).status).toBe("valid");
  });
});

describe("Dachaufbau passend zur Form", () => {
  it("ein unpassender Standard wird durch den ersten passenden ersetzt", () => {
    const gable = run(flatHouse, shape("shape.gable"));
    expect(gable.notes).toEqual([
      {
        slot_id: "roof_type",
        element_id: "roof",
        skipped_level: "default",
        skipped_value_ids: ["roof.flat"],
        skipped_number: null,
        applied_value_id: "roof.tiles",
        applied_number: null,
        code: "default_replaced",
        reason: null,
      },
    ]);
    expect(gable.resolved.find((r) => r.slot_id === "roof_type")).toMatchObject({ option_value_id: "roof.tiles", source: "default" });
    expect(run(templateR1, shape("shape.flat")).resolved.find((r) => r.slot_id === "roof_type")).toMatchObject({ option_value_id: "roof.flat" });
  });

  it("eine unpassende Wahl: eine Notiz, die den Ersatz nennt", () => {
    const green = run(flatHouse, { ...shape("shape.gable"), roof_type: { value: "roof.green" } });
    expect(green.notes).toEqual([expect.objectContaining({ slot_id: "roof_type", skipped_level: "global", skipped_value_ids: ["roof.green"], applied_value_id: "roof.tiles", code: "roof_kind_mismatch" })]);
  });

  it("Kandidaten: Flach- und Gründach unter dem Walmdach nicht verfügbar", () => {
    const evaluation = run(templateR1, shape("shape.hip"), { candidates: "roof_type" });
    const available = Object.fromEntries(evaluation.candidates!.map((c) => [c.option_value_id, c.available_count]));
    expect(available).toEqual({ "roof.flat": 0, "roof.green": 0, "roof.tiles": 1, "roof.slate": 1 });
  });
});

describe("Flaches Demohaus mit geneigtem Dach", () => {
  it("Sturz auf Auflagerhöhe: an den Traufseiten liegt das Dach außen tiefer als die Fenster", () => {
    const model = deriveModel({ template: flatHouse, catalog, configuration: configuration(shape("shape.gable")) });
    const south = model.openings.find((o) => o.id === "win-living-south")!;
    expect(south.ceiling / 10_000).toBeCloseTo(2.5 - 0.36 * tan(35), 9);
    const gable = run(flatHouse, shape("shape.gable"));
    expect(gable.status).toBe("blocked");
    expect(new Set(gable.rule_results.map((r) => r.code))).toEqual(new Set(["opening_above_ceiling"]));
    // Gedreht liegen Süd- und Nordseite unter den Giebeln; nur das Westfenster bleibt an einer Traufe
    expect(run(flatHouse, shape("shape.gable", 90)).rule_results.map((r) => r.element_ids)).toEqual([["win-living-west"]]);
  });

  it("Überstände der Form, weil das Template flach ist", () => {
    const model = deriveModel({ template: flatHouse, catalog, configuration: configuration(shape("shape.gable")) });
    expect([model.roof.eaveOverhang, model.roof.vergeOverhang]).toEqual([5000, 3000]);
    expect(run(flatHouse, shape("shape.gable")).facts.eave_height).toBeCloseTo(2.5 - 0.86 * tan(35) + lift(35), 9);
  });
});

describe("Rücknahme", () => {
  it("L-Grundriss ist verträglich, jede Form entsteht", () => {
    expect(checkCompatibility({ template: lShape, catalog })).toMatchObject({ supported: true, issues: [] });
    for (const form of ["mono_pitch", "gable", "hip", "half_hip", "mansard", "mansard_gable"]) {
      const evaluation = run(lShape, shape(`shape.${form}`));
      expect(evaluation.facts.roof_shape).toBe(form);
      expect(evaluation.notes.map((n) => n.code)).toEqual(["default_replaced"]);
    }
  });

  it("Drehung, bei der zwei Giebel aneinanderstießen, wird zurückgenommen", () => {
    const config = configuration(shape("shape.gable", 90));
    const before = structuredClone(config);
    const turned = evaluate({ template: lShape, catalog, configuration: config });
    expect(config).toEqual(before);
    expect(turned.notes).toContainEqual({
      slot_id: "roof_rotation",
      element_id: "roof",
      skipped_level: "global",
      skipped_value_ids: [],
      skipped_number: 90,
      applied_value_id: null,
      applied_number: 0,
      code: "roof_not_constructible",
      reason: null,
    });
    expect(turned.resolved.find((r) => r.slot_id === "roof_rotation")).toMatchObject({ number: 0, source: "default" });
    expect(turned.facts).toEqual(run(lShape, shape("shape.gable")).facts);
  });

  it("Kandidaten der Drehung: gesperrt mit Grund", () => {
    const evaluation = run(lShape, shape("shape.gable"), { candidates: "roof_rotation" });
    expect(evaluation.candidates!.map((c) => [c.number, c.available_count, c.status])).toEqual([
      [0, 1, "valid"],
      [90, 0, "blocked"],
      [180, 1, "valid"],
      [270, 0, "blocked"],
    ]);
    expect(evaluation.candidates![1]!.rule_results).toEqual([
      expect.objectContaining({ code: "roof_not_constructible", outcome: "block", element_ids: ["roof"], params: { reason: "gables_adjacent" } }),
    ]);
    // Neigung: stufenlos, keine Kandidaten
    expect(run(lShape, shape("shape.gable"), { candidates: "roof_pitch" }).candidates).toEqual([]);
  });

  it("Form, die auf dem Grundriss nicht entsteht: zurück zur Form des Templates", () => {
    // Krüppelhöhe 6 m liegt über dem First jeder Neigung der Spanne
    const high: HouseCatalog = { ...catalog, roof_shapes: catalog.roof_shapes.map((s) => (s.id === "shape.half_hip" ? { ...s, break_height: 6 } : s)) };
    const evaluation = run(templateR1, shape("shape.half_hip"), { catalog: high, candidates: "roof_shape" });
    expect(evaluation.notes).toEqual([
      expect.objectContaining({ slot_id: "roof_shape", skipped_value_ids: ["shape.half_hip"], applied_value_id: "shape.gable", code: "roof_not_constructible" }),
    ]);
    expect(evaluation.facts.roof_shape).toBe("gable");
    const halfHip = evaluation.candidates!.find((c) => c.option_value_id === "shape.half_hip")!;
    expect(halfHip).toMatchObject({ available_count: 0, status: "blocked", price_delta: 0 });
    expect(halfHip.rule_results[0]!.params).toEqual({ reason: "break_too_high" });
  });

  it("entsteht das Dach des Templates nicht, ist das ein Befund der Prüfung", () => {
    const turned: HouseTemplate = {
      ...lShape,
      roof: { ...lShape.roof, eave_overhang: 0.5, verge_overhang: 0.3, design: { form: "gable", pitch_deg: 35, upper_pitch_deg: null, break_height: null, rotation: 90 } },
      slabs: lShape.slabs.filter((s) => s.kind !== "roof"),
      defaults: { ...lShape.defaults, roof_shape: "shape.gable", roof_type: "roof.tiles" },
    };
    expect(checkCompatibility({ template: turned, catalog }).issues).toEqual([
      { code: "roof_not_constructible", slot_id: null, element_id: null, ref_id: "gables_adjacent" },
    ]);
    expect(() => run(turned)).toThrow(ModelError);
  });
});
