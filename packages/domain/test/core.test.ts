// Unit-Tests des Rechenkerns mit der Test-Fixture (P 20.1). Grundstückswerte (Grenzabstände, Überbauung) prüft
// Python ab HM4 (E-HM-4); „blocked speichern, nicht einreichen“ gehört zum Kundenweg (HM4).
import { describe, expect, it } from "vitest";
import {
  checkCompatibility,
  deriveModel,
  evaluate,
  perimeterMetres,
  toUnits,
  type HouseCatalog,
  type HouseConfiguration,
  type HouseEvaluation,
  type HousePoint,
} from "../src/index.ts";
import { catalog, configuration, template } from "./demo-house.ts";

type Selections = NonNullable<Parameters<typeof configuration>[0]>;

function run(selections: Selections = {}, options: { catalog?: HouseCatalog; candidates?: { slot_id: string; element_id: string | null } } = {}) {
  return evaluate({ template, catalog: options.catalog ?? catalog, configuration: configuration(selections), candidates: options.candidates ?? null });
}

function quantity(evaluation: HouseEvaluation, key: string, ref: string | null = null): number {
  const found = evaluation.quantities.filter((q) => q.key === key && q.ref_id === ref);
  expect(found, `${key}:${ref}`).toHaveLength(1);
  return found[0]!.value;
}

function size(points: readonly HousePoint[]): [number, number] {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  return [Math.max(...ys) - Math.min(...ys), Math.max(...xs) - Math.min(...xs)];
}

const BRICK = { wall_profile: { value: "wall.brick" } };
const WOOD = { wall_profile: { value: "wall.wood" } };
const FLOOR = { window_type: { value: "window.floor_length" } };
const GREEN = { roof_type: { value: "roof.green" } };
const base = run();

describe("Außen- und Innenkontur", () => {
  it.each([
    ["Standard", {}, [8.72, 12.72], 42.88],
    ["Ziegel", BRICK, [8.96, 12.96], 43.84],
    ["Holz", WOOD, [8.88, 12.88], 43.52],
  ] as const)("%s", (_, selections, outer, perimeter) => {
    const evaluation = run(selections);
    const [depth, width] = size(evaluation.facts.facade_outline);
    expect(depth).toBeCloseTo(outer[0], 10);
    expect(width).toBeCloseTo(outer[1], 10);
    const model = deriveModel({ template, catalog, configuration: configuration(selections) });
    expect(perimeterMetres(model.loops[0]!.facadeOutline)).toBeCloseTo(perimeter, 10);
    // Innenkontur bei jedem Profil exakt 8,00 × 12,00 m
    expect(model.loops[0]!.reference).toEqual(template.envelope[0]!.inner_polygon.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) })));
  });
});

describe("Mengen", () => {
  it("Öffnungsflächen mit Haustür", () => {
    expect(quantity(base, "opening.area")).toBeCloseTo(13.62, 10);
    expect(quantity(run(FLOOR), "opening.area")).toBeCloseTo(19.02, 10);
  });

  it("Schichtflächen mit Standardfenstern", () => {
    expect(quantity(base, "wall.layer.area", "layer.concrete_20")).toBeCloseTo(116.94, 10);
    expect(quantity(base, "wall.layer.area", "layer.insulation_16")).toBeCloseTo(121.548, 10);
    const brick = run(BRICK);
    expect(quantity(brick, "wall.layer.area", "layer.battens_4")).toBeCloseTo(124.108, 10);
    expect(quantity(brick, "wall.layer.area", "layer.brick_8")).toBeCloseTo(125.644, 10);
    expect(quantity(run(WOOD), "wall.layer.area", "layer.wood_4")).toBeCloseTo(125.132, 10);
  });

  it("Auflager und Laibungen", () => {
    const brick = run(BRICK);
    expect(quantity(brick, "bearing.length", "foundation_ledge")).toBeCloseTo(43.52, 10);
    expect(quantity(brick, "reveal.area", "brick_slips")).toBeCloseTo(3.792, 10);
    expect(quantity(run({ ...BRICK, ...FLOOR }), "reveal.area", "brick_slips")).toBeCloseTo(4.872, 10);
    const wood = run(WOOD);
    expect(quantity(wood, "reveal.area", "wood_cladding")).toBeCloseTo(2.528, 10);
    expect(wood.quantities.some((q) => q.key === "bearing.length")).toBe(false);
    expect(base.quantities.some((q) => q.key === "reveal.area" || q.key === "bearing.length")).toBe(false);
  });

  it("Dachfläche", () => {
    expect(quantity(base, "roof.area", "roof.flat")).toBeCloseTo(110.9184, 10);
    expect(quantity(run(BRICK), "roof.area", "roof.flat")).toBeCloseTo(110.9184, 10);
  });
});

