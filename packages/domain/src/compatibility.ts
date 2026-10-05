// Kompatibilitätsprüfung Template ↔ Katalog (P 2.1 Nr. 5, P 5.2): alle Standards und Slot-Ziele auflösbar und
// verfügbar, jedes bepreiste Bauteil mit genau einer Preisquelle, das Template geometrisch stimmig (P 6.6,
// P 20.1.1), Dachformen, Linien und Nebenbauten vollständig (HM5). Das Ergebnis ist ein Prüfbefund; freigeben muss
// ein Mensch (PLAN_HAUSMODELL 3.5).
import { FillRule, intersect } from "clipper2-ts";
import { RULE_CODES, type CompatibilityCode, type RuleCode } from "./codes.ts";
import type { HouseCatalog, HouseCompatibility, HouseCompatibilityIssue, HouseOptionAssigns, HouseTemplate } from "./contract.gen.ts";
import { ModelError } from "./errors.ts";
import { DOMAIN_VERSION, evaluate } from "./evaluate.ts";
import { GeometryError } from "./geometry/offset.ts";
import { polygonDefect, signedArea, toUnits, type Point, type Polygon } from "./geometry/polygon.ts";
import { CatalogIndex, TemplateIndex } from "./model.ts";
import { ruleUnit, targetEntries } from "./pricing.ts";
import { QUANTITY_KEYS, type QuantityKey } from "./quantities.ts";
import { exprContext, refusal, selectionContext, slotAssigns, slotTargets } from "./resolve.ts";

/** Toleranz der Geometrie (P 4): 1 mm, als Fläche 1 mm × 1 m. */
const TOLERANCE = 10;
const AREA_TOLERANCE = 10 * 10_000;

type Issue = HouseCompatibilityIssue;

function issue(code: CompatibilityCode, extra: Partial<Issue> = {}): Issue {
  return { code, slot_id: null, element_id: null, ref_id: null, ...extra };
}

function units(points: readonly { readonly x: number; readonly y: number }[]): Polygon {
  return points.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
}

function overlapArea(a: Polygon, b: Polygon): number {
  return intersect([a.map((p) => ({ ...p }))], [b.map((p) => ({ ...p }))], FillRule.NonZero).reduce((sum, ring) => sum + Math.abs(signedArea(ring)), 0);
}

/** Punkt in oder auf einem Polygon (gerade/ungerade, Rand mit Toleranz). */
function inside(point: Point, polygon: Polygon): boolean {
  let result = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]!;
    const b = polygon[j]!;
    const length = Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
    const cross = (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x);
    const along = (point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y);
    if (Math.abs(cross) / length <= TOLERANCE && along >= 0 && along <= length * length) return true;
    if (a.y > point.y !== b.y > point.y && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) result = !result;
  }
  return result;
}

