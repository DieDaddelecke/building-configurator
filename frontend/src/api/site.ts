/** Grundstück (Modul G1, Plan 3.3): Adresssuche, Kataster, Grundstück, Kantenkorrektur. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { MultiPolygon, Polygon } from "geojson";

import { api, ApiError, unwrap } from "./client";
import type { components } from "./schema";
import { sessionKey } from "./session";

export type SiteOut = components["schemas"]["SiteOut"];
export type EdgeOut = components["schemas"]["EdgeOut"];
export type EdgeKind = EdgeOut["kind"];
export type AddressOut = components["schemas"]["AddressOut"];
export type LookupOut = components["schemas"]["LookupOut"];
export type CommuneOut = components["schemas"]["CommuneOut"];
export type SiteReviewItem = components["schemas"]["SiteReviewItem"];
export type CustomerEdgeKind = "street" | "neighbour" | null;
export type ManualEdgeIn = components["schemas"]["ManualEdgeIn"];
export type TraceIn = components["schemas"]["TraceIn"];
export type ScanPreviewOut = components["schemas"]["ScanPreviewOut"];

export const SITE_FLAG = "site_selection";

export interface ParcelFeature {
  type: "Feature";
  id: string;
  geometry: MultiPolygon | Polygon;
  properties: { idu: string; section: string; number: string; commune_insee: string; area_official_m2: number | null };
}

export interface ParcelCollection {
  type: "FeatureCollection";
  truncated: boolean;
  features: ParcelFeature[];
}

export function useFlags() {
  return useQuery({
    queryKey: ["flags"],
    queryFn: async () => unwrap(await api.GET("/api/v1/flags")),
    staleTime: 60_000,
  });
}

export function useServiceArea(enabled: boolean) {
  return useQuery({
    queryKey: ["service-area"],
    queryFn: async () => unwrap(await api.GET("/api/v1/cadastre/service-area")),
    enabled,
    staleTime: 3_600_000,
  });
}

export function useGeocode(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["geocode", q.toLowerCase()],
    queryFn: async ({ signal }) => unwrap(await api.GET("/api/v1/geocode", { params: { query: { q } }, signal })),
    enabled: q.length >= 3,
    staleTime: 300_000,
    retry: false,
  });
}

/** Parzellen im Kartenausschnitt (WGS84: min_lon, min_lat, max_lon, max_lat). */
export async function fetchParcels(bbox: [number, number, number, number], signal?: AbortSignal): Promise<ParcelCollection> {
  const result = await api.GET("/api/v1/cadastre/parcels", {
    params: { query: { bbox: bbox.map((v) => v.toFixed(6)).join(",") } },
    signal,
  });
  return unwrap(result) as unknown as ParcelCollection;
}

/** Projekt des Cookies oder neu angelegt. Vor der Kontaktaufnahme ohne personenbezogene Daten. */
export function useEnsureProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (existing: string | null | undefined): Promise<string> => {
      if (existing) return existing;
      const created = unwrap(await api.POST("/api/v1/projects"));
      await client.invalidateQueries({ queryKey: sessionKey });
      return created.id;
    },
  });
}

export async function lookupParcels(
  projectId: string,
  body: { lon: number; lat: number } | { commune_insee: string; section: string; number: string },
): Promise<LookupOut> {
  return unwrap(await api.POST("/api/v1/projects/{project_id}/parcels/lookup", { params: { path: { project_id: projectId } }, body }));
}

export const siteKey = (projectId: string | null | undefined) => ["site", projectId] as const;

/** Grundstück des Projekts; `null`, solange keines gebildet ist. Fragt nach, bis Gelände und Risiken da sind. */
export function useSite(projectId: string | null | undefined) {
  return useQuery({
    queryKey: siteKey(projectId),
    enabled: Boolean(projectId),
    queryFn: async (): Promise<SiteOut | null> => {
      try {
        return unwrap(await api.GET("/api/v1/projects/{project_id}/site", { params: { path: { project_id: projectId! } } }));
      } catch (error) {
        if (error instanceof ApiError && error.problem.code === "site_not_found") return null;
        throw error;
      }
    },
    refetchInterval: (query) => {
      const site = query.state.data;
      const pending = site && (site.terrain.status === "pending" || site.risks.status === "pending");
      return pending && query.state.dataUpdateCount < 30 ? 2000 : false;
    },
  });
}

export function useFormSite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ projectId, idus }: { projectId: string; idus: string[] }) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/site", {
          params: { path: { project_id: projectId } },
          body: { parcel_idus: idus },
        }),
      ),
    onSuccess: (site) => {
      client.setQueryData(siteKey(site.project_id), site);
      // Neue Parzellen, neue Zonen: die Regeln des vorigen Grundstücks nicht kurz weiter zeigen
      client.removeQueries({ queryKey: ["rules", site.project_id] });
    },
  });
}

