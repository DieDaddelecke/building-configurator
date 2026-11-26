/** Werte einer Regel als kurzer Text (Spez. 5.2.4). Einheiten: Meter, Anteile 0–1, Grad. Jeder Parameter
 *  einer wirksamen Regel erscheint; eine wirksame Regel ergibt nie einen leeren Text. */

import type { TFunction } from "i18next";

import type { RuleOut } from "../api/rules";

type Params = Record<string, unknown>;

function num(value: unknown, language: string, digits = 2): string {
  return new Intl.NumberFormat(language === "de" ? "de-DE" : "fr-FR", { maximumFractionDigits: digits }).format(
    Number(value),
  );
}

const metres = (value: unknown, language: string) => `${num(value, language)} m`;
const percent = (value: unknown, language: string) => `${num(Number(value) * 100, language, 1)} %`;

function list(values: unknown, t: TFunction, prefix: string): string {
  return Array.isArray(values) ? values.map((v) => t(`${prefix}.${String(v)}`, { defaultValue: String(v) })).join(", ") : "";
}

function join(parts: (string | null | undefined | false)[]): string {
  return parts.filter(Boolean).join(" · ");
}

function measuredFrom(p: Params, t: TFunction): string | null {
  if (p.measured_from === "roof_edge") return t("rules.value.fromRoofEdge");
  if (p.measured_from === "any_projection") return t("rules.value.fromProjection");
  return null;
}

function boundary(p: Params, t: TFunction, language: string): string {
  const parts: string[] = [];
  if (p.min_m != null) parts.push(`≥ ${metres(p.min_m, language)}`);
  if (p.height_factor != null) {
    parts.push(t("rules.value.heightFactor", { factor: num(p.height_factor, language), basis: t(`rules.basis.${String(p.height_basis)}`) }));
  }
  let text = parts.join(" · ");
  if (p.allow_on_boundary) text = t("rules.value.orOnBoundary", { value: text });
  // Fassade ohne Ansichten (nur Umfang collectif, E-RD-9)
  const blind: string[] = [];
  if (p.blind_min_m != null) blind.push(`≥ ${metres(p.blind_min_m, language)}`);
  if (p.blind_height_factor != null) {
    blind.push(t("rules.value.heightFactor", { factor: num(p.blind_height_factor, language), basis: t(`rules.basis.${String(p.height_basis)}`) }));
  }
  return join([
    text,
    blind.length > 0 && t("rules.value.withoutViews", { value: blind.join(" · ") }),
    p.on_boundary_max_height_m != null && t("rules.value.onBoundaryHeight", { value: metres(p.on_boundary_max_height_m, language) }),
    measuredFrom(p, t),
  ]);
}

function street(p: Params, t: TFunction, language: string): string {
  let text: string;
  if (p.mode === "alignment") text = t("rules.value.alignment");
  else if (p.mode === "range") text = t("rules.value.range", { min: num(p.min_m, language), max: metres(p.max_m, language) });
  else if (p.mode === "fixed") text = t("rules.value.fixed", { value: metres(p.min_m, language) });
  else text = `≥ ${metres(p.min_m, language)}`;
  return join([text, measuredFrom(p, t)]);
}

function values(rule: RuleOut, t: TFunction, language: string): string {
  const p = rule.params as Params;
  switch (rule.kind) {
    case "setback_street":
      return street(p, t, language);
    case "setback_side":
    case "setback_rear":
    case "setback_between_buildings":
      return boundary(p, t, language);
    case "max_footprint_ratio":
      return `≤ ${percent(p.ratio, language)}`;
    case "max_height":
      return join([
        p.eave_m != null && `${t("rules.value.eave")} ≤ ${metres(p.eave_m, language)}`,
        p.ridge_m != null && `${t("rules.value.ridge")} ≤ ${metres(p.ridge_m, language)}`,
        p.parapet_m != null && `${t("rules.value.parapet")} ≤ ${metres(p.parapet_m, language)}`,
        p.storeys ? String(p.storeys) : null,
        p.reference === "street_level" && t("rules.value.streetLevel"),
        p.measured_at === "mean" && t("rules.value.mean"),
        p.includes_roof_installations === true && t("rules.value.roofInstallations"),
      ]);
    case "roof":
      return join([
        list(p.allowed_forms, t, "rules.roofForm"),
        (p.pitch_min_deg != null || p.pitch_max_deg != null) &&
          `${p.pitch_min_deg != null ? num(p.pitch_min_deg, language) : "…"}–${p.pitch_max_deg != null ? num(p.pitch_max_deg, language) : "…"}°`,
        p.flat_roof ? t(`rules.flatRoof.${String(p.flat_roof)}`) : null,
        p.ridge_orientation === "parallel_to_street" && t("rules.value.ridgeParallel"),
        p.ridge_orientation === "perpendicular_to_street" && t("rules.value.ridgePerpendicular"),
        Array.isArray(p.materials_allowed) &&
          p.materials_allowed.length > 0 &&
          t("rules.value.roofMaterials", { value: list(p.materials_allowed, t, "rules.material") }),
      ]);
    case "facade":
      return join([
        list(p.materials_allowed, t, "rules.material"),
        Array.isArray(p.materials_forbidden) &&
          p.materials_forbidden.length > 0 &&
          t("rules.value.notMaterials", { value: list(p.materials_forbidden, t, "rules.material") }),
        list(p.color_families_allowed, t, "rules.color"),
      ]);
    case "unsealed_min":
      return join([
        p.ratio != null && `≥ ${percent(p.ratio, language)}`,
        p.full_soil_ratio != null && t("rules.value.fullSoil", { value: percent(p.full_soil_ratio, language) }),
        typeof p.counting === "string" && p.counting,
      ]);
    case "parking":
      return join([
        p.spaces_per_dwelling != null && t("rules.value.spacesPerDwelling", { value: num(p.spaces_per_dwelling, language) }),
        p.spaces_per_m2_sdp != null && t("rules.value.spacesPerArea", { area: num(1 / Number(p.spaces_per_m2_sdp), language, 0) }),
        typeof p.min_dimensions === "string" && t("rules.value.minDimensions", { value: p.min_dimensions }),
      ]);
    case "annex":
      return join([
        p.max_footprint_m2 != null && `≤ ${num(p.max_footprint_m2, language)} m²`,
        p.max_height_m != null && `${t("rules.value.height")} ≤ ${metres(p.max_height_m, language)}`,
      ]);
    case "planting":
      return join([
        p.min_green_ratio != null && `≥ ${percent(p.min_green_ratio, language)}`,
        p.trees_per_m2 != null && t("rules.value.trees", { value: num(Number(p.trees_per_m2) * 100, language) }),
      ]);
    case "fence":
      return join([p.max_height_m != null && `≤ ${metres(p.max_height_m, language)}`, list(p.materials, t, "rules.material")]);
    case "max_area":
      return join([
        p.sdp_m2 != null && t("rules.value.sdpMax", { value: num(p.sdp_m2, language, 0) }),
        p.footprint_m2 != null && t("rules.value.footprintMax", { value: num(p.footprint_m2, language, 0) }),
      ]);
    default:
      return String(p.summary ?? "");
  }
}

/** Wert einer wirksamen Regel; für andere Status der Grund (`unknown`) oder „nicht geregelt“. */
export function ruleValue(rule: RuleOut, t: TFunction, language: string): string {
  if (rule.status === "not_regulated") return t("rules.status.not_regulated");
  if (rule.status === "unknown") return t(`rules.reason.${rule.reason ?? "missing"}`, { defaultValue: t("rules.status.unknown") });
  return values(rule, t, language) || t("rules.status.effective");
}
