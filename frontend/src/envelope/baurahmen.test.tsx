import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EnvelopeOut, SheetOut } from "../api/envelope";
import i18n from "../i18n";
import fixture from "./__fixtures__/envelope-ad0065.json";
import { Baurahmen } from "./Baurahmen";

// Der Steckbrief entsteht im Worker; hier zählt nur, was die Oberfläche je Zustand zeigt.
const sheet: { data?: SheetOut; isPending: boolean; isError: boolean; mutate: ReturnType<typeof vi.fn> } = {
  data: undefined,
  isPending: false,
  isError: false,
  mutate: vi.fn(),
};

vi.mock("../api/envelope", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/envelope")>()),
  useRequestSheet: () => sheet,
}));

// Echte Antwort der API für Treillières AD 65 (Zone Uh): Bauband 5–20 m, seitlich auf der Grenze oder 3 m
const envelope = fixture as unknown as EnvelopeOut;

function renderBaurahmen(data: EnvelopeOut = envelope) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Baurahmen envelope={data} projectId="p1" />
    </QueryClientProvider>,
  );
}

describe("Baurahmen als Simulation", () => {
  beforeEach(async () => {
    sheet.data = undefined;
    sheet.mutate.mockClear();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { headers: { "content-type": "application/json" } }),
    );
    await act(() => i18n.changeLanguage("de"));
  });

  it("kennzeichnet die Simulation und nennt beide Auslegungen", () => {
    renderBaurahmen();
    expect(screen.getByText("Simulation – unverbindlich.")).toBeInTheDocument();
    expect(screen.getAllByText(/keine Bauauskunft/).length).toBeGreaterThan(0);
    const lenient = envelope.contours.lenient?.area_m2 ?? 0;
    const strict = envelope.contours.strict?.area_m2 ?? 0;
    expect(strict).toBeLessThan(lenient);
    expect(screen.getAllByText(`${Math.round(lenient)} m²`).length).toBeGreaterThan(0);
    expect(screen.getAllByText(`${Math.round(strict)} m²`).length).toBeGreaterThan(0);
  });

  it("zeigt Grenzwerte und Abstände mit Quelle", () => {
    renderBaurahmen();
    const table = screen.getByRole("table", { name: "Baurahmen der Zone Uh" });
    expect(within(table).getByRole("row", { name: /^Höchste Grundfläche 232 m²/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /^Höhe Traufe ≤ 7 m · First ≤ 10 m/ })).toBeInTheDocument();
    const street = within(table).getByRole("row", { name: /^Grenze zur Straße 4/ });
    expect(street).toHaveTextContent("5,00 m");
    expect(within(street).getByRole("link", { name: /S\. \d+/ })).toBeInTheDocument();
    // Auf der Grenze zulässig: weiteste Auslegung 0 m, engste 3 m
    expect(within(table).getByRole("row", { name: /^Seitliche Grenze 1 0,00 – 3,00 m/ })).toBeInTheDocument();
  });

  it("markiert nicht ermittelte Abstände und die unvollständige engste Kontur", () => {
    const [first, ...rest] = envelope.edges;
    if (!first) throw new Error("Fixture ohne Kanten");
    const unknown = { ...first, lenient_m: null, strict_m: null, markers: ["setback_unknown"] };
    renderBaurahmen({
      ...envelope,
      edges: [unknown, ...rest],
      contours: {
        ...envelope.contours,
        strict: { ...envelope.contours.strict!, complete: false, incomplete_reasons: ["setback_unknown:side:Uh"] },
      },
      warnings: ["setbacks_incomplete"],
    });
    expect(screen.getByText("Abstand nicht ermittelt")).toBeInTheDocument();
    expect(screen.getByText(/Ein Abstand ist nicht ermittelt/)).toBeInTheDocument();
    expect(screen.getByText(/Die Fläche kann zu groß sein/)).toBeInTheDocument();
  });

  it("zeigt Teilflächen ohne Regeln als nicht berechnet", () => {
    const [part] = envelope.parts;
    if (!part) throw new Error("Fixture ohne Teilfläche");
    renderBaurahmen({
      ...envelope,
      status: "partial",
      parts: [part, { ...part, zone_code: "N", zone_status: "unavailable", excluded: "rules_unavailable" }],
      warnings: ["zones_without_rules"],
    });
    expect(screen.getByText(/Die Regeln dieser Zone sind nicht ermittelt/)).toBeInTheDocument();
    expect(screen.getByText(/diese Fläche bleibt frei/)).toBeInTheDocument();
  });

  it("nennt Bauverbotsflächen und überlagernde Vorgaben", () => {
    renderBaurahmen({
      ...envelope,
      constraints: [
        {
          effect: "no_build",
          category: "prescription",
          type_code: "05",
          label: "Emplacement réservé K21",
          endpoint: "prescription-surf",
          area_m2: 40,
          rings_local: [],
          lines_local: [],
        },
      ],
      warnings: ["no_build_area"],
    });
    expect(screen.getByText("Emplacement réservé K21", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/schließt die Bebauung eines Teils aus/)).toBeInTheDocument();
  });

  it("erklärt fehlende und laufende Auswertungen statt zu schätzen", () => {
    renderBaurahmen({ ...envelope, status: "unavailable", reason: "rnu" });
    expect(screen.getByText(/kein auswertbarer Bebauungsplan/)).toBeInTheDocument();
    expect(screen.getByText(/Anfrage an das Architekturbüro/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("fordert den Steckbrief an und zeigt Fortschritt und Ergebnis", async () => {
    renderBaurahmen();
    await userEvent.click(screen.getByRole("button", { name: "Steckbrief als PDF" }));
    expect(sheet.mutate).toHaveBeenCalledTimes(1);

    sheet.data = { status: "pending", input_hash: "sha256:abc", job_id: null, created_at: null };
    renderBaurahmen();
    expect(screen.getAllByText(/Der Steckbrief wird erzeugt/).length).toBeGreaterThan(0);

    sheet.data = { status: "ready", input_hash: "sha256:abc", job_id: null, created_at: null };
    renderBaurahmen();
    const link = screen.getAllByRole("link", { name: "Steckbrief öffnen" })[0];
    expect(link).toHaveAttribute("href", "/api/v1/projects/p1/envelope/sheet");
  });

  it("zeichnet beide Konturen im Lageplan", () => {
    renderBaurahmen();
    const plan = screen.getByRole("img", { name: /Lageplan mit bebaubarer Fläche/ });
    expect(plan.querySelector("[data-testid='kontur-strict']")).toBeTruthy();
    expect(plan.querySelector("[data-testid='kontur-lenient']")).toBeTruthy();
    expect(plan.querySelectorAll("[data-testid^='baurahmen-kante-']").length).toBe(envelope.edges.length);
  });
});
