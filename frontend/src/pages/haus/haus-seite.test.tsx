import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AREA } from "../../configuration/__fixtures__/konfiguration";
import { BRICK, CHOSEN, DOCUMENTS, EMPTY, EVALUATIONS, TEMPLATES } from "../../haus/__fixtures__/haus";
import { DOMAIN_VERSION } from "../../haus/kern";
import i18n from "../../i18n";
import site from "../../site/__fixtures__/site-ad0065.json";

const CONFIGURATION_KEY = ["test", "house-configuration"];

const state = vi.hoisted(() => ({
  flags: {} as Record<string, boolean>,
  site: null as unknown,
  configuration: null as unknown,
  client: null as QueryClient | null,
  patch: vi.fn(),
  presets: vi.fn(),
}));

vi.mock("../../api/session", () => ({
  useSession: () => ({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: { staff: null, project_id: "00000000-0000-4000-8000-000000000065" },
  }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: () => "/login",
  sessionKey: ["session"],
}));

vi.mock("../../api/site", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/site")>();
  return {
    ...original,
    useFlags: () => ({ isPending: false, isError: false, data: state.flags }),
    useSite: () => ({ isPending: false, isError: false, data: state.site }),
  };
});

vi.mock("../../api/envelope", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/envelope")>();
  return { ...original, useEnvelope: () => ({ isPending: false, isError: false, data: undefined }) };
});

// Die Konfiguration kommt wie im echten Hook aus dem Query-Cache, damit eine Antwort die Seite neu zeichnet
vi.mock("../../api/hausKonfiguration", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/hausKonfiguration")>();
  const { useQuery } = await import("@tanstack/react-query");
  return {
    ...original,
    useHouseTemplates: () => ({ isPending: false, isError: false, data: TEMPLATES }),
    useHouseConfiguration: () =>
      useQuery({ queryKey: ["test", "house-configuration"], queryFn: () => state.configuration, staleTime: Infinity }),
    useHouseDocuments: () => ({ isPending: false, isError: false, data: DOCUMENTS }),
    useHousePlacementArea: () => ({ isPending: false, isSuccess: true, data: AREA }),
    useHousePresets: () => ({ mutateAsync: state.presets, isPending: false, data: undefined }),
    usePatchHouseConfiguration: () => ({ mutateAsync: state.patch, isPending: false }),
  };
});

