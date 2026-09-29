import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { SiteOut } from "../api/site";
import { formatNumber } from "./geo";

/** Gelände und Standortrisiken eines Grundstücks (Plan 3.3), im Konfigurator und in der Analyse (AN5). Der
 *  Architekt sieht die Werte selbst (mittlere Höhe, Neigung, Zahl der Höhenpunkte), der Kunde eine Einordnung. */
export function GelaendeRisiken({
  site,
  rolle = "customer",
  ebene = 2,
}: {
  site: SiteOut;
  rolle?: "customer" | "architect";
  ebene?: 2 | 3;
}) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const gelaendeId = useId();
  const risikenId = useId();
  const Titel = ebene === 2 ? "h2" : "h3";
  const { terrain, risks } = site;
  const items = risks.items ?? [];

  return (
    <>
      <section aria-labelledby={gelaendeId} className="flex flex-col gap-2">
        <Titel id={gelaendeId} className="eyebrow m-0">
          {t("site.terrain.title")}
        </Titel>
        {terrain.status === "pending" && <p className="t-mute text-sm m-0">{t("site.pending")}</p>}
        {terrain.status === "unavailable" && <p className="t-warn text-sm m-0">{t("site.terrain.unavailable")}</p>}
        {terrain.status === "ok" && terrain.slope_percent != null && (
          <p className="text-sm m-0">
            {rolle === "architect"
              ? t("site.terrain.values", {
                  altitude: formatNumber(terrain.reference_altitude_ngf ?? 0, lng, 2),
                  slope: formatNumber(terrain.slope_percent, lng, 1),
                  count: terrain.samples,
                })
              : t(terrain.flat ? "site.terrain.flat" : "site.terrain.sloped", {
                  slope: formatNumber(terrain.slope_percent, lng),
                  altitude: formatNumber(terrain.reference_altitude_ngf ?? 0, lng),
                })}
          </p>
        )}
      </section>

      <section aria-labelledby={risikenId} className="flex flex-col gap-2">
        <Titel id={risikenId} className="eyebrow m-0">
          {t("site.risks.title")}
        </Titel>
        {risks.status === "pending" && <p className="t-mute text-sm m-0">{t("site.pending")}</p>}
        {risks.status === "unavailable" && <p className="t-warn text-sm m-0">{t("site.risks.unavailable")}</p>}
        {risks.status === "ok" && items.length === 0 && <p className="text-sm m-0">{t("site.risks.none")}</p>}
        {risks.status === "ok" && items.length > 0 && (
          <ul className="m-0 p-0 list-none text-sm">
            {items.map((risk) => (
              <li key={risk.kind} className="flex justify-between gap-4 py-1 border-t bd">
                <span>{t(`site.risks.kind.${risk.kind}`, { defaultValue: risk.kind })}</span>
                <span className={risk.level === "high" ? "t-alert" : "t-mute"}>
                  {t(`site.risks.level.${risk.level}`)}
                  {risk.scope === "commune" ? ` · ${t("site.risks.commune")}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
