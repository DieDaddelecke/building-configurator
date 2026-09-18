/**
 * Büro: Entwurf des Preiskatalogs (Plan H1 3.7). Die Preise kommen aus den Typdatenblättern (Blatt „Preise“) und
 * bleiben an die Typ-Identität gebunden; hier werden sie geprüft und gemeinsam veröffentlicht. Es erscheinen nur
 * Bestandteile und Spannen, nie ein Gesamtpreis (L1); die Korridorformel wertet erst H3 aus.
 */

import { useTranslation } from "react-i18next";
import { useOutletContext } from "react-router";

import { useDraftPriceCatalog, usePublishPriceCatalog, type PriceCatalogVersionOut } from "../../../api/catalog";
import type { components } from "../../../api/schema";
import { canEditCatalog, eur, KatalogFehler, number, spanne, Statusmarke } from "../../../katalog/bausteine";

type Staff = components["schemas"]["StaffInfo"];

function Tabelle({ titel, kopf, zeilen, leer }: { titel: string; kopf: string[]; zeilen: string[][]; leer: string }) {
  return (
    <section className="flex flex-col gap-2" aria-label={titel}>
      <h3 className="m-0 text-lg font-medium">{titel}</h3>
      {zeilen.length === 0 ? (
        <p className="m-0 text-sm t-mute">{leer}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b bd-strong">
                {kopf.map((label) => (
                  <th key={label} scope="col" className="py-2 pr-3 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {zeilen.map((row, i) => (
                <tr key={i} className="border-b bd">
                  {row.map((cell, j) => (
                    <td key={j} className={`py-2 pr-3 ${j === 0 ? "f-mono" : "num"}`}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Inhalt({ catalog }: { catalog: PriceCatalogVersionOut }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const none = t("catalog.prices.empty");
  return (
    <div className="flex flex-col gap-8">
      <Tabelle
        titel={t("catalog.prices.base")}
        kopf={[t("catalog.prices.type"), t("catalog.prices.range")]}
        zeilen={catalog.base_prices.map((p) => [p.building_type_slug, spanne(p.min_cents, p.max_cents, lang)])}
        leer={none}
      />
      <Tabelle
        titel={t("catalog.prices.lines")}
        kopf={[t("catalog.prices.line"), t("catalog.prices.type"), t("catalog.prices.surcharge")]}
        zeilen={catalog.package_prices.map((p) => [p.package_slug, p.building_type_slug, eur(p.surcharge_cents, lang)])}
        leer={none}
      />
      <Tabelle
        titel={t("catalog.prices.options")}
        kopf={[t("catalog.prices.option"), t("catalog.prices.type"), t("catalog.prices.surcharge")]}
        zeilen={catalog.module_prices.map((p) => [p.module_slug, p.building_type_slug, eur(p.surcharge_cents, lang)])}
        leer={none}
      />
      <Tabelle
        titel={t("catalog.prices.energy")}
        kopf={[t("catalog.prices.type"), t("catalog.prices.line"), t("catalog.type.energy.zone"), t("catalog.type.energy.verdict"), t("catalog.type.energy.surcharge")]}
        zeilen={catalog.energy_assessments.map((a) => [
          a.building_type_slug,
          a.package_slug,
          a.climate_zone,
          `${a.compliant ? t("catalog.type.energy.compliantShort") : t("catalog.type.energy.notCompliantShort")} · ${a.verdict}`,
          a.compliance_surcharge_cents != null ? eur(a.compliance_surcharge_cents, lang) : "–",
        ])}
        leer={none}
      />
    </div>
  );
}

export function KatalogPreise() {
  const { t, i18n } = useTranslation();
  const staff = useOutletContext<Staff>();
  const draft = useDraftPriceCatalog();
  const publish = usePublishPriceCatalog();
  const catalog = draft.data; // nach dem Veröffentlichen legt die nächste Abfrage einen neuen Entwurf an
  return (
    <div className="flex flex-col gap-6">
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.prices.intro")}</p>
      {draft.isPending && <p className="t-mute">{t("loading")}</p>}
      {draft.isError && <KatalogFehler error={draft.error} />}
      {catalog && (
        <>
          <dl className="m-0 flex gap-6 flex-wrap text-sm items-baseline">
            <div className="flex gap-2 items-baseline">
              <dt className="t-mute">{t("catalog.prices.version")}</dt>
              <dd className="m-0 f-mono">{catalog.region} · v{catalog.version}</dd>
              <Statusmarke status={catalog.status} />
            </div>
            <div className="flex gap-2">
              <dt className="t-mute">{t("catalog.prices.validFrom")}</dt>
              <dd className="m-0 num">{new Date(catalog.valid_from).toLocaleDateString(i18n.language)}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="t-mute">{t("catalog.prices.vat")}</dt>
              <dd className="m-0 num">{number(catalog.vat_rate_default * 100, i18n.language)} %</dd>
            </div>
          </dl>
          <Inhalt catalog={catalog} />
          {canEditCatalog(staff) && catalog.status === "draft" && (
            <div className="border-t bd pt-6 flex items-center gap-4 flex-wrap">
              <button
                type="button"
                className="btn btn-primary"
                disabled={publish.isPending}
                onClick={() => {
                  if (window.confirm(t("catalog.prices.publishConfirm", { version: catalog.version }))) publish.mutate();
                }}
              >
                {t("catalog.prices.publish")}
              </button>
              <span className="text-sm t-mute">{t("catalog.prices.publishHint")}</span>
            </div>
          )}
          {publish.isSuccess && <p role="status" className="m-0 text-sm t-mute">{t("catalog.prices.published", { version: publish.data.version })}</p>}
          {publish.isError && <KatalogFehler error={publish.error} />}
        </>
      )}
    </div>
  );
}
