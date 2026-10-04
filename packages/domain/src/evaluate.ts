// Pipeline (P 3): Auswahl → Resolver → Geometrie → Mengen → Preis, Regeln, Energie, Hausbeschreibung.
// Reine, deterministische Funktion von Template, Katalog und Auswahl (P 2.1 Nr. 7); dieselbe im Browser und in
// engine (L5). Kein Zwischenspeicher: die vollständige Rechnung des Demohauses dauert wenige Millisekunden (P 4.1).
import type {
  HouseCandidate,
  HouseCandidatesRequest,
  HouseCatalog,
  HouseConfiguration,
  HouseEvaluation,
  HouseRuleResult,
  HouseSlotSelection,
  HouseTemplate,
} from "./contract.gen.ts";
import { derive, type DerivedModel } from "./derive.ts";
import { energy } from "./energy.ts";
import { ModelError } from "./errors.ts";
import { holds } from "./expr.ts";
import { houseFacts } from "./facts.ts";
import { CatalogIndex, TemplateIndex } from "./model.ts";
import { price } from "./pricing.ts";
import { takeOff } from "./quantities.ts";
import { exprContext, resolve, selectionContext, slotTargets } from "./resolve.ts";
import { checkCatalogRules, checkGeometry, statusOf, type Status } from "./rules.ts";

/** Stand des Rechenkerns; geht in Snapshots als `engine_version` ein (P 16). */
export const DOMAIN_VERSION = "0.3.0";

/** Ein Durchlauf ohne Aufpreise und Vorschau. */
function compute(template: TemplateIndex, catalog: CatalogIndex, configuration: HouseConfiguration): HouseEvaluation {
  const resolution = resolve(configuration, template, catalog);
  const model = derive(template, catalog, resolution);
  const quantities = takeOff(model, catalog.catalog);
  const sum = price(catalog.catalog, template.template.slug, quantities, resolution);
  const selection = selectionContext(configuration, template, catalog);
  const ruleResults: HouseRuleResult[] = [...checkGeometry(model), ...checkCatalogRules(model, quantities, template, catalog, selection)];
  const vatRate = catalog.catalog.vat_rate;
  return {
    domain_version: DOMAIN_VERSION,
    status: statusOf(ruleResults),
    resolved: resolution.resolved,
    notes: resolution.notes,
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
}

function without(configuration: HouseConfiguration, slotId: string): HouseConfiguration {
  const selections = { ...configuration.selections };
  delete selections[slotId];
  return { selections };
}

function withValue(configuration: HouseConfiguration, slotId: string, optionId: string, elementId: string | null): HouseConfiguration {
  const current: HouseSlotSelection = configuration.selections[slotId] ?? { value: null, room_overrides: {}, element_overrides: {} };
  const value = { type: "option" as const, option_value_id: optionId };
  const next: HouseSlotSelection =
    elementId === null ? { ...current, value } : { ...current, element_overrides: { ...current.element_overrides, [elementId]: value } };
  return { selections: { ...configuration.selections, [slotId]: next } };
}

function candidates(
  template: TemplateIndex,
  catalog: CatalogIndex,
  configuration: HouseConfiguration,
  request: HouseCandidatesRequest,
  netAmount: number,
): HouseCandidate[] {
  const slot = catalog.slots.find((s) => s.id === request.slot_id);
  if (!slot) throw new ModelError("slot_unknown", { slot: request.slot_id });
  const selection = selectionContext(configuration, template, catalog);
  const targets = slotTargets(slot.target, template, catalog, selection).filter(
    (element) => request.element_id === null || element.id === request.element_id,
  );
  if (request.element_id !== null && !targets.length) throw new ModelError("element_unknown", { id: request.element_id });
  return (catalog.optionsBySlot.get(slot.id) ?? []).map((option): HouseCandidate => {
    const available = targets.filter((element) => holds(option.available_when, exprContext(element, selection, catalog))).length;
    let status: Status;
    let ruleResults: HouseCandidate["rule_results"];
    let priceDelta = 0;
    try {
      const hypothetical = compute(template, catalog, withValue(configuration, slot.id, option.id, request.element_id));
      status = hypothetical.status;
      ruleResults = hypothetical.rule_results;
      priceDelta = hypothetical.price.net_amount - netAmount;
    } catch (error) {
      if (!(error instanceof ModelError)) throw error;
      // Ein Wert, mit dem sich das Haus nicht rechnen lässt, würde blockieren (z. B. gemischte Profile)
      status = "blocked";
      ruleResults = [{ code: error.code, rule_id: null, outcome: "block", message: null, element_ids: [], suggestion: null, source: null, params: { ...error.detail } }];
    }
    return {
      option_value_id: option.id,
      available_count: available,
      target_count: targets.length,
      unavailable_reason: available < targets.length ? option.unavailable_reason : null,
      status,
      rule_results: ruleResults,
      price_delta: priceDelta,
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
  const evaluation = compute(template, catalog, input.configuration);
  // Aufpreis je gewähltem Slot: Differenz zum Ergebnis mit dem Standard dieses Slots (P 9.1)
  const deltas: Record<string, number> = {};
  for (const slotId of Object.keys(input.configuration.selections).sort()) {
    const base = compute(template, catalog, without(input.configuration, slotId)).price.net_amount;
    deltas[slotId] = evaluation.price.net_amount - base;
  }
  return {
    ...evaluation,
    price: { ...evaluation.price, deltas },
    candidates: input.candidates ? candidates(template, catalog, input.configuration, input.candidates, evaluation.price.net_amount) : null,
  };
}

/** Abgeleitetes Modell für Darstellung (2D, 3D ab HM2) und Tests; Teil des Kerns, nicht des Vertrags (3.4). */
export function deriveModel(input: EvaluateInput): DerivedModel {
  const catalog = new CatalogIndex(input.catalog);
  const template = new TemplateIndex(input.template, catalog);
  return derive(template, catalog, resolve(input.configuration, template, catalog));
}
