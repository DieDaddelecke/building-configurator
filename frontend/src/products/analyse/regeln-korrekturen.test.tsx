import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { AnalysisComparisonOut } from "../../api/analysis";
import type { ProjectOverrideOut, ProjectRulesOut, RuleOut } from "../../api/rules";
import i18n from "../../i18n";
import kinds from "../../rules/__fixtures__/rule-kinds.json";
import { RegelnKorrekturen } from "./RegelnKorrekturen";

const state = vi.hoisted(() => ({
  overrides: [] as unknown[],
  put: vi.fn(),
  remove: vi.fn(),
  comparisons: {} as Record<string, unknown>,
  requested: [] as (string | null)[],
}));

vi.mock("../../api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/rules")>()),
  useRuleKinds: () => ({ data: kinds, isPending: false }),
  useOwnOverrides: () => ({ data: state.overrides }),
  usePutOwnOverride: () => ({ mutate: state.put, isPending: false, error: null }),
  useDeleteOwnOverride: () => ({ mutate: state.remove, isPending: false, isError: false }),
  useNotices: () => ({ data: [] }),
}));

vi.mock("../../api/regulations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/regulations")>()),
  useProjectRegulations: () => ({
    data: [
      {
        role: "plu",
        zone_code: "Uh",
        chapter_code: "Uh",
        document: { id: "plu", title: "PLUi Erdre et Gesvres", page_count: 24 },
      },
    ],
  }),
}));

vi.mock("../../api/analysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/analysis")>()),
  useAnalysisComparison: (_projectId: string, base: string | null) => {
    state.requested.push(base);
    return base === null ? { data: undefined, isPending: true, isError: false } : { data: state.comparisons[base], isPending: false, isError: false };
  },
}));

vi.mock("../../site/GrundstueckPruefen", () => ({ useNotices: () => ({ data: [] }) }));

const rule = (kind: string, params: Record<string, unknown>, extra: Partial<RuleOut> = {}): RuleOut => ({
  kind,
  building_kind: "main",
  status: "effective",
  reason: null,
  params,
  page: 8,
  quote: "Zitat",
  quote_verified: true,
  source_url: "/api/v1/regulation-files/f1#page=8",
  confidence: 0.9,
  notes: null,
  origin: "extraction",
  source_document_id: "plu",
  ...extra,
});

const rules = (zoneRules: RuleOut[]): ProjectRulesOut => ({
  simulation: true,
  status: "ok",
  reason: null,
  commune_insee: null,
  plan: { id: "plu", origin: "upload", title: "PLUi Erdre et Gesvres", du_type: "PLUi", gpu_doc_id: null, gpu_update_date: null, regulation_url: null },
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
      rules: zoneRules,
      hints: [],
    },
  ],
  ignored_zones: [],
  uncovered_share: 0,
  overlays: [],
  warnings: [],
  notices: [],
});

const override = (extra: Partial<ProjectOverrideOut> = {}): ProjectOverrideOut => ({
  id: "o1",
  zone_code: "Uh",
  kind: "max_height",
  building_kind: "main",
  status: "effective",
  params: { eave_m: 7, ridge_m: 8 },
  note: "Lotissement Les Chênes, article 10",
  source: {
    document_id: "lot",
    document_title: "Lotissement",
    page: 2,
    quote: "8 mètres au faîtage",
    quote_verified: true,
    source_url: "/api/v1/regulation-files/f2#page=2",
    attached: true,
  },
  active: true,
  created_at: "2026-09-28T08:00:00Z",
  created_by: "staff:1",
  updated_at: "2026-09-28T08:00:00Z",
  updated_by: "staff:1",
  ...extra,
});

function renderPage(data: ProjectRulesOut) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RegelnKorrekturen projectId="p1" rules={data} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.overrides = [];
  state.comparisons = {};
  state.requested = [];
  state.put.mockReset();
  state.remove.mockReset();
});

it("korrigiert eine gelesene Regel mit der Fundstelle der Auswertung als Vorschlag", async () => {
  const user = userEvent.setup();
  renderPage(rules([rule("max_footprint_ratio", { ratio: 0.25 })]));
  const zeile = screen.getByRole("row", { name: /Grundfläche/ });
  await user.click(within(zeile).getByRole("button", { name: "Korrigieren" }));
  const formular = screen.getByRole("form", { name: "Korrektur: Grundfläche" });
  expect(within(formular).getByLabelText(/Anteil/)).toHaveValue("25");
  expect(within(formular).getByLabelText("Dokument")).toHaveValue("plu");
  expect(within(formular).getByLabelText("Seite")).toHaveValue("8");
  await user.clear(within(formular).getByLabelText(/Anteil/));
  await user.type(within(formular).getByLabelText(/Anteil/), "20");
  await user.type(within(formular).getByLabelText("Begründung"), "Modification n° 2");
  await user.click(within(formular).getByRole("button", { name: "Korrektur speichern" }));
  expect(state.put).toHaveBeenCalledWith(
    expect.objectContaining({
      zone_code: "Uh",
      kind: "max_footprint_ratio",
      params: { ratio: 0.2 },
      source: { document_id: "plu", page: 8, quote: "Zitat" },
    }),
    expect.anything(),
  );
});

