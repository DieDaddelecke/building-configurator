// Geometry Engine (P 6): aus Template und aufgelösten Typen das abgeleitete Modell, ganzzahlig in 0,1 mm.
// Geschosse mit derselben Bezugskontur (E-HM-63), das Dach über dem obersten: flach mit Dachdecke und Attika oder
// geneigt nach Ergänzung 11 (roof/build.ts, in Metern). Ein Geschoss reicht von seiner Höhe bis zur Höhe des
// nächsten (die Decke darüber gehört zu ihm), das Erdgeschoss ab Unterkante Bodenplatte.
import type { HouseCarportType, HouseRoofType, HouseTerraceType, HouseWallProfile } from "./contract.gen.ts";
import type { ModelErrorCode } from "./codes.ts";
import { ModelError } from "./errors.ts";
import { edgeLength, matchEdges, perimeter, rotate } from "./geometry/edges.ts";
import { offsetPolygon, unionPolygons } from "./geometry/offset.ts";
import { polygonDefect, signedArea, toMetres, toUnits, UNITS_PER_METRE, type Point, type Polygon } from "./geometry/polygon.ts";
import type { CatalogIndex, TemplateIndex } from "./model.ts";
import { buildRoof, RoofError, type Roof, type RoofDesign } from "./roof/build.ts";
import { assigned, assignedOptional, type Resolution } from "./resolve.ts";

/** Toleranz der Geometrie (P 4): 1 mm. */
const TOLERANCE = 10;
const AREA = UNITS_PER_METRE * UNITS_PER_METRE;

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
  /** Fläche auf der Mittellinie von Unter- bis Oberkante des Geschosses, vor Abzug der Öffnungen, Einheiten² (Ergänzung 5). */
  readonly grossArea: number;
}

export interface SegmentGeometry {
  readonly id: string;
  readonly start: Point;
  readonly end: Point;
  readonly length: number;
  /** Kante der Fassadenkontur auf dieser Seite, −1 wenn sie beim Versatz verschwand. */
  readonly facadeEdge: number;
  /** Fläche der Fassade vor dem Segment (Außenkante, Geschosshöhe), Einheiten². */
  readonly facadeArea: number;
}

export interface LoopGeometry {
  readonly levelId: string;
  /** Höhe des Geschosses über ±0,00. */
  readonly elevation: number;
  readonly reference: Polygon;
  readonly segments: readonly SegmentGeometry[];
  readonly profile: HouseWallProfile;
  readonly layers: readonly LayerGeometry[];
  /** Außenkante der äußersten Schicht; Kante 0 liegt vor Segment 0, soweit es sie gibt. */
  readonly facadeOutline: Polygon;
  /** Außenkante der letzten thermischen Schicht (Dachfläche des Flachdachs, P 7). */
  readonly thermalOutline: Polygon;
  /** Unterkante der Außenwand (Erdgeschoss: UK Bodenplatte) und Oberkante; `null` unter einem geneigten Dach. */
  readonly bottom: number;
  readonly top: number | null;
  readonly wallThickness: number;
  /** Mittellinie der getragenen Schichten (P 6.2), wenn das Geschoss ein eigenes Auflager braucht, sonst null. */
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
  /** Sturz der Öffnung in der Wand, einschließlich Rollladenkasten, über dem Fußboden des Geschosses. */
  readonly head: number;
  readonly sill: number;
  readonly shutterBox: number;
  /**
   * Decke über der Öffnung, über dem Fußboden des Geschosses. Unter einem geneigten Dach dessen tiefste Unterseite
   * über der Öffnungsbreite, an der Außenwand innen und außen gemessen: Das Dach fällt über der Wanddicke ab.
   */
  readonly ceiling: number;
  /** Mitte entlang des Hosts und Länge des Hosts. */
  readonly offset: number;
  readonly hostLength: number;
  /** Mitte auf der Bezugskontur bzw. der Wandachse. */
  readonly center: Point;
  /** Wandabzug: Breite × (Höhe + Kasten), Einheiten². */
  readonly area: number;
}

export interface FlatRoofGeometry {
  readonly slabThickness: number;
  readonly buildUp: number;
  readonly parapetTop: number;
  readonly buildUpTop: number;
  readonly upstand: number;
}

