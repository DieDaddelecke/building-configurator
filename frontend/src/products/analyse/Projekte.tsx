import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useSession } from "../../api/session";
import { useCreateProject, useOwnProjects } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { formatNumber } from "../../site/geo";

/** Projektliste des Büros (AN1), darunter das KI-Modell der Auswertung (PLAN_AN2_PLU 8). Benennung, Notiz und
 *  Archiv folgen mit AN5. */
export function Projekte() {
  const { t, i18n } = useTranslation();
  const projects = useOwnProjects();
  const create = useCreateProject();
  const navigate = useNavigate();
  const roles = useSession().data?.staff?.roles ?? [];

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

      {create.isError && <p className="t-alert">{t("error.generic")}</p>}
      {projects.isPending && <p className="t-mute">{t("loading")}</p>}
      {projects.isError && <p className="t-alert">{t("error.generic")}</p>}
      {projects.data?.length === 0 && <p className="t-mute">{t("analyse.projects.empty")}</p>}

      {projects.data && projects.data.length > 0 && (
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
              {projects.data.map((project) => (
                <tr key={project.id} className="border-b bd">
                  <td className="py-2 pr-4">
                    <Link className="link" to={`/projekt/${project.id}`}>
                      {project.address_label ?? t("analyse.projects.untitled")}
                    </Link>
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
    </div>
  );
}
