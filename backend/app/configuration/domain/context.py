"""Grundstück und Regeln als Eingabe von H2 (Plan H2 3.7, 4.1).

Aus der Eingabe von G3 (`EnvelopeInput`) und ihrem Ergebnis (`Envelope`) entsteht ein Kontext in lokalen
Metern. Zwei Arten:

- `rules`: Ein Baurahmen liegt vor. Die Zonen-Teilflächen mit Regeln sind die Flächen, in denen ein Haus
  stehen darf; ihre Regeln gelten für ein Haus in dieser Teilfläche.
- `free`: Kein Baurahmen (Weg E, Regeln nicht verfügbar oder noch in Auswertung). Der Umriss ist die
  einzige Fläche, es gibt keine Abstandsprüfung (D13).
"""

import math
from dataclasses import dataclass, field, replace

import shapely
from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from app.configuration.domain.geometry import polygons, segments, union
from app.configuration.domain.house import azimuth_deg
from app.envelope.domain.bands import Band
from app.envelope.domain.derive import Envelope
from app.envelope.domain.inputs import EdgeInput, EnvelopeInput, TerrainInput
from app.envelope.domain.setbacks import RuleIndex, index_rules

Point = tuple[float, float]

FREE_REASONS = ("manual_sketch", "rules_unavailable", "rules_in_progress")


@dataclass(frozen=True)
class PartContext:
    """Zonen-Teilfläche mit ihren Regeln (leer im freien Modus)."""

    zone_code: str
    polygon: BaseGeometry
    area_m2: float
    rules: RuleIndex = field(default_factory=dict)
    bands: list[Band] = field(default_factory=list)


@dataclass(frozen=True)
class SiteContext:
    mode: str
    """`rules` oder `free`."""
    free_reason: str | None
    origin: Point
    polygon: Polygon
    edges: list[EdgeInput]
    parts: list[PartContext]
    no_build: BaseGeometry | None
    restricted: BaseGeometry | None
    terrain: TerrainInput
    street_seq: int | None
    """Nummer der Hauptstraßenkante, sonst `None`."""
    reference_normal_deg: float
    """Azimut, in dem die Straßenfassade zeigen soll: Normale der Hauptstraßenkante, sonst der längsten
    Kante."""
    has_street: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def is_free(self) -> bool:
        return self.mode == "free"

    @property
    def street_tangent_deg(self) -> float:
        return (self.reference_normal_deg + 90.0) % 180.0


def build_context(data: EnvelopeInput, envelope: Envelope | None) -> SiteContext:
    """Kontext in lokalen Metern; `envelope = None` für ein frei gezeichnetes Grundstück."""
    origin = data.site.local_origin
    polygon = _local(orient(data.site.polygon, sign=1.0), origin)
    free_reason = _free_reason(data, envelope)
    edges = [] if free_reason else [replace(e, geometry=_local(e.geometry, origin)) for e in data.site.edges]
    street_normal, has_street = _reference_normal(data, polygon)

    if free_reason or envelope is None:
        parts = [PartContext(zone_code="", polygon=polygon, area_m2=float(polygon.area))]
        no_build = restricted = None
        warnings: list[str] = []
    else:
        rules = {zone.code: index_rules(zone.rules) for zone in data.zones}
        bands = [replace(b, polygon=_local(b.polygon, origin)) for b in envelope.bands]
        parts = [
            PartContext(
                zone_code=part.zone_code,
                polygon=_local(part.geometry, origin),
                area_m2=part.area_m2,
                rules=rules.get(part.zone_code, {}),
                bands=[b for b in bands if b.zone_code == part.zone_code],
            )
            for part in envelope.parts
            if part.excluded is None and not part.geometry.is_empty
        ]
        no_build = _effect_area(envelope, ("no_build",), origin)
        restricted = _effect_area(envelope, ("restricts",), origin)
        warnings = list(envelope.warnings)
    return SiteContext(
        mode="free" if free_reason else "rules",
        free_reason=free_reason,
        origin=origin,
        polygon=polygon,
        edges=edges,
        parts=parts,
        no_build=no_build,
        restricted=restricted,
        terrain=data.site.terrain,
        street_seq=data.site.main_street_seq if not free_reason else None,
        reference_normal_deg=street_normal,
        has_street=has_street and not free_reason,
        warnings=warnings,
    )


def _free_reason(data: EnvelopeInput, envelope: Envelope | None) -> str | None:
    if envelope is None:
        return "manual_sketch"
    if data.rules_reason == "manual_sketch":
        return "manual_sketch"
    if envelope.status == "in_progress":
        return "rules_in_progress"
    if envelope.status == "unavailable":
        return "rules_unavailable"
    if not any(part.excluded is None for part in envelope.parts):
        return "rules_unavailable"
    return None


def _reference_normal(data: EnvelopeInput, polygon: Polygon) -> tuple[float, bool]:
    """Azimut, zu dem die Straßenfassade weisen soll, und ob es eine Hauptstraße gibt."""
    seq = data.site.main_street_seq
    if seq is not None:
        for edge in data.site.edges:
            if edge.seq == seq:
                return float(edge.normal_azimuth_deg) % 360.0, True
    longest = max(segments(polygon), key=lambda s: math.dist(s[0], s[1]), default=None)
    if longest is None:
        return 0.0, False
    (ax, ay), (bx, by) = longest
    return (azimuth_deg(bx - ax, by - ay) + 90.0) % 360.0, False


def _effect_area(envelope: Envelope, effects: tuple[str, ...], origin: Point) -> BaseGeometry | None:
    areas = [item.geometry for item in envelope.constraints if item.effect in effects and item.area_m2 > 0]
    if not areas:
        return None
    return _local(union(areas), origin)


def _local(geometry: BaseGeometry, origin: Point) -> BaseGeometry:
    return affinity.translate(geometry, -origin[0], -origin[1])


def part_polygons(part: PartContext) -> list[Polygon]:
    return polygons(shapely.make_valid(part.polygon))
