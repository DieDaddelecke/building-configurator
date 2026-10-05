// Geneigtes Dach aus Form und Parametern (docs/PLAN_HAUSMODELL.md Ergänzung 4 und 11, Kapitel 10).
//
// 1. Kanten der Bezugskontur auf einer Geraden zusammenfassen (Folgerung 1).
// 2. Je Form Traufe oder Giebel je Kante: Giebel nur an Flügelenden (Kante mit zwei ausspringenden Ecken), nie zwei
//    Giebel nebeneinander (Folgerung 2). Ohne Drehung liegt der First längs der längeren Seite jedes Flügels.
// 3. Traufkontur: jede Kante um Wanddicke und Überstand nach außen (Traufe: `eaveOverhang`, Giebel: Ortgang).
//    Alle Traufkanten haben dieselbe Neigung und denselben Überstand, Giebel stehen senkrecht: Dann ist das Skelett
//    der Traufkontur genau das über die Bezugskontur hinaus verlängerte Dach (Folgerung 4).
// 4. Die Ebenen gehen auf der Bezugskontur durch die Auflagerhöhe: Unterseite des Dachs (Probedatei 2). Der Aufbau
//    liegt mit seiner Dicke senkrecht zur Fläche darüber, an der Traufe lotrecht geschnitten.
import { sloped, SkeletonError, vertical, weightedSkeleton, type EdgeProfile, type SkeletonErrorCode, type Vec, type Vec3 } from "./skeleton.ts";
import { ROOF_REFUSALS, type RoofRefusal } from "../codes.ts";
import { toMetres, type Polygon } from "../geometry/polygon.ts";

export type RoofForm = "flat" | "mono_pitch" | "gable" | "hip" | "half_hip" | "mansard" | "mansard_gable";
export type RoofRotation = 0 | 90 | 180 | 270;

/**
 * Form mit Parametern. `pitchDeg`: Traufflächen (Mansarde: unten). `upperPitchDeg`: Krüppelwalm bzw. oberer
 * Mansardenabschnitt. `breakHeight`: Krüppel- bzw. Knickhöhe über dem Auflager auf der Bezugskontur.
 */
export interface RoofDesign {
  readonly form: RoofForm;
  readonly pitchDeg: number | null;
  readonly upperPitchDeg: number | null;
  readonly breakHeight: number | null;
  readonly rotation: RoofRotation;
}

export interface RoofInput {
  /** Bezugskontur in 0,1 mm, gegen den Uhrzeigersinn. */
  readonly contour: Polygon;
  /** Unterseite des Dachs auf der Bezugskontur über ±0,00, in m. */
  readonly bearing: number;
  readonly wallThickness: number;
  readonly eaveOverhang: number;
  readonly vergeOverhang: number;
  readonly design: RoofDesign;
  /** Dicke des Aufbaus senkrecht zur Fläche, in m. */
  readonly thickness: number;
}

export type RoofErrorCode =
  | SkeletonErrorCode
  | "design_incomplete"
  | "no_gable_edge"
  | "gables_adjacent"
  | "no_eave_edge"
  | "outline_invalid"
  | "break_too_low"
  | "break_too_high"
  | "wall_uncovered";

/** Die Form lässt sich auf diesem Grundriss nicht erzeugen (Ergänzung 4: gesperrt mit Begründung). */
export class RoofError extends Error {
  readonly code: RoofErrorCode;

  constructor(code: RoofErrorCode) {
    super(code);
    this.code = code;
  }
}

/** Grund für die Oberfläche: die Codes des Skeletts (und eine nicht überdeckte Wand) sind Fehler des Verfahrens. */
export function roofRefusal(code: RoofErrorCode): RoofRefusal {
  return (ROOF_REFUSALS as readonly string[]).includes(code) ? (code as RoofRefusal) : "skeleton_failed";
}

export type RoofLineKind = "ridge" | "hip" | "valley" | "eave" | "verge" | "break";
export const ROOF_LINE_KINDS: readonly RoofLineKind[] = ["ridge", "hip", "valley", "eave", "verge", "break"];

export interface RoofFace {
  /** Kanten der Bezugskontur, zu denen die Fläche gehört (zusammengefasste Kanten auf einer Geraden). */
  readonly contourEdges: readonly number[];
  readonly segment: number;
  readonly pitchDeg: number;
  /** Unterseite, gegen den Uhrzeigersinn von oben gesehen, Höhen über ±0,00, in m. */
  readonly polygon: readonly Vec3[];
  /** Fläche geneigt bzw. im Grundriss, m². */
  readonly area: number;
  readonly planArea: number;
}

