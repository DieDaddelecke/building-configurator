import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import site from "../site/__fixtures__/site-ad0065.json";
import { CONFIGURED, COSTS, OPTIONS } from "./__fixtures__/konfiguration";
import { Kostenleiste } from "./Kostenleiste";
import { Linien } from "./Linien";
import { Nebenbauten } from "./Nebenbauten";
import { Optionen } from "./Optionen";
import { Vorentwurf } from "./Vorentwurf";
import { checkText, compassKey, localLabel, money } from "./format";

beforeEach(async () => {
  await act(() => i18n.changeLanguage("de"));
});

describe("Formatierung", () => {
  it("nennt die Himmelsrichtung aus dem Azimut", () => {
    expect([0, 44, 46, 90, 180, 268, 359, 360, -10].map(compassKey)).toEqual(["n", "ne", "ne", "e", "s", "w", "n", "n", "n"]);
  });

  it("formatiert Beträge und wählt die Bezeichnung nach Sprache", () => {
    expect(money(38_400_000, "de")).toBe("384.000 €");
    expect(localLabel({ label_de: "Terrasse", label_fr: "Terrasse bois" }, "de")).toBe("Terrasse");
    expect(localLabel({ label_de: "Terrasse", label_fr: "Terrasse bois" }, "fr")).toBe("Terrasse bois");
  });

  it("setzt den Namen der Option in den Text einer Prüfung", () => {
    const check = CONFIGURED.compliance!.checks[0]!;
    const text = checkText(check, i18n.t.bind(i18n), "de", { carport_2: "Carport zweistellig" });
    expect(text).toBe("Nebengebäude „Carport zweistellig“: 30,0 m² (höchstens 20,0 m²)");
  });

  it("gibt für einen Carport ohne Platz den Text der Option aus", () => {
    const text = checkText(
      { code: "no_valid_position", kind: "carport", status: "fail", binding: true, params: { subject: "carport_1" } },
      i18n.t.bind(i18n),
      "de",
      { carport_1: "Carport einstellig" },
    );
    expect(text).toBe("„Carport einstellig“ findet keine Stelle auf dem Grundstück");
  });
});

