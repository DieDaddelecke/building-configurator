import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MyInquiryOut } from "../../api/inquiry";
import i18n from "../../i18n";

const state = vi.hoisted(() => ({
  projectId: "p1" as string | null,
  mine: undefined as unknown,
  message: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
  withdraw: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
  redeem: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
  request: { mutate: vi.fn(), isPending: false, isError: false, isSuccess: false, error: undefined as unknown },
}));

vi.mock("../../api/session", () => ({
  useSession: () => ({ isPending: false, isError: false, isSuccess: true, data: { staff: null, project_id: state.projectId } }),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  staffLoginUrl: () => "/login",
  sessionKey: ["session"],
}));

vi.mock("../../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/site")>()),
  useFlags: () => ({ isPending: false, isError: false, data: { submission: true } }),
}));

vi.mock("../../api/inquiry", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/inquiry")>()),
  useMyInquiry: () => ({ isPending: false, data: state.mine }),
}));

vi.mock("../../api/submission", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/submission")>()),
  useCustomerMessage: () => state.message,
  useWithdraw: () => state.withdraw,
  useRedeemAccess: () => state.redeem,
  useRequestAccess: () => state.request,
}));

const { routes } = await import("../../App");

const CASE: MyInquiryOut = {
  exists: true,
  number: "EMP-2026-000042",
  status: "rueckfrage",
  can_withdraw: true,
  submissions: [
    {
      sequence: 2,
      status: "current",
      created_at: "2026-09-19T12:00:00Z",
      deviation_count: 1,
      dossier_status: "ready",
      files: [
        { name: "EMP-2026-000042_F2_fr.pdf", kind: "pdf", locale: "fr", variant: null, size_bytes: 1000 },
        { name: "EMP-2026-000042_F2_de.pdf", kind: "pdf", locale: "de", variant: null, size_bytes: 1000 },
      ],
    },
    { sequence: 1, status: "superseded", created_at: "2026-09-18T12:00:00Z", deviation_count: 0, dossier_status: "pending", files: [] },
  ],
  messages: [{ id: "m1", author: "office", body: "Wie breit ist die Zufahrt?", created_at: "2026-09-19T13:00:00Z" }],
};

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("Mein Vorgang und Zugangslink (Modul V)", () => {
  beforeEach(async () => {
    state.projectId = "p1";
    state.mine = CASE;
    for (const hook of [state.message, state.withdraw, state.redeem, state.request]) {
      hook.mutate.mockReset();
      hook.isError = false;
    }
    state.request.isSuccess = false;
    await act(() => i18n.changeLanguage("de"));
  });

  afterEach(() => {
    window.location.hash = "";
  });

  it("zeigt Status, Fassungen mit PDF und die Nachrichten des Büros", async () => {
    renderAt("/vorgang");
    expect(screen.getByTestId("vorgang-status")).toHaveTextContent("Vorgang EMP-2026-000042 · Status: Rückfrage");
    const pdf = screen.getByRole("link", { name: "PDF (DE)" });
    expect(pdf).toHaveAttribute("href", "/api/v1/projects/p1/submissions/2/files/EMP-2026-000042_F2_de.pdf");
    expect(screen.getByText("Dossier wird erstellt …")).toBeInTheDocument();
    expect(screen.getByTestId("nachrichten")).toHaveTextContent("Wie breit ist die Zufahrt?");

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Nachricht an das Büro"), "Etwa 3 Meter.");
    await user.click(screen.getByRole("button", { name: "Senden" }));
    expect(state.message.mutate).toHaveBeenCalledWith("Etwa 3 Meter.", expect.anything());

    vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Vorgang zurückziehen" }));
    expect(state.withdraw.mutate).toHaveBeenCalled();
  });

  it("bietet ohne Vorgang den Zugangslink per E-Mail an", async () => {
    state.mine = { exists: false, submissions: [], messages: [], can_withdraw: false };
    renderAt("/vorgang");
    expect(screen.getByText("Auf diesem Gerät ist kein Vorgang bekannt.")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("E-Mail"), "camille@example.fr");
    await user.click(screen.getByRole("button", { name: "Link anfordern" }));
    expect(state.request.mutate).toHaveBeenCalledWith("camille@example.fr");
  });

  it("löst den Zugangslink aus dem Fragment ein und wechselt zum Vorgang", async () => {
    window.location.hash = "#t=abcdefghijklmnop.qrstuvwx";
    state.redeem.mutate.mockImplementation((_token: string, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
    const router = renderAt("/zugang");
    expect(state.redeem.mutate).toHaveBeenCalledWith("abcdefghijklmnop.qrstuvwx", expect.anything());
    await vi.waitFor(() => expect(router.state.location.pathname).toBe("/vorgang"));
  });

  it("erklärt einen ungültigen Link und bietet einen neuen an", () => {
    window.location.hash = "";
    renderAt("/zugang");
    expect(screen.getByRole("alert")).toHaveTextContent("Der Link ist ungültig oder abgelaufen.");
    expect(state.redeem.mutate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Link anfordern" })).toBeInTheDocument();
  });
});
