import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { useStaffEnvelope } from "../../api/envelope";
import { pluOf, useProjectRegulations } from "../../api/regulations";
import { useStaffProjectRules } from "../../api/rules";
import { useClassifyEdge, useDeleteProject, useSite, type EdgeKind, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { Baurahmen } from "../../envelope/Baurahmen";
import { FreiesZeichnen } from "../../site/FreiesZeichnen";
import { formatNumber } from "../../site/geo";
import { KantenListe } from "../../site/KantenListe";
import { SiteLageplan } from "../../site/SiteLageplan";
import { Analyse } from "./Analyse";
import { Bebauungsplan } from "./Bebauungsplan";
import { GabaritSchnitt } from "./GabaritSchnitt";
import { ParzelleHochladen } from "./ParzelleHochladen";
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
  };
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm m-0">
      <dt className="t-mute">{t("analyse.site.area")}</dt>
      <dd className="f-mono num m-0">{formatNumber(site.area_m2, i18n.language)} m²</dd>
      <dt className="t-mute">{t("analyse.site.origin")}</dt>
      <dd className="m-0">{t(`analyse.origin.${site.origin}`)}</dd>
      <dt className="t-mute">{t("analyse.site.position")}</dt>
      <dd className="m-0">
        {site.georeferenced ? t("analyse.site.georeferenced") : t("analyse.site.local")}
      </dd>
      {quelle.file_name && (
        <>
          <dt className="t-mute">{t("analyse.site.file")}</dt>
          <dd className="m-0 break-all">
            {quelle.file_name}
            {quelle.layer && <span className="t-mute"> · {quelle.layer}</span>}
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

/** Regeln mit Korrekturen (AN4), dann Analyse, Gabarit und Schnitt (AN3) und Baurahmen aus dem hochgeladenen
 *  Bebauungsplan (AN2), über die Büro-Endpunkte (E-AN2-7). Die Regeln stehen vor den Ergebnissen, weil alles darunter
 *  aus ihnen folgt (E-AN4-6). */
function Ergebnis({ projectId, revision }: { projectId: string; revision: number }) {
  const { t } = useTranslation();
  const envelope = useStaffEnvelope(projectId);
  const rules = useStaffProjectRules(projectId);
  if (envelope.isPending || rules.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (envelope.isError || rules.isError) return <p className="t-alert" role="alert">{t("error.generic")}</p>;
  return (
    <>
      <RegelnKorrekturen key={revision} projectId={projectId} rules={rules.data} />
      <Analyse projectId={projectId} envelope={envelope.data} />
      <GabaritSchnitt projectId={projectId} envelope={envelope.data} />
      <section aria-labelledby="baurahmen" className="flex flex-col gap-5">
        <h2 id="baurahmen" className="eyebrow m-0">{t("analyse.envelope")}</h2>
        <Baurahmen key={revision} envelope={envelope.data} projectId={projectId} rolle="architect" />
      </section>
    </>
  );
}

/** Ein Projekt: Parzelle einbringen, Kanten einordnen (AN1), Bebauungsplan hochladen und Zone wählen; daraus
 *  Regeln und Baurahmen (AN2). Zusatzdokumente und die Analyse für den Entwurf (AN3). Regeln korrigieren, ergänzen,
 *  aus Zusatzdokumenten übernehmen und Stände vergleichen (AN4). */
export function ProjektSeite() {
  const { t } = useTranslation();
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const site = useSite(projectId);
  const regulations = useProjectRegulations(projectId);
  const entfernen = useDeleteProject();
  const [weg, setWeg] = useState<Weg>("wahl");
  const [hervorgehoben, setHervorgehoben] = useState<number | null>(null);
  const zoneGewaehlt = Boolean(pluOf(regulations.data)?.zone_code);

  const loeschen = () => {
    if (!window.confirm(t("analyse.site.deleteConfirm"))) return;
    entfernen.mutate(projectId, { onSuccess: () => void navigate("/") });
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Kopf
          eyebrow={t("analyse.eyebrow")}
          titel={site.data?.address_label ?? t("analyse.projects.untitled")}
        >
          <p>{t("analyse.site.intro")}</p>
        </Kopf>
        <div className="flex gap-3">
          <Link className="btn btn-ghost" to="/">
            {t("analyse.site.back")}
          </Link>
          <button type="button" className="btn btn-ghost" onClick={loeschen} disabled={entfernen.isPending}>
            {t("analyse.site.delete")}
          </button>
        </div>
      </div>

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
          <Grundstueck
            site={site.data}
            highlighted={hervorgehoben}
            onHighlight={setHervorgehoben}
            next={!regulations.data?.length}
          />
          <Bebauungsplan projectId={projectId} />
          <Zusatzdokumente projectId={projectId} />
          {zoneGewaehlt && <Ergebnis projectId={projectId} revision={site.data.revision} />}
        </>
      )}
    </div>
  );
}

function Grundstueck({
  site,
  highlighted,
  onHighlight,
  next,
}: {
  site: SiteOut;
  highlighted: number | null;
  onHighlight: (seq: number | null) => void;
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
        </section>
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
