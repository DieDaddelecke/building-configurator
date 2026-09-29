/** Organisation (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1, 3.7): Name und Mitglieder der eigenen Organisation.
 *  Verwalten darf nur die Rolle `admin`. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";
import { sessionKey } from "./session";

export type OrganisationOut = components["schemas"]["OrganisationOut"];
export type OrganisationIn = components["schemas"]["OrganisationIn"];
export type MemberOut = components["schemas"]["MemberOut"];
export type MemberIn = components["schemas"]["MemberIn"];
export type OrganisationRole = MemberOut["role"];

const organisationKey = ["organisation"] as const;
const membersKey = ["organisation", "members"] as const;

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