function checkTemplate(template: HouseTemplate, catalog: CatalogIndex): Issue[] {
  const issues: Issue[] = [];
  const levels = new Set(template.levels.map((l) => l.id));
  const rooms = new Set(template.rooms.map((r) => r.id));
  const segments = new Set(template.envelope.flatMap((loop) => loop.segments.map((s) => s.id)));
  const walls = new Set(template.interior_walls.map((w) => w.id));
  // Hülle je Geschoss; Räume und Innenwände liegen in der Hülle ihres Geschosses
  const envelopes = new Map<string, Polygon>();
  for (const loop of template.envelope) {
    if (!levels.has(loop.level_id)) issues.push(issue("level_unknown", { ref_id: loop.level_id }));
    const polygon = units(loop.inner_polygon);
    const defect = polygonDefect(polygon);
    if (defect) issues.push(issue(`envelope_${defect}`, { ref_id: loop.level_id }));
    else if (signedArea(polygon) <= 0) issues.push(issue("envelope_not_counter_clockwise", { ref_id: loop.level_id }));
    else envelopes.set(loop.level_id, polygon);
  }

  const roomPolygons: { id: string; level: string; polygon: Polygon }[] = [];
  for (const room of template.rooms) {
    if (!levels.has(room.level_id)) issues.push(issue("level_unknown", { element_id: room.id, ref_id: room.level_id }));
    if (!catalog.roomTypes.has(room.room_type_id)) issues.push(issue("room_type_unknown", { element_id: room.id, ref_id: room.room_type_id }));
    const polygon = units(room.polygon);
    const defect = polygonDefect(polygon);
    if (defect) {
      issues.push(issue(`room_${defect}`, { element_id: room.id }));
      continue;
    }
    const envelope = envelopes.get(room.level_id);
    if (envelope && signedArea(polygon) !== 0 && Math.abs(signedArea(polygon)) - overlapArea(polygon, envelope) > AREA_TOLERANCE) {
      issues.push(issue("room_outside_envelope", { element_id: room.id }));
    }
    roomPolygons.push({ id: room.id, level: room.level_id, polygon });
  }
  for (let i = 0; i < roomPolygons.length; i++) {
    for (let j = i + 1; j < roomPolygons.length; j++) {
      if (roomPolygons[i]!.level !== roomPolygons[j]!.level) continue;
      if (overlapArea(roomPolygons[i]!.polygon, roomPolygons[j]!.polygon) > AREA_TOLERANCE) {
        issues.push(issue("rooms_overlap", { element_id: roomPolygons[i]!.id, ref_id: roomPolygons[j]!.id }));
      }
    }
  }
  for (const wall of template.interior_walls) {
    if (!levels.has(wall.level_id)) issues.push(issue("level_unknown", { element_id: wall.id, ref_id: wall.level_id }));
    for (const id of wall.adjacent_room_ids) if (!rooms.has(id)) issues.push(issue("room_unknown", { element_id: wall.id, ref_id: id }));
    const axis = units(wall.axis);
    if (axis[0]!.x === axis[1]!.x && axis[0]!.y === axis[1]!.y) issues.push(issue("wall_axis_zero_length", { element_id: wall.id }));
    const envelope = envelopes.get(wall.level_id);
    if (envelope && !axis.every((p) => inside(p, envelope))) issues.push(issue("wall_outside_envelope", { element_id: wall.id }));
  }
  for (const opening of template.openings) {
    const hosts = opening.host_kind === "envelope_segment" ? segments : walls;
    if (!hosts.has(opening.host_id)) issues.push(issue("host_unknown", { element_id: opening.id, ref_id: opening.host_id }));
    for (const id of opening.adjacent_room_ids) if (!rooms.has(id)) issues.push(issue("room_unknown", { element_id: opening.id, ref_id: id }));
  }
  for (const id of [template.entrance_opening_id, template.garage_door_opening_id]) {
    const opening = template.openings.find((o) => o.id === id);
    if (id !== null && (!opening || opening.kind !== "door" || opening.host_kind !== "envelope_segment")) {
      issues.push(issue("exterior_door_unknown", { element_id: id }));
    }
  }
  // Bodenplatte einmal, eine Decke je oberem Geschoss, die Dachdecke nur beim Flachdach des Templates
  if (template.slabs.filter((s) => s.kind === "ground").length !== 1) issues.push(issue("ground_slab_missing"));
  if (template.roof.design.form === "flat" && template.slabs.filter((s) => s.kind === "roof").length !== 1) {
    issues.push(issue("roof_slab_missing"));
  }
  for (const level of [...template.levels].sort((a, b) => a.elevation - b.elevation).slice(1)) {
    if (template.slabs.filter((s) => s.kind === "floor" && s.level_id === level.id).length !== 1) {
      issues.push(issue("floor_slab_missing", { ref_id: level.id }));
    }
  }
  return issues;
}

