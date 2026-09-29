import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { useRefreshAnalysisOnTerrain } from "../api/analysis";
import { useStaffEnvelope } from "../api/envelope";
import { pluOf, useProjectRegulations } from "../api/regulations";
import { useStaffProjectRules } from "../api/rules";
import { useClassifyEdge, useDeleteProject, useSite, type EdgeKind, type SiteOut } from "../api/site";
import { Baurahmen } from "../envelope/Baurahmen";
import { FreiesZeichnen } from "../site/FreiesZeichnen";
import { GelaendeRisiken } from "../site/GelaendeRisiken";
import { formatNumber } from "../site/geo";
import { KantenListe } from "../site/KantenListe";
import { SiteLageplan } from "../site/SiteLageplan";
import { Analyse } from "./Analyse";
import { Ausgabe } from "./Ausgabe";
import { Bebauungsplan } from "./Bebauungsplan";
import { GabaritSchnitt } from "./GabaritSchnitt";
import { LageEinpassen } from "./LageEinpassen";
import { ParzelleHochladen } from "./ParzelleHochladen";
import { ProjektKopf } from "./ProjektKopf";
import { RegelnKorrekturen } from "./RegelnKorrekturen";
import { Zusatzdokumente } from "./Zusatzdokumente";

type Weg = "wahl" | "datei" | "zeichnen";

function Herkunft({ site }: { site: SiteOut }) {
  const { t, i18n } = useTranslation();
  const quelle = site.source_info as {
    file_name?: string;
    layer?: string;
    crs?: string;
    scale?: number;
    scale_source?: "file" | "input";
    indices?: number[];
    short_piece_m?: number;
    position?: { method?: "map" | "file"; at?: string };
    /** Nach einem Scan nachgezeichnet (AN7, docs/PLAN_AN7_SCAN.md 3.5) */
    trace?: { file_name: string; page?: number; scale_method: "plan" | "calibrated"; scale?: number; reference_m?: number };
  };
  const trace = quelle.trace;
  const datei = trace?.file_name ?? quelle.file_name;
  const lage = !site.georeferenced
    ? t("analyse.site.local")
    : site.origin === "parcel"
      ? t("analyse.site.georeferenced")
      : quelle.position?.method === "map"
        ? t("analyse.site.positionMap", {
            date: quelle.position.at ? new Date(quelle.position.at).toLocaleDateString(i18n.language) : "",
          })
        : t("analyse.site.positionFile");
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm m-0">
      <dt className="t-mute">{t("analyse.site.area")}</dt>
      <dd className="f-mono num m-0">{formatNumber(site.area_m2, i18n.language)} m²</dd>
      <dt className="t-mute">{t("analyse.site.origin")}</dt>
      <dd className="m-0">{t(trace ? "analyse.origin.traced" : `analyse.origin.${site.origin}`)}</dd>
      <dt className="t-mute">{t("analyse.site.position")}</dt>
      <dd className="m-0">{lage}</dd>
      {datei && (
        <>
          <dt className="t-mute">{t("analyse.site.file")}</dt>
          <dd className="m-0 break-all">
            {datei}
            {quelle.layer && <span className="t-mute"> · {quelle.layer}</span>}
            {trace?.page && trace.page > 1 && <span className="t-mute"> · {t("rules.page", { page: trace.page })}</span>}
          </dd>
        </>
      )}
      {quelle.indices && quelle.indices.length > 1 && (
        <>
          <dt className="t-mute">{t("analyse.site.outline")}</dt>
          <dd className="m-0">{t("analyse.site.pieces", { count: quelle.indices.length })}</dd>
        </>
      )}
      {quelle.short_piece_m && (
        <>
          <dt className="t-mute">{t("analyse.site.edges")}</dt>
          <dd className="m-0">
            {t("analyse.site.shortPieces", {
              length: formatNumber(quelle.short_piece_m, i18n.language, Number.isInteger(quelle.short_piece_m) ? 0 : 1),
            })}
          </dd>
        </>
      )}
      {trace?.scale_method === "calibrated" && trace.reference_m && (
        <>
          <dt className="t-mute">{t("analyse.site.scale")}</dt>
          <dd className="m-0">
            {t("analyse.site.scaleCalibrated", { length: formatNumber(trace.reference_m, i18n.language, 1) })}
          </dd>
        </>
      )}
      {trace?.scale_method === "plan" && trace.scale && (
        <>
          <dt className="t-mute">{t("analyse.site.scale")}</dt>
          <dd className="m-0">
            <span className="f-mono">1:{trace.scale}</span>
            <span className="t-mute"> · {t("analyse.site.scaleFile")}</span>
          </dd>
        </>
      )}
      {quelle.scale && (
        <>
          <dt className="t-mute">{t("analyse.site.scale")}</dt>
          <dd className="m-0">
            <span className="f-mono">1:{quelle.scale}</span>
            <span className="t-mute"> · {t(quelle.scale_source === "input" ? "analyse.site.scaleInput" : "analyse.site.scaleFile")}</span>
          </dd>
        </>
      )}
    </dl>
  );
}

