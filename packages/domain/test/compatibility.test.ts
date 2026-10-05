/// <reference types="node" />
// Kompatibilitätsprüfung Template ↔ Katalog (P 2.1 Nr. 5, P 5.2): jeder Fehler wird gemeldet, nichts wirft.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { checkCompatibility, COMPATIBILITY_CODES, type CompatibilityCode, type HouseCatalog, type HouseTemplate } from "../src/index.ts";
import { catalog, template } from "./demo-house.ts";

type Case = [string, { template?: Partial<HouseTemplate>; catalog?: Partial<HouseCatalog> }, CompatibilityCode[]];

const opening = (id: string, change: object) => template.openings.map((o) => (o.id === id ? { ...o, ...change } : o));
const room = (id: string, change: object) => template.rooms.map((r) => (r.id === id ? { ...r, ...change } : r));
const slot = (id: string) => catalog.slots.find((s) => s.id === id)!;
const option = (id: string) => catalog.option_values.find((o) => o.id === id)!;
const assigning = (changes: Record<string, object>) => catalog.option_values.map((o) => (changes[o.id] ? { ...o, assigns: { ...o.assigns, ...changes[o.id] } } : o));

const cases: Case[] = [
  ["Hülle im Uhrzeigersinn", { template: { envelope: [{ ...template.envelope[0]!, inner_polygon: [...template.envelope[0]!.inner_polygon].reverse() }] } }, ["envelope_not_counter_clockwise"]],
  ["unbekannter Raumtyp", { template: { rooms: room("room-hall", { room_type_id: "garage" }) } }, ["room_type_unknown"]],
  ["Raum außerhalb der Hülle", { template: { rooms: room("room-bath", { polygon: [{ x: 8.6, y: 4.8 }, { x: 12.5, y: 4.8 }, { x: 12.5, y: 8 }, { x: 8.6, y: 8 }] }) } }, ["room_outside_envelope"]],
  ["Räume überlappen", { template: { rooms: room("room-kitchen", { polygon: [{ x: 5.1, y: 4.8 }, { x: 9, y: 4.8 }, { x: 9, y: 8 }, { x: 5.1, y: 8 }] }) } }, ["rooms_overlap"]],
  ["unbekannter Host", { template: { openings: opening("win-kitchen", { host_id: "seg-up" }) } }, ["host_unknown"]],
  ["Haustür fehlt", { template: { entrance_opening_id: "door-front" } }, ["exterior_door_unknown"]],
  ["zwei Bodenplatten", { template: { slabs: [...template.slabs, { ...template.slabs[0]!, id: "slab-ground-2" }] } }, ["ground_slab_missing"]],
  ["Standard fehlt", { template: { defaults: Object.fromEntries(Object.entries(template.defaults).filter(([slot]) => slot !== "roof_type")) } }, ["default_missing"]],
  ["Standard unbekannt", { template: { defaults: { ...template.defaults, window_type: "door.entrance" } } }, ["default_unknown"]],
  [
    "Standard nicht überall verfügbar",
    { template: { defaults: { ...template.defaults, window_type: "window.floor_length" } } },
    ["default_unavailable"],
  ],
  [
    "Preiseintrag fehlt",
    { catalog: { price_entries: catalog.price_entries.filter((e) => e.id !== "price.layer.battens_4") } },
    ["price_entry_missing"],
  ],
  [
    "Preiseintrag doppelt",
    { catalog: { price_entries: [...catalog.price_entries, { ...catalog.price_entries.find((e) => e.id === "price.roof.flat")!, id: "price.roof.flat.2" }] } },
    ["price_entry_ambiguous"],
  ],
  [
    "Einheit passt nicht",
    { catalog: { price_entries: catalog.price_entries.map((e) => (e.id === "price.window.standard" ? { ...e, unit: "m2" as const } : e)) } },
    ["price_unit_mismatch"],
  ],
  [
    "unbekannter Mengenschlüssel",
    { catalog: { pricing_rules: catalog.pricing_rules.map((r) => (r.id === "roof" ? { ...r, quantity_key: "roof.volume" } : r)) } },
    ["quantity_key_unknown"],
  ],
  [
    "zwei Regeln für dieselbe Menge",
    { catalog: { pricing_rules: [...catalog.pricing_rules, { ...catalog.pricing_rules.find((r) => r.id === "roof")!, id: "roof_2", order: 60 }] } },
    ["price_source_ambiguous"],
  ],
  [
    "Ankerschicht nicht im Profil",
    { catalog: { wall_profiles: catalog.wall_profiles.map((p) => (p.id === "profile.wood" ? { ...p, opening_anchor_layer_id: "layer.brick_8" } : p)) } },
    ["anchor_layer_not_in_profile"],
  ],
  [
    "Wärmeleitfähigkeit fehlt",
    { catalog: { materials: catalog.materials.map((m) => (m.id === "mineral_wool" ? { ...m, conductivity: null } : m)) } },
    ["conductivity_missing"],
  ],
  [
    "Option verweist ins Leere",
    { catalog: { option_values: catalog.option_values.map((o) => (o.id === "roof.green" ? { ...o, assigns: { ...o.assigns, roof_type_id: "roof.blue" } } : o)) } },
    ["price_entry_missing", "roof_type_unknown"],
  ],
  [
    "Haustür ohne Slot",
    { catalog: { slots: catalog.slots.filter((s) => s.id !== "entrance_door"), option_values: catalog.option_values.filter((o) => o.slot_id !== "entrance_door") } },
    ["slot_unknown", "type_slot_missing"],
  ],
  [
    "Standard sperrt",
    {
      catalog: {
        roof_types: catalog.roof_types.map((r) => (r.id === "roof.flat" ? { ...r, build_up: [...r.build_up, { material_id: "green_substrate", thickness: 0.2 }] } : r)),
      },
    },
    ["default_catalog_rule"],
  ],
  ["Öffnung außerhalb ihres Hosts", { template: { openings: opening("win-child", { offset_along_host: 11.7 }) } }, ["default_opening_outside_host"]],
  ["Standard des Bauteils nicht verfügbar", { template: { element_defaults: { "win-bath": { window_type: "window.floor_length" } } } }, ["default_unavailable"]],
  ["Standard des Bauteils aus anderem Slot", { template: { element_defaults: { "win-bath": { window_type: "door.entrance" } } } }, ["default_unknown"]],
  ["Standard des Bauteils, Slot unbekannt", { template: { element_defaults: { "win-bath": { shutter: "window.standard" } } } }, ["slot_unknown"]],
  [
    "Standard des Bauteils, Slot trifft es nicht",
    { template: { element_defaults: { "door-bath": { window_type: "window.standard" } } } },
    ["element_default_not_targeted"],
  ],
  // Dachformen, Linien und Nebenbauten (HM5)
  ["Dachdecke fehlt beim Flachdach", { template: { slabs: template.slabs.filter((s) => s.kind !== "roof") } }, ["roof_slab_missing"]],
  [
    "Neigung und Drehung ohne Slot für die Form",
    {
      template: { defaults: Object.fromEntries(Object.entries(template.defaults).filter(([id]) => id !== "roof_shape")) },
      catalog: { slots: catalog.slots.filter((s) => s.id !== "roof_shape"), option_values: catalog.option_values.filter((o) => o.slot_id !== "roof_shape"), lines: [] },
    },
    ["parameter_slot_without_shape"],
  ],
  [
    "geneigte Formen ohne geneigten Dachaufbau",
    { catalog: { option_values: catalog.option_values.filter((o) => o.id !== "roof.tiles" && o.id !== "roof.slate"), lines: catalog.lines.filter((l) => l.id !== "line.traditional") } },
    ["roof_shape_without_roof_type"],
  ],
  ["voreingestellte Form anders als im Template", { template: { defaults: { ...template.defaults, roof_shape: "shape.gable" } } }, ["roof_shape_default_mismatch"]],
  [
    "zwei Slots für die Form",
    {
      template: { defaults: { ...template.defaults, roof_shape_2: "shape.flat.2" } },
      catalog: {
        slots: [...catalog.slots, { ...slot("roof_shape"), id: "roof_shape_2", sort_order: 48 }],
        option_values: [...catalog.option_values, { ...option("shape.flat"), id: "shape.flat.2", slot_id: "roof_shape_2" }],
      },
    },
    ["type_slot_ambiguous"],
  ],
  [
    "Form, Terrasse und Carport unbekannt",
    {
      catalog: {
        option_values: assigning({
          "shape.hip": { roof_shape_id: "shape.dome" },
          "terrace.wood": { terrace_type_id: "terrace.glass" },
          "carport.single": { carport_type_id: "carport.tent" },
        }),
      },
    },
    ["carport_type_unknown", "price_entry_missing", "roof_shape_unknown", "terrace_type_unknown"],
  ],
  // Ein Dachaufbau hat zwei Einträge (Fläche, First): fehlt einer, fehlt er, die Einheit des anderen stimmt
  ["Preis des Firsts fehlt", { catalog: { price_entries: catalog.price_entries.filter((e) => e.id !== "price.ridge.tiles") } }, ["price_entry_missing"]],
];