function checkCatalog(catalog: CatalogIndex): Issue[] {
  const issues: Issue[] = [];
  const c = catalog.catalog;
  const slots = new Set(c.slots.map((s) => s.id));
  for (const layer of c.wall_layers) {
    if (!catalog.materials.has(layer.material_id)) issues.push(issue("material_unknown", { ref_id: layer.material_id }));
  }
  for (const profile of c.wall_profiles) {
    for (const id of profile.layer_ids) if (!catalog.layers.has(id)) issues.push(issue("layer_unknown", { ref_id: id }));
    const inProfile = (id: string) => profile.layer_ids.includes(id);
    if (!inProfile(profile.opening_anchor_layer_id)) issues.push(issue("anchor_layer_not_in_profile", { ref_id: profile.id }));
    if (profile.bearing && !profile.bearing.supported_layer_ids.every(inProfile)) issues.push(issue("bearing_layer_not_in_profile", { ref_id: profile.id }));
    if (profile.reveal_finish && !catalog.materials.has(profile.reveal_finish.material_id)) {
      issues.push(issue("material_unknown", { ref_id: profile.reveal_finish.material_id }));
    }
    const layers = profile.layer_ids.map((id) => catalog.layers.get(id));
    for (const layer of layers) {
      if (layer?.thermal && catalog.materials.get(layer.material_id)?.conductivity === null) {
        issues.push(issue("conductivity_missing", { ref_id: layer.id }));
      }
    }
  }
  for (const roof of c.roof_types) {
    for (const layer of roof.build_up) if (!catalog.materials.has(layer.material_id)) issues.push(issue("material_unknown", { ref_id: layer.material_id }));
  }
  for (const slot of c.slots) {
    if (slot.parent_slot_id !== null && !slots.has(slot.parent_slot_id)) issues.push(issue("slot_unknown", { slot_id: slot.id, ref_id: slot.parent_slot_id }));
  }
  const refs: Record<keyof HouseOptionAssigns, [ReadonlyMap<string, unknown>, CompatibilityCode]> = {
    wall_profile_id: [catalog.profiles, "wall_profile_unknown"],
    window_type_id: [catalog.windowTypes, "window_type_unknown"],
    door_type_id: [catalog.doorTypes, "door_type_unknown"],
    roof_type_id: [catalog.roofTypes, "roof_type_unknown"],
    roof_shape_id: [catalog.roofShapes, "roof_shape_unknown"],
    terrace_type_id: [catalog.terraceTypes, "terrace_type_unknown"],
    carport_type_id: [catalog.carportTypes, "carport_type_unknown"],
  };
  for (const option of c.option_values) {
    if (!slots.has(option.slot_id)) issues.push(issue("slot_unknown", { slot_id: option.slot_id, ref_id: option.id }));
    for (const [field, [map, code]] of Object.entries(refs) as [keyof HouseOptionAssigns, [ReadonlyMap<string, unknown>, CompatibilityCode]][]) {
      const id = option.assigns[field];
      if (id !== null && !map.has(id)) issues.push(issue(code, { slot_id: option.slot_id, ref_id: id }));
    }
  }
  // Dachformen: Neigung und Drehung nur mit einem Slot für die Form; zu jeder Form ein passender Dachaufbau
  const shapeSlots = c.slots.filter((slot) => slotAssigns(catalog, slot.id, "roof_shape_id"));
  for (const slot of c.slots.filter((s) => s.parameter !== null)) {
    if (!shapeSlots.length) issues.push(issue("parameter_slot_without_shape", { slot_id: slot.id }));
  }
  const roofKinds = new Set(c.option_values.flatMap((o) => (o.assigns.roof_type_id ? [catalog.roofTypes.get(o.assigns.roof_type_id)?.kind] : [])));
  for (const id of new Set(c.option_values.flatMap((o) => (o.assigns.roof_shape_id ? [o.assigns.roof_shape_id] : [])))) {
    const shape = catalog.roofShapes.get(id);
    if (shape && !roofKinds.has(shape.form === "flat" ? "flat" : "pitched")) issues.push(issue("roof_shape_without_roof_type", { ref_id: id }));
  }
  // Linien: bekannte Slots, Werte der passenden Art
  const slotById = new Map(c.slots.map((slot) => [slot.id, slot]));
  for (const line of c.lines) {
    for (const [slotId, value] of Object.entries(line.presets)) {
      const slot = slotById.get(slotId);
      if (!slot) {
        issues.push(issue("line_slot_unknown", { slot_id: slotId, ref_id: line.id }));
        continue;
      }
      const option = value.type === "option" ? catalog.options.get(value.option_value_id) : undefined;
      const fits = slot.value_type === "number" ? value.type === "number" : option !== undefined && option.slot_id === slotId;
      if (!fits) issues.push(issue("line_value_unknown", { slot_id: slotId, ref_id: line.id }));
    }
  }
  return issues;
}

