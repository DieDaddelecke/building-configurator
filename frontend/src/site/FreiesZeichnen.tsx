/**
 * Weg E (Plan 3.3): Grundstück frei zeichnen und bemaßen, ohne Kataster. Kein Bebaubarkeitscheck – G2
 * und G3 werden für dieses Grundstück nicht aufgerufen (D13). Zeichenfläche als freies Koordinatenraster
 * ohne Kartenbezug (Plan 3.3, Prüfprotokoll 10.4).
 */

import { useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { useFormManualSite, type ManualEdgeIn } from "../api/site";
import { strich } from "../components/plan/Masskette";
import { toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { KantenBearbeiten } from "./KantenBearbeiten";
import { edgesFromPoints } from "./manual";

const GRID_M = 5;
const CANVAS_M = 40;
const MIN_POINTS = 3;

interface FreiesZeichnenProps {
  ensureProject: () => Promise<string>;
  onFormed: () => void;
  onCancel?: () => void;
}

function useSvgPoint() {
  const ref = useRef<SVGSVGElement | null>(null);
  const fromEvent = (event: ReactMouseEvent): LocalPoint | null => {
    const svg = ref.current;
    if (!svg) return null;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const inverse = svg.getScreenCTM()?.inverse();
    if (!inverse) return null;
    const local = point.matrixTransform(inverse);
    return [Math.round(local.x * 10) / 10, Math.round(-local.y * 10) / 10];
  };
  return { ref, fromEvent };
}

export function FreiesZeichnen({ ensureProject, onFormed, onCancel }: FreiesZeichnenProps) {
  const { t } = useTranslation();
  const [points, setPoints] = useState<LocalPoint[]>([]);
  const [edges, setEdges] = useState<ManualEdgeIn[] | null>(null);
  const [address, setAddress] = useState("");
  const formSite = useFormManualSite();
  const { ref: svgRef, fromEvent } = useSvgPoint();

  const canvasBounds = { minE: 0, minN: 0, maxE: CANVAS_M, maxN: CANVAS_M };
  const gridSteps: number[] = [];
  for (let v = 0; v <= CANVAS_M; v += GRID_M) gridSteps.push(v);

  const addPoint = (event: ReactMouseEvent) => {
    const point = fromEvent(event);
    if (point) setPoints((current) => [...current, point]);
  };

  const undo = () => setPoints((current) => current.slice(0, -1));
  const reset = () => {
    setPoints([]);
    setEdges(null);
  };

  const startDimensioning = () => {
    if (points.length < MIN_POINTS) return;
    setEdges(edgesFromPoints(points));
  };

  if (!edges) {
    return (
      <div className="flex flex-col gap-4">
        <p className="t-mute text-sm m-0">{t("site.manual.draw.hint")}</p>
        <svg
          ref={svgRef}
          viewBox={`${canvasBounds.minE} ${-canvasBounds.maxN} ${canvasBounds.maxE} ${canvasBounds.maxN}`}
          className="w-full h-auto block select-none border bd bg-sheet"
          style={{ maxHeight: "min(70vh, 34rem)", cursor: "crosshair" }}
          role="img"
          aria-label={t("site.manual.draw.canvas")}
          onClick={addPoint}
        >
          {gridSteps.map((v) => (
            <line key={`v${v}`} x1={v} y1={-canvasBounds.maxN} x2={v} y2={0} style={strich("var(--line)", 0.05)} />
          ))}
          {gridSteps.map((v) => (
            <line key={`h${v}`} x1={0} y1={-v} x2={canvasBounds.maxE} y2={-v} style={strich("var(--line)", 0.05)} />
          ))}
          {points.length >= 2 && (
            <path
              d={points.map((p, i) => `${i ? "L" : "M"}${toSvg(p)[0]} ${toSvg(p)[1]}`).join("")}
              style={strich("var(--accent)", 0.15)}
            />
          )}
          {points.length >= MIN_POINTS && points[0] && (
            <line
              x1={toSvg(points[points.length - 1] as LocalPoint)[0]}
              y1={toSvg(points[points.length - 1] as LocalPoint)[1]}
              x2={toSvg(points[0])[0]}
              y2={toSvg(points[0])[1]}
              style={strich("var(--faint)", 0.1, { strokeDasharray: "0.5 0.5" })}
            />
          )}
          {points.map((p, i) => (
            <circle key={i} cx={toSvg(p)[0]} cy={toSvg(p)[1]} r={0.4} style={{ fill: "var(--accent)" }} />
          ))}
        </svg>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn btn-ghost" disabled={points.length === 0} onClick={undo}>
            {t("site.manual.draw.undo")}
          </button>
          <button type="button" className="btn btn-ghost" disabled={points.length === 0} onClick={reset}>
            {t("site.manual.draw.reset")}
          </button>
          <button type="button" className="btn btn-primary" disabled={points.length < MIN_POINTS} onClick={startDimensioning}>
            {t("site.manual.draw.next")}
          </button>
          {onCancel && (
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              {t("site.selection.cancel")}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <KantenBearbeiten
      edges={edges}
      onEdges={setEdges}
      address={address}
      onAddress={setAddress}
      onBack={() => setEdges(null)}
      onSubmit={() =>
        void ensureProject().then((projectId) =>
          formSite.mutate({ projectId, edges, addressLabel: address.trim() }, { onSuccess: onFormed }),
        )
      }
      pending={formSite.isPending}
      error={formSite.error}
      onCancel={onCancel}
    />
  );
}
