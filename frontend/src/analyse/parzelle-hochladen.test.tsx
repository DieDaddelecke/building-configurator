import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { ScanPreviewOut, UploadCandidateOut, UploadResultOut } from "../api/site";
import i18n from "../i18n";
import { ParzelleHochladen } from "./ParzelleHochladen";

type Callbacks = { onSuccess?: (result: UploadResultOut) => void };

const state = vi.hoisted(() => ({
  mutate: vi.fn(),
  error: null as unknown,
  next: null as UploadResultOut | null,
  preview: null as ScanPreviewOut | null,
  formSite: vi.fn(),
}));

vi.mock("../api/site", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/site")>()),
  useUploadParcel: () => ({ mutate: state.mutate, reset: vi.fn(), isPending: false, error: state.error }),
  useScanPreview: () => ({ data: state.preview, isPending: false, isError: false, error: null }),
  useFormManualSite: () => ({ mutate: state.formSite, isPending: false, error: null }),
}));

const kandidat = (
  index: number,
  name: string | null,
  x0: number,
  area: number,
  [w, h, y0]: [number, number, number] = [20, 30, 0],
): UploadCandidateOut => ({
  index,
  area_m2: area,
  layer: null,
  name,
  crs: "local",
  georeferenced: false,
  outline_local: [[[0, 0], [w, 0], [w, h], [0, h], [0, 0]]],
  outline_overview: [[[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h], [x0, y0]]],
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
  state.formSite.mockReset();
  // Katasterauszug A5 quer mit 200 dpi, Maßstab 1:500 (wie `test_site_upload.scanned_plan` im Backend)
  state.preview = {
    page: 1,
    page_count: 1,
    image: "data:image/jpeg;base64,AAAA",
    width_px: 1654,
    height_px: 1166,
    paper_mm: [210, 148],
    scales: [500],
    scale: 500,
    metres_per_px: 0.063482,
  };
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
  // Im Plan gewählt, über die Auswahl wieder herausgenommen, dann aus der Liste gewählt
  await userEvent.click(screen.getByTestId("kontur-1"));
  expect(screen.getByTestId("kontur-1")).toHaveAttribute("data-auswahl", "gewaehlt");
  await userEvent.click(screen.getByRole("button", { name: "66 · 360,0 m² aus der Auswahl nehmen" }));
  expect(screen.queryByRole("button", { name: "Auswahl übernehmen" })).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("oder aus der Liste hinzufügen"), "0");
  expect(screen.getByTestId("kontur-0")).toHaveAttribute("data-auswahl", "gewaehlt");

  state.next = { ...auswahl, candidates: [] };
  await userEvent.click(screen.getByRole("button", { name: "Auswahl übernehmen" }));
  // Der Maßstab aus dem Plan geht nicht mit – so bleibt er in der Herkunft „aus dem Plan“
  expect(state.mutate).toHaveBeenLastCalledWith(
    expect.objectContaining({ index: [0], scale: undefined, addressLabel: "Parzelle 65" }),
    expect.anything(),
  );
});

it("legt die Teile einer zerschnittenen Parzelle zusammen und nimmt eine Fläche per zweitem Klick heraus", async () => {
  // 0 und 1 grenzen aneinander; 2 ist ein Haus in 0, 3 liegt abseits
  state.next = {
    ...auswahl,
    candidates: [
      kandidat(0, "65", 0, 600),
      kandidat(1, null, 20, 360, [12, 30, 0]),
      kandidat(2, null, 5, 48, [8, 6, 10]),
      kandidat(3, null, 60, 100, [10, 10, 0]),
    ],
  };
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await waehleDatei("extrait.pdf");
  await userEvent.click(screen.getByRole("button", { name: "Übernehmen" }));

  await userEvent.click(screen.getByTestId("kontur-0"));
  await userEvent.click(screen.getByTestId("kontur-1"));
  await userEvent.click(screen.getByTestId("kontur-3"));
  expect(screen.getByText("3 Flächen zusammen, ≈ 1.060 m²")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("kontur-3"));
  expect(screen.getByText("2 Flächen zusammen, ≈ 960 m²")).toBeInTheDocument();
  // Das Haus liegt in 65: Es gehört ohne Klick dazu und zählt auch mit Klick nicht doppelt
  expect(screen.getByTestId("kontur-2")).toHaveAttribute("data-auswahl", "enthalten");
  await userEvent.click(screen.getByTestId("kontur-2"));
  expect(screen.getByText("3 Flächen zusammen, ≈ 960 m²")).toBeInTheDocument();
  expect(screen.getByTestId("kontur-3")).not.toHaveAttribute("data-auswahl");

  await userEvent.click(screen.getByRole("button", { name: "Auswahl übernehmen" }));
  expect(state.mutate).toHaveBeenLastCalledWith(expect.objectContaining({ index: [0, 1, 2] }), expect.anything());
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

// AN7: Scan als Vorlage nachzeichnen (docs/PLAN_AN7_SCAN.md 3.5)

const MM = 200 / 25.4;
/** Rechteck 60 × 40 mm auf dem Blatt = 30 × 20 m bei 1:500. */
const RECHTECK: [number, number][] = [
  [40, 60],
  [100, 60],
  [100, 100],
  [40, 100],
];

function klicke(punkte: [number, number][]) {
  const svg = screen.getByRole("img", { name: "Vorlage zum Nachzeichnen" });
  // jsdom kennt kein Layout: Das Bild liegt in Originalgröße oben links
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1654, height: 1166, right: 1654, bottom: 1166, x: 0, y: 0, toJSON: () => ({}) });
  for (const [x, y] of punkte) fireEvent.click(svg, { clientX: x * MM, clientY: y * MM });
}