/** Was ein Slot zuweist: Felder, die mindestens einer seiner Werte setzt. */
function assignsOf(catalog: CatalogIndex, slotId: string): Set<keyof HouseOptionAssigns> {
  const fields = new Set<keyof HouseOptionAssigns>();
  for (const option of catalog.optionsBySlot.get(slotId) ?? []) {
    for (const field of Object.keys(option.assigns) as (keyof HouseOptionAssigns)[]) if (option.assigns[field] !== null) fields.add(field);
  }
  return fields;
}

function checkSlots(template: HouseTemplate, catalog: CatalogIndex, index: TemplateIndex): Issue[] {
  const issues: Issue[] = [];
  const selection = selectionContext({ selections: {} }, index, catalog);
  const form = template.roof.design.form;
  const coverage = new Map<string, Map<keyof HouseOptionAssigns, string[]>>();
  for (const [slotId, optionId] of Object.entries(template.defaults)) {
    const option = catalog.options.get(optionId);
    if (!catalog.slots.some((s) => s.id === slotId)) issues.push(issue("slot_unknown", { slot_id: slotId }));
    else if (!option || option.slot_id !== slotId) issues.push(issue("default_unknown", { slot_id: slotId, ref_id: optionId }));
  }
  const targeted = new Map<string, Set<string>>();
  for (const slot of catalog.slots.filter((s) => s.value_type !== "number")) {
    const targets = slotTargets(slot.target, index, catalog, selection);
    targeted.set(slot.id, new Set(targets.map((element) => element.id)));
    if (!targets.length) continue;
    const defaultId = template.defaults[slot.id];
    if (defaultId === undefined) issues.push(issue("default_missing", { slot_id: slot.id }));
    const fields = assignsOf(catalog, slot.id);
    for (const element of targets) {
      // Standard des Bauteils vor dem des Slots (E-HM-37)
      const own = template.element_defaults[element.id]?.[slot.id] ?? defaultId;
      const option = own === undefined ? undefined : catalog.options.get(own);
      if (option && option.slot_id === slot.id && refusal(option, exprContext(element, selection, catalog), catalog, form)) {
        issues.push(issue("default_unavailable", { slot_id: slot.id, element_id: element.id, ref_id: option.id }));
      }
      const perElement = coverage.get(element.id) ?? new Map<keyof HouseOptionAssigns, string[]>();
      for (const field of fields) perElement.set(field, [...(perElement.get(field) ?? []), slot.id]);
      coverage.set(element.id, perElement);
    }
  }
  for (const [elementId, values] of Object.entries(template.element_defaults)) {
    for (const [slotId, optionId] of Object.entries(values)) {
      const option = catalog.options.get(optionId);
      const targets = targeted.get(slotId);
      if (!targets) issues.push(issue("slot_unknown", { slot_id: slotId, element_id: elementId }));
      else if (!option || option.slot_id !== slotId) issues.push(issue("default_unknown", { slot_id: slotId, element_id: elementId, ref_id: optionId }));
      else if (!targets.has(elementId)) issues.push(issue("element_default_not_targeted", { slot_id: slotId, element_id: elementId, ref_id: optionId }));
    }
  }
  // Jedes Bauteil braucht genau einen Slot, der seinen Typ zuweist (E-HM-31); Form, Terrasse und Carport höchstens einen
  const needs: [string, keyof HouseOptionAssigns][] = [
    ...template.envelope.flatMap((loop) => loop.segments.map((s): [string, keyof HouseOptionAssigns] => [s.id, "wall_profile_id"])),
    ...template.openings.map((o): [string, keyof HouseOptionAssigns] => [o.id, o.kind === "window" ? "window_type_id" : "door_type_id"]),
    ["roof", "roof_type_id"],
  ];
  for (const [elementId, field] of needs) {
    const slots = coverage.get(elementId)?.get(field) ?? [];
    if (slots.length !== 1) {
      issues.push(issue(slots.length ? "type_slot_ambiguous" : "type_slot_missing", { element_id: elementId, ref_id: field, slot_id: slots[0] ?? null }));
    }
  }
  const optional: [string, keyof HouseOptionAssigns][] = [
    ["roof", "roof_shape_id"],
    ["site", "terrace_type_id"],
    ["site", "carport_type_id"],
  ];
  for (const [elementId, field] of optional) {
    const slots = coverage.get(elementId)?.get(field) ?? [];
    if (slots.length > 1) issues.push(issue("type_slot_ambiguous", { element_id: elementId, ref_id: field, slot_id: slots[0]! }));
  }
  // Voreingestellte Form = Form des Templates, sonst entstünde ohne Wahl ein anderes Dach als im IFC
  for (const slot of catalog.slots.filter((s) => slotAssigns(catalog, s.id, "roof_shape_id"))) {
    const shapeId = catalog.options.get(template.defaults[slot.id] ?? "")?.assigns.roof_shape_id;
    const shape = shapeId ? catalog.roofShapes.get(shapeId) : undefined;
    if (shape && shape.form !== form) issues.push(issue("roof_shape_default_mismatch", { slot_id: slot.id, ref_id: shape.id }));
  }
  // Die Terrasse liegt an der längsten Gartenkante (Ergänzung 7): ohne Gartenkante keine Terrasse
  const terraces = catalog.catalog.option_values.some((o) => o.assigns.terrace_type_id !== null);
  const ground = [...template.levels].sort((a, b) => a.elevation - b.elevation)[0];
  const garden = template.envelope.some((loop) => loop.level_id === ground?.id && loop.segments.some((s) => s.facade_role === "garden"));
  if (terraces && !garden) issues.push(issue("terrace_without_garden_edge"));
  return issues;
}

