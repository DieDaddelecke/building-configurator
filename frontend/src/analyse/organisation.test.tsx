import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { MemberOut, OrganisationOut } from "../api/organisation";
import i18n from "../i18n";
import { OrganisationSeite } from "./OrganisationSeite";

const state = vi.hoisted(() => ({
  role: "admin" as "admin" | "member",
  update: vi.fn(),
  addError: null as unknown,
}));

const organisation: OrganisationOut = {
  id: "o1",
  name: "atelier-sud",
  display_name: "Atelier Sud",
  kind: "customer",
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
  useMembers: () => ({ data: members, isPending: false, isError: false }),
  useUpdateOrganisation: () => mutation(state.update, organisation),
  useAddMember: () => mutation(vi.fn(), members, () => state.addError),
  useChangeMemberRole: () => mutation(vi.fn()),
  useRemoveMember: () => mutation(vi.fn()),
}));

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.role = "admin";
  state.addError = null;
  state.update.mockReset();
});

it("zeigt einem Mitglied nur den Namen der Organisation", () => {
  state.role = "member";
  render(<OrganisationSeite />);
  expect(screen.getByRole("heading", { name: "Atelier Sud" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Mitglieder" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Name" })).not.toBeInTheDocument();
});

it("ändert den Anzeigenamen", async () => {
  const user = userEvent.setup();
  render(<OrganisationSeite />);
  const bereich = screen.getByRole("region", { name: "Name" });
  const feld = within(bereich).getByLabelText("Anzeigename");
  await user.clear(feld);
  await user.type(feld, " Atelier Sud Architectes ");
  await user.click(within(bereich).getByRole("button", { name: "Speichern" }));
  expect(state.update).toHaveBeenCalledWith({ display_name: "Atelier Sud Architectes" });
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