describe("Öffnungen", () => {
  it("behalten Lage und Sturz bei Profil- und Typwechsel; bodentief ohne Brüstung", () => {
    const models = [{}, BRICK, WOOD, FLOOR, { ...BRICK, ...FLOOR }].map((s) => deriveModel({ template, catalog, configuration: configuration(s) }));
    const windows = (i: number) => models[i]!.openings.filter((o) => o.kind === "window");
    for (let i = 1; i < models.length; i++) {
      expect(windows(i).map((o) => [o.id, o.offset, o.center])).toEqual(windows(0).map((o) => [o.id, o.offset, o.center]));
      expect(windows(i).every((o) => o.head === toUnits(2.5))).toBe(true);
    }
    const floor = windows(3);
    expect(floor.filter((o) => o.typeId === "window.floor_length").map((o) => o.sill)).toEqual([0, 0, 0, 0, 0]);
    expect(floor.find((o) => o.id === "win-bath")).toMatchObject({ typeId: "window.standard", sill: toUnits(0.9) });
  });
});

describe("Resolver", () => {
  it("globaler Wert greift im Bad nicht, genau eine Notiz, Auswahl unverändert", () => {
    const config = configuration(FLOOR);
    const before = structuredClone(config);
    const evaluation = evaluate({ template, catalog, configuration: config });
    expect(config).toEqual(before);
    expect(evaluation.notes).toEqual([
      {
        slot_id: "window_type",
        element_id: "win-bath",
        skipped_level: "global",
        skipped_value_ids: ["window.floor_length"],
        applied_value_id: "window.standard",
        code: "unavailable",
        reason: catalog.option_values.find((o) => o.id === "window.floor_length")!.unavailable_reason,
      },
    ]);
    const windows = evaluation.resolved.filter((r) => r.slot_id === "window_type");
    expect(windows.filter((r) => r.option_value_id === "window.floor_length")).toHaveLength(5);
    expect(windows.find((r) => r.element_id === "win-bath")).toMatchObject({ option_value_id: "window.standard", source: "default" });
    expect(evaluation.status).toBe("valid");
  });

  it("Einzelüberschreibung auf ein anderes Fenster wirkt", () => {
    const evaluation = run({ window_type: { value: "window.floor_length", elements: { "win-kitchen": "window.standard" } } });
    expect(evaluation.resolved.find((r) => r.element_id === "win-kitchen")).toMatchObject({ option_value_id: "window.standard", source: "element" });
    expect(evaluation.resolved.find((r) => r.element_id === "win-living-south")).toMatchObject({ option_value_id: "window.floor_length", source: "global" });
  });

  it("Element-Override am Bad-Fenster wird übersprungen", () => {
    const evaluation = run({ window_type: { elements: { "win-bath": "window.floor_length" } } });
    expect(evaluation.notes).toHaveLength(1);
    expect(evaluation.notes[0]).toMatchObject({ element_id: "win-bath", skipped_level: "element", applied_value_id: "window.standard" });
  });

  it("Raum-Override zwischen Räumen gleicher Priorität greift nicht (E-HM-32)", () => {
    const evaluation = run({ interior_door: { rooms: { "room-bedroom": "door.interior_wide", "room-hall": "door.interior" } } });
    // Schlafzimmer und Flur haben Priorität 10: Gleichstand an door-bedroom
    expect(evaluation.notes).toEqual([
      {
        slot_id: "interior_door",
        element_id: "door-bedroom",
        skipped_level: "room",
        skipped_value_ids: ["door.interior", "door.interior_wide"],
        applied_value_id: "door.interior",
        code: "room_override_tie",
        reason: null,
      },
    ]);
    expect(evaluation.resolved.find((r) => r.element_id === "door-bedroom")).toMatchObject({ source: "default" });
    // Bad (30) schlägt Flur (10); nur ein Raum mit Überschreibung greift allein
    const bath = run({ interior_door: { rooms: { "room-bath": "door.interior_wide", "room-hall": "door.interior" } } });
    expect(bath.resolved.find((r) => r.element_id === "door-bath")).toMatchObject({ option_value_id: "door.interior_wide", source: "room" });
    const single = run({ interior_door: { rooms: { "room-bedroom": "door.interior_wide" } } });
    expect(single.resolved.find((r) => r.element_id === "door-bedroom")).toMatchObject({ option_value_id: "door.interior_wide", source: "room" });
    expect(single.notes).toEqual([]);
  });

  it("Standard des Bauteils geht dem des Slots vor, eine Auswahl beiden (E-HM-37)", () => {
    const own = { ...template, element_defaults: { "win-kitchen": { window_type: "window.floor_length" } } };
    const standard = evaluate({ template: own, catalog, configuration: configuration() });
    expect(standard.resolved.find((r) => r.element_id === "win-kitchen")).toMatchObject({ option_value_id: "window.floor_length", source: "default" });
    expect(standard.resolved.find((r) => r.element_id === "win-living-south")).toMatchObject({ option_value_id: "window.standard", source: "default" });
    expect(standard.price.deltas).toEqual({});
    const chosen = evaluate({ template: own, catalog, configuration: configuration({ window_type: { value: "window.standard" } }) });
    expect(chosen.resolved.find((r) => r.element_id === "win-kitchen")).toMatchObject({ option_value_id: "window.standard", source: "global" });
    expect(chosen.price.deltas.window_type).toBeCloseTo(-(standard.price.net_amount - base.price.net_amount), 6);
  });

  it("evaluateCandidates: Bodentief teilweise verfügbar (5 von 6), +1.352 €", () => {
    const evaluation = run({}, { candidates: { slot_id: "window_type", element_id: null } });
    const floor = evaluation.candidates!.find((c) => c.option_value_id === "window.floor_length")!;
    expect(floor).toMatchObject({ available_count: 5, target_count: 6, status: "valid" });
    expect(floor.unavailable_reason).not.toBeNull();
    expect(floor.price_delta).toBeCloseTo(1352, 6);
    const standard = evaluation.candidates!.find((c) => c.option_value_id === "window.standard")!;
    expect(standard).toMatchObject({ available_count: 6, target_count: 6, unavailable_reason: null, price_delta: 0 });
    // Für das Bad-Fenster allein ist Bodentief nicht verfügbar
    const bath = run({}, { candidates: { slot_id: "window_type", element_id: "win-bath" } });
    expect(bath.candidates!.find((c) => c.option_value_id === "window.floor_length")).toMatchObject({ available_count: 0, target_count: 1, price_delta: 0 });
  });
});

