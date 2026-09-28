/**
 * Regeln des Bebauungsplans für das Grundstück als unverbindliche Simulation (Plan 3.4, Entscheidung D11).
 * Jeder Wert mit Herkunft: Zitat und Seite im règlement écrit; unsichere Werte erscheinen als „nicht ermittelt“
 * mit Grund, nie geschätzt. Kunde und Büro nutzen dieselbe Ansicht.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ProjectRulesOut, RuleOut, ZoneRulesOut } from "../api/rules";
import { useNotices } from "../site/GrundstueckPruefen";
import { ruleValue } from "./format";

const KIND_ORDER = [
  "setback_street",
  "setback_side",
  "setback_rear",
  "max_footprint_ratio",
  "max_area",
  "max_height",
  "roof",
  "facade",
  "unsealed_min",
  "setback_between_buildings",
  "parking",
  "annex",
  "planting",
  "fence",
];

/** Fachliche Reihenfolge: Hauptgebäude zuerst, dann Pflichtarten wie in Spez. 5.2.4. */
export function sortRules<T extends Pick<RuleOut, "kind" | "building_kind">>(rules: T[]): T[] {
  const building = ["main", "any", "annex", "pool"];
  return [...rules].sort(
    (a, b) =>
      building.indexOf(a.building_kind) - building.indexOf(b.building_kind) ||
      KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind),
  );
}

/** Seite als Verweis; eine Projektkorrektur (AN4) mit Fundstelle zeigt die Seite und „Korrektur“, ohne Fundstelle die
 *  Herkunft allein. Ein unbestätigtes Zitat einer Korrektur trägt ein Sternchen wie im Baurahmen. */
function Quelle({ rule }: { rule: RuleOut }) {
  const { t } = useTranslation();
  const korrektur = rule.origin === "project";
  if (!rule.source_url || rule.page == null) {
    if (korrektur) return <span className="t-mute">{t("rules.origin.project")}</span>;
    return <span className="t-mute">{rule.origin === "office" ? t("rules.origin.office") : "–"}</span>;
  }
  return (
    <>
      <a className="link" href={rule.source_url} target="_blank" rel="noreferrer" title={rule.quote ?? undefined}>
        {t("rules.page", { page: rule.page })}
        {korrektur && !rule.quote_verified && <span className="t-warn"> *</span>}
      </a>
      {korrektur && <span className="t-mute"> · {t("rules.origin.correction")}</span>}
    </>
  );
}

interface ZoneExtras {
  extra?: (zone: ZoneRulesOut) => ReactNode;
  ruleAction?: (zone: ZoneRulesOut, rule: RuleOut) => ReactNode;
  ruleDetail?: (zone: ZoneRulesOut, rule: RuleOut) => ReactNode;
}

