/// <reference types="node" />
// Ergebnisse des Kerns für die Python-Tests des Kundenwegs (HM4): Dort steht der Dienst `engine` als
// `MockTransport`, der diese Antworten gibt (backend/tests/house_support.py). Neu schreiben mit
//   pnpm run evaluations
// `test/evaluations.test.ts` hält die Datei aktuell: Ändert sich der Kern, schlägt er fehl.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluate, type HouseCatalog, type HouseConfiguration, type HouseEvaluation, type HouseTemplate } from "../src/index.ts";

export interface EvaluationCase {
  readonly configuration: HouseConfiguration;
  readonly evaluation: HouseEvaluation;
}

function select(values: Record<string, string>): HouseConfiguration {
  return {
    selections: Object.fromEntries(
      Object.entries(values).map(([slot, id]) => [slot, { value: { type: "option" as const, option_value_id: id }, room_overrides: {}, element_overrides: {} }]),
    ),
  };
}

/** Standards, Ziegel- und Holzfassade (P 19.6/19.7) und das Gründach. */
export const CASES: Readonly<Record<string, HouseConfiguration>> = {
  standard: select({}),
  brick: select({ wall_profile: "wall.brick" }),
  wood: select({ wall_profile: "wall.wood" }),
  green_roof: select({ roof_type: "roof.green" }),
};

export function evaluations(template: HouseTemplate, catalog: HouseCatalog): Record<string, EvaluationCase> {
  return Object.fromEntries(
    Object.entries(CASES).map(([name, configuration]) => [name, { configuration, evaluation: evaluate({ template, catalog, configuration }) }]),
  );
}

export const FIXTURE = fileURLToPath(new URL("../test/fixtures/demo-house", import.meta.url));

if (import.meta.main) {
  const load = <T>(file: string) => JSON.parse(readFileSync(resolve(FIXTURE, file), "utf8")) as T;
  const result = evaluations(load<HouseTemplate>("template.json"), load<HouseCatalog>("catalog.json"));
  writeFileSync(resolve(FIXTURE, "evaluations.json"), `${JSON.stringify(result, null, 2)}\n`);
  console.log(`evaluations.json: ${Object.keys(result).join(", ")}`);
}
