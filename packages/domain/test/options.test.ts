// Ausstattungslinien (Ergänzung 6, E-HM-14) und Nebenbauten (Ergänzung 7): Linien setzen globale Werte ohne eigenen
// Preis; Terrasse und Carport sind Slots mit Ziel `site`, ihre Maße, Mengen und Preise rechnet der Kern.
import { describe, expect, it } from "vitest";
import { activeLine, applyLine, checkCompatibility, evaluate, type HouseCatalog, type HouseConfiguration, type HouseLine, type HouseTemplate } from "../src/index.ts";
import { catalog, configuration, template as flatHouse, templateR1 } from "./demo-house.ts";

type Selections = NonNullable<Parameters<typeof configuration>[0]>;

const line = (id: string): HouseLine => catalog.lines.find((l) => l.id === id)!;
const active = (config: HouseConfiguration, house: HouseTemplate = flatHouse, lines: HouseCatalog = catalog) =>
  activeLine({ template: house, catalog: lines, configuration: config });

function run(house: HouseTemplate, selections: Selections = {}) {
  return evaluate({ template: house, catalog, configuration: configuration(selections) });
}

describe("Ausstattungslinien", () => {
  it("setzen die globalen Werte und lassen Überschreibungen stehen", () => {
    const start = configuration({ wall_profile: { value: "wall.wood" }, window_type: { elements: { "win-kitchen": "window.floor_length" } } });
    const applied = applyLine(start, line("line.traditional"));
    expect(applied.selections.wall_profile!.value).toEqual({ type: "option", option_value_id: "wall.brick" });
    expect(applied.selections.roof_shape!.value).toEqual({ type: "option", option_value_id: "shape.gable" });
    expect(applied.selections.roof_type!.value).toEqual({ type: "option", option_value_id: "roof.tiles" });
    expect(applied.selections.window_type).toEqual(start.selections.window_type);
    expect(start.selections.roof_shape).toBeUndefined();
  });

  it("aktiv, solange jeder Wert gewählt ist oder als Standard gilt", () => {
    expect(active(configuration())).toBeNull();
    const traditional = applyLine(configuration(), line("line.traditional"));
    expect(active(traditional)).toBe("line.traditional");
    expect(active(applyLine(traditional, { ...line("line.traditional"), presets: { wall_profile: { type: "option", option_value_id: "wall.wood" } } }))).toBeNull();
    // Modern: das Flachdach ist der Standard des Demohauses und muss nicht gewählt sein
    const modern = configuration({ wall_profile: { value: "wall.wood" }, roof_type: { value: "roof.green" }, window_type: { value: "window.floor_length" } });
    expect(active(modern)).toBe("line.contemporary");
    expect(active(modern, templateR1)).toBeNull();
  });

  it("eine Zahl gilt nur, wenn sie ausdrücklich gewählt ist", () => {
    const steep: HouseLine = { id: "line.steep", name: { fr: "Pente", de: "Steil" }, description: null, presets: { roof_pitch: { type: "number", value: 35 } }, sort_order: 5 };
    const lines = { ...catalog, lines: [steep] };
    // 35° ist die Neigung des Templates, aber nicht gewählt
    expect(active(configuration(), templateR1, lines)).toBeNull();
    expect(active(configuration({ roof_pitch: { value: 35 } }), templateR1, lines)).toBe("line.steep");
  });

  it("kein eigener Preis: die Aufpreise kommen von den gesetzten Werten", () => {
    const evaluation = evaluate({ template: templateR1, catalog, configuration: applyLine(configuration(), line("line.traditional")) });
    expect(evaluation.status).toBe("valid");
    expect(Object.keys(evaluation.price.deltas)).toEqual(["roof_shape", "roof_type", "wall_profile"]);
    // Satteldach mit Ziegeln ist schon der Standard des R+1
    expect(evaluation.price.deltas.roof_shape).toBe(0);
    expect(evaluation.price.deltas.roof_type).toBe(0);
    expect(evaluation.price.deltas.wall_profile).toBeCloseTo(evaluation.price.net_amount - run(templateR1).price.net_amount, 6);
  });

  it("die Kompatibilitätsprüfung kennt Slots und Werte der Linien", () => {
    const broken: HouseCatalog = {
      ...catalog,
      lines: [
        { ...line("line.traditional"), presets: { facade_colour: { type: "option", option_value_id: "wall.brick" } } },
        { ...line("line.contemporary"), presets: { roof_type: { type: "option", option_value_id: "wall.wood" }, roof_pitch: { type: "option", option_value_id: "shape.flat" } } },
      ],
    };
    expect(checkCompatibility({ template: flatHouse, catalog: broken }).issues).toEqual([
      { code: "line_slot_unknown", slot_id: "facade_colour", element_id: null, ref_id: "line.traditional" },
      { code: "line_value_unknown", slot_id: "roof_type", element_id: null, ref_id: "line.contemporary" },
      { code: "line_value_unknown", slot_id: "roof_pitch", element_id: null, ref_id: "line.contemporary" },
    ]);
  });
});

