/** Texte der Prüfungen und Kennwerte des Konfigurators (Plan H2 4.4). Die API liefert nur stabile Codes. */

import type { TFunction } from "i18next";

import type { CheckOut, EdgeMeasureOut } from "../api/configuration";
import { formatNumber } from "../site/geo";

/** Kantenart und Nummer, z. B. „Straße (3)“. */
export function edgeName(kind: string, seq: number, t: TFunction): string {
  return t(`configurator.edge.${["street", "side", "rear"].includes(kind) ? kind : "other"}`, { seq });
}

function roofForms(value: string | number | null | undefined, t: TFunction): string {
  return String(value ?? "")
    .split(",")
    .filter(Boolean)
    .map((form) => t(`configurator.types.roof.${form}`, { defaultValue: form }))
    .join(", ");
}

/** Text einer Prüfung mit Messwert und Grenze. Unbekannte Codes erscheinen als Code, nie leer. */
export function checkText(check: CheckOut, t: TFunction, lng: string): string {
  const number = (value: string | number | null | undefined, digits = 2) =>
    typeof value === "number" ? formatNumber(value, lng, digits) : String(value ?? "");
  const isForm = check.code === "roof_form" || check.code === "roof_flat";
  const areas = check.code === "footprint";
  const orientation = typeof check.params?.orientation === "string" ? check.params.orientation : "";
  return t(`configurator.check.${check.code}`, {
    measured: isForm ? roofForms(check.measured, t) : number(check.measured, areas ? 1 : 2),
    limit: isForm ? roofForms(check.limit, t) : number(check.limit, areas ? 1 : 2),
    orientation: orientation ? t(`configurator.orientation.${orientation}`, { defaultValue: orientation }) : "",
    reason: check.reason ? t(`configurator.reason.${check.reason}`, { defaultValue: check.reason }) : "",
    defaultValue: check.code,
  });
}

/** Abstand einer Kante: gemessen und gefordert. */
export function requiredText(edge: EdgeMeasureOut, t: TFunction, lng: string): string {
  if (edge.on_boundary) return t("configurator.placement.onBoundary");
  if (edge.required_m == null) return t("configurator.placement.unknownRule");
  return `${formatNumber(edge.required_m, lng, 2)} m`;
}

export const STATUS_TONE: Record<CheckOut["status"], string> = {
  pass: "t-ink",
  fail: "t-alert",
  hint: "t-warn",
  unknown: "t-warn",
  not_applicable: "t-mute",
};

/** Verstöße zuerst, dann Hinweise und Unbekanntes, dann Bestandenes. */
export function sortChecks(checks: readonly CheckOut[]): CheckOut[] {
  const order: Record<CheckOut["status"], number> = { fail: 0, unknown: 1, hint: 2, not_applicable: 3, pass: 4 };
  return [...checks].sort((a, b) => order[a.status] - order[b.status]);
}
