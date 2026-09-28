/**
 * Regeln und Korrekturen (AN4, docs/PLAN_AN4_KORREKTUR.md 3.2, 3.3, 3.7): die Regeln des Bebauungsplans mit
 * „Korrigieren“ je Zeile, „Regel ergänzen“, Begründung und Fundstelle jeder Korrektur, nicht mehr wirksame Korrekturen
 * und der Vergleich zweier Stände. Korrekturen wirken sofort in Regeln, Baurahmen und Analyse und kosten nichts.
 */

import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { pluOf, supplementsOf, useProjectRegulations } from "../../api/regulations";
import {
  useDeleteOwnOverride,
  useOwnOverrides,
  usePutOwnOverride,
  useRuleKinds,
  type ProjectOverrideOut,
  type ProjectRulesOut,
  type RuleOut,
  type ZoneRulesOut,
} from "../../api/rules";
import { Abdeckung } from "../../rules/Abdeckung";
import { ruleValue } from "../../rules/format";
import { RegelFormular, type Baukoerper, type Dokument, type Vorlage } from "../../rules/RegelFormular";
import { RegelnSimulation } from "../../rules/RegelnSimulation";
import { StaendeVergleich } from "./StaendeVergleich";

/** Dokumente, die als Fundstelle in Frage kommen: PLU und Zusatzdokumente des Projekts, sonst der Planstand der Regeln. */
export function useFundstellen(projectId: string, rules: ProjectRulesOut | undefined): Dokument[] {
  const regulations = useProjectRegulations(projectId);
  const documents: Dokument[] = [];
  const plu = pluOf(regulations.data);
  if (plu) documents.push({ id: plu.document.id, title: plu.document.title, pageCount: plu.document.page_count });
  else if (rules?.plan) documents.push({ id: rules.plan.id, title: rules.plan.title });
  for (const supplement of supplementsOf(regulations.data)) {
    documents.push({ id: supplement.document.id, title: supplement.document.title, pageCount: supplement.document.page_count });
  }
  return documents;
}

interface KorrekturFormularProps {
  projectId: string;
  zoneCode: string;
  rules: ProjectRulesOut | undefined;
  vorlage: Vorlage;
  kindChoices?: string[];
  buildingChoice?: boolean;
  hint?: ReactNode;
  onDone: () => void;
}

/** Regelformular mit den Daten des Projekts: Arten, Fundstellen, Speichern als Korrektur. */
export function KorrekturFormular({ projectId, zoneCode, rules, vorlage, kindChoices, buildingChoice, hint, onDone }: KorrekturFormularProps) {
  const { t } = useTranslation();
  const kinds = useRuleKinds();
  const documents = useFundstellen(projectId, rules);
  const put = usePutOwnOverride(projectId);
  if (kinds.isPending) return <p className="t-mute m-0">{t("loading")}</p>;
  if (!kinds.data) return <p className="t-alert m-0">{t("error.generic")}</p>;
  return (
    <RegelFormular
      kinds={kinds.data}
      zoneCode={zoneCode}
      vorlage={vorlage}
      kindChoices={kindChoices}
      buildingChoice={buildingChoice}
      documents={documents}
      pending={put.isPending}
      error={put.error}
      hint={hint}
      onSubmit={(body) => put.mutate(body, { onSuccess: onDone })}
      onCancel={onDone}
    />
  );
}

type Bearbeitung =
  | { zone: string; mode: "rule"; rule: RuleOut; override?: ProjectOverrideOut }
  | { zone: string; mode: "add" };

