// Gewichtetes gerades Skelett mit Profilwechseln in der Höhe („procedural extrusions“, Kelly und Wonka 2011;
// docs/PLAN_HAUSMODELL.md Ergänzung 11, Kapitel 10). Aus dem Spike HM0 übernommen und erweitert um Teilflächen je
// Profilabschnitt: Jede Teilfläche ist eben, so lassen sich Flächen, Neigungen und Linien des Dachs bestimmen.
//
// Jede Kante der Kontur trägt ein Neigungsprofil. Die Wellenfront zur Höhe t ist die Kontur, deren Kanten um den bis
// t aufsummierten Weg (Höhe / Neigung) nach innen gewandert sind; senkrechte Abschnitte (Giebel) stehen. Ereignisse:
// Kante schrumpft auf null (Kantenereignis), einspringende Ecke trifft eine Kante (Teilungsereignis), Neigungswechsel
// (Profilereignis). Gleichzeitige Ereignisse werden zur selben Höhe gemeinsam behandelt.
//
// Rechnung in Metern als Gleitkomma; die Eingabe kommt aus dem Raster von 0,1 mm (P 4). Die Toleranzen sind feste
// Bruchteile dieses Rasters, keine relativen Schwellen (Kapitel 10, Folgerung 3).

export interface Vec {
  readonly x: number;
  readonly y: number;
}

export interface Vec3 extends Vec {
  readonly z: number;
}

/** Neigung als Steigung (tan) und in Grad; `slope` `Infinity` = senkrecht. Gilt bis `untilHeight` über der Kontur. */
export interface SlopeSegment {
  readonly slope: number;
  readonly pitchDeg: number;
  readonly untilHeight: number;
}

export type EdgeProfile = readonly SlopeSegment[];

/** Ebene Teilfläche: Kante der Kontur, Abschnitt ihres Profils, Umrisse (meist einer) in 3D. */
export interface SkeletonFace {
  readonly edge: number;
  readonly segment: number;
  readonly loops: readonly (readonly Vec3[])[];
}

export type SkeletonErrorCode =
  | "invalid_input"
  | "not_counter_clockwise"
  | "slope_not_positive"
  | "collinear_vertex"
  | "no_progress"
  | "no_event"
  | "face_open";

export class SkeletonError extends Error {
  readonly code: SkeletonErrorCode;

  constructor(code: SkeletonErrorCode) {
    super(code);
    this.code = code;
  }
}

/** Raster der Eingabe: 0,1 mm. */
const GRID = 1e-4;
/** Höhe gleichzeitiger Ereignisse. */
const EPS_T = GRID * 1e-5;
/** Punkt auf einer Geraden. */
const EPS_P = GRID * 1e-3;
/** Gleiche Punkte. */
const NEAR = GRID * 1e-2;
const MAX_STEPS = 10_000;

export const vertical = (untilHeight = Infinity): SlopeSegment => ({ slope: Infinity, pitchDeg: 90, untilHeight });
export const sloped = (pitchDeg: number, untilHeight = Infinity): SlopeSegment => ({
  slope: Math.tan((pitchDeg * Math.PI) / 180),
  pitchDeg,
  untilHeight,
});

const sub = (a: Vec, b: Vec): Vec => ({ x: a.x - b.x, y: a.y - b.y });
const addScaled = (a: Vec, b: Vec, s: number): Vec => ({ x: a.x + b.x * s, y: a.y + b.y * s });
const dot = (a: Vec, b: Vec) => a.x * b.x + a.y * b.y;
const cross = (a: Vec, b: Vec) => a.x * b.y - a.y * b.x;
const near = (a: Vec, b: Vec, eps = EPS_P * 10) => Math.abs(a.x - b.x) < eps && Math.abs(a.y - b.y) < eps;
const near3 = (a: Vec3, b: Vec3) => near(a, b, NEAR) && Math.abs(a.z - b.z) < NEAR;

export function signedArea(points: readonly Vec[]): number {
  let twice = 0;
  for (let i = 0; i < points.length; i++) {
    twice += cross(points[i]!, points[(i + 1) % points.length]!);
  }
  return twice / 2;
}

interface Edge {
  readonly p: Vec;
  readonly d: Vec;
  /** Normale nach innen (links bei Umlauf gegen den Uhrzeigersinn). */
  readonly n: Vec;
  readonly profile: EdgeProfile;
}

/** Ecke der Wellenfront: Lage zur aktuellen Höhe, Nachbarkanten, Knoten, an dem ihre Bahn begann. */
interface Corner {
  p: Vec;
  readonly prev: number;
  readonly next: number;
  start: Vec3;
  u: Vec;
}