describe("Preis", () => {
  it("Ausgangszustand und TVA", () => {
    expect(base.status).toBe("valid");
    expect(base.price.net_amount).toBeCloseTo(429_328.512, 6);
    expect(base.price.base_amount).toBe(390_000);
    expect(base.price.vat_amount).toBeCloseTo(base.price.net_amount * 0.2, 6);
    expect(base.price.gross_amount).toBeCloseTo(base.price.net_amount * 1.2, 6);
    expect(base.price.is_estimate).toBe(true);
  });

  it.each([
    ["Ziegel", BRICK, "wall_profile", 6961.12],
    ["Holz", WOOD, "wall_profile", 8118.22],
    ["Bodentief", FLOOR, "window_type", 1352],
    ["Gründach", GREEN, "roof_type", 8873.472],
  ] as const)("Aufpreis %s", (_, selections, slot, delta) => {
    const evaluation = run(selections);
    expect(evaluation.price.net_amount - base.price.net_amount).toBeCloseTo(delta, 6);
    expect(evaluation.price.deltas[slot]).toBeCloseTo(delta, 6);
  });

  it("Ziegel: Fassadenschichten und Auflager getrennt nachvollziehbar", () => {
    const brick = run(BRICK);
    const bearing = brick.price.items.find((i) => i.pricing_rule_id === "bearing")!;
    expect(bearing).toMatchObject({ price_entry_id: "price.bearing.foundation_ledge", unit_price: 45 });
    expect(bearing.amount).toBeCloseTo(1958.4, 6);
    expect(brick.price.net_amount - bearing.amount - base.price.net_amount).toBeCloseTo(5002.72, 6);
  });

  it("Bodentief: Fenster +2.000 €, Wand −648 €", () => {
    const floor = run(FLOOR);
    const sum = (e: HouseEvaluation, rule: string) => e.price.items.filter((i) => i.pricing_rule_id === rule).reduce((s, i) => s + i.amount, 0);
    expect(sum(floor, "windows") - sum(base, "windows")).toBeCloseTo(2000, 6);
    expect(sum(floor, "wall_layers") - sum(base, "wall_layers")).toBeCloseTo(-648, 6);
  });

  it("Aufpreise unabhängig von der Reihenfolge der Auswahl", () => {
    const a = run({ ...BRICK, ...FLOOR, ...GREEN });
    const b = run({ ...GREEN, ...FLOOR, ...BRICK });
    expect(b).toEqual(a);
    expect(Object.keys(a.price.deltas)).toEqual(["roof_type", "wall_profile", "window_type"]);
  });

  it("jeder Betrag geht auf genau einen Preiseintrag zurück", () => {
    for (const evaluation of [base, run({ ...BRICK, ...FLOOR, ...GREEN })]) {
      const entries = new Map(catalog.price_entries.map((e) => [e.id, e]));
      for (const item of evaluation.price.items) {
        const entry = entries.get(item.price_entry_id)!;
        expect(entry).toBeDefined();
        expect(item.unit_price).toBe(entry.value);
        expect(item.unit).toBe(entry.unit);
        expect(item.amount).toBeCloseTo(item.quantity * item.unit_price, 9);
      }
      expect(evaluation.price.items.reduce((s, i) => s + i.amount, 0)).toBeCloseTo(evaluation.price.net_amount, 9);
    }
  });

  it("fehlender Preiseintrag bei by_target meldet die Kompatibilitätsprüfung", () => {
    const missing = { ...catalog, price_entries: catalog.price_entries.filter((e) => e.id !== "price.window.floor_length") };
    const result = checkCompatibility({ template, catalog: missing });
    expect(result.supported).toBe(false);
    expect(result.issues).toContainEqual({ code: "price_entry_missing", slot_id: null, element_id: null, ref_id: "window_type:window.floor_length" });
  });
});

