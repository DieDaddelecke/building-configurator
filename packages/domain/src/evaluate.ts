// Pipeline (P 3): Auswahl → Resolver → Geometrie → Mengen → Preis, Regeln, Energie, Hausbeschreibung.
// Reine, deterministische Funktion von Template, Katalog und Auswahl (P 2.1 Nr. 7); dieselbe im Browser und in
// engine (L5). Kein Zwischenspeicher: die vollständige Rechnung des Demohauses dauert wenige Millisekunden (P 4.1).
//
// Lässt sich das Dach mit der Auswahl nicht erzeugen, gilt die kleinste Rücknahme von Drehung, Neigung und Form
// (in dieser Reihenfolge, die Form zuletzt), jede mit Notiz `roof_not_constructible` (Ergänzung 4, E-HM-60).
import type {
  HouseCandidate,
  HouseCandidatesRequest,
  HouseCatalog,
  HouseConfiguration,
  HouseEvaluation,
  HouseResolutionNote,
  HouseRuleResult,
  HouseSlot,
  HouseSlotSelection,
  HouseSlotValue,
  HouseTemplate,
} from "./contract.gen.ts";
import type { RoofRefusal } from "./codes.ts";
import { derive, type DerivedModel } from "./derive.ts";
import { energy } from "./energy.ts";
import { ModelError } from "./errors.ts";
import { houseFacts } from "./facts.ts";
import { CatalogIndex, TemplateIndex } from "./model.ts";
import { price } from "./pricing.ts";
import { takeOff } from "./quantities.ts";
import { exprContext, refusal, resolve, selectionContext, slotAssigns, slotTargets, type Resolution } from "./resolve.ts";
import { RoofError, roofRefusal } from "./roof/build.ts";
import { ROOF_ROTATIONS, type PitchRange } from "./roof/effective.ts";
import { checkCatalogRules, checkGeometry, statusOf, type Status } from "./rules.ts";

/** Stand des Rechenkerns; geht in Snapshots als `engine_version` ein (P 16). */
export const DOMAIN_VERSION = "0.4.0";

/** Rechnung nach der Rücknahme: wirksame Auswahl, Auflösung, Modell und die zurückgenommenen Slots. */
interface Settled {
  readonly resolution: Resolution;
  readonly model: DerivedModel;
  readonly notes: readonly HouseResolutionNote[];
  /** Zurückgenommene Slots mit dem Grund, aus dem das Dach mit der Auswahl nicht entstand. */
  readonly refused: ReadonlyMap<string, RoofRefusal>;
}

function without(configuration: HouseConfiguration, slotIds: readonly string[]): HouseConfiguration {
  const selections = { ...configuration.selections };
  for (const slotId of slotIds) delete selections[slotId];
  return { selections };
}

/** Slots, deren Wahl das Dach bestimmt und zurückgenommen werden kann: Drehung, Neigung, Form. */
function roofChoices(resolution: Resolution, catalog: CatalogIndex): HouseSlot[] {
  const chosen = (slot: HouseSlot) => {
    const value = resolution.bySlot.get(slot.id)?.get("roof");
    return value !== undefined && value.source !== "default";
  };
  const rank = (slot: HouseSlot) => (slot.parameter === "roof_rotation" ? 0 : slot.parameter === "roof_pitch" ? 1 : 2);
  return catalog.slots
    .filter((slot) => slot.parameter !== null || slotAssigns(catalog, slot.id, "roof_shape_id"))
    .filter(chosen)
    .sort((a, b) => rank(a) - rank(b));
}

/** Teilmengen in der Reihenfolge der Rücknahme: erst ohne Form, dann klein vor groß, Drehung vor Neigung. */
function retreats(slots: readonly HouseSlot[]): HouseSlot[][] {
  const subsets: HouseSlot[][] = [];
  for (let mask = 1; mask < 1 << slots.length; mask++) subsets.push(slots.filter((_, i) => mask & (1 << i)));
  const shapes = (subset: readonly HouseSlot[]) => subset.filter((slot) => slot.parameter === null).length;
  return subsets.sort((a, b) => shapes(a) - shapes(b) || a.length - b.length);
}

