import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { SupplementAnalysisOut } from "../../api/analysis";
import type { ProjectRegulationOut } from "../../api/regulations";
import i18n from "../../i18n";
import kinds from "../../rules/__fixtures__/rule-kinds.json";
import { Zusatzdokumente } from "./Zusatzdokumente";

const state = vi.hoisted(() => ({
  regulations: [] as unknown[],
  supplements: [] as unknown[],
  upload: vi.fn(),
  chooseLot: vi.fn(),
  remove: vi.fn(),
  put: vi.fn(),
}));

vi.mock("../../api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/rules")>()),
  useRuleKinds: () => ({ data: kinds, isPending: false }),
  usePutOwnOverride: () => ({ mutate: state.put, isPending: false, error: null }),
  useStaffProjectRules: () => ({
    data: {
      plan: { id: "plu", title: "PLUi Erdre et Gesvres" },
      zones: [{ code: "Uh", rules: [], hints: [] }],
    },
  }),
}));

vi.mock("../../api/regulations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/regulations")>()),
  useProjectRegulations: () => ({ data: state.regulations, isPending: false, isError: false, isSuccess: true }),
  useUploadRegulation: () => ({ mutate: state.upload, reset: vi.fn(), isPending: false, error: null }),
  useChooseLot: () => ({ mutate: state.chooseLot, isPending: false, error: null }),
  useRemoveRegulation: () => ({ mutate: state.remove, isPending: false, isError: false }),
}));

vi.mock("../../api/analysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/analysis")>()),
  useAnalysis: () => ({ data: { supplements: state.supplements }, isPending: false, isError: false }),
}));

const supplement = (
  overrides: Partial<ProjectRegulationOut> = {},
  document: Partial<ProjectRegulationOut["document"]> = {},
): ProjectRegulationOut => ({
  role: "supplement",
  zone_code: null,
  chapter_code: null,
  ...overrides,
  document: {
    id: "s1",
    title: "Règlement du lotissement Les Chênes",
    du_type: "lotissement",
    status: "active",
    error: null,
    file_name: "lotissement.pdf",
    file_url: "/api/v1/regulation-files/f2",
    page_count: 3,
    empty_pages: [],
    created_at: "2026-09-26T10:00:00Z",
    chapters: [
      {
        code: "DOC",
        title: "Règlement du lotissement Les Chênes",
        first_page: 1,
        last_page: 3,
        general_pages: [],
        detection: "document",
        sectors: overrides.zone_code ? [overrides.zone_code] : [],
        suggested_sectors: [],
        status: overrides.zone_code ? "succeeded" : "idle",
        error: null,
        runs: overrides.zone_code ? 2 : 0,
        cost_usd: overrides.zone_code ? 0.16 : 0,
      },
    ],
    ...document,
  },
});

const citation = (page: number) => ({
  page,
  quote: "Zitat",
  quote_verified: true,
  source_url: `/api/v1/regulation-files/f2#page=${page}`,
  origin: "extraction" as const,
  confidence: 0.9,
  notes: null,
});

const limit = (kind: string, params: Record<string, unknown>, page: number, status = "effective") => ({
  key: kind,
  kind,
  building_kind: "main",
  status: status as "effective",
  reason: null,
  value: null,
  params,
  citation: citation(page),
  derived_from: null,
});

const comparisons: SupplementAnalysisOut = {
  document_id: "s1",
  title: "Règlement du lotissement Les Chênes",
  du_type: "lotissement",
  lot: "Lot-12",
  status: "simulated",
  reason: null,
  updating: false,
  comparisons: [
    {
      kind: "max_height",
      building_kind: "main",
      verdict: "stricter",
      supplement: limit("max_height", { ridge_m: 8 }, 2),
      plu: limit("max_height", { eave_m: 7, ridge_m: 10 }, 9),
      details: { ridge_m: "stricter" },
      proposal: { eave_m: 7, ridge_m: 8, reference: "natural_terrain", measured_at: "highest_point", includes_roof_installations: false },
    },
    {
      kind: "max_area",
      building_kind: "any",
      verdict: "only_supplement",
      supplement: limit("max_area", { sdp_m2: 180, footprint_m2: 120 }, 3),
      plu: null,
      details: {},
      proposal: { sdp_m2: 180, footprint_m2: 120 },
    },
    {
      kind: "setback_side",
      building_kind: "main",
      verdict: "no_own_rule",
      supplement: limit("setback_side", {}, 2, "not_regulated"),
      plu: limit("setback_side", { min_m: 3, allow_on_boundary: true }, 7),
      details: {},
    },
  ],
  hints: [limit("text_only", { summary: "Clôtures sur rue en haies vives." }, 2, "text_only")],
};

function zeige() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Zusatzdokumente projectId="p1" />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.regulations = [];
  state.supplements = [];
  state.upload.mockReset();
  state.chooseLot.mockReset();
});

it("lädt ein Zusatzdokument mit Art hoch", async () => {
  zeige();
  await userEvent.click(screen.getByRole("button", { name: "Zusatzdokument hochladen" }));
  const file = new File(["%PDF-1.7"], "cahier.pdf", { type: "application/pdf" });
  await userEvent.upload(screen.getByLabelText("Zusatzdokument (PDF)"), file);
  await userEvent.selectOptions(screen.getByLabelText("Art"), "cahier_des_charges");
  await userEvent.click(screen.getByRole("button", { name: "Hochladen" }));
  expect(state.upload).toHaveBeenCalledWith({ file, title: "", duType: "cahier_des_charges" }, expect.anything());
});

