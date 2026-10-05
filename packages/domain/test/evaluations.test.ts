// Die Antworten des Kerns, mit denen die Python-Tests des Kundenwegs `engine` ersetzen (HM4), entsprechen dem
// aktuellen Kern. Schlägt der Test fehl: `pnpm run evaluations` und die Python-Tests erneut laufen lassen.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { evaluations, FIXTURE } from "../scripts/evaluations.ts";
import { catalog, template } from "./demo-house.ts";

it("evaluations.json ist auf dem Stand des Kerns", () => {
  const stored: unknown = JSON.parse(readFileSync(resolve(FIXTURE, "evaluations.json"), "utf8"));
  expect(stored).toEqual(evaluations(template, catalog));
});
