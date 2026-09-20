import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { ConfigurationOut } from "../api/configuration";
import type { ContactIn, MyInquiryOut } from "../api/inquiry";
import type { SubmitIn } from "../api/submission";
import i18n from "../i18n";
import { CONFIGURATION, CONFIGURED } from "./__fixtures__/konfiguration";
import { Uebergabe } from "./Uebergabe";

const NONE: MyInquiryOut = { exists: false, submissions: [], messages: [], can_withdraw: false };
const state = vi.hoisted(() => ({
  mine: undefined as unknown,
  contact: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
  submit: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
}));

vi.mock("../api/inquiry", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/inquiry")>()),
  useMyInquiry: () => ({ isPending: false, data: state.mine }),
  useSubmitContact: () => state.contact,
}));

vi.mock("../api/submission", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/submission")>()),
  useSubmitDesign: () => state.submit,
}));

function renderUebergabe(configuration: ConfigurationOut = CONFIGURATION) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <Uebergabe projectId="p1" configuration={configuration} names={{ carport_2: "Carport zweistellig" }} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Übergabe des Vorentwurfs (Modul V)", () => {
  beforeEach(async () => {
    state.mine = NONE;
    state.contact.mutate.mockReset();
    state.submit.mutate.mockReset();
    state.submit.isError = false;
    state.submit.error = undefined;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { headers: { "content-type": "application/json" } }));
    await act(() => i18n.changeLanguage("de"));
  });

  it("führt neue Kunden über Kontakt und Code zur Übergabe und zeigt die Vorgangsnummer", async () => {
    state.contact.mutate.mockImplementation((_body: ContactIn, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
    state.submit.mutate.mockImplementation(
      (_body: SubmitIn, opts?: { onSuccess?: (r: { number: string; sequence: number; status: "submitted" }) => void }) =>
        opts?.onSuccess?.({ number: "EMP-2026-000042", sequence: 1, status: "submitted" }),
    );
    renderUebergabe();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Name"), "Camille Martin");
    await user.type(screen.getByLabelText("E-Mail"), "camille.martin@example.fr");
    await user.click(screen.getByRole("button", { name: "Code anfordern" }));

    const send = screen.getByRole("button", { name: "Code bestätigen und übergeben" });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText("Bestätigungscode"), "123456");
    for (const checkbox of screen.getAllByRole("checkbox")) await user.click(checkbox);
    await user.click(send);

    expect(state.submit.mutate).toHaveBeenCalledWith(
      {
        review_stamp: CONFIGURATION.review_stamp,
        design_confirmation: true,
        transmission_design: true,
        deviations_acknowledged: false,
        code: "123456",
      },
      expect.anything(),
    );
    expect(screen.getByTestId("uebergabe-fertig")).toHaveTextContent("EMP-2026-000042, Fassung 1");
    expect(screen.getByRole("link", { name: "Zum Vorgang" })).toHaveAttribute("href", "/vorgang");
  });

  it("verlangt bei bestehendem Vorgang keinen Code, aber die Bestätigung der Abweichungen", async () => {
    state.mine = { ...NONE, exists: true, number: "EMP-2026-000007", status: "beantwortet", can_withdraw: true };
    renderUebergabe(CONFIGURED);
    expect(screen.getByText(/Vorgang EMP-2026-000007 besteht bereits/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Bestätigungscode")).not.toBeInTheDocument();
    expect(screen.getByTestId("uebergabe-abweichungen")).toHaveTextContent("Carport zweistellig");

    const user = userEvent.setup();
    const [ack, design, transmission] = screen.getAllByRole("checkbox");
    await user.click(design!);
    await user.click(transmission!);
    const send = screen.getByRole("button", { name: "Vorentwurf übergeben" });
    expect(send).toBeDisabled();
    await user.click(ack!);
    await user.click(send);
    expect(state.submit.mutate).toHaveBeenCalledWith(
      expect.objectContaining({ deviations_acknowledged: true, code: null }),
      expect.anything(),
    );
  });

  it("nennt, was sich seit dem Anzeigen geändert hat", () => {
    state.mine = { ...NONE, exists: true, number: "EMP-2026-000007", status: "neu", can_withdraw: true };
    state.submit.isError = true;
    state.submit.error = new ApiError({
      status: 409,
      code: "review_changed",
      title: "Konflikt",
      changes: ["rules", "result"],
    } as never);
    renderUebergabe();
    const banner = screen.getByTestId("uebergabe-geaendert");
    expect(banner).toHaveTextContent("Die Auswertung hat sich seit dem Anzeigen geändert");
    expect(banner).toHaveTextContent("Regeln des Bebauungsplans");
    expect(banner).toHaveTextContent("Ergebnis der Prüfung oder der Kosten");
  });
});
