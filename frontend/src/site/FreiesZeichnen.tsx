/**
 * Weg E (Plan 3.3): Grundstück frei zeichnen und bemaßen, ohne Kataster. Kein Bebaubarkeitscheck – G2
 * und G3 werden für dieses Grundstück nicht aufgerufen (D13). Zeichenfläche als freies Koordinatenraster
 * ohne Kartenbezug (Plan 3.3, Prüfprotokoll 10.4).
 */

import { useId, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import { useFormManualSite, type ManualEdgeIn } from "../api/site";
import { Nordpfeil, strich } from "../components/plan/Masskette";
import { boundsOf, PlanSvg, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { compass, formatNumber } from "./geo";
import { edgesFromPoints, pointsFromEdges, polygonArea } from "./manual";

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
  const { t, i18n } = useTranslation();
  const addressId = useId();
  const [points, setPoints] = useState<LocalPoint[]>([]);
  const [edges, setEdges] = useState<ManualEdgeIn[] | null>(null);
  const [address, setAddress] = useState("");
  const formSite = useFormManualSite();
  const { ref: svgRef, fromEvent } = useSvgPoint();
  const lng = i18n.language;

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

  const previewPoints = useMemo(() => (edges ? pointsFromEdges(edges) : points), [edges, points]);
  const previewBounds = boundsOf(previewPoints);
  const area = edges ? polygonArea(previewPoints) : 0;

  const updateLength = (index: number, raw: string) => {
    if (!edges) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    setEdges(edges.map((e, i) => (i === index ? { ...e, length_m: value } : e)));
  };

  const validLengths = edges?.every((e) => Number.isFinite(e.length_m) && e.length_m > 0) ?? false;
  const canSubmit = edges != null && validLengths && address.trim().length > 0 && !formSite.isPending;

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
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-7 flex flex-col gap-3">
        <PlanSvg bounds={previewBounds} label={t("site.manual.preview")}>
          <path d={ringPath(previewPoints)} style={{ ...strich("var(--accent)", 0.15), fill: "var(--sheet)", fillOpacity: 0.85 }} />
          <g transform={`translate(${previewBounds.maxE + 3} ${-previewBounds.maxN + 1})`}>
            <Nordpfeil x={0} y={0} />
          </g>
        </PlanSvg>
        <p className="text-sm t-mute m-0">{t("site.manual.area", { area: formatNumber(area, lng, 0) })}</p>
        <button type="button" className="btn btn-ghost self-start" onClick={() => setEdges(null)}>
          {t("site.manual.backToDrawing")}
        </button>
      </div>

      <div className="lg:col-span-5 flex flex-col gap-6">
        <section aria-labelledby="kanten-bemassen">
          <h2 id="kanten-bemassen" className="eyebrow mb-2">
            {t("site.manual.edges.title")}
          </h2>
          <ul className="m-0 p-0 list-none flex flex-col gap-3">
            {edges.map((edge, i) => (
              <li key={i} className="flex items-center justify-between gap-3">
                <span className="t-mute text-sm">
                  {t("site.manual.edges.label", { index: i + 1 })} · {t(`site.compass.${compass(edge.angle_deg)}`)}
                </span>
                <input
                  className="field w-28"
                  type="number"
                  min={1}
                  max={500}
                  step={0.1}
                  value={edge.length_m}
                  onChange={(event) => updateLength(i, event.target.value)}
                  aria-label={t("site.manual.edges.label", { index: i + 1 })}
                />
              </li>
            ))}
          </ul>
        </section>

        <div className="flex flex-col gap-2">
          <label htmlFor={addressId} className="text-sm font-medium t-ink">
            {t("site.manual.address.label")}
          </label>
          <input
            id={addressId}
            className="field"
            value={address}
            autoComplete="street-address"
            onChange={(event) => setAddress(event.target.value)}
            placeholder={t("site.manual.address.placeholder")}
          />
          <p className="text-xs t-faint m-0">{t("site.manual.address.hint")}</p>
        </div>

        <p className="bg-tint t-ink px-4 py-3 text-sm m-0">{t("site.notices.manual_sketch")}</p>

        {formSite.error instanceof ApiError && (
          <p role="alert" className="t-alert text-sm m-0">
            {formSite.error.problem.title}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={() =>
              void ensureProject().then((projectId) =>
                formSite.mutate({ projectId, edges, addressLabel: address.trim() }, { onSuccess: onFormed }),
              )
            }
          >
            {formSite.isPending ? t("loading") : t("site.manual.submit")}
          </button>
          {onCancel && (
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              {t("site.selection.cancel")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
