/// <reference types="node" />
// Szenarien des Demohauses (P 19.7) aus dem Rechenkern, als Markdown-Tabelle:
//   pnpm run scenarios              Test-Fixture (test/fixtures/demo-house)
//   pnpm run scenarios seed/demo-house
// Die Grundstückszeilen rechnet Python ab HM4 (E-HM-4); den Dachaufbau in 3D zeigt die Oberfläche ab HM2.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  deriveModel,
  evaluate,
  type HouseCatalog,
  type HouseConfiguration,
  type HouseEvaluation,
  type HousePoint,
  type HouseTemplate,
} from "../src/index.ts";

export interface Scenario {
  readonly name: string;
  readonly result: string;
}

const de = (digits: number) => new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const number = (value: number, digits = 2) => (value < 0 ? "−" : "") + de(digits).format(Math.abs(value));
const signed = (value: number, digits = 2) => (value < 0 ? "" : "+") + number(value, digits);
const euro = (value: number) => `${number(value, Number.isInteger(Math.round(value * 100) / 100) ? 0 : 2)} €`;
const delta = (value: number) => (value < 0 ? "" : "+") + euro(value);

function size(points: readonly HousePoint[]): string {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  return `${number(Math.max(...ys) - Math.min(...ys))} × ${number(Math.max(...xs) - Math.min(...xs))}`;
}

function select(values: Record<string, string>): HouseConfiguration {
  return {
    selections: Object.fromEntries(
      Object.entries(values).map(([slot, id]) => [slot, { value: { type: "option" as const, option_value_id: id }, room_overrides: {}, element_overrides: {} }]),
    ),
  };
}

function quantity(evaluation: HouseEvaluation, key: string): number | null {
  const found = evaluation.quantities.filter((q) => q.key === key);
  return found.length ? found.reduce((sum, q) => sum + q.value, 0) : null;
}

function rule(evaluation: HouseEvaluation, id: string): number {
  return evaluation.price.items.filter((i) => i.pricing_rule_id === id).reduce((sum, i) => sum + i.amount, 0);
}

export function scenarios(template: HouseTemplate, catalog: HouseCatalog): Scenario[] {
  const run = (configuration: HouseConfiguration) => ({
    evaluation: evaluate({ template, catalog, configuration }),
    model: deriveModel({ template, catalog, configuration }),
  });
  const base = run(select({}));
  const inner = (model: typeof base.model) => model.loops[0]!.reference.map((p) => ({ x: p.x / 10_000, y: p.y / 10_000 }));
  const name = (optionId: string) => catalog.option_values.find((o) => o.id === optionId)!.name.de;
  const rows: Scenario[] = [
    {
      name: "Ausgangszustand",
      result: `Innen ${size(inner(base.model))}; außen ${size(base.evaluation.facts.facade_outline)} m; Netto ${euro(base.evaluation.price.net_amount)}`,
    },
  ];

  for (const [label, option] of [
    ["Ziegelfassade", "wall.brick"],
    ["Holzfassade", "wall.wood"],
  ] as const) {
    const { evaluation, model } = run(select({ wall_profile: option }));
    const parts = [
      JSON.stringify(model.loops[0]!.reference) === JSON.stringify(base.model.loops[0]!.reference) ? "Innen unverändert" : "Innen GEÄNDERT",
      `außen ${size(evaluation.facts.facade_outline)} m`,
      `Wand ${number(model.loops[0]!.wallThickness / 100, 0)} cm`,
    ];
    const bearing = evaluation.price.items.find((i) => i.pricing_rule_id === "bearing");
    const total = evaluation.price.net_amount - base.evaluation.price.net_amount;
    if (bearing) {
      parts.push(
        `Fassadenschichten ${delta(rule(evaluation, "wall_layers") - rule(base.evaluation, "wall_layers"))}, ` +
          `Auflager ${number(bearing.quantity)} m × ${euro(bearing.unit_price)} = ${signed(bearing.amount)} €, gesamt ${delta(total)}`,
      );
    } else {
      parts.push(delta(total), "kein Auflager");
    }
    parts.push(`Laibungsfläche ${number(quantity(evaluation, "reveal.area") ?? 0, 3)} m²`);
    rows.push({ name: label, result: parts.join("; ") });
  }

  {
    const configuration = select({ window_type: "window.floor_length" });
    const before = JSON.stringify(configuration);
    const { evaluation, model } = run(configuration);
    const windows = evaluation.resolved.filter((r) => r.slot_id === "window_type");
    const effective = windows.filter((r) => r.option_value_id === "window.floor_length").length;
    const notes = evaluation.notes.map((note) => {
      const opening = template.openings.find((o) => o.id === note.element_id)!;
      const room = template.rooms.find((r) => r.id === opening.adjacent_room_ids[0]);
      const type = catalog.room_types.find((t) => t.id === room?.room_type_id);
      return `${type?.name.de ?? note.element_id}-Fenster ${name(note.applied_value_id)} mit \`ResolutionNote\``;
    });
    const positions = (m: typeof model) => JSON.stringify(m.openings.map((o) => [o.id, o.center]));
    rows.push({
      name: "Bodentief global (Standardfassade)",
      result: [
        JSON.stringify(configuration) === before ? `Auswahl bleibt global „${name("window.floor_length")}“` : "Auswahl GEÄNDERT",
        `effektiv ${effective} Fenster bodentief, ${notes.join(", ")}`,
        `Status \`${evaluation.status}\``,
        positions(model) === positions(base.model) ? "Fensterpositionen unverändert" : "Fensterpositionen GEÄNDERT",
        `Fenster ${delta(rule(evaluation, "windows") - rule(base.evaluation, "windows"))}, ` +
          `Wand ${delta(rule(evaluation, "wall_layers") - rule(base.evaluation, "wall_layers"))}, ` +
          `gesamt ${delta(evaluation.price.net_amount - base.evaluation.price.net_amount)}`,
      ].join("; "),
    });
  }

  {
    const { evaluation, model } = run(select({ roof_type: "roof.green" }));
    rows.push({
      name: "Gründach",
      result:
        `Dachaufbau ${number(model.roof.buildUp / 10_000)} m; Dachfläche ${number(quantity(evaluation, "roof.area")!)} m²; ` +
        delta(evaluation.price.net_amount - base.evaluation.price.net_amount),
    });
  }
  return rows;
}

if (import.meta.main) {
  const directory = process.argv[2] ? resolve(process.argv[2]) : fileURLToPath(new URL("../test/fixtures/demo-house", import.meta.url));
  const load = <T>(file: string) => JSON.parse(readFileSync(resolve(directory, file), "utf8")) as T;
  const rows = scenarios(load<HouseTemplate>("template.json"), load<HouseCatalog>("catalog.json"));
  console.log("| Szenario | Ergebnis |\n|---|---|");
  for (const row of rows) console.log(`| ${row.name} | ${row.result} |`);
}
