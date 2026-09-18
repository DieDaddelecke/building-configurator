/** Betroffenenrechte (Spez. 10.2, Plan A 3.9): Export als JSON-Download, Löschung vor einer Anfrage. */

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { useDeleteProject, useExportProject } from "../api/inquiry";

function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function DatenschutzAktionen({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const exportProject = useExportProject(projectId);
  const deleteProject = useDeleteProject(projectId);

  return (
    <details className="text-sm">
      <summary className="cursor-pointer t-mute">{t("inquiry.privacy.summary")}</summary>
      <div className="flex flex-col gap-3 pt-3">
        <button
          type="button"
          className="btn btn-ghost self-start"
          disabled={exportProject.isPending}
          onClick={() => exportProject.mutate(undefined, { onSuccess: (data) => downloadJson(data, `emprise-${projectId}.json`) })}
        >
          {t("inquiry.privacy.export")}
        </button>
        <button
          type="button"
          className="btn btn-ghost self-start"
          disabled={deleteProject.isPending}
          onClick={() => {
            if (!window.confirm(t("inquiry.privacy.deleteConfirm"))) return;
            deleteProject.mutate(undefined, { onSuccess: () => navigate("/") });
          }}
        >
          {t("inquiry.privacy.delete")}
        </button>
        {deleteProject.isError && (
          <p role="alert" className="t-alert m-0">
            {deleteProject.error instanceof ApiError
              ? (deleteProject.error.problem.detail ?? deleteProject.error.problem.title)
              : t("error.generic")}
          </p>
        )}
      </div>
    </details>
  );
}