/** Weg E (Plan 3.3): Grundstück frei zeichnen und bemaßen, ohne Kataster und ohne Bebaubarkeitscheck. */
export function useFormManualSite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      edges,
      addressLabel,
      trace,
    }: {
      projectId: string;
      edges: ManualEdgeIn[];
      addressLabel: string;
      /** Nach einem Scan nachgezeichnet (AN7): Datei, Seite, Maßstabsweg; landet in `source_info.trace`. */
      trace?: TraceIn;
    }) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/site", {
          params: { path: { project_id: projectId } },
          body: trace ? { edges, address_label: addressLabel, trace } : { edges, address_label: addressLabel },
        }),
      ),
    onSuccess: (site) => {
      client.setQueryData(siteKey(site.project_id), site);
      client.removeQueries({ queryKey: ["rules", site.project_id] });
    },
  });
}

export function useCorrectEdgeCustomer(site: SiteOut) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ seq, kind }: { seq: number; kind: CustomerEdgeKind }) =>
      unwrap(
        await api.PATCH("/api/v1/projects/{project_id}/site/edges/{seq}", {
          params: { path: { project_id: site.project_id, seq }, header: { "if-match": `"${site.revision}"` } },
          body: { kind },
        }),
      ),
    onSuccess: (updated) => client.setQueryData(siteKey(updated.project_id), updated),
    onError: () => client.invalidateQueries({ queryKey: siteKey(site.project_id) }),
  });
}

// ---------------------------------------------------------------------------
// Büro
// ---------------------------------------------------------------------------

export function useReviewQueue(scope: "corrections" | "all" = "corrections") {
  return useQuery({
    queryKey: ["admin", "site-review", scope],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/sites/review", { params: { query: { scope } } })),
  });
}

const staffSiteKey = (projectId: string) => ["admin", "site", projectId] as const;

export function useStaffSite(projectId: string) {
  return useQuery({
    queryKey: staffSiteKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/projects/{project_id}/site", { params: { path: { project_id: projectId } } })),
  });
}

export function useCorrectEdgeArchitect(site: SiteOut) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ seq, kind }: { seq: number; kind: EdgeKind | null }) =>
      unwrap(
        await api.PATCH("/api/v1/admin/projects/{project_id}/site/edges/{seq}", {
          params: { path: { project_id: site.project_id, seq }, header: { "if-match": `"${site.revision}"` } },
          body: { kind },
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(staffSiteKey(updated.project_id), updated);
      void client.invalidateQueries({ queryKey: ["admin", "site-review"] });
    },
    onError: () => client.invalidateQueries({ queryKey: staffSiteKey(site.project_id) }),
  });
}

export function useConfirmCustomerEdges(site: SiteOut) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/admin/projects/{project_id}/site/edges/confirm", {
          params: { path: { project_id: site.project_id }, header: { "if-match": `"${site.revision}"` } },
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(staffSiteKey(updated.project_id), updated);
      void client.invalidateQueries({ queryKey: ["admin", "site-review"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Emprise Analyse (AN1): Projekte am Architektenkonto, Parzelle aus einer Datei
// ---------------------------------------------------------------------------

export type ArchitectProjectOut = components["schemas"]["ArchitectProjectOut"];
export type UploadResultOut = components["schemas"]["UploadResultOut"];
export type UploadCandidateOut = components["schemas"]["UploadCandidateOut"];

export type ProjectUpdateIn = components["schemas"]["ProjectUpdateIn"];
export type PositionIn = components["schemas"]["PositionIn"];
export type SitePlacementOut = components["schemas"]["SitePlacementOut"];

export const ownProjectsKey = ["projects", "own"] as const;
const projectDetailsKey = (projectId: string) => ["projects", "details", projectId] as const;

/** Projekte mit Eigentümer; alle Architekten des Büros sehen dieselben (E-AN1-4). `archived` zeigt das Archiv
 *  (AN5, PLAN_AN5_AUSGABE 3.1). */
export function useOwnProjects(archived = false) {
  return useQuery({
    queryKey: [...ownProjectsKey, archived],
    queryFn: async () => unwrap(await api.GET("/api/v1/projects", { params: { query: { archived } } })),
  });
}

/** Name, ganze Notiz und Archiv eines Projekts (AN5). */
export function useProjectDetails(projectId: string) {
  return useQuery({
    queryKey: projectDetailsKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/details", { params: { path: { project_id: projectId } } })),
  });
}

/** Name, Notiz oder Archiv ändern; nur die genannten Felder ändern sich. */
export function useUpdateProject(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProjectUpdateIn) =>
      unwrap(
        await api.PATCH("/api/v1/projects/{project_id}", { params: { path: { project_id: projectId } }, body }),
      ),
    onSuccess: (project) => {
      client.setQueryData(projectDetailsKey(projectId), project);
      void client.invalidateQueries({ queryKey: ownProjectsKey });
    },
  });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/projects")),
    onSuccess: () => client.invalidateQueries({ queryKey: ownProjectsKey }),
  });
}

