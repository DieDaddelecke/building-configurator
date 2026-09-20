/**
 * Schritt Optionen (Plan H3 4.4, Spez. 5.5.4): Liste mit Preis oder „in der Linie enthalten“; gesperrte Optionen
 * nennen ihre Gründe (Ausschluss oder ein Verstoß, den sie neu verursachen würden), damit der Kunde keinen Fehler
 * auslösen muss, um ihn zu sehen.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type { CheckOut, OptionChoiceOut, OptionsOut, SelectionReasonOut } from "../api/configuration";
import { checkText, localLabel, money } from "./format";
import { formatNumber } from "../site/geo";

interface OptionenProps {
  options: OptionsOut;
  onToggle: (slug: string, on: boolean) => void;
  pending: boolean;
  reasons?: SelectionReasonOut[];
  refusedChecks?: CheckOut[];
  failed?: boolean;
}

function priceText(option: OptionChoiceOut, lng: string, t: TFunction): string {
  const price = option.price;
  if (!price) return "";
  const amount = t("configurator.costs.plus", { amount: money(price.min_cents, lng) });
  return price.basis === "per_m2" && price.quantity != null
    ? `${amount} · ${formatNumber(price.quantity, lng, 1)} m² × ${money(price.unit_price_cents ?? 0, lng)}`
    : amount;
}

export function Optionen({ options, onToggle, pending, reasons = [], refusedChecks = [], failed = false }: OptionenProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const names: Record<string, string> = Object.fromEntries(options.options.map((o) => [o.slug, localLabel(o, lng)]));
  if (options.options.length === 0) {
    return <p className="text-sm t-warn m-0" role="status">{t(options.catalog_available ? "configurator.options.empty" : "configurator.package.unavailable")}</p>;
  }
  const groups: { key: string; items: OptionChoiceOut[] }[] = [
    { key: "outdoor", items: options.options.filter((o) => o.kind !== "plain") },
    { key: "other", items: options.options.filter((o) => o.kind === "plain") },
  ].filter((g) => g.items.length > 0);

  return (
    <div className="flex flex-col gap-6">
      {groups.map((group) => (
        <section key={group.key}>
          <h3 className="eyebrow pb-2">{t(`configurator.options.${group.key}`)}</h3>
          <div className="border-b bd">
            {group.items.map((option) => {
              const included = option.state === "included";
              const selected = option.state === "selected";
              const blocked = option.state === "blocked";
              const label = localLabel(option, lng);
              return (
                <div key={option.slug} className="border-t bd">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={included || selected}
                    aria-disabled={included || blocked || undefined}
                    disabled={pending || included || blocked}
                    data-testid={`option-${option.slug}`}
                    onClick={() => onToggle(option.slug, !selected)}
                    className={`w-full flex items-center gap-4 py-3 text-left bg-transparent border-0 ${included || blocked ? "cursor-default" : "cursor-pointer"}`}
                  >
                    <span className="kasten" data-an={selected} data-inkl={included} aria-hidden="true" />
                    <span className="flex-1 min-w-0">
                      <span className={`block ${included || blocked ? "t-mute" : "t-ink"}`}>{label}</span>
                      {option.area_m2 != null && (
                        <span className="block text-xs t-faint">{t("configurator.options.area", { area: formatNumber(option.area_m2, lng, 1) })}</span>
                      )}
                    </span>
                    <span className="text-right num whitespace-nowrap text-base">
                      {included ? (
                        <span className="text-sm t-mute">{t("configurator.options.included")}</span>
                      ) : (
                        <span className={selected ? "t-accent font-medium" : "t-ink"}>{priceText(option, lng, t)}</span>
                      )}
                    </span>
                  </button>
                  {blocked && (
                    <ul className="m-0 pb-3 pl-9 text-xs t-warn flex flex-col gap-1" data-testid={`gruende-${option.slug}`}>
                      {option.reasons.map((reason) => (
                        <li key={`${reason.code}-${reason.other ?? ""}`}>
                          {t(`configurator.options.reason.${reason.code}`, { other: reason.other ? (names[reason.other] ?? reason.other) : "" })}
                        </li>
                      ))}
                      {option.checks.map((check, index) => (
                        <li key={`${check.code}-${index}`}>{checkText(check, t, lng, names)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
      {failed && (
        <div className="text-sm t-alert" role="alert">
          {t("configurator.options.error")}
          <ul className="m-0 mt-1 pl-5">
            {reasons.map((r) => (
              <li key={`${r.code}-${r.slug}`}>{t(`configurator.options.reason.${r.code}`, { other: r.other ? (names[r.other] ?? r.other) : "" })}</li>
            ))}
            {refusedChecks.map((check, index) => (
              <li key={`${check.code}-${index}`}>{checkText(check, t, lng, names)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
