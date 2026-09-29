/** Abstand je Grundstücksgrenze im Klartext (AN3, docs/PLAN_AN3_ANALYSE.md 3.5): aus dem Baurahmen, ohne
 *  eigenen Endpunkt. „auf der Grenze zulässig, sonst mindestens 3,00 m“, „H/2 an der Traufe, mindestens
 *  3,00 m – bei 7,00 m also 3,50 m“. Nicht ermittelte Werte bleiben „nicht ermittelt“, nie geschätzt. */

import type { TFunction } from "i18next";

import type { EnvelopeEdgeOut, PartOut } from "../api/envelope";
import type { components } from "../api/schema";
import { formatNumber } from "../site/geo";

type SetbackOut = components["schemas"]["SetbackOut"];
type HeightsOut = components["schemas"]["HeightsOut"];
type Params = Record<string, unknown>;

export interface Aussage {
  zone: string;
  kind: string;
  text: string;
  setback: SetbackOut;
}

const metres = (value: unknown, language: string) => `${formatNumber(Number(value), language, 2)} m`;

/** Faktor als Bruch, wie ihn Pläne schreiben: 0,5 → H/2, 1 → H, sonst 0,4 × H. */
function factorText(factor: number, language: string): string {
  if (Math.abs(factor - 1) < 1e-6) return "H";
  const inverse = 1 / factor;
  if (Math.abs(inverse - Math.round(inverse)) < 1e-6) return `H/${Math.round(inverse)}`;
  return `${formatNumber(factor, language, 2)} × H`;
}

/** Höhe zur Bezugsgröße wie in G3 (`Heights.for_basis`): Traufe, wenn genannt und bekannt, sonst die größte. */
function heightFor(heights: HeightsOut | undefined, basis: unknown): number | null {
  if (!heights) return null;
  if (basis === "eave" && heights.eave_m != null) return heights.eave_m;
  const known = [heights.ridge_m, heights.parapet_m, heights.eave_m].filter((v): v is number => v != null);
  return known.length ? Math.max(...known) : null;
}

function street(p: Params, t: TFunction, language: string): string {
  if (p.mode === "alignment") return t("analyse.distance.alignment");
  if (p.mode === "fixed") return t("analyse.distance.fixed", { value: metres(p.min_m, language) });
  if (p.mode === "range") {
    const key = p.band === "building" ? "rangeBuilding" : p.band === "facade" ? "rangeFacade" : "range";
    return t(`analyse.distance.${key}`, { min: metres(p.min_m, language), max: metres(p.max_m, language) });
  }
  return t("analyse.distance.min", { value: metres(p.min_m, language) });
}

function boundary(p: Params, heights: HeightsOut | undefined, t: TFunction, language: string): string {
  const parts: string[] = [];
  const factor = typeof p.height_factor === "number" ? p.height_factor : null;
  const minimum = typeof p.min_m === "number" ? p.min_m : null;
  if (factor != null) {
    const basis = t(`rules.basis.${String(p.height_basis)}`);
    let text = t("analyse.distance.factor", { factor: factorText(factor, language), basis });
    if (minimum != null) text += `, ${t("analyse.distance.atLeast", { value: metres(minimum, language) })}`;
    const height = heightFor(heights, p.height_basis);
    text +=
      height == null
        ? ` – ${t("analyse.distance.heightUnknown")}`
        : ` – ${t("analyse.distance.atHeight", {
            height: metres(height, language),
            value: metres(Math.max(minimum ?? 0, factor * height), language),
          })}`;
    parts.push(text);
  } else if (minimum != null) {
    parts.push(t("analyse.distance.min", { value: metres(minimum, language) }));
  }
  const rest = parts.join("");
  if (!p.allow_on_boundary) return rest;
  const onBoundary =
    typeof p.on_boundary_max_height_m === "number"
      ? t("analyse.distance.onBoundaryHeight", { value: metres(p.on_boundary_max_height_m, language) })
      : t("analyse.distance.onBoundary");
  return rest ? t("analyse.distance.otherwise", { first: onBoundary, second: rest }) : onBoundary;
}

export function statement(setback: SetbackOut, heights: HeightsOut | undefined, t: TFunction, language: string): string {
  if (setback.status === "not_regulated") return t("analyse.distance.notRegulated");
  if (setback.status !== "effective") return t("analyse.distance.unknown");
  const p = setback.params as Params;
  if (setback.kind === "setback_street") return street(p, t, language);
  return boundary(p, heights, t, language) || t("analyse.distance.unknown");
}

/** Aussagen einer Kante je Zone und Regel; eine Kante ohne Einordnung nennt beide Regeln (seitlich, hinten). */
export function aussagen(edge: EnvelopeEdgeOut, parts: PartOut[], t: TFunction, language: string): Aussage[] {
  const heights = new Map(parts.map((part) => [part.zone_code, part.heights]));
  return edge.setbacks.map((setback) => ({
    zone: setback.zone_code,
    kind: setback.kind,
    text: statement(setback, heights.get(setback.zone_code), t, language),
    setback,
  }));
}