type Loop = Corner[];

export function weightedSkeleton(polygon: readonly Vec[], profiles: readonly EdgeProfile[]): SkeletonFace[] {
  if (polygon.length < 3 || profiles.length !== polygon.length) throw new SkeletonError("invalid_input");
  if (signedArea(polygon) <= 0) throw new SkeletonError("not_counter_clockwise");
  const edges: Edge[] = polygon.map((p, i) => {
    const q = polygon[(i + 1) % polygon.length]!;
    const length = Math.sqrt((q.x - p.x) ** 2 + (q.y - p.y) ** 2);
    const d = { x: (q.x - p.x) / length, y: (q.y - p.y) / length };
    const profile = profiles[i]!;
    if (!profile.length || profile.some((s) => !(s.slope > 0) || !(s.untilHeight > 0))) throw new SkeletonError("slope_not_positive");
    return { p, d, n: { x: -d.y, y: d.x }, profile };
  });
  // Gerade durchlaufende Ecken haben keine Winkelhalbierende; der Aufrufer fasst solche Kanten vorher zusammen
  edges.forEach((e, i) => {
    if (Math.abs(cross(edges[(i - 1 + edges.length) % edges.length]!.d, e.d)) < 1e-9) throw new SkeletonError("collinear_vertex");
  });
  const segments = new Map<string, [Vec3, Vec3][]>();
  const key = (edge: number, segment: number) => `${edge}/${segment}`;

  const speed = (s: SlopeSegment) => (Number.isFinite(s.slope) ? 1 / s.slope : 0);
  const indexAt = (i: number, t: number) => {
    const profile = edges[i]!.profile;
    const found = profile.findIndex((s) => s.untilHeight > t + EPS_T);
    return found < 0 ? profile.length - 1 : found;
  };
  /** Abschnitt unmittelbar unter bzw. über der Höhe t. */
  const before = (i: number, t: number) => indexAt(i, t - 2 * EPS_T);
  const after = (i: number, t: number) => indexAt(i, t);
  const speedAt = (i: number, t: number) => speed(edges[i]!.profile[after(i, t)]!);
  const offsetAt = (i: number, t: number) => {
    let h0 = 0;
    let offset = 0;
    for (const s of edges[i]!.profile) {
      const h1 = Math.min(s.untilHeight, t);
      if (h1 > h0) offset += (h1 - h0) * speed(s);
      h0 = s.untilHeight;
      if (h0 >= t) break;
    }
    return offset;
  };
  const lineAt = (i: number, t: number) => dot(edges[i]!.n, edges[i]!.p) + offsetAt(i, t);
  const changesAt = (i: number, t: number) => edges[i]!.profile.some((s) => Math.abs(s.untilHeight - t) < EPS_T);
  const phaseEnd = (t: number) => {
    let end = Infinity;
    for (const e of edges) for (const s of e.profile) if (s.untilHeight > t + EPS_T) end = Math.min(end, s.untilHeight);
    return end;
  };

  /** Eine Strecke je Teilfläche höchstens einmal: fallen Ereignisse zusammen, melden sie dieselbe Grenze mehrfach. */
  const addSegment = (edge: number, segment: number, a: Vec3, b: Vec3) => {
    if (near3(a, b)) return;
    const k = key(edge, segment);
    const list = segments.get(k) ?? [];
    if (list.some(([p, q]) => (near3(p, a) && near3(q, b)) || (near3(p, b) && near3(q, a)))) return;
    segments.set(k, [...list, [a, b]]);
  };
  const closeTrack = (c: Corner, end: Vec3) => {
    const middle = (c.start.z + end.z) / 2;
    addSegment(c.prev, indexAt(c.prev, middle), c.start, end);
    addSegment(c.next, indexAt(c.next, middle), c.start, end);
  };
  const node = (p: Vec, t: number): Vec3 => ({ x: p.x, y: p.y, z: t });

  const velocity = (c: Corner, t: number): Vec => {
    const na = edges[c.prev]!.n;
    const nb = edges[c.next]!.n;
    const sa = speedAt(c.prev, t);
    const sb = speedAt(c.next, t);
    const det = cross(na, nb);
    if (Math.abs(det) > 1e-12) {
      return { x: (sa * nb.y - na.y * sb) / det, y: (na.x * sb - sa * nb.x) / det };
    }
    // Parallele Nachbarn bleiben nur, wenn sie gleich schnell und gleich gerichtet sind (resolveParallelOnce):
    // dann wandern sie gemeinsam, die Grenze ihrer Flächen steht senkrecht zur Kante
    return dot(na, nb) > 0 ? { x: (na.x * (sa + sb)) / 2, y: (na.y * (sa + sb)) / 2 } : { x: 0, y: 0 };
  };
  const isReflex = (c: Corner) => cross(edges[c.prev]!.d, edges[c.next]!.d) < -1e-12;

  const merge = (loop: Loop, t: number): Loop => {
    const n = loop.length;
    let first = 0;
    while (first < n && near(loop[first]!.p, loop[(first - 1 + n) % n]!.p)) first++;
    if (first === n) {
      const end = node(loop[0]!.p, t);
      loop.forEach((c) => closeTrack(c, end));
      return [];
    }
    const ring = [...loop.slice(first), ...loop.slice(0, first)];
    const out: Loop = [];
    for (let i = 0; i < n; ) {
      let j = i;
      while (j + 1 < n && near(ring[j + 1]!.p, ring[i]!.p)) j++;
      if (j === i) {
        out.push(ring[i]!);
      } else {
        const cluster = ring.slice(i, j + 1);
        const p = { x: cluster.reduce((s, c) => s + c.p.x, 0) / cluster.length, y: cluster.reduce((s, c) => s + c.p.y, 0) / cluster.length };
        const end = node(p, t);
        cluster.forEach((c) => closeTrack(c, end));
        out.push({ p, prev: ring[i]!.prev, next: ring[j]!.next, start: end, u: { x: 0, y: 0 } });
      }
      i = j + 1;
    }
    return out;
  };

  /** Eine zusammengefallene Schleife endet: waagerechte Linien zwischen ihren Ecken. */
  const finish = (loop: Loop, t: number) => {
    loop.forEach((c) => closeTrack(c, node(c.p, t)));
    for (let k = 0; k < loop.length && loop.length > 1; k++) {
      const a = loop[k]!;
      const b = loop[(k + 1) % loop.length]!;
      addSegment(a.next, before(a.next, t), node(a.p, t), node(b.p, t));
    }
  };

  /** Ersetzt `count` Ecken ab `from` (zyklisch) durch eine neue Ecke an `p`. */
  const replace = (loop: Loop, from: number, count: number, p: Vec, prev: number, next: number, t: number): Loop => {
    const ring = [...loop.slice(from), ...loop.slice(0, from)];
    ring.slice(0, count).forEach((c) => closeTrack(c, node(c.p, t)));
    return [{ p, prev, next, start: node(p, t), u: { x: 0, y: 0 } }, ...ring.slice(count)];
  };

  /**
   * Parallele Nachbarkanten (nach einem Ereignis liegen sie auf einer Linie). Gleich gerichtet: die langsamere
   * (steilere) Fläche endet waagerecht, die schnellere läuft weiter. Gegenläufig: der Sporn fällt auf der Länge
   * der kürzeren Kante zu einem waagerechten First zusammen.
   */
  const resolveParallelOnce = (loops: Loop[], t: number): boolean => {
    for (let li = 0; li < loops.length; li++) {
      const loop = loops[li]!;
      const n = loop.length;
      for (let k = 0; k < n; k++) {
        const c = loop[k]!;
        const a = edges[c.prev]!;
        const b = edges[c.next]!;
        if (Math.abs(cross(a.d, b.d)) > 1e-9) continue;
        const kp = (k - 1 + n) % n;
        const kn = (k + 1) % n;
        const cp = loop[kp]!;
        const cn = loop[kn]!;
        if (dot(a.d, b.d) > 0) {
          const sa = speedAt(c.prev, t);
          const sb = speedAt(c.next, t);
          if (Math.abs(sa - sb) < 1e-12) continue;
          // Die langsamere Fläche endet (Abschnitt darunter), die schnellere läuft weiter (Abschnitt darüber)
          const line = (slow: number, fast: number, from: Vec, to: Vec) => {
            addSegment(slow, before(slow, t), node(from, t), node(to, t));
            addSegment(fast, after(fast, t), node(from, t), node(to, t));
          };
          if (sa < sb) {
            line(c.prev, c.next, cp.p, c.p);
            loops[li] = replace(loop, kp, 2, cp.p, cp.prev, c.next, t);
          } else {
            line(c.next, c.prev, c.p, cn.p);
            loops[li] = replace(loop, k, 2, cn.p, c.prev, cn.next, t);
          }
          return true;
        }
        const la = dot(sub(c.p, cp.p), a.d);
        const lb = dot(sub(c.p, cn.p), a.d);
        const shorter = Math.abs(la - lb) < EPS_P * 10 ? "both" : la < lb ? "a" : "b";
        const base = shorter === "b" ? cn.p : cp.p;
        [c.prev, c.next].forEach((f) => addSegment(f, before(f, t), node(base, t), node(c.p, t)));
        loops[li] =
          shorter === "both" ? replace(loop, kp, 3, cp.p, cp.prev, cn.next, t)
          : shorter === "a" ? replace(loop, kp, 2, cp.p, cp.prev, c.next, t)
          : replace(loop, k, 2, cn.p, c.prev, cn.next, t);
        return true;
      }
    }
    return false;
  };

  /** Eine Teilung zur Höhe t, falls eine einspringende Ecke auf einer fremden Kante liegt. */
  const splitOnce = (loops: Loop[], t: number): boolean => {
    for (let li = 0; li < loops.length; li++) {
      const loop = loops[li]!;
      for (let iv = 0; iv < loop.length; iv++) {
        const v = loop[iv]!;
        if (!isReflex(v)) continue;
        for (let ia = 0; ia < loop.length; ia++) {
          const a = loop[ia]!;
          const ib = (ia + 1) % loop.length;
          const b = loop[ib]!;
          const e = a.next;
          if (ia === iv || ib === iv || e === v.prev || e === v.next) continue;
          if (Math.abs(dot(edges[e]!.n, v.p) - lineAt(e, t)) > EPS_P * 10) continue;
          const span = dot(sub(b.p, a.p), edges[e]!.d);
          const s = dot(sub(v.p, a.p), edges[e]!.d);
          if (s < -EPS_P * 10 || s > span + EPS_P * 10) continue;
          const at = node(v.p, t);
          closeTrack(v, at);
          const ring = (from: number, to: number) => {
            const out: Corner[] = [];
            for (let k = from; ; k = (k + 1) % loop.length) {
              out.push(loop[k]!);
              if (k === to) break;
            }
            return out;
          };
          // v teilt die Schleife: links v → … → a (Kante e ab v), rechts b → … → vor v (Kante e bis v)
          const left: Loop = [{ p: v.p, prev: e, next: v.next, start: at, u: { x: 0, y: 0 } }, ...ring((iv + 1) % loop.length, ia)];
          const right: Loop = [{ p: v.p, prev: v.prev, next: e, start: at, u: { x: 0, y: 0 } }, ...ring(ib, (iv - 1 + loop.length) % loop.length)];
          loops.splice(li, 1, left, right);
          return true;
        }
      }
    }
    return false;
  };

  const settle = (loops: Loop[], t: number): Loop[] => {
    let current = loops;
    for (let guard = 0; guard < MAX_STEPS; guard++) {
      current = current.map((l) => merge(l, t)).filter((l) => l.length > 0);
      const alive: Loop[] = [];
      for (const loop of current) {
        if (loop.length < 3 || Math.abs(signedArea(loop.map((c) => c.p))) < 1e-9) finish(loop, t);
        else alive.push(loop);
      }
      current = alive;
      if (resolveParallelOnce(current, t)) continue;
      if (!splitOnce(current, t)) return current;
    }
    throw new SkeletonError("no_progress");
  };

  edges.forEach((edge, i) => addSegment(i, after(i, 0), node(edge.p, 0), node(polygon[(i + 1) % polygon.length]!, 0)));
  let t = 0;
  let loops: Loop[] = [polygon.map((p, i) => ({ p, prev: (i - 1 + polygon.length) % polygon.length, next: i, start: node(p, 0), u: { x: 0, y: 0 } }))];
  loops = settle(loops, t);
  for (let step = 0; loops.length > 0; step++) {
    if (step > MAX_STEPS) throw new SkeletonError("no_progress");
    for (const loop of loops) for (const c of loop) c.u = velocity(c, t);
    let next = phaseEnd(t);
    for (const loop of loops) {
      for (let k = 0; k < loop.length; k++) {
        const v = loop[k]!;
        const w = loop[(k + 1) % loop.length]!;
        const rate = dot(sub(w.u, v.u), edges[v.next]!.d);
        if (rate < -1e-12) {
          const when = t + dot(sub(w.p, v.p), edges[v.next]!.d) / -rate;
          if (when > t + EPS_T) next = Math.min(next, when);
        }
      }
      for (const v of loop) {
        if (!isReflex(v)) continue;
        for (let ia = 0; ia < loop.length; ia++) {
          const a = loop[ia]!;
          const b = loop[(ia + 1) % loop.length]!;
          const e = a.next;
          if (a === v || b === v || e === v.prev || e === v.next) continue;
          const gap = dot(edges[e]!.n, v.p) - lineAt(e, t);
          const rate = dot(edges[e]!.n, v.u) - speedAt(e, t);
          if (gap < -EPS_P || rate > -1e-12) continue;
          const tau = gap / -rate;
          if (tau <= EPS_T || t + tau >= next) continue;
          const hit = addScaled(v.p, v.u, tau);
          const pa = addScaled(a.p, a.u, tau);
          const pb = addScaled(b.p, b.u, tau);
          const s = dot(sub(hit, pa), edges[e]!.d);
          if (s >= -EPS_P * 10 && s <= dot(sub(pb, pa), edges[e]!.d) + EPS_P * 10) next = t + tau;
        }
      }
    }
    if (!Number.isFinite(next)) throw new SkeletonError("no_event");
    // Fällt ein Ereignis mit einem Profilwechsel zusammen, gilt genau dessen Höhe: sonst ordneten `before` und
    // `after` die Strecken im Knick demselben Abschnitt zu
    const change = phaseEnd(t);
    if (change - next < EPS_T) next = change;
    for (const loop of loops) for (const c of loop) c.p = addScaled(c.p, c.u, next - t);
    t = next;
    const upper: { edge: number; a: Vec; b: Vec }[] = [];
    for (const loop of loops) {
      for (const c of loop) {
        if (changesAt(c.prev, t) || changesAt(c.next, t)) {
          const at = node(c.p, t);
          closeTrack(c, at);
          c.start = at;
        }
      }
      // Profilwechsel: die Wellenfront der Kante ist Oberkante des unteren Abschnitts und, wenn sie weiterläuft,
      // Unterkante des oberen
      for (let k = 0; k < loop.length; k++) {
        const a = loop[k]!;
        const b = loop[(k + 1) % loop.length]!;
        if (!changesAt(a.next, t)) continue;
        addSegment(a.next, before(a.next, t), node(a.p, t), node(b.p, t));
        upper.push({ edge: a.next, a: a.p, b: b.p });
      }
    }
    loops = settle(loops, t);
    for (const { edge, a, b } of upper) {
      const alive = loops.some((loop) => loop.some((c) => (c.next === edge && near(c.p, a)) || (c.prev === edge && near(c.p, b))));
      if (alive) addSegment(edge, after(edge, t), node(a, t), node(b, t));
    }
  }

  const faces: SkeletonFace[] = [];
  for (const [k, list] of [...segments.entries()].sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }))) {
    const [edge, segment] = k.split("/").map(Number) as [number, number];
    faces.push({ edge, segment, loops: cycles(list) });
  }
  return faces;
}

