/**
 * Schritt Ausstattungslinie (Plan H3 4.4, Spez. 5.5.6): Karten mit Leistungsumfang und Aufpreis, darunter der
 * RE2020-Hinweis der gewählten Linie. Preise brutto, immer als „+ ca.“ (L1, D10).
 */

import { useTranslation } from "react-i18next";

import type { EnergyStatusOut, OptionsOut, PackageChoiceOut, SelectionReasonOut } from "../api/configuration";
import { localLabel, money } from "./format";

interface LinienProps {
  options: OptionsOut;
  onSelect: (slug: string | null) => void;
  pending: boolean;
  /** Ablehnung des Servers (`invalid_selection`) */
  reasons?: SelectionReasonOut[];
  failed?: boolean;
}

export function EnergieHinweis({ energy, vatRate }: { energy: EnergyStatusOut; vatRate?: number }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const amount = energy.surcharge_cents != null ? money(energy.surcharge_cents, lng) : "";
  void vatRate;
  const tone = energy.status === "action" ? "bg-warn" : "bg-sheet border bd";
  return (
    <div role="status" className={`${tone} px-5 py-4 flex flex-col gap-1`} data-testid="energie">
      <div className="eyebrow t-warn">
        {t("configurator.energy.title")}
        {energy.climate_zone ? ` · ${t("configurator.energy.zone", { zone: energy.climate_zone })}` : ""}
      </div>
      <p className="t-ink m-0">
        {energy.status === "compliant" && t("configurator.energy.compliant", { verdict: energy.verdict ?? "" })}
        {energy.status === "action" &&
          (energy.surcharge_cents != null
            ? t("configurator.energy.action", { verdict: energy.verdict ?? "", measures: energy.measures ?? "", amount })
            : t("configurator.energy.actionNoPrice", { verdict: energy.verdict ?? "", measures: energy.measures ?? "" }))}
        {energy.status === "not_assessed" && t("configurator.energy.not_assessed")}
      </p>
    </div>
  );
}

function Karte({ pack, onSelect, pending, names }: { pack: PackageChoiceOut; onSelect: () => void; pending: boolean; names: string }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const label = localLabel(pack, lng);
  return (
    <article
      data-testid={`linie-${pack.slug}`}
      className={`border flex flex-col gap-3 p-5 ${pack.selected ? "bg-tint bd-strong" : "bg-sheet bd"}`}
    >
      <h3 className="f-display text-xl font-semibold t-ink m-0">{label}</h3>
      <div className="text-sm t-mute num">
        {pack.price.max_cents > 0 ? t("configurator.package.surcharge", { amount: money(pack.price.max_cents, lng) }) : t("configurator.package.included")}
      </div>
      {pack.scope.length > 0 && (
        <div>
          <div className="eyebrow pb-1">{t("configurator.package.scope")}</div>
          <ul className="m-0 pl-5 text-sm t-ink flex flex-col gap-1">
            {pack.scope.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {names && <p className="text-sm t-mute m-0">{t("configurator.package.includes", { options: names })}</p>}
      {pack.retired && <p className="text-sm t-warn m-0">{t("configurator.package.retired")}</p>}
      <button
        type="button"
        className={`btn justify-center mt-auto ${pack.selected ? "btn-primary" : "btn-ghost"}`}
        aria-pressed={pack.selected}
        disabled={pending}
        onClick={onSelect}
      >
        {pack.selected ? t("configurator.package.selected") : t("configurator.package.select", { name: label })}
      </button>
    </article>
  );
}

export function Linien({ options, onSelect, pending, reasons = [], failed = false }: LinienProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  if (!options.catalog_available || options.packages.length === 0) {
    return <p className="text-sm t-warn m-0" role="status">{options.catalog_available ? t("configurator.package.empty") : t("configurator.package.unavailable")}</p>;
  }
  const chosen = options.packages.find((p) => p.selected) ?? null;
  const nameOf = (slug: string) => {
    const found = options.options.find((o) => o.slug === slug);
    return found ? localLabel(found, lng) : slug;
  };
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {options.packages.map((pack) => (
          <Karte
            key={pack.slug}
            pack={pack}
            pending={pending}
            names={pack.included_option_slugs.map(nameOf).join(", ")}
            onSelect={() => onSelect(pack.selected ? null : pack.slug)}
          />
        ))}
      </div>
      {failed && (
        <p className="text-sm t-alert m-0" role="alert">
          {t("configurator.package.error")}
          {reasons.length > 0 && ` (${reasons.map((r) => t(`configurator.options.reason.${r.code}`, { other: r.other ?? "" })).join(", ")})`}
        </p>
      )}
      {chosen && <EnergieHinweis energy={chosen.energy} />}
    </div>
  );
}
