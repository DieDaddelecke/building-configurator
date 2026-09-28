/**
 * Analyse für den Entwurf (AN3, docs/PLAN_AN3_ANALYSE.md 3.10): bindende Grundfläche, Vollgeschosse und
 * Nutzfläche (SDP) als Spanne, darunter Herleitung mit Seite, Abstände je Grenze im Klartext, was nicht
 * gerechnet ist, und die Annahmen des Projekts zum Ändern. Zusatzdokumente sind nicht eingerechnet (E-AN3-2).
 */

import type { TFunction } from "i18next";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useAnalysis,
  useResetAnalysisParameters,
  useSaveAnalysisParameters,
  type AnalysisFootprintOut,
  type AnalysisOut,
  type AnalysisParametersIn,
  type AnalysisParametersOut,
  type AnalysisPartOut,
  type AnalysisStoreysOut,
  type StoreyAreaOut,
} from "../../api/analysis";
import type { EnvelopeOut } from "../../api/envelope";
import { edgeLabel } from "../../envelope/format";
import { formatNumber } from "../../site/geo";
import { aussagen } from "./abstand";

type Citation = AnalysisFootprintOut["candidates"][number]["citation"];

function Seite({ citation }: { citation: Citation | undefined }) {
  const { t } = useTranslation();
  if (!citation || citation.page == null) return <span className="t-mute">–</span>;
  const label = t("rules.page", { page: citation.page });
  if (!citation.source_url) return <span className="t-mute">{label}</span>;
  return (
    <>
      <a className="link" href={citation.source_url} target="_blank" rel="noreferrer" title={citation.quote ?? undefined}>
        {label}
        {!citation.quote_verified && <span className="t-warn"> *</span>}
      </a>
      {citation.origin === "project" && <span className="t-mute"> · {t("rules.origin.correction")}</span>}
    </>
  );
}

function spanne(low: number | null | undefined, high: number | null | undefined, language: string, unit = "m²"): string {
  if (low == null || high == null) return "–";
  const a = formatNumber(low, language, 0);
  const b = formatNumber(high, language, 0);
  return low === high ? `${a} ${unit}` : `${a} – ${b} ${unit}`;
}

function geschosse(storeys: AnalysisStoreysOut, t: TFunction): string {
  if (storeys.full_min == null || storeys.full_max == null) return t("analyse.analysis.storeys.unknown");
  const full =
    storeys.full_min === storeys.full_max ? String(storeys.full_min) : `${storeys.full_min} – ${storeys.full_max}`;
  if (storeys.top === "none") return full;
  const top = storeys.top === "attique" ? "attique" : storeys.top_certain ? "attic" : "atticPossible";
  return `${full} ${t(`analyse.analysis.storeys.top.${top}`)}`;
}

/** Geschossflächen des oberen Endes (PLAN_AN3_GABARIT 3.4): Vollgeschosse als Fläche, das oberste mit Anteil. */
function geschossflaechen(storeys: StoreyAreaOut[], t: TFunction, language: string): string {
  const liste = storeys.map((storey) =>
    storey.share === 1
      ? formatNumber(storey.area_m2, language, 0)
      : t("analyse.analysis.floorArea.top", {
          share: formatNumber(storey.share * 100, language, 0),
          area: formatNumber(storey.area_m2, language, 0),
        }),
  );
  return `${liste.join(" · ")} m²`;
}

function Kennzahl({ titel, wert, zusatz, warnung }: { titel: string; wert: string; zusatz?: string; warnung?: string }) {
  return (
    <div className="karte p-4 flex flex-col gap-1">
      <span className="eyebrow">{titel}</span>
      <span className="f-display text-2xl t-ink num">{wert}</span>
      {zusatz && <span className="text-sm t-mute">{zusatz}</span>}
      {warnung && <span className="text-sm t-warn">{warnung}</span>}
    </div>
  );
}