export interface RoofLine {
  readonly kind: RoofLineKind;
  readonly a: Vec3;
  readonly b: Vec3;
  readonly length: number;
}

export interface Roof {
  readonly faces: readonly RoofFace[];
  readonly lines: readonly RoofLine[];
  /** Traufkontur (Außenkante des Dachs im Grundriss), m, gegen den Uhrzeigersinn. */
  readonly outline: readonly Vec[];
  /** Je Kante der Bezugskontur: Traufe oder Giebel. */
  readonly edgeKinds: readonly ("eave" | "gable")[];
  /** Oberkante des Aufbaus: höchster Punkt und an der niedrigsten Traufe, über ±0,00. */
  readonly top: number;
  readonly eave: number;
  /** Richtung des längsten Firsts als Azimut 0–180° (0 = +y, im Uhrzeigersinn), ohne First `null`. */
  readonly ridgeAzimuthDeg: number | null;
  /** Giebelwände: Fläche auf der Bezugskontur zwischen Auflager und Unterseite des Dachs an den Giebelkanten, m². */
  readonly gableArea: number;
  /**
   * Integral der Höhe der Unterseite entlang einer Strecke (m²) bzw. ihr Minimum (m); `null`, wenn die Strecke nicht
   * ganz unter dem Dach liegt. Die Strecke ist eine Kante einer Kontur gegen den Uhrzeigersinn: Die Fläche darüber
   * wird 0,1 mm links davon gesucht, also innen, damit eine Fassadenkante auf der Traufkontur (Überstand 0) unter dem
   * Dach liegt; die Höhe gilt auf der Strecke selbst.
   */
  readonly undersideIntegral: (a: Vec, b: Vec) => number | null;
  readonly undersideMin: (a: Vec, b: Vec) => number | null;
}

/** 1 mm: Gleichstand von Längen, Höhen und Linien. */
const TOL = 1e-3;
const ON_LINE = 1e-6;
/** Abstand nach innen, in dem Höhen unter dem Dach gemessen werden: 0,1 mm. */
const INSIDE = 1e-4;

const sub = (a: Vec, b: Vec): Vec => ({ x: a.x - b.x, y: a.y - b.y });
const dot = (a: Vec, b: Vec) => a.x * b.x + a.y * b.y;
const cross = (a: Vec, b: Vec) => a.x * b.y - a.y * b.x;
const length2 = (a: Vec, b: Vec) => Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
const length3 = (a: Vec3, b: Vec3) => Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2);
const radians = (deg: number) => (deg * Math.PI) / 180;
const tan = (deg: number) => Math.tan(radians(deg));

function area2(points: readonly Vec[]): number {
  let twice = 0;
  for (let i = 0; i < points.length; i++) twice += cross(points[i]!, points[(i + 1) % points.length]!);
  return twice / 2;
}

interface Merged {
  /** Ecken in m. */
  readonly points: Vec[];
  /** Je zusammengefasster Kante die Kanten der Bezugskontur. */
  readonly members: number[][];
}

/** Kanten auf einer Geraden zusammenfassen, exakt in Ganzzahlen. */
export function mergeCollinear(contour: Polygon): Merged {
  const n = contour.length;
  const keep = contour.map((p, i) => {
    const a = contour[(i - 1 + n) % n]!;
    const b = contour[(i + 1) % n]!;
    return (p.x - a.x) * (b.y - p.y) - (p.y - a.y) * (b.x - p.x) !== 0;
  });
  const first = keep.indexOf(true);
  const points: Vec[] = [];
  const members: number[][] = [];
  if (first < 0) return { points, members };
  for (let k = 0; k < n; k++) {
    const i = (first + k) % n;
    if (keep[i]) {
      points.push({ x: toMetres(contour[i]!.x), y: toMetres(contour[i]!.y) });
      members.push([]);
    }
    members.at(-1)!.push(i);
  }
  return { points, members };
}

interface Frame {
  readonly d: Vec[];
  /** Normale nach innen. */
  readonly n: Vec[];
  readonly length: number[];
}

