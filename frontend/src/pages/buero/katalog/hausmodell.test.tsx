import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import type {
  HouseCatalogVersionOut,
  HouseImportFinding,
  HouseImportReport,
  HouseTemplate,
  HouseTemplateSummaryOut,
  HouseTemplateVersionOut,
} from "../../../api/haus";
import i18n from "../../../i18n";

const state = vi.hoisted(() => ({
  session: undefined as unknown,
  templates: [] as unknown[],
  catalogs: [] as unknown[],
  version: undefined as unknown,
  upload: vi.fn(),
  save: vi.fn(),
  actions: { check: vi.fn(), publish: vi.fn(), reject: vi.fn(), retire: vi.fn() } as Record<string, Mock>,
}));

vi.mock("../../../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: state.session }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: (next = "/buero") => `/api/v1/auth/staff/login?next=${encodeURIComponent(next)}`,
}));

// Abfragen und Änderungen des Hausmodells werden ersetzt; geprüft wird, was die Oberfläche daraus macht.
vi.mock("../../../api/haus", async (importOriginal) => {
  const idle = (mutate = vi.fn()) => ({
    mutate,
    reset: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    data: undefined,
  });
  return {
    ...(await importOriginal<typeof import("../../../api/haus")>()),
    useHouseTemplates: () => ({ isPending: false, isError: false, data: state.templates }),
    useHouseCatalogs: () => ({ isPending: false, isError: false, data: state.catalogs }),
    useHouseVersion: () => ({ isPending: false, isError: false, data: state.version }),
    useUploadHouseIfc: () => idle(state.upload),
    useSaveDecisions: () => idle(state.save),
    useHouseAction: (_slug: string, _version: number, action: string) => idle(state.actions[action]),
  };
});

const { routes } = await import("../../../App");

const P = (x: number, y: number) => ({ x, y });

/** 10 × 8 m, gegen den Uhrzeigersinn: Wohnen links mit Zone, rechts ein Raum ohne Zone; Fenster Süd, Tür Nord. */
const template = (overrides: Partial<HouseTemplate> = {}): HouseTemplate => ({
  schema_version: 2,
  slug: "demo",
  name: { fr: "Maison test", de: "Testhaus" },
  source_ifc: null,
  ground_floor_offset: 0.2,
  levels: [{ id: "rdc", name: "RDC", elevation: 0 }],
  envelope: [
    {
      level_id: "rdc",
      inner_polygon: [P(0, 0), P(10, 0), P(10, 8), P(0, 8)],
      segments: ["seg-s", "seg-e", "seg-n", "seg-w"].map((id) => ({ id, facade_role: null, source_ifc_guid: null })),
    },
  ],
  interior_walls: [
    {
      id: "wall-a",
      level_id: "rdc",
      axis: [P(6, 0), P(6, 8)],
      thickness: 0.1,
      adjacent_room_ids: ["room-living", "room-x"],
      source_ifc_guid: "guid-wall",
    },
  ],
  openings: [
    {
      id: "win-1",
      kind: "window",
      host_kind: "envelope_segment",
      host_id: "seg-s",
      offset_along_host: 3,
      adjacent_room_ids: ["room-living"],
      source_ifc_guid: "guid-win",
    },
    {
      id: "door-1",
      kind: "door",
      host_kind: "envelope_segment",
      host_id: "seg-n",
      offset_along_host: 2,
      adjacent_room_ids: ["room-x"],
      source_ifc_guid: "guid-door",
    },
  ],
  slabs: [
    { id: "slab-ground", level_id: "rdc", kind: "ground", thickness: 0.2, source_ifc_guid: null },
    { id: "slab-roof", level_id: "rdc", kind: "roof", thickness: 0.1, source_ifc_guid: null },
  ],
  roof: {
    bearing_height: 2.5,
    parapet_height: 0.4,
    eave_overhang: 0,
    verge_overhang: 0,
    design: { form: "flat", pitch_deg: null, upper_pitch_deg: null, break_height: null, rotation: 0 },
  },
  rooms: [
    {
      id: "room-living",
      level_id: "rdc",
      polygon: [P(0, 0), P(6, 0), P(6, 8), P(0, 8)],
      room_type_id: "living",
      source_ifc_guid: "guid-zone",
    },
    {
      id: "room-x",
      level_id: "rdc",
      polygon: [P(6, 0), P(10, 0), P(10, 8), P(6, 8)],
      room_type_id: "unassigned",
      source_ifc_guid: null,
    },
  ],
  entrance_opening_id: null,
  garage_door_opening_id: null,
  defaults: { window_type: "window.standard" },
  element_defaults: {},
  ...overrides,
});

