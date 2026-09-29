/** Organisation (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1, 3.4–3.7): Mitglieder, Erscheinungsbild, Verbrauch und
 *  API-Schlüssel der eigenen Organisation. Verwalten darf nur die Rolle `admin`; den Verbrauch sehen alle. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";
import { sessionKey } from "./session";

export type OrganisationOut = components["schemas"]["OrganisationOut"];
export type OrganisationIn = components["schemas"]["OrganisationIn"];
export type MemberOut = components["schemas"]["MemberOut"];
export type MemberIn = components["schemas"]["MemberIn"];
export type UsageOut = components["schemas"]["UsageOut"];
export type ApiKeyOut = components["schemas"]["ApiKeyOut"];
export type ApiKeyIn = components["schemas"]["ApiKeyIn"];
export type ApiKeyCreatedOut = components["schemas"]["ApiKeyCreatedOut"];
export type OrganisationRole = MemberOut["role"];

const organisationKey = ["organisation"] as const;
const membersKey = ["organisation", "members"] as const;
const usageKey = ["organisation", "usage"] as const;
const apiKeysKey = ["organisation", "api-keys"] as const;

/** Logo für die Vorschau; die Revision im Pfad umgeht den Cache nach einem Wechsel. */
export function logoUrl(revision: number): string {
  return `/api/v1/organisation/logo?r=${revision}`;
}

export function useOrganisation() {
  return useQuery({
    queryKey: organisationKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/organisation")),
  });
}

export function useUpdateOrganisation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: OrganisationIn) => unwrap(await api.PATCH("/api/v1/organisation", { body })),
    onSuccess: (organisation) => {
      client.setQueryData(organisationKey, organisation);
      // Der Kopf zeigt den Anzeigenamen aus der Sitzung
      void client.invalidateQueries({ queryKey: sessionKey });
    },
  });
}

export function useUploadLogo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return unwrap(
        await api.PUT("/api/v1/organisation/logo", {
          // Der Serialisierer ersetzt den Rumpf; der Platzhalter erfüllt nur den Typ des Schemas
          body: { file: "" },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: (organisation) => client.setQueryData(organisationKey, organisation),
  });
}

export function useRemoveLogo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/organisation/logo")),
    onSuccess: (organisation) => client.setQueryData(organisationKey, organisation),
  });
}

export function useMembers(enabled: boolean) {
  return useQuery({
    queryKey: membersKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/organisation/members")),
    enabled,
  });
}

export function useAddMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: MemberIn) => unwrap(await api.POST("/api/v1/organisation/members", { body })),
    onSuccess: (members) => client.setQueryData(membersKey, members),
  });
}

export function useChangeMemberRole() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: OrganisationRole }) =>
      unwrap(
        await api.PATCH("/api/v1/organisation/members/{user_id}", {
          params: { path: { user_id: userId } },
          body: { role },
        }),
      ),
    onSuccess: (members) => client.setQueryData(membersKey, members),
  });
}

export function useRemoveMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) =>
      unwrap(
        await api.DELETE("/api/v1/organisation/members/{user_id}", { params: { path: { user_id: userId } } }),
      ),
    onSuccess: (members) => client.setQueryData(membersKey, members),
  });
}

export function useUsage() {
  return useQuery({
    queryKey: usageKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/organisation/usage")),
  });
}

export function useApiKeys(enabled: boolean) {
  return useQuery({
    queryKey: apiKeysKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/organisation/api-keys")),
    enabled,
  });
}

/** Der Schlüssel im Klartext steht nur in dieser Antwort; die Seite zeigt ihn einmal. */
export function useCreateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApiKeyIn) => unwrap(await api.POST("/api/v1/organisation/api-keys", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: apiKeysKey }),
  });
}

export function useRevokeApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (keyId: string) => {
      const { response } = await api.DELETE("/api/v1/organisation/api-keys/{key_id}", {
        params: { path: { key_id: keyId } },
      });
      if (!response.ok) throw new Error(`revoke ${response.status}`);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: apiKeysKey }),
  });
}