function frame(points: readonly Vec[]): Frame {
  const d: Vec[] = [];
  const n: Vec[] = [];
  const length: number[] = [];
  points.forEach((p, i) => {
    const q = points[(i + 1) % points.length]!;
    const l = length2(p, q);
    const u = { x: (q.x - p.x) / l, y: (q.y - p.y) / l };
    d.push(u);
    n.push({ x: -u.y, y: u.x });
    length.push(l);
  });
  return { d, n, length };
}

/** Kürzester Weg nach innen bis zur Kontur, gemessen an Anfang, Mitte und Ende der Kante. */
function depth(points: readonly Vec[], f: Frame, e: number): number {
  const p = points[e]!;
  let best = Infinity;
  for (const s of [0.001, 0.5, 0.999]) {
    const origin = { x: p.x + f.d[e]!.x * f.length[e]! * s, y: p.y + f.d[e]!.y * f.length[e]! * s };
    points.forEach((a, j) => {
      if (j === e) return;
      const ab = sub(points[(j + 1) % points.length]!, a);
      const denom = cross(f.n[e]!, ab);
      if (Math.abs(denom) < 1e-12) return;
      const ao = sub(a, origin);
      const t = cross(ao, ab) / denom;
      const u = cross(ao, f.n[e]!) / denom;
      if (t > ON_LINE && u >= -1e-9 && u <= 1 + 1e-9) best = Math.min(best, t);
    });
  }
  return best;
}

/** Traufe oder Giebel je (zusammengefasster) Kante; wirft, wenn die Form auf dem Grundriss nicht entsteht. */
export function edgeKinds(points: readonly Vec[], design: RoofDesign): ("eave" | "gable")[] {
  const f = frame(points);
  const n = points.length;
  const convex = points.map((_, i) => cross(f.d[(i - 1 + n) % n]!, f.d[i]!) > 0);
  switch (design.form) {
    case "flat":
    case "hip":
    case "mansard":
      return points.map(() => "eave");
    case "mono_pitch": {
      // Traufe auf der Seite, zu der die Außennormale der längsten Kante zeigt, gedreht gegen den Uhrzeigersinn
      const longest = f.length.reduce((best, l, i) => (l > f.length[best]! + 1e-9 ? i : best), 0);
      let dir = { x: -f.n[longest]!.x, y: -f.n[longest]!.y };
      for (let k = 0; k < design.rotation / 90; k++) dir = { x: -dir.y, y: dir.x };
      const reach = Math.max(...points.map((p) => dot(p, dir)));
      const kinds = points.map((p, i): "eave" | "gable" => {
        const facing = -dot(f.n[i]!, dir) > Math.cos(radians(0.5));
        return facing && dot(p, dir) >= reach - TOL ? "eave" : "gable";
      });
      if (!kinds.includes("eave")) throw new RoofError("no_eave_edge");
      return kinds;
    }
    case "gable":
    case "half_hip":
    case "mansard_gable": {
      const rotated = design.rotation === 90 || design.rotation === 270;
      const kinds = points.map((_, i): "eave" | "gable" => {
        if (!convex[i] || !convex[(i + 1) % n]) return "eave";
        const l = f.length[i]!;
        const deep = depth(points, f, i);
        const alongY = Math.abs(f.d[i]!.x) < Math.abs(f.d[i]!.y);
        // Giebel am kurzen Ende des Flügels; bei gleichem Maß stehen die Giebel quer zur x-Achse
        if (Math.abs(l - deep) <= TOL) return alongY !== rotated ? "gable" : "eave";
        return l < deep !== rotated ? "gable" : "eave";
      });
      if (!kinds.includes("gable")) throw new RoofError("no_gable_edge");
      if (kinds.some((k, i) => k === "gable" && kinds[(i + 1) % n] === "gable")) throw new RoofError("gables_adjacent");
      return kinds;
    }
  }
}

/** Kontur mit je Kante eigenem Versatz nach außen (Ecken als Schnitt der versetzten Geraden). */
function offsetLines(points: readonly Vec[], f: Frame, distances: readonly number[]): Vec[] {
  const n = points.length;
  return points.map((_, i) => {
    const j = (i - 1 + n) % n;
    const pj = { x: points[j]!.x - f.n[j]!.x * distances[j]!, y: points[j]!.y - f.n[j]!.y * distances[j]! };
    const pi = { x: points[i]!.x - f.n[i]!.x * distances[i]!, y: points[i]!.y - f.n[i]!.y * distances[i]! };
    const t = cross(sub(pi, pj), f.d[i]!) / cross(f.d[j]!, f.d[i]!);
    return { x: pj.x + f.d[j]!.x * t, y: pj.y + f.d[j]!.y * t };
  });
}

