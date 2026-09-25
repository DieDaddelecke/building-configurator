/** Baurahmen (Modul G3, Plan 3.5): bebaubare Fläche, Grenzwerte und Hinweise als Simulation. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type EnvelopeOut = components["schemas"]["EnvelopeOut"];
export type ContourOut = components["schemas"]["ContourOut"];
export type PartOut = components["schemas"]["PartOut"];
export type LimitOut = components["schemas"]["LimitOut"];
export type EnvelopeEdgeOut = components["schemas"]["EnvelopeEdgeOut"];
export type ConstraintOut = components["schemas"]["ConstraintOut"];
export type BandOut = components["schemas"]["BandOut"];
export type SheetOut = components["schemas"]["SheetOut"];

export const ENVELOPE_FLAG = "envelope_simulation";

const envelopeKey = (projectId: string) => ["envelope", projectId] as const;

/** Fragt nach, solange Regeln ausgewertet werden oder das Gelände noch aussteht. */
function refetchWhilePending(data: EnvelopeOut | undefined, updates: number): number | false {
  const pending =
    data && (data.status === "in_progress" || data.provenance.terrain_status === "pending");
  return pending && updates < 60 ? 10_000 : false;
}

export function useEnvelope(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: envelopeKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/envelope", { params: { path: { project_id: projectId! } } })),
    refetchInterval: (query) => refetchWhilePending(query.state.data, query.state.dataUpdateCount),
  });
}

/** Steckbrief anfordern. Antwort `pending`: Der Worker setzt ihn, der Knopf fragt danach erneut. */
export function useRequestSheet(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/projects/{project_id}/envelope/sheet", { params: { path: { project_id: projectId } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: envelopeKey(projectId) }),
  });
}

export function sheetUrl(projectId: string): string {
  return `/api/v1/projects/${projectId}/envelope/sheet`;
}

export function useStaffEnvelope(projectId: string) {
  return useQuery({
    queryKey: ["admin", "envelope", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/projects/{project_id}/envelope", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (query) => refetchWhilePending(query.state.data, query.state.dataUpdateCount),
  });
}

/** Wie `useRequestSheet`/`sheetUrl`, aber für die Prüfung einer Anfrage (Modul A): Rolle statt Feature-Flag. */
export function useStaffRequestSheet(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/admin/projects/{project_id}/envelope/sheet", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "envelope", projectId] }),
  });
}

export function staffSheetUrl(projectId: string): string {
  return `/api/v1/admin/projects/${projectId}/envelope/sheet`;
}
