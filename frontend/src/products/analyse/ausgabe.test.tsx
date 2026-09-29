import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useRefreshAnalysisOnTerrain } from "../../api/analysis";
import type { SiteOut } from "../../api/site";
import i18n from "../../i18n";
import { Ausgabe } from "./Ausgabe";

const state = vi.hoisted(() => ({
  report: undefined as unknown,
  request: vi.fn(),
  reset: vi.fn(),
  pending: false,
}));

vi.mock("../../api/analysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/analysis")>()),
  useAnalysis: () => ({ data: { input_hash: "sha256:abc" }, isPending: false, isError: false }),
  useRequestReport: () => ({
    mutate: state.request,
    reset: state.reset,
    data: state.report,
    isPending: state.pending,
    isError: false,
    error: null,
  }),
}));

vi.mock("../../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/site")>()),
  useProjectDetails: () => ({ data: { name: "Maison Dupont", note: null }, isPending: false }),
}));

const site = (georeferenced: boolean) => ({ project_id: "p1", georeferenced, revision: 3 }) as unknown as SiteOut;

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.report = undefined;
  state.pending = false;
  state.request.mockReset();
  state.reset.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

it("bietet ohne Lage nur das lokale DXF an", () => {
  render(<Ausgabe projectId="p1" site={site(false)} />);
  const dateien = screen.getByRole("list");
  expect(within(dateien).getByRole("link", { name: "DXF lokal" })).toHaveAttribute(
    "href",
    "/api/v1/projects/p1/analysis/export/dxf?variant=local",
  );
  expect(within(dateien).getByRole("button", { name: "DXF Lambert-93" })).toBeDisabled();
  expect(within(dateien).getByRole("button", { name: "GeoJSON" })).toBeDisabled();
  expect(within(dateien).getAllByText("Erst mit Lage – im Abschnitt Grundstück festlegen.")).toHaveLength(2);
});

it("bietet mit Lage Lambert-93 und GeoJSON an", () => {
  render(<Ausgabe projectId="p1" site={site(true)} />);
  expect(screen.getByRole("link", { name: "DXF Lambert-93" })).toHaveAttribute(
    "href",
    "/api/v1/projects/p1/analysis/export/dxf?variant=L93",
  );
  expect(screen.getByRole("link", { name: "GeoJSON" })).toHaveAttribute("href", "/api/v1/projects/p1/analysis/export/geojson");
});

it("holt die Analyse neu, sobald das Gelände nach dem Einpassen da ist", () => {
  const client = new QueryClient();
  const neu = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { rerender } = renderHook(({ status }) => useRefreshAnalysisOnTerrain("p1", status), {
    wrapper,
    initialProps: { status: "unavailable" },
  });
  rerender({ status: "pending" });
  expect(neu).not.toHaveBeenCalled();
  rerender({ status: "ok" });
  expect(neu).toHaveBeenCalledExactlyOnceWith({ queryKey: ["analysis", "p1"] });
  rerender({ status: "ok" });
  expect(neu).toHaveBeenCalledOnce();
});

it("fordert den Bericht in der gewählten Sprache an und fragt nach, bis er fertig ist", async () => {
  const { rerender } = render(<Ausgabe projectId="p1" site={site(false)} />);
  // Vorgewählt ist die Sprache der Oberfläche
  expect(screen.getByRole("button", { name: "Deutsch" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "Französisch" }));
  expect(state.reset).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  await userEvent.click(screen.getByRole("button", { name: "Bericht erstellen" }));
  expect(state.request).toHaveBeenLastCalledWith("de");

  vi.useFakeTimers();
  state.report = { status: "pending", input_hash: "sha256:r1", locale: "de", job_id: "j1" };
  rerender(<Ausgabe projectId="p1" site={site(false)} />);
  expect(screen.getByRole("status")).toHaveTextContent("Bericht wird erstellt");
  expect(screen.getByRole("button", { name: "Bericht erstellen" })).toBeDisabled();
  act(() => vi.advanceTimersByTime(2000));
  expect(state.request).toHaveBeenCalledTimes(2);
  expect(state.request).toHaveBeenLastCalledWith("de");

  state.report = { status: "ready", input_hash: "sha256:r1", locale: "de" };
  rerender(<Ausgabe projectId="p1" site={site(false)} />);
  expect(screen.getByRole("link", { name: "Bericht herunterladen" })).toHaveAttribute(
    "href",
    "/api/v1/projects/p1/analysis/report?locale=de",
  );
});