/** Keine zwei nicht benachbarten Kanten berühren sich (auf einer Geraden: nur, wenn sie sich überlappen). */
function simple(points: readonly Vec[]): boolean {
  const n = points.length;
  const side = (a: Vec, b: Vec, c: Vec) => {
    const l = length2(a, b);
    const s = cross(sub(b, a), sub(c, a)) / l;
    return Math.abs(s) < ON_LINE ? 0 : Math.sign(s);
  };
  for (let i = 0; i < n; i++) {
    const a = points[i]!;
    const b = points[(i + 1) % n]!;
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      const c = points[j]!;
      const d = points[(j + 1) % n]!;
      const o1 = side(a, b, c);
      const o2 = side(a, b, d);
      const o3 = side(c, d, a);
      const o4 = side(c, d, b);
      if (o1 * o2 < 0 && o3 * o4 < 0) return false;
      if ((o1 === 0 && onSegment(c, a, b)) || (o2 === 0 && onSegment(d, a, b)) || (o3 === 0 && onSegment(a, c, d)) || (o4 === 0 && onSegment(b, c, d))) {
        return false;
      }
    }
  }
  return true;
}

interface Plane {
  /** Einheitsnormale nach oben. */
  readonly normal: Vec3;
  readonly origin: Vec3;
}

/** Ebene nach Newell: robust auch bei nahezu kollinearen Punkten. */
function planeOf(polygon: readonly Vec3[]): Plane {
  let nx = 0;
  let ny = 0;
  let nz = 0;
  polygon.forEach((p, i) => {
    const q = polygon[(i + 1) % polygon.length]!;
    nx += (p.y - q.y) * (p.z + q.z);
    ny += (p.z - q.z) * (p.x + q.x);
    nz += (p.x - q.x) * (p.y + q.y);
  });
  const l = Math.sqrt(nx * nx + ny * ny + nz * nz);
  const k = polygon.length;
  const origin = polygon.reduce((s, p) => ({ x: s.x + p.x / k, y: s.y + p.y / k, z: s.z + p.z / k }), { x: 0, y: 0, z: 0 });
  return { normal: { x: nx / l, y: ny / l, z: nz / l }, origin };
}

function heightOn(pl: Plane, p: Vec): number {
  return pl.origin.z - (pl.normal.x * (p.x - pl.origin.x) + pl.normal.y * (p.y - pl.origin.y)) / pl.normal.z;
}

function inside(p: Vec, polygon: readonly Vec[]): boolean {
  let result = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]!;
    const b = polygon[j]!;
    if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) result = !result;
  }
  return result;
}

function onSegment(p: Vec, a: Vec, b: Vec, eps = ON_LINE): boolean {
  const l = length2(a, b);
  if (l < eps) return length2(p, a) < eps;
  const u = { x: (b.x - a.x) / l, y: (b.y - a.y) / l };
  const s = dot(sub(p, a), u);
  return Math.abs(cross(u, sub(p, a))) < eps && s > -eps && s < l + eps;
}

/** Anteile [s0, s1] (0–1) einer Strecke innerhalb eines Polygons. */
function within(a: Vec, b: Vec, polygon: readonly Vec[]): [number, number][] {
  const ab = sub(b, a);
  const cuts = [0, 1];
  polygon.forEach((c, i) => {
    const cd = sub(polygon[(i + 1) % polygon.length]!, c);
    const denom = cross(ab, cd);
    if (Math.abs(denom) < 1e-15) return;
    const ac = sub(c, a);
    const s = cross(ac, cd) / denom;
    const u = cross(ac, ab) / denom;
    if (s > 0 && s < 1 && u >= -1e-12 && u <= 1 + 1e-12) cuts.push(s);
  });
  cuts.sort((x, y) => x - y);
  const out: [number, number][] = [];
  for (let k = 1; k < cuts.length; k++) {
    const s0 = cuts[k - 1]!;
    const s1 = cuts[k]!;
    if (s1 - s0 < 1e-12) continue;
    const m = (s0 + s1) / 2;
    if (inside({ x: a.x + ab.x * m, y: a.y + ab.y * m }, polygon)) out.push([s0, s1]);
  }
  return out;
}

