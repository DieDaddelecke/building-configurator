/** Vorentwurf-Übergabe (Modul V, docs/PLAN_V_VORENTWURF_UEBERGABE.md): Übergabe, Vorgang, Nachrichten,
 * Zugangslink, Dateien des Dossiers. */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, unwrap, type Problem } from "./client";
import { myInquiryKey, staffInquiryKey } from "./inquiry";
import type { components } from "./schema";
import { sessionKey } from "./session";

export type SubmitIn = components["schemas"]["SubmitIn"];
export type SubmitOut = components["schemas"]["SubmitOut"];
export type SubmissionFileOut = components["schemas"]["SubmissionFileOut"];
export type StaffSubmissionOut = components["schemas"]["StaffSubmissionOut"];
export type MessageOut = components["schemas"]["MessageOut"];

export const SUBMISSION_FLAG = "submission";

/** Teile des Prüfstempels, die sich seit dem Anzeigen geändert haben (V 3.3). */
export type ReviewPart = "site" | "rules" | "catalog" | "configuration" | "result" | "engine";

export type SubmissionProblem = Problem & {
  changes?: ReviewPart[];
  review_stamp?: string;
  missing?: string[];
  checks?: components["schemas"]["CheckOut"][];
};

export function submissionProblem(error: unknown): SubmissionProblem | null {
  return error instanceof ApiError ? (error.problem as SubmissionProblem) : null;
}

export function useSubmitDesign(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: SubmitIn) =>
      unwrap(await api.POST("/api/v1/projects/{project_id}/submission", { params: { path: { project_id: projectId } }, body })),
    onSuccess: () => client.invalidateQueries({ queryKey: myInquiryKey(projectId) }),
    onError: (error) => {
      // Neu gerechnete Auswertung laden, damit der Kunde sieht, was sich geändert hat (V 3.2 Schritt 3)
      if (submissionProblem(error)?.code === "review_changed") {
        void client.invalidateQueries({ queryKey: ["configuration", projectId] });
      }
    },
  });
}

export function useCustomerMessage(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: string) =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/inquiry/messages", {
          params: { path: { project_id: projectId } },
          body: { body },
        }),
      ),
    onSuccess: (updated) => client.setQueryData(myInquiryKey(projectId), updated),
  });
}

export function useWithdraw(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/projects/{project_id}/inquiry/withdraw", { params: { path: { project_id: projectId } } }),
      ),
    onSuccess: (updated) => client.setQueryData(myInquiryKey(projectId), updated),
  });
}

export function useRedeemAccess() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (token: string) => unwrap(await api.POST("/api/v1/access/redeem", { body: { token } })),
    onSuccess: () => client.invalidateQueries({ queryKey: sessionKey }),
  });
}

export function useRequestAccess() {
  return useMutation({
    mutationFn: async (email: string) => unwrap(await api.POST("/api/v1/access/request", { body: { email } })),
  });
}

/** Link zu einer Datei der eigenen Fassung (nur PDF); der Browser lädt sie mit dem Projekt-Cookie. */
export function fileUrl(projectId: string, sequence: number, name: string): string {
  return `/api/v1/projects/${projectId}/submissions/${sequence}/files/${encodeURIComponent(name)}`;
}

// ---------------------------------------------------------------------------
// Büro
// ---------------------------------------------------------------------------

export function staffFileUrl(projectId: string, sequence: number, name: string): string {
  return `/api/v1/admin/projects/${projectId}/submissions/${sequence}/files/${encodeURIComponent(name)}`;
}

export function useOfficeMessage(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: string) =>
      unwrap(
        await api.POST("/api/v1/admin/projects/{project_id}/inquiry/messages", {
          params: { path: { project_id: projectId } },
          body: { body },
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(staffInquiryKey(projectId), updated);
      void client.invalidateQueries({ queryKey: ["admin", "inquiries"] });
    },
  });
}

export function useRegenerateDossier(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (sequence: number) =>
      unwrap(
        await api.POST("/api/v1/admin/projects/{project_id}/submissions/{sequence}/dossier", {
          params: { path: { project_id: projectId, sequence } },
        }),
      ),
    onSuccess: (updated) => client.setQueryData(staffInquiryKey(projectId), updated),
  });
}