async function bildHochladen() {
  await userEvent.type(screen.getByLabelText("Bezeichnung des Grundstücks"), "Parzelle 65");
  await userEvent.upload(screen.getByLabelText("Datei"), new File(["png"], "extrait.png", { type: "image/png" }));
}

it("führt ein Bild direkt zum Nachzeichnen und übernimmt den Maßstab aus dem Plan", async () => {
  const fertig = vi.fn();
  render(<ParzelleHochladen projectId="p1" onFormed={fertig} onCancel={vi.fn()} />);
  await bildHochladen();
  expect(screen.queryByRole("button", { name: "Übernehmen" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Als Vorlage nachzeichnen" }));

  expect(screen.getByText("Im Plan gefunden: 1:500, Blatt 210 × 148 mm.")).toBeInTheDocument();
  const weiter = screen.getByRole("button", { name: "Weiter zum Bemaßen" });
  expect(weiter).toBeDisabled();
  klicke(RECHTECK);
  expect(screen.getByText(/4 Ecken/)).toHaveTextContent("Blattbreite in der Natur 105 m");
  await userEvent.click(weiter);

  // Kanten wie beim freien Zeichnen: 30 m nach Osten, 20 m nach Süden, 30 m nach Westen; Fläche ± 2 % (Abnahme 5)
  expect(screen.getByLabelText("Kante 1")).toHaveValue(30);
  expect(screen.getByLabelText("Kante 2")).toHaveValue(20);
  expect(screen.getByText(/Fläche: etwa 600 m²/)).toBeInTheDocument();
  expect(screen.getByLabelText("Adresse des Grundstücks")).toHaveValue("Parzelle 65");
  await userEvent.click(screen.getByRole("button", { name: "Dieses Grundstück übernehmen" }));
  expect(state.formSite).toHaveBeenCalledWith(
    expect.objectContaining({
      projectId: "p1",
      addressLabel: "Parzelle 65",
      trace: { file_name: "extrait.png", page: 1, scale_method: "plan", scale: 500 },
    }),
    { onSuccess: fertig },
  );
});

it("kalibriert über zwei Punkte, wenn das Bild keine verlässliche Auflösung hat", async () => {
  state.preview = { ...state.preview!, paper_mm: null, metres_per_px: null };
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await bildHochladen();
  await userEvent.click(screen.getByRole("button", { name: "Als Vorlage nachzeichnen" }));

  expect(screen.getByRole("radio", { name: /Maßstab aus dem Plan/ })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Ersten Punkt der Bezugsstrecke anklicken.");
  // Bezugsstrecke: die obere Grenze, 30 m
  klicke(RECHTECK.slice(0, 2));
  await userEvent.type(screen.getByLabelText("Länge"), "30");
  klicke(RECHTECK);
  await userEvent.click(screen.getByRole("button", { name: "Weiter zum Bemaßen" }));
  expect(screen.getByLabelText("Kante 2")).toHaveValue(20);
  await userEvent.click(screen.getByRole("button", { name: "Dieses Grundstück übernehmen" }));
  expect(state.formSite).toHaveBeenCalledWith(
    expect.objectContaining({
      trace: { file_name: "extrait.png", page: 1, scale_method: "calibrated", reference_m: 30 },
    }),
    expect.anything(),
  );
});

it("bietet bei einem gescannten PDF das Nachzeichnen an", async () => {
  state.error = new ApiError({ status: 422, code: "upload_pdf_no_vector", title: "" } as never);
  render(<ParzelleHochladen projectId="p1" onFormed={vi.fn()} onCancel={vi.fn()} />);
  await waehleDatei("scan.pdf");
  expect(screen.getByRole("alert")).toHaveTextContent("vermutlich ein Scan");
  await userEvent.click(screen.getByRole("button", { name: "Als Vorlage nachzeichnen" }));
  expect(screen.getByRole("heading", { name: "Scan nachzeichnen" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
  expect(screen.getByRole("heading", { name: "Parzelle aus einer Datei" })).toBeInTheDocument();
});
