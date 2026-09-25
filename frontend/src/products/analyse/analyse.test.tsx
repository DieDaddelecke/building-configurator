import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { routes } from "./App";

const state = vi.hoisted(() => ({
  staff: null as { email: string; display_name: string | null } | null,
  site: null as unknown,
  projects: [] as unknown[],
  classify: vi.fn(),
  upload: vi.fn(),
}));

vi.mock("../../api/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/session")>()),
  useSession: () => ({ data: { staff: state.staff }, isPending: false, isError: false, isSuccess: true }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("../../api/regulations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/regulations")>()),
  useProjectRegulations: () => ({ data: [], isPending: false, isError: false, isSuccess: true }),
}));

vi.mock("../../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/site")>()),
  useOwnProjects: () => ({ data: state.projects, isPending: false, isError: false }),
  useCreateProject: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useDeleteProject: () => ({ mutate: vi.fn(), isPending: false }),
  useSite: () => ({ data: state.site, isPending: false, isError: false, isSuccess: true }),
  useUploadParcel: () => ({ mutate: state.upload, reset: vi.fn(), isPending: false, error: null }),
  useClassifyEdge: () => ({ mutate: state.classify, isPending: false, isError: false }),
}));

const edge = (seq: number, coords: number[][]) => ({
  seq,
  ring: 0,
  kind: "other",
  kind_auto: "other",
  override_kind: null,
  classification_source: "auto",
  confidence: 0,
  length_m: 20,
  normal_azimuth_deg: 90 * seq,
  adjacent: [],
  street_name: null,
  road_share: null,
  coords_local: coords,
});

const site = {
  project_id: "p1",
  origin: "upload",
  georeferenced: false,
  source_info: { file_name: "parzelle.dxf", layer: "PARCELLE", crs: "local" },
  address_label: "Parzelle Nord",
  revision: 1,
  engine_version: "g1-1.1.0",
  updated_at: "2026-09-20T10:00:00Z",
  area_m2: 600,
  area_official_m2: null,
  local_origin: { e: 0, n: 0, crs: "EPSG:2154" },
  outline_local: [[[0, 0], [20, 0], [20, 30], [0, 30], [0, 0]]],
  outline_geojson: { type: "Polygon", coordinates: [] },
  parcels: [],
  edges: [
    edge(1, [[0, 0], [20, 0]]),
    edge(2, [[20, 0], [20, 30]]),
    edge(3, [[20, 30], [0, 30]]),
    edge(4, [[0, 30], [0, 0]]),
  ],
  main_street_seq: null,
  street_azimuth_deg: null,
  garden_azimuth_deg: null,
  binding: true,
  warnings: ["no_street_edge"],
  notices: ["notice.upload"],
  terrain: { status: "unavailable", samples: 0 },
  risks: { status: "unavailable", items: [] },
  context: { parcels: [], buildings: [] },
};

function zeige(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.staff = { email: "ops@buero.test", display_name: null };
  state.projects = [];
  state.site = null;
  state.classify.mockReset();
});

it("zeigt ohne Anmeldung die drei Schritte und den Anmeldeknopf", () => {
  state.staff = null;
  zeige("/");

  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Parzelle und Bebauungsplan");
  expect(screen.getByText("Regelwerk hochladen")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: i18n.t("office.login") })).toBeInTheDocument();
});

it("listet die Projekte des Büros", () => {
  state.projects = [
    {
      id: "p1",
      status: "draft",
      created_at: "2026-09-20T09:00:00Z",
      last_activity_at: "2026-09-20T10:00:00Z",
      address_label: "Parzelle Nord",
      site_origin: "upload",
      area_m2: 600,
    },
  ];
  zeige("/");

  expect(screen.getByRole("link", { name: "Parzelle Nord" })).toBeInTheDocument();
  expect(screen.getByText("aus Datei")).toBeInTheDocument();
  expect(screen.getByText(/600.*m²/)).toBeInTheDocument();
});

it("bietet ohne Parzelle Datei und Zeichnung an", async () => {
  zeige("/projekt/p1");

  expect(screen.getByRole("heading", { name: "Parzelle einbringen" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Datei hochladen" }));
  expect(screen.getByLabelText("Datei")).toBeInTheDocument();
  expect(screen.getByText(/DXF mit geschlossener Polylinie/)).toBeInTheDocument();
});

it("zeigt Herkunft und nicht eingeordnete Kanten und setzt eine Straßenkante", async () => {
  state.site = site;
  zeige("/projekt/p1");

  expect(screen.getByText("parzelle.dxf", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("ohne geografischen Bezug")).toBeInTheDocument();
  expect(screen.getByText(/Noch keine Straßenkante/)).toBeInTheDocument();

  const auswahl = within(screen.getByRole("region", { name: "Kanten" })).getAllByRole("combobox");
  expect(auswahl).toHaveLength(4);
  // Darunter der Bebauungsplan, noch ohne Dokument (AN2)
  expect(screen.getByRole("heading", { name: "Bebauungsplan" })).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Korrektur für Grenze 1"), "street");
  expect(state.classify).toHaveBeenCalledWith({ seq: 1, kind: "street" });
});
