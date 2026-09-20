import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InquiryDetailOut } from "../../api/inquiry";
import type { StaffSubmissionOut } from "../../api/submission";
import i18n from "../../i18n";
import { Fassungen, Nachrichten } from "./AnfrageFassungen";

const state = vi.hoisted(() => ({
  message: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
  regenerate: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown },
}));

vi.mock("../../api/submission", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/submission")>()),
  useOfficeMessage: () => state.message,
  useRegenerateDossier: () => state.regenerate,
}));

const summary: StaffSubmissionOut["summary"] = {
  type_name: "Ligne",
  type_version: 2,
  type_retired: true,
  package_label_de: "Confort",
  package_label_fr: "Confort",
  options: [
    { slug: "terrasse", label_de: "Terrasse Holz", label_fr: "Terrasse bois", included: false },
    { slug: "carport_2", label_de: "Carport zweistellig", label_fr: "Carport double", included: false },
  ],
  costs_display: { min_cents: 44_900_000, max_cents: 49_000_000 },
  vat_rate: 0.2,
  catalog_version: 1,
  deviations: [
    { code: "annex_footprint", kind: "annex", status: "fail", binding: true, measured: 30, limit: 20, unit: "m2", params: { subject: "carport_2" } },
  ],
  site_origin: "parcel",
};

const submission = (sequence: number, extra: Partial<StaffSubmissionOut> = {}): StaffSubmissionOut => ({
  sequence,
  status: "current",
  created_at: "2026-09-19T12:00:00Z",
  configuration_revision: 5,
  deviations_acknowledged: true,
  deviation_count: 1,
  open_points: 2,
  dossier_status: "ready",
  dossier_error: null,
  files: [
    { name: "EMP_F2_fr.pdf", kind: "pdf", locale: "fr", variant: null, size_bytes: 1 },
    { name: "EMP_F2_L93.dxf", kind: "dxf", locale: null, variant: "L93", size_bytes: 1 },
  ],
  summary,
  ...extra,
});

const DETAIL = {
  project_id: "p1",
  number: "EMP-2026-000042",
  status: "neu",
  configuration_revision: 7,
  submissions: [submission(2), submission(1, { status: "superseded", dossier_status: "failed", dossier_error: "RuntimeError: Test", files: [] })],
  messages: [{ id: "m1", author: "customer", body: "Gibt es einen Keller?", created_at: "2026-09-19T13:00:00Z" }],
} as unknown as InquiryDetailOut;

function renderDetail() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Fassungen projectId="p1" data={DETAIL} />
      <Nachrichten projectId="p1" data={DETAIL} />
    </QueryClientProvider>,
  );
}

describe("Büro: Fassungen und Nachrichten (Modul V)", () => {
  beforeEach(async () => {
    state.message.mutate.mockReset();
    state.regenerate.mutate.mockReset();
    await act(() => i18n.changeLanguage("de"));
  });

  it("zeigt die übergebene Fassung mit Abweichungen, Korridor und Dateien", () => {
    renderDetail();
    const current = screen.getByTestId("fassung-2");
    expect(current).toHaveTextContent("Fassung 2");
    expect(current).toHaveTextContent("Die Konfiguration des Kunden wurde seit dieser Fassung geändert (Revision 7)");
    expect(current).toHaveTextContent("Katalogstand inzwischen zurückgezogen");
    expect(current).toHaveTextContent("1 Abweichungen, vom Kunden bestätigt");
    expect(current).toHaveTextContent("Nebengebäude „Carport zweistellig“");
    expect(current).toHaveTextContent("ca. 449.000 € – 490.000 €");
    expect(within(current).getByRole("link", { name: "DXF Lambert-93" })).toHaveAttribute(
      "href",
      "/api/v1/admin/projects/p1/submissions/2/files/EMP_F2_L93.dxf",
    );
  });

  it("lässt ein gescheitertes Dossier neu erzeugen und schreibt dem Kunden", async () => {
    renderDetail();
    const user = userEvent.setup();
    const failed = screen.getByTestId("fassung-1");
    expect(failed).toHaveTextContent("Dossier fehlgeschlagen: RuntimeError: Test");
    await user.click(within(failed).getByRole("button", { name: "Dossier neu erzeugen" }));
    expect(state.regenerate.mutate).toHaveBeenCalledWith(1);

    expect(screen.getByText("Gibt es einen Keller?")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Nachricht an den Kunden"), "Nein, der Typ hat keinen Keller.");
    await user.click(screen.getByRole("button", { name: "Senden" }));
    expect(state.message.mutate).toHaveBeenCalledWith("Nein, der Typ hat keinen Keller.", expect.anything());
  });
});
