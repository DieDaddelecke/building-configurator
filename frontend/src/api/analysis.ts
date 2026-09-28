/** Analyse für den Entwurf (AN3, docs/PLAN_AN3_ANALYSE.md, PLAN_AN3_GABARIT.md): bindende Grundfläche,
 *  Vollgeschosse, Nutzfläche als Spanne mit Annahmen je Projekt, Gabarit und Schnitte, der Vergleich der
 *  Zusatzdokumente mit dem PLU. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type AnalysisOut = components["schemas"]["AnalysisOut"];
export type AnalysisPartOut = components["schemas"]["AnalysisPartOut"];
export type AnalysisFootprintOut = components["schemas"]["AnalysisFootprintOut"];
export type AnalysisStoreysOut = components["schemas"]["AnalysisStoreysOut"];
export type AnalysisParametersIn = components["schemas"]["AnalysisParametersIn"];
export type AnalysisParametersOut = components["schemas"]["AnalysisParametersOut"];
export type SupplementAnalysisOut = components["schemas"]["SupplementAnalysisOut"];
export type GabaritOut = components["schemas"]["GabaritOut"];
export type GabaritLevelOut = components["schemas"]["GabaritLevelOut"];
export type SectionOut = components["schemas"]["SectionOut"];
export type StoreyAreaOut = components["schemas"]["StoreyAreaOut"];
export type RuleComparisonOut = components["schemas"]["RuleComparisonOut"];

export const analysisKey = (projectId: string) => ["analysis", projectId] as const;

export function useAnalysis(projectId: string) {
  return useQuery({
    queryKey: analysisKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/analysis", { params: { path: { project_id: projectId } } })),
  });
}

/** Annahmen ändern; die Antwort ist die neu gerechnete Analyse. */
export function useSaveAnalysisParameters(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: AnalysisParametersIn) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/analysis/parameters", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: (data) => client.setQueryData(analysisKey(projectId), data),
  });
}

/** Zurück auf die Vorgaben. */
export function useResetAnalysisParameters(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/v1/projects/{project_id}/analysis/parameters", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: (data) => client.setQueryData(analysisKey(projectId), data),
  });
}

export type AnalysisComparisonOut = components["schemas"]["AnalysisComparisonOut"];
export type ComparisonBaseOut = components["schemas"]["ComparisonBaseOut"];

/** Zwei Stände nebeneinander (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5); `base` `automatic` oder eine Versions-ID. Erst
 *  rechnen, wenn der Architekt den Vergleich öffnet (`base` gesetzt). */
export function useAnalysisComparison(projectId: string, base: string | null) {
  return useQuery({
    queryKey: [...analysisKey(projectId), "comparison", base ?? ""],
    enabled: base !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/projects/{project_id}/analysis/comparison", {
          params: { path: { project_id: projectId }, query: { base: base ?? "automatic" } },
        }),
      ),
  });
}
