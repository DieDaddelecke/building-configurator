/** Fehler und Gründe zu Reglements in Worten des Büros; gemeinsam für Bebauungsplan, Zusatzdokumente und Scan (AN7). */

import type { TFunction } from "i18next";

import { ApiError } from "../api/client";

export function fehlerText(t: TFunction, error: unknown, prefix = "analyse.plu"): string | null {
  if (!error) return null;
  const code = error instanceof ApiError ? error.problem.code : "";
  // Weitere Felder des Problems (etwa `remaining` beim Scan-Kontingent, AN6) stehen dem Text zur Verfügung
  const werte = error instanceof ApiError ? { ...error.problem } : {};
  return t([`${prefix}.error.${code}`, `analyse.plu.error.${code}`, "error.generic"], werte);
}

/** Grund eines gescheiterten Lesens, einer gescheiterten Texterkennung oder Auswertung. */
export function grund(t: TFunction, reason: string | null): string {
  if (!reason) return "";
  if (reason.startsWith("interrupted")) return t("analyse.plu.error.interrupted");
  return t([`analyse.plu.reason.${reason}`, `analyse.plu.error.${reason}`, "analyse.plu.reason.other"], { reason });
}