/** Im Vertrag ist der Code einer Regel Text; der Kern meldet nur RULE_CODES (rules.ts). */
function ruleCode(code: string): RuleCode {
  if (!(RULE_CODES as readonly string[]).includes(code)) throw new Error(`rule code ${code} not in RULE_CODES`);
  return code as RuleCode;
}

/** Jede Menge, die eine Preisregel verrechnet, findet genau einen Eintrag mit passender Einheit (P 9.2). */
function checkPrices(template: HouseTemplate, catalog: CatalogIndex): Issue[] {
  const issues: Issue[] = [];
  const c = catalog.catalog;
  const entries = new Map(c.price_entries.map((e) => [e.id, e]));
  const optionRefs = (field: keyof HouseOptionAssigns) => [...new Set(c.option_values.map((o) => o.assigns[field]).filter((id): id is string => id !== null))];
  const possible: Record<string, string[]> = {
    wall_layer: [...new Set(optionRefs("wall_profile_id").flatMap((id) => catalog.profiles.get(id)?.layer_ids ?? []))],
    window_type: optionRefs("window_type_id"),
    door_type: optionRefs("door_type_id"),
    roof_type: optionRefs("roof_type_id"),
    terrace_type: optionRefs("terrace_type_id"),
    carport_type: optionRefs("carport_type_id"),
    template: [template.slug],
  };
  // Linien eines Dachs (First, Grat, …) gibt es nur bei geneigten Dachaufbauten
  const refsFor = (key: QuantityKey | null, target: string) =>
    key !== null && key.startsWith("roof.") && key !== "roof.area"
      ? (possible[target] ?? []).filter((id) => catalog.roofTypes.get(id)?.kind === "pitched")
      : (possible[target] ?? []);
  const unconditional = new Map<string, number>();
  for (const rule of c.pricing_rules) {
    const key = rule.quantity_key as QuantityKey | null;
    if (key !== null && !(key in QUANTITY_KEYS)) {
      issues.push(issue("quantity_key_unknown", { ref_id: `${rule.id}:${key}` }));
      continue;
    }
    if (rule.method === "per_unit" && rule.applies_to === null && key !== null) unconditional.set(key, (unconditional.get(key) ?? 0) + 1);
    const unit = ruleUnit(rule);
    if (rule.entry_id !== null) {
      const e = entries.get(rule.entry_id);
      if (!e) issues.push(issue("price_entry_unknown", { ref_id: rule.entry_id }));
      else if (e.unit !== unit) issues.push(issue("price_unit_mismatch", { ref_id: e.id }));
      continue;
    }
    const target = rule.by_target!;
    if (rule.method === "per_unit" && QUANTITY_KEYS[key!].ref !== target) {
      issues.push(issue("price_target_mismatch", { ref_id: rule.id }));
      continue;
    }
    for (const ref of refsFor(key, target)) {
      const found = targetEntries(c, target, ref, unit);
      if (found.length !== 1) issues.push(issue(found.length ? "price_entry_ambiguous" : "price_entry_missing", { ref_id: `${target}:${ref}` }));
      else if (found[0]!.unit !== unit) issues.push(issue("price_unit_mismatch", { ref_id: found[0]!.id }));
    }
  }
  for (const [key, count] of unconditional) if (count > 1) issues.push(issue("price_source_ambiguous", { ref_id: key }));
  return issues;
}