/** Regeln mit Korrekturen (AN4), dann Analyse, Gabarit und Schnitt (AN3), Bericht und Ausgabe (AN5) und Baurahmen
 *  aus dem hochgeladenen Bebauungsplan (AN2), über die Büro-Endpunkte (E-AN2-7). Die Regeln stehen vor den
 *  Ergebnissen, weil alles darunter aus ihnen folgt (E-AN4-6). Den Steckbrief des Konfigurators ersetzt der Bericht. */
function Ergebnis({ projectId, site }: { projectId: string; site: SiteOut }) {
  const revision = site.revision;
  const { t } = useTranslation();
  const envelope = useStaffEnvelope(projectId);
  const rules = useStaffProjectRules(projectId);
  useRefreshAnalysisOnTerrain(projectId, site.terrain.status);
  if (envelope.isPending || rules.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (envelope.isError || rules.isError) return <p className="t-alert" role="alert">{t("error.generic")}</p>;
  return (
    <>
      <RegelnKorrekturen key={revision} projectId={projectId} rules={rules.data} />
      <Analyse projectId={projectId} envelope={envelope.data} />
      <GabaritSchnitt projectId={projectId} envelope={envelope.data} />
      <Ausgabe projectId={projectId} site={site} />
      <section aria-labelledby="baurahmen" className="flex flex-col gap-5">
        <h2 id="baurahmen" className="eyebrow m-0">{t("analyse.envelope")}</h2>
        <Baurahmen key={revision} envelope={envelope.data} projectId={projectId} rolle="architect" steckbrief={false} />
      </section>
    </>
  );
}

/** Ein Projekt: Parzelle einbringen, Kanten einordnen (AN1), Bebauungsplan hochladen und Zone wählen; daraus
 *  Regeln und Baurahmen (AN2). Zusatzdokumente und die Analyse für den Entwurf (AN3). Regeln korrigieren, ergänzen,
 *  aus Zusatzdokumenten übernehmen und Stände vergleichen (AN4). Name, Notiz, Archiv, Lage auf der Karte, Gelände
 *  und Risiken, Bericht und Dateien (AN5). */
export function ProjektSeite() {
  const { t } = useTranslation();
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const site = useSite(projectId);
  const regulations = useProjectRegulations(projectId);
  const entfernen = useDeleteProject();
  const [weg, setWeg] = useState<Weg>("wahl");
  const [hervorgehoben, setHervorgehoben] = useState<number | null>(null);
  const [einpassen, setEinpassen] = useState(false);
  const zoneGewaehlt = Boolean(pluOf(regulations.data)?.zone_code);

  const loeschen = () => {
    if (!window.confirm(t("analyse.site.deleteConfirm"))) return;
    entfernen.mutate(projectId, { onSuccess: () => void navigate("/") });
  };

  return (
    <div className="flex flex-col gap-8">
      <ProjektKopf
        projectId={projectId}
        adresse={site.data?.address_label}
        onLoeschen={loeschen}
        loeschtGerade={entfernen.isPending}
      />

      {site.isPending && <p className="t-mute">{t("loading")}</p>}
      {site.isError && <p className="t-alert">{t("error.generic")}</p>}

      {site.isSuccess && site.data === null && (
        <>
          {weg === "wahl" && (
            <section className="karte p-5 flex flex-col gap-4" aria-labelledby="parzelle">
              <h2 id="parzelle" className="f-display text-xl">{t("analyse.site.choose")}</h2>
              <p className="t-mute m-0">{t("analyse.site.chooseIntro")}</p>
              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn btn-primary" onClick={() => setWeg("datei")}>
                  {t("analyse.site.fromFile")}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setWeg("zeichnen")}>
                  {t("analyse.site.draw")}
                </button>
              </div>
            </section>
          )}
          {weg === "datei" && (
            <ParzelleHochladen
              projectId={projectId}
              onFormed={() => setWeg("wahl")}
              onCancel={() => setWeg("wahl")}
            />
          )}
          {weg === "zeichnen" && (
            <FreiesZeichnen
              ensureProject={() => Promise.resolve(projectId)}
              onFormed={() => setWeg("wahl")}
              onCancel={() => setWeg("wahl")}
            />
          )}
        </>
      )}

      {site.data && (
        <>
          {einpassen ? (
            <LageEinpassen site={site.data} onFertig={() => setEinpassen(false)} />
          ) : (
            <Grundstueck
              site={site.data}
              highlighted={hervorgehoben}
              onHighlight={setHervorgehoben}
              onEinpassen={() => setEinpassen(true)}
              next={!regulations.data?.length}
            />
          )}
          <Bebauungsplan projectId={projectId} />
          <Zusatzdokumente projectId={projectId} />
          {zoneGewaehlt && <Ergebnis projectId={projectId} site={site.data} />}
        </>
      )}
    </div>
  );
}

