/**
 * Baurahmen des Grundstücks als unverbindliche Simulation (Plan 3.5, Entscheidung D11).
 * Links „Was darf ich bauen?“ mit Herkunft je Wert, rechts der Lageplan mit beiden Auslegungen der Regeln.
 * Nicht ermittelte Werte erscheinen als solche, nie geschätzt; Hinweise nach L7 stehen darunter.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { EnvelopeOut, LimitOut, PartOut } from "../api/envelope";
import { sheetUrl, staffSheetUrl, useRequestSheet, useStaffRequestSheet } from "../api/envelope";
import { Planblatt } from "../components/plan/Planblatt";
import { useNotices } from "../site/GrundstueckPruefen";
import { formatNumber } from "../site/geo";
import { BaurahmenPlan } from "./BaurahmenPlan";
import { edgeLabel, limitValue, setbackValue, sortLimits } from "./format";

interface BaurahmenProps {
  envelope: EnvelopeOut;
  projectId: string;
  rolle?: "customer" | "architect";
}

/** Rückfalltexte, solange die Rechtstexte nach L7 nicht veröffentlicht sind (G16). */
const FALLBACK_NOTICES: Record<string, string> = {
  "notice.envelope_simulation": "envelope.notices.simulation",
  "notice.rules_simulation": "rules.notices.simulation",
  "notice.rules_lotissement": "rules.notices.lotissement",
  "notice.rules_upload": "rules.notices.upload",
  "notice.site_without_cadastre": "site.notices.without_cadastre",
  "notice.cadastre_accuracy": "site.notices.cadastre_accuracy",
  "notice.risks_public_data": "site.notices.risks_public_data",
};

function Quelle({ limit }: { limit: LimitOut }) {
  const { t } = useTranslation();
  const citation = limit.citation;
  if (!citation || citation.page == null) {
    return <span className="t-mute">{citation?.origin === "project" ? t("rules.origin.project") : "–"}</span>;
  }
  const label = t("rules.page", { page: citation.page });
  // Projektkorrektur mit Fundstelle (AN4): Seite und „Korrektur“
  const korrektur = citation.origin === "project" && <span className="t-mute"> · {t("rules.origin.correction")}</span>;
  if (!citation.source_url) {
    return (
      <span className="t-mute">
        {label}
        {korrektur}
      </span>
    );
  }
  return (
    <>
      <a className="link" href={citation.source_url} target="_blank" rel="noreferrer" title={citation.quote ?? undefined}>
        {label}
        {!citation.quote_verified && <span className="t-warn"> *</span>}
      </a>
      {korrektur}
    </>
  );
}

function Zeile({ kopf, wert, quelle }: { kopf: string; wert: string; quelle?: React.ReactNode }) {
  return (
    <tr className="border-b bd align-top">
      <th scope="row" className="py-2 pr-3 font-normal text-left">{kopf}</th>
      <td className="py-2 pr-3 num t-ink">{wert}</td>
      <td className="py-2 text-sm">{quelle ?? <span className="t-mute">–</span>}</td>
    </tr>
  );
}

