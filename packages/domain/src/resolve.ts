// Resolver (P 8.2, P 2.1 Nr. 4): je Slot und Ziel-Element genau ein wirksamer Wert. Reihenfolge Element →
// Raum → global → Standard des Templates (der des Bauteils vor dem des Slots, E-HM-37); jede Stufe greift nur
// mit einem verfügbaren Wert, jede übersprungene erzeugt eine Notiz. Die Auswahl selbst bleibt unverändert
// (P 2.1 Nr. 9).
import type {
  HouseConfiguration,
  HouseOptionValue,
  HouseResolutionNote,
  HouseResolvedValue,
  HouseSelector,
  HouseSlot,
  HouseSlotValue,
} from "./contract.gen.ts";
import { ModelError } from "./errors.ts";
import { holds, type ExprContext } from "./expr.ts";
import type { CatalogIndex, ModelElement, TemplateIndex } from "./model.ts";

export interface Resolution {
  readonly resolved: readonly HouseResolvedValue[];
  readonly notes: readonly HouseResolutionNote[];
  /** Slot → Element → Wert. */
  readonly bySlot: ReadonlyMap<string, ReadonlyMap<string, HouseResolvedValue>>;
}

/** Wirksamer globaler Wert je Slot (Auswahl, sonst Standard): Kontext `selection.*`. */
export function selectionContext(
  configuration: HouseConfiguration,
  template: TemplateIndex,
  catalog: CatalogIndex,
): Record<string, string | null> {
  return Object.fromEntries(
    catalog.slots.map((slot) => [
      slot.id,
      configuration.selections[slot.id]?.value?.option_value_id ?? template.template.defaults[slot.id] ?? null,
    ]),
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

function option(catalog: CatalogIndex, slot: HouseSlot, value: HouseSlotValue): HouseOptionValue {
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

export function resolve(configuration: HouseConfiguration, template: TemplateIndex, catalog: CatalogIndex): Resolution {
  checkSelections(configuration, template, catalog);
  const selection = selectionContext(configuration, template, catalog);
  const resolved: HouseResolvedValue[] = [];
  const notes: HouseResolutionNote[] = [];
  const bySlot = new Map<string, Map<string, HouseResolvedValue>>();

  for (const slot of catalog.slots) {
    const targets = slotTargets(slot.target, template, catalog, selection);
    if (!targets.length) continue;
    const defaultId = template.template.defaults[slot.id];
    if (defaultId === undefined) throw new ModelError("default_missing", { slot: slot.id });
    const chosen = configuration.selections[slot.id];
    const perSlot = new Map<string, HouseResolvedValue>();
    bySlot.set(slot.id, perSlot);

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

      const skipped: { level: Stage["level"]; ids: string[]; code: "unavailable" | "room_override_tie"; reason: HouseOptionValue["unavailable_reason"] }[] = [];
      let applied: { option: HouseOptionValue; source: HouseResolvedValue["source"]; available: boolean } | null = null;
      for (const stage of stages) {
        const options = stage.values.map((value) => option(catalog, slot, value));
        if (stage.tie) {
          skipped.push({ level: stage.level, ids: options.map((o) => o.id).sort(), code: "room_override_tie", reason: null });
          continue;
        }
        const candidate = options[0]!;
        if (holds(candidate.available_when, context)) {
          applied = { option: candidate, source: stage.level, available: true };
          break;
        }
        skipped.push({ level: stage.level, ids: [candidate.id], code: "unavailable", reason: candidate.unavailable_reason });
      }
      // Ist schon der Standard nicht verfügbar, gilt er trotzdem: ein Fehler des Katalogs (P 8.2)
      applied ??= { option: fallback, source: "default", available: holds(fallback.available_when, context) };

      const value: HouseResolvedValue = {
        slot_id: slot.id,
        element_id: element.id,
        option_value_id: applied.option.id,
        source: applied.source,
        available: applied.available,
      };
      resolved.push(value);
      perSlot.set(element.id, value);
      for (const skip of skipped) {
        notes.push({
          slot_id: slot.id,
          element_id: element.id,
          skipped_level: skip.level,
          skipped_value_ids: skip.ids,
          applied_value_id: applied.option.id,
          code: skip.code,
          reason: skip.reason,
        });
      }
    }
  }
  return { resolved, notes, bySlot };
}

/** Wirksame Zuweisung eines Elements über alle Slots, z. B. `window_type_id`. */
export function assigned(
  resolution: Resolution,
  catalog: CatalogIndex,
  elementId: string,
  field: "wall_profile_id" | "window_type_id" | "door_type_id" | "roof_type_id",
): string {
  const found: string[] = [];
  for (const perSlot of resolution.bySlot.values()) {
    const value = perSlot.get(elementId);
    const id = value ? catalog.options.get(value.option_value_id)?.assigns[field] : null;
    if (id) found.push(id);
  }
  if (found.length !== 1) {
    throw new ModelError(found.length ? "assignment_ambiguous" : "assignment_missing", { element: elementId, field });
  }
  return found[0]!;
}
