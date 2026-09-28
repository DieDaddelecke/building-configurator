/** Regelwerk (Modul G2, Plan 3.4): Regeln des Grundstücks als Simulation, Abdeckung und Korrekturen im Büro. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type ProjectRulesOut = components["schemas"]["ProjectRulesOut"];
export type ZoneRulesOut = components["schemas"]["ZoneRulesOut"];
export type RuleOut = components["schemas"]["RuleOut"];
export type RuleDetailOut = components["schemas"]["RuleDetailOut"];
export type CoverageOut = components["schemas"]["CoverageOut"];
export type RuleSetOut = components["schemas"]["RuleSetOut"];
export type RuleIn = components["schemas"]["RuleIn"];
export type ProjectOverrideIn = components["schemas"]["ProjectOverrideIn"];

export const RULES_FLAG = "rules_simulation";

const projectRulesKey = (projectId: string) => ["rules", projectId] as const;

/** Fragt nach, solange Kapitel noch ausgewertet werden (höchstens rund 10 Minuten). */
function refetchWhileRunning(data: ProjectRulesOut | undefined, updates: number): number | false {
  const running =
    data &&
    (data.status === "in_progress" || data.warnings.includes("rules_updating") || data.warnings.includes("rules_outdated"));
  return running && updates < 60 ? 10_000 : false;
}

export function useProjectRules(projectId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: projectRulesKey(projectId ?? ""),
    enabled: Boolean(projectId) && enabled,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/rules", { params: { path: { project_id: projectId! } } })),
    refetchInterval: (query) => refetchWhileRunning(query.state.data, query.state.dataUpdateCount),
  });
}

// ---------------------------------------------------------------------------
// Büro
// ---------------------------------------------------------------------------

export function useRulesCoverage() {
  return useQuery({
    queryKey: ["admin", "rules-coverage"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/rules/coverage")),
  });
}

export function useStartRulesImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (force: boolean) => unwrap(await api.POST("/api/v1/admin/rules/imports", { body: { force } })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "rules-coverage"] }),
  });
}

/** Kapitel auswerten. Ohne `force` nutzt der Server gespeicherte Aufrufe derselben Eingabe (kostenlos). */
export function useStartExtraction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ chapterId, force }: { chapterId: string; force: boolean }) =>
      unwrap(
        await api.POST("/api/v1/admin/rules/chapters/{chapter_id}/extract", {
          params: { path: { chapter_id: chapterId } },
          body: { force },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "rules-coverage"] }),
  });
}

// ---------------------------------------------------------------------------
// KI-Modell der Auswertung (PLAN_AN2_PLU 8): eine Einstellung für die ganze Instanz
// ---------------------------------------------------------------------------

export type RulesModelOut = components["schemas"]["RulesModelOut"];
export type ModelOptionOut = components["schemas"]["ModelOptionOut"];

const rulesModelKey = ["admin", "rules-model"] as const;

export function useRulesModel() {
  return useQuery({
    queryKey: rulesModelKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/rules/model")),
  });
}

/** Wählbare Modelle; erst beim Öffnen des Dialogs geladen (der Server hält die Liste eine Stunde vor). */
export function useRulesModels(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "rules-models"],
    enabled,
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/rules/models")),
    staleTime: 10 * 60_000,
  });
}

export function useSetRulesModel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (model: string) => unwrap(await api.PUT("/api/v1/admin/rules/model", { body: { model } })),
    onSuccess: (data) => {
      client.setQueryData(rulesModelKey, data);
      void client.invalidateQueries({ queryKey: ["admin", "rules-coverage"] });
    },
  });
}

const ruleSetKey = (id: string) => ["admin", "rule-set", id] as const;

