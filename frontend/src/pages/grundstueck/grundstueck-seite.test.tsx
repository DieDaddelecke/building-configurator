import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import fixture from "../../site/__fixtures__/site-ad0065.json";

const state = vi.hoisted(() => ({
  flags: {} as Record<string, boolean>,
  site: null as unknown,
  queue: [] as unknown[],
  communes: [] as unknown[],
  areaPending: false,
  lookup: vi.fn(),
  session: { staff: null as unknown, project_id: "00000000-0000-4000-8000-000000000065" },
}));

vi.mock("../../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: state.session }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: () => "/login",
  sessionKey: ["session"],
}));

vi.mock("../../api/site", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/site")>();
  const mutation = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, error: null, data: undefined };
  return {
    ...original,
    useFlags: () => ({ isPending: false, isError: false, data: state.flags }),
    useSite: () => ({ isPending: false, isError: false, data: state.site }),
    useEnsureProject: () => ({ ...mutation, mutateAsync: () => Promise.resolve("p-1") }),
    useCorrectEdgeCustomer: () => mutation,
    useServiceArea: () => ({ isPending: state.areaPending, data: state.areaPending ? undefined : state.communes }),
    lookupParcels: (...args: unknown[]) => state.lookup(...args),
    useGeocode: () => ({ data: undefined, isError: false }),
    useFormSite: () => mutation,
    useReviewQueue: () => ({ isPending: false, isError: false, data: state.queue }),
  };
});

vi.mock("../../components/karte/Katasterkarte", () => ({ default: () => <div data-testid="karte" /> }));

const { routes } = await import("../../App");

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Grundstücksseite", () => {
  beforeEach(async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    state.flags = {};
    state.site = null;
    state.communes = [];
    state.areaPending = false;
    state.lookup.mockReset();
    await act(() => i18n.changeLanguage("de"));
  });

  it("bleibt ohne Freischaltung geschlossen", () => {
    renderAt("/grundstueck");
    expect(screen.getByRole("heading", { name: "Die Grundstückswahl ist noch nicht freigeschaltet" })).toBeInTheDocument();
    expect(screen.queryByTestId("karte")).not.toBeInTheDocument();
  });

  it("zeigt ohne Grundstück die Parzellenwahl mit Karte", async () => {
    state.flags = { site_selection: true };
    renderAt("/grundstueck");
    expect(screen.getByRole("heading", { name: "Wählen Sie Ihre Parzelle" })).toBeInTheDocument();
    expect(await screen.findByTestId("karte")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Grundstück übernehmen" })).toBeDisabled();
  });

  it("legt die Karte erst an, wenn die Gemeinden geladen sind", () => {
    state.flags = { site_selection: true };
    state.areaPending = true;
    renderAt("/grundstueck");
    expect(screen.queryByTestId("karte")).not.toBeInTheDocument();
  });

  it("zeigt ein gebildetes Grundstück zur Prüfung", () => {
    state.flags = { site_selection: true };
    state.site = fixture;
    renderAt("/grundstueck");
    expect(screen.getByRole("heading", { name: "Ihr Grundstück" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Andere Parzellen wählen" })).toBeInTheDocument();
  });

  it("lässt bei mehreren Gemeinden die Gemeinde der Parzellennummer wählen", async () => {
    state.flags = { site_selection: true };
    state.communes = [
      { insee: "75107", name: "PARIS 07", bbox: [2.29, 48.84, 2.33, 48.86], release: "2026-06-01", imported_at: null },
      { insee: "44209", name: "TREILLIERES", bbox: [-1.7, 47.3, -1.6, 47.4], release: "2026-06-01", imported_at: null },
    ];
    state.lookup.mockResolvedValue({ in_service_area: true, contained_idu: null, candidates: [] });
    renderAt("/grundstueck");
    const gemeinde = screen.getByRole("combobox", { name: "Gemeinde" });
    expect(gemeinde).toHaveValue("75107");
    fireEvent.change(gemeinde, { target: { value: "44209" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Sektion" }), { target: { value: "ad" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nummer" }), { target: { value: "65" } });
    await act(() => screen.getByRole("button", { name: "Parzelle suchen" }).click());
    expect(state.lookup).toHaveBeenCalledWith("p-1", { commune_insee: "44209", section: "AD", number: "65" });
  });

  it("bietet den Weg zum freien Zeichnen an und wechselt dorthin (Plan 3.3, Weg E)", async () => {
    state.flags = { site_selection: true };
    renderAt("/grundstueck");
    const link = screen.getByRole("button", { name: "Finden Sie Ihre Parzelle nicht? Zeichnen Sie den Umriss selbst" });
    await act(() => link.click());
    expect(screen.getByRole("heading", { name: "Zeichnen Sie den Umriss Ihres Grundstücks" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Zeichenfläche ohne Kartenhintergrund" })).toBeInTheDocument();
  });

  it("zeigt ein frei gezeichnetes Grundstück ohne Kanten, Regeln oder Baurahmen (Weg E, D13)", () => {
    state.flags = { site_selection: true, envelope_simulation: true, rules_simulation: true };
    state.site = {
      ...fixture,
      origin: "manual_sketch",
      address_label: "12 rue imaginaire",
      area_m2: 200,
      area_official_m2: null,
      parcels: [],
      edges: [],
      warnings: [],
      notices: ["notice.manual_sketch"],
      outline_local: [[[0, 0], [10, 0], [10, 20], [0, 20], [0, 0]]],
      terrain: { status: "unavailable" },
      risks: { status: "unavailable", items: [] },
    };
    renderAt("/grundstueck");
    expect(screen.getByRole("heading", { name: "Ihr Grundstück (gezeichnet)" })).toBeInTheDocument();
    expect(screen.getByText("12 rue imaginaire")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Diese Fläche wurde nicht mit dem Bebauungsplan abgeglichen. Die Vereinbarkeit mit den geltenden Vorschriften ist nicht geprüft.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Was darf ich bauen?" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Regeln des Bebauungsplans" })).not.toBeInTheDocument();
  });

  it("verlinkt die Büro-Prüfliste", () => {
    state.session = { ...state.session, staff: { id: "1", email: "archi@buero.test", display_name: null, roles: ["architect"] } };
    state.queue = [
      {
        project_id: "p-1",
        parcel_idus: ["44209000AD0065"],
        revision: 2,
        warnings: ["customer_corrections_unconfirmed"],
        customer_corrections: 1,
        updated_at: "2026-09-14T08:00:00Z",
      },
    ];
    renderAt("/buero/grundstuecke");
    expect(screen.getByRole("link", { name: "Grundstücke" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "44209000AD0065" })).toHaveAttribute("href", "/buero/grundstuecke/p-1");
  });
});
