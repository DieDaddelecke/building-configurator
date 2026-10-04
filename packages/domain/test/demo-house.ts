/// <reference types="node" />
// Eingefrorene Testdaten des Demohauses (P 19): nur zusammen mit den Erwartungswerten in P 19.7/20 ändern.
import { readFileSync } from "node:fs";
import type { HouseCatalog, HouseConfiguration, HouseSlotSelection, HouseTemplate } from "../src/index.ts";

function load<T>(name: string): T {
  return JSON.parse(readFileSync(new URL(`./fixtures/demo-house/${name}.json`, import.meta.url), "utf8")) as T;
}

export const template = load<HouseTemplate>("template");
export const catalog = load<HouseCatalog>("catalog");

/** Auswahl aus globalen Werten und Überschreibungen. */
export function configuration(
  selections: Record<string, { value?: string; rooms?: Record<string, string>; elements?: Record<string, string> }> = {},
): HouseConfiguration {
  const option = (id: string) => ({ type: "option" as const, option_value_id: id });
  const map = (values: Record<string, string> = {}) => Object.fromEntries(Object.entries(values).map(([k, v]) => [k, option(v)]));
  return {
    selections: Object.fromEntries(
      Object.entries(selections).map(([slot, s]): [string, HouseSlotSelection] => [
        slot,
        { value: s.value ? option(s.value) : null, room_overrides: map(s.rooms), element_overrides: map(s.elements) },
      ]),
    ),
  };
}
