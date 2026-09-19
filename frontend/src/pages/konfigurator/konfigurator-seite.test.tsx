import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { AREA, CONFIGURATION, TYPES, VIOLATED } from "../../configuration/__fixtures__/konfiguration";
import site from "../../site/__fixtures__/site-ad0065.json";

const state = vi.hoisted(() => ({
  flags: {} as Record<string, boolean>,
  site: null as unknown,
  configuration: null as unknown,
  patch: vi.fn(),
  presets: vi.fn(),
  patchError: null as unknown,
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

vi.mock("../../api/configuration", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/configuration")>();
  return {
    ...original,
    useTypes: () => ({ isPending: false, isError: false, data: TYPES }),
    useConfiguration: () => ({ isPending: false, isError: false, data: state.configuration }),
    usePlacementArea: () => ({ isPending: false, isSuccess: true, data: AREA }),
    usePatchConfiguration: () => ({
      mutate: state.patch,
      isPending: false,
      error: state.patchError,
      variables: undefined,
    }),
    usePresets: () => ({
      mutateAsync: state.presets,
      isPending: false,
      isSuccess: false,
      data: undefined,
    }),
  };
});

const { routes } = await import("../../App");

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const EMPTY = { ...CONFIGURATION, revision: 0, type: null, placement: null, fit: null, evaluation: null, rotations: [] };

describe("Konfigurator", () => {
  beforeEach(async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    state.flags = { configurator: true };
    state.site = site;
    state.configuration = EMPTY;
    state.patchError = null;
    state.patch.mockReset();
    state.presets.mockReset();
    await act(() => i18n.changeLanguage("de"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("bleibt ohne Freischaltung geschlossen", () => {
    state.flags = {};
    renderAt("/konfigurator");
    expect(screen.getByRole("heading", { name: "Die Hauswahl ist noch nicht freigeschaltet" })).toBeInTheDocument();
    expect(screen.queryByTestId("typkarten")).not.toBeInTheDocument();
  });

  it("verlangt zuerst ein Grundstück", () => {
    state.site = null;
    renderAt("/konfigurator");
    expect(screen.getByText("Bilden Sie zuerst Ihr Grundstück, um ein Haus zu wählen.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zum Grundstück" })).toHaveAttribute("href", "/grundstueck");
  });

  it("beginnt ohne Wahl bei den Typkarten und legt die Revision 0 zugrunde", async () => {
    renderAt("/konfigurator");
    expect(screen.getByRole("heading", { name: "Ihr Haus auf dem Grundstück" })).toBeInTheDocument();
    expect(await screen.findByTestId("typkarten")).toBeInTheDocument();
    await userEvent.click(within(screen.getByTestId("typ-ligne")).getByRole("button", { name: "Diesen Typ wählen" }));
    expect(state.patch).toHaveBeenCalledWith(
      { body: { type_slug: "ligne" }, revision: 0 },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("zeigt bei gewähltem Typ die Implantation mit Abständen und Prüfungen", () => {
    state.configuration = CONFIGURATION;
    renderAt("/konfigurator");
    expect(screen.getByRole("heading", { name: /Implantation · Ligne/ })).toBeInTheDocument();
    expect(screen.getByText("Alle geprüften Regeln sind eingehalten.")).toBeInTheDocument();
    const table = within(screen.getByTestId("abstaende"));
    expect(table.getByText("Straße (2)")).toBeInTheDocument();
    expect(table.getByText("5,00 m", { selector: "td.num.t-ink" })).toBeInTheDocument();
    expect(screen.getByTestId("haus")).toBeInTheDocument();
    expect(screen.getByText("Nächster Schritt: Linie, Optionen und geschätzte Kosten. Er ist noch nicht freigeschaltet.")).toBeInTheDocument();
  });

  it("nennt bei einem Verstoß alle verletzten Regeln", () => {
    state.configuration = VIOLATED;
    renderAt("/konfigurator");
    expect(screen.getByText("Diese Lage verletzt Regeln:")).toBeInTheDocument();
    expect(screen.getAllByText("Abstand zur Straße: 4,00 m (mindestens 5,00 m)").length).toBeGreaterThan(0);
  });

  it("bietet Bauen auf der Grenze nur an Kanten an, die es erlauben", () => {
    state.configuration = CONFIGURATION;
    renderAt("/konfigurator");
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "Auf der Grenze: Seitliche Grenze (1)" })).toBeInTheDocument();
    fireEvent.click(boxes[0]!);
    expect(state.patch).toHaveBeenCalledWith({ body: { boundary_options: { "1": true } }, revision: 3 });
  });

  it("verschiebt das Haus mit den Pfeiltasten und speichert nach kurzer Pause", () => {
    vi.useFakeTimers();
    state.configuration = CONFIGURATION;
    renderAt("/konfigurator");
    const house = screen.getByTestId("haus");
    fireEvent.keyDown(house, { key: "ArrowRight" });
    fireEvent.keyDown(house, { key: "ArrowUp", shiftKey: true });
    expect(state.patch).not.toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(400));
    expect(state.patch).toHaveBeenCalledTimes(1);
    expect(state.patch).toHaveBeenCalledWith({
      body: { placement: { origin: { e: 8.25, n: 26 }, rotation_deg: 0 } },
      revision: 3,
    });
  });

  it("dreht mit R um die Hausmitte zur nächsten erlaubten Ausrichtung", () => {
    state.configuration = CONFIGURATION;
    renderAt("/konfigurator");
    fireEvent.keyDown(screen.getByTestId("haus"), { key: "r" });
    expect(state.patch).toHaveBeenCalledWith({
      body: { placement: { origin: { e: 10, n: 35 }, rotation_deg: 90 } },
      revision: 3,
    });
  });

  it("übernimmt eine Schnellstellung des Servers", async () => {
    state.configuration = CONFIGURATION;
    state.presets.mockResolvedValue({
      type_slug: "ligne",
      presets: { street_near: { origin: { e: 4, n: 18 }, rotation_deg: 0 }, set_back: null, garden_max: null },
    });
    renderAt("/konfigurator");
    await userEvent.click(screen.getByRole("button", { name: "Straßennah" }));
    expect(state.presets).toHaveBeenCalledWith("ligne");
    await vi.waitFor(() =>
      expect(state.patch).toHaveBeenCalledWith({
        body: { placement: { origin: { e: 4, n: 18 }, rotation_deg: 0 } },
        revision: 3,
      }),
    );
  });

  it("zeigt den freien Modus (Weg E) mit Hinweis statt Regelprüfung", () => {
    state.configuration = { ...CONFIGURATION, mode: "free", free_reason: "manual_sketch" };
    renderAt("/konfigurator");
    expect(screen.getAllByText(/Sie haben das Grundstück selbst gezeichnet/).length).toBeGreaterThan(0);
  });
});
