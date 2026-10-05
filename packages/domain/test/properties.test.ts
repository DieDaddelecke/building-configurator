// Property-based Tests (P 20.2).
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import {
  areaSquareMetres,
  deriveModel,
  evaluate,
  perimeterMetres,
  toUnits,
  unionPolygons,
  type HouseCatalog,
  type HouseConfiguration,
  type HouseTemplate,
  type Polygon,
} from "../src/index.ts";
import { catalog, configuration, template } from "./demo-house.ts";

const CM = 100;
const PROFILES = ["wall.standard", "wall.brick", "wall.wood"];

// --- Rechtwinklige Hüllen: Rechteck mit höchstens einem Vorsprung je Seite, Maße in cm -------------------------

interface Bump {
  readonly start: number;
  readonly width: number;
  readonly depth: number;
}

const bump = (side: number) =>
  fc.option(
    fc
      .integer({ min: 50, max: side - 200 })
      .chain((start) => fc.record({ start: fc.constant(start), width: fc.integer({ min: 150, max: side - 50 - start }), depth: fc.integer({ min: 100, max: 400 }) })),
    { nil: null, freq: 2 },
  );

const hull = fc
  .record({ w: fc.integer({ min: 600, max: 1600 }), h: fc.integer({ min: 600, max: 1200 }) })
  .chain(({ w, h }) => fc.record({ w: fc.constant(w), h: fc.constant(h), bumps: fc.tuple(bump(w), bump(h), bump(w), bump(h)) }))
  .map(({ w, h, bumps }): Polygon => {
    const rect = (x0: number, y0: number, x1: number, y1: number): Polygon =>
      [
        { x: x0, y: y0 },
        { x: x1, y: y0 },
        { x: x1, y: y1 },
        { x: x0, y: y1 },
      ].map((p) => ({ x: p.x * CM, y: p.y * CM }));
    const [south, east, north, west] = bumps as readonly (Bump | null)[];
    const parts = [rect(0, 0, w, h)];
    // Jeder Vorsprung greift 10 cm in das Rechteck, damit die Vereinigung zusammenhängt
    if (south) parts.push(rect(south.start, -south.depth, south.start + south.width, 10));
    if (east) parts.push(rect(w - 10, east.start, w + east.depth, east.start + east.width));
    if (north) parts.push(rect(north.start, h - 10, north.start + north.width, h + north.depth));
    if (west) parts.push(rect(-west.depth, west.start, 10, west.start + west.width));
    return unionPolygons(parts);
  });

/** Schichtdicken in mm: Beton, Dämmung, Unterkonstruktion, Ziegel, Holz. */
const thicknesses = fc.tuple(...Array.from({ length: 5 }, () => fc.integer({ min: 20, max: 300 })));

function hullTemplate(polygon: Polygon): HouseTemplate {
  const points = polygon.map((p) => ({ x: p.x / 10_000, y: p.y / 10_000 }));
  const segments = points.map((_, i) => ({ id: `seg-${i}`, source_ifc_guid: null, facade_role: null }));
  const openings = points.flatMap((a, i) => {
    const b = points[(i + 1) % points.length]!;
    const length = Math.abs(b.x - a.x) + Math.abs(b.y - a.y);
    return length >= 1.5
      ? [{ id: `win-${i}`, source_ifc_guid: null, kind: "window" as const, host_kind: "envelope_segment" as const, host_id: `seg-${i}`, offset_along_host: length / 2, adjacent_room_ids: [] }]
      : [];
  });
  return {
    ...template,
    envelope: [{ level_id: "rdc", inner_polygon: points, segments }],
    interior_walls: [],
    openings,
    rooms: [],
    entrance_opening_id: null,
  };
}

function layered(mm: readonly number[]): HouseCatalog {
  const ids = ["layer.concrete_20", "layer.insulation_16", "layer.battens_4", "layer.brick_8", "layer.wood_4"];
  return { ...catalog, wall_layers: catalog.wall_layers.map((l) => ({ ...l, thickness: mm[ids.indexOf(l.id)]! / 1000 })) };
}

