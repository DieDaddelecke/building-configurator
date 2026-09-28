/**
 * Felder des Regelformulars (AN4, docs/PLAN_AN4_KORREKTUR.md 3.1): Umrechnung zwischen gespeicherten Parametern und
 * dem, was der Architekt eingibt. Die Beschreibung der Felder kommt vom Server (`GET /admin/rule-kinds`); hier nur die
 * Einheiten: Anteile als Prozent, Dichten als Kehrwert („1 je 50 m²“), Zahlen mit Komma. Zusammenhänge zwischen
 * Parametern prüft der Server.
 */

import type { ParamFieldOut } from "../api/rules";

export type Entwurf = Record<string, string | boolean | string[]>;
export type FeldFehler = Record<string, "required" | "number" | "range">;

/** Zahl aus einer Eingabe mit Komma oder Punkt; leer → `null`, unlesbar → `NaN`. */
export function parseZahl(text: string): number | null {
  const clean = text.trim().replace(/\s/g, "").replace(",", ".");
  if (clean === "") return null;
  return /^-?\d*\.?\d+$/.test(clean) ? Number(clean) : Number.NaN;
}

/** Gespeicherter Wert → angezeigte Zahl (Prozent, Kehrwert). */
function zurAnzeige(value: number, unit: ParamFieldOut["unit"]): number {
  if (unit === "share") return value * 100;
  if (unit === "per_area") return value > 0 ? 1 / value : value;
  return value;
}

/** Angezeigte Zahl → gespeicherter Wert. */
function zumSpeichern(value: number, unit: ParamFieldOut["unit"]): number {
  if (unit === "share") return value / 100;
  if (unit === "per_area") return value > 0 ? 1 / value : value;
  return value;
}

/** Ohne Gleitkommareste (0,07 × 100 = 7,000000000000001) und mit dem Dezimalzeichen der Sprache. */
export function zahlText(value: number, language: string): string {
  const rounded = Number(value.toFixed(6));
  return new Intl.NumberFormat(language === "de" ? "de-DE" : "fr-FR", { maximumFractionDigits: 4, useGrouping: false }).format(
    rounded,
  );
}

export function entwurfAus(fields: ParamFieldOut[], params: Record<string, unknown>, language: string): Entwurf {
  const draft: Entwurf = {};
  for (const field of fields) {
    const value = params[field.name] ?? field.default;
    if (field.type === "flag") draft[field.name] = Boolean(value);
    else if (field.type === "items") draft[field.name] = Array.isArray(value) ? value.map(String) : [];
    else if (field.type === "number") {
      draft[field.name] = typeof value === "number" ? zahlText(zurAnzeige(value, field.unit), language) : "";
    } else draft[field.name] = value == null ? "" : String(value);
  }
  return draft;
}

/** Parameter aus dem Entwurf: leere Felder entfallen (der Server setzt Vorgaben), Zahlen in gespeicherter Einheit. */
export function parameterAus(fields: ParamFieldOut[], draft: Entwurf): { params: Record<string, unknown>; errors: FeldFehler } {
  const params: Record<string, unknown> = {};
  const errors: FeldFehler = {};
  for (const field of fields) {
    const value = draft[field.name];
    if (field.type === "flag") {
      params[field.name] = Boolean(value);
    } else if (field.type === "items") {
      if (Array.isArray(value) && value.length > 0) params[field.name] = value;
    } else if (field.type === "number") {
      const parsed = parseZahl(typeof value === "string" ? value : "");
      if (parsed === null) {
        if (field.required) errors[field.name] = "required";
      } else if (Number.isNaN(parsed)) {
        errors[field.name] = "number";
      } else {
        const stored = Number(zumSpeichern(parsed, field.unit).toFixed(6));
        if ((field.min != null && stored < field.min) || (field.max != null && stored > field.max)) errors[field.name] = "range";
        else params[field.name] = stored;
      }
    } else {
      const text = typeof value === "string" ? value.trim() : "";
      if (text) params[field.name] = text;
      else if (field.required) errors[field.name] = "required";
    }
  }
  return { params, errors };
}

/** Grenzen eines Zahlenfelds in der Einheit der Eingabe (Prozent, Kehrwert: Grenzen vertauscht). */
export function grenzen(field: ParamFieldOut): [number | null, number | null] {
  const low = field.min ?? null;
  const high = field.max ?? null;
  if (field.unit === "per_area") {
    return [high != null && high > 0 ? 1 / high : null, low != null && low > 0 ? 1 / low : null];
  }
  return [low != null ? zurAnzeige(low, field.unit) : null, high != null ? zurAnzeige(high, field.unit) : null];
}

const OPTION_PREFIX: Record<string, string> = {
  height_basis: "rules.basis",
  allowed_forms: "rules.roofForm",
  flat_roof: "rules.flatRoof",
  materials_allowed: "rules.material",
  materials_forbidden: "rules.material",
  materials: "rules.material",
  color_families_allowed: "rules.color",
};

/** Übersetzungsschlüssel einer Auswahl: vorhandene Vokabulare (Dachform, Material …), sonst `rules.option.<Feld>.<Wert>`. */
export function optionKey(field: string, value: string): string {
  return `${OPTION_PREFIX[field] ?? `rules.option.${field}`}.${value}`;
}
