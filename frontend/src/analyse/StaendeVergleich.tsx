/**
 * Zwei Stände vergleichen (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5): ohne ↔ mit den Korrekturen des Projekts oder eine
 * frühere ↔ die aktuelle Auswertung (beide ohne Korrekturen). Gerechnet wird erst, wenn der Architekt den Vergleich
 * öffnet; die Antwort nennt die angebotenen Vergleiche.
 */

import type { TFunction } from "i18next";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAnalysisComparison, type AnalysisComparisonOut, type ComparisonBaseOut } from "../api/analysis";
import type { RuleOut } from "../api/rules";
import { ruleValue } from "../rules/format";
import { formatNumber } from "../site/geo";

type Figure = AnalysisComparisonOut["figures"][number];
type State = AnalysisComparisonOut["left"];

function datum(value: string, language: string): string {
  return new Date(value).toLocaleDateString(language === "de" ? "de-DE" : "fr-FR");
}

function basisLabel(base: ComparisonBaseOut, t: TFunction, language: string): string {
  if (base.kind === "corrections" || !base.version) return t("analyse.compare.base.corrections");
  return t("analyse.compare.base.version", {
    version: base.version.version,
    date: datum(base.version.created_at, language),
    origin: t(`analyse.compare.origin.${base.version.origin}`),
    zone: base.zone_code,
  });
}

function spalte(state: State, kind: AnalysisComparisonOut["kind"], side: "left" | "right", t: TFunction, language: string): string {
  if (kind === "corrections") return t(side === "left" ? "analyse.compare.withoutCorrections" : "analyse.compare.withCorrections");
  return state.version
    ? t("analyse.compare.versionColumn", { version: state.version.version, date: datum(state.version.created_at, language) })
    : t("analyse.compare.current");
}

function wert(figure: Figure, value: number | null | undefined, language: string): string {
  if (value == null) return "–";
  if (figure.unit === "m") return `${formatNumber(value, language, 2)} m`;
  if (figure.unit === "count") return formatNumber(value, language, 0);
  return `${formatNumber(value, language, 0)} m²`;
}

export function StaendeVergleich({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const selectId = useId();
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<string | null>(null);
  // Der Vergleich „automatisch“ nennt die angebotenen Vergleiche; ohne Korrekturen ist er selbst nicht darunter
  const first = useAnalysisComparison(projectId, open ? "automatic" : null);
  const bases = first.data?.bases ?? [];
  const selected = choice ?? bases[0]?.base ?? null;
  const second = useAnalysisComparison(projectId, open && selected !== null && selected !== "automatic" ? selected : null);
  const comparison = selected === "automatic" || selected === null ? first : second;
  const data = first.data;
  const shown = selected !== null && comparison.data?.base === selected ? comparison.data : undefined;
  const changedRules = shown?.rules.filter((r) => r.changed) ?? [];

  return (
    <details className="karte p-5 flex flex-col gap-4" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="cursor-pointer eyebrow">{t("analyse.compare.title")}</summary>
      <div className="flex flex-col gap-4 pt-4">
        <p className="t-mute text-sm m-0">{t("analyse.compare.intro")}</p>
        {comparison.isPending && open && <p className="t-mute m-0">{t("loading")}</p>}
        {comparison.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
        {data && bases.length === 0 && <p className="t-mute m-0">{t("analyse.compare.nothing")}</p>}
        {bases.length > 0 && (
          <div className="flex flex-col gap-1">
            <label htmlFor={selectId} className="text-sm">
              {t("analyse.compare.choose")}
            </label>
            <select id={selectId} className="field" value={selected ?? ""} onChange={(e) => setChoice(e.target.value)}>
              {bases.map((b) => (
                <option key={b.base} value={b.base}>
                  {basisLabel(b, t, lng)}
                </option>
              ))}
            </select>
          </div>
        )}
        {shown && (
          <>
            <div className="overflow-x-auto relative">
              <table className="w-full text-sm border-collapse">
                <caption className="sr-only">{t("analyse.compare.figures")}</caption>
                <thead>
                  <tr className="text-left border-b bd-strong">
                    <th scope="col" className="py-2 pr-3 font-medium">{t("analyse.compare.figure")}</th>
                    <th scope="col" className="py-2 pr-3 font-medium">{spalte(shown.left, shown.kind, "left", t, lng)}</th>
                    <th scope="col" className="py-2 font-medium">{spalte(shown.right, shown.kind, "right", t, lng)}</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.figures.map((figure) => (
                    <tr key={figure.key} className={`border-b bd ${figure.changed ? "t-ink font-medium" : "t-mute"}`}>
                      <th scope="row" className="py-2 pr-3 font-normal text-left">
                        {t(`analyse.compare.figureKey.${figure.key}`)}
                      </th>
                      <td className="py-2 pr-3 num">{wert(figure, figure.left, lng)}</td>
                      <td className="py-2 num">
                        {wert(figure, figure.right, lng)}
                        {figure.changed && <span className="sr-only"> {t("analyse.compare.changed")}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3 className="m-0 text-base font-medium t-ink">{t("analyse.compare.rules", { count: changedRules.length })}</h3>
            {changedRules.length === 0 ? (
              <p className="t-mute text-sm m-0">{t("analyse.compare.noRuleChanges")}</p>
            ) : (
              <div className="overflow-x-auto relative">
                <table className="w-full text-sm border-collapse">
                  <caption className="sr-only">{t("analyse.compare.rulesCaption")}</caption>
                  <thead>
                    <tr className="text-left border-b bd-strong">
                      <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
                      <th scope="col" className="py-2 pr-3 font-medium">{spalte(shown.left, shown.kind, "left", t, lng)}</th>
                      <th scope="col" className="py-2 font-medium">{spalte(shown.right, shown.kind, "right", t, lng)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changedRules.map((row) => (
                      <tr key={`${row.zone_code}-${row.kind}-${row.building_kind}`} className="border-b bd align-top">
                        <th scope="row" className="py-2 pr-3 font-normal text-left">
                          {t(`rules.kind.${row.kind}`)}
                          {row.building_kind !== "main" && row.building_kind !== "any" && (
                            <span className="t-mute"> · {t(`rules.building.${row.building_kind}`)}</span>
                          )}
                        </th>
                        <td className="py-2 pr-3">{row.left ? ruleValue(row.left as unknown as RuleOut, t, lng) : "–"}</td>
                        <td className="py-2 t-ink">{row.right ? ruleValue(row.right as unknown as RuleOut, t, lng) : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
}
