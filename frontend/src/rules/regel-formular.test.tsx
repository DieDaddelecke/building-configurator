import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { RuleKindFormOut } from "../api/rules";
import i18n from "../i18n";
import kindsFixture from "./__fixtures__/rule-kinds.json";
import { entwurfAus, parameterAus, parseZahl } from "./felder";
import { korrekturFehler, RegelFormular, type Vorlage } from "./RegelFormular";

const kinds = kindsFixture as unknown as RuleKindFormOut[];
const form = (kind: string) => kinds.find((k) => k.kind === kind)!;

beforeEach(async () => {
  await i18n.changeLanguage("de");
});

describe("Felder", () => {
  it("liest Zahlen mit Komma und erkennt Unlesbares", () => {
    expect(parseZahl(" 3,5 ")).toBe(3.5);
    expect(parseZahl("")).toBeNull();
    expect(Number.isNaN(parseZahl("3 m"))).toBe(true);
  });

  it("zeigt Anteile in Prozent und Dichten als Kehrwert", () => {
    const ratio = form("max_footprint_ratio").params;
    expect(entwurfAus(ratio, { ratio: 0.07 }, "de").ratio).toBe("7");
    expect(parameterAus(ratio, { ...entwurfAus(ratio, {}, "de"), ratio: "22,5" }).params.ratio).toBe(0.225);
    const parking = form("parking").params;
    expect(entwurfAus(parking, { spaces_per_m2_sdp: 0.02 }, "de").spaces_per_m2_sdp).toBe("50");
    expect(parameterAus(parking, { spaces_per_m2_sdp: "40", spaces_per_dwelling: "" }).params).toEqual({ spaces_per_m2_sdp: 0.025 });
    // Faktor bleibt Faktor (7.1 Nr. 6)
    const side = form("setback_side").params;
    expect(entwurfAus(side, { height_factor: 0.5 }, "fr").height_factor).toBe("0,5");
  });

  it("meldet Pflicht, Zahl und Grenzen, lässt Leeres weg", () => {
    const ratio = form("max_footprint_ratio").params;
    expect(parameterAus(ratio, { ratio: "" }).errors).toEqual({ ratio: "required" });
    expect(parameterAus(ratio, { ratio: "viel" }).errors).toEqual({ ratio: "number" });
    expect(parameterAus(ratio, { ratio: "120" }).errors).toEqual({ ratio: "range" });
    const height = form("max_height").params;
    const draft = entwurfAus(height, { eave_m: 7, ridge_m: 10 }, "de");
    expect(parameterAus(height, draft)).toEqual({
      params: { eave_m: 7, ridge_m: 10, reference: "natural_terrain", measured_at: "highest_point", includes_roof_installations: false },
      errors: {},
    });
  });
});

describe("RegelFormular", () => {
  const documents = [{ id: "plu", title: "PLUi Erdre et Gesvres", pageCount: 24 }];

  function renderForm(vorlage: Vorlage, props: Partial<Parameters<typeof RegelFormular>[0]> = {}) {
    const onSubmit = vi.fn();
    render(
      <RegelFormular
        kinds={kinds}
        zoneCode="Uh"
        vorlage={vorlage}
        documents={documents}
        pending={false}
        error={null}
        onSubmit={onSubmit}
        {...props}
      />,
    );
    return onSubmit;
  }

  it("korrigiert eine gelesene Regel mit Fundstelle und Begründung", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm({
      kind: "max_footprint_ratio",
      building_kind: "main",
      status: "effective",
      params: { ratio: 0.25 },
      source: { document_id: "plu", page: 8, quote: "limitée à 25%" },
    });
    expect(screen.queryByRole("textbox", { name: /json/i })).toBeNull();
    const anteil = screen.getByLabelText(/Anteil/);
    expect(anteil).toHaveValue("25");
    expect(screen.getByLabelText("Seite")).toHaveValue("8");
    const speichern = screen.getByRole("button", { name: "Korrektur speichern" });
    expect(speichern).toBeDisabled();
    await user.clear(anteil);
    await user.type(anteil, "20");
    await user.type(screen.getByLabelText("Begründung"), "Modification n° 2");
    await user.click(speichern);
    expect(onSubmit).toHaveBeenCalledWith({
      zone_code: "Uh",
      kind: "max_footprint_ratio",
      building_kind: "main",
      status: "effective",
      params: { ratio: 0.2 },
      note: "Modification n° 2",
      source: { document_id: "plu", page: 8, quote: "limitée à 25%" },
    });
  });

  it("prüft Felder vor dem Senden und nimmt „nicht ermittelt“ ohne Werte", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm({ kind: "max_footprint_ratio", building_kind: "any", status: "effective", params: {} });
    await user.type(screen.getByLabelText("Begründung"), "Lecture erronée");
    await user.click(screen.getByRole("button", { name: "Korrektur speichern" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Pflichtangabe")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Status"), "unknown");
    await user.click(screen.getByRole("button", { name: "Korrektur speichern" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ status: "unknown", params: {}, source: null }));
  });

  it("ergänzt eine Regel mit Wahl von Art und Baukörper", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm(
      { kind: "parking", building_kind: "any", status: "effective", params: {} },
      { kindChoices: ["parking", "setback_side"], buildingChoice: true },
    );
    expect(screen.queryByLabelText("Baukörper")).toBeNull();
    await user.selectOptions(screen.getByLabelText("Regel"), "setback_side");
    expect(screen.getByLabelText("Baukörper")).toHaveValue("main");
    await user.type(screen.getByLabelText(/Mindestabstand/), "4");
    await user.click(screen.getByLabelText("Bauen auf der Grenze zulässig"));
    await user.type(screen.getByLabelText("Begründung"), "Article 7 oublié");
    await user.click(screen.getByRole("button", { name: "Korrektur speichern" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "setback_side",
        building_kind: "main",
        params: { min_m: 4, allow_on_boundary: true, measured_from: "facade" },
      }),
    );
  });

  it("übersetzt Fehler des Servers", () => {
    const t = i18n.getFixedT("de");
    const invalid = new ApiError({ status: 422, code: "rule_params_invalid", title: "x", detail: "min_m_or_height_factor_required" });
    expect(korrekturFehler(t, invalid)).toBe("Mindestabstand oder Faktor der Höhe angeben");
    const implausible = new ApiError({ status: 422, code: "rule_params_invalid", title: "x", detail: "ratio=2" });
    expect(korrekturFehler(t, implausible)).toBe("Anteil: Wert unplausibel");
    expect(korrekturFehler(t, new ApiError({ status: 422, code: "zone_unknown", title: "x" }))).toBe(
      "Diese Zone gehört nicht zu den aktuellen Regeln des Projekts.",
    );
  });
});
