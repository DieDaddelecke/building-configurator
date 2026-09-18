/** Hauskatalog (Modul H1, docs/PLAN_H1_HAUSKATALOG.md): Katalogpflege im Büro. Kein Kundenschritt, kein Flag. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type TypeSummaryOut = components["schemas"]["TypeSummaryOut"];
export type TypeVersionOut = components["schemas"]["TypeVersionOut"];
export type TypeVersionRefOut = components["schemas"]["TypeVersionRefOut"];
export type VersionStatus = TypeVersionOut["status"];
export type FacadeRolesIn = components["schemas"]["FacadeRolesIn"];
export type PlacementIn = components["schemas"]["PlacementIn"];
export type PackageVersionOut = components["schemas"]["PackageVersionOut"];
export type PackageIn = components["schemas"]["PackageIn"];
export type ModuleVersionOut = components["schemas"]["ModuleVersionOut"];
export type ModuleIn = components["schemas"]["ModuleIn"];
export type PriceCatalogVersionOut = components["schemas"]["PriceCatalogVersionOut"];
export type EnergyAssessmentIn = components["schemas"]["EnergyAssessmentIn"];
export type EnergyAssessmentOut = components["schemas"]["EnergyAssessmentOut"];

const catalogKey = ["admin", "catalog"] as const;
const typesKey = [...catalogKey, "types"] as const;
const typeVersionKey = (slug: string, version: number) => [...catalogKey, "type", slug, version] as const;
const linesKey = [...catalogKey, "lines"] as const;
const optionsKey = [...catalogKey, "options"] as const;
const priceKey = [...catalogKey, "price-catalog"] as const;

export function useCatalogTypes() {
  return useQuery({
    queryKey: typesKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/catalog/types")),
  });
}

export function useTypeVersion(slug: string, version: number) {
  return useQuery({
    queryKey: typeVersionKey(slug, version),
    enabled: Number.isInteger(version),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/catalog/types/{slug}/versions/{version}", {
          params: { path: { slug, version } },
        }),
      ),
  });
}

/** Nach jeder Änderung an einem Typstand: Version im Cache ersetzen, Liste und Preise neu laden. */
function useTypeVersionMutation<TInput>(
  slug: string,
  version: number,
  run: (input: TInput) => Promise<TypeVersionOut>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (updated) => {
      client.setQueryData(typeVersionKey(slug, version), updated);
      void client.invalidateQueries({ queryKey: typesKey });
    },
  });
}

export function useSetFacadeRoles(slug: string, version: number) {
  return useTypeVersionMutation(slug, version, async (roles: FacadeRolesIn["roles"]) =>
    unwrap(
      await api.PUT("/api/v1/admin/catalog/types/{slug}/versions/{version}/facade-roles", {
        params: { path: { slug, version } },
        body: { roles },
      }),
    ),
  );
}

export function useSetPlacement(slug: string, version: number) {
  return useTypeVersionMutation(slug, version, async (body: PlacementIn) =>
    unwrap(
      await api.PUT("/api/v1/admin/catalog/types/{slug}/versions/{version}/placement", {
        params: { path: { slug, version } },
        body,
      }),
    ),
  );
}

export function usePublishType(slug: string, version: number) {
  return useTypeVersionMutation<void>(slug, version, async () =>
    unwrap(
      await api.POST("/api/v1/admin/catalog/types/{slug}/versions/{version}/publish", {
        params: { path: { slug, version } },
      }),
    ),
  );
}

export function useRetireType(slug: string, version: number) {
  return useTypeVersionMutation<void>(slug, version, async () =>
    unwrap(
      await api.POST("/api/v1/admin/catalog/types/{slug}/versions/{version}/retire", {
        params: { path: { slug, version } },
      }),
    ),
  );
}

export function useImportTypeVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, xlsx, dxf }: { slug: string; xlsx: File; dxf: File }) => {
      const form = new FormData();
      form.append("xlsx", xlsx);
      form.append("dxf", dxf);
      return unwrap(
        await api.POST("/api/v1/admin/catalog/types/{slug}/versions", {
          params: { path: { slug } },
          // Der Serialisierer ersetzt den Rumpf; die Platzhalter erfüllen nur die Typen des Schemas
          body: { xlsx: "", dxf: "" },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: typesKey });
      void client.invalidateQueries({ queryKey: priceKey });
    },
  });
}

export function useUploadPlanDocument(slug: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return unwrap(
        await api.POST("/api/v1/admin/catalog/types/{slug}/plan-document", {
          params: { path: { slug } },
          body: { file: "" },
          bodySerializer: () => form,
        }),
      );
    },
  });
}

// ---------------------------------------------------------------------------
// Linien und Optionen
// ---------------------------------------------------------------------------

export function usePackages() {
  return useQuery({
    queryKey: linesKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/catalog/lines")),
  });
}

export function useCreatePackageVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, body }: { slug: string; body: PackageIn }) =>
      unwrap(
        await api.POST("/api/v1/admin/catalog/lines/{slug}/versions", { params: { path: { slug } }, body }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: linesKey }),
  });
}

export function usePublishPackage() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, version }: { slug: string; version: number }) =>
      unwrap(
        await api.POST("/api/v1/admin/catalog/lines/{slug}/versions/{version}/publish", {
          params: { path: { slug, version } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: linesKey }),
  });
}

export function useModules() {
  return useQuery({
    queryKey: optionsKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/catalog/options")),
  });
}

export function useCreateModuleVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, body }: { slug: string; body: ModuleIn }) =>
      unwrap(
        await api.POST("/api/v1/admin/catalog/options/{slug}/versions", { params: { path: { slug } }, body }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: optionsKey }),
  });
}

export function usePublishModule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slug, version }: { slug: string; version: number }) =>
      unwrap(
        await api.POST("/api/v1/admin/catalog/options/{slug}/versions/{version}/publish", {
          params: { path: { slug, version } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: optionsKey }),
  });
}

// ---------------------------------------------------------------------------
// Preiskatalog und RE2020
// ---------------------------------------------------------------------------

export function useDraftPriceCatalog() {
  return useQuery({
    queryKey: priceKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/catalog/price-catalog/draft")),
  });
}

export function usePublishPriceCatalog() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/admin/catalog/price-catalog/publish")),
    onSuccess: () => client.invalidateQueries({ queryKey: priceKey }),
  });
}

export function useSetEnergyAssessment(typeSlug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ packageSlug, body }: { packageSlug: string; body: EnergyAssessmentIn }) =>
      unwrap(
        await api.PUT("/api/v1/admin/catalog/types/{type_slug}/energy-assessment/{package_slug}", {
          params: { path: { type_slug: typeSlug, package_slug: packageSlug } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: priceKey }),
  });
}
