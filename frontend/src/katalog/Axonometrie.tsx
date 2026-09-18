/**
 * Axonometrie eines Haustyps (isometrisch, Blick von Südosten; X = Ost, Y = Süd, Z = oben), clientseitig aus den
 * Kennwerten des Typs gezeichnet (Plan H1 3.6, Formel aus dem Mockup: x = (X − Y)·cos 30°, y = (X + Y)·0,5 − Z).
 * Schematisch: Wände über dem Umriss, Dach über dessen Hüllrechteck. So sieht das Büro beim Erfassen sofort, ob
 * Höhen, Dachform und Firstrichtung stimmen; eine Bilddatei entsteht nicht.
 */

import { useTranslation } from "react-i18next";

import type { components } from "../api/schema";
import { edgesOf, type Ring } from "./geometrie";

type Version = components["schemas"]["TypeVersionOut"];

const COS30 = Math.cos(Math.PI / 6);
type Point3 = readonly [number, number, number];

const project = ([x, y, z]: Point3): [number, number] => [(x - y) * COS30, (x + y) * 0.5 - z];
const points = (list: readonly Point3[]) => list.map((p) => project(p).map((v) => v.toFixed(3)).join(",")).join(" ");

interface Face {
  key: string;
  depth: number;
  corners: Point3[];
  fill: string;
}

/** Dachflächen und Giebel über dem Hüllrechteck; nur die Seiten, die der Betrachter (Südost) sieht. */
function roofFaces(version: Version, box: { x0: number; x1: number; y0: number; y1: number }, eave: number): Face[] {
  const { x0, x1, y0, y1 } = box;
  const w = x1 - x0;
  const d = y1 - y0;
  const ridge = version.ridge_height_m;
  const alongX = (w >= d) === (version.ridge_direction !== "quer");
  const hip = version.roof_form === "hip";
  const wall = "var(--sheet)";
  const roof = "var(--hatch)";
  const half = Math.min(w, d) / 2;
  const faces: Face[] = [];
  if (alongX) {
    const ym = y0 + d / 2;
    const inset = hip ? half : 0;
    faces.push({ key: "slope", depth: 2, fill: roof, corners: [[x0, y1, eave], [x1, y1, eave], [x1 - inset, ym, ridge], [x0 + inset, ym, ridge]] });
    faces.push({
      key: "end",
      depth: 1,
      fill: hip ? roof : wall,
      corners: [[x1, y0, eave], [x1, y1, eave], [x1 - inset, ym, ridge]],
    });
  } else {
    const xm = x0 + w / 2;
    const inset = hip ? half : 0;
    faces.push({ key: "slope", depth: 2, fill: roof, corners: [[x1, y0, eave], [x1, y1, eave], [xm, y1 - inset, ridge], [xm, y0 + inset, ridge]] });
    faces.push({
      key: "end",
      depth: 1,
      fill: hip ? roof : wall,
      corners: [[x0, y1, eave], [x1, y1, eave], [xm, y1 - inset, ridge]],
    });
  }
  return faces;
}

export function Axonometrie({ version }: { version: Version }) {
  const { t } = useTranslation();
  const ring = version.footprint_facade as Ring;
  const gable = version.roof_form === "gable" || version.roof_form === "hip";
  // Flach- und Sonderdach: Wände bis zur Oberkante (Attika bzw. Firsthöhe), oben flach geschlossen
  const wallHeight = gable || version.roof_form === "flat" ? version.eave_height_m : version.ridge_height_m;

  // (E, N) → (X, Y = −N), Ursprung an die Ecke rücken
  const minE = Math.min(...ring.map((p) => p[0]!));
  const maxN = Math.max(...ring.map((p) => p[1]!));
  const toXY = (p: readonly number[]): [number, number] => [p[0]! - minE, maxN - p[1]!];
  const outline = ring.map(toXY);
  const box = {
    x0: Math.min(...outline.map((p) => p[0])),
    x1: Math.max(...outline.map((p) => p[0])),
    y0: Math.min(...outline.map((p) => p[1])),
    y1: Math.max(...outline.map((p) => p[1])),
  };

  const walls: Face[] = edgesOf(ring)
    .filter((edge) => edge.normal[0] - edge.normal[1] > 0.05) // Normale in (X, Y): (nE, −nN); sichtbar zur Südost-Seite
    .map((edge) => {
      const [ax, ay] = toXY(edge.from);
      const [bx, by] = toXY(edge.to);
      return {
        key: `wall${edge.index}`,
        depth: (ax + bx + ay + by) / 2,
        fill: "var(--sheet)",
        corners: [[ax, ay, 0], [bx, by, 0], [bx, by, wallHeight], [ax, ay, wallHeight]] as Point3[],
      };
    })
    .sort((a, b) => a.depth - b.depth);

  const roof = gable ? roofFaces(version, box, wallHeight) : [];
  const cap: Face | null = gable
    ? null
    : { key: "cap", depth: 0, fill: "var(--hatch)", corners: outline.map(([x, y]) => [x, y, wallHeight] as Point3) };

  const ground = outline.map(([x, y]) => [x, y, 0] as Point3);
  const projectionGround = (version.footprint_projection as Ring).map(toXY).map(([x, y]) => [x, y, 0] as Point3);
  const all = [...ground, ...projectionGround, ...walls.flatMap((f) => f.corners), ...roof.flatMap((f) => f.corners), ...(cap?.corners ?? [])];
  const screen = all.map(project);
  const pad = 1.2;
  const minX = Math.min(...screen.map((p) => p[0])) - pad;
  const maxX = Math.max(...screen.map((p) => p[0])) + pad;
  const minY = Math.min(...screen.map((p) => p[1])) - pad;
  const maxY = Math.max(...screen.map((p) => p[1])) + pad;
  const edgeStyle = { stroke: "var(--axo)", strokeWidth: 0.07, strokeLinejoin: "round" as const };

  return (
    <svg
      viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`}
      className="w-full h-auto block"
      role="img"
      aria-label={t("catalog.type.axoLabel", {
        name: version.name,
        roof: t(`catalog.roofForm.${version.roof_form}`),
        height: version.ridge_height_m.toFixed(1),
      })}
      data-testid="axonometrie"
    >
      <polygon points={points(projectionGround)} style={{ fill: "var(--street)", stroke: "var(--line-strong)", strokeWidth: 0.05 }} />
      {[...walls, ...roof, ...(cap ? [cap] : [])].map((face) => (
        <polygon key={face.key} points={points(face.corners)} style={{ ...edgeStyle, fill: face.fill }} />
      ))}
    </svg>
  );
}
