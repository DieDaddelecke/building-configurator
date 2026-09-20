import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfirmIn, ContactIn, MyInquiryOut } from "../api/inquiry";
import i18n from "../i18n";
import { AnfrageFormular } from "./AnfrageFormular";

const NONE: MyInquiryOut = { exists: false, submissions: [], messages: [], can_withdraw: false };
const myInquiry: { data?: MyInquiryOut; isPending: boolean } = { data: NONE, isPending: false };
const submit = { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown };
const confirm = { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown };

vi.mock("../api/inquiry", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/inquiry")>()),
  useMyInquiry: () => myInquiry,
  useSubmitContact: () => submit,
  useConfirmContact: () => confirm,
}));

function renderFormular() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AnfrageFormular projectId="p1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Anfrageformular (Modul A)", () => {
  beforeEach(async () => {
    myInquiry.data = NONE;
    myInquiry.isPending = false;
    submit.mutate.mockReset();
    confirm.mutate.mockReset();
    submit.isError = false;
    confirm.isError = false;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { headers: { "content-type": "application/json" } }),
    );
    await act(() => i18n.changeLanguage("de"));
  });

  it("sendet den Kontakt und wechselt zur Codebestätigung", async () => {
    submit.mutate.mockImplementation((_body: ContactIn, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
    renderFormular();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Name"), "Camille Martin");
    await user.type(screen.getByLabelText("E-Mail"), "camille.martin@example.fr");
    await user.click(screen.getByRole("button", { name: "Code anfordern" }));

    expect(submit.mutate).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Camille Martin", email: "camille.martin@example.fr" }),
      expect.anything(),
    );
    expect(screen.getByLabelText("Bestätigungscode")).toBeInTheDocument();
  });

  it("bestätigt den Code mit beiden Einwilligungen und zeigt die Vorgangsnummer", async () => {
    submit.mutate.mockImplementation((_body: ContactIn, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
    confirm.mutate.mockImplementation(
      (_body: ConfirmIn, opts?: { onSuccess?: (r: { number: string }) => void }) =>
        opts?.onSuccess?.({ number: "EMP-2026-000042" }),
    );
    renderFormular();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Name"), "Camille Martin");
    await user.type(screen.getByLabelText("E-Mail"), "camille.martin@example.fr");
    await user.click(screen.getByRole("button", { name: "Code anfordern" }));

    await user.type(screen.getByLabelText("Bestätigungscode"), "123456");
    for (const checkbox of screen.getAllByRole("checkbox")) await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Anfrage absenden" }));

    expect(confirm.mutate).toHaveBeenCalledWith(
      { code: "123456", simulation_confirmation: true, transmission_office: true },
      expect.anything(),
    );
    expect(screen.getByText(/EMP-2026-000042/)).toBeInTheDocument();
  });

  it("zeigt bei bestehender Anfrage nur die Zusammenfassung", () => {
    myInquiry.data = { ...NONE, exists: true, number: "EMP-2026-000007", status: "in_bearbeitung", can_withdraw: true };
    renderFormular();
    expect(screen.getByText(/EMP-2026-000007/)).toBeInTheDocument();
    expect(screen.getByText(/in Bearbeitung/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zum Vorgang" })).toHaveAttribute("href", "/vorgang");
  });
});
