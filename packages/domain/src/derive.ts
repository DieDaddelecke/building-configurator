// Geometry Engine (P 6): aus Template und aufgelösten Typen das abgeleitete Modell, ganzzahlig in 0,1 mm.
// HM1: ein Geschoss und Flachdach; das Datenmodell trägt schon Geschosse und das Dach (PLAN_HAUSMODELL 6).
import type { HouseRoofType, HouseWallProfile } from "./contract.gen.ts";
import type { ModelErrorCode } from "./codes.ts";
import { ModelError } from "./errors.ts";
import { edgeLength, matchEdges, perimeter, rotate } from "./geometry/edges.ts";
import { offsetPolygon } from "./geometry/offset.ts";
import { polygonDefect, signedArea, toUnits, type Point, type Polygon } from "./geometry/polygon.ts";
import type { CatalogIndex, TemplateIndex } from "./model.ts";
import { assigned, type Resolution } from "./resolve.ts";

export interface LayerGeometry {
  readonly layerId: string;
  readonly materialId: string;
  readonly structural: boolean;
  readonly thermal: boolean;
  /** Abstand der Innen- und Außenkante von der Bezugskontur. */
  readonly inner: number;
  readonly outer: number;
  /** Außenkante der Schicht. */
  readonly outline: Polygon;
  /** Länge der Schicht-Mittellinie (P 7). */
  readonly centerline: number;
}

export interface SegmentGeometry {
  readonly id: string;
  readonly start: Point;
  readonly end: Point;
  readonly length: number;
  /** Kante der Fassadenkontur auf dieser Seite, −1 wenn sie beim Versatz verschwand. */
  readonly facadeEdge: number;
}

export interface LoopGeometry {
  readonly levelId: string;
  readonly reference: Polygon;
  readonly segments: readonly SegmentGeometry[];
  readonly profile: HouseWallProfile;
  readonly layers: readonly LayerGeometry[];
  /** Außenkante der äußersten Schicht; Kante 0 liegt vor Segment 0, soweit es sie gibt. */
  readonly facadeOutline: Polygon;
  /** Außenkante der letzten thermischen Schicht (Dachfläche, P 7). */
  readonly thermalOutline: Polygon;
  /** UK Bodenplatte bis OK Attika (P 7). */
  readonly facadeHeight: number;
  readonly wallThickness: number;
  /** Mittellinie der getragenen Schichten (P 6.2), sonst null. */
  readonly bearingLength: number | null;
  /** Schichten außerhalb der Ankerschicht (P 6.3). */
  readonly revealDepth: number;
}

export interface OpeningGeometry {
  readonly id: string;
  readonly kind: "window" | "door";
  readonly hostKind: "envelope_segment" | "interior_wall";
  readonly hostId: string;
  readonly levelId: string;
  readonly typeId: string;
  readonly width: number;
  readonly height: number;
  /** Sturz der Öffnung in der Wand, einschließlich Rollladenkasten. */
  readonly head: number;
  readonly sill: number;
  readonly shutterBox: number;
  /** Mitte entlang des Hosts und Länge des Hosts. */
  readonly offset: number;
  readonly hostLength: number;
  /** Mitte auf der Bezugskontur bzw. der Wandachse. */
  readonly center: Point;
  /** Wandabzug: Breite × (Höhe + Kasten), Einheiten². */
  readonly area: number;
}

export interface RoofGeometry {
  readonly roofType: HouseRoofType;
  readonly bearing: number;
  readonly slabThickness: number;
  readonly buildUp: number;
  readonly parapetTop: number;
  readonly buildUpTop: number;
  readonly upstand: number;
  readonly top: number;
}

export interface RoomGeometry {
  readonly id: string;
  readonly roomTypeId: string;
  readonly polygon: Polygon;
}

export interface DerivedModel {
  readonly loops: readonly LoopGeometry[];
  readonly openings: readonly OpeningGeometry[];
  readonly roof: RoofGeometry;
  readonly rooms: readonly RoomGeometry[];
  /** Decke des Geschosses: Unterkante der Dachdecke über ±0,00. */
  readonly ceiling: number;
}

function ring(points: readonly { readonly x: number; readonly y: number }[], code: ModelErrorCode): Polygon {
  const polygon = points.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
  const defect = polygonDefect(polygon);
  if (defect) throw new ModelError(code, { defect });
  return polygon;
}

function slabThickness(template: TemplateIndex, kind: "ground" | "roof"): number {
  const slabs = template.template.slabs.filter((slab) => slab.kind === kind);
  if (slabs.length !== 1) throw new ModelError(`${kind}_slab_missing`);
  return toUnits(slabs[0]!.thickness);
}

function layers(profile: HouseWallProfile, reference: Polygon, catalog: CatalogIndex): LayerGeometry[] {
  let inner = 0;
  return profile.layer_ids.map((id) => {
    const layer = catalog.get(catalog.layers, id, "layer_unknown");
    const outer = inner + toUnits(layer.thickness);
    const geometry: LayerGeometry = {
      layerId: layer.id,
      materialId: layer.material_id,
      structural: layer.structural,
      thermal: layer.thermal,
      inner,
      outer,
      outline: offsetPolygon(reference, outer),
      centerline: perimeter(offsetPolygon(reference, Math.round((inner + outer) / 2))),
    };
    inner = outer;
    return geometry;
  });
}

function layerIndex(profile: HouseWallProfile, id: string): number {
  const index = profile.layer_ids.indexOf(id);
  if (index < 0) throw new ModelError("layer_not_in_profile", { profile: profile.id, layer: id });
  return index;
}

