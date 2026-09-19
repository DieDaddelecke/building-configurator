import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { checkText, edgeName, sortChecks } from "./format";
import { CONFIGURATION, LIGNE, PLATEAU, PLATEAU_ADAPTE, ROOF_FORM_FAIL, TYPES } from "./__fixtures__/konfiguration";
import { TypKarten } from "./TypKarten";

describe("Typkarten", () => {
  beforeEach(async () => {
    await act(() => i18n.changeLanguage("de"));
  });

  it("zeigt zulässige Typen zuerst und nennt bei gesperrten alle Gründe", () => {
    render(<TypKarten types={[PLATEAU, LIGNE, PLATEAU_ADAPTE]} selectedSlug={null} onSelect={vi.fn()} />);
    const cards = screen.getAllByTestId(/^typ-/);
    expect(cards.map((c) => c.getAttribute("data-testid"))).toEqual(["typ-ligne", "typ-plateau_adapte", "typ-plateau"]);
    const blocked = within(screen.getByTestId("typ-plateau"));
    expect(blocked.getByText("Nicht zulässig")).toBeInTheDocument();
    expect(blocked.getByText("Dachform: Flachdach (zulässig: Satteldach, Walmdach)")).toBeInTheDocument();
    expect(blocked.getByRole("button", { name: "Diesen Typ wählen" })).toBeDisabled();
  });

  it("bietet bei einem gesperrten Typ den zulässigen als Vorschlag an", () => {
    render(<TypKarten types={TYPES.types} selectedSlug={null} onSelect={vi.fn()} />);
    const blocked = within(screen.getByTestId("typ-plateau"));
    expect(blocked.getByText(/Vorschlag: Plateau — angepasst/)).toBeInTheDocument();
    expect(blocked.getByRole("link", { name: "Plateau — angepasst ansehen" })).toHaveAttribute("href", "#typ-plateau_adapte");
  });

  it("wählt einen zulässigen Typ", async () => {
    const onSelect = vi.fn();
    render(<TypKarten types={TYPES.types} selectedSlug={null} onSelect={onSelect} />);
    await userEvent.click(within(screen.getByTestId("typ-ligne")).getByRole("button", { name: "Diesen Typ wählen" }));
    expect(onSelect).toHaveBeenCalledWith("ligne");
  });

  it("kennzeichnet den gewählten Typ und zeigt Hinweise als nicht bindend", () => {
    render(<TypKarten types={TYPES.types} selectedSlug="ligne" onSelect={vi.fn()} />);
    const chosen = within(screen.getByTestId("typ-ligne"));
    expect(chosen.getByText("Gewählter Typ")).toBeInTheDocument();
    expect(chosen.getByText("Zu beachten")).toBeInTheDocument();
    expect(chosen.getByText("Dach: Regel nicht ermittelt, nicht geprüft")).toBeInTheDocument();
  });

  it("zeigt Kennwerte der Karte", () => {
    render(<TypKarten types={[LIGNE]} selectedSlug={null} onSelect={vi.fn()} />);
    const card = within(screen.getByTestId("typ-ligne"));
    expect(card.getByText("12,0 × 8,0 m")).toBeInTheDocument();
    expect(card.getByText("Satteldach")).toBeInTheDocument();
    expect(card.getByText("R+1")).toBeInTheDocument();
  });

  it("zeigt eine leere Liste als Hinweis", () => {
    render(<TypKarten types={[]} selectedSlug={null} onSelect={vi.fn()} />);
    expect(screen.getByText("Es ist noch kein Haustyp veröffentlicht.")).toBeInTheDocument();
  });
});

describe("Texte der Prüfungen", () => {
  it("übersetzt Codes mit Messwert und Grenze in beiden Sprachen", async () => {
    const check = CONFIGURATION.evaluation!.checks[0]!;
    await act(() => i18n.changeLanguage("fr"));
    expect(checkText(check, i18n.t, "fr")).toBe("Recul sur voie : 5,00 m (minimum 5,00 m)");
    await act(() => i18n.changeLanguage("de"));
    expect(checkText(check, i18n.t, "de")).toBe("Abstand zur Straße: 5,00 m (mindestens 5,00 m)");
  });

  it("zeigt einen unbekannten Code als Code statt leer", () => {
    expect(checkText({ ...ROOF_FORM_FAIL, code: "neu_und_unbekannt" }, i18n.t, "de")).toBe("neu_und_unbekannt");
  });

  it("ordnet Verstöße vor Hinweisen und Bestandenem", () => {
    const order = sortChecks(CONFIGURATION.evaluation!.checks.concat(ROOF_FORM_FAIL)).map((c) => c.status);
    expect(order).toEqual(["fail", "hint", "pass", "pass"]);
  });

  it("benennt Kanten mit Art und Nummer", async () => {
    await act(() => i18n.changeLanguage("de"));
    expect(edgeName("street", 3, i18n.t)).toBe("Straße (3)");
    expect(edgeName("unbekannt", 4, i18n.t)).toBe("Grenze (4)");
  });
});