function Teilflaeche({
  part,
  envelope,
  onHighlight,
}: {
  part: PartOut;
  envelope: EnvelopeOut;
  onHighlight?: (seq: number | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const limits = sortLimits(part.limits);
  const edges = envelope.edges.filter((edge) => edge.setbacks.some((s) => s.zone_code === part.zone_code));

  return (
    <section aria-labelledby={`baurahmen-${part.zone_code}`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`baurahmen-${part.zone_code}`} className="m-0 text-base font-medium t-ink">
          {t("rules.zone", { code: part.zone_code })}
        </h3>
        <span className="text-xs t-mute">
          {formatNumber(part.area_m2, lng, 0)} m² · {t(`rules.zoneStatus.${part.zone_status}`)}
        </span>
      </div>
      {part.excluded ? (
        <p className="t-warn text-sm m-0">{t(`envelope.excluded.${part.excluded}`)}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <caption className="sr-only">{t("envelope.caption", { code: part.zone_code })}</caption>
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.value")}</th>
                <th scope="col" className="py-2 font-medium">{t("rules.column.source")}</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => (
                <tr
                  key={`edge-${edge.seq}`}
                  className="border-b bd align-top"
                  onMouseEnter={() => onHighlight?.(edge.seq)}
                  onMouseLeave={() => onHighlight?.(null)}
                  data-testid={`baurahmen-zeile-kante-${edge.seq}`}
                >
                  <th scope="row" className="py-2 pr-3 font-normal text-left">{edgeLabel(edge, t)}</th>
                  <td className="py-2 pr-3 num t-ink">
                    {setbackValue(edge, t, lng)}
                    {edge.markers
                      .filter((marker) => marker !== "on_boundary_allowed")
                      .map((marker) => (
                        <span key={marker} className="block text-xs t-warn">{t(`envelope.marker.${marker}`)}</span>
                      ))}
                  </td>
                  <td className="py-2 text-sm">
                    <Quelle limit={{ ...(edge.setbacks[0] ?? {}), key: "", derived_from: null } as unknown as LimitOut} />
                  </td>
                </tr>
              ))}
              {limits.map((limit) => (
                <Zeile
                  key={`${limit.key}-${limit.building_kind}`}
                  kopf={`${t(`envelope.limit.${limit.key}`)}${
                    limit.building_kind !== "main" && limit.building_kind !== "any"
                      ? ` · ${t(`rules.building.${limit.building_kind}`)}`
                      : ""
                  }`}
                  wert={limitValue(limit, t, lng)}
                  quelle={<Quelle limit={limit} />}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {part.hints.length > 0 && (
        <ul className="m-0 pl-5 text-sm t-mute flex flex-col gap-1">
          {part.hints.map((hint, index) => (
            <li key={index}>{String(hint.params.summary ?? "")}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

const SHEET_POLL_MS = 2000;
const SHEET_POLL_MAX = 15;

function Steckbrief({
  projectId,
  envelope,
  rolle,
}: {
  projectId: string;
  envelope: EnvelopeOut;
  rolle: "customer" | "architect";
}) {
  const { t } = useTranslation();
  const customerRequest = useRequestSheet(projectId);
  const staffRequest = useStaffRequestSheet(projectId);
  const request = rolle === "architect" ? staffRequest : customerRequest;
  const url = rolle === "architect" ? staffSheetUrl(projectId) : sheetUrl(projectId);
  const ready = request.data?.status === "ready";
  const tries = useRef(0);
  const { mutate, data } = request;

  // Der Worker setzt das PDF; die Seite fragt selbst nach, statt einen zweiten Klick zu verlangen
  useEffect(() => {
    if (data?.status !== "pending" || tries.current >= SHEET_POLL_MAX) return;
    const timer = setTimeout(() => {
      tries.current += 1;
      mutate();
    }, SHEET_POLL_MS);
    return () => clearTimeout(timer);
  }, [data, mutate]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        className="btn btn-ghost"
        onClick={() => request.mutate()}
        disabled={request.isPending || envelope.status === "unavailable"}
      >
        {t("envelope.sheet.request")}
      </button>
      {request.data?.status === "pending" && <span className="text-sm t-mute">{t("envelope.sheet.pending")}</span>}
      {ready && (
        <a className="link" href={url} target="_blank" rel="noreferrer">
          {t("envelope.sheet.download")}
        </a>
      )}
      {request.isError && <span className="text-sm t-alert">{t("error.generic")}</span>}
    </div>
  );
}

export function Baurahmen({ envelope, projectId, rolle = "customer" }: BaurahmenProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const notices = useNotices(envelope.notices);
  const lenient = envelope.contours.lenient;
  const strict = envelope.contours.strict;

  if (envelope.status === "in_progress") {
    return <p className="t-mute text-sm">{t("envelope.inProgress")}</p>;
  }
  if (envelope.status === "unavailable") {
    return (
      <div className="flex flex-col gap-2">
        <p className="t-warn text-sm m-0">{t("envelope.unavailable")}</p>
        {/* Der Hinweis auf die Anfrage gilt Kunden; das Büro (Prüfung, Emprise Analyse) sieht den Grund im Regelwerk */}
        {rolle === "customer" && <p className="text-sm t-mute m-0">{t("envelope.unavailableHint")}</p>}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
      <div className="lg:col-span-5 flex flex-col gap-6">
        <div className="bg-paper px-4 py-3 border-l-2 bd-accent">
          <div className="eyebrow t-accent">{t("envelope.simulation.label")}</div>
          <p className="text-sm t-ink m-0 mt-1">{t("envelope.simulation.text")}</p>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 m-0">
          <div>
            <dt className="eyebrow">{t("envelope.area.lenient")}</dt>
            <dd className="num t-ink m-0">{formatNumber(lenient?.area_m2 ?? 0, lng, 0)} m²</dd>
          </div>
          <div>
            <dt className="eyebrow">{t("envelope.area.strict")}</dt>
            <dd className="num t-ink m-0">
              {formatNumber(strict?.area_m2 ?? 0, lng, 0)} m²{strict && !strict.complete ? " *" : ""}
            </dd>
          </div>
        </dl>
        {strict && !strict.complete && <p className="text-sm t-warn m-0">* {t("envelope.incomplete")}</p>}
        {envelope.parts.map((part) => (
          <Teilflaeche key={part.zone_code} part={part} envelope={envelope} onHighlight={setHighlighted} />
        ))}
        {envelope.constraints.filter((item) => item.effect !== "info").length > 0 && (
          <section className="flex flex-col gap-1">
            <h3 className="m-0 text-base font-medium t-ink">{t("envelope.constraints.title")}</h3>
            <ul className="m-0 pl-5 text-sm flex flex-col gap-1">
              {envelope.constraints
                .filter((item) => item.effect !== "info")
                .map((item, index) => (
                  <li key={index}>
                    <span className={item.effect === "no_build" ? "t-alert" : "t-warn"}>
                      {t(`envelope.legend.${item.effect}`)}
                    </span>{" "}
                    · {item.label}
                  </li>
                ))}
            </ul>
          </section>
        )}
        {envelope.warnings.length > 0 && (
          <section className="flex flex-col gap-1">
            <h3 className="m-0 text-base font-medium t-ink">{t("envelope.warnings.title")}</h3>
            <ul className="m-0 pl-5 text-sm t-mute flex flex-col gap-1">
              {envelope.warnings.map((code) => (
                <li key={code}>{t(`envelope.warning.${code}`, { defaultValue: code })}</li>
              ))}
            </ul>
          </section>
        )}
        <Steckbrief projectId={projectId} envelope={envelope} rolle={rolle} />
        <section aria-labelledby="baurahmen-hinweise" className="flex flex-col gap-2 text-sm">
          <h3 id="baurahmen-hinweise" className="eyebrow m-0">{t("site.notices.title")}</h3>
          {envelope.notices.map((key) => {
            const published = notices.data?.find((n) => n.key === key);
            return (
              <p key={key} className="m-0 t-mute" lang={published?.locale}>
                {published ? published.body : t(FALLBACK_NOTICES[key] ?? key, { defaultValue: key })}
              </p>
            );
          })}
        </section>
      </div>
      <div className="lg:col-span-7 flex flex-col gap-3">
        <Planblatt
          inhalt={t("envelope.plan.title")}
          schriftfeld={[
            { label: t("sheet.parcel"), wert: envelope.parcels.join(", ") },
            { label: t("envelope.area.lenient"), wert: `${formatNumber(lenient?.area_m2 ?? 0, lng, 0)} m²` },
            { label: t("envelope.area.strict"), wert: `${formatNumber(strict?.area_m2 ?? 0, lng, 0)} m²` },
          ]}
          fuss={
            <ul className="flex flex-wrap gap-x-5 gap-y-1 px-4 py-2 border-t bd m-0 list-none text-xs t-mute">
              <li className="flex items-center gap-2">
                <span className="inline-block w-5 h-2" style={{ background: "var(--accent)", opacity: 0.28 }} />
                {t("envelope.area.strict")}
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-5 h-2 border" style={{ borderColor: "var(--accent)", borderStyle: "dashed" }} />
                {t("envelope.area.lenient")}
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-5 h-2" style={{ background: "var(--warn)", opacity: 0.4 }} />
                {t("envelope.legend.restricts")}
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-5 h-2" style={{ background: "var(--alert)", opacity: 0.5 }} />
                {t("envelope.legend.no_build")}
              </li>
            </ul>
          }
        >
          <BaurahmenPlan envelope={envelope} highlightedSeq={highlighted} onHighlight={setHighlighted} />
        </Planblatt>
        <p className="text-xs t-mute m-0">
          {t("envelope.provenance", {
            engine: envelope.engine_version,
            hash: envelope.input_hash.replace("sha256:", "").slice(0, 12),
          })}
        </p>
      </div>
    </div>
  );
}
