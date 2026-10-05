/**
 * Ausstattung und Ergebnis des Hausmodells mit den Bausteinen aus HM5: Neigung als Regler, Drehung des Dachs,
 * Ausstattungslinien, Sperrgründe des Kerns und Notizen mit Zahlen. Gerechnet wird mit dem Kern und den Testdaten
 * des R+1 mit Satteldach (Spanne 25–45°, Standard 35°).
 */

import type { HouseCandidate, HouseConfiguration } from "@emprise/domain";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { CHOSEN, DOCS, DOCS_BY_TEMPLATE, FACTS, TEMPLATES } from "./__fixtures__/haus";
import { Ausstattung, sperrgrund } from "./Ausstattung";
import { Ergebnisse } from "./Ergebnisse";
import { HausTypen } from "./HausTypen";

const R1 = DOCS_BY_TEMPLATE.demo_house_r1!;
const LEER: HouseConfiguration = { selections: {} };
const zahl = (slot: string, value: number): HouseConfiguration => ({
  selections: { [slot]: { value: { type: "number", value }, room_overrides: {}, element_overrides: {} } },
});

describe("Ausstattung des Hausmodells (HM5)", () => {
  beforeEach(async () => {
    await act(() => i18n.changeLanguage("de"));
  });

  it("stellt die Neigung in der Spanne der Form ein und speichert erst beim Loslassen", () => {
    const onChange = vi.fn();
    render(<Ausstattung docs={R1} configuration={LEER} onChange={onChange} />);
    const regler = screen.getByTestId("neigung");
    expect(regler).toHaveAttribute("min", "25");
    expect(regler).toHaveAttribute("max", "45");
    expect(regler).toHaveValue("35");
    expect(screen.getByTestId("neigung-wert")).toHaveTextContent("35° (von 25° bis 45°)");

    fireEvent.change(regler, { target: { value: "40" } });
    expect(screen.getByTestId("neigung-wert")).toHaveTextContent("40° (von 25° bis 45°)");
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.pointerUp(regler);
    expect(onChange).toHaveBeenCalledWith(zahl("roof_pitch", 40));
  });

  it("nimmt die Neigung auf den Standard der Form zurück", async () => {
    const onChange = vi.fn();
    render(<Ausstattung docs={R1} configuration={zahl("roof_pitch", 40)} onChange={onChange} />);
    expect(screen.getByTestId("neigung")).toHaveValue("40");
    await userEvent.click(within(screen.getByTestId("slot-roof_pitch")).getByRole("button", { name: "Standard" }));
    expect(onChange).toHaveBeenCalledWith(LEER);
  });

  it("zeigt beim Flachdach weder Regler noch Drehung", () => {
    render(<Ausstattung docs={DOCS} configuration={LEER} onChange={vi.fn()} />);
    expect(screen.queryByTestId("neigung")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("slot-roof_pitch")).getByText("Nur bei geneigtem Dach.")).toBeInTheDocument();
    expect(within(screen.getByTestId("slot-roof_rotation")).getByText(/keinen First/)).toBeInTheDocument();
  });

  it("dreht den First mit Preisunterschied; die Lage des Standards entfernt die Wahl", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Ausstattung docs={R1} configuration={LEER} onChange={onChange} />);
    const drehung = within(screen.getByTestId("slot-roof_rotation"));
    expect(drehung.getByRole("radio", { name: /^0°/ })).toBeChecked();
    // 1.364,54 € netto → 1.637,45 € brutto → 1.600 €
    expect(drehung.getByTestId("aufpreis-roof_rotation-90")).toHaveTextContent("ca. +1.600 €");
    expect(drehung.getByTestId("aufpreis-roof_rotation-180")).toHaveTextContent("gleicher Preis");
    await userEvent.click(drehung.getByRole("radio", { name: /^90°/ }));
    expect(onChange).toHaveBeenLastCalledWith(zahl("roof_rotation", 90));

    rerender(<Ausstattung docs={R1} configuration={zahl("roof_rotation", 90)} onChange={onChange} />);
    await userEvent.click(within(screen.getByTestId("slot-roof_rotation")).getByRole("radio", { name: /^0°/ }));
    expect(onChange).toHaveBeenLastCalledWith(LEER);
  });

  it("nennt den Grund, aus dem eine Dachform sperrt", () => {
    render(<Ausstattung docs={R1} configuration={LEER} onChange={vi.fn()} />);
    const form = within(screen.getByTestId("slot-roof_shape"));
    expect(form.getAllByText("sperrt die Übergabe – Eine Öffnung reicht über die Decke.")).toHaveLength(2);
  });

  it("übersetzt die Ablehnung einer Dachform durch den Kern", () => {
    const candidate: HouseCandidate = {
      option_value_id: "shape.half_hip",
      number: null,
      available_count: 0,
      target_count: 1,
      unavailable_reason: null,
      status: "blocked",
      price_delta: 0,
      rule_results: [
        {
          code: "roof_not_constructible",
          rule_id: null,
          outcome: "block",
          message: null,
          element_ids: ["roof"],
          suggestion: null,
          source: null,
          params: { reason: "gables_adjacent" },
        },
      ],
    };
    expect(sperrgrund(candidate, i18n.t, "de")).toBe("auf diesem Grundriss nicht baubar: zwei Giebel stießen aneinander");
  });

  it("setzt eine Ausstattungslinie mit ihrem Preis und zeigt sie als gewählt", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Ausstattung docs={R1} configuration={LEER} onChange={onChange} />);
    const linien = within(screen.getByTestId("linien"));
    expect(linien.getByText("Eigene Zusammenstellung")).toBeInTheDocument();
    expect(linien.getByTestId("aufpreis-line.traditional")).toHaveTextContent(/^ca\. \+/);
    await userEvent.click(linien.getByRole("radio", { name: /Traditionell/ }));
    // Satteldach und Tondachziegel sind beim R+1 Standard und entfallen; es bleibt die Ziegelfassade
    const gewaehlt = onChange.mock.calls[0]![0] as HouseConfiguration;
    expect(gewaehlt).toEqual({
      selections: { wall_profile: { value: { type: "option", option_value_id: "wall.brick" }, room_overrides: {}, element_overrides: {} } },
    });

    rerender(<Ausstattung docs={R1} configuration={gewaehlt} onChange={onChange} />);
    const danach = within(screen.getByTestId("linien"));
    expect(danach.getByRole("radio", { name: /Traditionell/ })).toBeChecked();
    expect(danach.queryByText("Eigene Zusammenstellung")).not.toBeInTheDocument();
  });

  it("nennt in den Notizen des Kerns Zahlen statt Werten", () => {
    const current = {
      ...CHOSEN,
      notes: [
        {
          slot_id: "roof_pitch",
          element_id: "roof",
          skipped_level: "global" as const,
          skipped_value_ids: [],
          skipped_number: 60,
          applied_value_id: null,
          applied_number: 35,
          code: "out_of_range" as const,
          reason: null,
        },
      ],
    };
    render(<Ergebnisse current={current} docs={R1} names={{}} veraltet={false} />);
    expect(
      within(screen.getByTestId("ergebnis-info")).getByText("Dachneigung: 60° liegt außerhalb der Spanne der Dachform; es gilt 35°."),
    ).toBeInTheDocument();
  });
});

describe("Haustypen mit geneigtem Dach", () => {
  it("nennt die Dachform mit ihren Neigungen", async () => {
    await act(() => i18n.changeLanguage("de"));
    const mansard = { ...TEMPLATES.templates[0]!, facts: { ...FACTS, storeys: "R+1", roof_form: "mansard", pitch_deg: null, pitches_deg: [25, 70] } };
    render(<HausTypen templates={[mansard]} selectedSlug={null} onSelect={vi.fn()} />);
    const karte = within(screen.getByTestId("haustyp-demo_house"));
    expect(karte.getByText("Mansarddach, 25° / 70°")).toBeInTheDocument();
    expect(karte.getByText("R+1")).toBeInTheDocument();
  });
});
