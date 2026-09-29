"""Baurahmen ableiten (Spez. 5.3.1, 5.3.2, 5.9.2; Plan 3.5, Plan G3 3).

`derive_envelope` ist rein und deterministisch: gleiche Eingabe, gleiche Ausgabe, ohne Datenbank und Netz.
Ergebnis sind zwei Konturen der bebaubaren Fläche (weiteste und engste Auslegung der Regeln), die
Grenzwerte je Zonen-Teilfläche, der Abstand je Kante und die Flächen überlagernder Vorgaben.
"""

from dataclasses import dataclass, field, replace
from typing import Any

import shapely
from shapely.geometry.base import BaseGeometry

from app.envelope.domain import bands as band_rules
from app.envelope.domain import overlays as overlay_rules
from app.envelope.domain import tolerances as tol
from app.envelope.domain.bands import Band
from app.envelope.domain.heights import Heights, from_rule
from app.envelope.domain.inputs import Citation, EnvelopeInput, RuleInput, ZoneInput
from app.envelope.domain.setbacks import (
    RuleIndex,
    Setback,
    at_height,
    distances,
    incomplete_reasons,
    index_rules,
    rule_for,
    setbacks_for_edge,
)
from app.site.domain.local import polygons

READINGS = ("lenient", "strict")
"""`lenient` = weiteste Auslegung (größte Fläche), `strict` = engste (kleinste)."""
ZONE_WITHOUT_RULES = ("in_progress", "unavailable")
CONFIDENCE_REVIEW_BELOW = 0.65
"""Wie in G1 (`REVIEW_CONFIDENCE_BELOW`): darunter ist die Einordnung der Kante unsicher (G23)."""
UNCOVERED_WARNING_SHARE = 0.01
"""Wie in G2 (RW27): ab 1 % des Grundstücks ohne Zone des Planwerks ist der Baurahmen unvollständig."""
FLAT_SLOPE_MAX_PERCENT = 5.0
"""Über dieser Neigung ist der Höhenbezug nicht belastbar (Spez. 5.9.4)."""


@dataclass(frozen=True)
class Limit:
    """Ein Grenzwert oder eine Vorgabe der Zone mit Herkunft (L3)."""

    key: str
    kind: str
    building_kind: str
    status: str
    reason: str | None = None
    value: float | None = None
    """Abgeleiteter Wert in m² (Grundfläche, Freifläche), sonst offen."""
    params: dict[str, Any] = field(default_factory=dict)
    citation: Citation | None = None
    derived_from: str | None = None


@dataclass(frozen=True)
class EdgeResult:
    seq: int
    ring: int
    kind: str
    classification_source: str
    confidence: float
    length_m: float
    normal_azimuth_deg: float
    street_name: str | None
    geometry: BaseGeometry
    setbacks: list[Setback]
    lenient_m: float | None
    strict_m: float | None
    markers: list[str]


@dataclass(frozen=True)
class Contour:
    geometry: BaseGeometry
    area_m2: float
    complete: bool
    incomplete_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PartResult:
    zone_code: str
    zone_status: str
    reason: str | None
    area_m2: float
    share: float
    geometry: BaseGeometry
    excluded: str | None
    """Grund, warum die Teilfläche nicht in den Konturen steckt (`rules_unavailable`, `footprint_zero`)."""
    limits: list[Limit]
    hints: list[RuleInput]
    heights: Heights


@dataclass(frozen=True)
class ConstraintResult:
    effect: str
    category: str
    type_code: str | None
    label: str
    endpoint: str
    geometry: BaseGeometry
    area_m2: float


@dataclass(frozen=True)
class Envelope:
    status: str
    """`ok`, `partial`, `in_progress` oder `unavailable`."""
    reason: str | None
    contours: dict[str, Contour]
    parts: list[PartResult]
    edges: list[EdgeResult]
    bands: list[Band]
    constraints: list[ConstraintResult]
    warnings: list[str]
    assumptions: list[str]