/** Teilt Strecken an Knoten anderer Strecken, die in ihrem Inneren liegen (eine Teilung zur selben Höhe). */
function splitAtNodes(segments: readonly [Vec3, Vec3][]): [Vec3, Vec3][] {
  const nodes = segments.flat();
  const out: [Vec3, Vec3][] = [];
  for (const [a, b] of segments) {
    const ab = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z };
    const l2 = ab.x ** 2 + ab.y ** 2 + ab.z ** 2;
    const cuts: { s: number; p: Vec3 }[] = [];
    for (const p of nodes) {
      const s = ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y + (p.z - a.z) * ab.z) / l2;
      const foot = { x: a.x + ab.x * s, y: a.y + ab.y * s, z: a.z + ab.z * s };
      if (near3(p, foot) && !near3(p, a) && !near3(p, b) && s > 0 && s < 1 && !cuts.some((c) => near3(c.p, p))) cuts.push({ s, p });
    }
    cuts.sort((x, y) => x.s - y.s);
    let from = a;
    for (const { p } of cuts) {
      out.push([from, p]);
      from = p;
    }
    out.push([from, b]);
  }
  return out;
}

/** Geschlossene Umrisse aus ungeordneten Strecken; jede Strecke genau einmal. */
function cycles(input: readonly [Vec3, Vec3][]): Vec3[][] {
  const segments = splitAtNodes(input);
  const used = new Set<number>();
  const out: Vec3[][] = [];
  for (let first = 0; first < segments.length; first++) {
    if (used.has(first)) continue;
    used.add(first);
    const [start, second] = segments[first]!;
    const ring: Vec3[] = [start];
    let current = second;
    for (let guard = 0; ; guard++) {
      if (guard > segments.length) throw new SkeletonError("face_open");
      if (near3(current, start)) break;
      ring.push(current);
      const k = segments.findIndex(([a, b], j) => !used.has(j) && (near3(a, current) || near3(b, current)));
      if (k < 0) throw new SkeletonError("face_open");
      used.add(k);
      const [a, b] = segments[k]!;
      current = near3(a, current) ? b : a;
    }
    if (ring.length >= 3) out.push(ring);
  }
  return out;
}
