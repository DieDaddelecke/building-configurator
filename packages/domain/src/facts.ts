// Hausbeschreibung für die Prüfung auf dem Grundstück in Python (PLAN_HAUSMODELL 3.1, E-HM-4).
import type { HouseEdgePosition, HouseFacts, HousePoint } from "./contract.gen.ts";
import type { DerivedModel } from "./derive.ts";
import { offsetPolygon } from "./geometry/offset.ts";
import { signedArea, toMetres, toUnits, UNITS_PER_METRE, type Polygon } from "./geometry/polygon.ts";
import type { TemplateIndex } from "./model.ts";

function metres(polygon: Polygon): HousePoint[] {
  return polygon.map((p) => ({ x: toMetres(p.x), y: toMetres(p.y) }));
}

function position(model: DerivedModel, openingId: string | null): HouseEdgePosition | null {
  const opening = model.openings.find((o) => o.id === openingId && o.hostKind === "envelope_segment");
  if (!opening) return null;
  for (const loop of model.loops) {
    const segment = loop.segments.find((s) => s.id === opening.hostId);
    if (!segment || segment.facadeEdge < 0) continue;
    const a = loop.facadeOutline[segment.facadeEdge]!;
    const b = loop.facadeOutline[(segment.facadeEdge + 1) % loop.facadeOutline.length]!;
    const t = ((opening.center.x - a.x) * (b.x - a.x) + (opening.center.y - a.y) * (b.y - a.y)) / ((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
    return { edge: segment.facadeEdge, position: Math.min(1, Math.max(0, t)) };
  }
  return null;
}

export function houseFacts(model: DerivedModel, template: TemplateIndex): HouseFacts {
  const t = template.template;
  // HM1: ein Geschoss; mit R+1 (HM5) die Vereinigung aller oberirdischen Geschosse
  const loop = model.loops[0]!;
  const overhang = toUnits(t.roof.eave_overhang);
  const projection = overhang > 0 ? offsetPolygon(loop.facadeOutline, overhang) : loop.facadeOutline;
  const floorArea = model.rooms.reduce((sum, room) => sum + signedArea(room.polygon), 0) / UNITS_PER_METRE ** 2;
  return {
    facade_outline: metres(loop.facadeOutline),
    projection_outline: metres(projection),
    storeys: model.loops.length,
    roof_form: "flat",
    roof_slopes_deg: [],
    ridge_direction: null,
    eave_height: toMetres(model.roof.parapetTop),
    top_height: toMetres(model.roof.top),
    ground_floor_offset: t.ground_floor_offset,
    floor_area: floorArea,
    facade_roles: loop.segments.flatMap((segment, i) => {
      const role = t.envelope[0]!.segments[i]!.facade_role;
      return role !== null && segment.facadeEdge >= 0 ? [{ edge: segment.facadeEdge, role }] : [];
    }),
    entrance: position(model, t.entrance_opening_id),
    garage_door: position(model, t.garage_door_opening_id),
    facade_material_class: loop.profile.material_class,
    roof_material_class: model.roof.roofType.material_class,
  };
}
