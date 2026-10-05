/**
 * Kundenpreise des Hausmodells (docs/PLAN_HAUSMODELL.md 3.8, E-HM-2): brutto, gesamt auf 1.000 €, Aufpreise auf
 * 100 € gerundet, immer mit „ca.“. Dieselbe Rundung wie der Server (`backend/app/configuration/domain/outcomes.py`),
 * damit Browser und Server dieselbe Zahl zeigen.
 */

import type { HousePrice } from "@emprise/domain";

import { formatNumber } from "../site/geo";

export const GESAMT_STUFE = 1000;
export const AUFPREIS_STUFE = 100;

/** Kaufmännisch auf `step` Euro, symmetrisch zur Null: `sign(x)·⌊|x|/step + 0,5⌋·step`. */
export function rundeBetrag(value: number, step: number): number {
  const rounded = Math.floor(Math.abs(value) / step + 0.5) * step;
  return rounded === 0 ? 0 : Math.sign(value) * rounded;
}

/** Netto-Aufpreis als gerundeter Bruttobetrag. */
export function aufpreis(netDelta: number, vatRate: number): number {
  return rundeBetrag(netDelta * (1 + vatRate), AUFPREIS_STUFE);
}

export interface Kundenpreis {
  gesamt: number;
  /** Slot → Aufpreis der Wahl gegenüber dem Standard, brutto gerundet. */
  aufpreise: Record<string, number>;
}

/** Was der Kunde vom exakten Preis des Kerns sieht; gleich `price_out` im Server. */
export function kundenpreis(price: Pick<HousePrice, "gross_amount" | "vat_rate" | "deltas">): Kundenpreis {
  return {
    gesamt: rundeBetrag(price.gross_amount, GESAMT_STUFE),
    aufpreise: Object.fromEntries(Object.entries(price.deltas).map(([slot, delta]) => [slot, aufpreis(delta, price.vat_rate)])),
  };
}

/** Betrag in Euro ohne Nachkommastellen, z. B. „515.000 €“. */
export function euro(value: number, lng: string): string {
  return `${formatNumber(value, lng, 0)} €`;
}

/** Aufpreis mit Vorzeichen, z. B. „+8.400 €“; null ist kein Aufpreis. */
export function euroDelta(value: number, lng: string): string {
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${euro(Math.abs(value), lng)}`;
}
