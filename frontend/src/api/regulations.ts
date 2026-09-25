/** Hochgeladenes règlement écrit (AN2, docs/PLAN_AN2_PLU.md): Dokument, Kapitel, Zonenwahl, Stand der Auswertung. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type ProjectRegulationOut = components["schemas"]["ProjectRegulationOut"];
export type RegulationDocumentOut = components["schemas"]["RegulationDocumentOut"];
export type DocumentChapterOut = components["schemas"]["DocumentChapterOut"];
export type ZoneChoiceIn = components["schemas"]["ZoneChoiceIn"];
export type UploadDuType = "PLU" | "PLUi" | "PSMV";

export const regulationsKey = (projectId: string) => ["regulations", projectId] as const;

/** Das Kapitel der gewählten Zone (oder `undefined`, solange keine gewählt ist). */
export function chosenChapter(regulation: ProjectRegulationOut): DocumentChapterOut | undefined {
  return regulation.document.chapters.find((chapter) => chapter.code === regulation.chapter_code);
}

/** Fragt nach, solange das Dokument gelesen oder das gewählte Kapitel ausgewertet wird (höchstens rund 20 Minuten). */
function refetchWhileWorking(data: ProjectRegulationOut[] | undefined, updates: number): number | false {
  const working = data?.some((regulation) => {
    const status = chosenChapter(regulation)?.status;
    return regulation.document.status === "importing" || status === "pending" || status === "extracting";
  });
  return working && updates < 240 ? 5_000 : false;
}

export function useProjectRegulations(projectId: string) {
  return useQuery({
    queryKey: regulationsKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/regulations", { params: { path: { project_id: projectId } } })),
    refetchInterval: (query) => refetchWhileWorking(query.state.data, query.state.dataUpdateCount),
  });
}

/** Regeln und Baurahmen hängen am Dokument: nach jeder Änderung neu laden. */
function useRefreshDerived(projectId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: regulationsKey(projectId) });
    void client.invalidateQueries({ queryKey: ["admin", "project-rules", projectId] });
    void client.invalidateQueries({ queryKey: ["admin", "envelope", projectId] });
  };
}

/** Regeln und Baurahmen neu laden, sobald sich der Stand von Dokument oder Kapitel ändert – deren eigenes
 *  Nachfragen endet nach zehn Minuten, eine Auswertung kann länger dauern. */
export function useRefreshWhenStateChanges(projectId: string, regulation: ProjectRegulationOut | undefined) {
  const client = useQueryClient();
  const state = regulation ? `${regulation.document.status}:${chosenChapter(regulation)?.status ?? ""}` : "";
  const previous = useRef(state);
  useEffect(() => {
    if (previous.current === state) return;
    previous.current = state;
    void client.invalidateQueries({ queryKey: ["admin", "project-rules", projectId] });
    void client.invalidateQueries({ queryKey: ["admin", "envelope", projectId] });
  }, [client, projectId, state]);
}

/** PDF hochladen. Das Lesen läuft im Hintergrund; es kostet nichts. */
export function useUploadRegulation(projectId: string) {
  const refresh = useRefreshDerived(projectId);
  return useMutation({
    mutationFn: async ({ file, title, duType }: { file: File; title: string; duType: UploadDuType }) => {
      const form = new FormData();
      form.append("file", file);
      if (title.trim()) form.append("title", title.trim());
      form.append("du_type", duType);
      return unwrap(
        await api.POST("/api/v1/projects/{project_id}/regulations", {
          params: { path: { project_id: projectId } },
          // Der Serialisierer ersetzt den Rumpf; der Platzhalter erfüllt nur die Typen des Schemas
          body: { file: "", du_type: duType },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: refresh,
  });
}

/** Zone wählen – plant die (bezahlte) Auswertung des Kapitels ein, wenn sich seine Eingabe ändert. */
export function useChooseZone(projectId: string, documentId: string) {
  const refresh = useRefreshDerived(projectId);
  return useMutation({
    mutationFn: async (body: ZoneChoiceIn) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/regulations/{document_id}/zone", {
          params: { path: { project_id: projectId, document_id: documentId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

/** Dokument vom Projekt lösen; das Dokument bleibt für andere Projekte bestehen. */
export function useRemoveRegulation(projectId: string) {
  const refresh = useRefreshDerived(projectId);
  return useMutation({
    mutationFn: async (documentId: string) => {
      const result = await api.DELETE("/api/v1/projects/{project_id}/regulations/{document_id}", {
        params: { path: { project_id: projectId, document_id: documentId } },
      });
      if (!result.response.ok) unwrap(result);
    },
    onSuccess: refresh,
  });
}
