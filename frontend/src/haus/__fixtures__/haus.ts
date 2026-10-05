/**
 * Testdaten des Kundenwegs im Hausmodell (HM4): das Demohaus aus den Testdaten des Kerns, die gespeicherten
 * Auswertungen (`packages/domain/test/fixtures/demo-house/evaluations.json`) und Antworten der API dazu.
 */

import type { HouseCatalog, HouseConfiguration, HouseTemplate } from "@emprise/domain";

import catalogJson from "../../../../packages/domain/test/fixtures/demo-house/catalog.json";
import evaluationsJson from "../../../../packages/domain/test/fixtures/demo-house/evaluations.json";
import templateJson from "../../../../packages/domain/test/fixtures/demo-house/template.json";
import type { HouseConfigurationOut, HouseDocumentsOut, HouseTemplatesOut } from "../../api/hausKonfiguration";
import { CONFIGURATION } from "../../configuration/__fixtures__/konfiguration";
import type { Dokumente } from "../kern";

export const template = templateJson as unknown as HouseTemplate;
export const catalog = catalogJson as unknown as HouseCatalog;
export const DOCS: Dokumente = { template, catalog };

type Fall = keyof typeof evaluationsJson;
export const EVALUATIONS = evaluationsJson as unknown as Record<
  Fall,
  { configuration: HouseConfiguration; evaluation: import("@emprise/domain").HouseEvaluation }
>;

export const DOCUMENTS: HouseDocumentsOut = {
  template_version_id: "00000000-0000-4000-8000-0000000000a1",
  catalog_version_id: "00000000-0000-4000-8000-0000000000c1",
  template: templateJson as unknown as HouseDocumentsOut["template"],
  catalog: catalogJson as unknown as HouseDocumentsOut["catalog"],
};

const box = (width: number, depth: number, margin = 0) => [
  [-margin, -margin],
  [width + margin, -margin],
  [width + margin, depth + margin],
  [-margin, depth + margin],
  [-margin, -margin],
];

const NAME = { fr: "Maison de démonstration", de: "Demohaus" };

export const FACTS: NonNullable<HouseConfigurationOut["facts"]> = {
  storeys: "R",
  roof_form: "flat",
  pitch_deg: null,
  height_m: 3.47,
  eave_height_m: 3.47,
  floor_area_m2: 98.6,
  footprint_m2: 116.1,
  width_m: 12.9,
  depth_m: 9,
  facade_local: box(12.9, 9),
  projection_local: box(12.9, 9, 0.3),
  facade_roles: { "0": "street", "1": "side_right", "2": "garden", "3": "side_left" },
  facade_material: "render",
  roof_material: "other",
};

const price = (gross: number, deltas: Record<string, number> = {}) => ({
  currency: "EUR" as const,
  vat_rate: 0.2,
  gross_rounded: gross,
  deltas_rounded: deltas,
  is_estimate: true as const,
});

export const TEMPLATES: HouseTemplatesOut = {
  simulation: true,
  mode: "rules",
  free_reason: null,
  notices: ["notice.envelope_simulation"],
  site_revision: 1,
  templates: [
    {
      slug: "demo_house",
      version: 1,
      catalog_version: 1,
      name: NAME,
      allowed: true,
      reasons: [],
      hints: [],
      rotations: [0, 90, 180, 270],
      status: "valid",
      price: price(515000),
      facts: FACTS,
    },
  ],
};

export const EMPTY: HouseConfigurationOut = {
  simulation: true,
  project_id: "00000000-0000-4000-8000-000000000065",
  revision: 0,
  mode: "rules",
  free_reason: null,
  notices: ["notice.envelope_simulation"],
  template: null,
  update_available: false,
  configuration: { selections: {} },
  placement: null,
  boundary_options: {},
  rotations: [],
  facts: null,
  evaluation: null,
  areas: null,
  orientation: null,
  status: null,
  rule_results: [],
  notes: [],
  site_results: [],
  suggestion: null,
  price: null,
  price_match: null,
  domain_version: null,
  site_changed: false,
  updated_at: null,
};

export const CHOSEN: HouseConfigurationOut = {
  ...EMPTY,
  revision: 1,
  template: { slug: "demo_house", version: 1, catalog_version: 1, name: NAME, retired: false },
  placement: { origin: { e: 8, n: 25 }, rotation_deg: 0 },
  rotations: [0, 90, 180, 270],
  facts: FACTS,
  evaluation: CONFIGURATION.evaluation,
  status: "valid",
  site_results: [
    {
      outcome: "info",
      check: { code: "parking_not_shown", kind: "parking", status: "hint", binding: false, params: {} },
    },
  ],
  price: price(515000),
  domain_version: "0.3.0",
  updated_at: "2026-10-04T08:00:00Z",
};

/** Ziegel gespeichert, Lage weicht ab und hat einen Vorschlag. */
export const BRICK: HouseConfigurationOut = {
  ...CHOSEN,
  revision: 2,
  configuration: EVALUATIONS.brick.configuration as unknown as HouseConfigurationOut["configuration"],
  status: "with_deviations",
  site_results: [
    {
      outcome: "deviation",
      check: { code: "outside_site", kind: "outside_site", status: "fail", binding: true, params: {} },
    },
    ...CHOSEN.site_results,
  ],
  suggestion: { origin: { e: 9, n: 26 }, rotation_deg: 0 },
  price: price(524000, { wall_profile: 8400 }),
};
