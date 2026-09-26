import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { DocumentChapterOut, ProjectRegulationOut } from "../../api/regulations";
import i18n from "../../i18n";
import { Bebauungsplan } from "./Bebauungsplan";

const state = vi.hoisted(() => ({
  regulations: [] as unknown[],
  upload: vi.fn(),
  choose: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("../../api/regulations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/regulations")>()),
  useProjectRegulations: () => ({ data: state.regulations, isPending: false, isError: false, isSuccess: true }),
  useUploadRegulation: () => ({ mutate: state.upload, reset: vi.fn(), isPending: false, error: null }),
  useChooseZone: () => ({ mutate: state.choose, isPending: false, error: null }),
  useRemoveRegulation: () => ({ mutate: state.remove, isPending: false, isError: false }),
}));

const chapter = (overrides: Partial<DocumentChapterOut> = {}): DocumentChapterOut => ({
  code: "Uh",
  title: "ZONE Uh",
  first_page: 4,
  last_page: 24,
  general_pages: [1, 2, 3],
  detection: "headings",
  sectors: [],
  suggested_sectors: ["Uh1"],
  status: "idle",
  error: null,
  runs: 0,
  cost_usd: 0,
  ...overrides,
});

const regulation = (
  overrides: Partial<ProjectRegulationOut> = {},
  document: Partial<ProjectRegulationOut["document"]> = {},
): ProjectRegulationOut => ({
  role: "plu",
  zone_code: null,
  chapter_code: null,
  ...overrides,
  document: {
    id: "d1",
    title: "PLUi Erdre et Gesvres",
    du_type: "PLUi",
    status: "active",
    error: null,
    file_name: "reglement.pdf",
    file_url: "/api/v1/regulation-files/f1",
    page_count: 24,
    empty_pages: [],
    created_at: "2026-09-25T10:00:00Z",
    chapters: [chapter()],
    ...document,
  },
});

function zeige() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Bebauungsplan projectId="p1" />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.regulations = [];
  state.upload.mockReset();
  state.choose.mockReset();
});

it("lädt ein Reglement mit Bezeichnung und Art hoch", async () => {
  zeige();
  const file = new File(["%PDF-1.7"], "reglement.pdf", { type: "application/pdf" });
  await userEvent.upload(screen.getByLabelText("règlement écrit (PDF)"), file);
  await userEvent.type(screen.getByLabelText("Bezeichnung"), "PLUi 2026");
  await userEvent.selectOptions(screen.getByLabelText("Art"), "PLUi");
  await userEvent.click(screen.getByRole("button", { name: "Hochladen" }));
  expect(state.upload).toHaveBeenCalledWith({ file, title: "PLUi 2026", duType: "PLUi" }, expect.anything());
});

it("zeigt, dass das Reglement gelesen wird", () => {
  state.regulations = [regulation({}, { status: "importing", chapters: [], page_count: null })];
  zeige();
  expect(screen.getByRole("status")).toHaveTextContent("Das Reglement wird gelesen");
});

it("wählt Kapitel und Sektor aus den Vorschlägen", async () => {
  state.regulations = [regulation()];
  zeige();
  expect(screen.getByRole("link", { name: "PDF öffnen" })).toHaveAttribute("href", "/api/v1/regulation-files/f1");
  expect(screen.getByLabelText("Zonenkapitel")).toHaveValue("Uh");
  expect(screen.getByLabelText("Zone oder Sektor des Grundstücks")).toHaveValue("Uh");
  await userEvent.click(screen.getByRole("button", { name: "Uh1" }));
  await userEvent.click(screen.getByRole("button", { name: "Zone übernehmen und auswerten" }));
  expect(state.choose).toHaveBeenCalledWith({ zone_code: "Uh1", chapter_code: "Uh" }, expect.anything());
});

it("nimmt ohne erkannte Kapitel einen Seitenbereich von Hand", async () => {
  state.regulations = [regulation({}, { chapters: [] })];
  zeige();
  expect(screen.getByText(/kein Inhaltsverzeichnis/)).toBeInTheDocument();
  const knopf = screen.getByRole("button", { name: "Zone übernehmen und auswerten" });
  expect(knopf).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Zone oder Sektor des Grundstücks"), "Ub");
  await userEvent.type(screen.getByLabelText("Kapitel von Seite"), "40");
  await userEvent.type(screen.getAllByLabelText("bis Seite")[0]!, "52");
  await userEvent.click(knopf);
  expect(state.choose).toHaveBeenCalledWith({ zone_code: "Ub", first_page: 40, last_page: 52 }, expect.anything());
});

it("nennt den Grund, wenn die Auswertung nicht eingerichtet ist", () => {
  state.regulations = [
    regulation(
      { zone_code: "Uh", chapter_code: "Uh" },
      { chapters: [chapter({ sectors: ["Uh"], status: "failed", error: "not_configured", runs: 0 })] },
    ),
  ];
  zeige();
  expect(screen.getByText("Zone Uh · Kapitel Uh")).toBeInTheDocument();
  expect(screen.getByText("Auswertung gescheitert")).toBeInTheDocument();
  expect(screen.getByText(/Es fehlt der Schlüssel der Claude API/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Zone ändern" })).toBeInTheDocument();
});

it("zeigt Aufrufe und Kosten einer fertigen Auswertung", () => {
  state.regulations = [
    regulation(
      { zone_code: "Uh", chapter_code: "Uh" },
      { chapters: [chapter({ sectors: ["Uh"], status: "succeeded", runs: 2, cost_usd: 0.16 })] },
    ),
  ];
  zeige();
  expect(screen.getByText("ausgewertet")).toBeInTheDocument();
  expect(screen.getByText(/2 Aufrufe · 0,16 \$/)).toBeInTheDocument();
});

it("meldet einen Scan ohne Text", () => {
  state.regulations = [regulation({}, { status: "failed", error: "document_no_text", chapters: [] })];
  zeige();
  expect(screen.getByRole("alert")).toHaveTextContent("vermutlich ein Scan");
});

it("nimmt ein Zusatzdokument nicht für den Bebauungsplan", () => {
  state.regulations = [regulation({ role: "supplement", zone_code: "Lot-12" }, { id: "s1", title: "Lotissement" })];
  zeige();
  expect(screen.queryByText("Lotissement")).not.toBeInTheDocument();
  expect(screen.getByLabelText("règlement écrit (PDF)")).toBeInTheDocument();
});
