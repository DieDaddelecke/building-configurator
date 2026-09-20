/** Testdaten des Konfigurators: drei Typen wie im Mockup, eine Konfiguration und die Fläche der Ursprünge. */

import type {
  CheckOut,
  ConfigurationOut,
  CostsOut,
  OptionsOut,
  PlacementAreaOut,
  TypeFitOut,
  TypesOut,
} from "../../api/configuration";

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
  selection: null,
  outbuildings: null,
  areas: null,
  compliance: null,
  energy: null,
  costs: null,
  orientation: null,
  review_stamp: "v1:site=aaaaaaaaaaaa.rules=bbbbbbbbbbbb.catalog=cccccccccccc.configuration=3.result=dddddddddddd.engine=eeeeeeeeeeee",
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

// ---------------------------------------------------------------------------
// H3: Linien, Optionen, Nebenbauten, Kosten
// ---------------------------------------------------------------------------

const NOT_ASSESSED = { status: "not_assessed" as const, climate_zone: null, verdict: null, measures: null, surcharge_cents: null };

export const OPTIONS: OptionsOut = {
  simulation: true,
  type_slug: "ligne",
  catalog_available: true,
  vat_rate: 0.2,
  display_basis: "gross",
  packages: [
    {
      slug: "base",
      version: 1,
      label_de: "Base",
      label_fr: "Base",
      scope: ["Fassade Putz", "Fenster Kunststoff"],
      included_option_slugs: [],
      price: { basis: "fixed", min_cents: 0, max_cents: 0, unit_price_cents: null, quantity: null },
      selected: false,
      retired: false,
      energy: {
        status: "action",
        climate_zone: "H2b",
        verdict: "Base verfehlt den Schwellenwert knapp",
        measures: "verstärkte Dämmung",
        surcharge_cents: 1140000,
      },
    },
    {
      slug: "confort",
      version: 1,
      label_de: "Confort",
      label_fr: "Confort",
      scope: ["Fassade Putz durchgefärbt", "Fenster Holz-Alu"],
      included_option_slugs: ["pv"],
      price: { basis: "fixed", min_cents: 4080000, max_cents: 4080000, unit_price_cents: null, quantity: null },
      selected: true,
      retired: false,
      energy: NOT_ASSESSED,
    },
  ],
  options: [
    { slug: "terrasse", version: 1, kind: "terrace", label_de: "Terrasse Holz", label_fr: "Terrasse bois", excludes: [], state: "selected", price: { basis: "per_m2", min_cents: 1728000, max_cents: 1728000, unit_price_cents: 48000, quantity: 36 }, reasons: [], checks: [], area_m2: 36 },
    { slug: "carport_1", version: 1, kind: "carport", label_de: "Carport einstellig", label_fr: "Carport simple", excludes: [], state: "available", price: { basis: "fixed", min_cents: 1080000, max_cents: 1080000, unit_price_cents: null, quantity: null }, reasons: [], checks: [], area_m2: 15 },
    { slug: "carport_2", version: 1, kind: "carport", label_de: "Carport zweistellig", label_fr: "Carport double", excludes: [], state: "blocked", price: { basis: "fixed", min_cents: 1740000, max_cents: 1740000, unit_price_cents: null, quantity: null }, reasons: [{ code: "excluded_by", slug: "carport_2", other: "carport_1" }], checks: [{ code: "annex_footprint", kind: "annex", status: "fail", binding: true, measured: 30, limit: 20, unit: "m2", params: { subject: "carport_2" } }], area_m2: 30 },
    { slug: "pv", version: 1, kind: "plain", label_de: "Photovoltaik 6 kWp", label_fr: "Photovoltaïque 6 kWc", excludes: [], state: "included", price: { basis: "fixed", min_cents: 1344000, max_cents: 1344000, unit_price_cents: null, quantity: null }, reasons: [], checks: [], area_m2: null },
    { slug: "keller", version: 1, kind: "plain", label_de: "Keller", label_fr: "Cave", excludes: [], state: "available", price: { basis: "fixed", min_cents: 5640000, max_cents: 5640000, unit_price_cents: null, quantity: null }, reasons: [], checks: [], area_m2: null },
  ],
};