const { routes } = await import("../../App");

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(CONFIGURATION_KEY, state.configuration);
  state.client = client;
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Hausmodell für Kunden", () => {
  beforeEach(async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    state.flags = { house_model: true };
    state.site = site;
    state.configuration = EMPTY;
    state.patch.mockReset();
    // Ohne Antwort bleibt der Lauf offen; einzelne Tests geben eine vor
    state.patch.mockReturnValue(new Promise(() => {}));
    state.presets.mockReset();
    await act(() => i18n.changeLanguage("de"));
  });

  it("bleibt ohne Freischaltung geschlossen", async () => {
    state.flags = { configurator: true };
    renderAt("/haus");
    expect(await screen.findByRole("heading", { name: "Die Hauskonfiguration ist noch nicht freigeschaltet" })).toBeInTheDocument();
    expect(screen.queryByTestId("haustypen")).not.toBeInTheDocument();
  });

  it("verlangt zuerst ein Grundstück", async () => {
    state.site = null;
    renderAt("/haus");
    expect(await screen.findByText("Bilden Sie zuerst Ihr Grundstück, um ein Haus zu konfigurieren.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zum Grundstück" })).toHaveAttribute("href", "/grundstueck");
  });

  it("zeigt die Haustypen mit gerundetem Preis ab und wählt mit Revision 0", async () => {
    renderAt("/haus");
    const card = within(await screen.findByTestId("haustyp-demo_house"));
    expect(card.getByTestId("ab-preis")).toHaveTextContent("ab ca. 515.000 €");
    expect(card.getByText("Auf Ihrem Grundstück möglich")).toBeInTheDocument();
    await userEvent.click(card.getByRole("button", { name: "Diesen Typ wählen" }));
    expect(state.patch).toHaveBeenCalledWith({ body: { template_slug: "demo_house" }, revision: 0 });
  });

  it("rechnet die Ausstattung im Browser und speichert sie mit dem Browserpreis", async () => {
    state.configuration = CHOSEN;
    renderAt("/haus");
    const wall = within(await screen.findByTestId("slot-wall_profile"));
    expect(wall.getByTestId("aufpreis-wall.brick")).toHaveTextContent("ca. +8.400 €");
    expect(screen.getByTestId("gesamtpreis")).toHaveTextContent("ca. 515.000 €");
    expect(screen.getByTestId("speicherstand")).toHaveTextContent("Gespeichert");

    await userEvent.click(wall.getByRole("radio", { name: /Vorgehängte Ziegelfassade/ }));

    expect(state.patch).toHaveBeenCalledTimes(1);
    expect(state.patch).toHaveBeenCalledWith({
      body: {
        configuration: EVALUATIONS.brick.configuration,
        client_price: { net_amount: EVALUATIONS.brick.evaluation.price.net_amount, domain_version: DOMAIN_VERSION },
      },
      revision: 1,
    });
    // Die Vorschau des Kerns steht sofort da, der Server bestätigt sie danach
    expect(screen.getByTestId("gesamtpreis")).toHaveTextContent("ca. 524.000 €");
    expect(screen.getByTestId("speicherstand")).toHaveTextContent("Wird gespeichert …");
    expect(within(screen.getByTestId("slot-wall_profile")).getByTestId("aufpreis-wall.standard")).toHaveTextContent("ca. −8.400 €");
  });

  it("meldet, wenn der Server anders rechnet als der Browser", async () => {
    state.configuration = CHOSEN;
    state.patch.mockImplementation(async () => {
      state.client?.setQueryData(CONFIGURATION_KEY, BRICK);
      return { ...BRICK, price_match: false };
    });
    renderAt("/haus");
    const wall = within(await screen.findByTestId("slot-wall_profile"));
    await userEvent.click(wall.getByRole("radio", { name: /Vorgehängte Ziegelfassade/ }));
    expect(await screen.findByTestId("preisabweichung")).toHaveTextContent("maßgeblich ist der gespeicherte Preis");
    expect(screen.getByTestId("speicherstand")).toHaveTextContent("Gespeichert");
    expect(screen.getByTestId("gesamtpreis")).toHaveTextContent("ca. 524.000 €");
  });

  it("weist Abweichungen aus und übernimmt die vorgeschlagene Lage", async () => {
    state.configuration = BRICK;
    renderAt("/haus");
    expect(await screen.findByTestId("haus-status")).toHaveTextContent("Mit Abweichungen");
    expect(within(screen.getByTestId("ergebnis-deviation")).getByText(/Abweichungen vom PLU/)).toBeInTheDocument();
    expect(screen.getByTestId("ergebnis-info")).toBeInTheDocument();
    expect(within(screen.getByTestId("aufpreise")).getByText("Außenwand – Vorgehängte Ziegelfassade")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("vorschlag"));
    expect(state.patch).toHaveBeenCalledWith({ body: { placement: { origin: { e: 9, n: 26 }, rotation_deg: 0 } }, revision: 2 });
  });

  it("zeigt beim Wechsel des Haustyps die Typen und kehrt ohne Änderung zurück", async () => {
    state.configuration = CHOSEN;
    renderAt("/haus");
    expect(await screen.findByTestId("haus-name")).toHaveTextContent("Demohaus");
    await userEvent.click(screen.getByRole("button", { name: "Haustyp wechseln" }));
    expect(screen.getByText("Gewählter Typ")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Zurück zu meiner Konfiguration" }));
    expect(screen.getByTestId("ausstattung")).toBeInTheDocument();
    expect(state.patch).not.toHaveBeenCalled();
  });
});
