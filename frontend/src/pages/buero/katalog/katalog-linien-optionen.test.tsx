import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../../i18n";

const state = vi.hoisted(() => ({
  modules: [] as unknown[],
  createModule: vi.fn(),
  createPackage: vi.fn(),
}));

vi.mock("../../../api/session", () => ({
  useSession: () => ({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: { staff: { id: "1", email: "k@buero.test", display_name: null, roles: ["architect"] }, project_id: null },
  }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: (next = "/buero") => `/api/v1/auth/staff/login?next=${encodeURIComponent(next)}`,
}));

vi.mock("../../../api/catalog", async (importOriginal) => {
  const idle = (mutate = vi.fn()) => ({ mutate, isPending: false, isSuccess: false, isError: false, error: null, data: undefined });
  return {
    ...(await importOriginal<typeof import("../../../api/catalog")>()),
    usePackages: () => ({ isSuccess: true, isPending: false, isError: false, data: [] }),
    useModules: () => ({ isSuccess: true, isPending: false, isError: false, data: state.modules }),
    useCreateModuleVersion: () => idle(state.createModule),
    useCreatePackageVersion: () => idle(state.createPackage),
    usePublishModule: () => idle(),
    usePublishPackage: () => idle(),
  };
});

const { routes } = await import("../../../App");

function renderPage() {
  const router = createMemoryRouter(routes, { initialEntries: ["/buero/katalog/linien-optionen"] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const module = (slug: string, overrides: Record<string, unknown> = {}) => ({
  id: slug,
  module_id: slug,
  slug,
  version: 1,
  status: "published",
  label_de: slug,
  label_fr: slug,
  excludes_slugs: [],
  kind: "plain",
  params: {},
  regulatory: {},
  published_at: null,
  ...overrides,
});

async function openOptionForm() {
  const section = screen.getByRole("heading", { name: "Optionen" }).closest("section")!;
  await userEvent.click(within(section).getByText("Neue Option anlegen", { selector: "summary" }));
  return section;
}

describe("Katalogpflege: Art, Maße und Material", () => {
  beforeEach(async () => {
    state.modules = [];
    state.createModule.mockReset();
    state.createPackage.mockReset();
    await act(() => i18n.changeLanguage("de"));
  });

  it("legt eine Terrasse mit Tiefe und Höhe an", async () => {
    renderPage();
    const section = await openOptionForm();
    await userEvent.type(within(section).getByLabelText("Kennung"), "terrasse");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Deutsch)"), "Terrasse Holz");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Französisch)"), "Terrasse bois");
    await userEvent.selectOptions(within(section).getByLabelText("Art"), "terrace");
    expect(within(section).getByLabelText("Tiefe (m)")).toHaveValue(3);
    expect(within(section).getByText(/Preis je Typ gilt je m²/)).toBeInTheDocument();
    await userEvent.selectOptions(within(section).getByLabelText("Material der Fassade"), "wood");
    await userEvent.click(within(section).getByRole("button", { name: "Neue Option anlegen" }));
    expect(state.createModule).toHaveBeenCalledWith(
      {
        slug: "terrasse",
        body: {
          label_de: "Terrasse Holz",
          label_fr: "Terrasse bois",
          excludes_slugs: [],
          kind: "terrace",
          params: { depth_m: 3, height_above_terrain_m: 0.3, sealing_factor: 1 },
          regulatory: { facade_material: "wood" },
        },
      },
      expect.anything(),
    );
  });

  it("legt einen zweistelligen Carport mit doppelter Breite an", async () => {
    renderPage();
    const section = await openOptionForm();
    await userEvent.type(within(section).getByLabelText("Kennung"), "carport_2");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Deutsch)"), "Carport zweistellig");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Französisch)"), "Carport double");
    await userEvent.selectOptions(within(section).getByLabelText("Art"), "carport");
    await userEvent.selectOptions(within(section).getByLabelText("Stellplätze"), "2");
    expect(within(section).getByLabelText("Breite (m)")).toHaveValue(6);
    await userEvent.click(within(section).getByRole("button", { name: "Neue Option anlegen" }));
    expect(state.createModule.mock.calls[0]![0].body).toMatchObject({
      kind: "carport",
      params: { spaces: 2, width_m: 6, depth_m: 5, height_m: 2.7 },
      regulatory: {},
    });
  });

  it("schickt eine einfache Option ohne Maße", async () => {
    renderPage();
    const section = await openOptionForm();
    await userEvent.type(within(section).getByLabelText("Kennung"), "pv");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Deutsch)"), "Photovoltaik");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Französisch)"), "Photovoltaïque");
    await userEvent.click(within(section).getByRole("button", { name: "Neue Option anlegen" }));
    expect(state.createModule.mock.calls[0]![0].body).toMatchObject({ kind: "plain", params: {}, regulatory: {} });
  });

  it("übernimmt die Maße einer vorhandenen Option in das Formular für die neue Version", async () => {
    state.modules = [module("carport_1", { kind: "carport", params: { spaces: 1, width_m: 3, depth_m: 5, height_m: 2.7 } })];
    renderPage();
    const entry = screen.getByTestId("eintrag-carport_1");
    expect(entry).toHaveTextContent("Carport spaces 1, width_m 3, depth_m 5, height_m 2.7");
    await userEvent.click(within(entry).getByRole("button", { name: "Als neue Version bearbeiten" }));
    expect(within(entry).getByLabelText("Art")).toHaveValue("carport");
    expect(within(entry).getByLabelText("Tiefe (m)")).toHaveValue(5);
  });

  it("gibt einer Linie Material für die Regelprüfung mit", async () => {
    renderPage();
    const section = screen.getByRole("heading", { name: "Ausstattungslinien" }).closest("section")!;
    await userEvent.click(within(section).getByText("Neue Linie anlegen", { selector: "summary" }));
    await userEvent.type(within(section).getByLabelText("Kennung"), "confort");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Deutsch)"), "Confort");
    await userEvent.type(within(section).getByLabelText("Bezeichnung (Französisch)"), "Confort");
    await userEvent.selectOptions(within(section).getByLabelText("Material des Daches"), "clay_tile");
    await userEvent.click(within(section).getByRole("button", { name: "Neue Linie anlegen" }));
    expect(state.createPackage.mock.calls[0]![0].body).toMatchObject({ regulatory: { roof_material: "clay_tile" } });
  });
});
