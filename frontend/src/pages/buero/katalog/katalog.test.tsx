import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TypeSummaryOut, TypeVersionOut } from "../../../api/catalog";
import i18n from "../../../i18n";

const state = vi.hoisted(() => ({
  session: undefined as unknown,
  types: [] as unknown[],
  version: undefined as unknown,
  saveRoles: vi.fn(),
  publish: vi.fn(),
}));

vi.mock("../../../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: state.session }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: (next = "/buero") => `/api/v1/auth/staff/login?next=${encodeURIComponent(next)}`,
}));

// Die Abfragen und Änderungen der Katalogpflege werden ersetzt; geprüft wird, was die Oberfläche daraus macht.
vi.mock("../../../api/catalog", async (importOriginal) => {
  const idle = (mutate = vi.fn()) => ({ mutate, isPending: false, isSuccess: false, isError: false, error: null, data: undefined });
  return {
    ...(await importOriginal<typeof import("../../../api/catalog")>()),
    useCatalogTypes: () => ({ isPending: false, isError: false, data: state.types }),
    useTypeVersion: () => ({ isPending: false, isError: false, data: state.version }),
    useSetFacadeRoles: () => idle(state.saveRoles),
    useSetPlacement: () => idle(),
    usePublishType: () => idle(state.publish),
    useRetireType: () => idle(),
    useImportTypeVersion: () => idle(),
    useUploadPlanDocument: () => idle(),
    usePackages: () => ({ isSuccess: true, isPending: false, isError: false, data: [] }),
    useDraftPriceCatalog: () => ({ isSuccess: true, isPending: false, isError: false, data: { energy_assessments: [] } }),
  };
});

const { routes } = await import("../../../App");

const version = (overrides: Partial<TypeVersionOut> = {}): TypeVersionOut => ({
  id: "v1",
  building_type_id: "t1",
  slug: "ligne",
  version: 1,
  status: "draft",
  name: "Ligne",
  family: null,
  storeys: "R+1",
  roof_form: "gable",
  pitch_deg: 40,
  ridge_direction: "laengs",
  ridge_height_m: 8.4,
  eave_height_m: 5.6,
  // 12 × 8 m, gegen den Uhrzeigersinn, Norden oben
  footprint_facade: [[0, 0], [12, 0], [12, 8], [0, 8]],
  footprint_facade_area_m2: 96,
  footprint_projection: [[-0.5, -0.5], [12.5, -0.5], [12.5, 8.5], [-0.5, 8.5]],
  footprint_projection_area_m2: 117,
  living_area_m2: 158,
  rooms_text: "4 Zimmer",
  rooms: [{ name: "Wohnen", category: "living", storey: "R", area_m2: 42 }],
  facade_roles: {},
  entrance: null,
  garage_door: null,
  base_price_min_cents: 32800000,
  base_price_max_cents: 36200000,
  consistency_warnings: [],
  published_at: null,
  created_at: "2026-09-18T10:00:00Z",
  ...overrides,
});

const summary = (current: TypeVersionOut | null, versions: TypeSummaryOut["versions"]): TypeSummaryOut => ({
  id: "t1",
  slug: "ligne",
  family: null,
  alternatives: [],
  current_version: current,
  versions,
});