describe("Kostenleiste", () => {
  it("zeigt nur die gerundete Spanne mit ca. und die Steuerangabe", () => {
    render(<Kostenleiste costs={COSTS} />);
    expect(screen.getByTestId("korridor")).toHaveTextContent("ca. 449.000 € – 490.000 €");
    expect(screen.getByTestId("korridor")).toHaveTextContent("inkl. MwSt. (TTC)");
    expect(screen.getByText(/Schätzung, unverbindlich/)).toBeInTheDocument();
  });

  it("listet die Posten: Basis als Spanne, Terrasse je m², enthaltene Option ohne Betrag", () => {
    render(<Kostenleiste costs={COSTS} />);
    const posten = within(screen.getByTestId("posten"));
    expect(posten.getByText("Ligne")).toBeInTheDocument();
    expect(posten.getByText("393.600 € – 434.400 €")).toBeInTheDocument();
    expect(posten.getByText("Terrasse Holz (36,0 m² × 480 €)")).toBeInTheDocument();
    expect(posten.getByText("+ ca. 17.280 €")).toBeInTheDocument();
    const included = posten.getByText("Photovoltaik 6 kWp").closest("li")!;
    expect(within(included).getByText("enthalten")).toBeInTheDocument();
  });

  it("nennt den Grund, wenn es keinen Korridor gibt", () => {
    render(<Kostenleiste costs={{ ...COSTS, available: false, reason: "catalog_unavailable", display: null, net: null, gross: null, items: [] }} />);
    expect(screen.getByTestId("korridor-fehlt")).toHaveTextContent("Es ist noch kein Preiskatalog veröffentlicht.");
    expect(screen.queryByTestId("korridor")).not.toBeInTheDocument();
  });

  it("zeigt nichts ohne Auswertung", () => {
    const { container } = render(<Kostenleiste costs={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("französisch mit HT, wenn keine Mehrwertsteuer anfällt", async () => {
    await act(() => i18n.changeLanguage("fr"));
    render(<Kostenleiste costs={{ ...COSTS, vat_rate: 0 }} />);
    expect(screen.getByTestId("korridor")).toHaveTextContent(/env. 449.000 € – 490.000 €/);
    expect(screen.getByTestId("korridor")).toHaveTextContent("HT");
  });
});

describe("Linien", () => {
  it("zeigt Umfang und Aufpreis und wählt eine Linie", async () => {
    const onSelect = vi.fn();
    render(<Linien options={OPTIONS} onSelect={onSelect} pending={false} />);
    const base = within(screen.getByTestId("linie-base"));
    expect(base.getByText("im Basispreis")).toBeInTheDocument();
    expect(base.getByText("Fassade Putz")).toBeInTheDocument();
    const confort = within(screen.getByTestId("linie-confort"));
    expect(confort.getByText("+ ca. 40.800 €")).toBeInTheDocument();
    expect(confort.getByText("Enthält zusätzlich: Photovoltaik 6 kWp")).toBeInTheDocument();
    expect(confort.getByRole("button", { name: "Gewählt" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(base.getByRole("button", { name: "Base wählen" }));
    expect(onSelect).toHaveBeenCalledWith("base");
  });

  it("nimmt die gewählte Linie zurück, wenn man sie noch einmal anklickt", async () => {
    const onSelect = vi.fn();
    render(<Linien options={OPTIONS} onSelect={onSelect} pending={false} />);
    await userEvent.click(within(screen.getByTestId("linie-confort")).getByRole("button", { name: "Gewählt" }));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("weist bei nicht konformer RE2020 auf den Aufpreis hin und rechnet ihn ein", () => {
    const withBase = { ...OPTIONS, packages: OPTIONS.packages.map((p) => ({ ...p, selected: p.slug === "base" })) };
    render(<Linien options={withBase} onSelect={vi.fn()} pending={false} />);
    const hint = within(screen.getByTestId("energie"));
    expect(hint.getByText(/Klimazone H2b/)).toBeInTheDocument();
    expect(hint.getByText(/Base verfehlt den Schwellenwert knapp\. Für die Konformität braucht es: verstärkte Dämmung\. Aufpreis 11\.400 €, im Korridor eingerechnet\./)).toBeInTheDocument();
  });

  it("sagt bei fehlendem Befund, dass die Plattform die RE2020 nicht rechnet", () => {
    render(<Linien options={OPTIONS} onSelect={vi.fn()} pending={false} />);
    expect(within(screen.getByTestId("energie")).getByText(/Wärmeschutznachweis ist erforderlich/)).toBeInTheDocument();
  });

  it("erklärt, dass ohne Preiskatalog nichts wählbar ist", () => {
    render(<Linien options={{ ...OPTIONS, catalog_available: false, packages: [], options: [] }} onSelect={vi.fn()} pending={false} />);
    expect(screen.getByText("Es liegen noch keine Preise vor; Linien und Optionen sind noch nicht wählbar.")).toBeInTheDocument();
  });

  it("nennt die Gründe einer abgelehnten Linie", () => {
    render(
      <Linien
        options={OPTIONS}
        onSelect={vi.fn()}
        pending={false}
        failed
        reasons={[{ code: "not_offered", slug: "gold", other: null }]}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Diese Linie lässt sich nicht wählen. (Für diesen Typ nicht angeboten)");
  });
});

describe("Optionen", () => {
  it("gruppiert Außenanlagen und zeigt Preis, Fläche und die Einheit je m²", () => {
    render(<Optionen options={OPTIONS} onToggle={vi.fn()} pending={false} />);
    expect(screen.getByRole("heading", { name: "Außenanlagen" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Weitere Optionen" })).toBeInTheDocument();
    const terrace = within(screen.getByTestId("option-terrasse"));
    expect(terrace.getByText("+ ca. 17.280 € · 36,0 m² × 480 €")).toBeInTheDocument();
    expect(terrace.getByText("36,0 m²")).toBeInTheDocument();
    expect(screen.getByTestId("option-terrasse")).toHaveAttribute("aria-checked", "true");
  });

  it("markiert in der Linie Enthaltenes und schaltet es nicht um", async () => {
    const onToggle = vi.fn();
    render(<Optionen options={OPTIONS} onToggle={onToggle} pending={false} />);
    const pv = screen.getByTestId("option-pv");
    expect(pv).toHaveAttribute("aria-checked", "true");
    expect(pv).toBeDisabled();
    expect(within(pv).getByText("in der Linie enthalten")).toBeInTheDocument();
    await userEvent.click(pv);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("wählt und entfernt eine Option", async () => {
    const onToggle = vi.fn();
    render(<Optionen options={OPTIONS} onToggle={onToggle} pending={false} />);
    await userEvent.click(screen.getByTestId("option-keller"));
    expect(onToggle).toHaveBeenCalledWith("keller", true);
    await userEvent.click(screen.getByTestId("option-terrasse"));
    expect(onToggle).toHaveBeenCalledWith("terrasse", false);
  });

  it("sperrt eine Option und nennt Ausschluss und Verstoß mit Namen", async () => {
    const onToggle = vi.fn();
    render(<Optionen options={OPTIONS} onToggle={onToggle} pending={false} />);
    const blocked = screen.getByTestId("option-carport_2");
    expect(blocked).toBeDisabled();
    const reasons = within(screen.getByTestId("gruende-carport_2"));
    expect(reasons.getByText("Schließt „Carport einstellig“ aus")).toBeInTheDocument();
    expect(reasons.getByText("Nebengebäude „Carport zweistellig“: 30,0 m² (höchstens 20,0 m²)")).toBeInTheDocument();
    await userEvent.click(blocked);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("deaktiviert alles, solange gespeichert wird", () => {
    render(<Optionen options={OPTIONS} onToggle={vi.fn()} pending />);
    expect(screen.getByTestId("option-keller")).toBeDisabled();
  });

  it("nennt die Gründe einer abgelehnten Auswahl", () => {
    render(
      <Optionen
        options={OPTIONS}
        onToggle={vi.fn()}
        pending={false}
        failed
        refusedChecks={[{ code: "no_garden_facade", kind: "terrace", status: "fail", binding: true, params: { subject: "terrasse" } }]}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Terrasse „Terrasse Holz“: Dieser Typ hat keine Gartenfassade");
  });

  it("sagt bei einem leeren Angebot, dass nichts wählbar ist", () => {
    render(<Optionen options={{ ...OPTIONS, options: [] }} onToggle={vi.fn()} pending={false} />);
    expect(screen.getByText("Für diesen Typ sind keine Optionen angeboten.")).toBeInTheDocument();
  });
});

describe("Nebenbauten im Plan", () => {
  it("zeichnet Terrasse, Carport und Zufahrt", () => {
    const { container } = render(
      <svg>
        <Nebenbauten outbuildings={CONFIGURED.outbuildings} size={40} />
      </svg>,
    );
    expect(container.querySelector('[data-testid="terrasse"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="carport"]')).not.toBeNull();
    expect(container.querySelectorAll('[data-testid="zufahrt"]')).toHaveLength(1);
  });

  it("lässt nicht Platzierbares weg und zeichnet ohne Auswertung nichts", () => {
    const unplaced = { terrace: null, carport: { ...CONFIGURED.outbuildings!.carport!, placed: false, polygon_local: null }, driveways: [] };
    const { container } = render(
      <svg>
        <Nebenbauten outbuildings={unplaced} size={40} />
        <Nebenbauten outbuildings={null} size={40} />
      </svg>,
    );
    expect(container.querySelector('[data-testid="carport"]')).toBeNull();
    expect(container.querySelectorAll('[data-testid="nebenbauten"]')).toHaveLength(1);
  });
});

describe("Vorentwurf", () => {
  const renderIt = (onGehe = vi.fn()) =>
    render(
      <MemoryRouter>
        <Vorentwurf site={site as never} configuration={CONFIGURED} options={OPTIONS} onGehe={onGehe} />
      </MemoryRouter>,
    );

  it("zeigt Auswahl, Himmelsrichtung mit Konvergenz und Flächen", () => {
    renderIt();
    expect(screen.getByText("Confort")).toBeInTheDocument();
    expect(screen.getByText("Terrasse Holz")).toBeInTheDocument();
    expect(screen.getByText(/Photovoltaik 6 kWp/)).toBeInTheDocument();
    expect(screen.getByText("Gartenfassade: Süden (177°)")).toBeInTheDocument();
    expect(screen.getByText("Straßenfassade: Norden (357°)")).toBeInTheDocument();
    expect(screen.getByText("Wahre Himmelsrichtung; die Meridiankonvergenz von -3,3° ist berücksichtigt.")).toBeInTheDocument();
    const areas = within(screen.getByTestId("flaechen"));
    expect(areas.getByText("Unversiegelt").closest("tr")).toHaveTextContent("448,0 m²");
    expect(areas.getByText("Wege (Pauschale)").closest("tr")).toHaveTextContent("10,0 m²");
    expect(areas.getByText("Carport")).toBeInTheDocument();
  });

  it("listet die Prüfungen mit Verstößen zuerst und Namen der Optionen", () => {
    renderIt();
    const items = within(screen.getByTestId("vorentwurf-pruefungen")).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Nebengebäude „Carport zweistellig“");
    expect(items[0]).toHaveTextContent("verletzt");
    expect(items[1]).toHaveTextContent("Carport „Carport einstellig“: Für Nebengebäude fehlen Abstände");
    expect(items[2]).toHaveTextContent("Unversiegelte Fläche: 448,0 m² (mindestens 186,0 m²)");
  });

  it("führt über „Ändern“ zurück zu Typ, Linie, Optionen und Lage", async () => {
    const onGehe = vi.fn();
    renderIt(onGehe);
    const buttons = screen.getAllByRole("button", { name: "Ändern" });
    expect(buttons).toHaveLength(4);
    for (const button of buttons) await userEvent.click(button);
    expect(onGehe.mock.calls.map((call) => call[0])).toEqual(["type", "package", "options", "placement"]);
  });

  it("verweist für die Übergabe auf die Anfrage und behauptet keinen Preis", () => {
    renderIt();
    expect(screen.getByRole("link", { name: "Zur Anfrage" })).toHaveAttribute("href", "/grundstueck");
    expect(screen.getByText(/Übergabe des Vorentwurfs an das Architekturbüro folgt/)).toBeInTheDocument();
  });

  it("zeichnet den Lageplan mit den Nebenbauten", () => {
    const { container } = renderIt();
    expect(container.querySelector('[data-testid="terrasse"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="carport"]')).not.toBeNull();
  });
});
