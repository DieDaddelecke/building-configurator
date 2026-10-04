/// <reference types="node" />
// Erzeugt src/contract.gen.ts aus backend/openapi.json (docs/PLAN_HAUSMODELL.md 3.4, E-HM-29): nur die Wurzeln
// aus `x-house-contract` und was sie referenzieren, mit demselben Werkzeug wie `pnpm run api:types` im Frontend.
import { readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const source = new URL("../../../backend/openapi.json", import.meta.url);
const target = new URL("../src/contract.gen.ts", import.meta.url);

interface Spec {
  info: { version: string };
  components: { schemas: Record<string, unknown> };
  "x-house-contract": string[];
}

const spec = JSON.parse(readFileSync(source, "utf8")) as Spec;
const schemas = spec.components.schemas;
const keep = new Set<string>();

function references(node: unknown, found: string[] = []): string[] {
  if (Array.isArray(node)) {
    node.forEach((item) => references(item, found));
  } else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      if (key === "$ref" && typeof value === "string") {
        found.push(value.replace("#/components/schemas/", ""));
      } else {
        references(value, found);
      }
    }
  }
  return found;
}

function visit(name: string): void {
  if (keep.has(name)) return;
  if (!(name in schemas)) throw new Error(`Schema ${name} fehlt in openapi.json`);
  keep.add(name);
  references(schemas[name]).forEach(visit);
}

spec["x-house-contract"].forEach(visit);

const document = {
  openapi: "3.1.0",
  info: { title: "Vertrag Hausmodell", version: spec.info.version },
  paths: {},
  components: { schemas: Object.fromEntries([...keep].sort().map((name) => [name, schemas[name]])) },
};
const ast = await openapiTS(document as Parameters<typeof openapiTS>[0], {
  immutable: true,
  rootTypes: true,
  rootTypesNoSchemaPrefix: true,
});
const header =
  "// Erzeugt von scripts/contract-types.ts aus backend/openapi.json; nicht von Hand ändern.\n" +
  "// Quelle: backend/app/house/contract.py (docs/PLAN_HAUSMODELL.md 3.4).\n";
writeFileSync(target, header + astToString(ast));