function Grundstueck({
  site,
  highlighted,
  onHighlight,
  onEinpassen,
  next,
}: {
  site: SiteOut;
  highlighted: number | null;
  onHighlight: (seq: number | null) => void;
  onEinpassen: () => void;
  next: boolean;
}) {
  const { t } = useTranslation();
  const classify = useClassifyEdge(site);

  return (
    <div className="grid gap-8 lg:grid-cols-[3fr_2fr] items-start [&>*]:min-w-0">
      <div className="karte p-4">
        <SiteLageplan site={site} highlightedSeq={highlighted} onHighlight={onHighlight} />
      </div>
      <div className="flex flex-col gap-6">
        <section aria-labelledby="herkunft" className="karte p-5">
          <h2 id="herkunft" className="eyebrow mb-3">{t("analyse.site.summary")}</h2>
          <Herkunft site={site} />
          {site.placement && (
            <div className="flex flex-col gap-2 mt-4">
              <button type="button" className="btn btn-ghost self-start" onClick={onEinpassen}>
                {t(site.georeferenced ? "analyse.position.correct" : "analyse.position.set")}
              </button>
              {!site.georeferenced && <p className="t-mute text-sm m-0">{t("analyse.position.why")}</p>}
            </div>
          )}
        </section>
        {site.georeferenced && (
          <div className="karte p-5 flex flex-col gap-5">
            <GelaendeRisiken site={site} rolle="architect" ebene={3} />
          </div>
        )}
        <section aria-labelledby="kanten" className="karte p-5 flex flex-col gap-3">
          <h2 id="kanten" className="eyebrow">{t("analyse.site.edges")}</h2>
          <p className="t-mute text-sm m-0">{t("analyse.site.edgesIntro")}</p>
          <KantenListe
            edges={site.edges}
            rolle="architect"
            pending={classify.isPending}
            highlightedSeq={highlighted}
            onHighlight={onHighlight}
            onChange={(seq, value) => classify.mutate({ seq, kind: (value as EdgeKind | null) ?? null })}
          />
          {classify.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
          {site.main_street_seq === null && <p className="t-warn m-0">{t("analyse.site.noStreet")}</p>}
        </section>
        {next && <p className="t-mute text-sm">{t("analyse.site.next")}</p>}
      </div>
    </div>
  );
}