function staff(...roles: string[]) {
  state.session = { staff: { id: "1", email: "k@buero.test", display_name: null, roles }, project_id: null };
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Katalogpflege", () => {
  beforeEach(async () => {
    state.saveRoles.mockClear();
    state.publish.mockClear();
    state.types = [];
    await act(() => i18n.changeLanguage("de"));
  });

  describe("Typenliste", () => {
    it("zeigt Entwürfe über die Versionsliste und bietet den Import an", () => {
      staff("catalog_admin");
      state.types = [summary(null, [{ version: 1, status: "draft", name: "Ligne", created_at: "2026-09-18T10:00:00Z", published_at: null }])];
      renderAt("/buero/katalog");
      const card = screen.getByTestId("typ-ligne");
      expect(within(card).getByText("Noch keine veröffentlichte Version.")).toBeInTheDocument();
      expect(within(card).getByRole("link", { name: /v1/ })).toHaveAttribute("href", "/buero/katalog/typen/ligne/1");
      expect(screen.getByRole("button", { name: "Entwurf anlegen" })).toBeInTheDocument();
    });

    it("zeigt einer lesenden Rolle keinen Import", () => {
      staff("ops");
      state.types = [summary(null, [])];
      renderAt("/buero/katalog");
      expect(screen.queryByRole("button", { name: "Entwurf anlegen" })).not.toBeInTheDocument();
      expect(screen.getByText("Ihre Rolle darf den Katalog lesen, aber nicht ändern.")).toBeInTheDocument();
    });

    it("zeigt den Preis einer veröffentlichten Version nur als Spanne", () => {
      staff("architect");
      const published = version({ status: "published" });
      state.types = [summary(published, [{ version: 1, status: "published", name: "Ligne", created_at: published.created_at, published_at: published.created_at }])];
      renderAt("/buero/katalog");
      expect(within(screen.getByTestId("typ-ligne")).getByText(/328\.000\s*€\s*–\s*362\.000\s*€/)).toBeInTheDocument();
    });
  });

  describe("Typstand", () => {
    it("sperrt die Veröffentlichung bei einem Fehler der Prüfung und nennt den Grund", () => {
      staff("catalog_admin");
      state.version = version({
        consistency_warnings: [{ code: "pitch_mismatch", level: "error", detail: "Neigung 40° angegeben, 35,0° berechnet" }],
      });
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByText(/Neigung 40° angegeben/)).toBeInTheDocument();
      expect(screen.getByText("Sperrt die Veröffentlichung.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Veröffentlichen" })).toBeDisabled();
    });

    it("übernimmt den Vorschlag der Fassadenrollen in den Plan und speichert ihn", async () => {
      staff("catalog_admin");
      state.version = version();
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByTestId("kante-0")).toHaveAttribute("data-role", "");

      await userEvent.click(screen.getByRole("button", { name: "Vorschlag übernehmen" }));
      // längste Kante 0 (Süd) ist die Straße, gegenüber der Garten, Blick nach Norden: links West, rechts Ost
      expect(screen.getByTestId("kante-0")).toHaveAttribute("data-role", "street");
      expect(screen.getByTestId("kante-2")).toHaveAttribute("data-role", "garden");
      expect(screen.getByTestId("kante-3")).toHaveAttribute("data-role", "side_left");
      expect(screen.getByTestId("kante-1")).toHaveAttribute("data-role", "side_right");

      const [saveRoles] = screen.getAllByRole("button", { name: "Speichern" });
      await userEvent.click(saveRoles!);
      expect(state.saveRoles).toHaveBeenCalledWith({ 0: "street", 1: "side_right", 2: "garden", 3: "side_left" });
    });

    it("lässt eine Rolle je Kante von Hand setzen", async () => {
      staff("architect");
      state.version = version();
      renderAt("/buero/katalog/typen/ligne/1");
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Rolle der Kante 1" }), "garden");
      expect(screen.getByTestId("kante-1")).toHaveAttribute("data-role", "garden");
    });

    it("zeigt Eingang und Garagentor erst nach dem Setzen im Plan", async () => {
      staff("catalog_admin");
      state.version = version();
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.queryByTestId("marke-eingang")).not.toBeInTheDocument();
      const [entrance] = screen.getAllByRole("checkbox", { name: "Gesetzt" });
      await userEvent.click(entrance!);
      expect(screen.getByTestId("marke-eingang")).toBeInTheDocument();
    });

    it("sperrt einen veröffentlichten Stand: keine Bearbeitung, nur Zurückziehen", () => {
      staff("catalog_admin");
      state.version = version({ status: "published", facade_roles: { "0": "street" } });
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByText(/veröffentlicht und unveränderlich/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Vorschlag übernehmen" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Veröffentlichen" })).not.toBeInTheDocument();
      expect(screen.getByRole("combobox", { name: "Rolle der Kante 0" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "Zurückziehen" })).toBeInTheDocument();
      expect(screen.getByTestId("kante-0")).toHaveAttribute("data-role", "street");
    });

    it("zeigt einer lesenden Rolle alles, aber ohne Schaltflächen zum Ändern", () => {
      staff("ops");
      state.version = version();
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByRole("heading", { name: "Ligne" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Speichern" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Veröffentlichen" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Zurückziehen" })).not.toBeInTheDocument();
    });

    it("veröffentlicht erst nach Bestätigung", async () => {
      staff("catalog_admin");
      state.version = version();
      const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
      renderAt("/buero/katalog/typen/ligne/1");
      await userEvent.click(screen.getByRole("button", { name: "Veröffentlichen" }));
      expect(state.publish).not.toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button", { name: "Veröffentlichen" }));
      expect(state.publish).toHaveBeenCalledTimes(1);
      confirm.mockRestore();
    });

    it("zeichnet die Axonometrie für Sattel- und Flachdach", () => {
      staff("catalog_admin");
      state.version = version();
      const first = renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByTestId("axonometrie")).toHaveAttribute("aria-label", expect.stringContaining("Satteldach"));
      first.unmount();
      state.version = version({ roof_form: "flat", pitch_deg: null, ridge_direction: null, name: "Plateau" });
      renderAt("/buero/katalog/typen/ligne/1");
      expect(screen.getByTestId("axonometrie")).toHaveAttribute("aria-label", expect.stringContaining("Flachdach"));
    });
  });
});