def derive_envelope(data: EnvelopeInput) -> Envelope:
    """Baurahmen für das Hauptgebäude (Plan G3 1)."""
    site = data.site
    constraints = _constraints(data)
    parts: list[PartResult] = []
    zone_rules: dict[str, RuleIndex] = {}
    zone_heights: dict[str, Heights] = {}
    zone_bands: dict[str, list[Band]] = {}
    assumptions: list[str] = []

    for zone in data.zones:
        rules = index_rules(zone.rules)
        heights = from_rule(rule_for(rules, "max_height"))
        zone_rules[zone.code] = rules
        zone_heights[zone.code] = heights
        zone_bands[zone.code] = band_rules.bands_for_zone(site.edges, rules, zone.code, zone.polygon)
        assumptions.extend(heights.assumptions)
        parts.append(_part(zone, rules, heights))

    edges = _edges(data, zone_rules, zone_heights)
    contours = {
        reading: _contour(reading, data, parts, edges, zone_bands, constraints) for reading in READINGS
    }
    status, reason = _status(data, parts, contours)
    warnings = _warnings(data, parts, edges, contours, zone_bands, constraints)
    return Envelope(
        status=status,
        reason=reason,
        contours=contours,
        parts=parts,
        edges=edges,
        bands=[band for bands in zone_bands.values() for band in bands],
        constraints=constraints,
        warnings=sorted(set(warnings)),
        assumptions=sorted(set(assumptions)),
    )


# ---------------------------------------------------------------------------
# Teilflächen und Grenzwerte
# ---------------------------------------------------------------------------


def _part(zone: ZoneInput, rules: RuleIndex, heights: Heights) -> PartResult:
    limits = [_limit(rule) for rule in zone.rules]
    limits.extend(_derived_limits(zone, rules))
    footprint = rule_for(rules, "max_footprint_ratio")
    excluded: str | None = None
    if zone.status in ZONE_WITHOUT_RULES:
        # Ohne ausgewertete Regeln keine bebaubare Fläche: eine Zone N sähe sonst bebaubar aus (E-G3-1)
        excluded = f"rules_{zone.status}"
    elif footprint is not None and footprint.status == "effective" and not footprint.params.get("ratio"):
        excluded = "footprint_zero"
    return PartResult(
        zone_code=zone.code,
        zone_status=zone.status,
        reason=zone.reason,
        area_m2=round(zone.area_m2, 2),
        share=zone.share,
        geometry=zone.polygon,
        excluded=excluded,
        limits=limits,
        hints=list(zone.hints),
        heights=heights,
    )


def _limit(rule: RuleInput) -> Limit:
    return Limit(
        key=rule.kind,
        kind=rule.kind,
        building_kind=rule.building_kind,
        status=rule.status,
        reason=rule.reason,
        params=dict(rule.params),
        citation=rule.citation,
    )


def _derived_limits(zone: ZoneInput, rules: RuleIndex) -> list[Limit]:
    """Flächen aus Anteilen, je Zonen-Teilfläche statt je Grundstück (Spez. 5.3.2; Zone Uh bezieht die
    Grundfläche ausdrücklich auf den Teil des Grundstücks in der Zone)."""
    derived: list[Limit] = []
    for kind, key, param in (
        ("max_footprint_ratio", "footprint_max_m2", "ratio"),
        ("unsealed_min", "unsealed_min_m2", "ratio"),
        ("unsealed_min", "full_soil_min_m2", "full_soil_ratio"),
    ):
        rule = rule_for(rules, kind)
        if rule is None or rule.status != "effective":
            continue
        ratio = rule.params.get(param)
        if not isinstance(ratio, int | float) or isinstance(ratio, bool):
            continue
        derived.append(
            Limit(
                key=key,
                kind=kind,
                building_kind=rule.building_kind,
                status="effective",
                value=round(float(ratio) * zone.area_m2, 2),
                citation=rule.citation,
                derived_from=kind,
            )
        )
    return derived


# ---------------------------------------------------------------------------
# Kanten
# ---------------------------------------------------------------------------