it("zeigt Korrekturen mit Seite, Begründung und Zurücknehmen", async () => {
  const user = userEvent.setup();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  state.overrides = [override()];
  renderPage(
    rules([
      rule("max_height", { eave_m: 7, ridge_m: 8 }, { origin: "project", page: 2, source_url: "/api/v1/regulation-files/f2#page=2", source_document_id: "lot" }),
    ]),
  );
  const zeile = screen.getByRole("row", { name: /Höhe/ });
  expect(within(zeile).getByRole("link", { name: "S. 2" })).toBeInTheDocument();
  expect(within(zeile).getByText(/Korrektur/)).toBeInTheDocument();
  expect(within(zeile).getByText("Begründung: Lotissement Les Chênes, article 10")).toBeInTheDocument();
  await user.click(within(zeile).getByRole("button", { name: "Zurücknehmen" }));
  expect(state.remove).toHaveBeenCalledWith("o1");
  await user.click(within(zeile).getByRole("button", { name: "Ändern" }));
  expect(screen.getByLabelText("Begründung")).toHaveValue("Lotissement Les Chênes, article 10");
});

it("ergänzt nur Arten, die fehlen, und listet nicht wirksame Korrekturen", async () => {
  const user = userEvent.setup();
  state.overrides = [override({ id: "o2", zone_code: "Ub", kind: "max_footprint_ratio", params: { ratio: 0.3 }, active: false })];
  renderPage(rules([rule("max_footprint_ratio", { ratio: 0.25 }), rule("max_height", { eave_m: 7 })]));
  expect(screen.getByRole("heading", { name: "Nicht wirksame Korrekturen" })).toBeInTheDocument();
  expect(screen.getByText(/Zone Ub · Grundfläche · ≤ 30 %/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Regel ergänzen" }));
  const optionen = within(screen.getByLabelText("Regel")).getAllByRole("option").map((o) => o.textContent);
  expect(optionen).not.toContain("Grundfläche");
  expect(optionen).not.toContain("Höhe");
  expect(optionen).toContain("Stellplätze");
});

const comparison = (extra: Partial<AnalysisComparisonOut>): AnalysisComparisonOut => ({
  simulation: true,
  kind: "corrections",
  base: "automatic",
  left: { corrections: false, version: null, status: "ok", reason: null },
  right: { corrections: true, version: null, status: "ok", reason: null },
  bases: [{ base: "automatic", kind: "corrections", zone_code: null, version: null }],
  figures: [
    { key: "footprint_strict", unit: "m2", left: 150, right: 120, changed: true },
    { key: "height_top", unit: "m", left: 10, right: 10, changed: false },
  ],
  rules: [
    {
      zone_code: "Uh",
      kind: "max_footprint_ratio",
      building_kind: "main",
      left: { key: "max_footprint_ratio", kind: "max_footprint_ratio", building_kind: "main", status: "effective", reason: null, params: { ratio: 0.25 }, citation: null },
      right: { key: "max_footprint_ratio", kind: "max_footprint_ratio", building_kind: "main", status: "effective", reason: null, params: { ratio: 0.2 }, citation: null },
      changed: true,
    },
  ],
  ...extra,
});

it("vergleicht zwei Stände erst beim Öffnen", async () => {
  const user = userEvent.setup();
  state.comparisons.automatic = comparison({});
  renderPage(rules([rule("max_footprint_ratio", { ratio: 0.25 })]));
  expect(state.requested.every((base) => base === null)).toBe(true);
  await user.click(screen.getByText("Stände vergleichen"));
  const kennzahlen = screen.getByRole("table", { name: "Kennzahlen beider Stände" });
  expect(within(kennzahlen).getByRole("columnheader", { name: "ohne Korrekturen" })).toBeInTheDocument();
  const zeile = within(kennzahlen).getByRole("row", { name: /Bindende Grundfläche \(eng\)/ });
  expect(zeile).toHaveTextContent("150 m²");
  expect(zeile).toHaveTextContent("120 m²");
  expect(screen.getByRole("heading", { name: "Eine geänderte Regel" })).toBeInTheDocument();
  const regeln = screen.getByRole("table", { name: "Regeln, die sich zwischen den Ständen unterscheiden" });
  expect(within(regeln).getByRole("row", { name: /Grundfläche/ })).toHaveTextContent("≤ 20 %");
});

it("bietet ohne Korrekturen den Vergleich der Auswertungen an", async () => {
  const user = userEvent.setup();
  const version = {
    id: "v1",
    version: 1,
    status: "retired" as const,
    origin: "extraction" as const,
    model: null,
    created_at: "2026-09-26T08:00:00Z",
    created_by: null,
    note: null,
    coverage: {},
    open_passages: [],
    out_of_scope_passages: [],
  };
  state.comparisons.automatic = comparison({ bases: [{ base: "v1", kind: "versions", zone_code: "Uh", version }] });
  state.comparisons.v1 = comparison({
    kind: "versions",
    base: "v1",
    left: { corrections: false, version, status: "ok", reason: null },
    right: { corrections: false, version: { ...version, id: "v2", version: 2, status: "simulated" }, status: "ok", reason: null },
    bases: [{ base: "v1", kind: "versions", zone_code: "Uh", version }],
  });
  renderPage(rules([rule("max_footprint_ratio", { ratio: 0.25 })]));
  await user.click(screen.getByText("Stände vergleichen"));
  expect(screen.getByLabelText("Vergleich")).toHaveValue("v1");
  const kennzahlen = screen.getByRole("table", { name: "Kennzahlen beider Stände" });
  expect(within(kennzahlen).getByRole("columnheader", { name: "v1 vom 26.9.2026" })).toBeInTheDocument();
  expect(state.requested).toContain("v1");
});

it("zeigt die Abdeckung der Textstellen und lässt nicht Gefundenes als nicht geregelt bestätigen", async () => {
  const user = userEvent.setup();
  const data = rules([
    rule("facade", {}, { status: "unknown", reason: "not_found_after_search", search_note: "Art. 11, façades", page: null, quote: null }),
    rule("max_footprint_ratio", {}, { status: "unknown", reason: "not_expressible", search_note: "14", page: null, quote: null }),
  ]);
  data.plan = { ...data.plan!, regulation_url: "/api/v1/regulation-files/f1" };
  data.zones[0]!.version = {
    id: "v3",
    version: 3,
    status: "simulated",
    origin: "extraction",
    model: "anthropic/claude-opus-5.5",
    created_at: "2026-09-28T20:00:00Z",
    created_by: null,
    note: null,
    coverage: { passages_total: 48, passages_assigned: 40, passages_open: 2, passages_out_of_scope: 6, gap_search: 1 },
    open_passages: [{ page: 13, text: "Les pompes à chaleur ne doivent pas être installées à moins de 4 mètres des limites." }],
    out_of_scope_passages: [{ page: 11, text: "Les eaux usées doivent être séparées des eaux pluviales.", reason: "networks" }],
  };
  renderPage(data);

  const abdeckung = screen.getByTestId("abdeckung");
  expect(abdeckung).toHaveTextContent("Abdeckung: 40 von 48 Vorschriften zugeordnet, 2 offen");
  expect(within(abdeckung).getByText("Eine Vorschrift ohne Regel")).toBeInTheDocument();
  expect(within(abdeckung).getByRole("link", { name: "S. 13" })).toHaveAttribute("href", "/api/v1/regulation-files/f1#page=13");
  expect(within(abdeckung).getByText("Netze")).toBeInTheDocument();
  expect(screen.getByText("nicht ermittelt: nach Nachsuche nicht gefunden")).toBeInTheDocument();
  expect(screen.getByText("Geprüft: Art. 11, façades")).toBeInTheDocument();
  expect(screen.getByText(/Die Vorschrift steht als Hinweis \(S\. 14\)/)).toBeInTheDocument();

  // Nur die nicht gefundene Angabe bietet die Bestätigung an; das Formular steht auf „nicht geregelt“
  expect(screen.getAllByRole("button", { name: "als nicht geregelt bestätigen" })).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "als nicht geregelt bestätigen" }));
  expect(screen.getByLabelText("Status")).toHaveValue("not_regulated");
});

it("zeigt ohne Zählung (ältere Auswertung) keine Abdeckung", () => {
  renderPage(rules([rule("max_footprint_ratio", { ratio: 0.25 })]));
  expect(screen.queryByTestId("abdeckung")).not.toBeInTheDocument();
});
