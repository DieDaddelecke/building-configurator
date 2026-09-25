import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import type { UploadCandidateOut, UploadResultOut } from "../../api/site";
import i18n from "../../i18n";
import { ParzelleHochladen } from "./ParzelleHochladen";

type Callbacks = { onSuccess?: (result: UploadResultOut) => void };

const state = vi.hoisted(() => ({
  mutate: vi.fn(),
  error: null as unknown,
  next: null as UploadResultOut | null,
}));

vi.mock("../../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/site")>()),
  useUploadParcel: () => ({ mutate: state.mutate, reset: vi.fn(), isPending: false, error: state.error }),
}));

const kandidat = (index: number, name: string | null, x0: number, area: number): UploadCandidateOut => ({
  index,
  area_m2: area,
  layer: null,
  name,
  crs: "local",
  georeferenced: false,
  outline_local: [[[0, 0], [20, 0], [20, 30], [0, 30], [0, 0]]],
  outline_overview: [[[x0, 0], [x0 + 20, 0], [x0 + 20, 30], [x0, 30], [x0, 0]]],
});

const auswahl: UploadResultOut = {
  site: null,
  candidates: [kandidat(0, "65", 0, 600), kandidat(1, "66", 20, 360)],
  format: "pdf",
  scale: 500,
  scale_source: "file",
};

async function waehleDatei(name: string) {
  await userEvent.type(screen.getByLabelText("Bezeichnung des Grundstücks"), "Parzelle 65");
  await userEvent.upload(screen.getByLabelText("Datei"), new File(["%PDF-1.7"], name, { type: "application/pdf" }));
}

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.error = null;
  state.mutate.mockReset();
  state.mutate.mockImplementation((_vars: unknown, callbacks?: Callbacks) => {
    if (state.next) callbacks?.onSuccess?.(state.next);
  });
  state.next = auswahl;
});

it("zeigt für PDF das Maßstabsfeld, für DXF nicht", async () => {
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await waehleDatei("plan.dxf");
  expect(screen.queryByLabelText("Maßstab des Plans")).not.toBeInTheDocument();
  await userEvent.upload(screen.getByLabelText("Datei"), new File(["%PDF"], "extrait.pdf"));
  expect(screen.getByLabelText("Maßstab des Plans")).toHaveAttribute("placeholder", "aus dem Plan");
});

it("lässt die Parzelle im Plan wählen und übernimmt sie ohne eigenen Maßstab", async () => {
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await waehleDatei("extrait.pdf");
  await userEvent.click(screen.getByRole("button", { name: "Übernehmen" }));

  expect(screen.getByText(/2 geschlossene Flächen gefunden/)).toBeInTheDocument();
  expect(screen.getByText("Maßstab 1:500 aus dem Plan.")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("kontur-1"));
  expect(screen.getByRole("combobox")).toHaveValue("1");
  await userEvent.selectOptions(screen.getByRole("combobox"), "0");

  state.next = { ...auswahl, candidates: [] };
  await userEvent.click(screen.getByRole("button", { name: "Diese übernehmen" }));
  // Der Maßstab aus dem Plan geht nicht mit – so bleibt er in der Herkunft „aus dem Plan“
  expect(state.mutate).toHaveBeenLastCalledWith(
    expect.objectContaining({ index: 0, scale: undefined, addressLabel: "Parzelle 65" }),
    expect.anything(),
  );
});

it("bietet bei zwei Maßstäben beide zur Wahl an", async () => {
  state.error = new ApiError({
    status: 422,
    code: "upload_scale_ambiguous",
    title: "",
    scales: [500, 2000],
  } as never);
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await waehleDatei("plan.pdf");

  expect(screen.getByRole("alert")).toHaveTextContent("mehrere Maßstäbe");
  await userEvent.click(screen.getByRole("button", { name: "1:2000" }));
  expect(state.mutate).toHaveBeenLastCalledWith(expect.objectContaining({ scale: 2000 }), expect.anything());
});
