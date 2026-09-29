/** Verwaltung: Referenzlisten (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10, VA10). Eine Liste gilt für Konfigurator und
 *  Analyse; gemessen wird die Auswertung der Anwendung. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type ReferenceListOut = components["schemas"]["ReferenceListOut"];
export type ReferenceListDetailOut = components["schemas"]["ReferenceListDetailOut"];
export type ReferenceEntryIn = components["schemas"]["ReferenceEntryIn"];
export type ReferenceEntryOut = components["schemas"]["ReferenceEntryOut"];
export type ReferenceCandidateOut = components["schemas"]["ReferenceCandidateOut"];
export type ReferenceMeasurementOut = components["schemas"]["ReferenceMeasurementOut"];
export type MeasuredEntryOut = components["schemas"]["MeasuredEntryOut"];

const listsKey = ["admin", "reference-lists"] as const;
const listKey = (id: string) => ["admin", "reference-list", id] as const;
const measurementKey = (id: string) => ["admin", "reference-measurement", id] as const;

export function useReferenceLists() {
  return useQuery({ queryKey: listsKey, queryFn: async () => unwrap(await api.GET("/api/v1/admin/reference-lists")) });
}

export function useReferenceCandidates(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "reference-candidates"],
    enabled,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/reference-lists/candidates")),
  });
}

export function useReferenceList(id: string) {
  return useQuery({
    queryKey: listKey(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/reference-lists/{list_id}", { params: { path: { list_id: id } } })),
  });
}

export function useReferenceMeasurement(id: string, version: number | null, enabled: boolean) {
  return useQuery({
    queryKey: [...measurementKey(id), version],
    enabled,
    retry: false,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/reference-lists/{list_id}/measurement", {
          params: { path: { list_id: id }, query: version ? { version } : {} },
        }),
      ),
  });
}

/** Nach jeder Änderung: Detail setzen, Liste und Messung neu laden. */
function useStore(id?: string) {
  const client = useQueryClient();
  return (data?: ReferenceListDetailOut) => {
    if (data) client.setQueryData(listKey(data.id), data);
    void client.invalidateQueries({ queryKey: listsKey });
    if (id ?? data?.id) void client.invalidateQueries({ queryKey: measurementKey((id ?? data?.id)!) });
  };
}

export function useCreateReferenceList() {
  const store = useStore();
  return useMutation({
    mutationFn: async (body: components["schemas"]["ReferenceListIn"]) =>
      unwrap(await api.POST("/api/v1/admin/reference-lists", { body })),
    onSuccess: store,
  });
}

export function useImportReferenceList() {
  const store = useStore();
  return useMutation({
    mutationFn: async ({ data, replace }: { data: Record<string, unknown>; replace: boolean }) =>
      unwrap(await api.POST("/api/v1/admin/reference-lists/import", { params: { query: { replace } }, body: data })),
    onSuccess: store,
  });
}

export function usePatchReferenceList(id: string) {
  const store = useStore(id);
  return useMutation({
    mutationFn: async (body: components["schemas"]["ReferenceListPatch"]) =>
      unwrap(await api.PATCH("/api/v1/admin/reference-lists/{list_id}", { params: { path: { list_id: id } }, body })),
    onSuccess: store,
  });
}

export function useDeleteReferenceList(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const response = await api.DELETE("/api/v1/admin/reference-lists/{list_id}", { params: { path: { list_id: id } } });
      if (response.error) unwrap(response);
    },
    onSuccess: () => {
      client.removeQueries({ queryKey: listKey(id) });
      void client.invalidateQueries({ queryKey: listsKey });
    },
  });
}

export function useSaveReferenceEntry(id: string) {
  const store = useStore(id);
  return useMutation({
    mutationFn: async ({ entryId, body }: { entryId?: string; body: ReferenceEntryIn }) =>
      unwrap(
        entryId
          ? await api.PUT("/api/v1/admin/reference-lists/{list_id}/entries/{entry_id}", {
              params: { path: { list_id: id, entry_id: entryId } },
              body,
            })
          : await api.POST("/api/v1/admin/reference-lists/{list_id}/entries", { params: { path: { list_id: id } }, body }),
      ),
    onSuccess: store,
  });
}

export function useDeleteReferenceEntry(id: string) {
  const store = useStore(id);
  return useMutation({
    mutationFn: async (entryId: string) =>
      unwrap(
        await api.DELETE("/api/v1/admin/reference-lists/{list_id}/entries/{entry_id}", {
          params: { path: { list_id: id, entry_id: entryId } },
        }),
      ),
    onSuccess: store,
  });
}

export function useReferenceFromEvaluation(id: string) {
  const store = useStore(id);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/admin/reference-lists/{list_id}/from-evaluation", { params: { path: { list_id: id } } }),
      ),
    onSuccess: store,
  });
}

/** Liste als Datei speichern (Format `emprise-reference/1`). */
export async function exportReferenceList(id: string, filename: string): Promise<void> {
  const data = unwrap(
    await api.GET("/api/v1/admin/reference-lists/{list_id}/export", { params: { path: { list_id: id } } }),
  );
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
