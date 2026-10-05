/**
 * Richtpreis als feste Leiste unten (docs/PLAN_HAUSMODELL.md 3.8): gesamt brutto auf 1.000 €, Aufpreise je Slot auf
 * 100 € gerundet, immer mit „ca.“ und dem Hinweis auf die Prüfung durch das Büro; keine Positionen (B-65). Solange
 * eine Wahl nicht gespeichert ist, zeigt sie die Vorschau des Kerns im Browser, danach den Preis des Servers (L5).
 */

import { useTranslation } from "react-i18next";

import { euro, euroDelta } from "./preis";

export interface Aufpreis {
  slot: string;
  /** Bezeichnung von Slot und gewähltem Wert, z. B. „Außenwand – Ziegel“. */
  text: string;
  betrag: number;
}

interface PreisleisteProps {
  gesamt: number | null;
  aufpreise: readonly Aufpreis[];
  /** Der Betrag kommt aus dem Browser, die Wahl ist noch nicht gespeichert. */
  vorschau: boolean;
  laeuft: boolean;
  gespeichert: boolean;
  fehler: string | null;
  /** `false`: Der Server hat beim letzten Speichern anders gerechnet als der Browser. */
  preisGleich: boolean | null;
}

export function Preisleiste({ gesamt, aufpreise, vorschau, laeuft, gespeichert, fehler, preisGleich }: PreisleisteProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const zustand = laeuft
    ? t("houseConfigurator.save.saving")
    : vorschau
      ? t("houseConfigurator.price.preview")
      : gespeichert
        ? t("houseConfigurator.save.saved")
        : "";
  return (
    <aside
      aria-label={t("houseConfigurator.price.title")}
      data-testid="preisleiste"
      className="sticky bottom-0 z-10 bg-paper border-t bd-strong -mx-6 lg:-mx-10 px-6 lg:px-10 py-3"
    >
      <div className="max-w-7xl mx-auto flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="eyebrow">{t("houseConfigurator.price.title")}</span>
            <span className="text-xs t-mute" role="status" aria-live="polite" data-testid="speicherstand">
              {zustand}
            </span>
          </div>
          {gesamt !== null && (
            <div className="f-display text-2xl font-semibold t-ink num" data-testid="gesamtpreis">
              {t("houseConfigurator.price.total", { amount: euro(gesamt, lng) })}
              <span className="text-sm font-normal t-mute ml-2">{t("houseConfigurator.price.gross")}</span>
            </div>
          )}
        </div>
        <p className="text-xs t-mute m-0">{t("houseConfigurator.price.hint")}</p>
        {fehler && (
          <p className="text-sm t-alert m-0" role="alert">
            {fehler}
          </p>
        )}
        {preisGleich === false && !vorschau && (
          <p className="text-sm t-warn m-0" role="status" data-testid="preisabweichung">
            {t("houseConfigurator.price.mismatch")}
          </p>
        )}
        <details className="text-sm">
          <summary className="cursor-pointer t-accent">{t("houseConfigurator.price.surcharges")}</summary>
          {aufpreise.length ? (
            <ul className="m-0 mt-2 p-0 list-none flex flex-col gap-1" data-testid="aufpreise">
              {aufpreise.map((item) => (
                <li key={item.slot} className="flex justify-between gap-4">
                  <span className="t-ink">{item.text}</span>
                  <span className="num whitespace-nowrap t-mute">
                    {t("houseConfigurator.equipment.delta", { amount: euroDelta(item.betrag, lng) })}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="t-mute mt-2 mb-0">{t("houseConfigurator.price.none")}</p>
          )}
        </details>
      </div>
    </aside>
  );
}
