"""Höchsthöhen einer Zone (Spez. 5.2.4 `max_height`, 5.9.4).

Die Höhe wird für die **engste** Kontur gebraucht, wenn ein Abstand von der Gebäudehöhe abhängt
(`max(min_m, faktor × H)`). Als Grenzwert angezeigt wird immer der Wert des Textes: Nennt der Plan nur
Geschosse, bleibt es bei `R+1+C`; die Umrechnung mit Standard-Geschosshöhen ist eine Annahme und wirkt
nur auf die Kontur (Plan 3.5).
"""

import re
from dataclasses import dataclass, field

from app.envelope.domain import tolerances as tol
from app.envelope.domain.inputs import RuleInput

_STOREYS = re.compile(r"^R(?:\+(\d))?(?:\+(C|A|CA|COMBLES))?$", re.IGNORECASE)


@dataclass(frozen=True)
class Heights:
    """Höchsthöhen einer Zone in Metern über dem Bezug der Regel; `None` heißt nicht ermittelt."""

    eave_m: float | None = None
    ridge_m: float | None = None
    parapet_m: float | None = None
    storeys: str | None = None
    reference: str = "natural_terrain"
    measured_at: str = "highest_point"
    assumptions: list[str] = field(default_factory=list)

    @property
    def highest_m(self) -> float | None:
        """Größte bekannte Höhe: die vorsichtige Wahl, wenn die Regel eine andere Bezugshöhe nennt."""
        known = [v for v in (self.ridge_m, self.parapet_m, self.eave_m) if v is not None]
        return max(known) if known else None

    def for_basis(self, basis: str | None) -> float | None:
        """Höhe zur Bezugsgröße eines höhenabhängigen Abstands (`eave`, `ridge`, `facade_point`).

        Fehlt der genannte Wert, gilt die größte bekannte Höhe: First ≥ Traufe, deshalb ist das nie zu
        niedrig, und eine zu kleine Höhe würde die engste Kontur zu groß machen.
        """
        if basis == "eave" and self.eave_m is not None:
            return self.eave_m
        return self.highest_m


def from_rule(rule: RuleInput | None) -> Heights:
    """Höhen aus der Regel `max_height`. Ohne wirksame Regel bleiben alle Werte offen."""
    if rule is None or rule.status != "effective":
        return Heights()
    params = rule.params
    storeys = params.get("storeys")
    heights = Heights(
        eave_m=_number(params.get("eave_m")),
        ridge_m=_number(params.get("ridge_m")),
        parapet_m=_number(params.get("parapet_m")),
        storeys=str(storeys) if storeys else None,
        reference=str(params.get("reference", "natural_terrain")),
        measured_at=str(params.get("measured_at", "highest_point")),
    )
    if heights.highest_m is not None or heights.storeys is None:
        return heights
    derived = from_storeys(heights.storeys)
    if derived is None:
        return heights
    eave, ridge = derived
    return Heights(
        eave_m=eave,
        ridge_m=ridge,
        parapet_m=None,
        storeys=heights.storeys,
        reference=heights.reference,
        measured_at=heights.measured_at,
        assumptions=[f"storey_height_{tol.STOREY_HEIGHT_M:.2f}"],
    )


def from_storeys(storeys: str, storey_height_m: float | None = None) -> tuple[float, float] | None:
    """Geschossangabe in Traufe und First umrechnen (Annahme, nur für die engste Kontur).

    `R+1+C`: Erdgeschoss und ein Obergeschoss ergeben die Traufe, das Dachgeschoss den First. Der Gabarit der
    Analyse (AN3) übergibt die Geschosshöhe aus den Annahmen des Projekts; sonst gelten die Standardhöhen.
    """
    match = _STOREYS.match(storeys.replace(" ", ""))
    if match is None:
        return None
    upper = int(match.group(1) or 0)
    top = (match.group(2) or "").upper()
    eave = (1 + upper) * (storey_height_m or tol.STOREY_HEIGHT_M)
    if top in ("C", "CA", "COMBLES"):
        return eave, eave + tol.ROOF_STOREY_RIDGE_M
    if top == "A":
        # Attikageschoss ist zurückgesetzt: die Traufe des Hauptbaukörpers bleibt, oben liegt die Attika
        return eave, eave + (storey_height_m or tol.ATTIC_STOREY_HEIGHT_M)
    return eave, eave


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