export function useDeleteProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { response } = await api.DELETE("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
      });
      if (!response.ok) throw new Error(`delete ${response.status}`);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ownProjectsKey }),
  });
}

/** Parzelle als DXF, GeoJSON oder vektorielles PDF (AN1). Ohne `index` und mit mehreren Konturen kommt die
 *  Auswahl zurück; mehrere gewählte Konturen vereinigt der Server (UP17). `scale` (1:n) gilt nur für PDF und
 *  ersetzt den Maßstab aus dem Plan. */
export function useUploadParcel(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      file,
      addressLabel,
      index,
      scale,
    }: {
      file: File;
      addressLabel: string;
      index?: readonly number[];
      scale?: number;
    }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("address_label", addressLabel);
      // Mehrere Konturen: das Feld wiederholt, der Server vereinigt sie (UP17)
      for (const i of index ?? []) form.append("index", String(i));
      if (scale !== undefined) form.append("scale", String(scale));
      return unwrap(
        await api.POST("/api/v1/projects/{project_id}/site/upload", {
          params: { path: { project_id: projectId } },
          // Der Serialisierer ersetzt den Rumpf; die Platzhalter erfüllen nur die Typen des Schemas
          body: { file: "", address_label: addressLabel },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: (result) => {
      if (result.site) {
        client.setQueryData(siteKey(result.site.project_id), result.site);
        void client.invalidateQueries({ queryKey: ownProjectsKey });
      }
    },
  });
}

/** Seite eines gescannten Plans (PDF, JPEG, PNG) als Vorlage zum Nachzeichnen (AN7, docs/PLAN_AN7_SCAN.md 3.5):
 *  Bild, erkannter Maßstab, Meter je Pixel. Der Server speichert nichts; die Texterkennung dauert 2–5 s. Als Abfrage
 *  je Datei und Seite, damit ein Seitenwechsel zurück nicht neu erkennt. */
export function useScanPreview(projectId: string, file: File, page: number) {
  return useQuery({
    queryKey: ["site-scan", projectId, file.name, file.size, file.lastModified, page],
    queryFn: async () => {
      const form = new FormData();
      form.append("file", file);
      form.append("page", String(page));
      return unwrap(
        await api.POST("/api/v1/projects/{project_id}/site/scan", {
          params: { path: { project_id: projectId } },
          // Der Serialisierer ersetzt den Rumpf; der Platzhalter erfüllt nur die Typen des Schemas
          body: { file: "", page },
          bodySerializer: () => form,
        }),
      );
    },
    staleTime: Infinity,
    retry: false,
  });
}

/** Grundstück ohne Kataster auf der Karte verorten oder die Lage korrigieren (AN5, PLAN_AN5_AUSGABE 3.2). Danach
 *  ändern sich Baurahmen und Analyse; Gelände und Risiken kommen im Hintergrund. */
export function usePositionSite(site: SiteOut) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<PositionIn, "expected_revision">) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/site/position", {
          params: { path: { project_id: site.project_id } },
          body: { ...body, expected_revision: site.revision },
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(siteKey(updated.project_id), updated);
      for (const key of [["admin", "envelope", updated.project_id], ["analysis", updated.project_id]]) {
        void client.invalidateQueries({ queryKey: key });
      }
    },
    onError: () => client.invalidateQueries({ queryKey: siteKey(site.project_id) }),
  });
}

/** Kantenart setzen als Architekt, auf dem eigenen Projekt (AN1); Ergebnis landet im Projekt-Cache. */
export function useClassifyEdge(site: SiteOut) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ seq, kind }: { seq: number; kind: EdgeKind | null }) =>
      unwrap(
        await api.PATCH("/api/v1/admin/projects/{project_id}/site/edges/{seq}", {
          params: { path: { project_id: site.project_id, seq }, header: { "if-match": `"${site.revision}"` } },
          body: { kind },
        }),
      ),
    onSuccess: (updated) => client.setQueryData(siteKey(updated.project_id), updated),
    onError: () => client.invalidateQueries({ queryKey: siteKey(site.project_id) }),
  });
}
