// Codes des Kerns (E-HM-33): geschlossene Listen, damit die Oberfläche jeden Code übersetzen kann. Text kommt nur
// aus dem Katalog (Regeltexte, `unavailable_reason`); den Rest übersetzt die Oberfläche, und ein Test im Frontend
// hält die Texte in FR und DE vollständig (wie E-HM-46). Ohne Importe, weil das Frontend die Datei direkt einbindet.

/** Mängel eines Rings (`polygonDefect`, P 4). */
export const POLYGON_DEFECTS = [
  "too_few_vertices",
  "coordinates_not_integer",
  "coordinates_out_of_range",
  "zero_length_edge",
  "self_intersecting",
  "zero_area",
] as const;
export type PolygonDefect = (typeof POLYGON_DEFECTS)[number];

/** Fehler der Geometrie (`GeometryError`): ein mangelhafter Ring oder ein Versatz, der nicht genau ein Polygon ergibt. */
export const GEOMETRY_ERROR_CODES = [...POLYGON_DEFECTS, "distance_not_integer", "offset_not_single", "union_not_single"] as const;
export type GeometryErrorCode = (typeof GEOMETRY_ERROR_CODES)[number];

/** Eingaben, die sich nicht rechnen lassen (`ModelError`). */
export const MODEL_ERROR_CODES = [
  "assignment_ambiguous",
  "assignment_missing",
  "carport_type_unknown",
  "conductivity_missing",
  "default_missing",
  "door_type_unknown",
  "element_unknown",
  "envelope_invalid",
  "envelope_not_counter_clockwise",
  "floor_slab_missing",
  "ground_slab_missing",
  "host_unknown",
  "layer_not_in_profile",
  "layer_unknown",
  "material_unknown",
  "mixed_wall_profiles",
  "option_unknown",
  "override_not_allowed",
  "price_entry_ambiguous",
  "price_entry_missing",
  "price_entry_unknown",
  "price_unit_mismatch",
  "roof_not_constructible",
  "roof_shape_unknown",
  "roof_slab_missing",
  "roof_type_kind_mismatch",
  "roof_type_unknown",
  "room_invalid",
  "room_unknown",
  "slot_unknown",
  "storey_envelope_mismatch",
  "storey_outlines_differ",
  "terrace_type_unknown",
  "value_type_mismatch",
  "wall_profile_unknown",
  "window_type_unknown",
] as const;
export type ModelErrorCode = (typeof MODEL_ERROR_CODES)[number];

/**
 * Gründe, aus denen der Kern eine Dachform auf dem Grundriss nicht erzeugt (Ergänzung 4): `params.reason` bei
 * `roof_not_constructible`. Fehler des Skeletts selbst zählen als `skeleton_failed`.
 */
export const ROOF_REFUSALS = [
  "break_too_high",
  "break_too_low",
  "design_incomplete",
  "gables_adjacent",
  "no_eave_edge",
  "no_gable_edge",
  "outline_invalid",
  "skeleton_failed",
] as const;
export type RoofRefusal = (typeof ROOF_REFUSALS)[number];

/** Ergebnisse der Regeln (P 6.6, P 8.3): Prüfungen der Geometrie und Katalogregeln (deren Text steht im Katalog). */
export const RULE_CODES = ["opening_outside_host", "opening_above_ceiling", "opening_below_floor", "openings_overlap", "catalog_rule"] as const;
export type RuleCode = (typeof RULE_CODES)[number];

/** Befunde, die nur die Kompatibilitätsprüfung meldet. */
const CHECK_CODES = [
  "anchor_layer_not_in_profile",
  "bearing_layer_not_in_profile",
  "default_unavailable",
  "default_unknown",
  "element_default_not_targeted",
  "exterior_door_unknown",
  "level_unknown",
  "line_slot_unknown",
  "line_value_unknown",
  "parameter_slot_without_shape",
  "price_source_ambiguous",
  "price_target_mismatch",
  "quantity_key_unknown",
  "roof_shape_default_mismatch",
  "roof_shape_without_roof_type",
  "room_outside_envelope",
  "room_type_unknown",
  "rooms_overlap",
  "terrace_without_garden_edge",
  "type_slot_ambiguous",
  "type_slot_missing",
  "wall_axis_zero_length",
  "wall_outside_envelope",
  ...POLYGON_DEFECTS.map((defect) => `envelope_${defect}` as const),
  ...POLYGON_DEFECTS.map((defect) => `room_${defect}` as const),
] as const;

/** Befund der Kompatibilitätsprüfung: eigene Prüfung, Fehler des Kerns oder Sperre des Standards (`default_…`). */
export type CompatibilityCode = (typeof CHECK_CODES)[number] | ModelErrorCode | GeometryErrorCode | `default_${RuleCode}`;

/** Alle Codes der Kompatibilitätsprüfung, auch die Ablehnung durch `engine` (422, E-HM-45), sortiert und ohne Doppel. */
export const COMPATIBILITY_CODES: readonly CompatibilityCode[] = [
  ...new Set<CompatibilityCode>([
    ...CHECK_CODES,
    ...MODEL_ERROR_CODES,
    ...GEOMETRY_ERROR_CODES,
    ...RULE_CODES.map((code) => `default_${code}` as const),
  ]),
].sort();
