// Rechendienst (docs/PLAN_HAUSMODELL.md 3.3): ohne Zustand, nur im Compose-Netz erreichbar.
// /evaluate und /compatibility rechnen mit dem Kern, /roof baut ein geneigtes Dach für den IFC-Import (E-HM-64);
// /render (SVG) folgt mit HM2.
// Den Inhalt der Anfrage prüft die API mit Pydantic vor dem Aufruf, die Antwort danach (3.4, E-HM-36);
// hier nur die Hülle der Anfrage. Fachliche Fehler des Kerns antworten mit 422 und ihrem Code.
import type { IncomingMessage, ServerResponse } from "node:http";
import {
  checkCompatibility,
  DOMAIN_VERSION,
  evaluate,
  GeometryError,
  ModelError,
  roofGeometry,
  type HouseCompatibilityRequest,
  type HouseEvaluateRequest,
  type HouseRoofRequest,
} from "@emprise/domain";

/** Demohaus etwa 23 kB; ein echter Haustyp mit Katalog bleibt weit darunter. */
const MAX_BODY_BYTES = 4_000_000;

export interface EngineOptions {
  /** Release des Images (EMPRISE_RELEASE), wie beim Backend. */
  readonly release: string;
}

class RequestError extends Error {
  readonly status: number;

  constructor(status: number, code: string) {
    super(code);
    this.status = status;
  }
}

function send(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json", "content-length": Buffer.byteLength(text) });
  res.end(text);
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    size += (chunk as Buffer).length;
    if (size > MAX_BODY_BYTES) {
      throw new RequestError(413, "body_too_large");
    }
    chunks.push(chunk as Buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
  } catch {
    throw new RequestError(400, "invalid_json");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function documents(body: unknown): HouseCompatibilityRequest {
  if (!isRecord(body) || !isRecord(body.template) || !isRecord(body.catalog)) throw new RequestError(400, "invalid_request");
  if (body.template.schema_version !== 2 || body.catalog.schema_version !== 2) throw new RequestError(400, "schema_version_unsupported");
  return body as unknown as HouseCompatibilityRequest;
}

function evaluateRequest(body: unknown): HouseEvaluateRequest {
  const { template, catalog } = documents(body);
  const { configuration, candidates } = body as Record<string, unknown>;
  if (!isRecord(configuration) || !isRecord(configuration.selections)) throw new RequestError(400, "invalid_request");
  if (candidates !== undefined && candidates !== null && (!isRecord(candidates) || typeof candidates.slot_id !== "string")) {
    throw new RequestError(400, "invalid_request");
  }
  return { template, catalog, configuration, candidates: candidates ?? null } as HouseEvaluateRequest;
}

function roofRequest(body: unknown): HouseRoofRequest {
  if (!isRecord(body) || !Array.isArray(body.contour) || !isRecord(body.design)) throw new RequestError(400, "invalid_request");
  // Das Flachdach rechnet der Kern beim Auswerten; hier gibt es nur geneigte Dächer
  if (body.design.form === "flat") throw new RequestError(400, "invalid_request");
  return body as unknown as HouseRoofRequest;
}

function log(entry: Record<string, unknown>): void {
  process.stdout.write(`${JSON.stringify({ time: new Date().toISOString(), ...entry })}\n`);
}

const routes: Record<string, (body: unknown) => unknown> = {
  "/evaluate": (body) => evaluate(evaluateRequest(body)),
  "/compatibility": (body) => checkCompatibility(documents(body)),
  "/roof": (body) => roofGeometry(roofRequest(body)),
};

export function createHandler(options: EngineOptions) {
  return async function handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const started = performance.now();
    const path = new URL(req.url ?? "/", "http://engine").pathname;
    let status = 500;
    try {
      if (path === "/health") {
        if (req.method !== "GET") throw new RequestError(405, "method_not_allowed");
        status = 200;
        send(res, status, { status: "ok", domain: DOMAIN_VERSION, release: options.release });
        return;
      }
      const route = Object.hasOwn(routes, path) ? routes[path] : undefined;
      if (!route) throw new RequestError(404, "not_found");
      if (req.method !== "POST") throw new RequestError(405, "method_not_allowed");
      const result = route(await readJson(req));
      status = 200;
      send(res, status, result);
    } catch (error) {
      if (error instanceof RequestError) {
        status = error.status;
        send(res, status, { code: error.message, detail: {} });
      } else if (error instanceof ModelError) {
        status = 422;
        send(res, status, { code: error.code, detail: error.detail });
      } else if (error instanceof GeometryError) {
        status = 422;
        send(res, status, { code: error.code, detail: {} });
      } else {
        status = 500;
        log({ level: "error", path, error: String(error) });
        send(res, status, { code: "internal_error", detail: {} });
      }
    } finally {
      if (path !== "/health" || status !== 200) {
        log({ level: "info", method: req.method, path, status, ms: Math.round(performance.now() - started) });
      }
    }
  };
}
