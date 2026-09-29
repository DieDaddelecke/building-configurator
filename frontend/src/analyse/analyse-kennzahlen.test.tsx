import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { AnalysisOut } from "../api/analysis";
import type { EnvelopeOut } from "../api/envelope";
import fixture from "../envelope/__fixtures__/envelope-ad0065.json";
import i18n from "../i18n";
import { Analyse } from "./Analyse";

const state = vi.hoisted(() => ({ analysis: null as unknown, save: vi.fn(), reset: vi.fn() }));

vi.mock("../api/analysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/analysis")>()),
  useAnalysis: () => ({ data: state.analysis, isPending: false, isError: false }),
  useSaveAnalysisParameters: () => ({ mutate: state.save, isPending: false, isError: false }),
  useResetAnalysisParameters: () => ({ mutate: state.reset, isPending: false }),
}));

const envelope = fixture as unknown as EnvelopeOut;
const citation = { page: 9, quote: "25%", quote_verified: true, source_url: "/api/v1/regulation-files/f1#page=9", origin: "extraction" as const, confidence: 0.9, notes: null, from_scan: false };
const span = (low: number, high: number) => ({ low, high });
const parameters = {
  storey_height_m: span(2.7, 3),
  wall_share: span(0.08, 0.15),
  attic_share: span(0.5, 0.75),
  attique_share: span(0.6, 0.8),
};
const footprint = {
  value_m2: 150,
  binding: "ratio" as const,
  complete: true,
  reasons: [],
  candidates: [
    { source: "contour" as const, value_m2: 336, status: "effective", citation: null },
    { source: "ratio" as const, value_m2: 150, status: "effective", citation },
  ],
};

function analysis(overrides: Partial<AnalysisOut> = {}): AnalysisOut {
  return {
    simulation: true,
    status: "ok",
    reason: null,
    engine_version: "an3-1.1.0",
    input_hash: "sha256:abc",
    assumptions: { values: parameters, defaults: parameters, custom: false },
    footprint: { strict: { value_m2: 150, complete: true }, lenient: { value_m2: 150, complete: true } },
    floor_area: { low_m2: 255, high_m2: 380, complete: true, capped: false, reasons: [] },
    parts: [
      {
        zone_code: "Uh",
        area_m2: 600,
        excluded: null,
        footprint: { strict: footprint, lenient: { ...footprint, candidates: [{ ...footprint.candidates[0]!, value_m2: 600 }, footprint.candidates[1]!] } },
        storeys: {
          full_min: 2,
          full_max: 2,
          top: "attic",
          top_certain: false,
          source: "eave",
          status: "effective",
          citation,
          notes: ["attic_possible"],
        },
        floor_area: {
          low_m2: 255,
          high_m2: 379.5,
          cap_m2: null,
          capped: false,
          complete: true,
          reasons: [],
          cap_citation: null,
          storeys_low: [],
          storeys_high: [
            { level_m: 2.7, area_m2: 150, share: 1 },
            { level_m: 5.4, area_m2: 150, share: 1 },
            { level_m: 5.4, area_m2: 150, share: 0.75 },
          ],
          notes: [],
        },
      },
    ],
    not_counted: ["stairs_lifts", "parking"],
    supplements: [],
    supplement_stricter: [],
    warnings: [],
    gabarit: null,
    sections: [],
    ...overrides,
  };
}

function zeige() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Analyse projectId="p1" envelope={envelope} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.analysis = analysis();
  state.save.mockReset();
  state.reset.mockReset();
});

it("zeigt die drei Kennzahlen mit bindendem Wert und Quelle", () => {
  zeige();
  const grundflaeche = screen.getByText("Bindende Grundfläche").parentElement!;
  expect(within(grundflaeche).getByText("150 m²")).toBeInTheDocument();
  expect(screen.getByText("die Grundflächenzahl bindet")).toBeInTheDocument();
  expect(screen.getAllByText("2 + Dachgeschoss möglich")[0]).toBeInTheDocument();
  expect(screen.getAllByText("aus der Traufhöhe")[0]).toBeInTheDocument();
  expect(screen.getAllByText("255 – 380 m²")[0]).toBeInTheDocument();
  const herleitung = screen.getByRole("table", { name: "Herleitung für Zone Uh" });
  const ratio = within(herleitung).getByRole("row", { name: /Grundflächenzahl/ });
  expect(ratio).toHaveTextContent("bindet");
  expect(within(ratio).getByRole("link", { name: "S. 9" })).toHaveAttribute("href", "/api/v1/regulation-files/f1#page=9");
  expect(within(herleitung).getByRole("row", { name: /Bebaubare Fläche/ })).toHaveTextContent("336 m²600 m²");
  expect(within(herleitung).getByText("Geschossflächen oben: 150 · 150 · 75 % von 150 m²")).toBeInTheDocument();
  expect(screen.queryByText("Der Gabarit begrenzt die oberen Geschosse.")).not.toBeInTheDocument();
});

it("sagt, wenn der Gabarit die oberen Geschosse begrenzt", () => {
  const part = analysis().parts[0]!;
  state.analysis = analysis({
    parts: [{ ...part, floor_area: { ...part.floor_area, notes: ["gabarit_limits_storeys"] } }],
  });
  zeige();
  expect(screen.getByText("Der Gabarit begrenzt die oberen Geschosse.")).toBeInTheDocument();
});

it("nennt Abstände je Grenze im Klartext und was nicht gerechnet ist", () => {
  zeige();
  expect(screen.getByTestId("abstand-1")).toHaveTextContent("auf der Grenze zulässig, sonst mindestens 3,00 m");
  expect(screen.getByTestId("abstand-4")).toHaveTextContent("zwischen 5,00 m und 20,00 m (ganzer Baukörper im Band)");
  expect(screen.getByText("Treppen- und Aufzugsöffnungen")).toBeInTheDocument();
});

it("warnt vor strengeren Zusatzdokumenten und markiert Obergrenzen", () => {
  state.analysis = analysis({
    supplement_stricter: ["max_area", "max_height"],
    footprint: { strict: { value_m2: 336, complete: false }, lenient: { value_m2: 600, complete: false } },
  });
  zeige();
  expect(screen.getByRole("note")).toHaveTextContent("Ein Zusatzdokument ist strenger bei: Höchstflächen, Höhe.");
  expect(screen.getByText("höchstens – Grundflächenzahl nicht ermittelt")).toBeInTheDocument();
});

it("ändert die Annahmen in Prozent und schickt Anteile", async () => {
  zeige();
  await userEvent.click(screen.getByText("Annahmen"));
  const low = screen.getByLabelText("von", { selector: `[id$="wall_share-low"]` });
  await userEvent.clear(low);
  await userEvent.type(low, "10");
  await userEvent.click(screen.getByRole("button", { name: "Annahmen übernehmen" }));
  expect(state.save).toHaveBeenCalledWith({
    storey_height_m: { low: 2.7, high: 3 },
    wall_share: { low: 0.1, high: 0.15 },
    attic_share: { low: 0.5, high: 0.75 },
    attique_share: { low: 0.6, high: 0.8 },
  });
});

it("erklärt, warum es noch keine Analyse gibt", () => {
  state.analysis = analysis({ status: "unavailable", reason: "upload", parts: [], floor_area: null });
  zeige();
  expect(screen.getByText(/Die Analyse braucht den Baurahmen/)).toBeInTheDocument();
});
