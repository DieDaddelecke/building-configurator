/** Anfrage (Modul A, docs/PLAN_A_ANFRAGE.md): Kontakt, Codebestätigung, Büro-Sicht, Export, Löschung. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, unwrap, type Problem } from "./client";
import { sessionKey } from "./session";
import type { components } from "./schema";

export type ContactIn = components["schemas"]["ContactIn"];
export type ConfirmIn = components["schemas"]["ConfirmIn"];
export type MyInquiryOut = components["schemas"]["MyInquiryOut"];
export type ExportOut = components["schemas"]["ExportOut"];
export type InquiryListItem = components["schemas"]["InquiryListItem"];
export type InquiryDetailOut = components["schemas"]["InquiryDetailOut"];
export type InquiryStatus = InquiryListItem["status"];

export const INQUIRY_FLAG = "inquiry";

const myInquiryKey = (projectId: string) => ["inquiry", projectId] as const;

export function useMyInquiry(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: myInquiryKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/inquiry", { params: { path: { project_id: projectId! } } })),
  });
}

export function useSubmitContact(projectId: string) {
  return useMutation({
    mutationFn: async (body: ContactIn) =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/inquiry/contact", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
  });
}

export function useConfirmContact(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ConfirmIn) =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/inquiry/confirm", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: myInquiryKey(projectId) }),
  });
}

export function useExportProject(projectId: string) {
  return useMutation({
    mutationFn: async (): Promise<ExportOut> =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/export", { params: { path: { project_id: projectId } } })),
  });
}

export function useDeleteProject(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      // 204 ohne Rumpf: `unwrap` erwartet immer Nutzdaten, hier reicht der Erfolg selbst
      const { error, response } = await api.DELETE("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
      });
      if (!response.ok) throw new ApiError(error as Problem);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: sessionKey }),
  });
}

// ---------------------------------------------------------------------------
// Büro
// ---------------------------------------------------------------------------

export function useInquiries(status: InquiryStatus | "" = "") {
  return useQuery({
    queryKey: ["admin", "inquiries", status],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/inquiries", { params: { query: status ? { status } : {} } })),
  });
}

const staffInquiryKey = (projectId: string) => ["admin", "inquiry", projectId] as const;

export function useStaffInquiry(projectId: string) {
  return useQuery({
    queryKey: staffInquiryKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/projects/{project_id}/inquiry", { params: { path: { project_id: projectId } } }),
      ),
  });
}

export function useSetInquiryStatus(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (status: InquiryStatus) =>
      unwrap(
        await api.PATCH("/api/v1/admin/projects/{project_id}/inquiry", {
          params: { path: { project_id: projectId } },
          body: { status },
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(staffInquiryKey(updated.project_id), updated);
      void client.invalidateQueries({ queryKey: ["admin", "inquiries"] });
    },
  });
}
