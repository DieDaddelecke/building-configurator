/**
 * Bericht und Ausgabe (AN5, docs/PLAN_AN5_AUSGABE.md 3.4–3.7): Bericht als PDF in einer Sprache, DXF lokal und in
 * Lambert-93, GeoJSON. Lambert-93 und GeoJSON gibt es erst mit Lage. Der Bericht entsteht im Worker; die Seite
 * fragt nach wie beim Steckbrief. Ein fertiger Bericht gilt für den Stand, zu dem er angefordert wurde: Ändert
 * sich danach etwas (Regeln, Annahmen, Name oder Notiz), beginnt die Anforderung neu.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  dxfUrl,
  geojsonUrl,
  reportUrl,
  useAnalysis,
  useRequestReport,
  type ReportLocale,
} from "../api/analysis";
import { ApiError } from "../api/client";
import { useProjectDetails, type SiteOut } from "../api/site";

const POLL_MS = 2000;
/** Bis zu 90 s; der Job darf 180 s laufen, der Knopf fragt danach wieder von vorn. */
const POLL_MAX = 45;
const SPRACHEN: readonly ReportLocale[] = ["fr", "de"];

function Bericht({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  // Vorgewählt die Sprache der Oberfläche (3.6)
  const [sprache, setSprache] = useState<ReportLocale>(i18n.language.startsWith("de") ? "de" : "fr");
  const anfrage = useRequestReport(projectId);
  const [versuche, setVersuche] = useState(0);
  const { mutate, data, reset } = anfrage;
  const fertig = data?.status === "ready" && data.locale === sprache;
  const zuLange = data?.status === "pending" && versuche >= POLL_MAX;
  const inArbeit = anfrage.isPending || (data?.status === "pending" && !zuLange);

  // Der Worker setzt das PDF; die Seite fragt selbst nach, statt einen zweiten Klick zu verlangen
  useEffect(() => {
    if (data?.status !== "pending" || versuche >= POLL_MAX) return;
    const timer = setTimeout(() => {
      setVersuche((value) => value + 1);
      mutate(data.locale);
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [data, mutate, versuche]);

  const anfordern = () => {
    setVersuche(0);
    mutate(sprache);
  };

  return (
    <div className="flex flex-col gap-3">
      <h3 className="m-0 text-base font-medium t-ink">{t("analyse.output.report.title")}</h3>
      <p className="t-mute text-sm m-0">{t("analyse.output.report.intro")}</p>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label={t("analyse.output.report.language")} className="flex gap-1">
          {SPRACHEN.map((value) => (
            <button
              key={value}
              type="button"
              className="chip"
              aria-pressed={sprache === value}
              onClick={() => {
                setSprache(value);
                reset();
              }}
            >
              {t(`analyse.output.report.locale.${value}`)}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-ghost" onClick={anfordern} disabled={inArbeit}>
          {t("analyse.output.report.request")}
        </button>
        {inArbeit && (
          <span className="text-sm t-mute" role="status">
            {t("analyse.output.report.pending")}
          </span>
        )}
        {zuLange && (
          <span className="text-sm t-warn" role="status">
            {t("analyse.output.report.slow")}
          </span>
        )}
        {fertig && (
          <a className="btn btn-primary" href={reportUrl(projectId, sprache)} download>
            {t("analyse.output.report.download")}
          </a>
        )}
      </div>
      {anfrage.isError && (
        <p className="text-sm t-alert m-0" role="alert">
          {anfrage.error instanceof ApiError ? anfrage.error.problem.title : t("error.generic")}
        </p>
      )}
    </div>
  );
}

function Datei({ href, label, hinweis }: { href: string | null; label: string; hinweis: string }) {
  return (
    <li className="flex flex-col gap-1 py-2 border-t bd sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <span className="text-sm">
        <span className="t-ink">{label}</span>
        <span className="block t-mute">{hinweis}</span>
      </span>
      {href ? (
        <a className="btn btn-ghost self-start sm:self-auto" href={href} download>
          {label}
        </a>
      ) : (
        <button type="button" className="btn btn-ghost self-start sm:self-auto" disabled aria-disabled="true">
          {label}
        </button>
      )}
    </li>
  );
}

export function Ausgabe({ projectId, site }: { projectId: string; site: SiteOut }) {
  const { t } = useTranslation();
  const analysis = useAnalysis(projectId);
  const details = useProjectDetails(projectId);
  const lage = site.georeferenced;
  // Stand des Berichts: Ändert sich etwas, das er zeigt, gilt ein fertiger Bericht nicht mehr
  const stand = [analysis.data?.input_hash, site.revision, details.data?.name, details.data?.note].join("|");
  const ohneLage = t("analyse.output.files.needsPosition");

  return (
    <section aria-labelledby="ausgabe" className="flex flex-col gap-5">
      <h2 id="ausgabe" className="eyebrow m-0">{t("analyse.output.title")}</h2>
      <div className="karte p-5 flex flex-col gap-6">
        <Bericht key={stand} projectId={projectId} />
        <div className="flex flex-col gap-2">
          <h3 className="m-0 text-base font-medium t-ink">{t("analyse.output.files.title")}</h3>
          <p className="t-mute text-sm m-0">{t("analyse.output.files.intro")}</p>
          <ul className="m-0 p-0 list-none">
            <Datei
              href={dxfUrl(projectId, "local")}
              label={t("analyse.output.files.dxfLocal")}
              hinweis={t(lage ? "analyse.output.files.dxfLocalHint" : "analyse.output.files.dxfLocalFree")}
            />
            <Datei
              href={lage ? dxfUrl(projectId, "L93") : null}
              label={t("analyse.output.files.dxfL93")}
              hinweis={lage ? t("analyse.output.files.dxfL93Hint") : ohneLage}
            />
            <Datei
              href={lage ? geojsonUrl(projectId) : null}
              label={t("analyse.output.files.geojson")}
              hinweis={lage ? t("analyse.output.files.geojsonHint") : ohneLage}
            />
          </ul>
        </div>
        <p className="text-xs t-mute m-0">{t("analyse.output.disclaimer")}</p>
      </div>
    </section>
  );
}
