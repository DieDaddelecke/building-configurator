/**
 * Kanten bemaßen und Grundstück bilden (Weg E, Plan 3.3): Vorschau, Länge je Kante, Bezeichnung, Absenden. Gemeinsam
 * für das freie Zeichnen und das Nachzeichnen eines Scans (AN7, docs/PLAN_AN7_SCAN.md 3.5). Der Server bildet das
 * Polygon aus denselben Kanten (L5); die Vorschau hier dient nur dem Auge.
 */

import { useId, useMemo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import type { ManualEdgeIn } from "../api/site";
import { Nordpfeil, strich } from "../components/plan/Masskette";
import { boundsOf, PlanSvg, ringPath } from "../components/plan/PlanSvg";
import { compass, formatNumber } from "./geo";
import { pointsFromEdges, polygonArea } from "./manual";

interface KantenBearbeitenProps {
  edges: ManualEdgeIn[];
  onEdges: (edges: ManualEdgeIn[]) => void;
  address: string;
  onAddress: (value: string) => void;
  /** Zurück zum Zeichnen bzw. Nachzeichnen. */
  onBack: () => void;
  onSubmit: () => void;
  pending: boolean;
  error: unknown;
  onCancel?: () => void;
  /** Zusatz unter der Fläche, etwa die Herkunft eines nachgezeichneten Scans. */
  herkunft?: ReactNode;
}

export function KantenBearbeiten({
  edges,
  onEdges,
  address,
  onAddress,
  onBack,
  onSubmit,
  pending,
  error,
  onCancel,
  herkunft,
}: KantenBearbeitenProps) {
  const { t, i18n } = useTranslation();
  const addressId = useId();
  const lng = i18n.language;
  const previewPoints = useMemo(() => pointsFromEdges(edges), [edges]);
  const previewBounds = boundsOf(previewPoints);
  const area = polygonArea(previewPoints);

  const updateLength = (index: number, raw: string) => {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    onEdges(edges.map((e, i) => (i === index ? { ...e, length_m: value } : e)));
  };

  const validLengths = edges.every((e) => Number.isFinite(e.length_m) && e.length_m > 0);
  const canSubmit = validLengths && address.trim().length > 0 && !pending;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-7 flex flex-col gap-3 min-w-0">
        <PlanSvg bounds={previewBounds} label={t("site.manual.preview")}>
          <path d={ringPath(previewPoints)} style={{ ...strich("var(--accent)", 0.15), fill: "var(--sheet)", fillOpacity: 0.85 }} />
          <g transform={`translate(${previewBounds.maxE + 3} ${-previewBounds.maxN + 1})`}>
            <Nordpfeil x={0} y={0} />
          </g>
        </PlanSvg>
        <p className="text-sm t-mute m-0">{t("site.manual.area", { area: formatNumber(area, lng, 0) })}</p>
        {herkunft}
        <button type="button" className="btn btn-ghost self-start" onClick={onBack}>
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
            onChange={(event) => onAddress(event.target.value)}
            placeholder={t("site.manual.address.placeholder")}
          />
          <p className="text-xs t-faint m-0">{t("site.manual.address.hint")}</p>
        </div>

        <p className="bg-tint t-ink px-4 py-3 text-sm m-0">{t("site.notices.manual_sketch")}</p>

        {error instanceof ApiError && (
          <p role="alert" className="t-alert text-sm m-0">
            {error.problem.title}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn btn-primary" disabled={!canSubmit} onClick={onSubmit}>
            {pending ? t("loading") : t("site.manual.submit")}
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
