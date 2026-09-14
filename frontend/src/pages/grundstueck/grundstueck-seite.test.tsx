import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import fixture from "../../site/__fixtures__/site-ad0065.json";

const state = vi.hoisted(() => ({
  flags: {} as Record<string, boolean>,
  site: null as unknown,
  queue: [] as unknown[],
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
    useEnsureProject: () => mutation,
    useCorrectEdgeCustomer: () => mutation,
    useServiceArea: () => ({ data: [] }),
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

  it("zeigt ein gebildetes Grundstück zur Prüfung", () => {
    state.flags = { site_selection: true };
    state.site = fixture;
    renderAt("/grundstueck");
    expect(screen.getByRole("heading", { name: "Ihr Grundstück" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Andere Parzellen wählen" })).toBeInTheDocument();
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