function settle(template: TemplateIndex, catalog: CatalogIndex, configuration: HouseConfiguration): Settled {
  const first = resolve(configuration, template, catalog);
  let reason: RoofRefusal;
  try {
    return { resolution: first, model: derive(template, catalog, first), notes: [], refused: new Map() };
  } catch (error) {
    if (!(error instanceof RoofError)) throw error;
    reason = roofRefusal(error.code);
  }
  for (const dropped of retreats(roofChoices(first, catalog).slice(0, 4))) {
    const resolution = resolve(without(configuration, dropped.map((slot) => slot.id)), template, catalog);
    let model: DerivedModel;
    try {
      model = derive(template, catalog, resolution);
    } catch (error) {
      if (error instanceof RoofError) continue;
      throw error;
    }
    const notes = dropped.map((slot): HouseResolutionNote => {
      const skipped = first.bySlot.get(slot.id)!.get("roof")!;
      const applied = resolution.bySlot.get(slot.id)?.get("roof");
      return {
        slot_id: slot.id,
        element_id: "roof",
        skipped_level: skipped.source,
        skipped_value_ids: skipped.option_value_id === null ? [] : [skipped.option_value_id],
        skipped_number: skipped.number,
        applied_value_id: applied?.option_value_id ?? null,
        applied_number: applied?.number ?? null,
        code: "roof_not_constructible",
        reason: null,
      };
    });
    return { resolution, model, notes, refused: new Map(dropped.map((slot) => [slot.id, reason])) };
  }
  throw new ModelError("roof_not_constructible", { reason });
}

/** Ein Durchlauf ohne Aufpreise und Vorschau. */
function compute(template: TemplateIndex, catalog: CatalogIndex, configuration: HouseConfiguration): { evaluation: HouseEvaluation; refused: ReadonlyMap<string, RoofRefusal> } {
  const { resolution, model, notes, refused } = settle(template, catalog, configuration);
  const quantities = takeOff(model, catalog.catalog);
  const sum = price(catalog.catalog, template.template.slug, quantities, resolution);
  const selection = selectionContext(configuration, template, catalog);
  const ruleResults: HouseRuleResult[] = [...checkGeometry(model), ...checkCatalogRules(model, quantities, template, catalog, selection)];
  const vatRate = catalog.catalog.vat_rate;
  const evaluation: HouseEvaluation = {
    domain_version: DOMAIN_VERSION,
    status: statusOf(ruleResults),
    resolved: resolution.resolved,
    notes: [...resolution.notes, ...notes],
    quantities,
    price: {
      market: catalog.catalog.market,
      currency: catalog.catalog.currency,
      base_amount: sum.baseAmount,
      items: sum.items,
      net_amount: sum.netAmount,
      vat_rate: vatRate,
      vat_amount: sum.netAmount * vatRate,
      gross_amount: sum.netAmount * (1 + vatRate),
      deltas: {},
      is_estimate: true,
    },
    rule_results: ruleResults,
    energy: energy(model, catalog),
    facts: houseFacts(model, template),
    candidates: null,
  };
  return { evaluation, refused };
}

function withValue(configuration: HouseConfiguration, slotId: string, value: HouseSlotValue, elementId: string | null): HouseConfiguration {
  const current: HouseSlotSelection = configuration.selections[slotId] ?? { value: null, room_overrides: {}, element_overrides: {} };
  const next: HouseSlotSelection =
    elementId === null ? { ...current, value } : { ...current, element_overrides: { ...current.element_overrides, [elementId]: value } };
  return { selections: { ...configuration.selections, [slotId]: next } };
}

/** Vorschau eines Werts: Status, Regeln, Aufpreis; ein Wert, mit dem das Dach nicht entsteht, ist gesperrt. */
function preview(
  template: TemplateIndex,
  catalog: CatalogIndex,
  configuration: HouseConfiguration,
  slot: HouseSlot,
  netAmount: number,
): Pick<HouseCandidate, "status" | "rule_results" | "price_delta"> & { refused: boolean } {
  try {
    const { evaluation, refused } = compute(template, catalog, configuration);
    const reason = refused.get(slot.id);
    if (reason !== undefined) {
      const result: HouseRuleResult = { code: "roof_not_constructible", rule_id: null, outcome: "block", message: null, element_ids: ["roof"], suggestion: null, source: null, params: { reason } };
      return { status: "blocked", rule_results: [result], price_delta: 0, refused: true };
    }
    return { status: evaluation.status, rule_results: evaluation.rule_results, price_delta: evaluation.price.net_amount - netAmount, refused: false };
  } catch (error) {
    if (!(error instanceof ModelError)) throw error;
    // Ein Wert, mit dem sich das Haus nicht rechnen lässt, würde blockieren (z. B. gemischte Profile)
    const result: HouseRuleResult = { code: error.code, rule_id: null, outcome: "block", message: null, element_ids: [], suggestion: null, source: null, params: { ...error.detail } };
    return { status: "blocked" satisfies Status, rule_results: [result], price_delta: 0, refused: false };
  }
}

