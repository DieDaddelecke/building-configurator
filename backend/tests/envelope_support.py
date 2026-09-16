"""Hilfen für die Tests des Moduls G3: Grundstücke, Zonen und Regeln als Eingabe der reinen Fachlogik."""

from typing import Any

from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

from app.envelope.domain.inputs import (
    Citation,
    ConstraintInput,
    EdgeInput,
    EnvelopeInput,
    RuleInput,
    SiteInput,
    TerrainInput,
    ZoneInput,
)

RECTANGLE = (20.0, 31.0)
"""Testgrundstück der Parität (Spez. 11.2): 20 × 31 m, Straße im Norden, Nachbarn Ost und West."""


def rectangle(width: float = RECTANGLE[0], depth: float = RECTANGLE[1]) -> Polygon:
    return Polygon([(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)])


def edges_of_rectangle(width: float = RECTANGLE[0], depth: float = RECTANGLE[1]) -> list[EdgeInput]:
    """Kanten des Testgrundstücks: Süden hinten, Osten und Westen seitlich, Norden Straße."""
    corners = [(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth), (0.0, 0.0)]
    kinds = ["rear", "side", "street", "side"]
    return [
        edge(seq=index + 1, kind=kinds[index], coords=[corners[index], corners[index + 1]])
        for index in range(4)
    ]


def edge(
    *,
    seq: int,
    kind: str,
    coords: list[tuple[float, float]],
    ring: int = 0,
    source: str = "auto",
    confidence: float = 0.9,
    street_name: str | None = None,
) -> EdgeInput:
    line = LineString(coords)
    return EdgeInput(
        seq=seq,
        ring=ring,
        kind=kind,
        classification_source=source,
        confidence=confidence,
        length_m=round(line.length, 3),
        normal_azimuth_deg=0.0,
        street_name=street_name,
        geometry=line,
    )


def rule(
    kind: str,
    params: dict[str, Any] | None = None,
    *,
    status: str = "effective",
    reason: str | None = None,
    building_kind: str = "main",
    page: int = 12,
    quote: str = "Zitat",
) -> RuleInput:
    return RuleInput(
        kind=kind,
        building_kind=building_kind,
        status=status,
        reason=reason,
        params=params or {},
        citation=Citation(page=page, quote=quote, quote_verified=True, confidence=0.9),
    )


def ub_rules() -> list[RuleInput]:
    """Regelwerk der Zone UB aus dem Mockup (Spez. Anhang C) mit festen Abständen."""
    return [
        rule("setback_street", {"min_m": 5.0, "mode": "min", "measured_from": "facade"}),
        rule("setback_side", {"min_m": 3.0, "allow_on_boundary": False, "measured_from": "facade"}),
        rule("setback_rear", {"min_m": 5.0, "allow_on_boundary": False, "measured_from": "facade"}),
        rule("max_footprint_ratio", {"ratio": 0.4}),
        rule("max_height", {"ridge_m": 9.0, "eave_m": 6.0, "storeys": "R+1+C"}),
        rule("roof", {"allowed_forms": ["gable", "hip"], "pitch_min_deg": 35.0, "pitch_max_deg": 45.0}),
        rule("facade", {"materials_allowed": ["render", "wood", "brick"]}),
        rule("unsealed_min", {"ratio": 0.3}),
    ]


def zone(
    code: str = "UB",
    *,
    polygon: BaseGeometry | None = None,
    rules: list[RuleInput] | None = None,
    status: str = "simulated",
    reason: str | None = None,
    area_m2: float | None = None,
    share: float = 1.0,
    hints: list[RuleInput] | None = None,
) -> ZoneInput:
    geometry = polygon if polygon is not None else rectangle()
    return ZoneInput(
        code=code,
        label=None,
        status=status,
        reason=reason,
        area_m2=area_m2 if area_m2 is not None else float(geometry.area),
        share=share,
        polygon=geometry,
        rules=rules if rules is not None else ub_rules(),
        hints=hints or [],
    )


def constraint(
    polygon: BaseGeometry,
    *,
    type_code: str = "05",
    category: str = "prescription",
    label: str = "Emplacement réservé",
) -> ConstraintInput:
    return ConstraintInput(
        category=category, type_code=type_code, label=label, endpoint="prescription-surf", geometry=polygon
    )


def site(
    *,
    polygon: Polygon | None = None,
    edges: list[EdgeInput] | None = None,
    terrain_status: str = "ok",
    slope_percent: float | None = 1.0,
    warnings: list[str] | None = None,
    customer_edges_unconfirmed: bool = False,
) -> SiteInput:
    outline = polygon if polygon is not None else rectangle()
    return SiteInput(
        polygon=outline,
        area_m2=float(outline.area),
        local_origin=(0.0, 0.0),
        edges=edges if edges is not None else edges_of_rectangle(),
        main_street_seq=3,
        warnings=warnings or [],
        customer_edges_unconfirmed=customer_edges_unconfirmed,
        terrain=TerrainInput(status=terrain_status, slope_percent=slope_percent, reference_altitude_ngf=30.0),
        parcels=["44209000AD0065"],
        revision=1,
        engine_version="g1-1.1.0",
    )


def envelope_input(
    *,
    site_input: SiteInput | None = None,
    zones: list[ZoneInput] | None = None,
    constraints: list[ConstraintInput] | None = None,
    rules_status: str = "ok",
    uncovered_share: float = 0.0,
    warnings: list[str] | None = None,
) -> EnvelopeInput:
    return EnvelopeInput(
        site=site_input or site(),
        zones=zones if zones is not None else [zone()],
        constraints=constraints or [],
        rules_status=rules_status,
        uncovered_share=uncovered_share,
        warnings=warnings or [],
        notices=["notice.envelope_simulation"],
        rules_engine_version="g2-1.2.0",
    )
