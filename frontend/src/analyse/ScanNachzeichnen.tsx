/**
 * Gescannten Plan als Vorlage nachzeichnen (AN7, docs/PLAN_AN7_SCAN.md 3.5): Seite als Bild, Maßstab aus dem Plan
 * (mit Papiermaß) oder über zwei Punkte mit bekanntem Abstand, Ecken im Uhrzeigersinn anklicken, dann die Kanten wie
 * beim freien Zeichnen bemaßen. Kein automatisches Erkennen der Parzelle; der Server speichert den Scan nicht.
 */

import { useId, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import { useFormManualSite, useScanPreview, type ManualEdgeIn, type ScanPreviewOut, type TraceIn } from "../api/site";
import { formatNumber } from "../site/geo";
import { KantenBearbeiten } from "../site/KantenBearbeiten";
import {
  edgesFromPixels,
  MAX_SCAN_PAGES,
  metresPerPxFromPoints,
  metresPerPxFromScale,
  parseLength,
  parseScale,
  type PixelPoint,
} from "./scan-nachzeichnen";

const PREFIX = "analyse.trace";
const MIN_CORNERS = 3;
const MAX_ZOOM = 4;

interface ScanNachzeichnenProps {
  projectId: string;
  file: File;
  addressLabel: string;
  onFormed: () => void;
  onCancel: () => void;
}

export function ScanNachzeichnen({ projectId, file, addressLabel, onFormed, onCancel }: ScanNachzeichnenProps) {
  const { t } = useTranslation();
  const pageId = useId();
  const [page, setPage] = useState(1);
  const vorschau = useScanPreview(projectId, file, page);
  const code = vorschau.error instanceof ApiError ? vorschau.error.problem.code : "";
  const seiten = Math.min(vorschau.data?.page_count ?? 1, MAX_SCAN_PAGES);

  return (
    <section className="karte p-5 flex flex-col gap-4" aria-labelledby="nachzeichnen-titel">
      <h3 id="nachzeichnen-titel" className="f-display text-xl">
        {t(`${PREFIX}.title`)}
      </h3>
      <p className="t-mute text-sm m-0">{t(`${PREFIX}.intro`, { file: file.name })}</p>
      {seiten > 1 && (
        <div className="flex items-center gap-2">
          <label htmlFor={pageId} className="text-sm">
            {t(`${PREFIX}.page`)}
          </label>
          <select id={pageId} className="field max-w-28" value={page} onChange={(event) => setPage(Number(event.target.value))}>
            {Array.from({ length: seiten }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      )}
      {vorschau.isPending && (
        <p className="t-mute m-0" role="status">
          {t(`${PREFIX}.preparing`)}
        </p>
      )}
      {vorschau.isError && (
        <>
          <p className="t-alert m-0" role="alert">
            {t([`${PREFIX}.error.${code}`, `analyse.upload.error.${code}`, "error.generic"])}
          </p>
          <div>
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              {t("analyse.upload.cancel")}
            </button>
          </div>
        </>
      )}
      {vorschau.data && (
        <Nachzeichnen
          key={page}
          projectId={projectId}
          preview={vorschau.data}
          fileName={file.name}
          addressLabel={addressLabel}
          onFormed={onFormed}
          onCancel={onCancel}
        />
      )}
    </section>
  );
}

type Weg = TraceIn["scale_method"];

function Nachzeichnen({
  projectId,
  preview,
  fileName,
  addressLabel,
  onFormed,
  onCancel,
}: {
  projectId: string;
  preview: ScanPreviewOut;
  fileName: string;
  addressLabel: string;
  onFormed: () => void;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const scaleId = useId();
  const lengthId = useId();
  const paper = preview.paper_mm;
  const [weg, setWeg] = useState<Weg>(preview.metres_per_px != null ? "plan" : "calibrated");
  const [massstab, setMassstab] = useState(preview.scale != null ? String(preview.scale) : "");
  const [bezug, setBezug] = useState<PixelPoint[]>([]);
  const [laenge, setLaenge] = useState("");
  const [ecken, setEcken] = useState<PixelPoint[]>([]);
  const [zoom, setZoom] = useState(1);
  const [edges, setEdges] = useState<ManualEdgeIn[] | null>(null);
  const [address, setAddress] = useState(addressLabel);
  const formSite = useFormManualSite();
  const W = preview.width_px;
  const H = preview.height_px;

  const scale = parseScale(massstab);
  const length = parseLength(laenge);
  const metresPerPx =
    weg === "plan"
      ? paper && scale
        ? metresPerPxFromScale(paper[0]!, scale, W)
        : null
      : bezug.length === 2 && length
        ? metresPerPxFromPoints(bezug[0]!, bezug[1]!, length)
        : null;
  // Beim Kalibrieren setzen die ersten beiden Klicks die Bezugsstrecke, danach die Ecken
  const kalibriert = weg === "plan" || bezug.length === 2;

  const klick = (event: ReactMouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const point: PixelPoint = [
      Math.round(((event.clientX - rect.left) / rect.width) * W * 10) / 10,
      Math.round(((event.clientY - rect.top) / rect.height) * H * 10) / 10,
    ];
    if (!kalibriert) setBezug((current) => [...current, point]);
    else setEcken((current) => [...current, point]);
  };

  if (edges) {
    const trace: TraceIn =
      weg === "plan"
        ? { file_name: fileName, page: preview.page, scale_method: "plan", scale: scale ?? undefined }
        : { file_name: fileName, page: preview.page, scale_method: "calibrated", reference_m: length ?? undefined };
    return (
      <KantenBearbeiten
        edges={edges}
        onEdges={setEdges}
        address={address}
        onAddress={setAddress}
        onBack={() => setEdges(null)}
        onSubmit={() => formSite.mutate({ projectId, edges, addressLabel: address.trim(), trace }, { onSuccess: onFormed })}
        pending={formSite.isPending}
        error={formSite.error}
        onCancel={onCancel}
        herkunft={<p className="text-sm t-mute m-0">{t(`${PREFIX}.editHint`)}</p>}
      />
    );
  }

  const r = Math.max(W, H) / 250 / zoom;
  const linie = (points: readonly PixelPoint[]) => points.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join("");

  return (
    <div className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-2 border-0 p-0 m-0">
        <legend className="text-sm font-medium t-ink mb-1">{t(`${PREFIX}.scaleTitle`)}</legend>
        <label className="flex items-start gap-2 text-sm">
          <input type="radio" name="weg" checked={weg === "plan"} disabled={!paper} onChange={() => setWeg("plan")} />
          <span>
            {t(`${PREFIX}.fromPlan`)}
            {!paper && <span className="block t-mute">{t(`${PREFIX}.noPaper`)}</span>}
          </span>
        </label>
        {weg === "plan" && paper && (
          <div className="flex flex-col gap-1 pl-6">
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor={scaleId} className="text-sm">
                {t(`${PREFIX}.scale`)}
              </label>
              <span className="f-mono">1&nbsp;:</span>
              <input
                id={scaleId}
                className="field max-w-28"
                inputMode="numeric"
                value={massstab}
                aria-invalid={massstab !== "" && scale === null}
                onChange={(event) => setMassstab(event.target.value)}
              />
              {preview.scales.length > 1 &&
                preview.scales.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="chip f-mono"
                    aria-pressed={scale === value}
                    onClick={() => setMassstab(String(value))}
                  >
                    1:{value}
                  </button>
                ))}
            </div>
            <p className="t-mute text-xs m-0">
              {preview.scale != null && scale === preview.scale
                ? t(`${PREFIX}.scaleFound`, {
                    scale: preview.scale,
                    width: formatNumber(paper[0]!, i18n.language, 0),
                    height: formatNumber(paper[1]!, i18n.language, 0),
                  })
                : t(preview.scales.length > 1 ? `${PREFIX}.scaleChoose` : `${PREFIX}.scaleEnter`)}
            </p>
          </div>
        )}
        <label className="flex items-start gap-2 text-sm">
          <input type="radio" name="weg" checked={weg === "calibrated"} onChange={() => setWeg("calibrated")} />
          <span>
            {t(`${PREFIX}.calibrate`)}
            <span className="block t-mute">{t(`${PREFIX}.calibrateWhy`)}</span>
          </span>
        </label>
        {weg === "calibrated" && (
          <div className="flex flex-col gap-2 pl-6">
            <p className="text-sm m-0 t-warn" role="status">
              {t(`${PREFIX}.${bezug.length === 0 ? "calibrateFirst" : bezug.length === 1 ? "calibrateSecond" : "calibrateLength"}`)}
            </p>
            {bezug.length === 2 && (
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor={lengthId} className="text-sm">
                  {t(`${PREFIX}.length`)}
                </label>
                <input
                  id={lengthId}
                  className="field max-w-28"
                  inputMode="decimal"
                  value={laenge}
                  aria-invalid={laenge !== "" && length === null}
                  onChange={(event) => setLaenge(event.target.value)}
                />
                <span className="text-sm">m</span>
                <button type="button" className="link text-sm" onClick={() => setBezug([])}>
                  {t(`${PREFIX}.calibrateAgain`)}
                </button>
              </div>
            )}
          </div>
        )}
      </fieldset>

      {kalibriert && <p className="text-sm m-0">{t(`${PREFIX}.corners`)}</p>}
      <div className="overflow-auto border bd bg-sheet" style={{ maxHeight: "70vh" }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="block select-none"
          style={{ width: `${zoom * 100}%`, height: "auto", cursor: "crosshair" }}
          role="img"
          aria-label={t(`${PREFIX}.canvas`)}
          onClick={klick}
        >
          <image href={preview.image} x={0} y={0} width={W} height={H} />
          {bezug.length > 0 && (
            <g style={{ stroke: "var(--warn)", fill: "var(--warn)" }}>
              {bezug.length === 2 && <path d={linie(bezug)} strokeWidth={2} vectorEffect="non-scaling-stroke" />}
              {bezug.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={r} />
              ))}
            </g>
          )}
          {ecken.length > 0 && (
            <g style={{ stroke: "var(--accent)", fill: "none" }}>
              <path d={linie(ecken)} strokeWidth={2} vectorEffect="non-scaling-stroke" />
              {ecken.length >= MIN_CORNERS && (
                <path
                  d={linie([ecken[ecken.length - 1]!, ecken[0]!])}
                  strokeWidth={1.5}
                  strokeDasharray="6 4"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {ecken.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={r} style={{ fill: "var(--accent)", stroke: "none" }} />
              ))}
            </g>
          )}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn btn-ghost" disabled={zoom <= 1} onClick={() => setZoom((z) => z - 1)} aria-label={t(`${PREFIX}.zoomOut`)}>
          −
        </button>
        <span className="text-sm f-mono num" aria-live="polite">
          {zoom}×
        </span>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => setZoom((z) => z + 1)}
          aria-label={t(`${PREFIX}.zoomIn`)}
        >
          +
        </button>
        <button type="button" className="btn btn-ghost" disabled={ecken.length === 0} onClick={() => setEcken((e) => e.slice(0, -1))}>
          {t("site.manual.draw.undo")}
        </button>
        <button type="button" className="btn btn-ghost" disabled={ecken.length === 0} onClick={() => setEcken([])}>
          {t("site.manual.draw.reset")}
        </button>
      </div>
      <p className="t-mute text-sm m-0">
        {t(`${PREFIX}.cornerCount`, { count: ecken.length })}
        {metresPerPx != null && ecken.length >= MIN_CORNERS && (
          <> · {t(`${PREFIX}.scaleCheck`, { width: formatNumber(metresPerPx * W, i18n.language, 0) })}</>
        )}
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-primary"
          disabled={metresPerPx == null || ecken.length < MIN_CORNERS}
          onClick={() => metresPerPx != null && setEdges(edgesFromPixels(ecken, metresPerPx))}
        >
          {t(`${PREFIX}.next`)}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {t("analyse.upload.cancel")}
        </button>
      </div>
    </div>
  );
}
