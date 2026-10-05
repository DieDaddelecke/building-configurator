/**
 * Büro: Hausmodell (docs/PLAN_HAUSMODELL.md 3.6, HM3): Haustypen aus IFC mit ihren Versionen, Upload einer
 * neuen Datei und die Katalogversionen. Den Katalog übernimmt der Betrieb per CLI; bearbeiten darf nur
 * `catalog_admin`, Architekt und Betrieb lesen.
 */

import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useOutletContext } from "react-router";

import {
  useHouseCatalogs,
  useHouseTemplates,
  useUploadHouseIfc,
  type HouseCatalogVersionOut,
  type HouseTemplateSummaryOut,
} from "../../../api/haus";
import type { components } from "../../../api/schema";
import { canEditHouse, HausStatusmarke, zeitpunkt } from "../../../haus/import/bausteine";
import { label } from "../../../haus/texte";
import { KatalogFehler } from "../../../katalog/bausteine";

type Staff = components["schemas"]["StaffInfo"];

/** Wie im Backend (`house/schemas.py`) und bei den Haustypen des Katalogs. */
const SLUG_PATTERN = "^[a-z][a-z0-9_]{1,59}$";

function HausKarte({ template }: { template: HouseTemplateSummaryOut }) {
  const { t, i18n } = useTranslation();
  return (
    <li className="karte p-4 flex flex-col gap-3" data-testid={`haus-${template.slug}`}>
      <div className="flex items-baseline gap-3 flex-wrap">
        <h4 className="m-0 text-lg font-medium">{template.name ? label(template.name, i18n.language) : template.slug}</h4>
        <span className="f-mono text-sm t-mute">{template.slug}</span>
        {template.current_version === null && <span className="text-sm t-mute">{t("house.list.unpublished")}</span>}
      </div>
      <ul className="m-0 p-0 list-none flex gap-2 flex-wrap" aria-label={t("house.list.versions")}>
        {template.versions.map((version) => (
          <li key={version.version}>
            <Link
              className="chip inline-flex items-center gap-2 no-underline"
              to={`/buero/katalog/hausmodell/${template.slug}/${version.version}`}
              title={version.ifc_file_name}
            >
              <span className="f-mono">v{version.version}</span>
              <HausStatusmarke status={version.status} />
              {template.current_version === version.version && (
                <span className="text-xs t-accent">{t("house.list.current")}</span>
              )}
              {version.importing && <span className="text-xs t-mute">{t("house.list.importing")}</span>}
              {version.status === "draft" && version.publishable === false && (
                <span className="text-xs t-warn">{t("house.list.open")}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </li>
  );
}

function Upload({ slugs, catalogReady }: { slugs: string[]; catalogReady: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const upload = useUploadHouseIfc();
  const [slug, setSlug] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    upload.mutate(
      { slug, file },
      { onSuccess: (version) => navigate(`/buero/katalog/hausmodell/${version.slug}/${version.version}`) },
    );
  };

  return (
    <section aria-labelledby="haus-upload" className="karte p-4 flex flex-col gap-4">
      <h3 id="haus-upload" className="m-0 text-lg font-medium">
        {t("house.upload.title")}
      </h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("house.upload.intro")}</p>
      {!catalogReady && <p className="m-0 text-sm t-warn">{t("house.upload.catalogMissing")}</p>}
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-2 items-start">
        <label className="flex flex-col gap-1 text-sm">
          {t("house.upload.slug")}
          <input
            className="field f-mono"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            pattern={SLUG_PATTERN}
            maxLength={60}
            list="haus-slugs"
            required
            aria-describedby="haus-slug-hint"
          />
          <datalist id="haus-slugs">
            {slugs.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <span id="haus-slug-hint" className="text-xs t-mute">
            {t("house.upload.slugHint")}
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("house.upload.file")}
          <input
            className="field"
            type="file"
            accept=".ifc"
            required
            aria-describedby="haus-file-hint"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <span id="haus-file-hint" className="text-xs t-mute">
            {t("house.upload.fileHint")}
          </span>
        </label>
        <div className="md:col-span-2">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={upload.isPending || !file || !slug || !catalogReady}
          >
            {upload.isPending ? t("house.upload.running") : t("house.upload.submit")}
          </button>
        </div>
      </form>
      {upload.isError && <KatalogFehler error={upload.error} />}
    </section>
  );
}

function Katalogversionen({ versions }: { versions: HouseCatalogVersionOut[] }) {
  const { t, i18n } = useTranslation();
  return (
    <section aria-labelledby="haus-kataloge" className="flex flex-col gap-3">
      <h3 id="haus-kataloge" className="m-0 text-lg font-medium">
        {t("house.catalogs.title")}
      </h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("house.catalogs.intro")}</p>
      {versions.length === 0 ? (
        <p className="m-0 text-sm t-warn">{t("house.catalogs.none")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("house.catalogs.version")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("house.catalogs.status")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("house.catalogs.contents")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("house.catalogs.source")}</th>
                <th scope="col" className="py-2 font-medium">{t("house.catalogs.published")}</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.version} className="border-b bd align-top" data-testid={`katalog-${version.version}`}>
                  <td className="py-2 pr-3">
                    <span className="f-mono">v{version.version}</span>
                    {version.current && <span className="t-accent"> · {t("house.catalogs.current")}</span>}
                  </td>
                  <td className="py-2 pr-3">{t(`house.catalogStatus.${version.status}`)}</td>
                  <td className="py-2 pr-3">
                    {t("house.catalogs.counts", {
                      roomTypes: version.room_types,
                      slots: version.slots,
                      values: version.option_values,
                    })}
                  </td>
                  <td className="py-2 pr-3">
                    <span className="break-all">{version.source}</span>
                    <div className="f-mono text-xs t-mute">{version.sha256.slice(0, 12)}</div>
                  </td>
                  <td className="py-2">
                    {version.published_at ? zeitpunkt(version.published_at, i18n.language) : "–"}
                    {version.published_by && <div className="text-xs t-mute">{version.published_by}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Hausmodell() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  const templates = useHouseTemplates();
  const catalogs = useHouseCatalogs();
  return (
    <div className="flex flex-col gap-8">
      <p className="m-0 t-mute max-w-prose">{t("house.intro")}</p>
      {templates.isPending && <p className="t-mute">{t("loading")}</p>}
      {templates.isError && <KatalogFehler error={templates.error} />}
      {templates.data && (
        <section aria-labelledby="haus-typen" className="flex flex-col gap-4">
          <h3 id="haus-typen" className="m-0 text-lg font-medium">
            {t("house.list.title")}
          </h3>
          {templates.data.length === 0 && <p className="m-0 t-mute">{t("house.list.empty")}</p>}
          <ul className="m-0 p-0 list-none flex flex-col gap-4">
            {templates.data.map((template) => (
              <HausKarte key={template.slug} template={template} />
            ))}
          </ul>
        </section>
      )}
      {!canEditHouse(staff) && <p className="m-0 text-sm t-mute">{t("house.readOnly")}</p>}
      {canEditHouse(staff) && templates.data && catalogs.data && (
        <Upload
          slugs={templates.data.map((template) => template.slug)}
          catalogReady={catalogs.data.some((version) => version.current)}
        />
      )}
      {catalogs.isError && <KatalogFehler error={catalogs.error} />}
      {catalogs.data && <Katalogversionen versions={catalogs.data} />}
    </div>
  );
}
