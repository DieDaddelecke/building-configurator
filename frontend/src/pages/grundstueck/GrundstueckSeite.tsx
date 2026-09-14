/** Öffentliche Seite des Bebaubarkeitschecks, Teil G1: Parzelle wählen und Grundstück prüfen (Plan 3.3). */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useSession } from "../../api/session";
import { SITE_FLAG, useCorrectEdgeCustomer, useEnsureProject, useFlags, useSite, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { centerOf } from "../../site/geo";
import { GrundstueckPruefen } from "../../site/GrundstueckPruefen";
import { ParzellenWahl } from "../../site/ParzellenWahl";

function Pruefen({ site, onChangeParcels }: { site: SiteOut; onChangeParcels: () => void }) {
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
          <p className="text-sm t-ink bg-tint px-4 py-3 m-0">{t("site.next")}</p>
          <button type="button" className="btn btn-ghost self-start" onClick={onChangeParcels}>
            {t("site.changeParcels")}
          </button>
        </div>
      }
    />
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
  const enabled = Boolean(flags.data?.[SITE_FLAG]);

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
  } else if (site.data && !editing) {
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("site.review.eyebrow")} titel={t("site.review.title")}>
          <p>{t("site.review.intro")}</p>
        </Kopf>
        <Pruefen site={site.data} onChangeParcels={() => setEditing(true)} />
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
