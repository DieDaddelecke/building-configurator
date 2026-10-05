// Hausbeschreibung für die Prüfung auf dem Grundstück in Python (PLAN_HAUSMODELL 3.1, E-HM-4). Fassade und Rollen
// gelten für alle Geschosse: Die Fassade des Geschosses mit der dicksten Wand umschließt die anderen (E-HM-63), die
// Rollen kommen aus dem Erdgeschoss. Die Dachform bleibt die des Kerns; die Begriffe der PLU ordnet Python zu (E-HM-61).
import type { HouseEdgePosition, HouseFacts, HousePoint } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { signedArea, toMetres, UNITS_PER_METRE, type Polygon } from "./geometry/polygon.ts";
import type { TemplateIndex } from "./model.ts";

function metres(polygon: Polygon): HousePoint[] {
  return polygon.map((p) => ({ x: toMetres(p.x), y: toMetres(p.y) }));
}

/** Lage einer Außentür auf der Fassade: Kante und Anteil, gemessen auf der Fassade aller Geschosse. */
function position(model: DerivedModel, openingId: string | null): HouseEdgePosition | null {
  const opening = model.openings.find((o) => o.id === openingId && o.hostKind === "envelope_segment");
  if (!opening) return null;
  const facade = model.loops[model.facadeLoop]!;
  for (const loop of model.loops) {
    const index = loop.segments.findIndex((s) => s.id === opening.hostId);
    const edge = index < 0 ? -1 : facade.segments[index]!.facadeEdge;
    if (edge < 0) continue;
    const a = facade.facadeOutline[edge]!;
    const b = facade.facadeOutline[(edge + 1) % facade.facadeOutline.length]!;
    const t = ((opening.center.x - a.x) * (b.x - a.x) + (opening.center.y - a.y) * (b.y - a.y)) / ((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
    return { edge, position: Math.min(1, Math.max(0, t)) };
  }
  return null;
}

export function houseFacts(model: DerivedModel, template: TemplateIndex): HouseFacts {
  const t = template.template;
  const facade = model.loops[model.facadeLoop]!;
  const roles = t.envelope.find((loop) => loop.level_id === model.loops[0]!.levelId)!.segments;
  const roof = model.roof;
  const floorArea = model.rooms.reduce((sum, room) => sum + signedArea(room.polygon), 0) / UNITS_PER_METRE ** 2;
  const { terrace, carport } = model.site;
  return {
    facade_outline: metres(facade.facadeOutline),
    projection_outline: metres(roof.projection),
    storeys: model.loops.length,
    roof_shape: roof.design.form,
    roof_slopes_deg: roof.pitched ? roof.pitched.faces.map((face) => face.pitchDeg) : [],
    ridge_azimuth_deg: roof.pitched?.ridgeAzimuthDeg ?? null,
    eave_height: toMetres(roof.eave),
    top_height: toMetres(roof.top),
    ground_floor_offset: t.ground_floor_offset,
    floor_area: floorArea,
    facade_roles: facade.segments.flatMap((segment, i) => {
      const role = roles[i]?.facade_role ?? null;
      return role !== null && segment.facadeEdge >= 0 ? [{ edge: segment.facadeEdge, role }] : [];
    }),
    entrance: position(model, t.entrance_opening_id),
    garage_door: position(model, t.garage_door_opening_id),
    facade_material_class: facade.profile.material_class,
    roof_material_class: roof.roofType.material_class,
    terrace: terrace
      ? {
          type_id: terrace.type.id,
          depth: terrace.type.depth,
          width: terrace.width,
          height_above_terrain: terrace.type.height_above_terrain,
          sealing_factor: terrace.type.sealing_factor,
        }
      : null,
    carport: carport ? { type_id: carport.id, spaces: carport.spaces, width: carport.width, depth: carport.depth, height: carport.height } : null,
  };
}