describe("Hülle und Profile", () => {
  it("der Generator liefert konvexe und konkave Hüllen", () => {
    const corners = fc.sample(hull, { numRuns: 200, seed: 1 }).map((p) => p.length);
    expect(corners).toContain(4);
    expect(Math.max(...corners)).toBeGreaterThanOrEqual(16);
  });

  it("Innenkontur bleibt, Außenkontur liegt außen, Öffnungen bleiben, Mittellinie = Innenumfang + 8·d", () => {
    fc.assert(
      fc.property(hull, thicknesses, (polygon, mm) => {
        const houseTemplate = hullTemplate(polygon);
        const houseCatalog = layered(mm);
        const reference = houseTemplate.envelope[0]!.inner_polygon.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
        const centers: unknown[] = [];
        for (const profile of PROFILES) {
          const model = deriveModel({ template: houseTemplate, catalog: houseCatalog, configuration: configuration({ wall_profile: { value: profile } }) });
          const loop = model.loops[0]!;
          expect(loop.reference).toEqual(reference);
          for (const layer of loop.layers) {
            expect(areaSquareMetres(layer.outline)).toBeGreaterThan(areaSquareMetres(reference));
            expect(areaSquareMetres(unionPolygons([layer.outline, reference]))).toBeCloseTo(areaSquareMetres(layer.outline), 8);
            expect(layer.centerline / 10_000).toBeCloseTo(perimeterMetres(reference) + (8 * (layer.inner + layer.outer)) / 2 / 10_000, 6);
          }
          centers.push(model.openings.map((o) => [o.id, o.center]));
        }
        expect(centers[1]).toEqual(centers[0]);
        expect(centers[2]).toEqual(centers[0]);
      }),
      { numRuns: 60 },
    );
  });
});

// --- Auswahl --------------------------------------------------------------------------------------------------

const windows = template.openings.filter((o) => o.kind === "window").map((o) => o.id);
const interiorDoors = template.openings.filter((o) => o.kind === "door" && o.host_kind === "interior_wall").map((o) => o.id);
const roomIds = template.rooms.map((r) => r.id);
const windowValues = ["window.standard", "window.floor_length"];
const doorValues = ["door.interior", "door.interior_wide"];

const overrides = (keys: readonly string[], values: readonly string[]) =>
  fc.dictionary(fc.constantFrom(...keys), fc.constantFrom(...values), { maxKeys: keys.length });

const selections = fc.record({
  wall_profile: fc.option(fc.record({ value: fc.constantFrom(...PROFILES) }), { nil: undefined }),
  window_type: fc.option(
    fc.record({ value: fc.option(fc.constantFrom(...windowValues), { nil: undefined }), elements: overrides(windows, windowValues), rooms: overrides(roomIds, windowValues) }),
    { nil: undefined },
  ),
  interior_door: fc.option(
    fc.record({ value: fc.option(fc.constantFrom(...doorValues), { nil: undefined }), elements: overrides(interiorDoors, doorValues), rooms: overrides(roomIds, doorValues) }),
    { nil: undefined },
  ),
  roof_type: fc.option(fc.record({ value: fc.constantFrom("roof.flat", "roof.green") }), { nil: undefined }),
});

/** Nur Optionswerte: die Eigenschaften gelten den Slots für Fenster und Türen. */
type Selections = Record<string, { value?: string; rooms?: Record<string, string>; elements?: Record<string, string> }>;

function compact(raw: Record<string, object | undefined>): Selections {
  return Object.fromEntries(Object.entries(raw).filter(([, v]) => v !== undefined)) as Selections;
}

/** Dieselbe Auswahl mit Schlüsseln in umgekehrter Reihenfolge. */
function reversed(config: HouseConfiguration): HouseConfiguration {
  const flip = <T>(record: Readonly<Record<string, T>>) => Object.fromEntries(Object.entries(record).reverse());
  return {
    selections: Object.fromEntries(
      Object.entries(config.selections)
        .reverse()
        .map(([k, s]) => [k, { value: s.value, room_overrides: flip(s.room_overrides), element_overrides: flip(s.element_overrides) }]),
    ),
  };
}

