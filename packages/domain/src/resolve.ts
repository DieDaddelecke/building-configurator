// Resolver (P 8.2, P 2.1 Nr. 4): je Slot und Ziel-Element genau ein wirksamer Wert. Reihenfolge Element →
// Raum → global → Standard des Templates (der des Bauteils vor dem des Slots, E-HM-37); jede Stufe greift nur
// mit einem verfügbaren Wert, jede übersprungene erzeugt eine Notiz. Ist auch der Standard nicht verfügbar, gilt
// der erste verfügbare Wert des Slots (E-HM-60). Die Auswahl selbst bleibt unverändert (P 2.1 Nr. 9).
//
// Dach (Ergänzung 4, E-HM-62): zuerst die Slots der Dachform, dann die übrigen Werte (ein Dachaufbau ist nur
// verfügbar, wenn seine Art zur wirksamen Form passt), zuletzt die Zahlen für Neigung und Drehung.
import type {
  HouseConfiguration,
  HouseOptionValue,
  HouseResolutionNote,
  HouseResolvedValue,
  HouseSelector,
  HouseSlot,
  HouseSlotSelection,
  HouseSlotValue,
} from "./contract.gen.ts";
import { ModelError } from "./errors.ts";
import { holds, type ExprContext } from "./expr.ts";
import type { CatalogIndex, ModelElement, TemplateIndex } from "./model.ts";
import type { RoofForm, RoofRotation } from "./roof/build.ts";
import { baseRoof, inRange, ROOF_ROTATIONS, rotates, withNumbers, type EffectiveRoof } from "./roof/effective.ts";

export interface Resolution {
  readonly resolved: readonly HouseResolvedValue[];
  readonly notes: readonly HouseResolutionNote[];
  /** Slot → Element → Wert. */
  readonly bySlot: ReadonlyMap<string, ReadonlyMap<string, HouseResolvedValue>>;
  /** Wirksames Dach nach Form, Aufbau und Zahlen. */
  readonly roof: EffectiveRoof;
}

type AssignField = keyof HouseOptionValue["assigns"];

/** Wirksamer globaler Wert je Options-Slot (Auswahl, sonst Standard): Kontext `selection.*`. Zahl-Slots: `null`. */
export function selectionContext(
  configuration: HouseConfiguration,
  template: TemplateIndex,
  catalog: CatalogIndex,
): Record<string, string | null> {
  return Object.fromEntries(
    catalog.slots.map((slot) => {
      const value = configuration.selections[slot.id]?.value;
      if (slot.value_type === "number") return [slot.id, null];
      return [slot.id, value?.type === "option" ? value.option_value_id : (template.template.defaults[slot.id] ?? null)];
    }),
  );
}

export function exprContext(
  element: ModelElement,
  selection: Readonly<Record<string, string | null>>,
  catalog: CatalogIndex,
): ExprContext {
  return {
    element: element.context,
    room: element.elementKind === "room" ? element.context : null,
    selection,
    parameter: catalog.catalog.parameters,
  };
}

/** Elemente, die ein Selektor erfasst (Slot-Ziel, Ziel einer Regel). */
export function slotTargets(
  selector: HouseSelector,
  template: TemplateIndex,
  catalog: CatalogIndex,
  selection: Readonly<Record<string, string | null>>,
): ModelElement[] {
  return template.elements.filter(
    (element) => element.elementKind === selector.element_kind && holds(selector.where, exprContext(element, selection, catalog)),
  );
}

/** Weist ein Wert des Slots dieses Feld zu? */
export function slotAssigns(catalog: CatalogIndex, slotId: string, field: AssignField): boolean {
  return (catalog.optionsBySlot.get(slotId) ?? []).some((option) => option.assigns[field] !== null);
}

function option(catalog: CatalogIndex, slot: HouseSlot, value: HouseSlotValue): HouseOptionValue {
  if (value.type !== "option") throw new ModelError("value_type_mismatch", { slot: slot.id });
  const found = catalog.options.get(value.option_value_id);
  if (!found || found.slot_id !== slot.id) {
    throw new ModelError("option_unknown", { slot: slot.id, option: value.option_value_id });
  }
  return found;
}