export function useRuleSet(ruleSetId: string) {
  return useQuery({
    queryKey: ruleSetKey(ruleSetId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/rule-sets/{rule_set_id}", { params: { path: { rule_set_id: ruleSetId } } })),
  });
}

export function useCreateRuleSetVersion(ruleSetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { rules: RuleIn[]; note: string }) =>
      unwrap(
        await api.POST("/api/v1/admin/rule-sets/{rule_set_id}/versions", {
          params: { path: { rule_set_id: ruleSetId } },
          body,
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData(ruleSetKey(ruleSetId), updated);
      void client.invalidateQueries({ queryKey: ["admin", "rules-coverage"] });
    },
  });
}

const staffRulesKey = (projectId: string) => ["admin", "project-rules", projectId] as const;

export function useStaffProjectRules(projectId: string) {
  return useQuery({
    queryKey: staffRulesKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/projects/{project_id}/rules", { params: { path: { project_id: projectId } } })),
    refetchInterval: (query) => refetchWhileRunning(query.state.data, query.state.dataUpdateCount),
  });
}

export function usePutOverride(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProjectOverrideIn) =>
      unwrap(
        await api.PUT("/api/v1/admin/projects/{project_id}/rule-overrides", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: staffRulesKey(projectId) }),
  });
}

export function useDeleteOverride(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (overrideId: string) =>
      unwrap(
        await api.DELETE("/api/v1/admin/projects/{project_id}/rule-overrides/{override_id}", {
          params: { path: { project_id: projectId, override_id: overrideId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: staffRulesKey(projectId) }),
  });
}

export function useProjectOverrides(projectId: string) {
  return useQuery({
    queryKey: [...staffRulesKey(projectId), "overrides"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/projects/{project_id}/rule-overrides", { params: { path: { project_id: projectId } } }),
      ),
  });
}

// ---------------------------------------------------------------------------
// Regelformular und Korrekturen im Analyse-Produkt (AN4, docs/PLAN_AN4_KORREKTUR.md)
// ---------------------------------------------------------------------------

export type RuleKindFormOut = components["schemas"]["RuleKindFormOut"];
export type ParamFieldOut = components["schemas"]["ParamFieldOut"];
export type ProjectOverrideOut = components["schemas"]["ProjectOverrideOut"];
export type RuleSourceIn = components["schemas"]["RuleSourceIn"];

/** Formularbeschreibung der Regelarten; ändert sich nur mit dem Server. */
export function useRuleKinds() {
  return useQuery({
    queryKey: ["admin", "rule-kinds"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/rule-kinds")),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

const ownOverridesKey = (projectId: string) => ["rule-overrides", projectId] as const;

export function useOwnOverrides(projectId: string) {
  return useQuery({
    queryKey: ownOverridesKey(projectId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/projects/{project_id}/rule-overrides", { params: { path: { project_id: projectId } } })),
  });
}

/** Regeln, Baurahmen, Analyse und Vergleich hängen an den Korrekturen: nach jeder Änderung neu laden. */
function useAfterCorrection(projectId: string) {
  const client = useQueryClient();
  return (overrides: ProjectOverrideOut[]) => {
    client.setQueryData(ownOverridesKey(projectId), overrides);
    for (const key of [staffRulesKey(projectId), ["admin", "envelope", projectId], ["analysis", projectId]]) {
      void client.invalidateQueries({ queryKey: key });
    }
  };
}

export function usePutOwnOverride(projectId: string) {
  const refresh = useAfterCorrection(projectId);
  return useMutation({
    mutationFn: async (body: ProjectOverrideIn) =>
      unwrap(
        await api.PUT("/api/v1/projects/{project_id}/rule-overrides", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteOwnOverride(projectId: string) {
  const refresh = useAfterCorrection(projectId);
  return useMutation({
    mutationFn: async (overrideId: string) =>
      unwrap(
        await api.DELETE("/api/v1/projects/{project_id}/rule-overrides/{override_id}", {
          params: { path: { project_id: projectId, override_id: overrideId } },
        }),
      ),
    onSuccess: refresh,
  });
}
