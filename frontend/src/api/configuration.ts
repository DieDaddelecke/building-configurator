/** Konfigurator (Modul H2, Plan H2 4.3): Typen mit Zulässigkeit, Konfiguration, Lage. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, unwrap, type Problem } from "./client";
import type { components } from "./schema";

export type ConfigurationOut = components["schemas"]["ConfigurationOut"];
export type ConfigurationPatch = components["schemas"]["ConfigurationPatch"];
export type TypesOut = components["schemas"]["TypesOut"];
export type TypeFitOut = components["schemas"]["TypeFitOut"];
export type TypeFactsOut = components["schemas"]["TypeFactsOut"];
export type CheckOut = components["schemas"]["CheckOut"];
export type EdgeMeasureOut = components["schemas"]["EdgeMeasureOut"];
export type PlacementOut = components["schemas"]["PlacementOut"];
export type PlacementAreaOut = components["schemas"]["PlacementAreaOut"];
export type PresetsOut = components["schemas"]["PresetsOut"];
export type PresetName = keyof PresetsOut["presets"];

export const CONFIGURATOR_FLAG = "configurator";

/** Fehler des Servers mit den Angaben, die die Oberfläche braucht (Spez. 6.1). */
export type ConfigurationProblem = Problem & {
  checks?: CheckOut[];
  reasons?: CheckOut[];
  edges?: EdgeMeasureOut[];
  allowed?: number[];
  current_revision?: number;
};

export function problemOf(error: unknown): ConfigurationProblem | null {
  return error instanceof ApiError ? (error.problem as ConfigurationProblem) : null;
}

const typesKey = (projectId: string) => ["configuration", projectId, "types"] as const;
const configurationKey = (projectId: string) => ["configuration", projectId, "current"] as const;
const areaKey = (projectId: string, slug: string, options: string) =>
  ["configuration", projectId, "area", slug, options] as const;

export function useTypes(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: typesKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/catalog/types", { params: { path: { project_id: projectId! } } })),
  });
}

export function useConfiguration(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: configurationKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/configuration", { params: { path: { project_id: projectId! } } })),
  });
}

export function usePlacementArea(
  projectId: string,
  slug: string | null | undefined,
  boundaryOptions: Record<string, boolean>,
) {
  return useQuery({
    queryKey: areaKey(projectId, slug ?? "", JSON.stringify(boundaryOptions)),
    enabled: Boolean(slug),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/projects/{project_id}/configuration/placement-area", {
          params: { path: { project_id: projectId }, query: { type: slug! } },
        }),
      ),
  });
}

export function usePresets(projectId: string) {
  return useMutation({
    mutationFn: async (slug: string) =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/configuration/placement-presets", {
          params: { path: { project_id: projectId }, query: { type: slug } },
        }),
      ),
  });
}

/** Ändert Typ, Lage oder Grenzschalter. `revision` geht als `If-Match` mit (Spez. 6.1). */
export function usePatchConfiguration(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ body, revision }: { body: ConfigurationPatch; revision: number }) =>
      unwrap(
        await api.PATCH("/api/v1/projects/{project_id}/configuration", {
          params: { path: { project_id: projectId }, header: { "if-match": String(revision) } },
          body,
        }),
      ),
    onSuccess: (data) => {
      client.setQueryData(configurationKey(projectId), data);
      void client.invalidateQueries({ queryKey: ["configuration", projectId, "area"] });
      void client.invalidateQueries({ queryKey: typesKey(projectId) });
    },
    onError: (error) => {
      // Veralteter Stand: neu laden, damit der nächste Versuch die aktuelle Revision kennt
      if (problemOf(error)?.code === "revision_conflict") void client.invalidateQueries({ queryKey: configurationKey(projectId) });
    },
  });
}
