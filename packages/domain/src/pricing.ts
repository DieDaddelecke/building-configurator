// Pricing Engine (P 9): bottom-up aus Mengen und Preiseinträgen, intern ungerundet. Jeder Betrag stammt aus genau
// einem Preiseintrag (P 2.1 Nr. 11); Preisregeln enthalten keine Beträge und berechnen keine Mengen.
import type { HouseCatalog, HousePriceEntry, HousePriceItem, HousePricingRule, HouseQuantity } from "./contract.gen.ts";
import { ModelError } from "./errors.ts";
import { QUANTITY_KEYS, type QuantityKey } from "./quantities.ts";
import type { Resolution } from "./resolve.ts";

export interface PriceSum {
  readonly baseAmount: number;
  readonly items: readonly HousePriceItem[];
  readonly netAmount: number;
}

/** Einheit, in der eine Regel bepreist; leer bei unbekanntem Mengenschlüssel (meldet die Kompatibilitätsprüfung). */
export function ruleUnit(rule: HousePricingRule): string {
  if (rule.method === "lump_sum" || rule.method === "percent") return rule.method;
  return rule.quantity_key !== null && rule.quantity_key in QUANTITY_KEYS ? QUANTITY_KEYS[rule.quantity_key as QuantityKey].unit : "";
}

/**
 * Preiseinträge eines Bauteils (`by_target`) für eine Einheit: Ein Bauteil kann mehrere haben, z. B. ein Dachaufbau
 * je m² Fläche und je m First. Fehlt der mit der Einheit, kommen die Einträge zurück, die keine Regel dieses Ziels
 * braucht: Deren Einheit ist falsch (`price_unit_mismatch`); gibt es keinen, fehlt der Eintrag.
 */
export function targetEntries(catalog: HouseCatalog, target: string, refId: string | null, unit: string): HousePriceEntry[] {
  const found = catalog.price_entries.filter((e) => e.target_kind === target && e.target_id === refId);
  const fitting = found.filter((e) => e.unit === unit);
  if (fitting.length) return fitting;
  const used = new Set(catalog.pricing_rules.filter((r) => r.by_target === target).map(ruleUnit));
  return found.filter((e) => !used.has(e.unit));
}

function entry(catalog: HouseCatalog, rule: HousePricingRule, refId: string | null, unit: string): HousePriceEntry {
  if (rule.entry_id !== null) {
    const fixed = catalog.price_entries.find((e) => e.id === rule.entry_id);
    if (!fixed) throw new ModelError("price_entry_unknown", { rule: rule.id, entry: rule.entry_id });
    return fixed;
  }
  const found = targetEntries(catalog, rule.by_target!, refId, unit);
  if (found.length !== 1) {
    throw new ModelError(found.length ? "price_entry_ambiguous" : "price_entry_missing", {
      rule: rule.id,
      target: `${rule.by_target}:${refId ?? ""}`,
    });
  }
  return found[0]!;
}

function applies(rule: HousePricingRule, resolution: Resolution): boolean {
  if (rule.applies_to === null) return true;
  const values = resolution.bySlot.get(rule.applies_to.slot_id);
  return values !== undefined && [...values.values()].some((v) => v.option_value_id === rule.applies_to!.option_value_id);
}

export function price(catalog: HouseCatalog, templateSlug: string, quantities: readonly HouseQuantity[], resolution: Resolution): PriceSum {
  const items: HousePriceItem[] = [];
  const rules = [...catalog.pricing_rules].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  const subtotal = () => items.reduce((sum, item) => sum + item.amount, 0);

  for (const rule of rules) {
    if (!applies(rule, resolution)) continue;
    const base = { pricing_rule_id: rule.id, label: rule.label };
    if (rule.method === "lump_sum") {
      const e = entry(catalog, rule, templateSlug, "lump_sum");
      if (e.unit !== "lump_sum") throw new ModelError("price_unit_mismatch", { rule: rule.id, entry: e.id });
      items.push({ ...base, price_entry_id: e.id, quantity_key: null, ref_id: null, quantity: 1, unit: e.unit, unit_price: e.value, amount: e.value, element_ids: [] });
    } else if (rule.method === "per_unit") {
      for (const quantity of quantities.filter((q) => q.key === rule.quantity_key && q.value !== 0)) {
        const e = entry(catalog, rule, quantity.ref_id, quantity.unit);
        if (e.unit !== quantity.unit) throw new ModelError("price_unit_mismatch", { rule: rule.id, entry: e.id });
        items.push({
          ...base,
          price_entry_id: e.id,
          quantity_key: quantity.key,
          ref_id: quantity.ref_id,
          quantity: quantity.value,
          unit: e.unit,
          unit_price: e.value,
          amount: quantity.value * e.value,
          element_ids: quantity.element_ids,
        });
      }
    } else {
      const e = entry(catalog, rule, null, "percent");
      if (e.unit !== "percent") throw new ModelError("price_unit_mismatch", { rule: rule.id, entry: e.id });
      const basis =
        rule.percent_base === "subtotal"
          ? subtotal()
          : items.filter((item) => item.quantity_key === rule.percent_base).reduce((sum, item) => sum + item.amount, 0);
      items.push({ ...base, price_entry_id: e.id, quantity_key: null, ref_id: null, quantity: basis, unit: e.unit, unit_price: e.value, amount: (basis * e.value) / 100, element_ids: [] });
    }
  }
  const templateEntries = new Set(catalog.price_entries.filter((e) => e.target_kind === "template").map((e) => e.id));
  return {
    baseAmount: items.filter((item) => templateEntries.has(item.price_entry_id)).reduce((sum, item) => sum + item.amount, 0),
    items,
    netAmount: subtotal(),
  };
}
