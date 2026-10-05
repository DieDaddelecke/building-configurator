// Mengenermittlung (P 7): flache Liste benannter Mengen mit Herkunft, nur aus dem abgeleiteten Modell.
import type { HouseCatalog, HouseQuantity } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { signedArea, toUnits, UNITS_PER_METRE } from "./geometry/polygon.ts";
import { ROOF_LINE_KINDS, type RoofLineKind } from "./roof/build.ts";

const AREA = UNITS_PER_METRE * UNITS_PER_METRE;

/** Mengenschlüssel mit Einheit und der Art des Katalogeintrags hinter `ref_id` (für `by_target`). */
export const QUANTITY_KEYS = {
  "wall.layer.area": { unit: "m2", ref: "wall_layer" },
  "opening.area": { unit: "m2", ref: null },
  "window.count": { unit: "pcs", ref: "window_type" },
  "door.count": { unit: "pcs", ref: "door_type" },
  "roof.area": { unit: "m2", ref: "roof_type" },
  "roof.ridge.length": { unit: "m", ref: "roof_type" },
  "roof.hip.length": { unit: "m", ref: "roof_type" },
  "roof.valley.length": { unit: "m", ref: "roof_type" },
  "roof.eave.length": { unit: "m", ref: "roof_type" },
  "roof.verge.length": { unit: "m", ref: "roof_type" },
  "roof.break.length": { unit: "m", ref: "roof_type" },
  "gable.area": { unit: "m2", ref: null },
  "bearing.length": { unit: "m", ref: null },
  "reveal.area": { unit: "m2", ref: null },
  "footprint.area": { unit: "m2", ref: null },
  "terrace.area": { unit: "m2", ref: "terrace_type" },
  "carport.count": { unit: "pcs", ref: "carport_type" },
} as const;

export type QuantityKey = keyof typeof QUANTITY_KEYS;

const LINE_KEYS: Readonly<Record<RoofLineKind, QuantityKey>> = {
  ridge: "roof.ridge.length",
  hip: "roof.hip.length",
  valley: "roof.valley.length",
  eave: "roof.eave.length",
  verge: "roof.verge.length",
  break: "roof.break.length",
};

class Collector {
  private readonly entries = new Map<string, { key: QuantityKey; ref: string | null; value: number; elements: Set<string> }>();

  add(key: QuantityKey, ref: string | null, value: number, elementIds: readonly string[]): void {
    const id = `${key}\u0000${ref ?? ""}`;
    const entry = this.entries.get(id) ?? { key, ref, value: 0, elements: new Set<string>() };
    entry.value += value;
    elementIds.forEach((element) => entry.elements.add(element));
    this.entries.set(id, entry);
  }

  list(): HouseQuantity[] {
    return [...this.entries.values()]
      .sort((a, b) => a.key.localeCompare(b.key) || (a.ref ?? "").localeCompare(b.ref ?? ""))
      .map((e) => ({ key: e.key, ref_id: e.ref, value: e.value, unit: QUANTITY_KEYS[e.key].unit, element_ids: [...e.elements].sort() }));
  }
}

export function takeOff(model: DerivedModel, catalog: HouseCatalog): HouseQuantity[] {
  const quantities = new Collector();
  const threshold = toUnits(catalog.parameters.opening_deduction_threshold) * UNITS_PER_METRE;

  for (const loop of model.loops) {
    const segmentIds = loop.segments.map((s) => s.id);
    const hosted = model.openings.filter((o) => o.hostKind === "envelope_segment" && segmentIds.includes(o.hostId));
    const deducted = hosted.filter((o) => o.area > threshold);
    const deduction = deducted.reduce((sum, o) => sum + o.area, 0);
    quantities.add("opening.area", null, deduction / AREA, deducted.map((o) => o.id));
    // Fläche einer Wandschicht: auf der Mittellinie bis zur Oberkante des Geschosses − Öffnungen (P 7, Ergänzung 5)
    for (const layer of loop.layers) {
      quantities.add("wall.layer.area", layer.layerId, (layer.grossArea - deduction) / AREA, segmentIds);
    }
    if (loop.bearingLength !== null && loop.profile.bearing) {
      quantities.add("bearing.length", loop.profile.bearing.kind, loop.bearingLength / UNITS_PER_METRE, segmentIds);
    }
    if (loop.profile.reveal_finish && loop.revealDepth > 0) {
      // Laibung: (2 · Höhe + Breite) × Tiefe je Öffnung in der Hülle (P 7)
      const reveal = hosted.reduce((sum, o) => sum + (2 * (o.height + o.shutterBox) + o.width) * loop.revealDepth, 0);
      quantities.add("reveal.area", loop.profile.reveal_finish.material_id, reveal / AREA, hosted.map((o) => o.id));
    }
  }
  // Grundfläche einmal: die Fassade des Geschosses mit der dicksten Wand umschließt alle anderen
  const facade = model.loops[model.facadeLoop]!;
  quantities.add("footprint.area", null, signedArea(facade.facadeOutline) / AREA, model.loops.flatMap((loop) => loop.segments.map((s) => s.id)));

  for (const opening of model.openings) {
    quantities.add(opening.kind === "window" ? "window.count" : "door.count", opening.typeId, 1, [opening.id]);
  }
  const roof = model.roof;
  const roofTypeId = roof.roofType.id;
  if (roof.pitched) {
    // Geneigt: je Dachfläche mit Überstand; Linien nach Art (Ergänzung 11)
    quantities.add("roof.area", roofTypeId, roof.pitched.faces.reduce((sum, face) => sum + face.area, 0), ["roof"]);
    for (const kind of ROOF_LINE_KINDS) {
      const length = roof.pitched.lines.filter((line) => line.kind === kind).reduce((sum, line) => sum + line.length, 0);
      if (length > 0) quantities.add(LINE_KEYS[kind], roofTypeId, length, ["roof"]);
    }
    if (roof.pitched.gableArea > 0) quantities.add("gable.area", null, roof.pitched.gableArea, ["roof"]);
  } else {
    // Flach: innerhalb der Außenkante der letzten thermischen Schicht des obersten Geschosses (P 7)
    quantities.add("roof.area", roofTypeId, signedArea(model.loops.at(-1)!.thermalOutline) / AREA, ["roof"]);
  }
  const { terrace, carport } = model.site;
  if (terrace && terrace.width !== null) quantities.add("terrace.area", terrace.type.id, terrace.width * terrace.type.depth, ["site"]);
  if (carport) quantities.add("carport.count", carport.id, 1, ["site"]);
  return quantities.list();
}

/** Summe einer Menge über alle `ref_id`. */
export function total(quantities: readonly HouseQuantity[], key: string): number {
  return quantities.filter((q) => q.key === key).reduce((sum, q) => sum + q.value, 0);
}
