// Rule Engine (P 8.3) für Katalogregeln und die Prüfung der Geometrie (P 6.6). Ergebnisse sind Hinweise und
// Vorschläge; nichts hier verändert die Auswahl (P 2.1 Nr. 9). PLU-Prüfungen liefert Python (E-HM-4).
import type { RuleCode } from "./codes.ts";
import type { HouseQuantity, HouseRuleResult } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { applies, type ExprContext } from "./expr.ts";
import { toMetres } from "./geometry/polygon.ts";
import type { CatalogIndex, TemplateIndex } from "./model.ts";
import { exprContext, slotTargets } from "./resolve.ts";

/** Toleranz der Geometrie (P 4): 1 mm. */
const TOLERANCE = 10;

export type Status = "valid" | "valid_with_warnings" | "with_deviations" | "blocked";

/**
 * Gebäudekennwerte für `building.*` in Regeln. Wand des Erdgeschosses; `roof_pitch` ist die Neigung der Traufflächen,
 * `parapet_upstand` gibt es nur beim Flachdach (sonst `null`, Vergleiche ergeben dann false, E-HM-34).
 */
export function buildingContext(model: DerivedModel, quantities: readonly HouseQuantity[]): Record<string, unknown> {
  const loop = model.loops[0]!;
  const roof = model.roof;
  return {
    storeys: model.loops.length,
    facade_height: toMetres(model.facadeHeight),
    wall_thickness: toMetres(loop.wallThickness),
    wall_profile_id: loop.profile.id,
    roof_type_id: roof.roofType.id,
    roof_kind: roof.roofType.kind,
    roof_form: roof.design.form,
    roof_shape_id: roof.shapeId,
    roof_pitch: roof.design.form === "flat" ? null : roof.design.pitchDeg,
    green_roof: roof.roofType.green,
    parapet_upstand: roof.flat ? toMetres(roof.flat.upstand) : null,
    top_height: toMetres(roof.top),
    footprint_area: quantities.find((q) => q.key === "footprint.area")?.value ?? 0,
  };
}

/** Mengen für `quantity.*`: Schlüssel mit Punkten werden verschachtelt, z. B. `quantity.roof.area`. */
function quantityContext(quantities: readonly HouseQuantity[]): Record<string, unknown> {
  const root: Record<string, unknown> = {};
  for (const quantity of quantities) {
    const parts = quantity.key.split(".");
    let node = root;
    for (const part of parts.slice(0, -1)) {
      node = (node[part] ??= {}) as Record<string, unknown>;
    }
    const last = parts.at(-1)!;
    node[last] = ((node[last] as number | undefined) ?? 0) + quantity.value;
  }
  return root;
}

function geometryResult(code: Exclude<RuleCode, "catalog_rule">, elementIds: string[], params: Record<string, number | string>): HouseRuleResult {
  return { code, rule_id: null, outcome: "block", message: null, element_ids: elementIds, suggestion: null, source: null, params };
}

/** Prüfung der Öffnungen nach der Auflösung (P 6.6): im Host, ohne Überlappung, unter der Decke ihres Geschosses. */
export function checkGeometry(model: DerivedModel): HouseRuleResult[] {
  const results: HouseRuleResult[] = [];
  const byHost = new Map<string, typeof model.openings>();
  for (const opening of model.openings) {
    byHost.set(opening.hostId, [...(byHost.get(opening.hostId) ?? []), opening]);
    const from = opening.offset - opening.width / 2;
    const to = opening.offset + opening.width / 2;
    if (from < -TOLERANCE || to > opening.hostLength + TOLERANCE) {
      results.push(geometryResult("opening_outside_host", [opening.id, opening.hostId], { host_length: toMetres(opening.hostLength) }));
    }
    if (opening.head > opening.ceiling + TOLERANCE) {
      results.push(geometryResult("opening_above_ceiling", [opening.id], { head: toMetres(opening.head), ceiling: toMetres(opening.ceiling) }));
    }
    if (opening.sill < -TOLERANCE) {
      results.push(geometryResult("opening_below_floor", [opening.id], { sill: toMetres(opening.sill) }));
    }
  }
  for (const openings of byHost.values()) {
    const sorted = [...openings].sort((a, b) => a.offset - b.offset);
    for (let i = 1; i < sorted.length; i++) {
      const a = sorted[i - 1]!;
      const b = sorted[i]!;
      if (a.offset + a.width / 2 > b.offset - b.width / 2 + TOLERANCE) {
        results.push(geometryResult("openings_overlap", [a.id, b.id], {}));
      }
    }
  }
  return results;
}

/** Katalogregeln mit `scope` building, selection und element. */
export function checkCatalogRules(
  model: DerivedModel,
  quantities: readonly HouseQuantity[],
  template: TemplateIndex,
  catalog: CatalogIndex,
  selection: Readonly<Record<string, string | null>>,
): HouseRuleResult[] {
  const shared: ExprContext = {
    building: buildingContext(model, quantities),
    quantity: quantityContext(quantities),
    selection,
    parameter: catalog.catalog.parameters,
  };
  const results: HouseRuleResult[] = [];
  for (const rule of catalog.catalog.rules) {
    const result = (elementIds: string[]): HouseRuleResult => ({
      code: "catalog_rule" satisfies RuleCode,
      rule_id: rule.id,
      outcome: rule.outcome,
      message: rule.message,
      element_ids: elementIds,
      suggestion: rule.suggestion,
      source: rule.source,
      params: {},
    });
    if (rule.scope !== "element" || rule.target === null) {
      if (applies(rule.when, shared)) results.push(result([]));
      continue;
    }
    for (const element of slotTargets(rule.target, template, catalog, selection)) {
      if (applies(rule.when, { ...shared, ...exprContext(element, selection, catalog) })) results.push(result([element.id]));
    }
  }
  return results;
}

export function statusOf(results: readonly HouseRuleResult[]): Status {
  if (results.some((r) => r.outcome === "block")) return "blocked";
  if (results.some((r) => r.outcome === "deviation")) return "with_deviations";
  if (results.some((r) => r.outcome === "warning")) return "valid_with_warnings";
  return "valid";
}