function complete(design: RoofDesign): boolean {
  const angle = (deg: number | null) => deg !== null && deg > 0 && deg < 90;
  if (!angle(design.pitchDeg)) return false;
  if (design.form === "half_hip" || design.form === "mansard" || design.form === "mansard_gable") {
    return angle(design.upperPitchDeg) && design.breakHeight !== null && design.breakHeight > 0;
  }
  return true;
}

function profilesFor(input: RoofInput, kinds: readonly ("eave" | "gable")[], h0: number): EdgeProfile[] {
  const { design, bearing, wallThickness, vergeOverhang } = input;
  const pitch = design.pitchDeg!;
  return kinds.map((kind): EdgeProfile => {
    if (kind === "eave") {
      if (design.form === "mansard" || design.form === "mansard_gable") {
        return [sloped(pitch, bearing + design.breakHeight! - h0), sloped(design.upperPitchDeg!)];
      }
      return [sloped(pitch)];
    }
    if (design.form === "half_hip") {
      // Der Walm beginnt auf der Bezugskontur in der Krüppelhöhe; auf der Ortganglinie entsprechend tiefer
      const upper = design.upperPitchDeg!;
      const kink = bearing + design.breakHeight! - (wallThickness + vergeOverhang) * tan(upper) - h0;
      if (kink <= TOL) throw new RoofError("break_too_low");
      return [vertical(kink), sloped(upper)];
    }
    return [vertical()];
  });
}

interface SlopedFace {
  readonly polygon: Vec3[];
  readonly plane: Plane;
  readonly edge: number;
  readonly segment: number;
  readonly pitchDeg: number;
}

/** Punkt im Inneren der Fläche neben der Mitte der Strecke a–b (im Grundriss, Abstand `by`). */
function besides(a: Vec, b: Vec, polygon: readonly Vec[], by: number): Vec {
  const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  const l = length2(a, b);
  let n = { x: -(b.y - a.y) / l, y: (b.x - a.x) / l };
  if (!inside({ x: m.x + n.x * 1e-4, y: m.y + n.y * 1e-4 }, polygon)) n = { x: -n.x, y: -n.y };
  return { x: m.x + n.x * by, y: m.y + n.y * by };
}

/** Steigt die Fläche von der Strecke aus nach innen? */
function rises(face: SlopedFace, a: Vec3, b: Vec3): boolean {
  const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  return heightOn(face.plane, besides(a, b, face.polygon, 1e-3)) > heightOn(face.plane, m);
}

interface ClassifiedLine extends RoofLine {
  readonly faces: readonly number[];
}

/** Linienart jeder Kante der Flächen: am Rand der Traufkontur oder zwischen zwei Flächen (einmal je Paar). */
function classify(faces: readonly SlopedFace[], outline: readonly Vec[]): ClassifiedLine[] {
  const lines: ClassifiedLine[] = [];
  faces.forEach((face, fi) => {
    const ring = face.polygon;
    ring.forEach((a, k) => {
      const b = ring[(k + 1) % ring.length]!;
      const horizontal = Math.abs(a.z - b.z) < TOL;
      const length = length3(a, b);
      if (length < ON_LINE) return;
      const onOutline = outline.some((c, j) => {
        const d = outline[(j + 1) % outline.length]!;
        return onSegment(a, c, d) && onSegment(b, c, d);
      });
      if (onOutline) {
        const kind: RoofLineKind = !horizontal ? "verge" : rises(face, a, b) ? "eave" : "ridge";
        lines.push({ kind, a, b, length, faces: [fi] });
        return;
      }
      const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
      const other = faces.findIndex(
        (g, gi) =>
          gi !== fi &&
          Math.abs(heightOn(g.plane, m) - m.z) < TOL &&
          g.polygon.some((p, q) => onSegment(m, p, g.polygon[(q + 1) % g.polygon.length]!)),
      );
      // Jede innere Strecke einmal, von der Fläche mit dem kleineren Index aus; gleiche Ebenen haben keine Linie
      if (other < fi) return;
      const g = faces[other]!;
      const n1 = face.plane.normal;
      const n2 = g.plane.normal;
      if (Math.abs(n1.x - n2.x) + Math.abs(n1.y - n2.y) + Math.abs(n1.z - n2.z) < 1e-9) return;
      let kind: RoofLineKind;
      if (horizontal) {
        const upF = rises(face, a, b);
        const upG = rises(g, a, b);
        kind = !upF && !upG ? "ridge" : upF && upG ? "valley" : "break";
      } else {
        // Grat: die Nachbarebene liegt über dieser Fläche (das Dach ist dort das Minimum der Ebenen)
        const p = besides(a, b, ring, 1e-2);
        kind = heightOn(g.plane, p) > heightOn(face.plane, p) ? "hip" : "valley";
      }
      lines.push({ kind, a, b, length, faces: [fi, other] });
    });
  });
  return lines;
}