function checkSelections(configuration: HouseConfiguration, template: TemplateIndex, catalog: CatalogIndex): void {
  const slots = new Map(catalog.slots.map((slot) => [slot.id, slot]));
  const rooms = new Set(template.template.rooms.map((room) => room.id));
  for (const [slotId, selection] of Object.entries(configuration.selections)) {
    const slot = slots.get(slotId);
    if (!slot) throw new ModelError("slot_unknown", { slot: slotId });
    const elementOverrides = Object.keys(selection.element_overrides);
    const roomOverrides = Object.keys(selection.room_overrides);
    if (elementOverrides.length && slot.granularity !== "per_element") {
      throw new ModelError("override_not_allowed", { slot: slotId, level: "element" });
    }
    if (roomOverrides.length && slot.granularity === "global") {
      throw new ModelError("override_not_allowed", { slot: slotId, level: "room" });
    }
    for (const id of roomOverrides) {
      if (!rooms.has(id)) throw new ModelError("room_unknown", { slot: slotId, id });
    }
    for (const id of elementOverrides) {
      if (!template.elementsById.has(id)) throw new ModelError("element_unknown", { slot: slotId, id });
    }
    const wanted = slot.value_type === "number" ? "number" : "option";
    const values = [selection.value, ...Object.values(selection.room_overrides), ...Object.values(selection.element_overrides)];
    if (values.some((value) => value !== null && value.type !== wanted)) throw new ModelError("value_type_mismatch", { slot: slotId });
  }
}

interface Stage {
  readonly level: "element" | "room" | "global";
  readonly values: readonly HouseSlotValue[];
  /** Mehrere Räume mit gleicher Priorität: die Stufe greift nicht (P 8.2). */
  readonly tie: boolean;
}

function roomStage(
  element: ModelElement,
  overrides: Readonly<Record<string, HouseSlotValue>>,
  template: TemplateIndex,
  catalog: CatalogIndex,
): Stage | null {
  // Nur Räume mit Überschreibung zählen; es gilt die höchste Priorität, Gleichstand hebt sie auf (E-HM-32)
  const candidates = element.roomIds
    .filter((id) => overrides[id] !== undefined)
    .map((id) => {
      const type = template.template.rooms.find((room) => room.id === id)!.room_type_id;
      return { value: overrides[id]!, priority: catalog.roomTypes.get(type)?.override_priority ?? 0 };
    });
  if (!candidates.length) return null;
  const top = Math.max(...candidates.map((c) => c.priority));
  const winners = candidates.filter((c) => c.priority === top);
  return { level: "room", values: winners.map((w) => w.value), tie: winners.length > 1 };
}

type Refusal = { readonly code: "unavailable" | "roof_kind_mismatch"; readonly reason: HouseOptionValue["unavailable_reason"] };

/**
 * Verfügbarkeit eines Werts an einem Element: `available_when`, dazu muss ein Dachaufbau zur wirksamen Form passen
 * (flach zu flach, geneigt zu geneigt). Weist der Wert selbst eine Form zu, gilt seine.
 */
export function refusal(option: HouseOptionValue, context: ExprContext, catalog: CatalogIndex, form: RoofForm): Refusal | null {
  if (!holds(option.available_when, context)) return { code: "unavailable", reason: option.unavailable_reason };
  const typeId = option.assigns.roof_type_id;
  if (typeId !== null) {
    const kind = catalog.roofTypes.get(typeId)?.kind;
    const shapeId = option.assigns.roof_shape_id;
    const own = shapeId === null ? form : (catalog.roofShapes.get(shapeId)?.form ?? form);
    if (kind !== undefined && (kind === "flat") !== (own === "flat")) return { code: "roof_kind_mismatch", reason: option.unavailable_reason };
  }
  return null;
}

interface SlotResult {
  readonly values: HouseResolvedValue[];
  readonly notes: HouseResolutionNote[];
}

function note(
  slot: HouseSlot,
  elementId: string,
  fields: Pick<HouseResolutionNote, "skipped_level" | "code" | "reason"> & Partial<HouseResolutionNote>,
): HouseResolutionNote {
  return {
    slot_id: slot.id,
    element_id: elementId,
    skipped_value_ids: [],
    skipped_number: null,
    applied_value_id: null,
    applied_number: null,
    ...fields,
  };
}

