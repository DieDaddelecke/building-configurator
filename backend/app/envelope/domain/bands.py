"""Bauband an der Straße (`setback_street` mit `mode = range`; Plan G3 3.3).

Französische Pläne kennen zwei Bedeutungen: eine *bande d'implantation*, in der der **ganze** Hauptbaukörper
stehen muss (Treillières Uh: „hors bande d'implantation, les constructions nouvelles ne sont pas
autorisées“), und ein Band, in dem nur die **Straßenfassade** liegen muss („recul compris entre 0 et 5 m“).
G2 liefert dazu den Parameter `band`; fehlt er, gilt die weiteste Auslegung ohne und die engste mit
Flächenwirkung, mit Hinweis.
"""

from dataclasses import dataclass

import shapely
from shapely.geometry.base import BaseGeometry

from app.envelope.domain.inputs import Citation, EdgeInput
from app.envelope.domain.setbacks import RuleIndex, rule_for


@dataclass(frozen=True)
class Band:
    edge_seq: int
    zone_code: str
    min_m: float
    max_m: float
    band: str | None
    """`building`, `facade` oder `None` (Text sagt es nicht)."""
    polygon: BaseGeometry
    """Streifen bis `max_m` vor der Kante, auf das Grundstück beschnitten."""
    citation: Citation | None = None


def bands_for_zone(
    edges: list[EdgeInput], rules: RuleIndex, zone_code: str, area: BaseGeometry
) -> list[Band]:
    """Bänder aller Straßenkanten. Bei mehreren Straßen gilt jede (Uh: „par rapport à toutes les voies“);
    für die Fläche zählt ihre Vereinigung."""
    rule = rule_for(rules, "setback_street")
    if rule is None or rule.status != "effective" or rule.params.get("mode") != "range":
        return []
    minimum = float(rule.params.get("min_m") or 0.0)
    maximum = rule.params.get("max_m")
    if maximum is None:
        return []
    bands: list[Band] = []
    for edge in edges:
        if edge.kind != "street":
            continue
        strip = edge.geometry.buffer(float(maximum), cap_style="round").intersection(area)
        if strip.is_empty:
            continue
        bands.append(
            Band(
                edge_seq=edge.seq,
                zone_code=zone_code,
                min_m=minimum,
                max_m=float(maximum),
                band=rule.params.get("band"),
                polygon=strip,
                citation=rule.citation,
            )
        )
    return bands


def restriction(bands: list[Band], reading: str) -> BaseGeometry | None:
    """Fläche, auf die der Hauptbaukörper begrenzt ist, oder `None`, wenn das Band die Fläche nicht
    begrenzt (nur die Lage der Fassade, die H2 prüft)."""
    relevant = [b for b in bands if _limits_area(b.band, reading)]
    if not relevant:
        return None
    return shapely.union_all([b.polygon for b in relevant])


def _limits_area(band: str | None, reading: str) -> bool:
    if band == "building":
        return True
    if band == "facade":
        return False
    return reading == "strict"


def unclear(bands: list[Band]) -> bool:
    """Wahr, wenn ein Band ohne Angabe der Bedeutung vorliegt: dann unterscheiden sich die Konturen
    allein wegen der Auslegung, und darauf weist der Baurahmen hin."""
    return any(b.band is None for b in bands)
