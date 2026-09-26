"""Annahmen der Analyse (docs/PLAN_AN3_ANALYSE.md 3.4; Vorgaben in docs/ANNAHMEN.md EA04).

Jede Annahme ist ein Bereich: Das untere Ende der Nutzfläche rechnet mit der ungünstigen, das obere mit der
günstigen Seite. Der Architekt kann jeden Bereich je Projekt ändern.
"""

from dataclasses import asdict, dataclass
from typing import Any

ATTIC_MIN_RISE_M = 2.20
"""Höhe vom Boden des obersten Vollgeschosses bis zum First, ab der ein Dachgeschoss mit anrechenbarem
Streifen (Lichthöhe über 1,80 m, R.111-22) entsteht: 1,80 m plus Dachaufbau und Boden."""
ROOF_RISE_M = 5.00
"""Dachhöhe von der Traufe zum First, wenn der Plan nur die Firsthöhe nennt (wie `ROOF_STOREY_RIDGE_M` in
G3): untere Grenze der Vollgeschosse unter einem geneigten Dach."""


@dataclass(frozen=True)
class Span:
    low: float
    high: float


@dataclass(frozen=True)
class Parameters:
    storey_height_m: Span = Span(2.70, 3.00)
    """Geschosshöhe Boden bis Boden: 2,50 m Lichthöhe plus Decke; 3,00 m ist die übliche Umrechnung in PLU."""
    wall_share: Span = Span(0.08, 0.15)
    """Außenwandabzug: SDP wird innen gemessen, die Grundfläche außen (Wände 30–40 cm, 80–200 m²)."""
    attic_share: Span = Span(0.50, 0.75)
    """Anrechenbarer Anteil eines Dachgeschosses (Lichthöhe über 1,80 m) bei 30–45° Dachneigung."""
    attique_share: Span = Span(0.60, 0.80)
    """Anteil eines Attikageschosses an der Grundfläche (zurückgesetztes oberstes Geschoss)."""

    def as_json(self) -> dict[str, Any]:
        return {name: [span["low"], span["high"]] for name, span in asdict(self).items()}

    @staticmethod
    def from_json(data: dict[str, Any] | None) -> "Parameters":
        """Gespeicherte Annahmen; fehlende Einträge nehmen die Vorgabe (z. B. nach einer neuen Annahme)."""
        values: dict[str, Span] = {}
        for name, default in asdict(DEFAULTS).items():
            raw = (data or {}).get(name)
            values[name] = (
                Span(float(raw[0]), float(raw[1]))
                if isinstance(raw, list) and len(raw) == 2
                else Span(default["low"], default["high"])
            )
        return Parameters(**values)


DEFAULTS = Parameters()
BOUNDS: dict[str, tuple[float, float]] = {
    "storey_height_m": (2.40, 4.00),
    "wall_share": (0.0, 0.30),
    "attic_share": (0.0, 1.0),
    "attique_share": (0.0, 1.0),
}
"""Zulässige Werte je Annahme; außerhalb wäre es kein Wohngebäude mehr oder ein Tippfehler."""
