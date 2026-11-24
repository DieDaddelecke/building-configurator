"""Rangfolge der Regelebenen (Vorgabe Soheyl 24.11.2026, BESTANDSAUFNAHME_PLU_PIPELINE S9d).

Allgemeine Bestimmungen („dispositions générales“, „toutes zones“) gelten zuerst; die Zone, dann der Sektor,
zuletzt die grafische Festsetzung (Plan) ersetzen sie. Allgemein 14 m und Zone 9 m ergibt 9 m; die ersetzte
Regel bleibt mit Fundstelle sichtbar. Zwei Ausnahmen:

- **Ergänzen:** Die speziellere Regel sagt ausdrücklich, dass sie hinzukommt („en complément“, „en outre“).
  Beide gelten; maßgeblich ist die strengere.
- **Überlagern:** Risikogebiete, Servituten und Schutzbereiche gelten neben der Zone. Maßgeblich ist die
  strengere Regel; die andere erscheint als Hinweis mit Fundstelle.

Ist nicht eindeutig, welche Regel strenger ist (verschiedene Parameter, Plan ohne Zahl), bleibt die Regel
offen (`ambiguous`) mit allen Fassungen – nie ein geratener Wert.
"""

import unicodedata
from collections.abc import Mapping
from typing import Any, Literal

from app.rules.domain.text import normalize

RuleLevel = Literal["general", "zone", "sector", "plan", "overlay"]
LEVEL_RANK: dict[str, int] = {"general": 0, "zone": 1, "sector": 2, "plan": 3}
"""Höherer Rang ersetzt niedrigeren. `overlay` steht außerhalb der Reihe."""

OVERLAY_MARKERS: tuple[str, ...] = (
    "inondab",
    "inondation",
    "submersion",
    "ppri",
    "pprn",
    "pprt",
    "plandeprevention",
    "risquesnaturels",
    "risquestechnologiques",
    "servitudedutilite",
    "servitudesdutilite",
    "monumenthistorique",
    "monumentshistoriques",
    "abordsdesmonuments",
    "sitepatrimonialremarquable",
    "perimetredeprotection",
)
"""Überlagernde Vorgaben in der Vergleichsform ohne Akzente (Überschwemmung, Risiken, Servituten,
Denkmalschutz)."""
COMPLEMENT_MARKERS: tuple[str, ...] = ("encomplement", "enoutre", "sajout", "cumulativ")
"""„en complément“, „en outre“, „s'ajoute(nt)“, „cumulativement“: Die Regel kommt hinzu, statt zu ersetzen."""

Direction = Literal["min", "max"]
DIRECTIONS: dict[str, Direction] = {
    "min_m": "min",
    "height_factor": "min",
    "full_soil_ratio": "min",
    "min_green_ratio": "min",
    "spaces_per_dwelling": "min",
    "spaces_per_m2_sdp": "min",
    "trees_per_m2": "min",
    "pitch_min_deg": "min",
    "max_m": "max",
    "ratio": "max",
    "ridge_m": "max",
    "eave_m": "max",
    "parapet_m": "max",
    "max_height_m": "max",
    "max_footprint_m2": "max",
    "sdp_m2": "max",
    "footprint_m2": "max",
    "on_boundary_max_height_m": "max",
    "pitch_max_deg": "max",
}
"""Richtung, in der ein Wert strenger ist: `min` – größer ist strenger, `max` – kleiner ist strenger."""
KIND_DIRECTIONS: dict[str, dict[str, Direction]] = {"unsealed_min": {"ratio": "min"}}
"""Abweichungen je Regelart: In `unsealed_min` ist `ratio` ein Mindestanteil."""
TOLERANCE = 1e-9


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize(value))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("'", "")


def is_overlay(quote: str | None) -> bool:
    plain = _plain(quote or "")
    return any(marker in plain for marker in OVERLAY_MARKERS)


def is_complement(quote: str | None) -> bool:
    plain = _plain(quote or "")
    return any(marker in plain for marker in COMPLEMENT_MARKERS)


def _direction(kind: str, name: str) -> Direction | None:
    return KIND_DIRECTIONS.get(kind, {}).get(name) or DIRECTIONS.get(name)


def stricter(
    kind: str, a_status: str, a: Mapping[str, Any], b_status: str, b: Mapping[str, Any]
) -> Literal["a", "b", "equal"] | None:
    """Welche von zwei Fassungen derselben Regelart ist strenger? None, wenn das nicht eindeutig ist.

    Eine wirksame Regel ist strenger als „nicht geregelt“. Sonst müssen beide wirksam sein, dieselben
    Parameter ohne Richtung gleich haben (Bauweise, Bezug, Mengen) und in allen gemeinsamen Zahlen in
    dieselbe Richtung zeigen. Eine Zahl, die nur eine Fassung hat, macht diese strenger."""
    if a_status == "not_regulated" and b_status == "effective":
        return "b"
    if b_status == "not_regulated" and a_status == "effective":
        return "a"
    if a_status != "effective" or b_status != "effective":
        return None
    votes: set[Literal["a", "b"]] = set()
    for name in sorted(set(a) | set(b)):
        left, right = a.get(name), b.get(name)
        direction = _direction(kind, name)
        numeric = all(
            value is None or (isinstance(value, int | float) and not isinstance(value, bool))
            for value in (left, right)
        )
        if direction is None or not numeric:
            if left != right:
                return None
            continue
        if left is None and right is None:
            continue
        if left is None or right is None:
            votes.add("a" if right is None else "b")
            continue
        difference = float(left) - float(right)
        if abs(difference) <= TOLERANCE:
            continue
        a_wins = difference > 0 if direction == "min" else difference < 0
        votes.add("a" if a_wins else "b")
    if not votes:
        return "equal"
    return next(iter(votes)) if len(votes) == 1 else None
