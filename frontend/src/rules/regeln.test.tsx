import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProjectRulesOut, RuleOut } from "../api/rules";
import i18n from "../i18n";
import fixture from "./__fixtures__/rules-ad0065.json";
import { ruleValue } from "./format";
import { RegelnSimulation } from "./RegelnSimulation";

// Echte Antwort der API für Treillières AD 65 (Zone Uh) nach zwei Läufen, die bei der Grundfläche abweichen
const rules = fixture as unknown as ProjectRulesOut;

function renderRegeln(data: ProjectRulesOut = rules) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RegelnSimulation rules={data} />
    </QueryClientProvider>,
  );
}

function rule(partial: Partial<RuleOut>): RuleOut {
  return {
    kind: "setback_street",
    building_kind: "main",
    status: "effective",
    reason: null,
    params: {},
    page: null,
    quote: null,
    quote_verified: false,
    source_url: null,
    confidence: 1,
    notes: null,
    origin: "extraction",
    ...partial,
  };
}

describe("Regeln als Simulation", () => {
  beforeEach(async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    await act(() => i18n.changeLanguage("de"));
  });

  it("kennzeichnet die Simulation und zeigt Werte mit Quelle", () => {
    renderRegeln();
    expect(screen.getByRole("note")).toHaveTextContent("Simulation – unverbindlich.");
    const table = screen.getByRole("table", { name: "Regeln der Zone Uh" });
    const street = within(table).getByRole("row", { name: /^Abstand zur Straße 5–20 m/ });
    const link = within(street).getByRole("link", { name: "S. 9" });
    expect(link.getAttribute("href")).toMatch(/244400503_reglement_20260304\.pdf#page=9$/);
    expect(within(table).getByRole("row", { name: /^Seitlicher Abstand auf der Grenze oder ≥ 3 m/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /^Höhe Traufe ≤ 7 m · First ≤ 10 m/ })).toBeInTheDocument();
  });

  it("zeigt unsichere Werte als nicht ermittelt statt zu schätzen", () => {
    renderRegeln();
    const table = screen.getByRole("table", { name: "Regeln der Zone Uh" });
    expect(within(table).getByRole("row", { name: /^Grundfläche nicht ermittelt: Text mehrdeutig/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /^Dach nicht ermittelt/ })).toBeInTheDocument();
    expect(screen.getByText(/Volumes simples/)).toHaveAttribute("lang", "fr");
    expect(screen.getByText(/keine Bauauskunft/)).toBeInTheDocument();
    expect(screen.getByText(/Lotissement/)).toBeInTheDocument();
  });

  it("nennt den Grund, wenn keine Simulation möglich ist, und zeigt Vorgaben", () => {
    renderRegeln({ ...rules, status: "unavailable", reason: "rnu", plan: null, zones: [], overlays: [{ category: "servitude", type_code: "i4", label: "I4 – Zone de protection", endpoint: "assiette-sup-s" }] });
    expect(screen.getByText(/nationale Recht \(RNU\)/)).toBeInTheDocument();
    expect(screen.getByText("I4 – Zone de protection")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("formatiert Werte je Regelart auf Französisch", async () => {
    await act(() => i18n.changeLanguage("fr"));
    const t = i18n.t.bind(i18n);
    expect(ruleValue(rule({ params: { mode: "alignment" } }), t, "fr")).toBe("à l'alignement");
    expect(ruleValue(rule({ kind: "max_footprint_ratio", params: { ratio: 0.4 } }), t, "fr")).toBe("≤ 40 %");
    expect(
      ruleValue(rule({ kind: "setback_side", params: { min_m: 3, height_factor: 0.5, height_basis: "eave" } }), t, "fr"),
    ).toBe("≥ 3 m · 0,5 × hauteur à l'égout");
    expect(ruleValue(rule({ kind: "roof", params: { allowed_forms: ["gable", "hip"], pitch_min_deg: 35, pitch_max_deg: 45 } }), t, "fr")).toBe(
      "deux pans, quatre pans · 35–45°",
    );
    expect(ruleValue(rule({ kind: "parking", params: { spaces_per_m2_sdp: 0.02 } }), t, "fr")).toBe("1 pour 50 m² de surface de plancher");
    expect(ruleValue(rule({ status: "not_regulated" }), t, "fr")).toBe("non réglementé");
  });

  it("zeigt jeden Parameter einer wirksamen Regel und nie einen leeren Wert", () => {
    const t = i18n.t.bind(i18n);
    expect(ruleValue(rule({ kind: "facade", params: { materials_forbidden: ["metal"] } }), t, "de")).toBe("nicht Metall");
    expect(ruleValue(rule({ kind: "roof", params: { ridge_orientation: "parallel_to_street" } }), t, "de")).toBe("First parallel zur Straße");
    expect(ruleValue(rule({ kind: "roof", params: { materials_allowed: ["slate"] } }), t, "de")).toBe("Deckung: Schiefer");
    expect(
      ruleValue(rule({ kind: "setback_side", params: { min_m: 3, allow_on_boundary: true, on_boundary_max_height_m: 3.5 } }), t, "de"),
    ).toBe("auf der Grenze oder ≥ 3 m · auf der Grenze höchstens 3,5 m hoch");
    expect(ruleValue(rule({ kind: "max_height", params: { ridge_m: 9, reference: "street_level" } }), t, "de")).toBe(
      "First ≤ 9 m · ab Straßenniveau",
    );
    expect(ruleValue(rule({ kind: "fence", params: { max_height_m: 1.5, materials: ["wood"] } }), t, "de")).toBe("≤ 1,5 m · Holz");
    expect(ruleValue(rule({ kind: "annex", params: {} }), t, "de")).toBe("wirksam");
  });

  it("kennzeichnet Regeln eines vorigen Planstands und nicht erfasste Teilflächen", () => {
    const [first] = rules.zones;
    if (!first) throw new Error("Fixture ohne Zone");
    const zone = { ...first, status: "outdated" as const };
    renderRegeln({ ...rules, zones: [zone], uncovered_share: 0.3, warnings: ["rules_outdated", "zone_coverage_incomplete"] });
    expect(screen.getByText("veraltet (voriger Planstand)")).toBeInTheDocument();
    expect(screen.getByText(/Regeln des vorigen Planstands/)).toBeInTheDocument();
    expect(screen.getByText(/Ein Teil des Grundstücks \(30 %\)/)).toBeInTheDocument();
  });
});
