import { render, screen } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it } from "vitest";

import i18n from "../../i18n";
import { MassH } from "./Masskette";
import { Planblatt } from "./Planblatt";
import { boundsOf, polygonPath, toSvg } from "./PlanSvg";

describe("PlanSvg", () => {
  it("kehrt die Nordachse für SVG um", () => {
    expect(toSvg([3, 5])).toEqual([3, -5]);
  });

  it("zeichnet Ringe mit Löchern als einen Pfad", () => {
    const path = polygonPath([
      [[0, 0], [10, 0], [10, 10]],
      [[2, 2], [3, 2], [3, 3]],
    ]);
    expect(path).toBe("M0.000 0.000L10.000 0.000L10.000 -10.000ZM2.000 -2.000L3.000 -2.000L3.000 -3.000Z");
  });

  it("bestimmt die Ausdehnung", () => {
    expect(boundsOf([[1, -2], [4, 7], [-3, 0]])).toEqual({ minE: -3, minN: -2, maxE: 4, maxN: 7 });
  });
});

describe("Planblatt", () => {
  it("zeigt Schriftfeld und übersetzt den Maßstab", async () => {
    await act(() => i18n.changeLanguage("de"));
    const { rerender } = render(
      <Planblatt inhalt="Lageplan" schriftfeld={[{ label: "Parzelle", wert: "AB 123" }]}>
        <svg>
          <MassH x1={0} x2={10} y={1} label="10,00" />
        </svg>
      </Planblatt>,
    );
    expect(screen.getByText("AB 123")).toBeInTheDocument();
    expect(screen.getByText("10,00")).toBeInTheDocument();
    expect(screen.getByText(/Maßstab schematisch/)).toBeInTheDocument();

    await act(() => i18n.changeLanguage("fr"));
    rerender(
      <Planblatt inhalt="Plan de situation" schriftfeld={[{ label: "Parcelle", wert: "AB 123" }]}>
        <svg />
      </Planblatt>,
    );
    expect(screen.getByText(/Échelle schématique/)).toBeInTheDocument();
  });
});
