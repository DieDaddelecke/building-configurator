/**
 * Haustypen des Hausmodells mit Zulässigkeit (docs/PLAN_HAUSMODELL.md Ergänzung 9, D12): geprüft mit den Standards
 * des Templates; ein gesperrter Typ nennt alle Gründe. Der Richtpreis „ab“ ist brutto und auf 1.000 € gerundet.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type { CheckOut } from "../api/configuration";
import type { HouseTemplateFitOut } from "../api/hausKonfiguration";
import { checkText, STATUS_TONE } from "../configuration/format";
import { formatNumber } from "../site/geo";
import { euro } from "./preis";
import { grad, label } from "./texte";

interface HausTypenProps {
  templates: readonly HouseTemplateFitOut[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
  pending?: boolean;
  /** Der zuletzt versuchte Haustyp wurde abgelehnt (z. B. inzwischen gesperrt). */
  failedSlug?: string | null;
}

function Pruefungen({ title, checks, tone }: { title: string; checks: readonly CheckOut[]; tone: string }) {
  const { t, i18n } = useTranslation();
  if (checks.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <div className={`eyebrow ${tone}`}>{title}</div>
      <ul className="m-0 pl-5 text-sm flex flex-col gap-1">
        {checks.map((check, index) => (
          <li key={`${check.code}-${check.edge_seq ?? ""}-${index}`} className={STATUS_TONE[check.status]}>
            {checkText(check, t, i18n.language)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Dachform mit ihren Neigungen, z. B. „Mansarddach, 25° / 70°“ (E-HM-61). */
function dach(facts: HouseTemplateFitOut["facts"], t: TFunction, lng: string): string {
  const form = t(`configurator.types.roof.${facts.roof_form}`, { defaultValue: facts.roof_form });
  if (facts.pitches_deg.length === 0) return form;
  return `${form}, ${facts.pitches_deg.map((pitch) => grad(pitch, lng)).join(" / ")}`;
}

export function HausTypen({ templates, selectedSlug, onSelect, pending = false, failedSlug = null }: HausTypenProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  if (templates.length === 0) return <p className="t-mute">{t("houseConfigurator.types.empty")}</p>;
  const ordered = [...templates].sort((a, b) => Number(b.allowed) - Number(a.allowed));

  return (
    <ul className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 m-0 p-0 list-none" data-testid="haustypen">
      {ordered.map((template) => {
        const selected = template.slug === selectedSlug;
        const facts = template.facts;
        const rows: [string, string][] = [
          [t("houseConfigurator.fact.footprint"), `${formatNumber(facts.footprint_m2, lng, 0)} m²`],
          [t("houseConfigurator.fact.floorArea"), `${formatNumber(facts.floor_area_m2, lng, 0)} m²`],
          [t("houseConfigurator.fact.size"), `${formatNumber(facts.width_m, lng, 2)} × ${formatNumber(facts.depth_m, lng, 2)} m`],
          [t("houseConfigurator.fact.roof"), dach(facts, t, lng)],
          [t("houseConfigurator.fact.height"), `${formatNumber(facts.height_m, lng, 2)} m`],
          [t("houseConfigurator.fact.storeys"), facts.storeys],
        ];
        return (
          <li
            key={template.slug}
            data-testid={`haustyp-${template.slug}`}
            className={`flex flex-col gap-4 p-5 border ${selected ? "bd-accent bg-tint" : "bd bg-sheet"}`}
            style={selected ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="flex flex-col gap-1">
              <h3 className="f-display text-xl font-semibold t-ink m-0">{label(template.name, lng)}</h3>
              <span className={`eyebrow ${template.allowed ? "t-accent" : "t-alert"}`}>
                {template.allowed ? t("configurator.types.allowed") : t("configurator.types.blocked")}
              </span>
            </div>
            <p className="m-0 t-ink">
              <span className="f-display text-2xl font-semibold num" data-testid="ab-preis">
                {t("houseConfigurator.price.from", { amount: euro(template.price.gross_rounded, lng) })}
              </span>{" "}
              <span className="text-sm t-mute">{t("houseConfigurator.price.gross")}</span>
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 m-0 text-sm">
              {rows.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-2 border-t bd py-1">
                  <dt className="t-mute">{label}</dt>
                  <dd className="m-0 num t-ink text-right">{value}</dd>
                </div>
              ))}
            </dl>
            {!template.allowed && <Pruefungen title={t("configurator.types.reasons")} checks={template.reasons} tone="t-alert" />}
            <Pruefungen title={t("configurator.types.hints")} checks={template.hints} tone="t-mute" />
            {failedSlug === template.slug && (
              <p role="alert" className="text-sm t-alert m-0">
                {t("configurator.types.selectError")}
              </p>
            )}
            <div className="mt-auto pt-2">
              {selected ? (
                <span className="eyebrow t-accent">{t("configurator.types.selected")}</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!template.allowed || pending}
                  onClick={() => onSelect(template.slug)}
                >
                  {t("configurator.types.select")}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
