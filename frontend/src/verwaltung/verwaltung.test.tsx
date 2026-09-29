import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";

import type { ReferenceListDetailOut, ReferenceListOut, ReferenceMeasurementOut } from "../api/reference";
import i18n from "../i18n";
import kinds from "../rules/__fixtures__/rule-kinds.json";
import { ModellWahl } from "./ModellWahl";
import { Verwaltung } from "./Verwaltung";

const state = vi.hoisted(() => ({
  lists: [] as unknown[],
  detail: null as unknown,
  measurement: null as unknown,
  create: vi.fn(),
  save: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("../api/reference", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/reference")>()),
  useReferenceLists: () => ({ data: state.lists, isPending: false, isError: false }),
  useReferenceCandidates: () => ({
    data: [{ document_sha256: "a".repeat(64), document_title: "PLU Beyenes", sectors: ["UC", "UR"] }],
    isPending: false,
  }),
  useCreateReferenceList: () => ({ mutate: state.create, isPending: false, error: null }),
  useImportReferenceList: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useReferenceList: () => ({ data: state.detail, isPending: false }),
  useReferenceMeasurement: () => ({ data: state.measurement }),
  usePatchReferenceList: () => ({ mutate: state.patch, isPending: false }),
  useReferenceFromEvaluation: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useDeleteReferenceList: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteReferenceEntry: () => ({ mutate: vi.fn(), isPending: false }),
  useSaveReferenceEntry: () => ({ mutate: state.save, isPending: false, error: null }),
}));

vi.mock("../api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/rules")>()),
  useRuleKinds: () => ({ data: kinds, isPending: false }),
  useRulesModel: () => ({
    data: {
      model: "anthropic/claude-opus-5.5",
      source: "setting",
      default_model: "anthropic/claude-opus-5",
      price_input_per_mtok: 4,
      price_output_per_mtok: 20,
      updated_at: "2026-09-28T20:00:00Z",
      input: "pdf",
      configured: true,
      month_cost_usd: 2.5,
      budget_month_usd: 20,
      updated_by_name: "Sarah",
    },
  }),
}));

const summary: ReferenceListOut = {
  id: "l1",
  document_sha256: "a".repeat(64),
  document_title: "PLU Beyenes",
  sector: "UC",
  status: "draft",
  note: "",
  entries_count: 2,
  updated_at: "2026-09-28T20:00:00Z",
  updated_by_name: "Sarah",
  summary: { version: 8, recall: 0.84, counts: { hit: 21, wrong_value: 0, silent_gap: 1, entries: 25 } },
};

const detail: ReferenceListDetailOut = {
  ...summary,
  entries: [
    {
      id: "e1",
      position: 1,
      kind: "max_height",
      building_kind: "any",
      expected: "effective",
      params: { ridge_m: 9, parapet_m: 7 },
      page: 14,
      quote: "La hauteur maximale des constructions est de 9 mètres au faîtage",
      note: "",
    },
    {
      id: "e2",
      position: 2,
      kind: "text_only",
      building_kind: "main",
      expected: "text_only",
      params: {},
      page: 15,
      quote: "Les débords de toit sont interdits.",
      note: "",
    },
  ],
};

const measurement: ReferenceMeasurementOut = {
  version: 8,
  versions: [7, 8],
  model: "anthropic/claude-opus-5.5",
  created_at: "2026-09-28T19:17:00Z",
  recall: 0.5,
  counts: { hit: 1, wrong_value: 0, named_gap: 0, dismissed: 0, silent_gap: 1, entries: 2, extra: 3 },
  coverage: {},
  results: [
    { entry_id: "e1", outcome: "hit", detail: "", found: null },
    { entry_id: "e2", outcome: "silent_gap", detail: "", found: null },
  ],
  extra: [],
};

