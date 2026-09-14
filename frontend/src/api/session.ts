import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";

export const sessionKey = ["session"] as const;

/** Wer bin ich. Der erste Aufruf setzt auch das CSRF-Cookie. */
export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/session")),
    staleTime: 60_000,
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST("/api/v1/auth/staff/logout");
      if (!response.ok) throw new Error(`logout ${response.status}`);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: sessionKey }),
  });
}

export function staffLoginUrl(next = "/buero"): string {
  return `/api/v1/auth/staff/login?${new URLSearchParams({ next })}`;
}
