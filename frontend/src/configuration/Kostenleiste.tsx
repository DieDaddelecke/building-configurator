/**
 * Kostenkorridor als feste Leiste unten (Plan H3 4.4, Spez. 5.6.5): nur eine Spanne, gerundet und mit „ca.“, nie
 * ein Einzelbetrag als Gesamtpreis (L1). Die Posten lassen sich aufklappen; der Betrag ist eine Schätzung.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type { CostItemOut, CostsOut } from "../api/configuration";
import { formatNumber } from "../site/geo";
import { localLabel, money } from "./format";

function itemLabel(item: CostItemOut, lng: string, t: TFunction): string {
  if (item.kind === "energy") return t("configurator.costs.energy");
  const label = localLabel(item, lng);
  return item.unit === "m2" && item.quantity != null && item.unit_price_cents != null
    ? `${label} (${t("configurator.costs.perM2", { quantity: formatNumber(item.quantity, lng, 1), unit: money(item.unit_price_cents, lng) })})`
    : label;
}

function itemAmount(item: CostItemOut, lng: string, t: TFunction): string {
  if (item.included) return t("configurator.costs.included");
  if (item.kind === "base") return `${money(item.min_cents, lng)} – ${money(item.max_cents, lng)}`;
  return item.min_cents === item.max_cents
    ? t("configurator.costs.plus", { amount: money(item.min_cents, lng) })
    : t("configurator.costs.plusRange", { min: money(item.min_cents, lng), max: money(item.max_cents, lng) });
}

export function Kostenleiste({ costs }: { costs: CostsOut | null | undefined }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  if (!costs) return null;
  return (
    <aside
      aria-label={t("configurator.costs.title")}
      data-testid="kostenleiste"
      className="sticky bottom-0 z-10 bg-paper border-t bd-strong -mx-6 lg:-mx-10 px-6 lg:px-10 py-3"
    >
      <div className="max-w-7xl mx-auto flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <div className="eyebrow">{t("configurator.costs.title")}</div>
          {costs.available && costs.display ? (
            <div className="f-display text-2xl font-semibold t-ink num" data-testid="korridor">
              {t("configurator.costs.range", { min: money(costs.display.min_cents, lng), max: money(costs.display.max_cents, lng) })}
              <span className="text-sm font-normal t-mute ml-2">
                {costs.vat_rate > 0 ? t("configurator.costs.gross") : t("configurator.costs.net")}
              </span>
            </div>
          ) : (
            <div className="text-sm t-warn" role="status" data-testid="korridor-fehlt">
              {t("configurator.costs.unavailable", { reason: t(`configurator.costs.reason.${costs.reason ?? "catalog_unavailable"}`) })}
            </div>
          )}
        </div>
        {costs.available && (
          <details className="text-sm">
            <summary className="cursor-pointer t-accent">{t("configurator.costs.details")}</summary>
            <ul className="m-0 mt-2 p-0 list-none flex flex-col gap-1" data-testid="posten">
              {costs.items.map((item) => (
                <li key={item.code} className="flex justify-between gap-4">
                  <span className={item.included ? "t-mute" : "t-ink"}>{itemLabel(item, lng, t)}</span>
                  <span className="num whitespace-nowrap t-mute">{itemAmount(item, lng, t)}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs t-mute mt-2 mb-0">{t("configurator.costs.hint")}</p>
          </details>
        )}
      </div>
    </aside>
  );
}
