/**
 * Büro: Typenliste mit Versionen und Import eines neuen Entwurfs aus Typdatenblatt (XLSX) und Umriss (DXF)
 * (Plan H1 3.2, 3.3, 4.2). Das Schema der Dateien ist streng; Fehler nennen Blatt und Zelle.
 */

import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useOutletContext } from "react-router";

import { useCatalogTypes, useImportTypeVersion, type TypeSummaryOut } from "../../../api/catalog";
import type { components } from "../../../api/schema";
import { canEditCatalog, KatalogFehler, number, Statusmarke, spanne } from "../../../katalog/bausteine";

type Staff = components["schemas"]["StaffInfo"];

const SLUG_PATTERN = "^[a-z][a-z0-9_]{1,59}$";

function TypKarte({ type }: { type: TypeSummaryOut }) {
  const { t, i18n } = useTranslation();
  const current = type.current_version;
  const name = current?.name ?? type.versions[0]?.name ?? type.slug;
  return (
    <li className="karte p-4 flex flex-col gap-3" data-testid={`typ-${type.slug}`}>
      <div className="flex items-baseline gap-3 flex-wrap">
        <h3 className="m-0 text-lg font-medium">{name}</h3>
        <span className="f-mono text-sm t-mute">{type.slug}</span>
      </div>
      {current ? (
        <dl className="m-0 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-sm">
          <div>
            <dt className="t-mute">{t("catalog.type.storeys")}</dt>
            <dd className="m-0 f-mono">{current.storeys}</dd>
          </div>
          <div>
            <dt className="t-mute">{t("catalog.type.roof")}</dt>
            <dd className="m-0">{t(`catalog.roofForm.${current.roof_form}`)}</dd>
          </div>
          <div>
            <dt className="t-mute">{t("catalog.type.livingArea")}</dt>
            <dd className="m-0 num">{number(current.living_area_m2, i18n.language, 0)} m²</dd>
          </div>
          <div>
            <dt className="t-mute">{t("catalog.type.basePrice")}</dt>
            <dd className="m-0 num">{spanne(current.base_price_min_cents, current.base_price_max_cents, i18n.language)}</dd>
          </div>
        </dl>
      ) : (
        <p className="m-0 text-sm t-mute">{t("catalog.types.unpublished")}</p>
      )}
      <ul className="m-0 p-0 list-none flex gap-2 flex-wrap" aria-label={t("catalog.types.versions")}>
        {type.versions.map((version) => (
          <li key={version.version}>
            <Link
              className="chip inline-flex items-center gap-2 no-underline"
              to={`/buero/katalog/typen/${type.slug}/${version.version}`}
            >
              <span className="f-mono">v{version.version}</span>
              <Statusmarke status={version.status} />
            </Link>
          </li>
        ))}
      </ul>
    </li>
  );
}

function Import({ slugs }: { slugs: string[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const importVersion = useImportTypeVersion();
  const [slug, setSlug] = useState("");
  const [xlsx, setXlsx] = useState<File | null>(null);
  const [dxf, setDxf] = useState<File | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!xlsx || !dxf) return;
    importVersion.mutate(
      { slug, xlsx, dxf },
      { onSuccess: (version) => navigate(`/buero/katalog/typen/${version.slug}/${version.version}`) },
    );
  };

  return (
    <section aria-labelledby="katalog-import" className="karte p-4 flex flex-col gap-4">
      <h3 id="katalog-import" className="m-0 text-lg font-medium">
        {t("catalog.import.title")}
      </h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.import.intro")}</p>
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-3 items-end">
        <label className="flex flex-col gap-1 text-sm">
          {t("catalog.import.slug")}
          <input
            className="field f-mono"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            pattern={SLUG_PATTERN}
            list="katalog-slugs"
            required
            aria-describedby="katalog-slug-hint"
          />
          <datalist id="katalog-slugs">
            {slugs.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <span id="katalog-slug-hint" className="text-xs t-mute">
            {t("catalog.import.slugHint")}
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("catalog.import.xlsx")}
          <input
            className="field"
            type="file"
            accept=".xlsx"
            required
            onChange={(e) => setXlsx(e.target.files?.[0] ?? null)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("catalog.import.dxf")}
          <input
            className="field"
            type="file"
            accept=".dxf"
            required
            onChange={(e) => setDxf(e.target.files?.[0] ?? null)}
          />
        </label>
        <div className="md:col-span-3 flex items-center gap-4">
          <button type="submit" className="btn btn-primary" disabled={importVersion.isPending || !xlsx || !dxf || !slug}>
            {importVersion.isPending ? t("catalog.import.running") : t("catalog.import.submit")}
          </button>
        </div>
      </form>
      {importVersion.isError && <KatalogFehler error={importVersion.error} />}
      <details className="text-sm">
        <summary className="cursor-pointer link">{t("catalog.import.formatTitle")}</summary>
        <ul className="mt-2 pl-5 flex flex-col gap-1 t-mute">
          <li>{t("catalog.import.formatKennwerte")}</li>
          <li>{t("catalog.import.formatRooms")}</li>
          <li>{t("catalog.import.formatPrices")}</li>
          <li>{t("catalog.import.formatDxf")}</li>
        </ul>
      </details>
    </section>
  );
}

export function KatalogTypen() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  const types = useCatalogTypes();
  return (
    <div className="flex flex-col gap-6">
      {types.isPending && <p className="t-mute">{t("loading")}</p>}
      {types.isError && <KatalogFehler error={types.error} />}
      {types.data && (
        <>
          {types.data.length === 0 && <p className="t-mute">{t("catalog.types.empty")}</p>}
          <ul className="m-0 p-0 list-none flex flex-col gap-4">
            {types.data.map((type) => (
              <TypKarte key={type.slug} type={type} />
            ))}
          </ul>
          {canEditCatalog(staff) ? (
            <Import slugs={types.data.map((type) => type.slug)} />
          ) : (
            <p className="text-sm t-mute">{t("catalog.readOnly")}</p>
          )}
        </>
      )}
    </div>
  );
}