export function checkCompatibility(input: { readonly template: HouseTemplate; readonly catalog: HouseCatalog }): HouseCompatibility {
  const catalog = new CatalogIndex(input.catalog);
  let issues = [...checkCatalog(catalog), ...checkPrices(input.template, catalog)];
  let index: TemplateIndex | null = null;
  try {
    index = new TemplateIndex(input.template, catalog);
  } catch (error) {
    if (!(error instanceof ModelError)) throw error;
    issues.push(issue(error.code, { element_id: error.detail.id ?? null }));
  }
  issues.push(...checkTemplate(input.template, catalog));
  if (index) issues.push(...checkSlots(input.template, catalog, index));
  // Zuletzt der Standard selbst: rechnet er, und ist er ohne Sperre (z. B. Öffnungen im Host, P 6.6)?
  if (!issues.length) {
    try {
      const result = evaluate({ template: input.template, catalog: input.catalog, configuration: { selections: {} } });
      for (const r of result.rule_results.filter((r) => r.outcome === "block")) {
        issues.push(issue(`default_${ruleCode(r.code)}`, { element_id: r.element_ids[0] ?? null, ref_id: r.rule_id }));
      }
    } catch (error) {
      if (!(error instanceof ModelError || error instanceof GeometryError)) throw error;
      // Grund, aus dem das Dach des Templates nicht entsteht (Ergänzung 4)
      issues.push(issue(error.code, { ref_id: error instanceof ModelError ? (error.detail.reason ?? null) : null }));
    }
  }
  issues = issues.sort((a, b) => a.code.localeCompare(b.code) || (a.element_id ?? "").localeCompare(b.element_id ?? ""));
  return { domain_version: DOMAIN_VERSION, supported: issues.length === 0, issues };
}
