// Ausgabe von `pnpm run scenarios` gleich P 19.7 (Abnahme HM1). Abweichungen im Wortlaut: Holz nennt zusätzlich
// Innenmaß und Wanddicke; statt „Dachaufbau in 3D sichtbar“ (HM2) die Dicke des Aufbaus. Grundstück ab HM4.
import { expect, it } from "vitest";
import { scenarios } from "../scripts/scenarios.ts";
import { catalog, template } from "./demo-house.ts";

it("Szenarien des Demohauses wie P 19.7", () => {
  expect(scenarios(template, catalog)).toEqual([
    { name: "Ausgangszustand", result: "Innen 8,00 × 12,00; außen 8,72 × 12,72 m; Netto 429.328,51 €" },
    {
      name: "Ziegelfassade",
      result:
        "Innen unverändert; außen 8,96 × 12,96 m; Wand 48 cm; Fassadenschichten +5.002,72 €, Auflager 43,52 m × 45 € = +1.958,40 €, " +
        "gesamt +6.961,12 €; Laibungsfläche 3,792 m²",
    },
    { name: "Holzfassade", result: "Innen unverändert; außen 8,88 × 12,88 m; Wand 44 cm; +8.118,22 €; kein Auflager; Laibungsfläche 2,528 m²" },
    {
      name: "Bodentief global (Standardfassade)",
      result:
        "Auswahl bleibt global „Bodentief“; effektiv 5 Fenster bodentief, Bad-Fenster Standard mit `ResolutionNote`; Status `valid`; " +
        "Fensterpositionen unverändert; Fenster +2.000 €, Wand −648 €, gesamt +1.352 €",
    },
    { name: "Gründach", result: "Dachaufbau 0,28 m; Dachfläche 110,92 m²; +8.873,47 €" },
  ]);
});