export interface RoofGeometry {
  readonly roofType: HouseRoofType;
  /** Dachform des Katalogs, `null` ohne Slot für die Form. */
  readonly shapeId: string | null;
  readonly design: RoofDesign;
  /** Unterseite des Dachs bzw. Unterkante der Dachdecke auf der Bezugskontur, über ±0,00. */
  readonly bearing: number;
  readonly eaveOverhang: number;
  readonly vergeOverhang: number;
  /** Flachdach, sonst `null`. */
  readonly flat: FlatRoofGeometry | null;
  /** Geneigtes Dach in Metern (roof/build.ts), sonst `null`. */
  readonly pitched: Roof | null;
  /** Höchster Punkt und Traufe (Flachdach: Oberkante Attika), über ±0,00. */
  readonly top: number;
  readonly eave: number;
  /** Fassade mit Dachüberstand im Grundriss. */
  readonly projection: Polygon;
}

export interface RoomGeometry {
  readonly id: string;
  readonly roomTypeId: string;
  readonly polygon: Polygon;
}

export interface SiteGeometry {
  /** Terrasse an der längsten Gartenkante, so breit wie diese (`null` ohne Gartenkante, Ergänzung 7). */
  readonly terrace: { readonly type: HouseTerraceType; readonly width: number | null } | null;
  readonly carport: HouseCarportType | null;
}

export interface DerivedModel {
  /** Nach Höhe sortiert, das Erdgeschoss zuerst. */
  readonly loops: readonly LoopGeometry[];
  /** Geschoss mit der dicksten Wand: seine Fassade umschließt alle anderen (gleiche Bezugskontur). */
  readonly facadeLoop: number;
  readonly openings: readonly OpeningGeometry[];
  readonly roof: RoofGeometry;
  readonly rooms: readonly RoomGeometry[];
  /** UK Bodenplatte bis OK Attika bzw. bis zum Auflager des geneigten Dachs (Kennwert `building.facade_height`). */
  readonly facadeHeight: number;
  readonly site: SiteGeometry;
}

function ring(points: readonly { readonly x: number; readonly y: number }[], code: ModelErrorCode): Polygon {
  const polygon = points.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
  const defect = polygonDefect(polygon);
  if (defect) throw new ModelError(code, { defect });
  return polygon;
}

function slabs(template: TemplateIndex, kind: "ground" | "floor" | "roof", levelId?: string): number {
  const found = template.template.slabs.filter((slab) => slab.kind === kind && (levelId === undefined || slab.level_id === levelId));
  if (found.length !== 1) throw new ModelError(`${kind}_slab_missing`, levelId === undefined ? {} : { level: levelId });
  return toUnits(found[0]!.thickness);
}