const finding = (code: string, severity: HouseImportFinding["severity"], extra: Partial<HouseImportFinding> = {}) => ({
  code,
  severity,
  element_id: null,
  ifc_guid: null,
  params: {},
  ...extra,
});

const report = (findings: HouseImportFinding[], publishable = false): HouseImportReport => ({
  findings,
  publishable,
  zones: [
    {
      ifc_guid: "guid-zone",
      result: "room",
      room_type_id: "living",
      source: "type",
      raw: "SEJOUR",
      values: [
        { kind: "type", raw: "SEJOUR" },
        { kind: "name", raw: "01" },
      ],
      room_id: "room-living",
      share: 0.98,
    },
  ],
  openings: [
    {
      element_id: "win-1",
      ifc_guid: "guid-win",
      kind: "window",
      width: 1.2,
      height: 1.35,
      head_height: 2.15,
      shutter_box_height: 0,
      slot_id: "window_type",
      option_value_id: "window.standard",
      source: "catalog",
    },
    {
      element_id: "door-1",
      ifc_guid: "guid-door",
      kind: "door",
      width: 0.9,
      height: 2.15,
      head_height: 2.15,
      shutter_box_height: 0,
      slot_id: null,
      option_value_id: null,
      source: null,
    },
  ],
  summary: {
    storeys: 1,
    roof_levels: 0,
    exterior_walls: 4,
    interior_walls: 1,
    windows: 1,
    doors: 1,
    rooms: 2,
    zones: 1,
    inner_width: 10,
    inner_depth: 8,
    inner_area: 80,
  },
});

const OPEN = [
  finding("room_without_zone", "open", { element_id: "room-x", params: { area: 32 } }),
  finding("opening_type_unmatched", "open", {
    element_id: "door-1",
    ifc_guid: "guid-door",
    params: { width: 0.9, height: 2.15, head_height: 2.15, shutter_box_height: 0 },
  }),
  finding("entrance_missing", "open"),
];

const NAME = { fr: "Type", de: "Typ" };

const version = (overrides: Partial<HouseTemplateVersionOut> = {}): HouseTemplateVersionOut => ({
  slug: "demo",
  version: 2,
  status: "draft",
  current: false,
  ifc_file_name: "demo.ifc",
  ifc_sha256: "a".repeat(64),
  ifc_size_bytes: 2 * 1024 * 1024,
  created_at: "2026-10-04T08:00:00Z",
  created_by: "u-1",
  reviewed_at: null,
  reviewed_by: null,
  published_at: null,
  published_by: null,
  rejected_at: null,
  rejected_by: null,
  retired_at: null,
  retired_by: null,
  job: { status: "succeeded", attempts: 1, max_attempts: 3 },
  decisions: {
    name: null,
    ground_floor_offset: null,
    zone_types: {},
    room_types: {},
    confirmed_splits: [],
    facade_roles: {},
    entrance: null,
    garage_door: null,
    defaults: {},
    element_defaults: {},
    roof: null,
  },
  template: template(),
  report: report(OPEN),
  catalog: {
    version: 1,
    current: true,
    room_types: [
      { id: "living", name: { fr: "Séjour", de: "Wohnen" } },
      { id: "kitchen", name: { fr: "Cuisine", de: "Küche" } },
    ],
    slots: [
      {
        id: "window_type",
        category: "window",
        name: { fr: "Fenêtre", de: "Fenster" },
        values: [{ id: "window.standard", name: { fr: "Standard", de: "Standard" } }],
      },
      {
        id: "entrance_door",
        category: "door",
        name: { fr: "Porte d'entrée", de: "Haustür" },
        values: [{ id: "door.entrance", name: NAME }],
      },
    ],
  },
  compatibility: null,
  people: { "u-1": "Katalogpflege Test" },
  ...overrides,
});

