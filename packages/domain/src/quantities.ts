// Mengenermittlung (P 7): flache Liste benannter Mengen mit Herkunft, nur aus dem abgeleiteten Modell.
import type { HouseCatalog, HouseQuantity } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { signedArea, toUnits, UNITS_PER_METRE } from "./geometry/polygon.ts";

const AREA = UNITS_PER_METRE * UNITS_PER_METRE;

/** Mengenschlüssel mit Einheit und der Art des Katalogeintrags hinter `ref_id` (für `by_target`). */
export const QUANTITY_KEYS = {
  "wall.layer.area": { unit: "m2", ref: "wall_layer" },
  "opening.area": { unit: "m2", ref: null },
  "window.count": { unit: "pcs", ref: "window_type" },
  "door.count": { unit: "pcs", ref: "door_type" },
  "roof.area": { unit: "m2", ref: "roof_type" },
  "bearing.length": { unit: "m", ref: null },
  "reveal.area": { unit: "m2", ref: null },
  "footprint.area": { unit: "m2", ref: null },
} as const;

export type QuantityKey = keyof typeof QUANTITY_KEYS;

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
    // Fläche einer Wandschicht: Länge der Mittellinie × Fassadenhöhe − Öffnungen (P 7)
    for (const layer of loop.layers) {
      quantities.add("wall.layer.area", layer.layerId, (layer.centerline * loop.facadeHeight - deduction) / AREA, segmentIds);
    }
    if (loop.bearingLength !== null && loop.profile.bearing) {
      quantities.add("bearing.length", loop.profile.bearing.kind, loop.bearingLength / UNITS_PER_METRE, segmentIds);
    }
    if (loop.profile.reveal_finish && loop.revealDepth > 0) {
      // Laibung: (2 · Höhe + Breite) × Tiefe je Öffnung in der Hülle (P 7)
      const reveal = hosted.reduce((sum, o) => sum + (2 * (o.height + o.shutterBox) + o.width) * loop.revealDepth, 0);
      quantities.add("reveal.area", loop.profile.reveal_finish.material_id, reveal / AREA, hosted.map((o) => o.id));
    }
    quantities.add("footprint.area", null, signedArea(loop.facadeOutline) / AREA, segmentIds);
  }

  for (const opening of model.openings) {
    quantities.add(opening.kind === "window" ? "window.count" : "door.count", opening.typeId, 1, [opening.id]);
  }
  // Dachfläche: innerhalb der Außenkante der letzten thermischen Schicht des obersten Geschosses (P 7)
  const top = model.loops.at(-1)!;
  quantities.add("roof.area", model.roof.roofType.id, signedArea(top.thermalOutline) / AREA, ["roof"]);
  return quantities.list();
}

/** Summe einer Menge über alle `ref_id`. */
export function total(quantities: readonly HouseQuantity[], key: string): number {
  return quantities.filter((q) => q.key === key).reduce((sum, q) => sum + q.value, 0);
}
