import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useSession } from "../api/session";
import { useCreateProject, useOwnProjects, type ArchitectProjectOut } from "../api/site";
import { Kopf } from "../components/Kopf";
import { formatNumber } from "../site/geo";
import { darfVerwalten } from "../verwaltung/Verwaltung";
import { ModellWahl } from "../verwaltung/ModellWahl";

/** Bezeichnung eines Projekts in Liste und Kopf: Name, sonst die Adresse (AN5, PLAN_AN5_AUSGABE 3.1). */
export function projektTitel(project: Pick<ArchitectProjectOut, "name" | "address_label">): string | null {
  return project.name ?? project.address_label ?? null;
}

/** Suche im Browser über Name, Adresse und Notiz; Groß- und Kleinschreibung und Akzente zählen nicht. */
export function passtZurSuche(project: ArchitectProjectOut, suche: string): boolean {
  const norm = (text: string) =>
    text
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase();
  const gesucht = norm(suche.trim());
  if (!gesucht) return true;
  return [project.name, project.address_label, project.note].some((feld) => feld && norm(feld).includes(gesucht));
}

/** Projektliste des Büros (AN1) mit Name, Archiv und Suche (AN5), darunter das KI-Modell der Auswertung
 *  (PLAN_AN2_PLU 8). */
export function Projekte() {
  const { t, i18n } = useTranslation();
  const [archiv, setArchiv] = useState(false);
  const [suche, setSuche] = useState("");
  const projects = useOwnProjects(archiv);
  const create = useCreateProject();
  const navigate = useNavigate();
  const staff = useSession().data?.staff;
  const roles = staff?.roles ?? [];
  // Das Modell wählt der Betrieb für alle; fremde Büros sehen die Einstellung nicht (AN6, 3.2)
  const betrieb = staff?.organisation?.kind === "operator";
  const sucheId = useId();
  const gezeigt = projects.data?.filter((project) => passtZurSuche(project, suche)) ?? [];

  const anlegen = () =>
    create.mutate(undefined, { onSuccess: (project) => void navigate(`/projekt/${project.id}`) });

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Kopf eyebrow={t("analyse.eyebrow")} titel={t("analyse.projects.title")}>
          <p>{t("analyse.projects.intro")}</p>
        </Kopf>
        <button type="button" className="btn btn-primary" onClick={anlegen} disabled={create.isPending}>
          {t("analyse.projects.new")}
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div role="group" aria-label={t("analyse.projects.filter")} className="flex gap-1">
          {([false, true] as const).map((value) => (
            <button
              key={String(value)}
              type="button"
              className="chip"
              aria-pressed={archiv === value}
              onClick={() => setArchiv(value)}
            >
              {t(value ? "analyse.projects.archived" : "analyse.projects.active")}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-1 min-w-0 flex-1 sm:max-w-xs">
          <label htmlFor={sucheId} className="text-sm t-mute">
            {t("analyse.projects.search")}
          </label>
          <input
            id={sucheId}
            className="field"
            type="search"
            value={suche}
            onChange={(event) => setSuche(event.target.value)}
          />
        </div>
      </div>

      {create.isError && <p className="t-alert">{t("error.generic")}</p>}
      {projects.isPending && <p className="t-mute">{t("loading")}</p>}
      {projects.isError && <p className="t-alert">{t("error.generic")}</p>}
      {projects.data?.length === 0 && (
        <p className="t-mute">{t(archiv ? "analyse.projects.emptyArchive" : "analyse.projects.empty")}</p>
      )}
      {projects.data && projects.data.length > 0 && gezeigt.length === 0 && (
        <p className="t-mute">{t("analyse.projects.noMatch")}</p>
      )}

      {gezeigt.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <caption className="sr-only">{t("analyse.projects.title")}</caption>
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-4 font-medium">{t("analyse.projects.label")}</th>
                <th scope="col" className="py-2 pr-4 font-medium">{t("analyse.projects.origin")}</th>
                <th scope="col" className="py-2 pr-4 font-medium text-right">{t("analyse.projects.area")}</th>
                <th scope="col" className="py-2 font-medium">{t("analyse.projects.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {gezeigt.map((project) => (
                <tr key={project.id} className="border-b bd align-top">
                  <td className="py-2 pr-4">
                    <Link className="link" to={`/projekt/${project.id}`}>
                      {projektTitel(project) ?? t("analyse.projects.untitled")}
                    </Link>
                    {project.name && project.address_label && (
                      <span className="block t-mute">{project.address_label}</span>
                    )}
                    {project.note && <span className="block t-mute text-xs break-words">{project.note}</span>}
                  </td>
                  <td className="py-2 pr-4 t-mute">
                    {project.site_origin ? t(`analyse.origin.${project.site_origin}`) : t("analyse.projects.noSite")}
                  </td>
                  <td className="py-2 pr-4 text-right f-mono num">
                    {project.area_m2 === null ? "–" : `${formatNumber(project.area_m2, i18n.language)} m²`}
                  </td>
                  <td className="py-2 t-mute">
                    {new Date(project.last_activity_at).toLocaleDateString(i18n.language)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {betrieb && <ModellWahl darfAendern={false} aendernUnter={darfVerwalten(roles) ? "/verwaltung" : undefined} />}
    </div>
  );
}