const FORM_KINDS = [
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

function vorlageAusRegel(rule: RuleOut, override: ProjectOverrideOut | undefined): Vorlage {
  if (override) {
    return {
      kind: override.kind,
      building_kind: override.building_kind as Baukoerper,
      status: override.status === "text_only" ? "effective" : override.status,
      params: override.params,
      source:
        override.source?.document_id != null
          ? { document_id: override.source.document_id, page: override.source.page, quote: override.source.quote }
          : null,
      note: override.note ?? "",
    };
  }
  // Fundstelle der Auswertung als Vorschlag: Sonst verlöre der unveränderte Teil der Regel seine Herkunft (7.1 Nr. 9)
  return {
    kind: rule.kind,
    building_kind: rule.building_kind as Baukoerper,
    status: rule.status === "not_regulated" ? "not_regulated" : "effective",
    params: rule.params,
    source: rule.page != null && rule.source_document_id ? { document_id: rule.source_document_id, page: rule.page, quote: rule.quote } : null,
  };
}

/** Nachsuche (PLAN_G2_VOLLSTAENDIGKEIT 3.8): geprüfte Stellen bzw. Seite des Hinweises. */
function Nachsuche({ rule }: { rule: RuleOut }) {
  const { t } = useTranslation();
  if (!rule.search_note) return null;
  const text =
    rule.reason === "not_expressible"
      ? t("rules.coverage.hintPage", { page: rule.search_note })
      : t("rules.coverage.searched", { note: rule.search_note });
  return <span className="block text-xs t-mute">{text}</span>;
}

function Begruendung({ override }: { override: ProjectOverrideOut }) {
  const { t } = useTranslation();
  return (
    <span className="block text-xs t-mute">
      {t("analyse.corrections.reason", { note: override.note ?? "" })}
      {override.source && !override.source.attached && <span className="t-warn"> · {t("analyse.corrections.detached")}</span>}
    </span>
  );
}

export function RegelnKorrekturen({ projectId, rules }: { projectId: string; rules: ProjectRulesOut }) {
  const { t, i18n } = useTranslation();
  const overrides = useOwnOverrides(projectId);
  const remove = useDeleteOwnOverride(projectId);
  const [edit, setEdit] = useState<Bearbeitung | null>(null);
  const list = overrides.data ?? [];
  const find = (zone: ZoneRulesOut, rule: RuleOut) =>
    rule.origin === "project"
      ? list.find((o) => o.active && o.zone_code === zone.code && o.kind === rule.kind && o.building_kind === rule.building_kind)
      : undefined;
  const inactive = list.filter((o) => !o.active);
  const zuruecknehmen = (override: ProjectOverrideOut) => {
    if (window.confirm(t("analyse.corrections.removeConfirm"))) remove.mutate(override.id);
  };

  const formular = (zone: ZoneRulesOut) => {
    if (edit?.zone !== zone.code) return null;
    if (edit.mode === "add") {
      const present = new Set(zone.rules.filter((r) => r.building_kind === "main" || r.building_kind === "any").map((r) => r.kind));
      const choices = FORM_KINDS.filter((k) => !present.has(k));
      const [first] = choices;
      if (!first) return null;
      return (
        <KorrekturFormular
          key="add"
          projectId={projectId}
          zoneCode={zone.code}
          rules={rules}
          vorlage={{ kind: first, building_kind: "any", status: "effective", params: {} }}
          kindChoices={choices}
          buildingChoice
          onDone={() => setEdit(null)}
        />
      );
    }
    return (
      <KorrekturFormular
        key={`${edit.rule.kind}-${edit.rule.building_kind}`}
        projectId={projectId}
        zoneCode={zone.code}
        rules={rules}
        vorlage={vorlageAusRegel(edit.rule, edit.override)}
        onDone={() => setEdit(null)}
      />
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <RegelnSimulation
        rules={rules}
        rolle="architect"
        intro={<p className="text-sm t-mute m-0">{t("analyse.corrections.intro")}</p>}
        ruleAction={(zone, rule) => {
          const override = find(zone, rule);
          return (
            <span className="inline-flex gap-2">
              <button type="button" className="link text-sm" onClick={() => setEdit({ zone: zone.code, mode: "rule", rule, override })}>
                {t(override ? "analyse.corrections.change" : "analyse.corrections.correct")}
              </button>
              {override && (
                <button type="button" className="link text-sm" onClick={() => zuruecknehmen(override)} disabled={remove.isPending}>
                  {t("analyse.corrections.remove")}
                </button>
              )}
              {!override && rule.reason === "not_found_after_search" && (
                <button
                  type="button"
                  className="link text-sm"
                  onClick={() => setEdit({ zone: zone.code, mode: "rule", rule: { ...rule, status: "not_regulated" } })}
                >
                  {t("analyse.corrections.confirmNotRegulated")}
                </button>
              )}
            </span>
          );
        }}
        ruleDetail={(zone, rule) => {
          const override = find(zone, rule);
          return override ? <Begruendung override={override} /> : <Nachsuche rule={rule} />;
        }}
        zoneExtra={(zone) => (
          <>
            <Abdeckung version={zone.version} documentUrl={rules.plan?.regulation_url} />
            {formular(zone)}
            {edit === null && (
              <div>
                <button type="button" className="btn btn-ghost" onClick={() => setEdit({ zone: zone.code, mode: "add" })}>
                  {t("analyse.corrections.add")}
                </button>
              </div>
            )}
          </>
        )}
      />
      {remove.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {inactive.length > 0 && (
        <section aria-labelledby="korrekturen-inaktiv" className="flex flex-col gap-2 text-sm">
          <h3 id="korrekturen-inaktiv" className="m-0 text-base font-medium t-ink">
            {t("analyse.corrections.inactive")}
          </h3>
          <p className="t-mute m-0">{t("analyse.corrections.inactiveIntro")}</p>
          <ul className="m-0 p-0 list-none">
            {inactive.map((o) => (
              <li key={o.id} className="flex flex-wrap justify-between gap-3 py-1 border-t bd">
                <span>
                  {t("rules.zone", { code: o.zone_code })} · {t(`rules.kind.${o.kind}`)} ·{" "}
                  {ruleValue({ ...o, reason: null } as unknown as RuleOut, t, i18n.language)} · <span className="t-mute">{o.note}</span>
                </span>
                <button type="button" className="link" onClick={() => zuruecknehmen(o)} disabled={remove.isPending}>
                  {t("analyse.corrections.remove")}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <StaendeVergleich projectId={projectId} />
    </div>
  );
}