it("wählt das Lot und prüft seine Schreibweise", async () => {
  state.regulations = [supplement()];
  zeige();
  const feld = screen.getByLabelText("Lot des Grundstücks (optional)");
  const knopf = screen.getByRole("button", { name: "Lot übernehmen und auswerten" });
  await userEvent.type(feld, "12 a");
  expect(knopf).toBeDisabled();
  await userEvent.clear(feld);
  await userEvent.type(feld, "12");
  await userEvent.click(knopf);
  expect(state.chooseLot).toHaveBeenCalledWith({ lot: "12" }, expect.anything());
});

it("ohne Lot gilt das ganze Dokument, mit Seitenbereich nur dieser", async () => {
  state.regulations = [supplement()];
  zeige();
  await userEvent.click(screen.getByLabelText(/Nur einen Seitenbereich/));
  await userEvent.type(screen.getByLabelText("Kapitel von Seite"), "1");
  await userEvent.type(screen.getByLabelText("bis Seite"), "40");
  await userEvent.click(screen.getByRole("button", { name: "Lot übernehmen und auswerten" }));
  expect(state.chooseLot).toHaveBeenCalledWith({ first_page: 1, last_page: 40 }, expect.anything());
});

it("zeigt den Stand und den Vergleich mit dem Bebauungsplan", () => {
  state.regulations = [supplement({ zone_code: "Lot-12", chapter_code: "DOC" })];
  state.supplements = [comparisons];
  zeige();
  expect(screen.getByRole("status")).toHaveTextContent("Lot 12");
  expect(screen.getByRole("status")).toHaveTextContent("ausgewertet");
  const table = screen.getByRole("table", { name: /Vergleich von Règlement du lotissement/ });
  const height = within(table).getByRole("row", { name: /Höhe/ });
  expect(height).toHaveTextContent("First ≤ 8 m");
  expect(height).toHaveTextContent("strenger als der PLU");
  expect(within(height).getByRole("link", { name: "S. 2" })).toHaveAttribute("href", "/api/v1/regulation-files/f2#page=2");
  const area = within(table).getByRole("row", { name: /Höchstflächen/ });
  expect(area).toHaveTextContent("keine Regel");
  expect(area).toHaveTextContent("Nutzfläche (SDP) ≤ 180 m²");
  expect(area).toHaveTextContent("nur im Zusatzdokument");
  expect(within(table).getByRole("row", { name: /Seitlicher Abstand/ })).toHaveTextContent("keine eigene Regel – der PLU gilt");
  expect(screen.getByText("Clôtures sur rue en haies vives.")).toBeInTheDocument();
  expect(screen.getByText(/Nicht von selbst in Regeln, Baurahmen und Analyse eingerechnet/)).toBeInTheDocument();
  expect(within(height).getByRole("button", { name: "Übernehmen" })).toBeInTheDocument();
  expect(within(table).getByRole("row", { name: /Seitlicher Abstand/ })).not.toHaveTextContent("Übernehmen");
});

it("übernimmt das Strengere mit der Fundstelle des Zusatzdokuments (AN4)", async () => {
  state.regulations = [supplement({ zone_code: "Lot-12", chapter_code: "DOC" })];
  state.supplements = [comparisons];
  state.put.mockReset();
  zeige();
  const table = screen.getByRole("table", { name: /Vergleich von Règlement du lotissement/ });
  await userEvent.click(within(within(table).getByRole("row", { name: /Höhe/ })).getByRole("button", { name: "Übernehmen" }));
  const formular = screen.getByRole("form", { name: "Korrektur: Höhe" });
  expect(within(formular).getByLabelText("Traufhöhe")).toHaveValue("7");
  expect(within(formular).getByLabelText("Firsthöhe")).toHaveValue("8");
  expect(within(formular).getByLabelText("Dokument")).toHaveValue("s1");
  expect(within(formular).getByLabelText("Seite")).toHaveValue("2");
  await userEvent.type(within(formular).getByLabelText("Begründung"), "Lotissement autorisé en 2021");
  await userEvent.click(within(formular).getByRole("button", { name: "Korrektur speichern" }));
  expect(state.put).toHaveBeenCalledWith(
    expect.objectContaining({
      zone_code: "Uh",
      kind: "max_height",
      params: { eave_m: 7, ridge_m: 8, reference: "natural_terrain", measured_at: "highest_point", includes_roof_installations: false },
      source: { document_id: "s1", page: 2, quote: "Zitat" },
    }),
    expect.anything(),
  );
});

it("zeigt übernommene Werte als übernommen", () => {
  state.regulations = [supplement({ zone_code: "Lot-12", chapter_code: "DOC" })];
  const [height] = comparisons.comparisons;
  state.supplements = [{ ...comparisons, comparisons: [{ ...height!, verdict: "adopted", proposal: null }] }];
  zeige();
  const row = screen.getByRole("row", { name: /Höhe/ });
  expect(row).toHaveTextContent("übernommen");
  expect(within(row).queryByRole("button", { name: "Übernehmen" })).toBeNull();
});

it("nimmt höchstens drei Zusatzdokumente an", () => {
  state.regulations = [
    supplement({}, { id: "a" }),
    supplement({}, { id: "b" }),
    supplement({}, { id: "c" }),
  ];
  zeige();
  expect(screen.queryByRole("button", { name: "Zusatzdokument hochladen" })).not.toBeInTheDocument();
  expect(screen.getByText("Höchstens drei Zusatzdokumente je Projekt.")).toBeInTheDocument();
});