describe("Nebenbauten", () => {
  it("Terrasse an der längsten Gartenkante der Fassade, Fläche und Preis", () => {
    const wood = run(flatHouse, { terrace: { value: "terrace.wood" } });
    expect(wood.facts.terrace).toEqual({ type_id: "terrace.wood", depth: 3, width: 12.72, height_above_terrain: 0.3, sealing_factor: 0.5 });
    expect(wood.quantities.find((q) => q.key === "terrace.area")).toMatchObject({ ref_id: "terrace.wood", value: expect.closeTo(12.72 * 3, 9) });
    expect(wood.price.deltas.terrace).toBeCloseTo(12.72 * 3 * 180, 6);
    // Die Breite folgt dem Wandprofil (Ziegel: 12,96 m) und dem Haus (R+1: 10,72 m)
    expect(run(flatHouse, { terrace: { value: "terrace.wood" }, wall_profile: { value: "wall.brick" } }).facts.terrace!.width).toBeCloseTo(12.96, 9);
    const stone = run(templateR1, { terrace: { value: "terrace.stone" } });
    expect(stone.facts.terrace).toMatchObject({ type_id: "terrace.stone", depth: 3.5, width: 10.72 });
    expect(stone.price.deltas.terrace).toBeCloseTo(10.72 * 3.5 * 220, 6);
  });

  it("Carport mit Stellplätzen, je Stück bepreist", () => {
    const double = run(flatHouse, { carport: { value: "carport.double" } });
    expect(double.facts.carport).toEqual({ type_id: "carport.double", spaces: 2, width: 5.5, depth: 5, height: 2.6 });
    expect(double.quantities.find((q) => q.key === "carport.count")).toMatchObject({ ref_id: "carport.double", value: 1 });
    expect(double.price.deltas.carport).toBeCloseTo(15_500, 6);
    expect(run(flatHouse, { carport: { value: "carport.single" } }).facts.carport).toMatchObject({ spaces: 1, width: 3 });
  });

  it("ohne Wahl keine Nebenbauten, keine Mengen", () => {
    const none = run(flatHouse);
    expect([none.facts.terrace, none.facts.carport]).toEqual([null, null]);
    expect(none.quantities.some((q) => q.key === "terrace.area" || q.key === "carport.count")).toBe(false);
  });

  it("ohne Gartenkante keine Breite und kein Preis; die Prüfung meldet es", () => {
    const blind: HouseTemplate = {
      ...flatHouse,
      envelope: flatHouse.envelope.map((loop) => ({ ...loop, segments: loop.segments.map((s) => (s.facade_role === "garden" ? { ...s, facade_role: "side_left" as const } : s)) })),
    };
    const terrace = run(blind, { terrace: { value: "terrace.wood" } });
    expect(terrace.facts.terrace).toMatchObject({ type_id: "terrace.wood", width: null });
    expect(terrace.quantities.some((q) => q.key === "terrace.area")).toBe(false);
    expect(terrace.price.deltas.terrace).toBe(0);
    expect(checkCompatibility({ template: blind, catalog }).issues.map((i) => i.code)).toEqual(["terrace_without_garden_edge"]);
  });
});
