/** Testdaten des Konfigurators: drei Typen wie im Mockup, eine Konfiguration und die Fläche der Ursprünge. */

import type { CheckOut, ConfigurationOut, PlacementAreaOut, TypeFitOut, TypesOut } from "../../api/configuration";

const box = (width: number, depth: number, margin = 0) => [
  [-margin, -margin],
  [width + margin, -margin],
  [width + margin, depth + margin],
  [-margin, depth + margin],
  [-margin, -margin],
];

const ROLES = { "0": "garden", "1": "side_right", "2": "street", "3": "side_left" };

function type(
  slug: string,
  name: string,
  width: number,
  overrides: Partial<TypeFitOut> & { roof?: string; ridge?: number } = {},
): TypeFitOut {
  const { roof = "gable", ridge = 8.4, ...rest } = overrides;
  return {
    slug,
    version: 1,
    name,
    family: "plateau",
    allowed: true,
    reasons: [],
    hints: [],
    rotations: [0, 90, 180, 270],
    suggestions: [],
    facts: {
      storeys: "R+1",
      roof_form: roof,
      pitch_deg: roof === "flat" ? null : 40,
      ridge_direction: roof === "flat" ? null : "laengs",
      ridge_height_m: ridge,
      eave_height_m: 5.6,
      footprint_m2: width * 8,
      width_m: width,
      depth_m: 8,
      living_area_m2: 141,
      rooms_text: "4 Zimmer",
      base_price_min_cents: 32800000,
      base_price_max_cents: 36200000,
      facade_local: box(width, 8),
      projection_local: box(width, 8, 0.5),
      facade_roles: ROLES,
      entrance: null,
    },
    ...rest,
  };
}

export const ROOF_FORM_FAIL: CheckOut = {
  code: "roof_form",
  kind: "roof",
  status: "fail",
  binding: true,
  measured: "flat",
  limit: "gable,hip",
  zone_code: "UB",
  params: {},
};

export const LIGNE = type("ligne", "Ligne", 12, {
  hints: [{ code: "roof_unknown", kind: "roof", status: "unknown", binding: false, reason: "missing", params: {} }],
});
export const PLATEAU = type("plateau", "Plateau", 16.5, {
  roof: "flat",
  ridge: 6.8,
  allowed: false,
  reasons: [ROOF_FORM_FAIL],
  rotations: [],
  suggestions: ["plateau_adapte"],
});
export const PLATEAU_ADAPTE = type("plateau_adapte", "Plateau — angepasst", 13.5);

export const TYPES: TypesOut = {
  simulation: true,
  mode: "rules",
  free_reason: null,
  notices: ["notice.envelope_simulation"],
  site_revision: 1,
  types: [LIGNE, PLATEAU, PLATEAU_ADAPTE],
};

const edge = (seq: number, kind: string, measured: number, required: number | null, allowsBoundary = false) => ({
  seq,
  kind,
  measured_m: measured,
  required_m: required,
  contour: "facade" as const,
  status: "pass" as const,
  on_boundary: false,
  on_boundary_allowed: allowsBoundary,
  markers: [],
});

export const CONFIGURATION: ConfigurationOut = {
  simulation: true,
  project_id: "00000000-0000-4000-8000-000000000065",
  revision: 3,
  engine_version: "h2-1.0.0",
  mode: "rules",
  free_reason: null,
  type: { slug: "ligne", version: 1, name: "Ligne", retired: false },
  placement: { origin: { e: 8, n: 25 }, rotation_deg: 0 },
  boundary_options: {},
  rotations: [0, 90, 180, 270],
  fit: LIGNE,
  evaluation: {
    valid: true,
    zone_code: "Uh",
    facade_local: [],
    projection_local: [],
    edges: [edge(1, "side", 4, 3, true), edge(2, "street", 5, 5), edge(3, "rear", 18, 3, true)],
    checks: [
      { code: "setback_street", kind: "setback_street", status: "pass", binding: true, measured: 5, limit: 5, unit: "m", edge_seq: 2, params: {} },
      { code: "setback_side", kind: "setback_side", status: "pass", binding: true, measured: 4, limit: 3, unit: "m", edge_seq: 1, params: {} },
      { code: "band_unclear", kind: "setback_street", status: "hint", binding: false, edge_seq: 2, params: {} },
    ],
  },
  notices: ["notice.envelope_simulation"],
  updated_at: "2026-09-19T08:00:00Z",
};

export const VIOLATED: ConfigurationOut = {
  ...CONFIGURATION,
  evaluation: {
    ...CONFIGURATION.evaluation!,
    valid: false,
    checks: [
      { code: "setback_street", kind: "setback_street", status: "fail", binding: true, measured: 4, limit: 5, unit: "m", edge_seq: 2, params: {} },
    ],
  },
};

/** Grosse Fläche, damit Verschiebungen im Test innerhalb bleiben. */
export const AREA: PlacementAreaOut = {
  type_slug: "ligne",
  rotations: [0, 90, 180, 270].map((rotation) => ({
    rotation_deg: rotation,
    rings_local: [
      [
        [0, 0],
        [30, 0],
        [30, 60],
        [0, 60],
        [0, 0],
      ],
    ],
    area_m2: 1800,
  })),
};
