/// <reference types="node" />
// Dächer des Kerns für die Python-Tests des IFC-Imports (HM5, E-HM-65): Je Probe schreibt
// `backend/tests/house_support.py` ein IFC mit diesem Dach als Platzhalter (Unterseite aus `geometry`, Wände 0,30 m),
// der Import erkennt Form und Parameter und fragt den Kern (`engine /roof`); dort antwortet `answers`. Proben: das
// Rechteck des R+1 und der L-Grundriss der Probedatei 2, je Form mit den Werten des Demo-Katalogs. Neu schreiben mit
//   pnpm run roofs
// `test/roofs.test.ts` hält die Datei aktuell: Ändert sich der Kern, schlägt er fehl.
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ModelError, roofGeometry, type HouseRoofDesign, type HouseRoofGeometry, type HouseRoofRequest } from "../src/index.ts";

export interface RoofProbe {
  readonly name: string;
  readonly request: HouseRoofRequest;
  readonly geometry: HouseRoofGeometry;
}

export interface RoofAnswer {
  readonly request: HouseRoofRequest;
  readonly geometry: HouseRoofGeometry | null;
  /** Ablehnung des Kerns wie `engine` sie mit 422 meldet. */
  readonly rejection: { readonly code: string; readonly detail: Readonly<Record<string, string>> } | null;
}

const ring = (points: readonly (readonly [number, number])[]) => points.map(([x, y]) => ({ x, y }));
const RECTANGLE = ring([[0, 0], [10, 0], [10, 8], [0, 8]]);
const L_SHAPE = ring([[0, 0], [10, 0], [10, 4], [6, 4], [6, 6.5], [0, 6.5]]);
/** Dicke der Platzhalterwand im IFC und des Dachkörpers (Anfrage des Imports, `roof.py`). */
const WALL = 0.3;
const THICKNESS = 0.3;
/** Drehungen, die der Import je Form versucht (`ROTATIONS` in `roof.py`). */
const ROTATIONS: Readonly<Record<HouseRoofDesign["form"], readonly HouseRoofDesign["rotation"][]>> = {
  flat: [0],
  hip: [0],
  mansard: [0],
  gable: [0, 90],
  half_hip: [0, 90],
  mansard_gable: [0, 90],
  mono_pitch: [0, 90, 180, 270],
};

function design(form: HouseRoofDesign["form"], pitch: number, more: Partial<HouseRoofDesign> = {}): HouseRoofDesign {
  return { form, pitch_deg: pitch, upper_pitch_deg: null, break_height: null, rotation: 0, ...more };
}

function request(contour: HouseRoofRequest["contour"], bearing: number, roof: HouseRoofDesign, eave: number, verge: number): HouseRoofRequest {
  // Ohne Giebel gilt der Traufüberstand auch am Ortgang (so liest ihn der Import)
  const gables = !["hip", "mansard"].includes(roof.form);
  return { contour, wall_thickness: WALL, bearing_height: bearing, eave_overhang: eave, verge_overhang: gables ? verge : eave, design: roof, thickness: THICKNESS };
}

const REQUESTS: Readonly<Record<string, HouseRoofRequest>> = {
  "rectangle-gable": request(RECTANGLE, 5.8, design("gable", 35), 0.5, 0.3),
  "rectangle-gable-90": request(RECTANGLE, 5.8, design("gable", 35, { rotation: 90 }), 0.5, 0.3),
  "rectangle-mono-pitch": request(RECTANGLE, 5.8, design("mono_pitch", 15), 0.5, 0.3),
  "rectangle-mono-pitch-270": request(RECTANGLE, 5.8, design("mono_pitch", 15, { rotation: 270 }), 0.5, 0.3),
  "rectangle-hip": request(RECTANGLE, 5.8, design("hip", 30), 0.5, 0.5),
  "rectangle-half-hip": request(RECTANGLE, 5.8, design("half_hip", 40, { upper_pitch_deg: 60, break_height: 2 }), 0.5, 0.3),
  "rectangle-mansard": request(RECTANGLE, 5.8, design("mansard", 70, { upper_pitch_deg: 25, break_height: 2.2 }), 0.3, 0.3),
  "rectangle-mansard-gable": request(RECTANGLE, 5.8, design("mansard_gable", 70, { upper_pitch_deg: 25, break_height: 2.2 }), 0.3, 0.3),
  "l-gable": request(L_SHAPE, 3.77, design("gable", 35), 0.5, 0.3),
  "l-mono-pitch": request(L_SHAPE, 3.77, design("mono_pitch", 15), 0.5, 0.3),
  "l-hip": request(L_SHAPE, 3.77, design("hip", 20), 0.5, 0.5),
  "l-half-hip": request(L_SHAPE, 3.77, design("half_hip", 40, { upper_pitch_deg: 60, break_height: 1 }), 0.5, 0.3),
  "l-mansard": request(L_SHAPE, 3.77, design("mansard", 70, { upper_pitch_deg: 25, break_height: 2.2 }), 0.3, 0.3),
  "l-mansard-gable": request(L_SHAPE, 3.77, design("mansard_gable", 70, { upper_pitch_deg: 25, break_height: 2.2 }), 0.3, 0.3),
};

function answer(req: HouseRoofRequest): RoofAnswer {
  try {
    return { request: req, geometry: roofGeometry(req), rejection: null };
  } catch (error) {
    if (!(error instanceof ModelError)) throw error;
    return { request: req, geometry: null, rejection: { code: error.code, detail: error.detail } };
  }
}

export function roofs(): { probes: RoofProbe[]; answers: RoofAnswer[] } {
  const probes = Object.entries(REQUESTS).map(([name, req]) => ({ name, request: req, geometry: roofGeometry(req) }));
  const answers = Object.values(REQUESTS).flatMap((req) => ROTATIONS[req.design.form].map((rotation) => answer({ ...req, design: { ...req.design, rotation } })));
  // Jede Anfrage einmal: Drehung 0 und 90 eines Satteldachs stehen bei zwei Proben
  const unique = new Map(answers.map((a) => [JSON.stringify(a.request), a]));
  return { probes, answers: [...unique.values()] };
}

export const FIXTURE = fileURLToPath(new URL("../test/fixtures/demo-house", import.meta.url));

if (import.meta.main) {
  const result = roofs();
  writeFileSync(resolve(FIXTURE, "roofs.json"), `${JSON.stringify(result, null, 2)}\n`);
  console.log(`roofs.json: ${result.probes.length} Proben, ${result.answers.length} Antworten`);
}
