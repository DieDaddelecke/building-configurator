/** Büro: Grundstücke mit Prüfbedarf und Detail mit Kantenkorrektur und Bestätigung (Plan 3.3, Rolle architect). */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/client";
import {
  useDeleteOverride,
  useProjectOverrides,
  usePutOverride,
  useRuleKinds,
  useStaffProjectRules,
  type ProjectRulesOut,
  type RuleOut,
  type ZoneRulesOut,
} from "../../api/rules";
import { useConfirmCustomerEdges, useCorrectEdgeArchitect, useReviewQueue, useStaffSite, type EdgeKind, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { ruleValue } from "../../rules/format";
import { RegelFormular } from "../../rules/RegelFormular";
import { RegelnSimulation } from "../../rules/RegelnSimulation";
import { GrundstueckPruefen } from "../../site/GrundstueckPruefen";

export function Fehler({ error }: { error: unknown }) {
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

export function Detail({ site }: { site: SiteOut }) {
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

const OVERRIDE_KINDS = [
  "setback_street",
  "setback_side",
  "setback_rear",
  "max_footprint_ratio",
  "max_area",
  "max_height",
  "roof",
  "facade",
  "unsealed_min",
  "parking",
  "annex",
] as const;

/** Korrektur nur für dieses Projekt (z. B. Regeln eines Lotissement, Plan 3.4); andere Projekte bleiben unberührt.
 *  Felder aus der Beschreibung der Regelarten statt JSON, Fundstelle im règlement des Planstands (AN4, RW15). */
function ProjektKorrektur({ projectId, zone, rules }: { projectId: string; zone: ZoneRulesOut; rules: ProjectRulesOut }) {
  const { t } = useTranslation();
  const put = usePutOverride(projectId);
  const kinds = useRuleKinds();
  const [runde, setRunde] = useState(0);
  const documents = rules.plan ? [{ id: rules.plan.id, title: rules.plan.title }] : [];
  return (
    <details className="karte p-3 text-sm">
      <summary className="cursor-pointer">{t("office.rules.projectOverride", { code: zone.code })}</summary>
      <div className="mt-3">
        {kinds.data ? (
          <RegelFormular
            key={runde}
            kinds={kinds.data}
            zoneCode={zone.code}
            vorlage={{ kind: "max_footprint_ratio", building_kind: "any", status: "effective", params: {} }}
            kindChoices={[...OVERRIDE_KINDS]}
            buildingChoice
            documents={documents}
            pending={put.isPending}
            error={put.error}
            onSubmit={(body) => put.mutate(body, { onSuccess: () => setRunde((n) => n + 1) })}
          />
        ) : (
          <p className="t-mute m-0">{t("loading")}</p>
        )}
      </div>
    </details>
  );
}

export function ProjektRegeln({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const rules = useStaffProjectRules(projectId);
  const overrides = useProjectOverrides(projectId);
  const remove = useDeleteOverride(projectId);
  if (rules.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (rules.isError) return <Fehler error={rules.error} />;
  return (
    <div className="flex flex-col gap-4 max-w-4xl border-t bd pt-8">
      <RegelnSimulation rules={rules.data} zoneExtra={(zone) => <ProjektKorrektur projectId={projectId} zone={zone} rules={rules.data} />} />
      {(overrides.data ?? []).length > 0 && (
        <ul className="m-0 p-0 list-none text-sm" aria-label={t("office.rules.overrides")}>
          {(overrides.data ?? []).map((o) => (
            <li key={o.id} className="flex justify-between gap-3 py-1 border-t bd">
              <span>
                {o.zone_code} · {t(`rules.kind.${o.kind}`)} · {ruleValue({ ...o, reason: null } as unknown as RuleOut, t, i18n.language)}
                {o.source && <> · {t("rules.page", { page: o.source.page })}</>} · {o.note}
              </span>
              <button type="button" className="btn btn-ghost" onClick={() => remove.mutate(o.id)} disabled={remove.isPending}>
                {t("office.rules.removeOverride")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
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
      {site.data && <ProjektRegeln projectId={projectId} />}
    </div>
  );
}