function resolveOptions(
  slot: HouseSlot,
  chosen: HouseSlotSelection | undefined,
  template: TemplateIndex,
  catalog: CatalogIndex,
  selection: Readonly<Record<string, string | null>>,
  form: RoofForm,
): SlotResult | null {
  const targets = slotTargets(slot.target, template, catalog, selection);
  if (!targets.length) return null;
  const defaultId = template.template.defaults[slot.id];
  if (defaultId === undefined) throw new ModelError("default_missing", { slot: slot.id });
  const values: HouseResolvedValue[] = [];
  const notes: HouseResolutionNote[] = [];

  for (const element of targets) {
    const elementDefault = template.template.element_defaults[element.id]?.[slot.id] ?? defaultId;
    const fallback = option(catalog, slot, { type: "option", option_value_id: elementDefault });
    const context = exprContext(element, selection, catalog);
    const stages: Stage[] = [];
    const own = chosen?.element_overrides[element.id];
    if (own) stages.push({ level: "element", values: [own], tie: false });
    const room = chosen ? roomStage(element, chosen.room_overrides, template, catalog) : null;
    if (room) stages.push(room);
    if (chosen?.value) stages.push({ level: "global", values: [chosen.value], tie: false });

    const skipped: { level: HouseResolutionNote["skipped_level"]; ids: string[]; code: HouseResolutionNote["code"]; reason: Refusal["reason"] }[] = [];
    let applied: { option: HouseOptionValue; source: HouseResolvedValue["source"]; available: boolean } | null = null;
    for (const stage of stages) {
      const options = stage.values.map((value) => option(catalog, slot, value));
      if (stage.tie) {
        skipped.push({ level: stage.level, ids: options.map((o) => o.id).sort(), code: "room_override_tie", reason: null });
        continue;
      }
      const candidate = options[0]!;
      const refused = refusal(candidate, context, catalog, form);
      if (!refused) {
        applied = { option: candidate, source: stage.level, available: true };
        break;
      }
      skipped.push({ level: stage.level, ids: [candidate.id], code: refused.code, reason: refused.reason });
    }
    if (!applied) {
      const refused = refusal(fallback, context, catalog, form);
      // Standard nicht verfügbar: der erste verfügbare Wert; gibt es keinen, gilt der Standard (Fehler des Katalogs)
      const replacement = refused ? (catalog.optionsBySlot.get(slot.id) ?? []).find((o) => !refusal(o, context, catalog, form)) : undefined;
      if (refused && replacement) {
        // Gemeldet nur ohne übersprungene Wahl: deren Notiz nennt den Ersatz schon
        if (!skipped.length) skipped.push({ level: "default", ids: [fallback.id], code: "default_replaced", reason: refused.reason });
        applied = { option: replacement, source: "default", available: true };
      } else {
        applied = { option: fallback, source: "default", available: !refused };
      }
    }

    values.push({
      slot_id: slot.id,
      element_id: element.id,
      option_value_id: applied.option.id,
      number: null,
      source: applied.source,
      available: applied.available,
    });
    for (const skip of skipped) {
      notes.push(
        note(slot, element.id, { skipped_level: skip.level, skipped_value_ids: skip.ids, applied_value_id: applied.option.id, code: skip.code, reason: skip.reason }),
      );
    }
  }
  return { values, notes };
}

/** Zahl eines Parameter-Slots; `null`, wenn der Slot für die wirksame Form nicht gilt. */
function resolveNumber(slot: HouseSlot, chosen: HouseSlotSelection | undefined, roof: EffectiveRoof): SlotResult | null {
  const wanted = chosen?.value?.type === "number" ? chosen.value.value : null;
  let fallback: number;
  let valid: (value: number) => boolean;
  if (slot.parameter === "roof_pitch") {
    const range = roof.pitch;
    if (range === null || roof.design.form === "flat") return null;
    fallback = range.default;
    valid = (value) => inRange(range, value);
  } else {
    if (!rotates(roof.design.form)) return null;
    fallback = roof.design.rotation;
    valid = (value) => (ROOF_ROTATIONS as readonly number[]).includes(value);
  }
  const ok = wanted !== null && valid(wanted);
  const value: HouseResolvedValue = {
    slot_id: slot.id,
    element_id: "roof",
    option_value_id: null,
    number: ok ? wanted : fallback,
    source: ok ? "global" : "default",
    available: true,
  };
  const notes =
    wanted !== null && !ok
      ? [note(slot, "roof", { skipped_level: "global", skipped_number: wanted, applied_number: fallback, code: "out_of_range", reason: null })]
      : [];
  return { values: [value], notes };
}

