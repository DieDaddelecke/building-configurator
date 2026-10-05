/// <reference types="node" />
// Eingefrorene Testdaten des Demohauses (P 19): nur zusammen mit den Erwartungswerten in P 19.7/20 ändern. Dazu das
// zweigeschossige Demohaus mit Satteldach (HM5); seine Erwartungswerte stehen von Hand gerechnet in storeys.test.ts.
import { readFileSync } from "node:fs";
import type { HouseCatalog, HouseConfiguration, HouseSlotSelection, HouseSlotValue, HouseTemplate } from "../src/index.ts";

function load<T>(name: string): T {
  return JSON.parse(readFileSync(new URL(`./fixtures/demo-house/${name}.json`, import.meta.url), "utf8")) as T;
}

export const template = load<HouseTemplate>("template");
export const templateR1 = load<HouseTemplate>("template-r1");
export const catalog = load<HouseCatalog>("catalog");

/** Auswahl aus globalen Werten (Option oder Zahl) und Überschreibungen. */
export function configuration(
  selections: Record<string, { value?: string | number; rooms?: Record<string, string>; elements?: Record<string, string> }> = {},
): HouseConfiguration {
  const option = (id: string) => ({ type: "option" as const, option_value_id: id });
  const value = (v: string | number): HouseSlotValue => (typeof v === "number" ? { type: "number", value: v } : option(v));
  const map = (values: Record<string, string> = {}) => Object.fromEntries(Object.entries(values).map(([k, v]) => [k, option(v)]));
  return {
    selections: Object.fromEntries(
      Object.entries(selections).map(([slot, s]): [string, HouseSlotSelection] => [
        slot,
        { value: s.value === undefined ? null : value(s.value), room_overrides: map(s.rooms), element_overrides: map(s.elements) },
      ]),
    ),
  };
}