function Kennzahlen({ analysis }: { analysis: AnalysisOut }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const strict = analysis.footprint.strict;
  const lenient = analysis.footprint.lenient;
  const single = analysis.parts.length === 1 ? analysis.parts[0] : undefined;
  const binding = single?.footprint.strict?.binding;
  const floor = analysis.floor_area;
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Kennzahl
        titel={t("analyse.analysis.footprint.title")}
        wert={strict && lenient ? spanne(strict.value_m2, lenient.value_m2, lng) : "–"}
        zusatz={binding ? t(`analyse.analysis.footprint.binding.${binding}`) : undefined}
        warnung={strict && !strict.complete ? t("analyse.analysis.footprint.upperBound") : undefined}
      />
      <Kennzahl
        titel={t("analyse.analysis.storeys.title")}
        wert={single ? geschosse(single.storeys, t) : analysis.parts.map((p) => `${p.zone_code}: ${geschosse(p.storeys, t)}`).join(" · ")}
        zusatz={single ? t(`analyse.analysis.storeys.source.${single.storeys.source}`) : undefined}
      />
      <Kennzahl
        titel={t("analyse.analysis.floorArea.title")}
        wert={floor?.low_m2 != null ? spanne(floor.low_m2, floor.high_m2, lng) : t("analyse.analysis.floorArea.unknown")}
        zusatz={floor?.capped ? t("analyse.analysis.floorArea.capped") : t("analyse.analysis.floorArea.hint")}
        warnung={floor && floor.low_m2 != null && !floor.complete ? t("analyse.analysis.floorArea.upperBound") : undefined}
      />
    </div>
  );
}