function layers(profile: HouseWallProfile, reference: Polygon, catalog: CatalogIndex): Omit<LayerGeometry, "grossArea">[] {
  let inner = 0;
  return profile.layer_ids.map((id) => {
    const layer = catalog.get(catalog.layers, id, "layer_unknown");
    const outer = inner + toUnits(layer.thickness);
    const geometry = {
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

const metres = (p: Point) => ({ x: toMetres(p.x), y: toMetres(p.y) });

/** Fläche zwischen `bottom` und der Oberkante entlang einer Strecke gegen den Uhrzeigersinn, Einheiten². */
function band(a: Point, b: Point, bottom: number, top: number | null, roof: Roof | null): number {
  const length = edgeLength(a, b);
  if (top !== null) return length * (top - bottom);
  const integral = roof!.undersideIntegral(metres(a), metres(b));
  if (integral === null) throw new RoofError("wall_uncovered");
  return integral * AREA - length * bottom;
}

/**
 * Je Geschoss genau eine Hülle, alle mit derselben Bezugskontur wie das Erdgeschoss (1 mm, gleicher Startpunkt).
 * Höhen relativ zum Erdgeschoss: ±0,00 ist Oberkante seiner Bodenplatte (E-HM-35).
 */
function storeys(template: TemplateIndex): { levelId: string; elevation: number; reference: Polygon; loopIndex: number }[] {
  const t = template.template;
  const levels = [...t.levels].sort((a, b) => a.elevation - b.elevation || a.id.localeCompare(b.id));
  const base = toUnits(levels[0]!.elevation);
  const result = levels.map((level) => {
    const loops = t.envelope.flatMap((loop, i) => (loop.level_id === level.id ? [i] : []));
    if (loops.length !== 1) throw new ModelError("storey_envelope_mismatch", { level: level.id });
    const reference = ring(t.envelope[loops[0]!]!.inner_polygon, "envelope_invalid");
    if (signedArea(reference) <= 0) throw new ModelError("envelope_not_counter_clockwise");
    return { levelId: level.id, elevation: toUnits(level.elevation) - base, reference, loopIndex: loops[0]! };
  });
  if (t.envelope.length !== levels.length) throw new ModelError("storey_envelope_mismatch");
  const ground = result[0]!.reference;
  for (const storey of result.slice(1)) {
    const same =
      storey.reference.length === ground.length &&
      storey.reference.every((p, i) => Math.abs(p.x - ground[i]!.x) <= TOLERANCE && Math.abs(p.y - ground[i]!.y) <= TOLERANCE);
    if (!same) throw new ModelError("storey_outlines_differ", { level: storey.levelId });
  }
  return result;
}

export function derive(template: TemplateIndex, catalog: CatalogIndex, resolution: Resolution): DerivedModel {
  const t = template.template;
  const effective = resolution.roof;
  const design = effective.design;
  const flat = design.form === "flat";
  const levels = storeys(template);
  const groundSlab = slabs(template, "ground");
  const bearing = toUnits(t.roof.bearing_height);

  const roofType = catalog.get(catalog.roofTypes, assigned(resolution, catalog, "roof", "roof_type_id"), "roof_type_unknown");
  if ((roofType.kind === "flat") !== flat) throw new ModelError("roof_type_kind_mismatch", { roof_type: roofType.id, form: design.form });
  const buildUp = roofType.build_up.reduce((sum, layer) => sum + toUnits(layer.thickness), 0);

  // Geschosse: Profil, Schichten, Fassade; die Höhen kommen danach, wenn das Dach steht
  const shells = levels.map((storey, index) => {
    const loop = t.envelope[storey.loopIndex]!;
    const reference = storey.reference;
    const profileIds = new Set(loop.segments.map((s) => assigned(resolution, catalog, s.id, "wall_profile_id")));
    if (profileIds.size !== 1) throw new ModelError("mixed_wall_profiles", { level: loop.level_id });
    const profile = catalog.get(catalog.profiles, [...profileIds][0]!, "wall_profile_unknown");
    const geometry = layers(profile, reference, catalog);
    const outermost = geometry.at(-1)!;
    const edges = matchEdges(reference, outermost.outline, outermost.outer);
    const facadeOutline = rotate(outermost.outline, edges[0] ?? 0);
    const shift = edges[0] !== undefined && edges[0] > 0 ? edges[0] : 0;
    const count = facadeOutline.length;
    const facadeEdges = loop.segments.map((_, i) => (edges[i]! < 0 ? -1 : (edges[i]! - shift + count) % count));
    const top = index === levels.length - 1;
    return { storey, loop, profile, geometry, facadeOutline, facadeEdges, top, elevation: storey.elevation, index };
  });
  const topShell = shells.at(-1)!;
  const topWall = topShell.geometry.at(-1)!.outer;

  // Dach über dem obersten Geschoss
  let flatRoof: FlatRoofGeometry | null = null;
  let pitched: Roof | null = null;
  let roofTop: number;
  let roofEave: number;
  if (flat) {
    const slabThickness = effective.slabThickness === null ? slabs(template, "roof") : toUnits(effective.slabThickness);
    const parapet = toUnits(effective.parapetHeight);
    const parapetTop = bearing + slabThickness + parapet;
    const buildUpTop = bearing + slabThickness + buildUp;
    flatRoof = { slabThickness, buildUp, parapetTop, buildUpTop, upstand: parapet - buildUp };
    roofTop = Math.max(parapetTop, buildUpTop);
    roofEave = parapetTop;
  } else {
    pitched = buildRoof({
      contour: topShell.storey.reference,
      bearing: t.roof.bearing_height,
      wallThickness: toMetres(topWall),
      eaveOverhang: effective.eaveOverhang,
      vergeOverhang: effective.vergeOverhang,
      design,
      thickness: toMetres(buildUp),
    });
    roofTop = pitched.top * UNITS_PER_METRE;
    roofEave = pitched.eave * UNITS_PER_METRE;
  }

  // Ein eigenes Auflager braucht das Erdgeschoss und jedes Geschoss, dessen Profil sich von dem darunter unterscheidet
  const loops = shells.map((shell): LoopGeometry => {
    const { profile, geometry, storey, loop } = shell;
    const reference = storey.reference;
    const bottom = shell.index === 0 ? -groundSlab : shell.elevation;
    const top = shell.top ? (flatRoof ? flatRoof.parapetTop : null) : shells[shell.index + 1]!.elevation;
    const roof = shell.top ? pitched : null;
    const layerGeometry = geometry.map((layer): LayerGeometry => {
      const centerline = offsetPolygon(reference, Math.round((layer.inner + layer.outer) / 2));
      let grossArea = 0;
      centerline.forEach((a, i) => (grossArea += band(a, centerline[(i + 1) % centerline.length]!, bottom, top, roof)));
      return { ...layer, grossArea };
    });
    const segments = loop.segments.map((segment, i): SegmentGeometry => {
      const start = reference[i]!;
      const end = reference[(i + 1) % reference.length]!;
      const edge = shell.facadeEdges[i]!;
      const facadeArea =
        edge < 0 ? 0 : band(shell.facadeOutline[edge]!, shell.facadeOutline[(edge + 1) % shell.facadeOutline.length]!, bottom, top, roof);
      return { id: segment.id, start, end, length: edgeLength(start, end), facadeEdge: edge, facadeArea };
    });
    const thermal = geometry.findLast((layer) => layer.thermal);
    let bearingLength: number | null = null;
    const below = shell.index > 0 ? shells[shell.index - 1]!.profile.id : null;
    if (profile.bearing && profile.id !== below) {
      const indices = profile.bearing.supported_layer_ids.map((id) => layerIndex(profile, id));
      const inner = geometry[Math.min(...indices)]!.inner;
      const outer = geometry[Math.max(...indices)]!.outer;
      bearingLength = perimeter(offsetPolygon(reference, Math.round((inner + outer) / 2)));
    }
    const anchor = geometry[layerIndex(profile, profile.opening_anchor_layer_id)]!;
    const outermost = geometry.at(-1)!;
    return {
      levelId: loop.level_id,
      elevation: shell.elevation,
      reference,
      segments,
      profile,
      layers: layerGeometry,
      facadeOutline: shell.facadeOutline,
      thermalOutline: thermal ? thermal.outline : reference,
      bottom,
      top,
      wallThickness: outermost.outer,
      bearingLength,
      revealDepth: outermost.outer - anchor.outer,
    };
  });

  const facadeLoop = loops.reduce((best, loop, i) => (loop.wallThickness > loops[best]!.wallThickness ? i : best), 0);
  const facade = loops[facadeLoop]!.facadeOutline;
  const eaveOverhang = toUnits(effective.eaveOverhang);
  let projection: Polygon;
  if (pitched) {
    // Gerundet auf 0,1 mm; dabei zusammenfallende Ecken entfallen
    const outline = pitched.outline
      .map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }))
      .filter((p, i, all) => {
        const next = all[(i + 1) % all.length]!;
        return p.x !== next.x || p.y !== next.y;
      });
    projection = unionPolygons([facade, outline]);
  } else {
    projection = eaveOverhang > 0 ? offsetPolygon(facade, eaveOverhang) : facade;
  }

  // Öffnungen: Lage auf dem Host, Maße des Typs, Decke über dem Geschoss
  const level = new Map(loops.map((loop, i) => [loop.levelId, i]));
  type Host = { start: Point; end: Point; levelId: string; thickness: number };
  const hosts = new Map<string, Host>();
  for (const loop of loops) {
    for (const segment of loop.segments) hosts.set(segment.id, { start: segment.start, end: segment.end, levelId: loop.levelId, thickness: loop.wallThickness });
  }
  for (const wall of t.interior_walls) {
    const [a, b] = wall.axis;
    hosts.set(wall.id, { start: { x: toUnits(a.x), y: toUnits(a.y) }, end: { x: toUnits(b.x), y: toUnits(b.y) }, levelId: wall.level_id, thickness: 0 });
  }
  const ceilingOf = (levelId: string, host: Host, from: number, to: number): number => {
    const i = level.get(levelId) ?? 0;
    const loop = loops[i]!;
    if (i < loops.length - 1) {
      const next = loops[i + 1]!;
      return next.elevation - slabs(template, "floor", next.levelId) - loop.elevation;
    }
    if (!pitched) return bearing - loop.elevation;
    const length = edgeLength(host.start, host.end);
    const dx = (host.end.x - host.start.x) / length;
    const dy = (host.end.y - host.start.y) / length;
    // Punkt auf dem Host, um `out` nach außen versetzt (rechts der Kante gegen den Uhrzeigersinn)
    const at = (s: number, out: number) => {
      const along = Math.min(length, Math.max(0, s));
      return metres({ x: host.start.x + dx * along + dy * out, y: host.start.y + dy * along - dx * out });
    };
    const lowest = (host.thickness > 0 ? [0, host.thickness] : [0])
      .map((out) => (from < to ? pitched.undersideMin(at(from, out), at(to, out)) : null))
      .filter((z): z is number => z !== null);
    return (lowest.length ? Math.min(...lowest) : t.roof.bearing_height) * UNITS_PER_METRE - loop.elevation;
  };
  // Decken zwischen den Geschossen: fehlt eine, rechnet das Modell nicht
  for (const loop of loops.slice(1)) slabs(template, "floor", loop.levelId);

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
      return {
        ...base,
        typeId: type.id,
        width,
        height,
        shutterBox,
        head: windowHead + shutterBox,
        sill: windowHead - height,
        ceiling: ceilingOf(host.levelId, host, offset - width / 2, offset + width / 2),
        area: width * (height + shutterBox),
      };
    }
    const type = catalog.get(catalog.doorTypes, assigned(resolution, catalog, opening.id, "door_type_id"), "door_type_unknown");
    const width = toUnits(type.width);
    const height = toUnits(type.height);
    return {
      ...base,
      typeId: type.id,
      width,
      height,
      shutterBox: 0,
      head: height,
      sill: 0,
      ceiling: ceilingOf(host.levelId, host, offset - width / 2, offset + width / 2),
      area: width * height,
    };
  });

  // Nebenbauten: Terrasse an der längsten Gartenkante der Fassade (Rollen aus dem Erdgeschoss)
  const terraceId = assignedOptional(resolution, catalog, "site", "terrace_type_id");
  const carportId = assignedOptional(resolution, catalog, "site", "carport_type_id");
  let terrace: SiteGeometry["terrace"] = null;
  if (terraceId !== null) {
    const type = catalog.get(catalog.terraceTypes, terraceId, "terrace_type_unknown");
    terrace = { type, width: gardenLength(template, loops, facadeLoop) };
  }
  const carport = carportId === null ? null : catalog.get(catalog.carportTypes, carportId, "carport_type_unknown");

  const rooms = t.rooms.map((room) => ({ id: room.id, roomTypeId: room.room_type_id, polygon: ring(room.polygon, "room_invalid") }));
  return {
    loops,
    facadeLoop,
    openings,
    roof: {
      roofType,
      shapeId: effective.shapeId,
      design,
      bearing,
      eaveOverhang,
      vergeOverhang: toUnits(effective.vergeOverhang),
      flat: flatRoof,
      pitched,
      top: roofTop,
      eave: roofEave,
      projection,
    },
    rooms,
    facadeHeight: groundSlab + (flatRoof ? flatRoof.parapetTop : bearing),
    site: { terrace, carport },
  };
}

/** Länge der längsten Fassadenkante mit der Rolle `garden` in Metern, sonst `null`. */
function gardenLength(template: TemplateIndex, loops: readonly LoopGeometry[], facadeLoop: number): number | null {
  const roles = template.template.envelope.find((loop) => loop.level_id === loops[0]!.levelId)!.segments;
  const loop = loops[facadeLoop]!;
  let best: number | null = null;
  loop.segments.forEach((segment, i) => {
    if (roles[i]?.facade_role !== "garden" || segment.facadeEdge < 0) return;
    const a = loop.facadeOutline[segment.facadeEdge]!;
    const b = loop.facadeOutline[(segment.facadeEdge + 1) % loop.facadeOutline.length]!;
    const length = edgeLength(a, b) / UNITS_PER_METRE;
    if (best === null || length > best) best = length;
  });
  return best;
}
