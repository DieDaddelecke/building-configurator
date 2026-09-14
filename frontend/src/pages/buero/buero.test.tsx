import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";

const session = vi.hoisted(() => ({ data: undefined as unknown }));

vi.mock("../../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: session.data }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: (next = "/buero") => `/api/v1/auth/staff/login?next=${encodeURIComponent(next)}`,
}));

const { routes } = await import("../../App");

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Büro", () => {
  beforeEach(async () => {
    await act(() => i18n.changeLanguage("de"));
  });

  it("zeigt ohne Sitzung die Anmeldung mit Rücksprungziel", () => {
    session.data = { staff: null, project_id: null };
    renderAt("/buero");
    const login = screen.getByRole("link", { name: "Anmelden" });
    expect(login).toHaveAttribute("href", expect.stringContaining("/api/v1/auth/staff/login"));
  });

  it("zeigt mit Sitzung Navigation und Rollen", () => {
    session.data = {
      staff: { id: "1", email: "ops@buero.test", display_name: null, roles: ["ops"] },
      project_id: null,
    };
    renderAt("/buero");
    expect(screen.getByRole("navigation", { name: "Büro" })).toBeInTheDocument();
    expect(screen.getByText("ops")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
  });

  it("erklärt eine abgelehnte Anmeldung", () => {
    renderAt("/buero/kein-zugang?grund=mfa");
    expect(screen.getByRole("alert")).toHaveTextContent("zweiten Faktor");
  });
});
