/** Hochgeladenes règlement écrit (AN2, docs/PLAN_AN2_PLU.md): Dokument, Kapitel, Zonenwahl, Stand der Auswertung. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { api, unwrap } from "./client";
import type { components, paths } from "./schema";

export type ProjectRegulationOut = components["schemas"]["ProjectRegulationOut"];
export type RegulationDocumentOut = components["schemas"]["RegulationDocumentOut"];
export type DocumentChapterOut = components["schemas"]["DocumentChapterOut"];
export type OcrOut = components["schemas"]["OcrOut"];
export type ZoneChoiceIn = components["schemas"]["ZoneChoiceIn"];
export type LotChoiceIn = components["schemas"]["LotChoiceIn"];
/** Dokumentarten, die der Upload annimmt (Formular von `POST …/regulations`). */
export type UploadDuType = NonNullable<
  paths["/api/v1/projects/{project_id}/regulations"]["post"]["requestBody"]
>["content"]["multipart/form-data"]["du_type"];
export type SupplementDuType = Extract<UploadDuType, "lotissement" | "cahier_des_charges">;
export type PluDuType = Exclude<UploadDuType, SupplementDuType>;

/** Höchstens so viele Zusatzdokumente je Projekt (AN3, E-AN3-6; `documents.MAX_SUPPLEMENTS`). */
export const MAX_SUPPLEMENTS = 3;

export const regulationsKey = (projectId: string) => ["regulations", projectId] as const;

/** Das PLU des Projekts: Grundlage von Regeln, Baurahmen und Analyse. */
export function pluOf(regulations: ProjectRegulationOut[] | undefined): ProjectRegulationOut | undefined {
  return regulations?.find((regulation) => regulation.role === "plu");
}

/** Zusatzdokumente (lotissement, cahier des charges), nur im Vergleich der Analyse (AN3). */
export function supplementsOf(regulations: ProjectRegulationOut[] | undefined): ProjectRegulationOut[] {
  return regulations?.filter((regulation) => regulation.role === "supplement") ?? [];
}

/** Das Kapitel der gewählten Zone (oder `undefined`, solange keine gewählt ist). */
export function chosenChapter(regulation: ProjectRegulationOut): DocumentChapterOut | undefined {
  return regulation.document.chapters.find((chapter) => chapter.code === regulation.chapter_code);
}

/** Fragt nach, solange das Dokument gelesen oder das gewählte Kapitel ausgewertet wird (höchstens rund 20 Minuten),
 *  bei einer Texterkennung höchstens eine Stunde (AN7: etwa 3 s je Seite, ein Scan mit 1 000 Seiten dauert lange). */
function refetchWhileWorking(data: ProjectRegulationOut[] | undefined, updates: number): number | false {
  const recognizing = data?.some((regulation) => regulation.document.ocr?.state === "running");
  const working = data?.some((regulation) => {
    const status = chosenChapter(regulation)?.status;
    return regulation.document.status === "importing" || status === "pending" || status === "extracting";
  });
  return (recognizing && updates < 720) || (working && updates < 240) ? 5_000 : false;
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
    void client.invalidateQueries({ queryKey: ["analysis", projectId] });
  };
}

/** Regeln, Baurahmen und Analyse neu laden, sobald sich der Stand eines Dokuments oder Kapitels ändert – deren
 *  eigenes Nachfragen endet nach zehn Minuten, eine Auswertung kann länger dauern. Gilt für PLU und
 *  Zusatzdokumente (AN3). */
export function useRefreshWhenStateChanges(projectId: string, regulations: ProjectRegulationOut[] | undefined) {
  const client = useQueryClient();
  const state = (regulations ?? [])
    .map(
      (regulation) =>
        `${regulation.document.id}:${regulation.document.status}:${regulation.document.ocr?.state ?? ""}:${chosenChapter(regulation)?.status ?? ""}`,
    )
    .join("|");
  const previous = useRef(state);
  useEffect(() => {
    if (previous.current === state) return;
    previous.current = state;
    void client.invalidateQueries({ queryKey: ["admin", "project-rules", projectId] });
    void client.invalidateQueries({ queryKey: ["admin", "envelope", projectId] });
    void client.invalidateQueries({ queryKey: ["analysis", projectId] });
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

/** Lot eines Zusatzdokuments wählen (AN3) – plant wie die Zonenwahl eine (bezahlte) Auswertung ein. */
export function useChooseLot(projectId: string, documentId: string) {
  const refresh = useRefreshDerived(projectId);
  return useMutation({
    mutationFn: async (body: LotChoiceIn) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/regulations/{document_id}/lot", {
          params: { path: { project_id: projectId, document_id: documentId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

/** Text der Seiten ohne Textschicht erkennen lassen (AN7, docs/PLAN_AN7_SCAN.md 3.2): nach dem Hinweis bei einem
 *  Scan oder für einzelne leere Seiten. Kostet nichts, dauert etwa 3 s je Seite; läuft im Hintergrund in Teilen. */
export function useRequestOcr(projectId: string, documentId: string) {
  const refresh = useRefreshDerived(projectId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/regulations/{document_id}/ocr", {
          params: { path: { project_id: projectId, document_id: documentId } },
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
