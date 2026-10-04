/** Hausmodell im Büro (docs/PLAN_HAUSMODELL.md 3.6, HM3): Haustypen aus IFC, Entwurf, Prüfung und Freigabe. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";

async function fetchTemplates() {
  return unwrap(await api.GET("/api/v1/admin/house/templates"));
}

async function fetchCatalogs() {
  return unwrap(await api.GET("/api/v1/admin/house/catalogs"));
}

async function fetchVersion(slug: string, version: number) {
  return unwrap(
    await api.GET("/api/v1/admin/house/templates/{slug}/versions/{version}", {
      params: { path: { slug, version } },
    }),
  );
}

// Typen aus den Antworten, nicht aus `components`: openapi-fetch liefert Tupel (Wandachse) als Arrays
export type HouseTemplateSummaryOut = Awaited<ReturnType<typeof fetchTemplates>>[number];
export type HouseCatalogVersionOut = Awaited<ReturnType<typeof fetchCatalogs>>[number];
export type HouseTemplateVersionOut = Awaited<ReturnType<typeof fetchVersion>>;
export type HouseTemplateStatus = HouseTemplateVersionOut["status"];
export type HouseDraftDecisions = HouseTemplateVersionOut["decisions"];
export type HouseCatalogChoicesOut = HouseTemplateVersionOut["catalog"];
export type HouseImportReport = NonNullable<HouseTemplateVersionOut["report"]>;
export type HouseImportFinding = HouseImportReport["findings"][number];
export type HouseTemplate = NonNullable<HouseTemplateVersionOut["template"]>;
export type HouseText = HouseTemplate["name"];
export type FacadeRole = NonNullable<HouseTemplate["envelope"][number]["segments"][number]["facade_role"]>;

const houseKey = ["admin", "house"] as const;
const templatesKey = [...houseKey, "templates"] as const;
const catalogsKey = [...houseKey, "catalogs"] as const;
const versionKey = (slug: string, version: number) => [...houseKey, "version", slug, version] as const;

/** Der Job liest die Datei noch: Entwurf und Bericht fehlen, die Seite fragt nach. */
export const importing = (version: HouseTemplateVersionOut) =>
  version.status === "draft" && version.report === null && version.job?.status !== "failed";

export const IMPORT_POLL_MS = 2000;

export function useHouseTemplates() {
  return useQuery({ queryKey: templatesKey, queryFn: fetchTemplates });
}

export function useHouseCatalogs() {
  return useQuery({ queryKey: catalogsKey, queryFn: fetchCatalogs });
}

export function useHouseVersion(slug: string, version: number) {
  return useQuery({
    queryKey: versionKey(slug, version),
    enabled: Number.isInteger(version) && version >= 1,
    queryFn: () => fetchVersion(slug, version),
    refetchInterval: (query) => (query.state.data && importing(query.state.data) ? IMPORT_POLL_MS : false),
  });
}

export function useUploadHouseIfc() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, file }: { slug: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      return unwrap(
        await api.POST("/api/v1/admin/house/templates/{slug}/versions", {
          params: { path: { slug } },
          // Der Serialisierer ersetzt den Rumpf; der Platzhalter erfüllt nur die Typen des Schemas
          body: { file: "" },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: (version) => {
      client.setQueryData(versionKey(version.slug, version.version), version);
      void client.invalidateQueries({ queryKey: templatesKey });
    },
  });
}

/** Nach jeder Änderung an einer Version: Version im Cache ersetzen, Liste neu laden. Nach einem Fehler die
 * Version neu laden: Die Prüfung legt den Entwurf auch bei offenen Punkten neu an, oder jemand anderes war schneller. */
function useVersionMutation<TInput>(
  slug: string,
  version: number,
  run: (input: TInput) => Promise<HouseTemplateVersionOut>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (updated) => {
      client.setQueryData(versionKey(slug, version), updated);
      void client.invalidateQueries({ queryKey: templatesKey });
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: versionKey(slug, version) });
    },
  });
}

export function useSaveDecisions(slug: string, version: number) {
  return useVersionMutation(slug, version, async (body: HouseDraftDecisions) =>
    unwrap(
      await api.PUT("/api/v1/admin/house/templates/{slug}/versions/{version}/decisions", {
        params: { path: { slug, version } },
        body,
      }),
    ),
  );
}

export type HouseAction = "check" | "publish" | "reject" | "retire";

export function useHouseAction(slug: string, version: number, action: HouseAction) {
  return useVersionMutation<void>(slug, version, async () => {
    const params = { params: { path: { slug, version } } };
    switch (action) {
      case "check":
        return unwrap(await api.POST("/api/v1/admin/house/templates/{slug}/versions/{version}/check", params));
      case "publish":
        return unwrap(await api.POST("/api/v1/admin/house/templates/{slug}/versions/{version}/publish", params));
      case "reject":
        return unwrap(await api.POST("/api/v1/admin/house/templates/{slug}/versions/{version}/reject", params));
      case "retire":
        return unwrap(await api.POST("/api/v1/admin/house/templates/{slug}/versions/{version}/retire", params));
    }
  });
}