describe("checkCompatibility", () => {
  it.each(cases)("%s", (_, change, codes) => {
    const result = checkCompatibility({ template: { ...template, ...change.template }, catalog: { ...catalog, ...change.catalog } });
    expect(result.supported).toBe(false);
    expect([...new Set(result.issues.map((i) => i.code))]).toEqual(codes);
    // Die Oberfläche übersetzt jeden Code der Liste (E-HM-33)
    expect(COMPATIBILITY_CODES).toEqual(expect.arrayContaining(result.issues.map((i) => i.code)));
  });

  it("führt jeden Code genau einmal und sortiert", () => {
    expect(new Set(COMPATIBILITY_CODES).size).toBe(COMPATIBILITY_CODES.length);
    expect([...COMPATIBILITY_CODES].sort()).toEqual(COMPATIBILITY_CODES);
    expect(COMPATIBILITY_CODES).toEqual(expect.arrayContaining(["default_opening_outside_host", "envelope_self_intersecting", "union_not_single"]));
  });
});

it.each(["template", "template-r1"])("Demo-Seed %s ist mit seinem Katalog verträglich", (name) => {
  // Der Seed ist frei änderbar (P 19), muss aber rechnen
  const load = (file: string) => JSON.parse(readFileSync(new URL(`../seed/demo-house/${file}.json`, import.meta.url), "utf8"));
  expect(checkCompatibility({ template: load(name), catalog: load("catalog") })).toMatchObject({ supported: true, issues: [] });
});
