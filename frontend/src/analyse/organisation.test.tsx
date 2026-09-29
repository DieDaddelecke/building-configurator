import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { ApiKeyCreatedOut, MemberOut, OrganisationOut, UsageOut } from "../api/organisation";
import i18n from "../i18n";
import { kontrastZuWeiss, OrganisationSeite } from "./OrganisationSeite";

const state = vi.hoisted(() => ({
  role: "admin" as "admin" | "member",
  create: vi.fn(),
  update: vi.fn(),
  addError: null as unknown,
}));

const organisation: OrganisationOut = {
  id: "o1",
  name: "atelier-sud",
  display_name: "Atelier Sud",
  kind: "customer",
  address_lines: ["12 rue de la Paix", "44000 Nantes"],
  phone: "02 40 00 00 00",
  email: null,
  website: null,
  registration: "Ordre des architectes S12345",
  accent_color: "#1d4ed8",
  has_logo: false,
  branding_revision: 3,
};

const usage: UsageOut = {
  budget_month_usd: 20,
  ocr_pages_month: 2000,
  months: [
    { month: "2026-09", cost_usd: 12.34, ocr_pages: 48 },
    { month: "2026-08", cost_usd: 3.5, ocr_pages: 0 },
  ],
};

const members: MemberOut[] = [
  {
    id: "u1",
    email: "chef@atelier-sud.fr",
    display_name: "Chef",
    role: "admin",
    active: true,
    last_login_at: "2026-09-28T08:00:00Z",
    signed_in: true,
  },
  {
    id: "u2",
    email: "neu@atelier-sud.fr",
    display_name: null,
    role: "member",
    active: true,
    last_login_at: null,
    signed_in: false,
  },
];

const created: ApiKeyCreatedOut = {
  id: "k1",
  name: "CAD",
  prefix: "ab12cd34",
  scopes: ["read"],
  created_at: "2026-09-29T10:00:00Z",
  expires_at: "2027-09-29T10:00:00Z",
  last_used_at: null,
  revoked_at: null,
  token: "emp_beispiel",
};

const mutation = (fn: (...args: unknown[]) => void, result?: unknown, error: () => unknown = () => null) => ({
  mutate: (body: unknown, options?: { onSuccess?: (value: unknown) => void }) => {
    fn(body);
    options?.onSuccess?.(result);
  },
  isPending: false,
  isSuccess: false,
  get error() {
    return error();
  },
});

vi.mock("../api/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/session")>()),
  useSession: () => ({
    data: {
      project_id: null,
      staff: {
        id: "u1",
        email: "chef@atelier-sud.fr",
        display_name: "Chef",
        roles: ["architect"],
        organisation: { id: "o1", display_name: "Atelier Sud", kind: "customer", role: state.role },
      },
    },
  }),
}));

vi.mock("../api/organisation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/organisation")>()),
  useOrganisation: () => ({ data: organisation, isPending: false, isError: false }),
  useUsage: () => ({ data: usage, isPending: false, isError: false }),
  useMembers: () => ({ data: members, isPending: false, isError: false }),
  useApiKeys: () => ({ data: [], isPending: false, isError: false }),
  useUpdateOrganisation: () => mutation(state.update, organisation),
  useUploadLogo: () => mutation(vi.fn()),
  useRemoveLogo: () => mutation(vi.fn()),
  useAddMember: () => mutation(vi.fn(), members, () => state.addError),
  useChangeMemberRole: () => mutation(vi.fn()),
  useRemoveMember: () => mutation(vi.fn()),
  useCreateApiKey: () => mutation(state.create, created),
  useRevokeApiKey: () => mutation(vi.fn()),
}));

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.role = "admin";
  state.addError = null;
  state.create.mockReset();
  state.update.mockReset();
});

it("zeigt einem Mitglied nur den Verbrauch", () => {
  state.role = "member";
  render(<OrganisationSeite />);
  expect(screen.getByRole("heading", { name: "Atelier Sud" })).toBeInTheDocument();
  expect(screen.getByTestId("usage-cost")).toHaveTextContent("12,34 $ von 20,00 $");
  expect(screen.getByTestId("usage-ocr")).toHaveTextContent("48 von 2000 Seiten");
  expect(screen.getByRole("table", { name: "Verbrauch der letzten Monate" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Mitglieder" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "API-Schlüssel" })).not.toBeInTheDocument();
});

it("zeigt einen neuen Schlüssel einmal und legt ihn nur lesend an, wenn nichts anderes gewählt ist", async () => {
  const user = userEvent.setup();
  render(<OrganisationSeite />);
  const bereich = screen.getByRole("region", { name: "API-Schlüssel" });
  await user.type(within(bereich).getByLabelText("Name (wofür)"), "CAD");
  await user.click(within(bereich).getByRole("button", { name: "Schlüssel anlegen" }));
  expect(state.create).toHaveBeenCalledWith({ name: "CAD", scopes: ["read"], days: 365 });
  expect(within(bereich).getByTestId("api-key-token")).toHaveTextContent("emp_beispiel");
  await user.click(within(bereich).getByRole("button", { name: "Fertig" }));
  expect(within(bereich).queryByTestId("api-key-token")).not.toBeInTheDocument();
});

it("prüft die Akzentfarbe vor dem Speichern und zeigt die Vorschau des Berichtskopfs", async () => {
  const user = userEvent.setup();
  render(<OrganisationSeite />);
  const bereich = screen.getByRole("region", { name: "Erscheinungsbild" });
  const vorschau = within(bereich).getByTestId("branding-preview");
  expect(vorschau).toHaveTextContent("Atelier Sud");
  expect(vorschau).toHaveTextContent("44000 Nantes");
  expect(vorschau).toHaveTextContent("Ordre des architectes S12345");

  const farbe = within(bereich).getByLabelText("Akzentfarbe");
  await user.clear(farbe);
  await user.type(farbe, "#ffff00");
  expect(within(bereich).getByText(/Zu hell/)).toBeInTheDocument();
  expect(within(bereich).getByRole("button", { name: "Speichern" })).toBeDisabled();

  await user.clear(farbe);
  await user.type(farbe, "#1D4ED8");
  await user.click(within(bereich).getByRole("button", { name: "Speichern" }));
  expect(state.update).toHaveBeenCalledWith(
    expect.objectContaining({
      display_name: "Atelier Sud",
      address_lines: ["12 rue de la Paix", "44000 Nantes"],
      accent_color: "#1d4ed8",
    }),
  );
});

it("nennt Mitglieder mit Anmeldestand und übersetzt Fehler des Servers", () => {
  state.addError = new ApiError({ status: 409, code: "member_of_other_organisation", title: "Conflict" });
  render(<OrganisationSeite />);
  const bereich = screen.getByRole("region", { name: "Mitglieder" });
  expect(within(bereich).getByText("noch nicht angemeldet")).toBeInTheDocument();
  // Sich selbst entfernt man nicht; die anderen schon
  expect(within(bereich).getAllByRole("button", { name: "Entfernen" })).toHaveLength(1);
  expect(within(bereich).getByRole("alert")).toHaveTextContent("Diese Adresse gehört zu einer anderen Organisation.");
});

it("rechnet den Kontrast zu Weiß nach WCAG", () => {
  expect(kontrastZuWeiss("#ffffff")).toBeCloseTo(1);
  expect(kontrastZuWeiss("#000000")).toBeCloseTo(21);
  expect(kontrastZuWeiss("#2b45b0")).toBeGreaterThan(4.5);
  expect(kontrastZuWeiss("#ffff00")).toBeLessThan(4.5);
  expect(kontrastZuWeiss("blau")).toBeNull();
});
