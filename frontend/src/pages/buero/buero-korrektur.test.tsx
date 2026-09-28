/** Büro des Konfigurators: Korrekturen über Felder statt JSON (AN4, RW15). */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import kinds from "../../rules/__fixtures__/rule-kinds.json";
import { ProjektRegeln } from "./Grundstuecke";
import { Regelwerk } from "./Regeln";

const state = vi.hoisted(() => ({ put: vi.fn(), create: vi.fn() }));

const rule = (kind: string, params: Record<string, unknown>) => ({
  kind,
  building_kind: "main",
  status: "effective",
  reason: null,
  params,
  page: 8,
  quote: "Zitat",
  quote_verified: true,
  source_url: "https://gpu/reglement.pdf#page=8",
  confidence: 0.9,
  notes: null,
  origin: "extraction",
  source_document_id: "plan",
  detail: null,
  alternatives: [],
  similarity: 1,
});

vi.mock("../../api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/rules")>()),
  useRuleKinds: () => ({ data: kinds, isPending: false }),
  useStaffProjectRules: () => ({
    isPending: false,
    isError: false,
    data: {
      simulation: true,
      status: "ok",
      reason: null,
      commune_insee: "44209",
      plan: { id: "plan", origin: "gpu", title: "PLUi Erdre et Gesvres", du_type: "PLUi", gpu_doc_id: "x", gpu_update_date: null, regulation_url: null },
      zones: [
        {
          code: "Uh",
          label: null,
          chapter_code: "Uh",
          area_m2: 600,
          share: 1,
          status: "simulated",
          reason: null,
          rule_set_id: "rs",
          version: null,
          rules: [rule("max_footprint_ratio", { ratio: 0.25 })],
          hints: [],
        },
      ],
      ignored_zones: [],
      uncovered_share: 0,
      overlays: [],
      warnings: [],
      notices: [],
    },
  }),
  useProjectOverrides: () => ({ data: [] }),
  usePutOverride: () => ({ mutate: state.put, isPending: false, error: null }),
  useDeleteOverride: () => ({ mutate: vi.fn(), isPending: false }),
  useRuleSet: () => ({
    isPending: false,
    isError: false,
    data: {
      id: "rs",
      zone_code: "Uh",
      plan: { id: "plan", origin: "gpu", title: "PLUi", du_type: "PLUi", gpu_doc_id: "x", gpu_update_date: null, regulation_url: null },
      current: null,
      versions: [],
      rules: [rule("max_footprint_ratio", { ratio: 0.25 }), rule("max_height", { eave_m: 7, ridge_m: 10 })],
    },
  }),
  useCreateRuleSetVersion: () => ({ mutate: state.create, isPending: false, isError: false, isSuccess: false }),
}));

vi.mock("../../site/GrundstueckPruefen", () => ({ useNotices: () => ({ data: [] }) }));

function renderWith(element: React.ReactNode, path = "/") {
  const router = createMemoryRouter([{ path: "/buero/regeln/:ruleSetId", element }, { path: "/", element }], {
    initialEntries: [path],
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.put.mockReset();
  state.create.mockReset();
});

it("korrigiert eine Regel für ein Projekt mit Feldern und Fundstelle", async () => {
  const user = userEvent.setup();
  renderWith(<ProjektRegeln projectId="p1" />);
  await user.click(screen.getByText("Nur für dieses Projekt korrigieren (Zone Uh)"));
  const formular = screen.getByRole("form", { name: "Korrektur: Grundfläche" });
  expect(within(formular).queryByPlaceholderText(/ratio/)).toBeNull();
  await user.type(within(formular).getByLabelText(/Anteil/), "20");
  await user.selectOptions(within(formular).getByLabelText("Dokument"), "plan");
  await user.type(within(formular).getByLabelText("Seite"), "8");
  await user.type(within(formular).getByLabelText("Begründung"), "Lotissement");
  await user.click(within(formular).getByRole("button", { name: "Korrektur speichern" }));
  expect(state.put).toHaveBeenCalledWith(
    {
      zone_code: "Uh",
      kind: "max_footprint_ratio",
      building_kind: "any",
      status: "effective",
      params: { ratio: 0.2 },
      note: "Lotissement",
      source: { document_id: "plan", page: 8, quote: null },
    },
    expect.anything(),
  );
});

it("legt eine Zonenversion mit Feldern statt JSON an", async () => {
  const user = userEvent.setup();
  renderWith(<Regelwerk />, "/buero/regeln/rs");
  const zeile = screen.getAllByRole("row", { name: /Grundfläche/ }).at(-1)!;
  const anteil = within(zeile).getByLabelText(/Anteil/);
  expect(anteil).toHaveValue("25");
  await user.clear(anteil);
  await user.type(anteil, "30");
  await user.type(screen.getByLabelText("Begründung"), "Relecture");
  await user.click(screen.getByRole("button", { name: "Speichern" }));
  expect(state.create).toHaveBeenCalledWith({
    rules: [
      expect.objectContaining({ kind: "max_footprint_ratio", params: { ratio: 0.3 } }),
      expect.objectContaining({
        kind: "max_height",
        params: { eave_m: 7, ridge_m: 10, reference: "natural_terrain", measured_at: "highest_point", includes_roof_installations: false },
      }),
    ],
    note: "Relecture",
  });
});