function renderAt(path: string, darf = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/verwaltung/*" element={<Verwaltung darf={darf} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.lists = [summary];
  state.detail = detail;
  state.measurement = measurement;
  state.create.mockReset();
  state.save.mockReset();
  state.patch.mockReset();
});

it("ist dem Betrieb vorbehalten", () => {
  renderAt("/verwaltung", false);
  expect(screen.getByRole("alert")).toHaveTextContent("dem Betrieb vorbehalten");
});

it("zeigt das KI-Modell für Konfigurator und Analyse mit Wer-hat-gewählt", () => {
  renderAt("/verwaltung");
  expect(screen.getByRole("link", { name: "Referenzlisten" })).toBeInTheDocument();
  expect(screen.getByTestId("ki-modell")).toHaveTextContent("anthropic/claude-opus-5.5");
  expect(screen.getByText(/gewählt von Sarah/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ändern" })).toBeInTheDocument();
});

it("listet Referenzlisten mit Messung und legt eine neue für Dokument und Sektor an", async () => {
  renderAt("/verwaltung/referenzlisten");
  expect(screen.getByRole("link", { name: "Referenzlisten" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "KI-Modell" })).not.toHaveAttribute("aria-current");
  const zeile = screen.getByRole("row", { name: /PLU Beyenes · Zone UC/ });
  expect(zeile).toHaveTextContent("84 % richtig (Version 8)");
  expect(zeile).toHaveTextContent("eine fehlt still");
  expect(within(zeile).getByText("Entwurf")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Neue Referenzliste" }));
  await userEvent.selectOptions(screen.getByLabelText("Dokument"), `${"a".repeat(64)}|UR`);
  await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));
  expect(state.create).toHaveBeenCalledWith(
    { document_sha256: "a".repeat(64), document_title: "PLU Beyenes", sector: "UR", note: "" },
    expect.anything(),
  );
});

it("misst die Einträge und ergänzt einen Hinweis", async () => {
  renderAt("/verwaltung/referenzlisten/l1");
  expect(screen.getByRole("link", { name: "Alle Referenzlisten" })).toHaveAttribute("href", "/verwaltung/referenzlisten");
  expect(screen.getByRole("link", { name: "Referenzlisten" })).toHaveAttribute("href", "/verwaltung/referenzlisten");
  expect(screen.getByTestId("messung")).toHaveTextContent("1 von 2 richtig (50 %) · 0 falsch · 0 sichtbar offen · 0 verworfen · 1 still fehlend");
  expect(screen.getByRole("row", { name: /Höhe/ })).toHaveTextContent("richtig");
  expect(screen.getByRole("row", { name: /Hinweis/ })).toHaveTextContent("fehlt still");

  await userEvent.click(screen.getByRole("button", { name: "Als geprüft markieren" }));
  expect(state.patch).toHaveBeenCalledWith({ status: "checked" });

  await userEvent.click(screen.getByRole("button", { name: "Eintrag hinzufügen" }));
  const formular = screen.getByRole("form", { name: "Eintrag hinzufügen" });
  await userEvent.selectOptions(within(formular).getByLabelText("Regel"), "text_only");
  expect(within(formular).getByLabelText("Erwartet")).toHaveValue("text_only");
  await userEvent.type(within(formular).getByLabelText("Seite"), "13");
  await userEvent.type(within(formular).getByLabelText("Zitat"), "Les pompes à chaleur à 4 mètres des limites.");
  await userEvent.click(within(formular).getByRole("button", { name: "Speichern" }));
  expect(state.save).toHaveBeenCalledWith(
    {
      entryId: undefined,
      body: expect.objectContaining({ kind: "text_only", expected: "text_only", page: 13, params: {} }),
    },
    expect.anything(),
  );
});

it("verweist außerhalb der Verwaltung auf sie, statt selbst zu ändern", () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ModellWahl darfAendern={false} aendernUnter="/verwaltung" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.queryByRole("button", { name: "Ändern" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "In der Verwaltung ändern" })).toHaveAttribute("href", "/verwaltung");
});
