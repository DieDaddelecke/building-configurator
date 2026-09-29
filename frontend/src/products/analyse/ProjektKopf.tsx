/**
 * Kopf eines Projekts (AN5, docs/PLAN_AN5_AUSGABE.md 3.1): Name (sonst die Adresse), Notiz, bearbeiten,
 * archivieren und zurückholen, löschen. Archivieren blendet das Projekt nur in der Liste aus (E-AN5-7). Name und
 * Notiz bleiben in der Instanz; sie stehen im Bericht, gehen aber an keinen Dienst (Datenschutz, 3.1).
 */

import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { ApiError } from "../../api/client";
import { useProjectDetails, useUpdateProject, type ArchitectProjectOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { projektTitel } from "./Projekte";

const NAME_MAX = 120;
const NOTIZ_MAX = 2000;

function Bearbeiten({ project, onFertig }: { project: ArchitectProjectOut; onFertig: () => void }) {
  const { t } = useTranslation();
  const nameId = useId();
  const notizId = useId();
  const [name, setName] = useState(project.name ?? "");
  const [notiz, setNotiz] = useState(project.note ?? "");
  const speichern = useUpdateProject(project.id);

  return (
    <form
      className="karte p-5 flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        speichern.mutate({ name, note: notiz }, { onSuccess: onFertig });
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={nameId} className="text-sm font-medium t-ink">
          {t("analyse.project.name")}
        </label>
        <input
          id={nameId}
          className="field"
          value={name}
          maxLength={NAME_MAX}
          placeholder={project.address_label ?? ""}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={notizId} className="text-sm font-medium t-ink">
          {t("analyse.project.note")}
        </label>
        <textarea
          id={notizId}
          className="field"
          rows={4}
          value={notiz}
          maxLength={NOTIZ_MAX}
          onChange={(event) => setNotiz(event.target.value)}
          aria-describedby={`${notizId}-hinweis`}
        />
        <p id={`${notizId}-hinweis`} className="text-xs t-mute m-0">
          {t("analyse.project.noteHint")}
        </p>
      </div>
      {speichern.error && (
        <p role="alert" className="t-alert text-sm m-0">
          {speichern.error instanceof ApiError ? speichern.error.problem.title : t("error.generic")}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button type="submit" className="btn btn-primary" disabled={speichern.isPending}>
          {speichern.isPending ? t("loading") : t("analyse.project.save")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onFertig}>
          {t("analyse.project.cancel")}
        </button>
      </div>
    </form>
  );
}

export function ProjektKopf({
  projectId,
  adresse,
  onLoeschen,
  loeschtGerade,
}: {
  projectId: string;
  adresse: string | null | undefined;
  onLoeschen: () => void;
  loeschtGerade: boolean;
}) {
  const { t, i18n } = useTranslation();
  const details = useProjectDetails(projectId);
  const aendern = useUpdateProject(projectId);
  const [bearbeiten, setBearbeiten] = useState(false);
  const project = details.data;
  const archiviert = Boolean(project?.archived_at);
  const titel =
    (project && projektTitel({ name: project.name, address_label: adresse ?? project.address_label })) ??
    t("analyse.projects.untitled");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Kopf eyebrow={t("analyse.eyebrow")} titel={titel}>
          {project?.name && adresse && <p className="m-0">{adresse}</p>}
          {archiviert && project?.archived_at && (
            <p className="t-warn m-0" role="status">
              {t("analyse.project.archivedSince", {
                date: new Date(project.archived_at).toLocaleDateString(i18n.language),
              })}
            </p>
          )}
          <p>{t("analyse.site.intro")}</p>
        </Kopf>
        <div className="flex flex-wrap gap-3">
          <Link className="btn btn-ghost" to="/">
            {t("analyse.site.back")}
          </Link>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setBearbeiten(true)}
            disabled={!project || bearbeiten}
          >
            {t("analyse.project.edit")}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => aendern.mutate({ archived: !archiviert })}
            disabled={!project || aendern.isPending}
          >
            {t(archiviert ? "analyse.project.restore" : "analyse.project.archive")}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onLoeschen} disabled={loeschtGerade}>
            {t("analyse.site.delete")}
          </button>
        </div>
      </div>
      {aendern.isError && (
        <p role="alert" className="t-alert text-sm m-0">
          {t("error.generic")}
        </p>
      )}
      {bearbeiten && project && <Bearbeiten project={project} onFertig={() => setBearbeiten(false)} />}
      {!bearbeiten && project?.note && (
        <section aria-label={t("analyse.project.note")} className="karte px-5 py-4 text-sm whitespace-pre-line break-words">
          {project.note}
        </section>
      )}
    </div>
  );
}
