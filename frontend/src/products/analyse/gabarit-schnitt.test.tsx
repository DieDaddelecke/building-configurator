import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { AnalysisOut, GabaritOut, SectionOut } from "../../api/analysis";
import type { EnvelopeOut } from "../../api/envelope";
import fixture from "../../envelope/__fixtures__/envelope-ad0065.json";
import i18n from "../../i18n";
import { GabaritSchnitt } from "./GabaritSchnitt";

const state = vi.hoisted(() => ({ analysis: null as unknown }));

vi.mock("../../api/analysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/analysis")>()),
  useAnalysis: () => ({ data: state.analysis, isPending: false, isError: false }),
}));

const envelope = fixture as unknown as EnvelopeOut;

/** Rechteck in lokalen Metern (Ost, Nord). */
function rechteck(e0: number, n0: number, e1: number, n1: number): number[][][] {
  return [[[e0, n0], [e1, n0], [e1, n1], [e0, n1], [e0, n0]]];
}

function contour(rings: number[][][], area: number) {
  return { rings_local: rings, area_m2: area, complete: true, reasons: [] };
}

/** Beispiel aus PLAN_AN3_GABARIT 3.2: 20 × 31 m, Seiten H/2 an der Traufe, auf der Grenze bis 3,50 m. */
function gabarit(overrides: Partial<GabaritOut> = {}): GabaritOut {
  return {
    status: "ok",
    reason: null,
    top_m: 10,
    storey_height_m: null,
    reasons: [],
    heights: [{ zone_code: "UB", eave_m: 7, ridge_m: 10, parapet_m: null, derived: false }],
    levels: [
      { from_m: 0, to_m: 3.5, roof: false, contours: { lenient: contour(rechteck(0, 5, 20, 26), 420), strict: contour(rechteck(3, 5, 17, 26), 294) } },
      { from_m: 3.5, to_m: 6, roof: false, contours: { lenient: contour(rechteck(3, 5, 17, 26), 294), strict: contour(rechteck(3, 5, 17, 26), 294) } },
      { from_m: 6, to_m: 7, roof: false, contours: { lenient: contour(rechteck(3.5, 5, 16.5, 26), 273), strict: contour(rechteck(3.5, 5, 16.5, 26), 273) } },
      { from_m: 7, to_m: 10, roof: true, contours: { lenient: contour(rechteck(3.5, 5, 16.5, 26), 273), strict: contour(rechteck(3.5, 5, 16.5, 26), 273) } },
    ],
    terrain_status: "unavailable",
    terrain_slope_percent: null,
    ...overrides,
  };
}

function section(key: "A" | "B", terrain: number[][] = []): SectionOut {
  const a = key === "A";
  return {
    key,
    terrain,
    start_local: a ? [10, 31] : [20, 15.5],
    end_local: a ? [10, 0] : [0, 15.5],
    length_m: a ? 31 : 20,
    parcel: [[0, a ? 31 : 20]],
    crossings: a
      ? [
          { s: 0, edge_seq: 3, kind: "street", inward: 1 },
          { s: 31, edge_seq: 1, kind: "rear", inward: -1 },
        ]
      : [
          { s: 0, edge_seq: 2, kind: "side", inward: 1 },
          { s: 20, edge_seq: 4, kind: "side", inward: -1 },
        ],
    levels: [
      { from_m: 0, to_m: 3.5, roof: false, intervals: { lenient: [a ? [5, 26] : [0, 20]], strict: [a ? [5, 26] : [3, 17]] } },
      { from_m: 3.5, to_m: 6, roof: false, intervals: { lenient: [a ? [5, 26] : [3, 17]], strict: [a ? [5, 26] : [3, 17]] } },
    ],
    height_lines: [
      { zone_code: "UB", kind: "eave", height_m: 7, start: 0, end: a ? 31 : 20, derived: false },
      { zone_code: "UB", kind: "ridge", height_m: 10, start: 0, end: a ? 31 : 20, derived: false },
    ],
    prospects: a
      ? [{ edge_seq: 3, reading: "strict", points: [[5, 0], [5, 10]] }]
      : [
          { edge_seq: 2, reading: "lenient", points: [[0, 0], [0, 3.5], [3, 3.501], [3, 6], [3.5, 7], [3.5, 10]] },
          { edge_seq: 2, reading: "strict", points: [[3, 0], [3, 6], [3.5, 7], [3.5, 10]] },
        ],
  };
}

function analysis(overrides: Partial<AnalysisOut> = {}): AnalysisOut {
  return {
    simulation: true,
    status: "ok",
    reason: null,
    engine_version: "an3-1.1.0",
    input_hash: "sha256:abc",
    assumptions: {
      values: { storey_height_m: { low: 2.7, high: 3 }, wall_share: { low: 0.08, high: 0.15 }, attic_share: { low: 0.5, high: 0.75 }, attique_share: { low: 0.6, high: 0.8 } },
      defaults: { storey_height_m: { low: 2.7, high: 3 }, wall_share: { low: 0.08, high: 0.15 }, attic_share: { low: 0.5, high: 0.75 }, attique_share: { low: 0.6, high: 0.8 } },
      custom: false,
    },
    footprint: {},
    floor_area: null,
    parts: [],
    not_counted: [],
    supplements: [],
    supplement_stricter: [],
    warnings: [],
    gabarit: gabarit(),
    sections: [section("A"), section("B")],
    ...overrides,
  };
}