function Zone({ zone, extra, ruleAction, ruleDetail }: { zone: ZoneRulesOut } & ZoneExtras) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const rules = sortRules(zone.rules);
  return (
    <section aria-labelledby={`zone-${zone.code}`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`zone-${zone.code}`} className="m-0 text-base font-medium t-ink">
          {t("rules.zone", { code: zone.code })}
          {zone.label ? <span className="t-mute font-normal"> · {zone.label.replace(`${zone.code} : `, "")}</span> : null}
        </h3>
        <span className="text-xs t-mute">
          {t("rules.share", { share: Math.round(zone.share * 100) })} ·{" "}
          <span className={zone.status === "outdated" ? "t-warn" : undefined}>{t(`rules.zoneStatus.${zone.status}`)}</span>
        </span>
      </div>
      {zone.status === "in_progress" && <p className="t-mute text-sm m-0">{t("rules.inProgress")}</p>}
      {zone.status === "unavailable" && (
        <p className="t-warn text-sm m-0">{t(`rules.unavailable.${zone.reason ?? "failed"}`, { defaultValue: t("rules.unavailable.failed") })}</p>
      )}
      {rules.length > 0 && (
        <div className="overflow-x-auto relative">
          <table className="w-full text-sm border-collapse">
            <caption className="sr-only">{t("rules.caption", { code: zone.code })}</caption>
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.value")}</th>
                <th scope="col" className="py-2 font-medium">{t("rules.column.source")}</th>
                {ruleAction && (
                  <th scope="col" className="py-2 pl-3 font-medium">
                    <span className="sr-only">{t("rules.column.action")}</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={`${rule.kind}-${rule.building_kind}`} className="border-b bd align-top">
                  <th scope="row" className="py-2 pr-3 font-normal text-left">
                    {t(`rules.kind.${rule.kind}`)}
                    {rule.building_kind !== "main" && rule.building_kind !== "any" && (
                      <span className="t-mute"> · {t(`rules.building.${rule.building_kind}`)}</span>
                    )}
                  </th>
                  <td className={`py-2 pr-3 ${rule.status === "effective" ? "t-ink" : "t-mute"}`}>
                    {ruleValue(rule, t, lng)}
                    {ruleDetail?.(zone, rule)}
                  </td>
                  <td className="py-2 whitespace-nowrap">
                    <Quelle rule={rule} />
                  </td>
                  {ruleAction && <td className="py-2 pl-3 text-right whitespace-nowrap">{ruleAction(zone, rule)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {zone.hints.length > 0 && (
        <ul className="m-0 pl-5 flex flex-col gap-1 text-sm">
          {zone.hints.map((hint, index) => (
            <li key={index}>
              <span lang={hint.origin === "extraction" ? "fr" : undefined}>{String(hint.params.summary ?? hint.notes ?? "")}</span>{" "}
              <Quelle rule={hint} />
            </li>
          ))}
        </ul>
      )}
      {extra?.(zone)}
    </section>
  );
}

interface RegelnSimulationProps {
  rules: ProjectRulesOut;
  /** Zusätzliche Bedienelemente je Zone (Büro: Korrektur). */
  zoneExtra?: (zone: ZoneRulesOut) => ReactNode;
  /** Bedienelement je Regel in einer eigenen Spalte (Analyse-Produkt: korrigieren, AN4). */
  ruleAction?: (zone: ZoneRulesOut, rule: RuleOut) => ReactNode;
  /** Zusatz unter dem Wert (Analyse-Produkt: Begründung einer Korrektur). */
  ruleDetail?: (zone: ZoneRulesOut, rule: RuleOut) => ReactNode;
  /** Einleitung unter der Überschrift. */
  intro?: ReactNode;
  /** `architect`: Hinweis ohne den Verweis auf die Anfrage (Emprise Analyse, AN2). */
  rolle?: "customer" | "architect";
}

export function RegelnSimulation({ rules, zoneExtra, ruleAction, ruleDetail, intro, rolle = "customer" }: RegelnSimulationProps) {
  const { t } = useTranslation();
  const notices = useNotices(rules.notices);
  return (
    <section aria-labelledby="regeln" className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 id="regeln" className="eyebrow m-0">
          {t("rules.title")}
        </h2>
        <p className="bg-warn t-warn px-4 py-3 text-sm m-0" role="note">
          <strong>{t("rules.simulation.label")}</strong>{" "}
          {t(rolle === "architect" ? "rules.simulation.textOffice" : "rules.simulation.text")}
        </p>
        {intro}
        {rules.plan && (
          <p className="text-sm t-mute m-0">
            {rules.plan.origin === "upload"
              ? t("rules.uploaded", { title: rules.plan.title })
              : t("rules.plan", { title: rules.plan.title, date: rules.plan.gpu_update_date?.slice(0, 10) ?? "–" })}
            {rules.plan.regulation_url && (
              <>
                {" · "}
                <a className="link" href={rules.plan.regulation_url} target="_blank" rel="noreferrer">
                  {t("rules.document")}
                </a>
              </>
            )}
          </p>
        )}
      </div>

      {rules.status === "unavailable" && (
        <p className="t-warn text-sm m-0">
          {t(`rules.unavailable.${rules.reason ?? "failed"}`, { defaultValue: t("rules.unavailable.failed") })}
        </p>
      )}
      {rules.warnings.length > 0 && (
        <ul className="m-0 pl-5 flex flex-col gap-1 text-sm">
          {rules.warnings.map((w) => (
            <li key={w} className={w === "rules_outdated" || w === "plan_update_failed" || w === "zone_coverage_incomplete" ? "t-warn" : undefined}>
              {t(`rules.warning.${w}`, { defaultValue: w, share: Math.round((rules.uncovered_share ?? 0) * 100) })}
            </li>
          ))}
        </ul>
      )}

      {rules.zones.map((zone) => (
        <Zone key={zone.code} zone={zone} extra={zoneExtra} ruleAction={ruleAction} ruleDetail={ruleDetail} />
      ))}

      {rules.overlays.length > 0 && (
        <section aria-labelledby="vorgaben" className="flex flex-col gap-2">
          <h3 id="vorgaben" className="m-0 text-base font-medium t-ink">
            {t("rules.overlays.title")}
          </h3>
          <ul className="m-0 p-0 list-none text-sm">
            {rules.overlays.map((overlay, index) => (
              <li key={index} className="flex justify-between gap-4 py-1 border-t bd">
                <span lang="fr">{overlay.label}</span>
                <span className="t-mute whitespace-nowrap">{t(`rules.overlays.${overlay.category}`)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="regeln-hinweise" className="flex flex-col gap-2 text-sm">
        <h3 id="regeln-hinweise" className="eyebrow m-0">
          {t("site.notices.title")}
        </h3>
        {rules.notices.map((key) => {
          const published = notices.data?.find((n) => n.key === key);
          return (
            <p key={key} className="m-0 t-mute" lang={published?.locale}>
              {published ? published.body : t(`rules.notices.${key.replace("notice.rules_", "")}`)}
            </p>
          );
        })}
      </section>
    </section>
  );
}
