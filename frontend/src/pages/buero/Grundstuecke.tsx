/** Büro: Grundstücke mit Prüfbedarf und Detail mit Kantenkorrektur und Bestätigung (Plan 3.3, Rolle architect). */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/client";
import { useConfirmCustomerEdges, useCorrectEdgeArchitect, useReviewQueue, useStaffSite, type EdgeKind, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { GrundstueckPruefen } from "../../site/GrundstueckPruefen";

function Fehler({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const forbidden = error instanceof ApiError && error.problem.status === 403;
  return (
    <p role="alert" className="t-alert">
      {forbidden ? t("office.sites.forbidden") : t("error.generic")}
    </p>
  );
}

export function Grundstuecke() {
  const { t, i18n } = useTranslation();
  const [scope, setScope] = useState<"corrections" | "all">("corrections");
  const queue = useReviewQueue(scope);
  return (
    <div className="flex flex-col gap-6">
      <Kopf titel={t("office.sites.title")}>
        <p>{t("office.sites.intro")}</p>
      </Kopf>
      <div role="group" aria-label={t("office.sites.scope")} className="flex gap-1">
        {(["corrections", "all"] as const).map((value) => (
          <button key={value} type="button" className="chip" aria-pressed={scope === value} onClick={() => setScope(value)}>
            {t(`office.sites.scopes.${value}`)}
          </button>
        ))}
      </div>
      {queue.isPending && <p className="t-mute">{t("loading")}</p>}
      {queue.isError && <Fehler error={queue.error} />}
      {queue.data && queue.data.length === 0 && <p className="t-mute">{t("office.sites.empty")}</p>}
      {queue.data && queue.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("site.facts.parcels")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("office.sites.corrections")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("site.warnings.title")}</th>
                <th scope="col" className="py-2 font-medium">{t("office.sites.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {queue.data.map((item) => (
                <tr key={item.project_id} className="border-b bd">
                  <td className="py-2 pr-3">
                    <Link className="link f-mono" to={`/buero/grundstuecke/${item.project_id}`}>
                      {item.parcel_idus.join(", ")}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 f-mono num">{item.customer_corrections}</td>
                  <td className="py-2 pr-3">{item.warnings.map((w) => t(`site.warnings.${w}`)).join(" · ")}</td>
                  <td className="py-2 t-mute">{new Date(item.updated_at).toLocaleString(i18n.language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Detail({ site }: { site: SiteOut }) {
  const { t } = useTranslation();
  const correct = useCorrectEdgeArchitect(site);
  const confirm = useConfirmCustomerEdges(site);
  return (
    <GrundstueckPruefen
      site={site}
      rolle="architect"
      pending={correct.isPending || confirm.isPending}
      error={correct.error ?? confirm.error}
      onEdgeChange={(seq, value) => correct.mutate({ seq, kind: value as EdgeKind | null })}
      actions={
        !site.binding && (
          <button type="button" className="btn btn-primary self-start" onClick={() => confirm.mutate()} disabled={confirm.isPending}>
            {t("office.sites.confirm")}
          </button>
        )
      }
    />
  );
}

export function GrundstueckBuero() {
  const { t } = useTranslation();
  const { projectId = "" } = useParams();
  const site = useStaffSite(projectId);
  return (
    <div className="flex flex-col gap-6">
      <Link className="link text-sm" to="/buero/grundstuecke">
        {t("office.sites.back")}
      </Link>
      <Kopf titel={t("office.sites.detailTitle")}>
        <p className="f-mono text-sm">{projectId}</p>
      </Kopf>
      {site.isPending && <p className="t-mute">{t("loading")}</p>}
      {site.isError && <Fehler error={site.error} />}
      {site.data && <Detail site={site.data} />}
    </div>
  );
}
