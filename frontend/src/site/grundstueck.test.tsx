import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SiteOut } from "../api/site";
import i18n from "../i18n";
import fixture from "./__fixtures__/site-ad0065.json";
import { GrundstueckPruefen } from "./GrundstueckPruefen";

// Echte Antwort der API für Treillières AD 65 mit einer Kundenkorrektur (hintere Grenze als Straße)
const site = fixture as unknown as SiteOut;

function renderPruefen(props: Partial<Parameters<typeof GrundstueckPruefen>[0]> = {}) {
  const onEdgeChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <GrundstueckPruefen site={site} rolle="customer" onEdgeChange={onEdgeChange} pending={false} error={null} {...props} />
    </QueryClientProvider>,
  );
  return onEdgeChange;
}

describe("Grundstück prüfen", () => {
  beforeEach(async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    await act(() => i18n.changeLanguage("de"));
  });

  it("zeigt Kanten mit Art, Richtung und Straßennamen", () => {
    renderPruefen();
    const table = screen.getByRole("table", { name: "Grenzen des Grundstücks" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(site.edges.length);
    expect(within(table).getAllByText("Rue des chênes").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Seitliche Grenze")).toHaveLength(2);
    expect(within(table).getByText("Ihre Angabe")).toBeInTheDocument();
  });

  it("macht die fehlende Bestätigung und die Grenzen der Aussage sichtbar", () => {
    renderPruefen();
    expect(screen.getByRole("status")).toHaveTextContent("nicht verbindlich");
    expect(screen.getByText(/nicht vermessungsgenau/)).toBeInTheDocument();
    expect(screen.getByText("Radon")).toBeInTheDocument();
    expect(screen.getByText(/Weitgehend eben/)).toBeInTheDocument();
    expect(screen.queryByText("Mindestens eine Grenze ist unsicher eingeordnet.")).not.toBeInTheDocument();
  });

  it("meldet eine Korrektur als Straße oder Nachbar, automatisch setzt zurück", async () => {
    const user = userEvent.setup();
    const onEdgeChange = renderPruefen();
    const side = site.edges.find((e) => e.kind === "side")!;
    await user.selectOptions(screen.getByLabelText(`Korrektur für Grenze ${side.seq}`), "Nachbar");
    expect(onEdgeChange).toHaveBeenLastCalledWith(side.seq, "neighbour");
    const corrected = site.edges.find((e) => e.classification_source === "customer")!;
    await user.selectOptions(screen.getByLabelText(`Korrektur für Grenze ${corrected.seq}`), "Automatisch");
    expect(onEdgeChange).toHaveBeenLastCalledWith(corrected.seq, null);
  });

  it("bietet dem Architekten alle Arten an", () => {
    renderPruefen({ rolle: "architect" });
    const select = screen.getByLabelText(`Korrektur für Grenze ${site.edges[0]!.seq}`);
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Automatisch",
      "Straße",
      "Seitlich",
      "Hinten",
      "Sonstige",
    ]);
    expect(screen.getByRole("status")).toHaveTextContent("warten auf Bestätigung");
  });

  it("zeichnet jede Kante im Lageplan", () => {
    renderPruefen();
    for (const edge of site.edges) expect(screen.getByTestId(`plan-edge-${edge.seq}`)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Lageplan des Grundstücks 44209000AD0065/ })).toBeInTheDocument();
  });
});
