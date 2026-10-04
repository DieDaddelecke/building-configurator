import { readFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import type { HouseCatalog, HouseCompatibility, HouseEvaluation, HouseTemplate } from "@emprise/domain";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createHandler } from "./app.ts";

let server: Server;
let base: string;

beforeAll(async () => {
  vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  const handler = createHandler({ release: "test" });
  server = createServer((req, res) => void handler(req, res));
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  await new Promise((resolve) => server.close(resolve));
  vi.restoreAllMocks();
});

// Testdaten des Kerns (P 19)
const load = <T>(name: string) =>
  JSON.parse(readFileSync(new URL(`../../packages/domain/test/fixtures/demo-house/${name}.json`, import.meta.url), "utf8")) as T;
const template = load<HouseTemplate>("template");
const catalog = load<HouseCatalog>("catalog");
const brick = { selections: { wall_profile: { value: { type: "option", option_value_id: "wall.brick" }, room_overrides: {}, element_overrides: {} } } };

const post = (path: string, body: unknown) =>
  fetch(`${base}${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: typeof body === "string" ? body : JSON.stringify(body) });

describe("engine", () => {
  it("meldet sich gesund mit Stand des Kerns", async () => {
    const res = await fetch(`${base}/health`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", domain: expect.any(String), release: "test" });
  });

  it("rechnet das Demohaus mit Aufpreis und Kandidaten", async () => {
    const res = await post("/evaluate", { template, catalog, configuration: brick, candidates: { slot_id: "window_type", element_id: null } });
    expect(res.status).toBe(200);
    const body = (await res.json()) as HouseEvaluation;
    expect(body.status).toBe("valid");
    expect(body.price.deltas.wall_profile).toBeCloseTo(6961.12, 6);
    expect(body.candidates?.find((c) => c.option_value_id === "window.floor_length")).toMatchObject({ available_count: 5, target_count: 6 });
  });

  it("rechnet ohne Kandidaten", async () => {
    const res = await post("/evaluate", { template, catalog, configuration: { selections: {} } });
    expect(res.status).toBe(200);
    expect(((await res.json()) as HouseEvaluation).candidates).toBeNull();
  });

  it("prüft die Kompatibilität", async () => {
    const res = await post("/compatibility", { template, catalog });
    expect(res.status).toBe(200);
    expect((await res.json()) as HouseCompatibility).toEqual({ domain_version: expect.any(String), supported: true, issues: [] });
    const missing = { ...catalog, price_entries: catalog.price_entries.filter((e) => e.id !== "price.roof.green") };
    const broken = (await (await post("/compatibility", { template, catalog: missing })).json()) as HouseCompatibility;
    expect(broken.supported).toBe(false);
  });

  it.each([
    ["kein JSON", "/evaluate", "{", 400, "invalid_json"],
    ["falsche Form", "/evaluate", { template: "x" }, 400, "invalid_request"],
    ["ohne Auswahl", "/evaluate", { template, catalog }, 400, "invalid_request"],
    ["Kandidaten ohne Slot", "/evaluate", { template, catalog, configuration: brick, candidates: {} }, 400, "invalid_request"],
    ["andere Schemaversion", "/compatibility", { template: { ...template, schema_version: 2 }, catalog }, 400, "schema_version_unsupported"],
  ])("lehnt ab: %s", async (_name, path, body, status, code) => {
    const res = await post(path, body);
    expect(res.status).toBe(status);
    expect(await res.json()).toEqual({ code, detail: {} });
  });

  it("meldet Fehler des Kerns als 422 mit Code", async () => {
    const unknown = { selections: { wall_profile: { value: { type: "option", option_value_id: "wall.glass" }, room_overrides: {}, element_overrides: {} } } };
    const res = await post("/evaluate", { template, catalog, configuration: unknown });
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({ code: "option_unknown", detail: { slot: "wall_profile", option: "wall.glass" } });
  });

  it.each([
    ["Schleife", [[0, 0], [10, 10], [10, 0], [0, 10]]],
    // Rücklauf auf einer Linie: clipper2-ts liefe hier endlos (Spike HM0)
    ["Rücklauf", [[0, 0], [10, 0], [9, 0], [8.9, 0.5], [1.1, 0.5], [1, 0], [0.5, 0]]],
  ])("meldet eine nicht einfache Hülle als 422: %s", async (_name, points) => {
    const loop = template.envelope[0]!;
    const ring = points.map(([x, y]) => ({ x: x!, y: y! }));
    const envelope = [{ ...loop, inner_polygon: ring, segments: ring.map((_, i) => ({ id: `seg-${i}`, source_ifc_guid: null, facade_role: null })) }];
    const res = await post("/evaluate", { template: { ...template, envelope, openings: [] }, catalog, configuration: { selections: {} } });
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({ code: "envelope_invalid", detail: { defect: "self_intersecting" } });
  });

  it("lehnt große Anfragen und fremde Wege ab", async () => {
    expect((await post("/evaluate", "x".repeat(4_100_000))).status).toBe(413);
    expect((await fetch(`${base}/nope`)).status).toBe(404);
    expect((await fetch(`${base}/evaluate`)).status).toBe(405);
    expect((await fetch(`${base}/constructor`)).status).toBe(404);
  });
});