export const COSTS: CostsOut = {
  available: true,
  reason: null,
  net: { min_cents: 37_400_000, max_cents: 40_800_000 },
  gross: { min_cents: 44_880_000, max_cents: 48_960_000 },
  vat_rate: 0.2,
  display_basis: "gross",
  display: { min_cents: 44_900_000, max_cents: 49_000_000 },
  catalog_version: 1,
  items: [
    { code: "TYPE_BASE", kind: "base", slug: null, label_de: "Ligne", label_fr: "Ligne", min_cents: 39_360_000, max_cents: 43_440_000, included: false, quantity: null, unit: null, unit_price_cents: null, source: "catalog" },
    { code: "PKG_CONFORT", kind: "package", slug: "confort", label_de: "Confort", label_fr: "Confort", min_cents: 4_080_000, max_cents: 4_080_000, included: false, quantity: null, unit: null, unit_price_cents: null, source: null },
    { code: "MOD_TERRASSE", kind: "option", slug: "terrasse", label_de: "Terrasse Holz", label_fr: "Terrasse bois", min_cents: 1_728_000, max_cents: 1_728_000, included: false, quantity: 36, unit: "m2", unit_price_cents: 48_000, source: null },
    { code: "MOD_PV", kind: "option", slug: "pv", label_de: "Photovoltaik 6 kWp", label_fr: "Photovoltaïque 6 kWc", min_cents: 0, max_cents: 0, included: true, quantity: null, unit: null, unit_price_cents: null, source: null },
  ],
};

const ring = (x: number, y: number, w: number, d: number) => [
  [x, y],
  [x + w, y],
  [x + w, y + d],
  [x, y + d],
  [x, y],
];

/** Ligne mit Confort, Terrasse und einem Carport samt Zufahrt: alle Antwortfelder von H3 gefüllt. */
export const CONFIGURED: ConfigurationOut = {
  ...CONFIGURATION,
  evaluation: { ...CONFIGURATION.evaluation!, facade_local: ring(8, 25, 12, 8), projection_local: ring(7.5, 24.5, 13, 9) },
  selection: {
    package_slug: "confort",
    package_version: 1,
    option_slugs: ["terrasse"],
    included_slugs: ["pv"],
    invalid: [],
    dropped: [],
  },
  outbuildings: {
    terrace: { slug: "terrasse", kind: "terrace", placed: true, polygon_local: ring(8, 22, 12, 3), area_m2: 36, width_m: 12, depth_m: 3, spaces: null, setback: null },
    carport: { slug: "carport_1", kind: "carport", placed: true, polygon_local: ring(2, 40, 3, 5), area_m2: 15, width_m: 3, depth_m: 5, spaces: 1, setback: "assumed" },
    driveways: [{ source: "carport", polygon_local: ring(2, 45, 3, 5), length_m: 5, area_m2: 15 }],
  },
  areas: { site_m2: 620, house_m2: 96, carport_m2: 15, terrace_m2: 36, driveway_m2: 15, paths_m2: 10, emprise_m2: 111, sealed_m2: 172, unsealed_m2: 448, parts: [] },
  compliance: {
    checks: [
      { code: "annex_footprint", kind: "annex", status: "fail", binding: true, measured: 30, limit: 20, unit: "m2", params: { subject: "carport_2" } },
      { code: "carport_setback_assumed", kind: "annex", status: "hint", binding: false, params: { subject: "carport_1" } },
      { code: "unsealed_min", kind: "unsealed_min", status: "pass", binding: true, measured: 448, limit: 186, unit: "m2", params: { ratio: 0.3 } },
    ],
    fail: 1,
    hint: 1,
    unknown: 0,
    passed: 1,
  },
  energy: NOT_ASSESSED,
  costs: COSTS,
  orientation: { convergence_deg: -3.3, facades: { garden: 176.7, street: 356.7 } },
};
