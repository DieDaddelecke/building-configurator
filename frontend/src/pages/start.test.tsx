import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";

const session = vi.hoisted(() => ({ data: undefined as unknown }));
const flags = vi.hoisted(() => ({ data: {} as Record<string, boolean> }));

vi.mock("../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: session.data }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: (next = "/buero") => `/api/v1/auth/staff/login?next=${encodeURIComponent(next)}`,
}));

vi.mock("../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/site")>()),
  useFlags: () => ({ data: flags.data }),
}));

vi.mock("../api/client", () => ({
  api: { GET: vi.fn(() => Promise.resolve({ data: [], response: new Response() })) },
  unwrap: (r: { data: unknown }) => r.data,
}));

const { routes } = await import("../App");

function renderStart() {
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Startseite", () => {
  beforeEach(async () => {
    await act(() => i18n.changeLanguage("de"));
  });

  it("bietet ohne Sitzung die Anmeldung mit Rücksprung auf die Startseite, ohne Bereiche", () => {
    session.data = { staff: null, project_id: null };
    flags.data = {};
    renderStart();
    expect(screen.getByRole("link", { name: "Anmeldung für Fachleute" })).toHaveAttribute(
      "href",
      "/api/v1/auth/staff/login?next=%2F",
    );
    expect(screen.queryByRole("heading", { name: "Ihre Bereiche" })).not.toBeInTheDocument();
  });

  it("zeigt angemeldet die Bereiche nach Flags und Rollen", () => {
    session.data = {
      staff: { id: "1", email: "ops@buero.test", display_name: null, roles: ["architect", "ops"] },
      project_id: null,
    };
    flags.data = { site_selection: true };
    renderStart();
    expect(screen.queryByRole("link", { name: "Anmeldung für Fachleute" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ihre Bereiche" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Konfigurator" })).toHaveAttribute("href", "/grundstueck");
    expect(screen.getByRole("link", { name: "Emprise Analyse" })).toHaveAttribute("href", "/analyse");
    expect(screen.getByRole("link", { name: "Büro" })).toHaveAttribute("href", "/buero");
    expect(screen.getByRole("link", { name: "Verwaltung" })).toHaveAttribute("href", "/analyse/verwaltung");
  });

  it("blendet Konfigurator ohne Flag und Verwaltung ohne Rolle aus", () => {
    session.data = {
      staff: { id: "2", email: "arch@buero.test", display_name: null, roles: ["architect"] },
      project_id: null,
    };
    flags.data = {};
    renderStart();
    expect(screen.queryByRole("link", { name: "Konfigurator" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Verwaltung" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Emprise Analyse" })).toBeInTheDocument();
  });
});
