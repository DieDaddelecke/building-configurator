/**
 * Büro: Abdeckung der Regelwerke je Gemeinde und Kapitel, Regelwerk mit Zitaten und Korrektur für die Zone
 * (Plan 3.4). Nichts davon ist Voraussetzung für die Simulation beim Kunden (D11); Korrekturen verbessern
 * spätere Simulationen. Parameter über Felder aus der Beschreibung der Regelarten statt JSON (AN4, RW15).
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useOutletContext, useParams } from "react-router";

import { ApiError } from "../../api/client";
import {
  useCreateRuleSetVersion,
  useRuleKinds,
  useRuleSet,
  useRulesCoverage,
  useStartExtraction,
  useStartRulesImport,
  type RuleDetailOut,
  type RuleIn,
  type RuleKindFormOut,
} from "../../api/rules";
import type { components } from "../../api/schema";
import { Kopf } from "../../components/Kopf";
import { Abdeckung } from "../../rules/Abdeckung";
import { entwurfAus, parameterAus, type Entwurf, type FeldFehler } from "../../rules/felder";
import { ruleValue } from "../../rules/format";
import { RegelFelder } from "../../rules/RegelFormular";
import { sortRules } from "../../rules/RegelnSimulation";

type Staff = components["schemas"]["StaffInfo"];

function Fehler({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (error instanceof ApiError && error.problem.status === 403) return <p role="alert" className="t-alert">{t("office.rules.forbidden")}</p>;
  if (error instanceof ApiError) return <p role="alert" className="t-alert">{error.problem.detail ?? error.problem.title}</p>;
  return <p role="alert" className="t-alert">{t("error.generic")}</p>;
}

export function Regeln() {
  const { t, i18n } = useTranslation();
  const staff = useOutletContext<Staff>();
  const coverage = useRulesCoverage();
  const startImport = useStartRulesImport();
  const extract = useStartExtraction();
  const operator = staff.roles.some((r) => r === "ops" || r === "rules_admin");
  const usd = (value: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "USD" }).format(value);

  return (
    <div className="flex flex-col gap-6">
      <Kopf titel={t("office.rules.title")}>
        <p>{t("office.rules.intro")}</p>
      </Kopf>
      {coverage.isPending && <p className="t-mute">{t("loading")}</p>}
      {coverage.isError && <Fehler error={coverage.error} />}
      {coverage.data && (
        <>
          <dl className="m-0 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div className="karte p-3">
              <dt className="t-mute">{t("office.rules.model")}</dt>
              <dd className="m-0 f-mono">{coverage.data.model}</dd>
            </div>
            <div className="karte p-3">
              <dt className="t-mute">{t("office.rules.cost")}</dt>
              <dd className="m-0 f-mono">
                {usd(coverage.data.month_cost_usd)} / {usd(coverage.data.budget_month_usd)}
              </dd>
            </div>
            <div className="karte p-3">
              <dt className="t-mute">{t("office.rules.configured")}</dt>
              <dd className={`m-0 ${coverage.data.configured ? "" : "t-alert"}`}>
                {t(coverage.data.configured ? "office.rules.yes" : "office.rules.notConfigured")}
              </dd>
            </div>
          </dl>
          {operator && (
            <div className="flex gap-3 items-center">
              <button type="button" className="btn btn-ghost" onClick={() => startImport.mutate(false)} disabled={startImport.isPending}>
                {t("office.rules.import")}
              </button>
              {startImport.isSuccess && <span className="text-sm t-mute" role="status">{t("office.rules.started")}</span>}
            </div>
          )}
          {extract.isError && <Fehler error={extract.error} />}
          {coverage.data.communes.map((commune) => (
            <section key={commune.commune_insee} className="flex flex-col gap-3" aria-labelledby={`gemeinde-${commune.commune_insee}`}>
              <h2 id={`gemeinde-${commune.commune_insee}`} className="m-0 text-base font-medium">
                {commune.plan?.title ?? commune.commune_insee}
                <span className="t-mute font-normal">
                  {" "}
                  · {commune.commune_insee} · {t(`office.rules.communeStatus.${commune.status}`, { defaultValue: commune.status })}
                </span>
              </h2>
              {commune.error && <p className="text-sm t-warn m-0 f-mono">{commune.error}</p>}
              {commune.fallback_plan && (
                <p className="text-sm t-warn m-0">{t("office.rules.fallbackPlan", { title: commune.fallback_plan.title })}</p>
              )}
              {commune.chapters.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="text-left border-b bd-strong">
                        <th scope="col" className="py-2 pr-3 font-medium">{t("office.rules.chapter")}</th>
                        <th scope="col" className="py-2 pr-3 font-medium">{t("office.rules.sectors")}</th>
                        <th scope="col" className="py-2 pr-3 font-medium">{t("office.rules.status")}</th>
                        <th scope="col" className="py-2 pr-3 font-medium text-right">{t("office.rules.runs")}</th>
                        <th scope="col" className="py-2 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {commune.chapters.map((chapter) => (
                        <tr key={chapter.id} className="border-b bd align-top">
                          <td className="py-2 pr-3">
                            <span className="f-mono">{chapter.code}</span>
                            <span className="t-mute"> · {t("rules.pages", { first: chapter.first_page, last: chapter.last_page })}</span>
                          </td>
                          <td className="py-2 pr-3">
                            <ul className="m-0 p-0 list-none flex flex-col gap-1">
                              {chapter.sectors.map((sector) => {
                                const version = chapter.rule_sets[sector];
                                const id = chapter.rule_set_ids[sector];
                                return (
                                  <li key={sector}>
                                    {id ? (
                                      <Link className="link f-mono" to={`/buero/regeln/${id}`}>
                                        {sector}
                                      </Link>
                                    ) : (
                                      <span className="f-mono">{sector}</span>
                                    )}
                                    {version && (
                                      <span className="t-mute">
                                        {" "}
                                        · {t(`rules.zoneStatus.${version.status}`)} · {t("office.rules.unknownCount", { count: version.coverage.mandatory_unknown ?? 0 })}
                                      </span>
                                    )}
                                  </li>
                                );
                              })}
                            </ul>
                          </td>
                          <td className="py-2 pr-3">
                            {t(`office.rules.chapterStatus.${chapter.status}`)}
                            {chapter.error && <span className="block text-xs t-alert f-mono">{chapter.error}</span>}
                          </td>
                          <td className="py-2 pr-3 text-right f-mono num">
                            {chapter.runs} · {usd(chapter.cost_usd)}
                          </td>
                          <td className="py-2 text-right">
                            {operator && chapter.status !== "extracting" && chapter.sectors.length > 0 && (
                              <button
                                type="button"
                                className="btn btn-ghost"
                                disabled={extract.isPending}
                                onClick={() => {
                                  // Gescheitert oder wartend: gespeicherte Teile weiterverwenden. Ausgewertet: nur
                                  // bewusst und mit Kostenhinweis vollständig neu
                                  const force = chapter.status === "succeeded";
                                  if (force && !window.confirm(t("office.rules.confirmExtract", { code: chapter.code, cost: usd(chapter.cost_usd) }))) {
                                    return;
                                  }
                                  extract.mutate({ chapterId: chapter.id, force });
                                }}
                              >
                                {t(chapter.status === "succeeded" ? "office.rules.extract" : "office.rules.retry")}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Regelwerk
// ---------------------------------------------------------------------------

interface Zeile {
  key: string;
  rule: RuleIn;
  draft: Entwurf;
  errors: FeldFehler;
}

function zeileAus(rule: RuleDetailOut, form: RuleKindFormOut | undefined, language: string): Zeile {
  return {
    key: `${rule.kind}-${rule.building_kind}`,
    rule: {
      kind: rule.kind as RuleIn["kind"],
      building_kind: rule.building_kind as RuleIn["building_kind"],
      status: rule.status,
      params: rule.params,
      page: rule.page,
      quote: rule.quote,
      notes: rule.notes,
    },
    draft: entwurfAus(form?.params ?? [], rule.params, language),
    errors: {},
  };
}

function Korrektur({ ruleSetId, rules, kinds }: { ruleSetId: string; rules: RuleDetailOut[]; kinds: RuleKindFormOut[] }) {
  const { t, i18n } = useTranslation();
  const create = useCreateRuleSetVersion(ruleSetId);
  const forms = new Map(kinds.map((k) => [k.kind as string, k]));
  const [zeilen, setZeilen] = useState<Zeile[]>(() => sortRules(rules).map((r) => zeileAus(r, forms.get(r.kind), i18n.language)));
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);

  const update = (index: number, change: Partial<Zeile>) =>
    setZeilen((current) => current.map((item, i) => (i === index ? { ...item, ...change } : item)));

  const submit = () => {
    const checked = zeilen.map((z) => {
      const form = forms.get(z.rule.kind);
      const withParams = z.rule.status === "effective" || z.rule.kind === "text_only";
      const result = withParams && form ? parameterAus(form.params, z.draft) : { params: {}, errors: {} };
      return { ...z, errors: result.errors, rule: { ...z.rule, params: withParams ? result.params : {} } };
    });
    setZeilen(checked);
    const hasErrors = checked.some((z) => Object.keys(z.errors).length > 0);
    setInvalid(hasErrors);
    if (!hasErrors) create.mutate({ rules: checked.map((z) => z.rule), note });
  };

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 className="eyebrow m-0">{t("office.rules.correction")}</h2>
      <p className="text-sm t-mute m-0">{t("office.rules.correctionIntro")}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("office.rules.status")}</th>
              <th scope="col" className="py-2 font-medium">{t("office.rules.params")}</th>
            </tr>
          </thead>
          <tbody>
            {zeilen.map((zeile, index) => (
              <tr key={zeile.key} className="border-b bd align-top">
                <th scope="row" className="py-2 pr-3 font-normal text-left">
                  {t(`rules.kind.${zeile.rule.kind}`)}
                  {zeile.rule.building_kind !== "main" && <span className="t-mute"> · {t(`rules.building.${zeile.rule.building_kind}`)}</span>}
                </th>
                <td className="py-2 pr-3">
                  <select
                    className="field"
                    aria-label={t("office.rules.statusFor", { kind: t(`rules.kind.${zeile.rule.kind}`) })}
                    value={zeile.rule.status}
                    onChange={(e) => update(index, { rule: { ...zeile.rule, status: e.target.value as RuleIn["status"] } })}
                  >
                    {(["effective", "unknown", "not_regulated", "text_only"] as const).map((status) => (
                      <option key={status} value={status}>
                        {t(`rules.status.${status}`)}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2" aria-label={t("office.rules.paramsFor", { kind: t(`rules.kind.${zeile.rule.kind}`) })}>
                  {(zeile.rule.status === "effective" || zeile.rule.kind === "text_only") && forms.get(zeile.rule.kind) && (
                    <RegelFelder
                      form={forms.get(zeile.rule.kind)!}
                      draft={zeile.draft}
                      errors={zeile.errors}
                      onChange={(draft) => update(index, { draft })}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        {t("office.rules.note")}
        <textarea className="field" rows={2} required minLength={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {invalid && <p role="alert" className="t-alert text-sm m-0">{t("rules.form.invalid")}</p>}
      {create.isError && <Fehler error={create.error} />}
      {create.isSuccess && <p role="status" className="text-sm m-0">{t("office.rules.saved")}</p>}
      <button type="submit" className="btn btn-primary self-start" disabled={create.isPending}>
        {t("office.rules.save")}
      </button>
    </form>
  );
}

export function Regelwerk() {
  const { t, i18n } = useTranslation();
  const { ruleSetId = "" } = useParams();
  const ruleSet = useRuleSet(ruleSetId);
  const kinds = useRuleKinds();
  const data = ruleSet.data;
  return (
    <div className="flex flex-col gap-6">
      <Link className="link text-sm" to="/buero/regeln">
        {t("office.rules.back")}
      </Link>
      {ruleSet.isPending && <p className="t-mute">{t("loading")}</p>}
      {ruleSet.isError && <Fehler error={ruleSet.error} />}
      {data && (
        <>
          <Kopf titel={t("rules.zone", { code: data.zone_code })}>
            <p>
              {data.plan.title}
              {data.current && (
                <span className="t-mute">
                  {" "}
                  · v{data.current.version} · {t(`rules.zoneStatus.${data.current.status}`)} · {new Date(data.current.created_at).toLocaleString(i18n.language)}
                </span>
              )}
            </p>
          </Kopf>
          <Abdeckung version={data.current} documentUrl={data.plan.regulation_url} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left border-b bd-strong">
                  <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.value")}</th>
                  <th scope="col" className="py-2 font-medium">{t("office.rules.quote")}</th>
                </tr>
              </thead>
              <tbody>
                {sortRules(data.rules).map((rule) => (
                  <tr key={`${rule.kind}-${rule.building_kind}`} className="border-b bd align-top">
                    <th scope="row" className="py-2 pr-3 font-normal text-left">
                      {t(`rules.kind.${rule.kind}`)}
                      {rule.building_kind !== "main" && rule.building_kind !== "any" && <span className="t-mute"> · {t(`rules.building.${rule.building_kind}`)}</span>}
                    </th>
                    <td className="py-2 pr-3">
                      {rule.status === "text_only" ? String(rule.params.summary ?? "") : ruleValue(rule, t, i18n.language)}
                      {rule.detail && <span className="block text-xs t-mute f-mono">{rule.detail}</span>}
                      {rule.alternatives.length > 0 && (
                        <span className="block text-xs t-mute f-mono">{JSON.stringify(rule.alternatives.map((a) => a.params ?? a.status))}</span>
                      )}
                    </td>
                    <td className="py-2 text-xs" lang="fr">
                      {rule.quote && <q>{rule.quote}</q>}{" "}
                      {rule.source_url && (
                        <a className="link whitespace-nowrap" href={rule.source_url} target="_blank" rel="noreferrer">
                          {t("rules.page", { page: rule.page })}
                        </a>
                      )}
                      {rule.quote && !rule.quote_verified && rule.origin === "extraction" && <span className="block t-alert">{t("office.rules.quoteUnverified")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {kinds.data && <Korrektur key={data.current?.id ?? "none"} ruleSetId={data.id} rules={data.rules} kinds={kinds.data} />}
        </>
      )}
    </div>
  );
}
