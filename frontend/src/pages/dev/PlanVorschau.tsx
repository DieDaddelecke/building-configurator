/**
 * Nur in der Entwicklung (import.meta.env.DEV): Planbausteine mit einem beliebigen Polygon in lokalen Metern.
 * Zeigt, dass die Mockup-Bausteine nicht mehr an das Rechteck 20 × 31 m gebunden sind.
 */

import { Kopfzeile } from "../../components/Kopfzeile";
import { MassH, MassV, Massstab, Nordpfeil, Schraffur, strich } from "../../components/plan/Masskette";
import { boundsOf, PlanSvg, polygonPath, toSvg, type LocalPoint } from "../../components/plan/PlanSvg";
import { Planblatt } from "../../components/plan/Planblatt";

const GRUNDSTUECK: LocalPoint[] = [[0, 0], [21.5, 1.2], [20.4, 31.0], [-0.8, 29.6]];
const BEBAUBAR: LocalPoint[] = [[3.1, 5.2], [18.2, 6.0], [17.6, 24.1], [2.5, 23.2]];

export function PlanVorschau() {
  const bounds = boundsOf(GRUNDSTUECK);
  const [sx, sy] = toSvg([0, 0]);
  const [, strasseY] = toSvg([0, 5.2]);
  return (
    <div className="emp">
      <Kopfzeile untertitel="Plan-Bausteine" />
      <main className="max-w-3xl mx-auto px-6 py-10">
        <Planblatt inhalt="Lageplan · Vorschau" schriftfeld={[{ label: "Parzelle", wert: "Beispiel" }, { label: "Blatt", wert: "1 / 1" }]}>
          <PlanSvg bounds={bounds} label="Beispiel-Lageplan">
            <defs>
              <Schraffur id="h-bau" farbe="var(--accent)" abstand={0.9} breite={0.045} />
            </defs>
            <path d={polygonPath([GRUNDSTUECK])} style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: 0.16 }} />
            <path d={polygonPath([BEBAUBAR])} style={{ fill: "url(#h-bau)", ...strich("var(--accent)", 0.17), fillOpacity: 0.6 }} />
            <MassV y1={sy} y2={strasseY} x={-3.5} label="5,20" farbe="var(--accent)" />
            <MassH x1={sx} x2={21.5} y={sy + 4} label="21,50" von={sy} farbe="var(--ink)" />
            <Nordpfeil x={24} y={-28} />
            <Massstab x={-4} y={-bounds.minN + 4} />
          </PlanSvg>
        </Planblatt>
      </main>
    </div>
  );
}