describe("Energie", () => {
  it("U-Werte; Hinterlüftung setzt Rse = Rsi", () => {
    const u = (e: HouseEvaluation) => e.energy.wall_u_values[0]!.u_value;
    expect(u(base)).toBeCloseTo(0.207, 3);
    expect(u(run(BRICK))).toBeCloseTo(0.203, 3);
    expect(u(run(WOOD))).toBeCloseTo(0.203, 3);
  });

  it("Fensteranteile je Himmelsrichtung", () => {
    const south = base.energy.window_shares.find((s) => s.direction === "s")!;
    expect(south.window_area).toBeCloseTo(3 * 1.92, 10);
    expect(south.facade_area).toBeCloseTo(12.72 * 3.2, 10);
  });
});

describe("Status und Hausbeschreibung", () => {
  it("eine Regel mit block sperrt, ohne die Auswahl zu ändern", () => {
    // Dachaufbau 0,41 m überragt die Attika (0,40 m): Regel parapet_upstand
    const thick: HouseCatalog = {
      ...catalog,
      roof_types: catalog.roof_types.map((r) =>
        r.id === "roof.green" ? { ...r, build_up: r.build_up.map((l) => (l.material_id === "green_substrate" ? { ...l, thickness: 0.25 } : l)) } : r,
      ),
    };
    const config: HouseConfiguration = configuration(GREEN);
    const before = structuredClone(config);
    const evaluation = evaluate({ template, catalog: thick, configuration: config });
    expect(evaluation.status).toBe("blocked");
    expect(evaluation.rule_results).toEqual([expect.objectContaining({ code: "catalog_rule", rule_id: "parapet_upstand", outcome: "block" })]);
    expect(config).toEqual(before);
    expect(evaluation.resolved.find((r) => r.slot_id === "roof_type")).toMatchObject({ option_value_id: "roof.green", source: "global" });
    expect(run(GREEN).status).toBe("valid");
  });

  it("Höhen, Fläche und Lage der Haustür", () => {
    expect(base.facts).toMatchObject({ storeys: 1, roof_form: "flat", eave_height: 3, top_height: 3, ground_floor_offset: 0.2, facade_material_class: "render" });
    expect(base.facts.floor_area).toBeCloseTo(40 + 2 * 11.56 + 8.28 + 2 * 10.88, 10);
    // Haustür auf der Ostseite (Kante 1 ab der Straßenseite), 4,10 m von der Innenecke
    expect(base.facts.entrance).toEqual({ edge: 1, position: expect.closeTo((4.1 + 0.36) / 8.72, 12) });
    expect(base.facts.facade_roles.map((r) => r.role)).toEqual(["street", "side_right", "garden", "side_left"]);
    expect(run(GREEN).facts.top_height).toBe(3);
  });

  it("Demohaus ist mit dem Katalog verträglich", () => {
    expect(checkCompatibility({ template, catalog })).toEqual({ domain_version: base.domain_version, supported: true, issues: [] });
  });
});
