/** Kundenweg des Hausmodells (docs/PLAN_HAUSMODELL.md 3.7–3.10, HM4): Haustypen, Konfiguration, Lage. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import { problemOf } from "./configuration";
import type { components } from "./schema";

export const HOUSE_MODEL_FLAG = "house_model";

async function fetchTemplates(projectId: string) {
  return unwrap(await api.GET("/api/v1/projects/{project_id}/house/templates", { params: { path: { project_id: projectId } } }));
}

async function fetchConfiguration(projectId: string) {
  return unwrap(await api.GET("/api/v1/projects/{project_id}/house/configuration", { params: { path: { project_id: projectId } } }));
}

async function fetchDocuments(projectId: string) {
  return unwrap(
    await api.GET("/api/v1/projects/{project_id}/house/configuration/documents", { params: { path: { project_id: projectId } } }),
  );
}

// Typen aus den Antworten, nicht aus `components` (README: openapi-fetch und Tupel)
export type HouseTemplatesOut = Awaited<ReturnType<typeof fetchTemplates>>;
export type HouseTemplateFitOut = HouseTemplatesOut["templates"][number];
export type HouseConfigurationOut = Awaited<ReturnType<typeof fetchConfiguration>>;
export type HouseDocumentsOut = Awaited<ReturnType<typeof fetchDocuments>>;
export type HouseSiteResultOut = HouseConfigurationOut["site_results"][number];
export type HousePriceOut = NonNullable<HouseConfigurationOut["price"]>;
export type HouseSelection = HouseConfigurationOut["configuration"];
export type HouseConfigurationPatch = components["schemas"]["HouseConfigurationPatch"];

const houseKey = (projectId: string) => ["house", projectId] as const;
const templatesKey = (projectId: string) => [...houseKey(projectId), "templates"] as const;
const configurationKey = (projectId: string) => [...houseKey(projectId), "configuration"] as const;
const documentsKey = (projectId: string, pinned: string) => [...houseKey(projectId), "documents", pinned] as const;
const areaKey = (projectId: string, revision: number) => [...houseKey(projectId), "area", revision] as const;

export function useHouseTemplates(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: templatesKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: () => fetchTemplates(projectId!),
  });
}

export function useHouseConfiguration(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: configurationKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: () => fetchConfiguration(projectId!),
  });
}

/** Festgehaltene Dokumente für den Kern im Browser; sie ändern sich nur mit Haustyp oder Versionen. */
export function useHouseDocuments(projectId: string, configuration: HouseConfigurationOut | null) {
  const template = configuration?.template;
  const pinned = template ? `${template.slug}:${template.version}:${template.catalog_version}` : "";
  return useQuery({
    queryKey: documentsKey(projectId, pinned),
    enabled: Boolean(template),
    staleTime: Infinity,
    queryFn: () => fetchDocuments(projectId),
  });
}

/** Fläche zulässiger Ursprünge für die gespeicherte Auswahl; sie hängt von Profil und Grenzschaltern ab. */
export function useHousePlacementArea(projectId: string, configuration: HouseConfigurationOut | null) {
  return useQuery({
    queryKey: areaKey(projectId, configuration?.revision ?? 0),
    enabled: Boolean(configuration?.template),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/projects/{project_id}/house/configuration/placement-area", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useHousePresets(projectId: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/house/configuration/placement-presets", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

/** Ändert Haustyp, Auswahl, Lage oder Grenzschalter; `revision` geht als `If-Match` mit (Spez. 6.1). */
export function usePatchHouseConfiguration(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ body, revision }: { body: HouseConfigurationPatch; revision: number }) =>
      unwrap(
        await api.PATCH("/api/v1/projects/{project_id}/house/configuration", {
          params: { path: { project_id: projectId }, header: { "if-match": String(revision) } },
          body,
        }),
      ),
    onSuccess: (data) => {
      client.setQueryData(configurationKey(projectId), data);
    },
    onError: (error) => {
      // Veralteter Stand: neu laden, damit der nächste Versuch die aktuelle Revision kennt
      if (problemOf(error)?.code === "revision_conflict") void client.invalidateQueries({ queryKey: configurationKey(projectId) });
    },
  });
}
