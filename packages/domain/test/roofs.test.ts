// Die Dächer, mit denen die Python-Tests des IFC-Imports `engine /roof` ersetzen (HM5), entsprechen dem aktuellen
// Kern. Schlägt der Test fehl: `pnpm run roofs` und die Python-Tests erneut laufen lassen.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { FIXTURE, roofs } from "../scripts/roofs.ts";

it("roofs.json ist auf dem Stand des Kerns", () => {
  const stored: unknown = JSON.parse(readFileSync(resolve(FIXTURE, "roofs.json"), "utf8"));
  expect(stored).toEqual(roofs());
});

it("jede Probe ist baubar, jede abgelehnte Drehung nennt ihren Grund", () => {
  const { probes, answers } = roofs();
  expect(probes).toHaveLength(14);
  for (const a of answers) expect(a.geometry === null).toBe(a.rejection !== null);
  // L-Grundriss: gedreht lägen zwei Giebel nebeneinander
  const turned = answers.filter((a) => a.rejection !== null).map((a) => [a.request.design.form, a.request.design.rotation, a.rejection!.detail.reason]);
  expect(turned).toEqual([
    ["gable", 90, "gables_adjacent"],
    ["half_hip", 90, "gables_adjacent"],
    ["mansard_gable", 90, "gables_adjacent"],
  ]);
});