export function derive(template: TemplateIndex, catalog: CatalogIndex, resolution: Resolution): DerivedModel {
  const t = template.template;
  if (t.levels.length !== 1 || t.envelope.length !== 1) throw new ModelError("multi_storey_not_supported");
  const groundSlab = slabThickness(template, "ground");
  const roofSlab = slabThickness(template, "roof");
  const bearing = toUnits(t.roof.bearing_height);
  const parapet = toUnits(t.roof.parapet_height);

  const roofType = catalog.get(catalog.roofTypes, assigned(resolution, catalog, "roof", "roof_type_id"), "roof_type_unknown");
  if (roofType.kind !== "flat") throw new ModelError("roof_kind_not_supported", { roof_type: roofType.id });
  const buildUp = roofType.build_up.reduce((sum, layer) => sum + toUnits(layer.thickness), 0);
  const parapetTop = bearing + roofSlab + parapet;
  const buildUpTop = bearing + roofSlab + buildUp;
  const roof: RoofGeometry = {
    roofType,
    bearing,
    slabThickness: roofSlab,
    buildUp,
    parapetTop,
    buildUpTop,
    upstand: parapet - buildUp,
    top: Math.max(parapetTop, buildUpTop),
  };

  const loops = t.envelope.map((loop): LoopGeometry => {
    const reference = ring(loop.inner_polygon, "envelope_invalid");
    if (signedArea(reference) <= 0) throw new ModelError("envelope_not_counter_clockwise");
    const profileIds = new Set(loop.segments.map((s) => assigned(resolution, catalog, s.id, "wall_profile_id")));
    if (profileIds.size !== 1) throw new ModelError("mixed_wall_profiles", { level: loop.level_id });
    const profile = catalog.get(catalog.profiles, [...profileIds][0]!, "wall_profile_unknown");
    const geometry = layers(profile, reference, catalog);
    const outermost = geometry.at(-1)!;
    const edges = matchEdges(reference, outermost.outline, outermost.outer);
    const facadeOutline = rotate(outermost.outline, edges[0] ?? 0);
    const shift = edges[0] !== undefined && edges[0] > 0 ? edges[0] : 0;
    const count = facadeOutline.length;
    const segments = loop.segments.map((segment, i): SegmentGeometry => {
      const start = reference[i]!;
      const end = reference[(i + 1) % reference.length]!;
      const edge = edges[i]!;
      return { id: segment.id, start, end, length: edgeLength(start, end), facadeEdge: edge < 0 ? -1 : (edge - shift + count) % count };
    });
    const thermal = geometry.findLast((layer) => layer.thermal);
    let bearingLength: number | null = null;
    if (profile.bearing) {
      const indices = profile.bearing.supported_layer_ids.map((id) => layerIndex(profile, id));
      const inner = geometry[Math.min(...indices)]!.inner;
      const outer = geometry[Math.max(...indices)]!.outer;
      bearingLength = perimeter(offsetPolygon(reference, Math.round((inner + outer) / 2)));
    }
    const anchor = geometry[layerIndex(profile, profile.opening_anchor_layer_id)]!;
    return {
      levelId: loop.level_id,
      reference,
      segments,
      profile,
      layers: geometry,
      facadeOutline,
      thermalOutline: thermal ? thermal.outline : reference,
      facadeHeight: groundSlab + parapetTop,
      wallThickness: outermost.outer,
      bearingLength,
      revealDepth: outermost.outer - anchor.outer,
    };
  });

  const hosts = new Map<string, { start: Point; end: Point; levelId: string }>();
  for (const loop of loops) {
    for (const segment of loop.segments) hosts.set(segment.id, { start: segment.start, end: segment.end, levelId: loop.levelId });
  }
  for (const wall of t.interior_walls) {
    const [a, b] = wall.axis;
    hosts.set(wall.id, { start: { x: toUnits(a.x), y: toUnits(a.y) }, end: { x: toUnits(b.x), y: toUnits(b.y) }, levelId: wall.level_id });
  }

  const openings = t.openings.map((opening): OpeningGeometry => {
    const host = hosts.get(opening.host_id);
    if (!host) throw new ModelError("host_unknown", { id: opening.id });
    const hostLength = edgeLength(host.start, host.end);
    const offset = toUnits(opening.offset_along_host);
    const center = {
      x: host.start.x + ((host.end.x - host.start.x) * offset) / hostLength,
      y: host.start.y + ((host.end.y - host.start.y) * offset) / hostLength,
    };
    const base = { id: opening.id, kind: opening.kind, hostKind: opening.host_kind, hostId: opening.host_id, levelId: host.levelId, offset, hostLength, center };
    if (opening.kind === "window") {
      const type = catalog.get(catalog.windowTypes, assigned(resolution, catalog, opening.id, "window_type_id"), "window_type_unknown");
      const width = toUnits(type.width);
      const height = toUnits(type.height);
      const shutterBox = toUnits(type.shutter_box_height);
      const windowHead = toUnits(type.head_height);
      return { ...base, typeId: type.id, width, height, shutterBox, head: windowHead + shutterBox, sill: windowHead - height, area: width * (height + shutterBox) };
    }
    const type = catalog.get(catalog.doorTypes, assigned(resolution, catalog, opening.id, "door_type_id"), "door_type_unknown");
    const width = toUnits(type.width);
    const height = toUnits(type.height);
    return { ...base, typeId: type.id, width, height, shutterBox: 0, head: height, sill: 0, area: width * height };
  });

  const rooms = t.rooms.map((room) => ({ id: room.id, roomTypeId: room.room_type_id, polygon: ring(room.polygon, "room_invalid") }));
  return { loops, openings, roof, rooms, ceiling: bearing };
}