function candidates(
  template: TemplateIndex,
  catalog: CatalogIndex,
  configuration: HouseConfiguration,
  request: HouseCandidatesRequest,
  current: HouseEvaluation,
): HouseCandidate[] {
  const slot = catalog.slots.find((s) => s.id === request.slot_id);
  if (!slot) throw new ModelError("slot_unknown", { slot: request.slot_id });
  const netAmount = current.price.net_amount;
  if (slot.value_type === "number") {
    // Neigung: stufenlos in der Spanne (`roofPitchRange`); Drehung: die vier Lagen, wenn sie für die Form gilt
    if (slot.parameter !== "roof_rotation" || !current.resolved.some((value) => value.slot_id === slot.id)) return [];
    return ROOF_ROTATIONS.map((rotation): HouseCandidate => {
      const { refused, ...shown } = preview(template, catalog, withValue(configuration, slot.id, { type: "number", value: rotation }, null), slot, netAmount);
      return { option_value_id: null, number: rotation, available_count: refused ? 0 : 1, target_count: 1, unavailable_reason: null, ...shown };
    });
  }
  const selection = selectionContext(configuration, template, catalog);
  const targets = slotTargets(slot.target, template, catalog, selection).filter(
    (element) => request.element_id === null || element.id === request.element_id,
  );
  if (request.element_id !== null && !targets.length) throw new ModelError("element_unknown", { id: request.element_id });
  return (catalog.optionsBySlot.get(slot.id) ?? []).map((option): HouseCandidate => {
    const value: HouseSlotValue = { type: "option", option_value_id: option.id };
    const { refused, ...shown } = preview(template, catalog, withValue(configuration, slot.id, value, request.element_id), slot, netAmount);
    const available = refused
      ? 0
      : targets.filter((element) => !refusal(option, exprContext(element, selection, catalog), catalog, current.facts.roof_shape)).length;
    return {
      option_value_id: option.id,
      number: null,
      available_count: available,
      target_count: targets.length,
      unavailable_reason: available < targets.length ? option.unavailable_reason : null,
      ...shown,
    };
  });
}

export interface EvaluateInput {
  readonly template: HouseTemplate;
  readonly catalog: HouseCatalog;
  readonly configuration: HouseConfiguration;
  readonly candidates?: HouseCandidatesRequest | null;
}

export function evaluate(input: EvaluateInput): HouseEvaluation {
  const catalog = new CatalogIndex(input.catalog);
  const template = new TemplateIndex(input.template, catalog);
  const { evaluation } = compute(template, catalog, input.configuration);
  // Aufpreis je gewähltem Slot: Differenz zum Ergebnis mit dem Standard dieses Slots (P 9.1)
  const deltas: Record<string, number> = {};
  for (const slotId of Object.keys(input.configuration.selections).sort()) {
    const base = compute(template, catalog, without(input.configuration, [slotId])).evaluation.price.net_amount;
    deltas[slotId] = evaluation.price.net_amount - base;
  }
  return {
    ...evaluation,
    price: { ...evaluation.price, deltas },
    candidates: input.candidates ? candidates(template, catalog, input.configuration, input.candidates, evaluation) : null,
  };
}

/** Abgeleitetes Modell für Darstellung (2D, 3D ab HM2) und Tests; Teil des Kerns, nicht des Vertrags (3.4). */
export function deriveModel(input: EvaluateInput): DerivedModel {
  const catalog = new CatalogIndex(input.catalog);
  const template = new TemplateIndex(input.template, catalog);
  return settle(template, catalog, input.configuration).model;
}

/** Spanne der Neigung für den Regler (Slot `roof_pitch`), `null` beim Flachdach oder ohne geneigte Form. */
export function roofPitchRange(input: EvaluateInput): PitchRange | null {
  const catalog = new CatalogIndex(input.catalog);
  const template = new TemplateIndex(input.template, catalog);
  const { roof } = settle(template, catalog, input.configuration).resolution;
  return roof.design.form === "flat" ? null : roof.pitch;
}
