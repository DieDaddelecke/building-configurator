import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { DocumentChapterOut, OcrOut, ProjectRegulationOut } from "../api/regulations";
import i18n from "../i18n";
import { Bebauungsplan } from "./Bebauungsplan";

const state = vi.hoisted(() => ({
  regulations: [] as unknown[],
  upload: vi.fn(),
  choose: vi.fn(),
  remove: vi.fn(),
  ocr: vi.fn(),
}));

vi.mock("../api/regulations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/regulations")>()),
  useProjectRegulations: () => ({ data: state.regulations, isPending: false, isError: false, isSuccess: true }),
  useUploadRegulation: () => ({ mutate: state.upload, reset: vi.fn(), isPending: false, error: null }),
  useChooseZone: () => ({ mutate: state.choose, isPending: false, error: null }),
  useRemoveRegulation: () => ({ mutate: state.remove, isPending: false, isError: false }),
  useRequestOcr: () => ({ mutate: state.ocr, isPending: false, error: null }),
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

const ocr = (overrides: Partial<OcrOut> = {}): OcrOut => ({
  state: "offered",
  pages_total: 74,
  pages_done: 0,
  uncertain_pages: [],
  still_empty_pages: [],
  estimated_seconds: 222,
  error: null,
  ...overrides,
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
  state.ocr.mockReset();
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
  expect(screen.getByText(/Es fehlt der Schlüssel von OpenRouter/)).toBeInTheDocument();
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

it("bittet bei einem alten Fehler „ohne Text“ um erneutes Hochladen", () => {
  state.regulations = [regulation({}, { status: "failed", error: "document_no_text", chapters: [] })];
  zeige();
  expect(screen.getByRole("alert")).toHaveTextContent("Bitte erneut hochladen");
});

// AN7: gescannte Reglements (docs/PLAN_AN7_SCAN.md 3.2, 3.7)

it("nennt vor der Texterkennung Seiten, Dauer und Grenzen", async () => {
  state.regulations = [regulation({}, { status: "scan", page_count: 74, chapters: [], ocr: ocr() })];
  zeige();
  const hinweis = screen.getByRole("note");
  expect(hinweis).toHaveTextContent("Dieses PDF ist ein Scan (74 von 74 Seiten ohne Text)");
  expect(hinweis).toHaveTextContent("das dauert etwa 4 Minuten");
  expect(hinweis).toHaveTextContent("Tabellen und Handschrift werden schlecht gelesen");
  // Ohne erkannten Text keine Zonenwahl
  expect(screen.queryByLabelText("Zone oder Sektor des Grundstücks")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Text erkennen" }));
  expect(state.ocr).toHaveBeenCalled();
});

it("zeigt den Fortschritt der Texterkennung", () => {
  state.regulations = [
    regulation({}, { status: "scan", chapters: [], ocr: ocr({ state: "running", pages_done: 40, estimated_seconds: 102 }) }),
  ];
  zeige();
  expect(screen.getByText(/Texterkennung: Seite 40 von 74/)).toBeInTheDocument();
  expect(screen.getByText(/noch etwa 2 Minuten/)).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Fortschritt der Texterkennung" })).toHaveAttribute("value", "40");
  expect(screen.getByText(/Andere Aufgaben laufen dazwischen weiter/)).toBeInTheDocument();
});

it("fasst die Texterkennung zusammen und gibt die Zonenwahl frei", () => {
  state.regulations = [
    regulation(
      {},
      {
        empty_pages: Array.from({ length: 74 }, (_, index) => index + 1),
        ocr: ocr({ state: "done", pages_done: 74, uncertain_pages: [12, 40, 41], still_empty_pages: [70, 74], estimated_seconds: 0 }),
      },
    ),
  ];
  zeige();
  expect(
    screen.getByText("74 Seiten per Texterkennung gelesen, davon 3 unsicher (S. 12, 40, 41); 2 auch danach ohne Text (S. 70, 74)"),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Seiten ohne Text (z. B. Pläne)/)).not.toBeInTheDocument();
  expect(screen.getByLabelText("Zonenkapitel")).toHaveValue("Uh");
});

it("bietet für einzelne leere Seiten die Texterkennung an", async () => {
  state.regulations = [
    regulation({}, { empty_pages: [7, 8], ocr: ocr({ state: "none", pages_total: 2, estimated_seconds: 6 }) }),
  ];
  zeige();
  expect(screen.getByText(/2 Seiten ohne Text/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Text dieser 2 Seiten erkennen (etwa eine Minute)" }));
  expect(state.ocr).toHaveBeenCalled();
});

it("setzt eine unterbrochene Texterkennung fort", async () => {
  state.regulations = [
    regulation(
      {},
      { status: "scan", chapters: [], ocr: ocr({ state: "failed", pages_done: 20, error: "interrupted:TimeoutError" }) },
    ),
  ];
  zeige();
  expect(screen.getByText(/bereits erkannte Seiten bleiben erhalten/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  expect(state.ocr).toHaveBeenCalled();
});

it("nennt den Grund, wenn auch nach der Texterkennung kein Text da ist", () => {
  state.regulations = [
    regulation({}, { status: "failed", error: "ocr_no_text", chapters: [], ocr: ocr({ state: "failed", error: "ocr_no_text" }) }),
  ];
  zeige();
  expect(screen.getByRole("alert")).toHaveTextContent("Auch nach der Texterkennung ist mehr als die Hälfte");
});

it("nimmt ein Zusatzdokument nicht für den Bebauungsplan", () => {
  state.regulations = [regulation({ role: "supplement", zone_code: "Lot-12" }, { id: "s1", title: "Lotissement" })];
  zeige();
  expect(screen.queryByText("Lotissement")).not.toBeInTheDocument();
  expect(screen.getByLabelText("règlement écrit (PDF)")).toBeInTheDocument();
});
