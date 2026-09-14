/**
 * Schritt „Grundstück prüfen“ (Plan 3.3): Lageplan, Kennwerte, Kanten mit Korrektur, Gelände, Risiken und
 * Hinweise nach L7. Kunde und Büro nutzen dieselbe Ansicht mit unterschiedlichen Korrekturrechten.
 */

import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError, unwrap } from "../api/client";
import type { SiteOut } from "../api/site";
import { Planblatt } from "../components/plan/Planblatt";
import { compass, CUSTOMER_WARNINGS, formatNumber } from "./geo";
import { KantenListe } from "./KantenListe";
import { SiteLageplan } from "./SiteLageplan";

interface GrundstueckPruefenProps {
  site: SiteOut;
  rolle: "customer" | "architect";
  onEdgeChange: (seq: number, value: string | null) => void;
  pending: boolean;
  error: unknown;
  actions?: ReactNode;
}

function Zeile({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-2 border-t bd">
      <dt className="t-mute">{k}</dt>
      <dd className="m-0 t-ink text-right">{v}</dd>
    </div>
  );
}

export function useNotices(keys: readonly string[]) {
  const { i18n } = useTranslation();
  return useQuery({
    queryKey: ["legal-notices", i18n.resolvedLanguage, ...keys],
    queryFn: async () => unwrap(await api.GET("/api/v1/legal/notices", { params: { query: { key: [...keys] } } })),
    enabled: keys.length > 0,
    staleTime: 3_600_000,
  });
}

export function GrundstueckPruefen({ site, rolle, onEdgeChange, pending, error, actions }: GrundstueckPruefenProps) {
  const { t, i18n } = useTranslation();
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const notices = useNotices(site.notices);
  const lng = i18n.language;
  const warnings = rolle === "customer" ? site.warnings.filter((w) => CUSTOMER_WARNINGS.has(w)) : site.warnings;
  const idus = site.parcels.map((p) => `${p.section.replace(/^0/, "")} ${Number(p.number)}`).join(" + ");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
      <div className="lg:col-span-7 flex flex-col gap-6">
        <Planblatt
          inhalt={t("site.plan.title")}
          schriftfeld={[
            { label: t("sheet.parcel"), wert: idus },
            { label: t("site.facts.area"), wert: `${formatNumber(site.area_m2, lng, 0)} m²` },
            { label: t("site.facts.revision"), wert: String(site.revision) },
          ]}
          fuss={
            <ul className="flex flex-wrap gap-x-5 gap-y-1 px-4 py-2 border-t bd m-0 list-none text-xs t-mute">
              {(["street", "side", "rear", "other"] as const).map((kind) => (
                <li key={kind} className="flex items-center gap-2">
                  <span className="inline-block w-5 h-0.5" style={{ background: `var(--${{ street: "accent", side: "ink", rear: "warn", other: "faint" }[kind]})` }} />
                  {t(`site.kind.${kind}`)}
                </li>
              ))}
              <li>{t("site.plan.dashed")}</li>
            </ul>
          }
        >
          <SiteLageplan site={site} highlightedSeq={highlighted} onHighlight={setHighlighted} />
        </Planblatt>
        <KantenListe
          edges={site.edges}
          rolle={rolle}
          onChange={onEdgeChange}
          pending={pending}
          highlightedSeq={highlighted}
          onHighlight={setHighlighted}
        />
        {error instanceof ApiError && (
          <p role="alert" className="t-alert text-sm m-0">
            {error.problem.title}
          </p>
        )}
      </div>

      <aside className="lg:col-span-5 flex flex-col gap-6">
        {!site.binding && (
          <p className="bg-warn t-warn px-4 py-3 text-sm m-0" role="status">
            {t(rolle === "customer" ? "site.binding.customer" : "site.binding.architect")}
          </p>
        )}
        <dl className="m-0">
          <Zeile k={t("site.facts.area")} v={`${formatNumber(site.area_m2, lng, 0)} m²`} />
          <Zeile
            k={t("site.facts.officialArea")}
            v={site.area_official_m2 != null ? `${formatNumber(site.area_official_m2, lng, 0)} m²` : "–"}
          />
          <Zeile
            k={t("site.facts.streetSide")}
            v={site.street_azimuth_deg != null ? t(`site.compass.${compass(site.street_azimuth_deg)}`) : "–"}
          />
          <Zeile
            k={t("site.facts.gardenSide")}
            v={site.garden_azimuth_deg != null ? t(`site.compass.${compass(site.garden_azimuth_deg)}`) : "–"}
          />
          <Zeile k={t("site.facts.parcels")} v={site.parcels.map((p) => p.idu).join(", ")} />
        </dl>

        {warnings.length > 0 && (
          <section aria-labelledby="hinweise-grundstueck">
            <h2 id="hinweise-grundstueck" className="eyebrow mb-2">
              {t("site.warnings.title")}
            </h2>
            <ul className="m-0 pl-5 flex flex-col gap-1 text-sm">
              {warnings.map((w) => (
                <li key={w}>{t(`site.warnings.${w}`)}</li>
              ))}
            </ul>
          </section>
        )}

        <section aria-labelledby="gelaende" className="flex flex-col gap-2">
          <h2 id="gelaende" className="eyebrow m-0">
            {t("site.terrain.title")}
          </h2>
          {site.terrain.status === "pending" && <p className="t-mute text-sm m-0">{t("site.pending")}</p>}
          {site.terrain.status === "unavailable" && <p className="t-warn text-sm m-0">{t("site.terrain.unavailable")}</p>}
          {site.terrain.status === "ok" && site.terrain.slope_percent != null && (
            <p className="text-sm m-0">
              {t(site.terrain.flat ? "site.terrain.flat" : "site.terrain.sloped", {
                slope: formatNumber(site.terrain.slope_percent, lng),
                altitude: formatNumber(site.terrain.reference_altitude_ngf ?? 0, lng),
              })}
            </p>
          )}
        </section>

        <section aria-labelledby="risiken" className="flex flex-col gap-2">
          <h2 id="risiken" className="eyebrow m-0">
            {t("site.risks.title")}
          </h2>
          {site.risks.status === "pending" && <p className="t-mute text-sm m-0">{t("site.pending")}</p>}
          {site.risks.status === "unavailable" && <p className="t-warn text-sm m-0">{t("site.risks.unavailable")}</p>}
          {site.risks.status === "ok" && (site.risks.items ?? []).length === 0 && <p className="text-sm m-0">{t("site.risks.none")}</p>}
          {site.risks.status === "ok" && (site.risks.items ?? []).length > 0 && (
            <ul className="m-0 p-0 list-none text-sm">
              {(site.risks.items ?? []).map((risk) => (
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

        <section aria-labelledby="rechtliches" className="flex flex-col gap-2 text-sm">
          <h2 id="rechtliches" className="eyebrow m-0">
            {t("site.notices.title")}
          </h2>
          {site.notices.map((key) => {
            const published = notices.data?.find((n) => n.key === key);
            return (
              <p key={key} className="m-0 t-mute" lang={published?.locale}>
                {published ? published.body : t(`site.notices.${key.replace("notice.", "")}`)}
              </p>
            );
          })}
        </section>

        {actions}
      </aside>
    </div>
  );
}
