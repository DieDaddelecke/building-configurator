// Rechenkern des Hausmodells (docs/PLAN_HAUSMODELL.md 3.2): ohne React, DOM, Three.js oder Datenbank.
export {
  COMPATIBILITY_CODES,
  GEOMETRY_ERROR_CODES,
  MODEL_ERROR_CODES,
  POLYGON_DEFECTS,
  ROOF_REFUSALS,
  RULE_CODES,
  type CompatibilityCode,
  type GeometryErrorCode,
  type ModelErrorCode,
  type RoofRefusal,
  type RuleCode,
} from "./codes.ts";
export { checkCompatibility } from "./compatibility.ts";
export type * from "./contract.gen.ts";
export { wallUValue } from "./energy.ts";
export { ModelError } from "./errors.ts";
export { evaluateExpr } from "./expr.ts";
export type {
  DerivedModel,
  FlatRoofGeometry,
  LayerGeometry,
  LoopGeometry,
  OpeningGeometry,
  RoofGeometry,
  RoomGeometry,
  SegmentGeometry,
  SiteGeometry,
} from "./derive.ts";
export { deriveModel, DOMAIN_VERSION, evaluate, roofPitchRange, type EvaluateInput } from "./evaluate.ts";
export { GeometryError, offsetPolygon, unionPolygons } from "./geometry/offset.ts";
export {
  areaSquareMetres,
  counterClockwise,
  MAX_COORDINATE,
  perimeterMetres,
  polygonDefect,
  signedArea,
  toMetres,
  toUnits,
  UNITS_PER_METRE,
  type Point,
  type Polygon,
  type PolygonDefect,
} from "./geometry/polygon.ts";
export { activeLine, applyLine } from "./lines.ts";
export {
  buildRoof,
  ROOF_LINE_KINDS,
  RoofError,
  roofRefusal,
  type Roof,
  type RoofDesign,
  type RoofErrorCode,
  type RoofFace,
  type RoofForm,
  type RoofInput,
  type RoofLine,
  type RoofLineKind,
  type RoofRotation,
} from "./roof/build.ts";
export { rotates, type EffectiveRoof, type PitchRange } from "./roof/effective.ts";
export { roofGeometry } from "./roof/request.ts";