export function buildRoof(input: RoofInput): Roof {
  const { design } = input;
  if (design.form === "flat") throw new Error("buildRoof: das Flachdach rechnet derive");
  if (!complete(design)) throw new RoofError("design_incomplete");
  const merged = mergeCollinear(input.contour);
  const points = merged.points;
  if (points.length < 3) throw new RoofError("outline_invalid");
  const f = frame(points);
  const kinds = edgeKinds(points, design);
  const distances = kinds.map((k) => input.wallThickness + (k === "eave" ? input.eaveOverhang : input.vergeOverhang));
  const outline = offsetLines(points, f, distances);
  const of = frame(outline);
  if (area2(outline) <= 0 || !simple(outline) || of.d.some((d, i) => dot(d, f.d[i]!) <= 0)) throw new RoofError("outline_invalid");

  // Höhe der Traufkontur: von dort steigt die Traufebene bis zur Bezugskontur auf die Auflagerhöhe
  const h0 = input.bearing - (input.wallThickness + input.eaveOverhang) * tan(design.pitchDeg!);
  const sloping: SlopedFace[] = [];
  if (design.form === "mono_pitch") {
    // Eine Ebene über der ganzen Traufkontur. Das Skelett verlängerte an einspringenden Ecken neben senkrechten
    // Kanten die Wand über die Ecke hinaus und deckte dahinter liegende Teile nicht ab.
    const first = kinds.indexOf("eave");
    const out = { x: -f.n[first]!.x, y: -f.n[first]!.y };
    const reach = dot(outline[first]!, out);
    const lift = (p: Vec): Vec3 => ({ x: p.x, y: p.y, z: h0 + (reach - dot(p, out)) * tan(design.pitchDeg!) });
    const polygon = outline.map(lift);
    sloping.push({ polygon, plane: planeOf(polygon), edge: first, segment: 0, pitchDeg: design.pitchDeg! });
  } else {
    const profiles = profilesFor(input, kinds, h0);
    let raw;
    try {
      raw = weightedSkeleton(outline, profiles);
    } catch (error) {
      if (error instanceof SkeletonError) throw new RoofError(error.code);
      throw error;
    }
    for (const face of raw) {
      const segment = profiles[face.edge]![face.segment]!;
      for (const loop of face.loops) {
        const polygon = loop.map((p) => ({ x: p.x, y: p.y, z: p.z + h0 }));
        // Senkrechte Abschnitte (Giebel) sind keine Dachflächen; ihre Fläche folgt unten aus der Unterseite
        if (!Number.isFinite(segment.slope)) continue;
        const oriented = area2(polygon) < 0 ? [...polygon].reverse() : polygon;
        if (area2(oriented) < 1e-9) continue;
        sloping.push({ polygon: oriented, plane: planeOf(oriented), edge: face.edge, segment: face.segment, pitchDeg: segment.pitchDeg });
      }
    }
  }
  // Krüppelwalm und Mansarde: der obere Abschnitt muss entstehen, sonst ist es eine andere Form
  if (design.form === "half_hip") {
    kinds.forEach((k, i) => {
      if (k === "gable" && !sloping.some((s) => s.edge === i && s.segment === 1)) throw new RoofError("break_too_high");
    });
  }
  if ((design.form === "mansard" || design.form === "mansard_gable") && !sloping.some((s) => s.segment === 1)) {
    throw new RoofError("break_too_high");
  }

  const classified = classify(sloping, outline);
  const lift = (face: SlopedFace) => input.thickness / Math.cos(radians(face.pitchDeg));
  const faces: RoofFace[] = sloping.map((s) => {
    const planArea = area2(s.polygon);
    return {
      // Das Pultdach gehört zu allen Traufkanten
      contourEdges: design.form === "mono_pitch" ? kinds.flatMap((k, i) => (k === "eave" ? merged.members[i]! : [])) : merged.members[s.edge]!,
      segment: s.segment,
      pitchDeg: s.pitchDeg,
      polygon: s.polygon,
      planArea,
      area: planArea / Math.cos(radians(s.pitchDeg)),
    };
  });
  // Oberkante je Knoten über der flachsten anliegenden Fläche: am First gleich geneigter Flächen exakt
  let top = -Infinity;
  for (const s of sloping) {
    for (const v of s.polygon) {
      const adjacent = sloping.filter((t) => t.polygon.some((w) => length3(v, w) < ON_LINE));
      top = Math.max(top, v.z + Math.min(...adjacent.map(lift)));
    }
  }
  const eave = Math.min(...classified.filter((l) => l.kind === "eave").map((l) => Math.min(l.a.z, l.b.z) + lift(sloping[l.faces[0]!]!)));
  const ridges = classified.filter((l) => l.kind === "ridge" && l.length > TOL);
  let ridgeAzimuthDeg: number | null = null;
  if (ridges.length) {
    const longest = ridges.reduce((best, l) => (l.length > best.length + TOL ? l : best));
    const deg = (Math.atan2(longest.b.x - longest.a.x, longest.b.y - longest.a.y) * 180) / Math.PI;
    const axis = ((deg % 180) + 180) % 180;
    ridgeAzimuthDeg = axis > 180 - 1e-9 ? 0 : axis;
  }

  /**
   * Stücke der Strecke unter den Flächen mit den Höhen an ihren Enden; `null`, wenn sie nicht ganz bedeckt ist. Die
   * Fläche wird 0,1 mm innen gesucht, die Höhe gilt auf der Strecke selbst.
   */
  const pieces = (from: Vec, to: Vec): { length: number; z0: number; z1: number }[] | null => {
    const l = length2(from, to);
    if (l < ON_LINE) return null;
    const inward = { x: (-(to.y - from.y) / l) * INSIDE, y: ((to.x - from.x) / l) * INSIDE };
    const a = { x: from.x + inward.x, y: from.y + inward.y };
    const b = { x: to.x + inward.x, y: to.y + inward.y };
    const out: { length: number; z0: number; z1: number }[] = [];
    for (const s of sloping) {
      for (const [s0, s1] of within(a, b, s.polygon)) {
        const p0 = { x: from.x + (to.x - from.x) * s0, y: from.y + (to.y - from.y) * s0 };
        const p1 = { x: from.x + (to.x - from.x) * s1, y: from.y + (to.y - from.y) * s1 };
        out.push({ length: (s1 - s0) * l, z0: heightOn(s.plane, p0), z1: heightOn(s.plane, p1) });
      }
    }
    const covered = out.reduce((sum, p) => sum + p.length, 0);
    return Math.abs(covered - l) <= TOL ? out : null;
  };
  const undersideIntegral = (a: Vec, b: Vec): number | null =>
    pieces(a, b)?.reduce((sum, p) => sum + ((p.z0 + p.z1) / 2) * p.length, 0) ?? null;
  const undersideMin = (a: Vec, b: Vec): number | null => {
    const found = pieces(a, b);
    return found ? Math.min(...found.flatMap((p) => [p.z0, p.z1])) : null;
  };
  // Giebelwände: auf der Bezugskontur vom Auflager bis zur Unterseite des Dachs, an jeder Giebelkante
  let gableArea = 0;
  kinds.forEach((kind, i) => {
    if (kind !== "gable") return;
    const a = points[i]!;
    const b = points[(i + 1) % points.length]!;
    const integral = undersideIntegral(a, b);
    if (integral !== null) gableArea += integral - input.bearing * length2(a, b);
  });

  const edgeKindsByContour: ("eave" | "gable")[] = [];
  merged.members.forEach((members, i) => members.forEach((m) => (edgeKindsByContour[m] = kinds[i]!)));
  const lines: RoofLine[] = classified.map(({ kind, a, b, length }) => ({ kind, a, b, length }));
  return { faces, lines, outline, edgeKinds: edgeKindsByContour, top, eave, ridgeAzimuthDeg, gableArea, undersideIntegral, undersideMin };
}