def _edges(
    data: EnvelopeInput, zone_rules: dict[str, RuleIndex], zone_heights: dict[str, Heights]
) -> list[EdgeResult]:
    active = [z for z in data.zones if z.status not in ZONE_WITHOUT_RULES]
    results: list[EdgeResult] = []
    for edge in data.site.edges:
        setbacks: list[Setback] = []
        for zone in active:
            setbacks.extend(
                setbacks_for_edge(edge, zone_rules[zone.code], zone_heights[zone.code], zone.code)
            )
        lenient, strict, markers = distances(setbacks) if setbacks else (None, None, [])
        if edge.classification_source == "customer":
            markers = [*markers, "customer_correction"]
        if edge.classification_source == "auto" and edge.confidence < CONFIDENCE_REVIEW_BELOW:
            markers = [*markers, "classification_uncertain"]
        if edge.kind == "other":
            markers = [*markers, "kind_unclear"]
        results.append(
            EdgeResult(
                seq=edge.seq,
                ring=edge.ring,
                kind=edge.kind,
                classification_source=edge.classification_source,
                confidence=edge.confidence,
                length_m=edge.length_m,
                normal_azimuth_deg=edge.normal_azimuth_deg,
                street_name=edge.street_name,
                geometry=edge.geometry,
                setbacks=setbacks,
                lenient_m=lenient,
                strict_m=strict,
                markers=sorted(set(markers)),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Konturen
# ---------------------------------------------------------------------------


def contour_at_height(
    data: EnvelopeInput,
    envelope: Envelope,
    height_m: float,
    reading: str,
    heights: dict[str, Heights] | None = None,
) -> Contour:
    """Kontur für Baukörperteile, die bis `height_m` reichen (Gabarit der Analyse, PLAN_AN3_GABARIT.md 3.2).

    Dieselbe Ableitung wie die Konturen des Baurahmens, aber jeder Abstand mit der Höhe der Stufe
    (`setbacks.at_height`). Teilflächen, deren Höchsthöhe darunter liegt oder nicht ermittelt ist, tragen
    nichts bei. `heights` ersetzt die Höhen einer Zone (Geschossangabe mit anderer Geschosshöhe umgerechnet).
    """
    override = heights or {}
    zone_heights = {part.zone_code: override.get(part.zone_code, part.heights) for part in envelope.parts}
    parts = [
        part
        if part.excluded is not None or reaches(zone_heights[part.zone_code], height_m)
        else replace(part, excluded="above_max_height")
        for part in envelope.parts
    ]
    edges = [
        replace(edge, setbacks=[at_height(s, zone_heights[s.zone_code], height_m) for s in edge.setbacks])
        for edge in envelope.edges
    ]
    zone_bands: dict[str, list[Band]] = {}
    for band in envelope.bands:
        zone_bands.setdefault(band.zone_code, []).append(band)
    return _contour(reading, data, parts, edges, zone_bands, envelope.constraints)


def reaches(heights: Heights, height_m: float) -> bool:
    """Darf in der Zone bis `height_m` gebaut werden? Ohne ermittelte Höchsthöhe nicht bestimmt: nein."""
    top = heights.highest_m
    return top is not None and height_m <= top + tol.DISTANCE_EPSILON_M


def _contour(
    reading: str,
    data: EnvelopeInput,
    parts: list[PartResult],
    edges: list[EdgeResult],
    zone_bands: dict[str, list[Band]],
    constraints: list[ConstraintResult],
) -> Contour:
    pieces: list[BaseGeometry] = []
    subtract = _subtracted(constraints, reading)
    for part in parts:
        if part.excluded is not None:
            continue
        area: BaseGeometry = part.geometry
        for edge in edges:
            distance = _distance(edge, part.zone_code, reading)
            if distance is None or distance <= 0:
                continue
            area = area.difference(edge.geometry.buffer(distance, cap_style="round"))
            if area.is_empty:
                break
        band = band_rules.restriction(zone_bands.get(part.zone_code, []), reading)
        if band is not None and not area.is_empty:
            area = area.intersection(band)
        if subtract is not None and not area.is_empty:
            area = area.difference(subtract)
        if not area.is_empty:
            pieces.append(area)
    reasons = _strict_reasons(data, parts, edges) if reading == "strict" else []
    geometry = _clean(shapely.union_all(pieces) if pieces else shapely.Polygon())
    return Contour(
        geometry=geometry,
        area_m2=round(float(geometry.area), 2),
        complete=not reasons,
        incomplete_reasons=sorted(set(reasons)),
    )


def _distance(edge: EdgeResult, zone_code: str, reading: str) -> float | None:
    setbacks = [s for s in edge.setbacks if s.zone_code == zone_code]
    if not setbacks:
        return None
    lenient, strict, _ = distances(setbacks)
    return lenient if reading == "lenient" else strict


def _strict_reasons(data: EnvelopeInput, parts: list[PartResult], edges: list[EdgeResult]) -> list[str]:
    """Die engste Kontur ist nur belastbar, wenn jeder Abstand ermittelt ist."""
    active = {p.zone_code for p in parts if p.excluded is None}
    by_seq = {edge.seq: edge for edge in data.site.edges}
    reasons: list[str] = []
    for edge in edges:
        relevant = [s for s in edge.setbacks if s.zone_code in active]
        if relevant:
            reasons.extend(incomplete_reasons(by_seq[edge.seq], relevant))
        if "alignment" in edge.markers:
            reasons.append(f"alignment:{edge.seq}")
    return reasons


def _subtracted(constraints: list[ConstraintResult], reading: str) -> BaseGeometry | None:
    """Bauverbot wirkt in beiden Auslegungen, einschränkende Vorgaben nur in der engsten (Plan G3 3.4)."""
    effects = ("no_build",) if reading == "lenient" else ("no_build", "restricts")
    geometries = [c.geometry for c in constraints if c.effect in effects and not c.geometry.is_empty]
    return shapely.union_all(geometries) if geometries else None


def _clean(geometry: BaseGeometry) -> BaseGeometry:
    """Splitter und zu schmale Streifen entfernen (Spez. 5.3.2)."""
    kept = [
        polygon
        for polygon in polygons(shapely.make_valid(geometry))
        if polygon.area >= tol.MIN_PART_AREA_M2 and _wide_enough(polygon)
    ]
    return shapely.union_all(kept) if kept else shapely.Polygon()


def _wide_enough(polygon: BaseGeometry) -> bool:
    return not polygon.buffer(-tol.MIN_PART_WIDTH_M / 2).is_empty


# ---------------------------------------------------------------------------
# Vorgaben, Status, Hinweise
# ---------------------------------------------------------------------------


def _constraints(data: EnvelopeInput) -> list[ConstraintResult]:
    results: list[ConstraintResult] = []
    for item in data.constraints:
        areas = polygons(item.geometry)
        geometry = shapely.union_all(areas) if areas else item.geometry
        effect = overlay_rules.effect(item.category, item.type_code, bool(areas))
        results.append(
            ConstraintResult(
                effect=effect,
                category=item.category,
                type_code=item.type_code,
                label=item.label,
                endpoint=item.endpoint,
                geometry=geometry,
                area_m2=round(float(geometry.area), 2) if areas else 0.0,
            )
        )
    return results


def _status(
    data: EnvelopeInput, parts: list[PartResult], contours: dict[str, Contour]
) -> tuple[str, str | None]:
    if not parts:
        return "unavailable", data.rules_reason or "no_zone"
    active = [p for p in parts if p.excluded is None]
    if not active:
        if any(p.zone_status == "in_progress" for p in parts):
            return "in_progress", None
        return "unavailable", parts[0].reason or parts[0].excluded
    if len(active) < len(parts) or data.uncovered_share >= UNCOVERED_WARNING_SHARE:
        return "partial", None
    if contours["lenient"].geometry.is_empty:
        return "partial", "no_buildable_area"
    return "ok", None


def _warnings(
    data: EnvelopeInput,
    parts: list[PartResult],
    edges: list[EdgeResult],
    contours: dict[str, Contour],
    zone_bands: dict[str, list[Band]],
    constraints: list[ConstraintResult],
) -> list[str]:
    warnings = [*data.site.warnings, *data.warnings]
    if data.site.customer_edges_unconfirmed:
        warnings.append("customer_edges_unconfirmed")
    terrain = data.site.terrain
    if terrain.status != "ok":
        warnings.append("terrain_unavailable")
    elif terrain.slope_percent is not None and terrain.slope_percent > FLAT_SLOPE_MAX_PERCENT:
        warnings.append("terrain_steep")
    if any(p.excluded is not None for p in parts):
        warnings.append("zones_without_rules")
    if not contours["strict"].complete:
        warnings.append("setbacks_incomplete")
    if contours["lenient"].geometry.is_empty:
        warnings.append("no_buildable_area")
    if any(band_rules.unclear(bands) for bands in zone_bands.values()):
        warnings.append("band_unclear")
    if any(c.effect == "no_build" for c in constraints):
        warnings.append("no_build_area")
    if any(c.effect == "restricts" for c in constraints):
        warnings.append("restricted_area")
    if any("kind_unclear" in edge.markers for edge in edges):
        warnings.append("edge_kind_unclear")
    return warnings
