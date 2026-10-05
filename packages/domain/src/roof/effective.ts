// Wirksames Dach (Ergänzung 4, E-HM-10): Form und Parameter aus dem Entwurf des Templates und der gewählten
// Dachform des Katalogs, danach Neigung und Drehung aus den Zahl-Slots (E-HM-62).
import type { HouseRoofShape, HouseTemplate } from "../contract.gen.ts";
import type { RoofDesign, RoofForm, RoofRotation } from "./build.ts";

export const ROOF_ROTATIONS: readonly RoofRotation[] = [0, 90, 180, 270];

export interface PitchRange {
  readonly min: number;
  readonly max: number;
  readonly default: number;
}

export interface EffectiveRoof {
  /** Dachform des Katalogs; `null` ohne Slot für die Form, dann gilt der Entwurf des Templates. */
  readonly shapeId: string | null;
  readonly design: RoofDesign;
  /** Spanne der Neigung der Traufflächen; `null` beim Flachdach. */
  readonly pitch: PitchRange | null;
  /** Überstände in m. */
  readonly eaveOverhang: number;
  readonly vergeOverhang: number;
  /** Flachdach auf einem geneigten Template: Dachdecke der Katalogform in m; sonst `null` (Platte `roof` des Templates). */
  readonly slabThickness: number | null;
  /** Flachdach: Attika über Oberkante Dachdecke in m; geneigt 0. */
  readonly parapetHeight: number;
}

/** Drehsemantik: Sattel, Krüppelwalm und Mansardsattel legen den First fest, das Pultdach die Traufseite. */
const ROTATION_KIND: Readonly<Record<RoofForm, "ridge" | "eave" | null>> = {
  flat: null,
  hip: null,
  mansard: null,
  gable: "ridge",
  half_hip: "ridge",
  mansard_gable: "ridge",
  mono_pitch: "eave",
};

/** Lässt sich die Form drehen (Slot `roof_rotation`)? */
export function rotates(form: RoofForm): boolean {
  return ROTATION_KIND[form] !== null;
}

/**
 * Dach vor den Zahl-Slots. Gleiche Form wie das Template: Werte aus dem IFC, die Spanne der Katalogform wird bis zur
 * Neigung des Templates erweitert. Andere Form: Werte der Katalogform; Überstände bei gleicher Dachart (flach oder
 * geneigt) vom Template, sonst von der Form; Drehung des Templates nur bei gleicher Drehsemantik.
 */
export function baseRoof(template: HouseTemplate, shape: HouseRoofShape | null): EffectiveRoof {
  const placement = template.roof;
  const own = placement.design;
  if (shape === null || shape.form === own.form) {
    const pitch = own.pitch_deg;
    const range =
      pitch === null
        ? null
        : { min: Math.min(shape?.pitch?.min_deg ?? pitch, pitch), max: Math.max(shape?.pitch?.max_deg ?? pitch, pitch), default: pitch };
    return {
      shapeId: shape?.id ?? null,
      design: { form: own.form, pitchDeg: pitch, upperPitchDeg: own.upper_pitch_deg, breakHeight: own.break_height, rotation: own.rotation },
      pitch: range,
      eaveOverhang: placement.eave_overhang,
      vergeOverhang: placement.verge_overhang,
      slabThickness: null,
      parapetHeight: own.form === "flat" ? placement.parapet_height : 0,
    };
  }
  const flat = shape.form === "flat";
  const sameKind = flat === (own.form === "flat");
  const sameRotation = ROTATION_KIND[shape.form] !== null && ROTATION_KIND[shape.form] === ROTATION_KIND[own.form];
  return {
    shapeId: shape.id,
    design: {
      form: shape.form,
      pitchDeg: shape.pitch?.default_deg ?? null,
      upperPitchDeg: shape.upper_pitch_deg,
      breakHeight: shape.break_height,
      rotation: sameRotation ? own.rotation : 0,
    },
    pitch: shape.pitch ? { min: shape.pitch.min_deg, max: shape.pitch.max_deg, default: shape.pitch.default_deg } : null,
    eaveOverhang: sameKind ? placement.eave_overhang : shape.eave_overhang,
    vergeOverhang: sameKind ? placement.verge_overhang : shape.verge_overhang,
    slabThickness: flat && !sameKind ? shape.slab_thickness : null,
    parapetHeight: flat ? (sameKind ? placement.parapet_height : (shape.parapet_height ?? 0)) : 0,
  };
}

/** Neigung und Drehung aus den Zahl-Slots übernehmen (`null`: Voreinstellung). */
export function withNumbers(roof: EffectiveRoof, pitchDeg: number | null, rotation: RoofRotation | null): EffectiveRoof {
  return {
    ...roof,
    design: {
      ...roof.design,
      pitchDeg: pitchDeg ?? roof.design.pitchDeg,
      rotation: rotation ?? roof.design.rotation,
    },
  };
}

/** Liegt eine Neigung in der Spanne? Grad mit einer Toleranz für Rundung im Browser. */
export function inRange(range: PitchRange, value: number): boolean {
  return value >= range.min - 1e-9 && value <= range.max + 1e-9;
}
