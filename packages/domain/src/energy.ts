// Bauphysik, vorbereitet (P 11): U-Wert eines Wandprofils nach vereinfachtem Verfahren und Fensterflächenanteil
// je Fassadenrichtung. Ohne Winkelfunktionen, damit jeder Browser dasselbe rechnet.
import type { HouseEnergy, HouseWallProfile, HouseWindowShare } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { ModelError } from "./errors.ts";
import { edgeLength } from "./geometry/edges.ts";
import { UNITS_PER_METRE } from "./geometry/polygon.ts";
import type { CatalogIndex } from "./model.ts";

const AREA = UNITS_PER_METRE * UNITS_PER_METRE;

/** U = 1 / (Rsi + Σ d/λ der thermischen Schichten + Rse); hinter einer Hinterlüftung gilt Rse = Rsi. */
export function wallUValue(profile: HouseWallProfile, catalog: CatalogIndex): number {
  const { surface_resistance_inside: rsi, surface_resistance_outside: rse } = catalog.catalog.parameters;
  const layers = profile.layer_ids.map((id) => catalog.get(catalog.layers, id, "layer_unknown"));
  const lastThermal = layers.findLastIndex((layer) => layer.thermal);
  const ventilated = layers.slice(lastThermal + 1).some((layer) => !layer.thermal);
  let resistance = rsi + (ventilated ? rsi : rse);
  for (const layer of layers.filter((l) => l.thermal)) {
    const conductivity = catalog.get(catalog.materials, layer.material_id, "material_unknown").conductivity;
    if (conductivity === null) throw new ModelError("conductivity_missing", { layer: layer.id });
    resistance += layer.thickness / conductivity;
  }
  return 1 / resistance;
}

/** Himmelsrichtung der Außennormalen einer Kante gegen den Uhrzeigersinn (Modellnord = +y); 45° zählt zu N/S. */
function direction(dx: number, dy: number): HouseWindowShare["direction"] {
  const nx = dy;
  const ny = -dx;
  if (Math.abs(nx) <= Math.abs(ny)) return ny > 0 ? "n" : "s";
  return nx > 0 ? "e" : "w";
}

export function energy(model: DerivedModel, catalog: CatalogIndex): HouseEnergy {
  const profiles = [...new Map(model.loops.map((loop) => [loop.profile.id, loop.profile])).values()];
  const shares = new Map<HouseWindowShare["direction"], { window: number; facade: number }>();
  for (const loop of model.loops) {
    for (const segment of loop.segments) {
      const key = direction(segment.end.x - segment.start.x, segment.end.y - segment.start.y);
      const share = shares.get(key) ?? { window: 0, facade: 0 };
      if (segment.facadeEdge >= 0) {
        const outline = loop.facadeOutline;
        const a = outline[segment.facadeEdge]!;
        const b = outline[(segment.facadeEdge + 1) % outline.length]!;
        share.facade += edgeLength(a, b) * loop.facadeHeight;
      }
      for (const opening of model.openings) {
        if (opening.hostId === segment.id && opening.kind === "window") share.window += opening.width * opening.height;
      }
      shares.set(key, share);
    }
  }
  return {
    wall_u_values: profiles.map((profile) => ({ wall_profile_id: profile.id, u_value: wallUValue(profile, catalog) })),
    window_shares: (["n", "e", "s", "w"] as const)
      .filter((key) => shares.has(key))
      .map((key) => {
        const { window, facade } = shares.get(key)!;
        return { direction: key, window_area: window / AREA, facade_area: facade / AREA, ratio: facade > 0 ? window / facade : 0 };
      }),
  };
}