/** Wirksame Zuweisung eines Elements über alle Slots oder `null`; mehrere sind ein Fehler. */
function assignedOrNull(bySlot: Resolution["bySlot"], catalog: CatalogIndex, elementId: string, field: AssignField): string | null {
  const found: string[] = [];
  for (const perSlot of bySlot.values()) {
    const value = perSlot.get(elementId);
    const id = value?.option_value_id ? catalog.options.get(value.option_value_id)?.assigns[field] : null;
    if (id) found.push(id);
  }
  if (found.length > 1) throw new ModelError("assignment_ambiguous", { element: elementId, field });
  return found[0] ?? null;
}

export function resolve(configuration: HouseConfiguration, template: TemplateIndex, catalog: CatalogIndex): Resolution {
  checkSelections(configuration, template, catalog);
  const selection = selectionContext(configuration, template, catalog);
  const results = new Map<string, SlotResult>();
  const bySlot = new Map<string, Map<string, HouseResolvedValue>>();
  const store = (slot: HouseSlot, result: SlotResult | null) => {
    if (!result) return;
    results.set(slot.id, result);
    bySlot.set(slot.id, new Map(result.values.map((value) => [value.element_id, value])));
  };

  const numbers = catalog.slots.filter((slot) => slot.value_type === "number");
  const shapes = catalog.slots.filter((slot) => slot.value_type !== "number" && slotAssigns(catalog, slot.id, "roof_shape_id"));
  const others = catalog.slots.filter((slot) => slot.value_type !== "number" && !shapes.includes(slot));
  const templateForm = template.template.roof.design.form;
  for (const slot of shapes) store(slot, resolveOptions(slot, configuration.selections[slot.id], template, catalog, selection, templateForm));

  const shapeId = assignedOrNull(bySlot, catalog, "roof", "roof_shape_id");
  const shape = shapeId === null ? null : catalog.get(catalog.roofShapes, shapeId, "roof_shape_unknown");
  let roof = baseRoof(template.template, shape);
  for (const slot of others) store(slot, resolveOptions(slot, configuration.selections[slot.id], template, catalog, selection, roof.design.form));

  let pitch: number | null = null;
  let rotation: RoofRotation | null = null;
  for (const slot of numbers) {
    const result = resolveNumber(slot, configuration.selections[slot.id], roof);
    store(slot, result);
    const value = result?.values[0]?.number ?? null;
    if (slot.parameter === "roof_pitch") pitch = value;
    else rotation = value as RoofRotation | null;
  }
  roof = withNumbers(roof, pitch, rotation);

  // Ausgabe in der Reihenfolge der Slots des Katalogs, unabhängig von der Reihenfolge der Auflösung
  const ordered = catalog.slots.map((slot) => results.get(slot.id)).filter((result) => result !== undefined);
  return {
    resolved: ordered.flatMap((result) => result.values),
    notes: ordered.flatMap((result) => result.notes),
    bySlot,
    roof,
  };
}

/** Wirksame Zuweisung eines Elements über alle Slots, z. B. `window_type_id`; genau eine. */
export function assigned(resolution: Resolution, catalog: CatalogIndex, elementId: string, field: AssignField): string {
  const id = assignedOrNull(resolution.bySlot, catalog, elementId, field);
  if (id === null) throw new ModelError("assignment_missing", { element: elementId, field });
  return id;
}

/** Wirksame Zuweisung oder `null`, z. B. keine Terrasse. */
export function assignedOptional(resolution: Resolution, catalog: CatalogIndex, elementId: string, field: AssignField): string | null {
  return assignedOrNull(resolution.bySlot, catalog, elementId, field);
}