const summary = (versions: HouseTemplateSummaryOut["versions"], current: number | null = null): HouseTemplateSummaryOut => ({
  slug: "demo",
  name: { fr: "Maison test", de: "Testhaus" },
  current_version: current,
  versions,
});

const catalogVersion = (overrides: Partial<HouseCatalogVersionOut> = {}): HouseCatalogVersionOut => ({
  market: "FR",
  version: 1,
  status: "published",
  current: true,
  sha256: "b".repeat(64),
  source: "catalog.json",
  created_at: "2026-10-01T08:00:00Z",
  created_by: "cli",
  published_at: "2026-10-01T08:00:00Z",
  published_by: "cli",
  room_types: 5,
  slots: 5,
  option_values: 10,
  ...overrides,
});

function staff(...roles: string[]) {
  state.session = { staff: { id: "1", email: "k@buero.test", display_name: null, roles }, project_id: null };
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("Hausmodell im Büro", () => {
  beforeEach(async () => {
    state.upload.mockReset();
    state.save.mockReset();
    Object.values(state.actions).forEach((action) => action.mockReset());
    state.templates = [];
    state.catalogs = [catalogVersion()];
    state.version = version();
    await act(() => i18n.changeLanguage("de"));
  });

  describe("Liste", () => {
    it("zeigt Haustypen mit Versionen und Status und bietet der Katalogpflege den Upload an", () => {
      staff("catalog_admin");
      state.templates = [
        summary(
          [
            { version: 2, status: "draft", ifc_file_name: "b.ifc", created_at: "2026-10-04T08:00:00Z", created_by: null, importing: true, publishable: null },
            { version: 1, status: "published", ifc_file_name: "a.ifc", created_at: "2026-10-01T08:00:00Z", created_by: null, importing: false, publishable: true },
          ],
          1,
        ),
      ];
      renderAt("/buero/katalog/hausmodell");
      expect(screen.getByRole("link", { name: "Hausmodell" })).toHaveAttribute("aria-current", "page");
      const card = screen.getByTestId("haus-demo");
      expect(within(card).getByRole("heading", { name: "Testhaus" })).toBeInTheDocument();
      const first = within(card).getByRole("link", { name: /v1/ });
      expect(first).toHaveAttribute("href", "/buero/katalog/hausmodell/demo/1");
      expect(within(first).getByText("veröffentlicht")).toBeInTheDocument();
      expect(within(first).getByText("aktuell")).toBeInTheDocument();
      expect(within(within(card).getByRole("link", { name: /v2/ })).getByText("wird gelesen")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Hochladen und lesen" })).toBeDisabled();
      expect(within(screen.getByTestId("katalog-1")).getByText("5 Raumtypen, 5 Optionsgruppen, 10 Werte")).toBeInTheDocument();
    });

    it("lädt eine IFC-Datei unter einer Kennung hoch", async () => {
      staff("catalog_admin");
      renderAt("/buero/katalog/hausmodell");
      const file = new File(["ISO-10303-21;"], "haus.ifc", { type: "application/octet-stream" });
      await userEvent.type(screen.getByRole("combobox", { name: /Kennung des Haustyps/ }), "maison_90");
      await userEvent.upload(screen.getByLabelText(/^IFC-Datei \(\.ifc\)/), file);
      const submit = screen.getByRole("button", { name: "Hochladen und lesen" });
      expect(submit).toBeEnabled();
      // jsdom hält ein Pflichtfeld für Dateien auch nach `upload` für leer und sperrte den Klick; daher direkt absenden
      fireEvent.submit(submit.closest("form")!);
      expect(state.upload).toHaveBeenCalledWith({ slug: "maison_90", file }, expect.anything());
    });

    it("sperrt den Upload ohne veröffentlichte Katalogversion", () => {
      staff("catalog_admin");
      state.catalogs = [];
      renderAt("/buero/katalog/hausmodell");
      expect(screen.getByText(/Es ist noch keine Katalogversion des Hausmodells veröffentlicht/)).toBeInTheDocument();
      expect(screen.getByText("Noch keine Katalogversion.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Hochladen und lesen" })).toBeDisabled();
    });

    it("zeigt Architekt und Betrieb keinen Upload", () => {
      staff("architect");
      renderAt("/buero/katalog/hausmodell");
      expect(screen.queryByRole("button", { name: "Hochladen und lesen" })).not.toBeInTheDocument();
      expect(screen.getByText(/nur die Katalogpflege/)).toBeInTheDocument();
    });
  });

  describe("Version", () => {
    it("zeigt Kennwerte, Vorschau und Befunde und sperrt die Prüfung bei offenen Punkten", () => {
      staff("catalog_admin");
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByRole("heading", { name: "Testhaus" })).toBeInTheDocument();
      expect(screen.getByText(/^Datei demo\.ifc \(2,0 MB\)/)).toBeInTheDocument();
      expect(screen.getByText(/^Hochgeladen .* von Katalogpflege Test$/)).toBeInTheDocument();
      expect(screen.getByText("2 Räume aus 1 Zonen")).toBeInTheDocument();
      const findings = screen.getByRole("list", { name: "Befunde" });
      expect(within(findings).getByText("Raum ohne Zone (32 m²); bitte einen Raumtyp wählen.")).toBeInTheDocument();
      expect(
        within(findings).getByText(/Kein Typ im Katalog passt zur Öffnung \(0,9 × 2,15 m, Sturz 2,15 m, Rollladenkasten 0 m\)/),
      ).toBeInTheDocument();
      expect(screen.getByTestId("raum-room-x")).toHaveTextContent("ohne Raumtyp");
      expect(screen.getByRole("button", { name: "Gegen den Katalog prüfen" })).toBeDisabled();
      expect(screen.getByText("Erst Fehler und offene Punkte klären.")).toBeInTheDocument();
    });

    it("hebt die Elemente eines Befunds in der Vorschau hervor", async () => {
      staff("architect");
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByTestId("raum-room-x")).not.toHaveAttribute("data-lit");
      await userEvent.hover(screen.getByRole("button", { name: /Raum ohne Zone/ }));
      expect(screen.getByTestId("raum-room-x")).toHaveAttribute("data-lit", "true");
    });

    it("speichert die Angaben des Büros und prüft erst danach", async () => {
      staff("catalog_admin");
      state.version = version({ report: report([OPEN[0]!]) });
      renderAt("/buero/katalog/hausmodell/demo/2");
      const save = screen.getByRole("button", { name: "Angaben speichern" });
      expect(save).toBeDisabled();

      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Raumtyp für Raum room-x" }), "kitchen");
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Rolle der Kante 0" }), "street");
      expect(screen.getByTestId("segment-0")).toHaveAttribute("data-role", "street");
      expect(screen.getByText("Ungespeicherte Änderungen.")).toBeInTheDocument();
      expect(screen.getByText("Erst die Angaben speichern, dann prüfen.")).toBeInTheDocument();

      await userEvent.click(save);
      expect(state.save).toHaveBeenCalledWith(
        expect.objectContaining({ room_types: { "room-x": "kitchen" }, facade_roles: { "seg-s": "street" } }),
      );
    });

    it("legt ein nicht erkanntes Dach im Entwurf fest (E-HM-65)", async () => {
      staff("catalog_admin");
      const roofOpen = finding("roof_form_not_recognized", "open", { params: { reason: "edges_differ", slopes: "45°" } });
      state.version = version({ report: report([roofOpen]) });
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(
        within(screen.getByRole("list", { name: "Befunde" })).getByText(
          "Die Dachform wurde nicht erkannt: keine Dachform hat dieselben Trauf- und Giebelkanten. Geneigte Flächen: 45°. Bitte das Dach im Entwurf festlegen.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByTestId("dach-entwurf")).toHaveTextContent("Dach im Entwurf: Flachdach, Attika 0,40 m, Unterkante Dachdecke 2,50 m");

      await userEvent.click(screen.getByRole("radio", { name: "Geneigtes Dach festlegen" }));
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Dachform" }), "mansard");
      const pitch = screen.getByRole("spinbutton", { name: "Neigung der Traufflächen (°)" });
      await userEvent.clear(pitch);
      await userEvent.type(pitch, "70");
      expect(screen.getByRole("spinbutton", { name: "Knickhöhe (m)" })).toHaveValue(2.2);
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Drehung" }), "90");
      await userEvent.click(screen.getByRole("button", { name: "Angaben speichern" }));
      expect(state.save).toHaveBeenCalledWith(
        expect.objectContaining({
          roof: {
            bearing_height: 2.5,
            parapet_height: 0,
            eave_overhang: 0.5,
            verge_overhang: 0.3,
            design: { form: "mansard", pitch_deg: 70, upper_pitch_deg: 25, break_height: 2.2, rotation: 90 },
          },
        }),
      );
    });

    it("verlangt den Namen in beiden Sprachen", async () => {
      staff("catalog_admin");
      renderAt("/buero/katalog/hausmodell/demo/2");
      await userEvent.type(screen.getByRole("textbox", { name: "Name (Französisch)" }), "Maison");
      expect(screen.getByText("Den Namen in beiden Sprachen angeben oder beide Felder leer lassen.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Angaben speichern" })).toBeDisabled();
      await userEvent.type(screen.getByRole("textbox", { name: "Name (Deutsch)" }), "Haus");
      expect(screen.getByRole("button", { name: "Angaben speichern" })).toBeEnabled();
    });

    it("wählt für eine Öffnung ohne Katalogtyp einen Wert und den Eingang", async () => {
      staff("catalog_admin");
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.queryByRole("combobox", { name: "Typ für Öffnung win-1" })).not.toBeInTheDocument();
      await userEvent.selectOptions(
        screen.getByRole("combobox", { name: "Typ für Öffnung door-1" }),
        "entrance_door::door.entrance",
      );
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Eingang" }), "door-1");
      await userEvent.click(screen.getByRole("button", { name: "Angaben speichern" }));
      expect(state.save).toHaveBeenCalledWith(
        expect.objectContaining({
          element_defaults: { "door-1": { entrance_door: "door.entrance" } },
          entrance: { opening_id: "door-1" },
        }),
      );
    });

    it("gibt eine geprüfte Version erst nach Bestätigung frei", async () => {
      staff("catalog_admin");
      state.version = version({
        status: "reviewed",
        report: report([], true),
        compatibility: {
          catalog_version: 1,
          domain_version: "1.0.0",
          supported: true,
          issues: [],
          checked_at: "2026-10-04T09:00:00Z",
          checked_by: "k@buero.test",
          approved_at: null,
          approved_by: null,
        },
      });
      const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByTestId("pruefergebnis")).toHaveTextContent("Kompatibel mit dem Katalog.");
      const publish = screen.getByRole("button", { name: "Freigeben und veröffentlichen" });
      await userEvent.click(publish);
      expect(state.actions.publish).not.toHaveBeenCalled();
      await userEvent.click(publish);
      expect(state.actions.publish).toHaveBeenCalledTimes(1);
      confirm.mockRestore();
    });

    it("verlangt nach einer neuen Katalogversion eine neue Prüfung", () => {
      staff("catalog_admin");
      const reviewed = version({ status: "reviewed", report: report([], true) });
      state.version = {
        ...reviewed,
        catalog: { ...reviewed.catalog, current: false },
        compatibility: {
          catalog_version: 1,
          domain_version: "1.0.0",
          supported: true,
          issues: [],
          checked_at: "2026-10-04T09:00:00Z",
          checked_by: null,
          approved_at: null,
          approved_by: null,
        },
      };
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByText(/Seit diesem Stand ist eine neue Katalogversion veröffentlicht/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Freigeben und veröffentlichen" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "Erneut prüfen" })).toBeEnabled();
      expect(screen.getByText("Neue Katalogversion: erneut prüfen, dann freigeben.")).toBeInTheDocument();
    });

    it("nennt die Befunde einer nicht kompatiblen Prüfung", () => {
      staff("catalog_admin");
      state.version = version({
        report: report([], true),
        compatibility: {
          catalog_version: 1,
          domain_version: "1.0.0",
          supported: false,
          issues: [
            { code: "room_type_unknown", element_id: "room-x", slot_id: null, ref_id: "garage" },
            { code: "neu_im_kern", element_id: null, slot_id: null, ref_id: "x" },
          ],
          checked_at: "2026-10-04T09:00:00Z",
          checked_by: null,
          approved_at: null,
          approved_by: null,
        },
      });
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByTestId("pruefergebnis")).toHaveTextContent("Nicht kompatibel");
      expect(screen.getByText("Der Raumtyp fehlt im Katalog.")).toBeInTheDocument();
      expect(screen.getByText("room_type_unknown · room-x · garage")).toBeInTheDocument();
      // Ein Code ohne Text erscheint roh
      expect(screen.getByText("neu_im_kern")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Freigeben und veröffentlichen" })).not.toBeInTheDocument();
    });

    it("zeigt den Lesestand, solange der Job die Datei liest", () => {
      staff("catalog_admin");
      state.version = version({ report: null, template: null, job: { status: "running", attempts: 2, max_attempts: 3 } });
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByRole("status")).toHaveTextContent("Die Datei wird gelesen.");
      expect(screen.getByRole("status")).toHaveTextContent("Versuch 2 von 3");
      expect(screen.queryByRole("button", { name: "Angaben speichern" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument();
    });

    it("verweist bei einer unlesbaren Datei auf einen neuen Upload", () => {
      staff("catalog_admin");
      state.version = version({
        template: null,
        report: { ...report([finding("reader_failed", "error")]), zones: [], openings: [] },
      });
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByText("Das Lesen der Datei ist gescheitert: –")).toBeInTheDocument();
      expect(screen.getByText(/Laden Sie sie erneut hoch/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Angaben speichern" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Gegen den Katalog prüfen" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument();
    });

    it("sperrt eine veröffentlichte Version: nur Zurückziehen", () => {
      staff("catalog_admin");
      state.version = version({ status: "published", current: true, report: report([], true) });
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByText(/Veröffentlichte Versionen sind unveränderlich/)).toBeInTheDocument();
      expect(screen.getByRole("combobox", { name: "Rolle der Kante 0" })).toBeDisabled();
      expect(screen.queryByRole("button", { name: "Angaben speichern" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Verwerfen" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Zurückziehen" })).toBeInTheDocument();
    });

    it("zeigt einer lesenden Rolle alles, aber ohne Schaltflächen zum Ändern", () => {
      staff("ops");
      renderAt("/buero/katalog/hausmodell/demo/2");
      expect(screen.getByRole("heading", { name: "Testhaus" })).toBeInTheDocument();
      expect(screen.getByText(/nur die Katalogpflege/)).toBeInTheDocument();
      expect(screen.getByRole("combobox", { name: "Raumtyp für Raum room-x" })).toBeDisabled();
      expect(screen.queryByRole("button", { name: "Angaben speichern" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Gegen den Katalog prüfen" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Verwerfen" })).not.toBeInTheDocument();
    });

    it("spricht Französisch", async () => {
      staff("catalog_admin");
      renderAt("/buero/katalog/hausmodell/demo/2");
      await act(() => i18n.changeLanguage("fr"));
      expect(screen.getByRole("heading", { name: "Maison test" })).toBeInTheDocument();
      expect(screen.getByText("Pièce sans zone (32 m²) ; merci de choisir un type de pièce.")).toBeInTheDocument();
    });
  });
});
