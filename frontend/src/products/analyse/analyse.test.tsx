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
  archive: [] as unknown[],
  details: undefined as unknown,
  addresses: [] as unknown[],
  classify: vi.fn(),
  upload: vi.fn(),
  update: vi.fn(),
  position: vi.fn(),
}));

// MapLibre braucht WebGL; die Karte wird durch eine Fläche ersetzt, die Tastatur und Fokus hat
vi.mock("./EinpassKarte", () => ({
  default: () => <div tabIndex={0} data-testid="einpass-karte" />,
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
  useOwnProjects: (archived = false) => ({
    data: archived ? state.archive : state.projects,
    isPending: false,
    isError: false,
  }),
  useProjectDetails: () => ({ data: state.details, isPending: false, isError: false }),
  useUpdateProject: () => ({ mutate: state.update, isPending: false, isError: false, error: null }),
  usePositionSite: () => ({ mutate: state.position, isPending: false, error: null }),
  useGeocode: (query: string) => ({ data: query ? state.addresses : undefined, isError: false }),
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
  state.archive = [];
  state.details = undefined;
  state.addresses = [];
  state.site = null;
  state.classify.mockReset();
  state.update.mockReset();
  state.position.mockReset();
});

const projekt = (id: string, felder: Record<string, unknown>) => ({
  id,
  status: "draft",
  created_at: "2026-09-20T09:00:00Z",
  last_activity_at: "2026-09-20T10:00:00Z",
  name: null,
  note: null,
  archived_at: null,
  address_label: null,
  site_origin: "upload",
  area_m2: 600,
  ...felder,
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

it("nennt, aus wie vielen Flächen der Datei der Umriss zusammengesetzt ist", () => {
  state.site = { ...site, source_info: { ...site.source_info, index: null, indices: [3, 7] } };
  zeige("/projekt/p1");
  expect(screen.getByText("aus 2 Flächen der Datei zusammengesetzt")).toBeInTheDocument();
});

it("nennt die Schwelle, unter der kurze Stücke zu einer Kante gehören", () => {
  state.site = { ...site, source_info: { ...site.source_info, short_piece_m: 2 } };
  zeige("/projekt/p1");
  expect(screen.getByText("Stücke unter 2 m zu einer Kante zusammengefasst")).toBeInTheDocument();
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

it("zeigt Name und Notiz, sucht und wechselt ins Archiv", async () => {
  state.projects = [
    projekt("p1", { name: "Maison Dupont", address_label: "12 rue des Chênes", note: "Garage à conserver" }),
    projekt("p2", { address_label: "Lotissement Les Pins" }),
  ];
  state.archive = [projekt("p3", { name: "Ancien projet", archived_at: "2026-09-21T10:00:00Z" })];
  zeige("/");

  expect(screen.getByRole("link", { name: "Maison Dupont" })).toBeInTheDocument();
  expect(screen.getByText("12 rue des Chênes")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Lotissement Les Pins" })).toBeInTheDocument();
  // Suche über Name, Adresse und Notiz, ohne Akzente
  await userEvent.type(screen.getByLabelText("Suchen (Name, Adresse, Notiz)"), "garage a");
  expect(screen.queryByRole("link", { name: "Lotissement Les Pins" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Maison Dupont" })).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Suchen (Name, Adresse, Notiz)"));

  await userEvent.click(screen.getByRole("button", { name: "Archiv" }));
  expect(screen.getByRole("button", { name: "Archiv" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("link", { name: "Ancien projet" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Maison Dupont" })).not.toBeInTheDocument();
});

it("bearbeitet Name und Notiz im Kopf und archiviert", async () => {
  state.site = site;
  state.details = projekt("p1", { name: "Maison Dupont", address_label: "Parzelle Nord", note: "Rendez-vous le 3" });
  zeige("/projekt/p1");

  expect(screen.getByRole("heading", { level: 2, name: "Maison Dupont" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Notiz" })).toHaveTextContent("Rendez-vous le 3");
  await userEvent.click(screen.getByRole("button", { name: "Name und Notiz" }));
  const name = screen.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Maison Martin");
  await userEvent.click(screen.getByRole("button", { name: "Speichern" }));
  expect(state.update).toHaveBeenCalledWith({ name: "Maison Martin", note: "Rendez-vous le 3" }, expect.anything());

  await userEvent.click(screen.getByRole("button", { name: "Archivieren" }));
  expect(state.update).toHaveBeenLastCalledWith({ archived: true });
});

it("passt ein Grundstück ohne Lage auf der Karte ein", async () => {
  state.site = { ...site, placement: { pivot_local: [10, 15], pivot_wgs84: null, map_rotation_deg: 0 } };
  state.addresses = [
    {
      label: "12 Rue des Chênes 44119 Treillières",
      kind: "housenumber",
      lon: -1.6186,
      lat: 47.3322,
      citycode: "44209",
      postcode: "44119",
      city: "Treillières",
      in_service_area: false,
    },
  ];
  zeige("/projekt/p1");

  expect(screen.getByText(/Mit Lage gibt es Gelände, Risiken/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Lage festlegen" }));
  expect(screen.getByRole("heading", { name: "Lage festlegen" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Lage übernehmen" })).toBeDisabled();
  expect(screen.getByText(/Zuerst eine Adresse wählen/)).toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("Adresse des Grundstücks"), "12 rue des chenes");
  await userEvent.click(await screen.findByRole("button", { name: "12 Rue des Chênes 44119 Treillières" }));
  // Eine Taste nach rechts (0,1 m), mit Umschalttaste nach Norden (1 m), dann 1° im Uhrzeigersinn
  const karte = await screen.findByTestId("einpass-karte");
  karte.focus();
  await userEvent.keyboard("{ArrowRight}{Shift>}{ArrowUp}{/Shift}");
  await userEvent.click(screen.getByRole("button", { name: "um 1,0° drehen" }));
  await userEvent.click(screen.getByRole("button", { name: "Lage übernehmen" }));

  const [body] = state.position.mock.calls[0]!;
  expect(body.rotation_deg).toBe(1);
  expect((body.lon + 1.6186) * 75_470).toBeCloseTo(0.1, 2);
  expect((body.lat - 47.3322) * 111_178).toBeCloseTo(1, 2);
});

it("zeigt nach der Lage Gelände und Risiken mit den Werten für den Architekten", () => {
  state.site = {
    ...site,
    georeferenced: true,
    source_info: { ...site.source_info, position: { method: "map", at: "2026-09-28T10:00:00Z" } },
    placement: { pivot_local: [10, 15], pivot_wgs84: [-1.6186, 47.3322], map_rotation_deg: -3.35 },
    terrain: { status: "ok", method: "ign_altimetry", reference_altitude_ngf: 52.8, slope_percent: 1.2, flat: true, samples: 150 },
    risks: { status: "ok", items: [{ kind: "radon", level: "low", scope: "commune" }] },
  };
  zeige("/projekt/p1");

  expect(screen.getByText("von Hand auf dem Kataster eingepasst (28.9.2026)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Lage korrigieren" })).toBeInTheDocument();
  expect(screen.getByText("Mittlere Höhe 52,80 m NGF, Neigung 1,2 %, aus 150 Höhenpunkten (IGN RGE ALTI).")).toBeInTheDocument();
  expect(screen.getByText("Radon")).toBeInTheDocument();
});