function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object") {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

describe("Preis, Resolver und Regeln", () => {
  it("Preis ist deterministisch und unabhängig von der Reihenfolge der Auswahl", () => {
    fc.assert(
      fc.property(selections, (raw) => {
        const config = configuration(compact(raw));
        const a = evaluate({ template, catalog, configuration: config });
        expect(JSON.stringify(evaluate({ template, catalog, configuration: config }))).toBe(JSON.stringify(a));
        expect(JSON.stringify(evaluate({ template, catalog, configuration: reversed(config) }))).toBe(JSON.stringify(a));
      }),
      { numRuns: 60 },
    );
  });

  it("Resolver: Element > Raum > global > Standard, jeweils nur verfügbare Werte", () => {
    const rooms = new Map(template.rooms.map((r) => [r.id, r]));
    const priority = new Map(catalog.room_types.map((t) => [t.id, t.override_priority]));
    const openings = new Map(template.openings.map((o) => [o.id, o]));
    const available = (elementId: string, value: string) =>
      value !== "window.floor_length" || !openings.get(elementId)!.adjacent_room_ids.some((id) => rooms.get(id)!.room_type_id === "bathroom");

    fc.assert(
      fc.property(selections, (raw) => {
        const s = compact(raw);
        const evaluation = evaluate({ template, catalog, configuration: configuration(s) });
        for (const [slot, elements] of [
          ["window_type", windows],
          ["interior_door", interiorDoors],
        ] as const) {
          const chosen = s[slot];
          for (const elementId of elements) {
            const stages: [string, string | undefined][] = [["element", chosen?.elements?.[elementId]]];
            const withOverride = openings.get(elementId)!.adjacent_room_ids.filter((id) => chosen?.rooms?.[id] !== undefined);
            const top = Math.max(...withOverride.map((id) => priority.get(rooms.get(id)!.room_type_id)!));
            const winners = withOverride.filter((id) => priority.get(rooms.get(id)!.room_type_id) === top);
            stages.push(["room", winners.length === 1 ? chosen!.rooms![winners[0]!] : undefined]);
            stages.push(["global", chosen?.value]);
            const hit = stages.find(([, value]) => value !== undefined && available(elementId, value));
            const expected = hit ? { source: hit[0], option_value_id: hit[1] } : { source: "default", option_value_id: template.defaults[slot] };
            expect(evaluation.resolved.find((r) => r.slot_id === slot && r.element_id === elementId)).toMatchObject(expected);
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  it("Neuberechnung nach einer Folge von Änderungen gleich der vollständigen Rechnung", () => {
    // Der Kern rechnet ohne Zwischenspeicher (evaluate.ts); die Invariante 12 heißt hier: kein Zustand zwischen Aufrufen
    fc.assert(
      fc.property(fc.array(selections, { minLength: 2, maxLength: 5 }), (steps) => {
        const results = steps.map((raw) => evaluate({ template, catalog, configuration: configuration(compact(raw)) }));
        expect(results.at(-1)).toEqual(evaluate({ template, catalog, configuration: configuration(compact(steps.at(-1)!)) }));
      }),
      { numRuns: 20 },
    );
  });

  it("die Regeln verändern die Auswahl nie, auch nicht bei einer Sperre", () => {
    const thick: HouseCatalog = {
      ...catalog,
      roof_types: catalog.roof_types.map((r) => (r.id === "roof.green" ? { ...r, build_up: [...r.build_up, { material_id: "green_substrate", thickness: 0.2 }] } : r)),
    };
    fc.assert(
      fc.property(selections, fc.constantFrom("wall_profile", "window_type", "interior_door", "roof_type"), (raw, slot) => {
        const config = deepFreeze(configuration(compact(raw)));
        const before = structuredClone(config);
        const evaluation = evaluate({ template, catalog: thick, configuration: config, candidates: { slot_id: slot, element_id: null } });
        expect(config).toEqual(before);
        if (raw.roof_type?.value === "roof.green") expect(evaluation.status).toBe("blocked");
      }),
      { numRuns: 40 },
    );
  });
});
