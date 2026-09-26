/** Analyse für den Entwurf (AN3, docs/PLAN_AN3_ANALYSE.md): bindende Grundfläche, Vollgeschosse, Nutzfläche
 *  als Spanne mit Annahmen je Projekt und der Vergleich der Zusatzdokumente mit dem PLU. */

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