function zeige() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <GabaritSchnitt projectId="p1" envelope={envelope} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.analysis = analysis();
});

it("listet die Höhenstufen mit Fläche in beiden Auslegungen", () => {
  zeige();
  const tabelle = screen.getByRole("table", { name: "Höhenstufen des Gabarits" });
  const erste = within(tabelle).getByTestId("gabarit-stufe-0");
  expect(erste).toHaveTextContent("0,00 – 3,50 m");
  expect(erste).toHaveTextContent("420 m²294 m²");
  expect(within(tabelle).getByTestId("gabarit-stufe-3")).toHaveTextContent("Dachzone über der Traufe");
  expect(screen.getByText(/Gelände nicht bekannt – eben dargestellt/)).toBeInTheDocument();
});

it("wechselt im Lageplan zwischen weitester und engster Auslegung", async () => {
  zeige();
  const weit = screen.getByTestId("gabarit-kontur-0").getAttribute("d");
  expect(screen.getByRole("button", { name: "weiteste Auslegung" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "engste Auslegung" }));
  expect(screen.getByTestId("gabarit-kontur-0").getAttribute("d")).not.toBe(weit);
  expect(screen.getByTestId("schnittlinie-A")).toBeInTheDocument();
  expect(screen.getByTestId("schnittlinie-B")).toBeInTheDocument();
});

it("zeigt den Schnitt A–A' und wechselt zu B–B'", async () => {
  zeige();
  const schnitt = screen.getByRole("img", { name: /Schnitt A–A'/ });
  expect(within(schnitt).getByTestId("schnitt-grenze-3")).toHaveTextContent("Straße 3");
  expect(within(schnitt).getByTestId("schnitt-grenze-1")).toHaveTextContent("hinten 1");
  expect(within(schnitt).getByText("Traufe 7,00")).toBeInTheDocument();
  expect(within(schnitt).getByText("First 10,00")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Schnitt B–B' längs zur Straße" }));
  const quer = screen.getByRole("img", { name: /Schnitt B–B'/ });
  expect(within(quer).getByTestId("schnitt-grenze-2")).toHaveTextContent("seitlich 2");
  expect(within(quer).getByTestId("schnitt-abstand-2-lenient").getAttribute("d")).toBe(
    "M0.000 0.000L0.000 -3.500L3.000 -3.501L3.000 -6.000L3.500 -7.000L3.500 -10.000",
  );
  expect(within(quer).getByTestId("schnitt-stufe-lenient-0-0")).toHaveAttribute("width", "20");
});

it("ohne Unterschied der Auslegungen gibt es keinen Wechsel", () => {
  const gleich = gabarit();
  gleich.levels = gleich.levels.map((level) => ({ ...level, contours: { lenient: level.contours.strict!, strict: level.contours.strict! } }));
  state.analysis = analysis({ gabarit: gleich });
  zeige();
  expect(screen.queryByRole("button", { name: "engste Auslegung" })).not.toBeInTheDocument();
});

it("zeigt das Geländeprofil im Schnitt und prüft ab 5 % den Höhenbezug", () => {
  // Hang von +0,80 m an der Straße bis −0,75 m hinten, Bezugshöhe 52,40 m NGF
  const profil = [[0, 0.8], [15.5, 0.02], [31, -0.75]];
  state.analysis = analysis({
    gabarit: gabarit({ terrain_status: "ok", terrain_slope_percent: 5.0, reference_altitude_ngf: 52.4 }),
    sections: [section("A", profil), section("B")],
  });
  zeige();
  const schnitt = screen.getByRole("img", { name: /Schnitt A–A'/ });
  const gelaende = within(schnitt).getByTestId("schnitt-gelaende-A");
  expect(gelaende.querySelectorAll("path")[1]?.getAttribute("d")).toBe("M0.000 -0.800L15.500 -0.020L31.000 0.750");
  expect(screen.getByText(/Gelände mit 5,0 % Neigung im Schnitt als Profil/)).toHaveTextContent("52,40 m NGF = ±0,00");

  cleanup();
  state.analysis = analysis({
    gabarit: gabarit({ terrain_status: "ok", terrain_slope_percent: 8.2, reference_altitude_ngf: 52.4 }),
    sections: [section("A", profil), section("B")],
  });
  zeige();
  expect(screen.getByText(/Geländeneigung 8,2 % – Höhenbezug nach PLU prüfen \(Messpunkt der Höhe\)/)).toBeInTheDocument();
  // Ohne Profil bleibt der Boden eben
  expect(screen.queryByTestId("schnitt-gelaende-B")).not.toBeInTheDocument();
});

it("erklärt, warum es keinen Gabarit gibt", () => {
  state.analysis = analysis({ gabarit: gabarit({ status: "unavailable", reason: "height_unknown", levels: [], top_m: null }), sections: [] });
  zeige();
  expect(screen.getByText("Ohne ermittelte Höchsthöhe gibt es keinen Gabarit.")).toBeInTheDocument();
});
