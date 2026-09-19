/** Öffentliche Seite des Bebaubarkeitschecks, Teil G1: Parzelle wählen und Grundstück prüfen (Plan 3.3). */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { CONFIGURATOR_FLAG } from "../../api/configuration";
import { ENVELOPE_FLAG, useEnvelope } from "../../api/envelope";
import { INQUIRY_FLAG } from "../../api/inquiry";
import { RULES_FLAG, useProjectRules } from "../../api/rules";
import { useSession } from "../../api/session";
import { SITE_FLAG, useCorrectEdgeCustomer, useEnsureProject, useFlags, useSite, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { Nordpfeil, strich } from "../../components/plan/Masskette";
import { PlanSvg, ringPath, type LocalPoint } from "../../components/plan/PlanSvg";
import { centerOf, formatNumber, siteBounds } from "../../site/geo";
import { Baurahmen } from "../../envelope/Baurahmen";
import { AnfrageFormular } from "../../inquiry/AnfrageFormular";
import { DatenschutzAktionen } from "../../inquiry/DatenschutzAktionen";
import { FreiesZeichnen } from "../../site/FreiesZeichnen";
import { GrundstueckPruefen, useNotices } from "../../site/GrundstueckPruefen";
import { RegelnSimulation } from "../../rules/RegelnSimulation";
import { ParzellenWahl } from "../../site/ParzellenWahl";

function Pruefen({ site, onChangeParcels, rulesBelow }: { site: SiteOut; onChangeParcels: () => void; rulesBelow: boolean }) {
  const { t } = useTranslation();
  const correct = useCorrectEdgeCustomer(site);
  return (
    <GrundstueckPruefen
      site={site}
      rolle="customer"
      pending={correct.isPending}
      error={correct.error}
      onEdgeChange={(seq, value) => correct.mutate({ seq, kind: value as "street" | "neighbour" | null })}
      actions={
        <div className="flex flex-col gap-3 border-t bd pt-4">
          <p className="text-sm t-ink bg-tint px-4 py-3 m-0">{t(rulesBelow ? "site.nextBelow" : "site.next")}</p>
          <button type="button" className="btn btn-ghost self-start" onClick={onChangeParcels}>
            {t("site.changeParcels")}
          </button>
        </div>
      }
    />
  );
}

/** Ergebnis von Weg E (Plan 3.3): kein Kataster, keine Kanten, kein Baurahmen – G2 und G3 werden für ein
 * frei gezeichnetes Grundstück nicht aufgerufen (D13). Deutlich einfacher als `GrundstueckPruefen`. */
function ManuelleZeichnungAnsicht({ site, onRedraw }: { site: SiteOut; onRedraw: () => void }) {
  const { t, i18n } = useTranslation();
  const notices = useNotices(site.notices);
  const bounds = siteBounds(site);
  const outline = (site.outline_local[0] ?? []) as unknown as LocalPoint[];
  const published = notices.data?.find((n) => n.key === "notice.manual_sketch");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
      <div className="lg:col-span-7 flex flex-col gap-3">
        <PlanSvg bounds={bounds} label={t("site.manual.preview")}>
          <path d={ringPath(outline)} style={{ ...strich("var(--accent)", 0.15), fill: "var(--sheet)", fillOpacity: 0.85 }} />
          <g transform={`translate(${bounds.maxE + 3} ${-bounds.maxN + 1})`}>
            <Nordpfeil x={0} y={0} />
          </g>
        </PlanSvg>
      </div>
      <div className="lg:col-span-5 flex flex-col gap-6">
        <dl className="m-0">
          <div className="flex justify-between gap-4 py-2 border-t bd">
            <dt className="t-mute">{t("site.manual.address.label")}</dt>
            <dd className="m-0 t-ink text-right">{site.address_label}</dd>
          </div>
          <div className="flex justify-between gap-4 py-2 border-t bd">
            <dt className="t-mute">{t("site.manual.areaLabel")}</dt>
            <dd className="m-0 t-ink text-right">{`${formatNumber(site.area_m2, i18n.language, 0)} m²`}</dd>
          </div>
        </dl>
        <p className="bg-tint t-ink px-4 py-3 text-sm m-0" lang={published?.locale}>
          {published ? published.body : t("site.notices.manual_sketch")}
        </p>
        <button type="button" className="btn btn-ghost self-start" onClick={onRedraw}>
          {t("site.manual.redraw")}
        </button>
      </div>
    </div>
  );
}

