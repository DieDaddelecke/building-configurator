/** Werte einer Regel als kurzer Text (Spez. 5.2.4). Einheiten: Meter, Anteile 0–1, Grad. */

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

function boundary(p: Params, t: TFunction, language: string): string {
  const parts: string[] = [];
  if (p.min_m != null) parts.push(`≥ ${metres(p.min_m, language)}`);
  if (p.height_factor != null) {
    parts.push(t("rules.value.heightFactor", { factor: num(p.height_factor, language), basis: t(`rules.basis.${String(p.height_basis)}`) }));
  }
  let text = parts.join(" · ");
  if (p.allow_on_boundary) text = t("rules.value.orOnBoundary", { value: text });
  return text;
}

/** Wert einer wirksamen Regel; für andere Status der Grund (`unknown`) oder „nicht geregelt“. */
export function ruleValue(rule: RuleOut, t: TFunction, language: string): string {
  if (rule.status === "not_regulated") return t("rules.status.not_regulated");
  if (rule.status === "unknown") return t(`rules.reason.${rule.reason ?? "missing"}`, { defaultValue: t("rules.status.unknown") });
  const p = rule.params as Params;
  switch (rule.kind) {
    case "setback_street":
      if (p.mode === "alignment") return t("rules.value.alignment");
      if (p.mode === "range") return t("rules.value.range", { min: num(p.min_m, language), max: metres(p.max_m, language) });
      if (p.mode === "fixed") return t("rules.value.fixed", { value: metres(p.min_m, language) });
      return `≥ ${metres(p.min_m, language)}`;
    case "setback_side":
    case "setback_rear":
    case "setback_between_buildings":
      return boundary(p, t, language);
    case "max_footprint_ratio":
      return `≤ ${percent(p.ratio, language)}`;
    case "max_height":
      return [
        p.eave_m != null ? `${t("rules.value.eave")} ≤ ${metres(p.eave_m, language)}` : null,
        p.ridge_m != null ? `${t("rules.value.ridge")} ≤ ${metres(p.ridge_m, language)}` : null,
        p.parapet_m != null ? `${t("rules.value.parapet")} ≤ ${metres(p.parapet_m, language)}` : null,
        p.storeys ? String(p.storeys) : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "roof":
      return [
        list(p.allowed_forms, t, "rules.roofForm"),
        p.pitch_min_deg != null || p.pitch_max_deg != null
          ? `${p.pitch_min_deg != null ? num(p.pitch_min_deg, language) : "…"}–${p.pitch_max_deg != null ? num(p.pitch_max_deg, language) : "…"}°`
          : null,
        p.flat_roof ? t(`rules.flatRoof.${String(p.flat_roof)}`) : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "facade":
      return [list(p.materials_allowed, t, "rules.material"), list(p.color_families_allowed, t, "rules.color")].filter(Boolean).join(" · ");
    case "unsealed_min":
      return [p.ratio != null ? `≥ ${percent(p.ratio, language)}` : null, p.full_soil_ratio != null ? t("rules.value.fullSoil", { value: percent(p.full_soil_ratio, language) }) : null]
        .filter(Boolean)
        .join(" · ");
    case "parking":
      return p.spaces_per_dwelling != null
        ? t("rules.value.spacesPerDwelling", { value: num(p.spaces_per_dwelling, language) })
        : t("rules.value.spacesPerArea", { area: num(1 / Number(p.spaces_per_m2_sdp), language, 0) });
    case "annex":
      return [
        p.max_footprint_m2 != null ? `≤ ${num(p.max_footprint_m2, language)} m²` : null,
        p.max_height_m != null ? `${t("rules.value.height")} ≤ ${metres(p.max_height_m, language)}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "planting":
      return p.min_green_ratio != null ? `≥ ${percent(p.min_green_ratio, language)}` : t("rules.value.trees", { value: num(Number(p.trees_per_m2) * 100, language) });
    case "fence":
      return p.max_height_m != null ? `≤ ${metres(p.max_height_m, language)}` : list(p.materials, t, "rules.material");
    default:
      return String(p.summary ?? "");
  }
}
