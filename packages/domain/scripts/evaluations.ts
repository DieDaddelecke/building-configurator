/// <reference types="node" />
// Ergebnisse des Kerns für die Python-Tests des Kundenwegs (HM4, HM5): Dort steht der Dienst `engine` als
// `MockTransport`, der diese Antworten nach Haustyp und Auswahl gibt (backend/tests/house_support.py). Neu
// schreiben mit
//   pnpm run evaluations
// `test/evaluations.test.ts` hält die Datei aktuell: Ändert sich der Kern, schlägt er fehl.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluate, type HouseCatalog, type HouseConfiguration, type HouseEvaluation, type HouseTemplate } from "../src/index.ts";

export interface EvaluationCase {
  /** Slug des Haustyps. */
  readonly template: string;
  readonly configuration: HouseConfiguration;
  readonly evaluation: HouseEvaluation;
}

/** Testdaten der Haustypen: das Demohaus (P 19) und das zweigeschossige mit Satteldach (HM5). */
export type Templates = Readonly<Record<"template" | "template-r1", HouseTemplate>>;

function select(values: Record<string, string | number>): HouseConfiguration {
  const value = (v: string | number) => (typeof v === "number" ? { type: "number" as const, value: v } : { type: "option" as const, option_value_id: v });
  return {
    selections: Object.fromEntries(Object.entries(values).map(([slot, v]) => [slot, { value: value(v), room_overrides: {}, element_overrides: {} }])),
  };
}

/** Standards, Ziegel- und Holzfassade (P 19.6/19.7), das Gründach und Terrasse mit Carport; das R+1 mit den
 * Dachformen, die die PLU-Prüfung verschieden behandelt (eindeutig, Lesarten, mehrere Neigungen), und mit gedrehtem
 * First. */
export const CASES: Readonly<Record<string, readonly [keyof Templates, HouseConfiguration]>> = {
  standard: ["template", select({})],
  brick: ["template", select({ wall_profile: "wall.brick" })],
  wood: ["template", select({ wall_profile: "wall.wood" })],
  green_roof: ["template", select({ roof_type: "roof.green" })],
  outbuildings: ["template", select({ terrace: "terrace.wood", carport: "carport.single" })],
  r1_standard: ["template-r1", select({})],
  r1_hip: ["template-r1", select({ roof_shape: "shape.hip" })],
  r1_half_hip: ["template-r1", select({ roof_shape: "shape.half_hip" })],
  r1_mansard: ["template-r1", select({ roof_shape: "shape.mansard" })],
  r1_turned: ["template-r1", select({ roof_rotation: 90 })],
};

export function evaluations(templates: Templates, catalog: HouseCatalog): Record<string, EvaluationCase> {
  return Object.fromEntries(
    Object.entries(CASES).map(([name, [key, configuration]]) => {
      const template = templates[key];
      return [name, { template: template.slug, configuration, evaluation: evaluate({ template, catalog, configuration }) }];
    }),
  );
}

export const FIXTURE = fileURLToPath(new URL("../test/fixtures/demo-house", import.meta.url));

if (import.meta.main) {
  const load = <T>(file: string) => JSON.parse(readFileSync(resolve(FIXTURE, file), "utf8")) as T;
  const templates = { template: load<HouseTemplate>("template.json"), "template-r1": load<HouseTemplate>("template-r1.json") };
  const result = evaluations(templates, load<HouseCatalog>("catalog.json"));
  writeFileSync(resolve(FIXTURE, "evaluations.json"), `${JSON.stringify(result, null, 2)}\n`);
  console.log(`evaluations.json: ${Object.keys(result).join(", ")}`);
}