/** Regeln mit Zitaten: als Herleitung eingeklappt, sobald der Baurahmen dieselben Werte schon zeigt. */
function RegelnBereich({
  projectId,
  revision,
  collapsed,
}: {
  projectId: string;
  revision: number;
  collapsed: boolean;
}) {
  const { t } = useTranslation();
  const rules = useProjectRules(projectId, true);
  if (rules.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (rules.isError) return <p className="t-alert" role="alert">{t("error.generic")}</p>;
  const inhalt = <RegelnSimulation key={revision} rules={rules.data} />;
  if (!collapsed) return inhalt;
  return (
    <details className="flex flex-col gap-4">
      <summary className="cursor-pointer eyebrow t-accent">{t("envelope.rulesDetails")}</summary>
      <div className="pt-6">{inhalt}</div>
    </details>
  );
}

function BaurahmenBereich({ projectId, revision }: { projectId: string; revision: number }) {
  const { t } = useTranslation();
  const envelope = useEnvelope(projectId, true);
  if (envelope.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (envelope.isError) return <p className="t-alert" role="alert">{t("error.generic")}</p>;
  return (
    <section aria-labelledby="baurahmen" className="flex flex-col gap-5">
      <h2 id="baurahmen" className="eyebrow m-0">{t("envelope.title")}</h2>
      <Baurahmen key={revision} envelope={envelope.data} projectId={projectId} />
    </section>
  );
}

/** Einstieg in den Konfigurator (H2): Typ wählen und auf dem Grundstück platzieren. */
function KonfiguratorLink() {
  const { t } = useTranslation();
  return (
    <div className="border-t bd pt-8 max-w-xl flex flex-col gap-3">
      <p className="text-sm t-mute m-0">{t("configurator.openHint")}</p>
      <Link className="btn btn-primary self-start" to="/konfigurator">
        {t("configurator.open")}
      </Link>
    </div>
  );
}

function focusOf(site: SiteOut | null | undefined) {
  const position = site ? centerOf(site.outline_geojson) : null;
  return position ? { lon: position[0], lat: position[1], key: `site-${site?.revision}` } : null;
}

export function GrundstueckSeite() {
  const { t } = useTranslation();
  const session = useSession();
  const flags = useFlags();
  const ensure = useEnsureProject();
  const projectId = session.data?.project_id ?? ensure.data ?? null;
  const site = useSite(projectId);
  const [editing, setEditing] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const enabled = Boolean(flags.data?.[SITE_FLAG]);
  const rulesEnabled = Boolean(flags.data?.[RULES_FLAG]);
  const envelopeEnabled = Boolean(flags.data?.[ENVELOPE_FLAG]);
  const inquiryEnabled = Boolean(flags.data?.[INQUIRY_FLAG]);
  const configuratorEnabled = Boolean(flags.data?.[CONFIGURATOR_FLAG]);

  let inhalt;
  // Ein eben angelegtes Projekt hat noch kein Grundstück: kein Ladezustand, sonst verliert die
  // Parzellenwahl ihre Eingaben beim ersten Klick
  const siteLoading = Boolean(projectId) && site.isPending && !ensure.isSuccess;
  if (flags.isPending || session.isPending || siteLoading) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (flags.isError || session.isError || site.isError) {
    inhalt = <p className="t-alert" role="alert">{t("error.generic")}</p>;
  } else if (!enabled) {
    inhalt = (
      <Kopf eyebrow={t("site.disabled.eyebrow")} titel={t("site.disabled.title")}>
        <p>{t("site.disabled.text")}</p>
        <Link className="link" to="/">
          {t("error.home")}
        </Link>
      </Kopf>
    );
  } else if (site.data && site.data.origin === "manual_sketch" && !editing) {
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("site.review.eyebrow")} titel={t("site.manual.review.title")}>
          <p>{t("site.manual.review.intro")}</p>
        </Kopf>
        <ManuelleZeichnungAnsicht
          site={site.data}
          onRedraw={() => {
            setEditing(true);
            setManualMode(true);
          }}
        />
        {configuratorEnabled && <KonfiguratorLink />}
        {inquiryEnabled && (
          <div className="border-t bd pt-8 max-w-xl">
            <AnfrageFormular projectId={site.data.project_id} />
          </div>
        )}
        <div className="border-t bd pt-8 max-w-xl">
          <DatenschutzAktionen projectId={site.data.project_id} />
        </div>
      </div>
    );
  } else if (site.data && !editing) {
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("site.review.eyebrow")} titel={t("site.review.title")}>
          <p>{t("site.review.intro")}</p>
        </Kopf>
        <Pruefen site={site.data} onChangeParcels={() => setEditing(true)} rulesBelow={rulesEnabled} />
        {envelopeEnabled && (
          <div className="border-t bd pt-8">
            <BaurahmenBereich projectId={site.data.project_id} revision={site.data.revision} />
          </div>
        )}
        {rulesEnabled && (
          <div className="border-t bd pt-8 max-w-4xl">
            <RegelnBereich
              projectId={site.data.project_id}
              revision={site.data.revision}
              collapsed={envelopeEnabled}
            />
          </div>
        )}
        {configuratorEnabled && <KonfiguratorLink />}
        {inquiryEnabled && (
          <div className="border-t bd pt-8 max-w-xl">
            <AnfrageFormular projectId={site.data.project_id} />
          </div>
        )}
        <div className="border-t bd pt-8 max-w-xl">
          <DatenschutzAktionen projectId={site.data.project_id} />
        </div>
      </div>
    );
  } else if (manualMode) {
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("site.manual.select.eyebrow")} titel={t("site.manual.select.title")}>
          <p>{t("site.manual.select.intro")}</p>
        </Kopf>
        <FreiesZeichnen
          ensureProject={() => ensure.mutateAsync(projectId)}
          onFormed={() => {
            setEditing(false);
            setManualMode(false);
          }}
          onCancel={() => setManualMode(false)}
        />
      </div>
    );
  } else {
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("site.select.eyebrow")} titel={t("site.select.title")}>
          <p>{t("site.select.intro")}</p>
        </Kopf>
        <ParzellenWahl
          ensureProject={() => ensure.mutateAsync(projectId)}
          initial={site.data?.parcels.map((p) => p.idu) ?? []}
          initialFocus={focusOf(site.data)}
          onFormed={() => setEditing(false)}
          onCancel={site.data ? () => setEditing(false) : undefined}
        />
        <button type="button" className="link self-start" onClick={() => setManualMode(true)}>
          {t("site.manual.switch")}
        </button>
      </div>
    );
  }

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-7xl mx-auto px-6 lg:px-10 py-10 anim-seite">{inhalt}</main>
    </div>
  );
}