function Herleitung({ part }: { part: AnalysisPartOut }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const sources = ["contour", "ratio", "absolute"] as const;
  const wert = (reading: "strict" | "lenient", source: (typeof sources)[number]) => {
    const candidate = part.footprint[reading]?.candidates.find((c) => c.source === source);
    if (!candidate) return null;
    if (candidate.value_m2 == null) return t(`analyse.analysis.candidate.status.${candidate.status}`, { defaultValue: "–" });
    return `${formatNumber(candidate.value_m2, lng, 0)} m²`;
  };
  const storeys = part.storeys;
  const floor = part.floor_area;
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <caption className="sr-only">{t("analyse.analysis.derivation", { zone: part.zone_code })}</caption>
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("analyse.analysis.candidate.title")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("analyse.analysis.reading.strict")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("analyse.analysis.reading.lenient")}</th>
              <th scope="col" className="py-2 font-medium">{t("rules.column.source")}</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => {
              const strict = wert("strict", source);
              if (strict == null) return null;
              const citation = part.footprint.strict?.candidates.find((c) => c.source === source)?.citation;
              return (
                <tr key={source} className="border-b bd align-top">
                  <th scope="row" className="py-2 pr-3 font-normal text-left">
                    {t(`analyse.analysis.candidate.${source}`)}
                    {part.footprint.strict?.binding === source && (
                      <span className="block text-xs t-accent">{t("analyse.analysis.candidate.binds")}</span>
                    )}
                  </th>
                  <td className="py-2 pr-3 num t-ink">{strict}</td>
                  <td className="py-2 pr-3 num t-ink">{wert("lenient", source)}</td>
                  <td className="py-2">{source === "contour" ? <span className="t-mute">{t("analyse.analysis.candidate.envelope")}</span> : <Seite citation={citation} />}</td>
                </tr>
              );
            })}
            <tr className="border-b bd align-top">
              <th scope="row" className="py-2 pr-3 font-normal text-left">{t("analyse.analysis.storeys.title")}</th>
              <td className="py-2 pr-3 t-ink" colSpan={2}>
                {geschosse(storeys, t)}
                <span className="block text-xs t-mute">{t(`analyse.analysis.storeys.source.${storeys.source}`)}</span>
                {storeys.notes
                  .filter((note) => note !== "attic_possible")
                  .map((note) => (
                    <span key={note} className="block text-xs t-warn">{t(`analyse.analysis.storeys.note.${note}`)}</span>
                  ))}
              </td>
              <td className="py-2"><Seite citation={storeys.citation} /></td>
            </tr>
            <tr className="align-top">
              <th scope="row" className="py-2 pr-3 font-normal text-left">{t("analyse.analysis.floorArea.title")}</th>
              <td className="py-2 pr-3 num t-ink" colSpan={2}>
                {floor.low_m2 != null ? spanne(floor.low_m2, floor.high_m2, lng) : t("analyse.analysis.floorArea.unknown")}
                {floor.cap_m2 != null && (
                  <span className="block text-xs t-mute">
                    {t("analyse.analysis.floorArea.cap", { value: formatNumber(floor.cap_m2, lng, 0) })}
                  </span>
                )}
                {floor.storeys_high.length > 0 && (
                  <span className="block text-xs t-mute">
                    {t("analyse.analysis.floorArea.storeys", { list: geschossflaechen(floor.storeys_high, t, lng) })}
                  </span>
                )}
                {floor.notes.includes("gabarit_limits_storeys") && (
                  <span className="block text-xs t-accent">{t("analyse.analysis.floorArea.gabaritLimits")}</span>
                )}
                {floor.reasons.map((reason) => (
                  <span key={reason} className="block text-xs t-warn">
                    {t(`analyse.analysis.reason.${reason}`, { defaultValue: reason })}
                  </span>
                ))}
              </td>
              <td className="py-2">{floor.cap_citation ? <Seite citation={floor.cap_citation} /> : <span className="t-mute">–</span>}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Abstaende({ envelope }: { envelope: EnvelopeOut }) {
  const { t, i18n } = useTranslation();
  const edges = envelope.edges.filter((edge) => edge.setbacks.length > 0);
  if (!edges.length) return null;
  const mehrereZonen = envelope.parts.length > 1;
  return (
    <section aria-labelledby="abstaende" className="flex flex-col gap-2">
      <h3 id="abstaende" className="m-0 text-base font-medium t-ink">{t("analyse.distance.title")}</h3>
      <ul className="m-0 p-0 list-none flex flex-col gap-2 text-sm">
        {edges.map((edge) => (
          <li key={edge.seq} className="flex flex-col gap-0.5" data-testid={`abstand-${edge.seq}`}>
            <span className="t-ink">{edgeLabel(edge, t)}</span>
            {aussagen(edge, envelope.parts, t, i18n.language).map((aussage) => (
              <span key={`${aussage.zone}-${aussage.kind}`} className="t-mute">
                {edge.setbacks.length > 1 && `${t(`rules.kind.${aussage.kind}`)}${mehrereZonen ? ` (${aussage.zone})` : ""}: `}
                {aussage.text}
                {aussage.setback.citation?.page != null && (
                  <>
                    {" · "}
                    <Seite citation={aussage.setback.citation} />
                  </>
                )}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}

const PARAMETER_NAMES = ["storey_height_m", "wall_share", "attic_share", "attique_share"] as const;
type ParameterName = (typeof PARAMETER_NAMES)[number];
const PERCENT = new Set<ParameterName>(["wall_share", "attic_share", "attique_share"]);

function anzeige(name: ParameterName, value: number): string {
  return PERCENT.has(name) ? String(Math.round(value * 1000) / 10) : String(value);
}

function Annahmen({ projectId, analysis }: { projectId: string; analysis: AnalysisOut }) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const save = useSaveAnalysisParameters(projectId);
  const reset = useResetAnalysisParameters(projectId);
  const values: AnalysisParametersOut = analysis.assumptions.values;
  const [form, setForm] = useState(() =>
    Object.fromEntries(
      PARAMETER_NAMES.map((name) => [name, { low: anzeige(name, values[name].low), high: anzeige(name, values[name].high) }]),
    ) as Record<ParameterName, { low: string; high: string }>,
  );

  const body = (): AnalysisParametersIn | null => {
    const result: Partial<AnalysisParametersIn> = {};
    for (const name of PARAMETER_NAMES) {
      const low = Number(form[name].low.replace(",", "."));
      const high = Number(form[name].high.replace(",", "."));
      if (!Number.isFinite(low) || !Number.isFinite(high) || form[name].low.trim() === "" || form[name].high.trim() === "") return null;
      const factor = PERCENT.has(name) ? 100 : 1;
      result[name] = { low: low / factor, high: high / factor };
    }
    return result as AnalysisParametersIn;
  };
  const neu = body();

  return (
    <details className="flex flex-col gap-3">
      <summary className="cursor-pointer eyebrow t-accent">
        {t("analyse.analysis.assumptions.title")}
        {analysis.assumptions.custom && <span className="t-warn"> · {t("analyse.analysis.assumptions.custom")}</span>}
      </summary>
      <div className="pt-4 flex flex-col gap-3">
        <p className="t-mute text-sm m-0">{t("analyse.analysis.assumptions.intro")}</p>
        {PARAMETER_NAMES.map((name) => (
          <fieldset key={name} className="flex flex-wrap items-end gap-3 border-0 p-0 m-0">
            <legend className="text-sm mb-1">{t(`analyse.analysis.assumptions.${name}`)}</legend>
            {(["low", "high"] as const).map((end) => (
              <div key={end} className="flex flex-col gap-1">
                <label htmlFor={`${id}-${name}-${end}`} className="text-xs t-mute">
                  {t(`analyse.analysis.assumptions.${end}`)}
                </label>
                <input
                  id={`${id}-${name}-${end}`}
                  className="field max-w-24 f-mono"
                  inputMode="decimal"
                  value={form[name][end]}
                  onChange={(event) => setForm({ ...form, [name]: { ...form[name], [end]: event.target.value } })}
                />
              </div>
            ))}
            <span className="text-xs t-mute pb-2">
              {t("analyse.analysis.assumptions.default", {
                low: formatNumber(
                  PERCENT.has(name) ? analysis.assumptions.defaults[name].low * 100 : analysis.assumptions.defaults[name].low,
                  i18n.language,
                  PERCENT.has(name) ? 0 : 2,
                ),
                high: formatNumber(
                  PERCENT.has(name) ? analysis.assumptions.defaults[name].high * 100 : analysis.assumptions.defaults[name].high,
                  i18n.language,
                  PERCENT.has(name) ? 0 : 2,
                ),
              })}
            </span>
          </fieldset>
        ))}
        {(save.isError || neu === null) && (
          <p className="t-alert m-0" role="alert">{t("analyse.analysis.assumptions.invalid")}</p>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!neu || save.isPending}
            onClick={() => neu && save.mutate(neu)}
          >
            {t("analyse.analysis.assumptions.save")}
          </button>
          {analysis.assumptions.custom && (
            <button
              type="button"
              className="btn btn-ghost"
              disabled={reset.isPending}
              onClick={() => reset.mutate()}
            >
              {t("analyse.analysis.assumptions.reset")}
            </button>
          )}
        </div>
      </div>
    </details>
  );
}

export function Analyse({ projectId, envelope }: { projectId: string; envelope: EnvelopeOut }) {
  const { t } = useTranslation();
  const analysis = useAnalysis(projectId);
  if (analysis.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (analysis.isError) return <p className="t-alert" role="alert">{t("error.generic")}</p>;
  const data = analysis.data;
  const stricter = data.supplement_stricter.map((kind) => t(`rules.kind.${kind}`)).join(", ");

  return (
    <section aria-labelledby="analyse" className="flex flex-col gap-5">
      <h2 id="analyse" className="eyebrow m-0">{t("analyse.analysis.title")}</h2>
      {data.parts.length === 0 ? (
        <p className="t-mute m-0">
          {t(data.status === "in_progress" ? "analyse.analysis.inProgress" : "analyse.analysis.unavailable")}
        </p>
      ) : (
        <>
          <Kennzahlen analysis={data} />
          {stricter && (
            <p className="t-warn text-sm m-0" role="note">
              {t("analyse.analysis.supplementStricter", { kinds: stricter })}
            </p>
          )}
          {data.parts.map((part) => (
            <section key={part.zone_code} aria-label={t("analyse.analysis.derivation", { zone: part.zone_code })}>
              {data.parts.length > 1 && <h3 className="m-0 mb-2 text-base font-medium t-ink">{t("rules.zone", { code: part.zone_code })}</h3>}
              <Herleitung part={part} />
            </section>
          ))}
          <Abstaende envelope={envelope} />
          <details className="flex flex-col gap-2">
            <summary className="cursor-pointer eyebrow t-accent">{t("analyse.analysis.notCounted.title")}</summary>
            <ul className="m-0 pt-3 pl-5 text-sm t-mute flex flex-col gap-1">
              {data.not_counted.map((key) => (
                <li key={key}>{t(`analyse.analysis.notCounted.${key}`)}</li>
              ))}
            </ul>
          </details>
          <Annahmen key={JSON.stringify(data.assumptions.values)} projectId={projectId} analysis={data} />
        </>
      )}
    </section>
  );
}
