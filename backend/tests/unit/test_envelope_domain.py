"""Fachlogik des Baurahmens (Modul G3): Parität mit dem Mockup, Rechenbeispiele der Spezifikation,
Sonderfälle und Eigenschaften.

Fälle A: Konturen und Abstände · B: fehlende und unsichere Angaben · C: Zonen und Vorgaben ·
D: Höhen · E: Eigenschaften (Spez. 11.1).
"""

import math
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from shapely.geometry import Polygon

from app.envelope.domain.derive import derive_envelope
from app.envelope.domain.heights import Heights, from_storeys
from app.envelope.domain.inputs import RuleInput
from app.envelope.domain.overlays import effect
from tests.envelope_support import (
    constraint,
    edge,
    edges_of_rectangle,
    envelope_input,
    rectangle,
    rule,
    site,
    ub_rules,
    zone,
)


def limits(envelope: Any, key: str, zone_code: str = "UB") -> Any:
    part = next(p for p in envelope.parts if p.zone_code == zone_code)
    return next((limit for limit in part.limits if limit.key == key), None)


def setback(envelope: Any, seq: int) -> Any:
    return next(e for e in envelope.edges if e.seq == seq)


# ---------------------------------------------------------------------------
# A – Konturen und Abstände
# ---------------------------------------------------------------------------


def test_parity_rectangle_is_fourteen_by_twentyone() -> None:
    """Spez. 11.2: 20 × 31 m, Straße 5 m, seitlich je 3 m, hinten 5 m → 14,0 × 21,0 m = 294,0 m².

    Ohne höhenabhängige Regeln sind beide Auslegungen gleich (Spez. 5.3.1)."""
    envelope = derive_envelope(envelope_input())
    lenient, strict = envelope.contours["lenient"], envelope.contours["strict"]
    assert lenient.area_m2 == pytest.approx(294.0, abs=0.05)
    assert strict.area_m2 == pytest.approx(294.0, abs=0.05)
    assert strict.complete and envelope.status == "ok"
    min_x, min_y, max_x, max_y = strict.geometry.bounds
    assert (max_x - min_x, max_y - min_y) == pytest.approx((14.0, 21.0), abs=0.01)


def test_height_dependent_setback_matches_example_d4() -> None:
    """Spez. Anhang D4: seitlich `max(3,0; H/2)`, Traufe 7,0 m → 3,50 m in der engsten Auslegung."""
    rules = [
        *[r for r in ub_rules() if r.kind not in ("setback_side", "max_height")],
        rule("setback_side", {"min_m": 3.0, "height_factor": 0.5, "height_basis": "eave"}),
        rule("max_height", {"eave_m": 7.0, "ridge_m": 10.0}),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    side = setback(envelope, 2)
    assert side.strict_m == pytest.approx(3.5)
    assert side.lenient_m == pytest.approx(3.0)
    # 20 − 2 × 3,5 = 13,0 breit gegenüber 14,0 in der weitesten Auslegung
    assert envelope.contours["strict"].area_m2 < envelope.contours["lenient"].area_m2


def test_building_on_boundary_widens_the_lenient_contour() -> None:
    """Zone Uh: „soit en limite séparative, soit en retrait d'au moins 3 mètres“. Die weiteste Auslegung
    muss die Lagen auf der Grenze enthalten, sonst verliert H2 sie (Spez. 5.3.6)."""
    rules = [
        *[r for r in ub_rules() if r.kind != "setback_side"],
        rule("setback_side", {"min_m": 3.0, "allow_on_boundary": True}),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    assert setback(envelope, 2).lenient_m == 0.0
    assert setback(envelope, 2).strict_m == pytest.approx(3.0)
    assert "on_boundary_allowed" in setback(envelope, 2).markers
    assert envelope.contours["lenient"].geometry.bounds[0] == pytest.approx(0.0, abs=0.01)


def test_band_limits_the_area_only_as_far_as_the_text_says() -> None:
    """Bauband 5–20 m (Zone Uh). `building`: der ganze Baukörper liegt im Band – beide Konturen enden bei
    20 m. Ohne Angabe gilt das nur für die engste Auslegung (Plan G3 3.3)."""

    def area(band: str | None) -> Any:
        params: dict[str, Any] = {"mode": "range", "min_m": 5.0, "max_m": 20.0}
        if band is not None:
            params["band"] = band
        rules = [*[r for r in ub_rules() if r.kind != "setback_street"], rule("setback_street", params)]
        return derive_envelope(envelope_input(zones=[zone(rules=rules)]))

    building = area("building")
    # Straße liegt im Norden (y = 31): Band von y = 11 bis y = 26
    assert building.contours["lenient"].geometry.bounds[1] == pytest.approx(11.0, abs=0.01)
    assert building.contours["strict"].geometry.bounds[1] == pytest.approx(11.0, abs=0.01)
    facade = area("facade")
    assert facade.contours["lenient"].geometry.bounds[1] == pytest.approx(5.0, abs=0.01)
    unclear = area(None)
    assert unclear.contours["lenient"].geometry.bounds[1] == pytest.approx(5.0, abs=0.01)
    assert unclear.contours["strict"].geometry.bounds[1] == pytest.approx(11.0, abs=0.01)
    assert "band_unclear" in unclear.warnings


def test_alignment_cannot_be_derived() -> None:
    """„à l'alignement“ hängt von der Nachbarbebauung ab: kein Abzug, Kante markiert, engste Kontur
    unvollständig."""
    rules = [
        *[r for r in ub_rules() if r.kind != "setback_street"],
        rule("setback_street", {"mode": "alignment"}),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    assert "alignment" in setback(envelope, 3).markers
    assert not envelope.contours["strict"].complete


# ---------------------------------------------------------------------------
# B – Fehlende und unsichere Angaben
# ---------------------------------------------------------------------------


def test_unknown_setback_is_not_deducted_but_marked() -> None:
    """Plan 3.5: Ohne ermittelten Abstand wird die Fläche ohne ihn gerechnet und die Kante markiert."""
    rules = [
        *[r for r in ub_rules() if r.kind != "setback_rear"],
        rule("setback_rear", status="unknown", reason="runs_disagree"),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    rear = setback(envelope, 1)
    assert rear.lenient_m is None and rear.strict_m is None
    assert "setback_unknown" in rear.markers
    assert not envelope.contours["strict"].complete
    assert "setbacks_incomplete" in envelope.warnings
    # 20 − 6 = 14 breit, 31 − 5 = 26 tief
    assert envelope.contours["lenient"].area_m2 == pytest.approx(14.0 * 26.0, abs=0.05)


def test_missing_rule_behaves_like_unknown() -> None:
    rules = [r for r in ub_rules() if r.kind != "setback_side"]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    assert setback(envelope, 2).setbacks[0].status == "missing"
    assert not envelope.contours["strict"].complete


def test_not_regulated_means_no_distance() -> None:
    """`not_regulated` ist belegt (RW24) und heißt: kein Abstand vorgeschrieben."""
    rules = [
        *[r for r in ub_rules() if r.kind != "setback_rear"],
        rule("setback_rear", status="not_regulated"),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    assert setback(envelope, 1).strict_m == 0.0
    assert envelope.contours["strict"].complete


def test_unclassified_edge_uses_both_separative_rules() -> None:
    """Kante `other`: weiteste Auslegung nimmt den kleineren, engste den größeren Abstand."""
    edges = edges_of_rectangle()
    edges[0] = edge(seq=1, kind="other", coords=[(0.0, 0.0), (20.0, 0.0)])
    envelope = derive_envelope(envelope_input(site_input=site(edges=edges)))
    other = setback(envelope, 1)
    assert other.lenient_m == pytest.approx(3.0)
    assert other.strict_m == pytest.approx(5.0)
    assert "kind_unclear" in other.markers and "edge_kind_unclear" in envelope.warnings


def test_uncertain_and_customer_edges_are_marked() -> None:
    edges = edges_of_rectangle()
    edges[2] = edge(seq=3, kind="street", coords=[(20.0, 31.0), (0.0, 31.0)], confidence=0.55)
    edges[1] = edge(seq=2, kind="side", coords=[(20.0, 0.0), (20.0, 31.0)], source="customer")
    envelope = derive_envelope(envelope_input(site_input=site(edges=edges, customer_edges_unconfirmed=True)))
    assert "classification_uncertain" in setback(envelope, 3).markers
    assert "customer_correction" in setback(envelope, 2).markers
    assert "customer_edges_unconfirmed" in envelope.warnings


def test_steep_terrain_and_missing_terrain_are_warnings() -> None:
    steep = derive_envelope(envelope_input(site_input=site(slope_percent=8.0)))
    assert "terrain_steep" in steep.warnings
    missing = derive_envelope(envelope_input(site_input=site(terrain_status="unavailable")))
    assert "terrain_unavailable" in missing.warnings


# ---------------------------------------------------------------------------
# C – Zonen, Grenzwerte und Vorgaben
# ---------------------------------------------------------------------------


def test_zone_parts_carry_their_own_limits_example_d10() -> None:
    """Spez. Anhang D10: 600 m², davon 500 m² UB (40 %) und 100 m² N (0 %) → 200 m² und 0 m²."""
    outline = Polygon([(0, 0), (20, 0), (20, 30), (0, 30)])
    ub_part = Polygon([(0, 0), (20, 0), (20, 25), (0, 25)])
    n_part = Polygon([(0, 25), (20, 25), (20, 30), (0, 30)])
    n_rules = [
        *[r for r in ub_rules() if r.kind != "max_footprint_ratio"],
        rule("max_footprint_ratio", {"ratio": 0.0}),
    ]
    data = envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(20.0, 30.0)),
        zones=[
            zone("UB", polygon=ub_part, share=0.833),
            zone("N", polygon=n_part, rules=n_rules, share=0.167),
        ],
    )
    envelope = derive_envelope(data)
    assert limits(envelope, "footprint_max_m2").value == pytest.approx(200.0)
    assert limits(envelope, "footprint_max_m2", "N").value == pytest.approx(0.0)
    n_part_result = next(p for p in envelope.parts if p.zone_code == "N")
    assert n_part_result.excluded == "footprint_zero"
    assert envelope.status == "partial"
    assert envelope.contours["lenient"].geometry.bounds[3] <= 25.0 + 0.01


def test_zone_without_rules_is_not_buildable() -> None:
    """Entscheidung E-G3-1: Ohne ausgewertete Regeln keine Fläche, sonst sähe eine Zone N bebaubar aus."""
    outline = Polygon([(0, 0), (20, 0), (20, 30), (0, 30)])
    data = envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(20.0, 30.0)),
        zones=[
            zone("UB", polygon=Polygon([(0, 0), (20, 0), (20, 25), (0, 25)]), share=0.833),
            zone(
                "N",
                polygon=Polygon([(0, 25), (20, 25), (20, 30), (0, 30)]),
                rules=[],
                status="unavailable",
                reason="chapter_not_found",
                share=0.167,
            ),
        ],
    )
    envelope = derive_envelope(data)
    assert next(p for p in envelope.parts if p.zone_code == "N").excluded == "rules_unavailable"
    assert "zones_without_rules" in envelope.warnings
    assert envelope.status == "partial"
    # Kanten der Zone N liefern keine Abstände, aber ihre Fläche fehlt in beiden Konturen
    assert envelope.contours["lenient"].geometry.bounds[3] <= 25.01


def test_rules_in_progress_gives_status_in_progress() -> None:
    data = envelope_input(zones=[zone(rules=[], status="in_progress", reason=None)])
    envelope = derive_envelope(data)
    assert envelope.status == "in_progress"
    assert envelope.contours["lenient"].geometry.is_empty


def test_without_zones_the_envelope_is_unavailable() -> None:
    envelope = derive_envelope(envelope_input(zones=[], rules_status="unavailable"))
    assert envelope.status == "unavailable"


def test_no_build_and_restricting_constraints() -> None:
    """Emplacement réservé (05) fehlt in beiden Konturen, ein Risikobereich (02) nur in der engsten."""
    reserved = Polygon([(0, 0), (20, 0), (20, 8), (0, 8)])
    risk = Polygon([(0, 8), (20, 8), (20, 14), (0, 14)])
    envelope = derive_envelope(
        envelope_input(
            constraints=[
                constraint(reserved, type_code="05"),
                constraint(risk, type_code="02", label="risque d'inondation"),
            ]
        )
    )
    assert envelope.contours["lenient"].geometry.bounds[1] == pytest.approx(8.0, abs=0.01)
    assert envelope.contours["strict"].geometry.bounds[1] == pytest.approx(14.0, abs=0.01)
    assert {"no_build_area", "restricted_area"} <= set(envelope.warnings)


def test_unknown_constraint_type_is_only_a_hint() -> None:
    envelope = derive_envelope(
        envelope_input(constraints=[constraint(rectangle(), type_code="17", label="mixité sociale")])
    )
    assert envelope.constraints[0].effect == "info"
    assert envelope.contours["strict"].area_m2 == pytest.approx(294.0, abs=0.05)


@pytest.mark.parametrize(
    ("category", "type_code", "is_area", "expected"),
    [
        ("prescription", "01", True, "no_build"),
        ("prescription", "05", True, "no_build"),
        ("prescription", "02", True, "restricts"),
        ("prescription", "05", False, "info"),
        ("information", "05", True, "info"),
        ("servitude", None, True, "info"),
        ("prescription", "99", True, "info"),
    ],
)
def test_overlay_effects(category: str, type_code: str | None, is_area: bool, expected: str) -> None:
    assert effect(category, type_code, is_area) == expected


def test_derived_limits_use_the_part_not_the_site() -> None:
    """Uh: „emprise au sol … à l'intérieur de la zone“ (Spez. 5.3.2)."""
    part = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
    envelope = derive_envelope(envelope_input(zones=[zone("UB", polygon=part, share=0.645)]))
    assert limits(envelope, "footprint_max_m2").value == pytest.approx(160.0)
    assert limits(envelope, "unsealed_min_m2").value == pytest.approx(120.0)


def test_small_or_narrow_remainders_are_dropped() -> None:
    """Spez. 5.3.2: unter 4 m² oder schmaler als 2 m."""
    narrow = rectangle(7.0, 31.0)  # 7 − 2 × 3 = 1 m breit
    envelope = derive_envelope(
        envelope_input(
            site_input=site(polygon=narrow, edges=edges_of_rectangle(7.0, 31.0)),
            zones=[zone(polygon=narrow)],
        )
    )
    assert envelope.contours["lenient"].geometry.is_empty
    assert "no_buildable_area" in envelope.warnings


def test_hole_in_the_site_reduces_the_contour() -> None:
    outline = Polygon([(0, 0), (20, 0), (20, 31), (0, 31)], holes=[[(9, 14), (13, 14), (13, 18), (9, 18)]])
    edges = [
        *edges_of_rectangle(),
        edge(seq=5, kind="other", coords=[(9, 14), (13, 14), (13, 18), (9, 18), (9, 14)], ring=1),
    ]
    envelope = derive_envelope(
        envelope_input(site_input=site(polygon=outline, edges=edges), zones=[zone(polygon=outline)])
    )
    assert envelope.contours["lenient"].area_m2 < 294.0
    assert "kind_unclear" in setback(envelope, 5).markers


# ---------------------------------------------------------------------------
# D – Höhen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("storeys", "eave", "ridge"),
    [("R", 3.0, 3.0), ("R+1", 6.0, 6.0), ("R+1+C", 6.0, 11.0), ("R+2+A", 9.0, 12.0)],
)
def test_storeys_to_metres(storeys: str, eave: float, ridge: float) -> None:
    assert from_storeys(storeys) == (eave, ridge)


def test_storeys_only_is_an_assumption_and_no_displayed_limit() -> None:
    """Plan 3.5: Standard-Geschosshöhen wirken nur auf die engste Kontur; angezeigt bleibt `R+1+C`."""
    rules = [
        *[r for r in ub_rules() if r.kind not in ("max_height", "setback_side")],
        rule("max_height", {"storeys": "R+1+C"}),
        rule("setback_side", {"min_m": 3.0, "height_factor": 0.5, "height_basis": "eave"}),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    part = envelope.parts[0]
    assert part.heights.storeys == "R+1+C"
    assert part.heights.assumptions == ["storey_height_3.00"]
    assert setback(envelope, 2).strict_m == pytest.approx(3.0)  # 6,00 m Traufe aus R+1, davon die Hälfte
    assert limits(envelope, "max_height").params == {"storeys": "R+1+C"}


def test_height_basis_falls_back_to_the_highest_known_value() -> None:
    """Fehlt die Traufe, gilt der First: First ≥ Traufe, die Kontur wird dadurch nie zu groß."""
    heights = Heights(eave_m=None, ridge_m=9.0)
    assert heights.for_basis("eave") == 9.0
    assert Heights().for_basis("ridge") is None


def test_height_dependent_setback_without_height_is_incomplete() -> None:
    rules = [
        *[r for r in ub_rules() if r.kind not in ("max_height", "setback_side")],
        rule("max_height", status="unknown", reason="missing"),
        rule("setback_side", {"min_m": 3.0, "height_factor": 0.5, "height_basis": "eave"}),
    ]
    envelope = derive_envelope(envelope_input(zones=[zone(rules=rules)]))
    assert "height_unknown" in setback(envelope, 2).markers
    assert not envelope.contours["strict"].complete
    assert setback(envelope, 2).strict_m == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# E – Eigenschaften (Spez. 11.1)
# ---------------------------------------------------------------------------


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    width=st.floats(min_value=12.0, max_value=60.0),
    depth=st.floats(min_value=12.0, max_value=60.0),
    street=st.floats(min_value=0.0, max_value=8.0),
    side=st.floats(min_value=0.0, max_value=6.0),
    factor=st.sampled_from([None, 0.5, 1.0]),
)
def test_contours_are_nested_and_keep_their_distance(
    width: float, depth: float, street: float, side: float, factor: float | None
) -> None:
    side_params: dict[str, Any] = {"min_m": side}
    if factor is not None:
        side_params |= {"height_factor": factor, "height_basis": "eave"}
    rules: list[RuleInput] = [
        rule("setback_street", {"min_m": street, "mode": "min"}),
        rule("setback_side", side_params),
        rule("setback_rear", {"min_m": side}),
        rule("max_height", {"eave_m": 6.0, "ridge_m": 9.0}),
        rule("max_footprint_ratio", {"ratio": 0.4}),
    ]
    outline = rectangle(width, depth)
    data = envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(width, depth)),
        zones=[zone(polygon=outline, rules=rules)],
    )
    envelope = derive_envelope(data)
    lenient, strict = envelope.contours["lenient"].geometry, envelope.contours["strict"].geometry
    assert lenient.covers(strict.buffer(-1e-6)) or strict.is_empty
    assert lenient.is_empty or outline.buffer(1e-6).covers(lenient)
    for reading, geometry in (("lenient", lenient), ("strict", strict)):
        if geometry.is_empty:
            continue
        for edge_result in envelope.edges:
            distance = edge_result.lenient_m if reading == "lenient" else edge_result.strict_m
            if distance is None or distance <= 0:
                continue
            assert geometry.distance(edge_result.geometry) >= distance - 0.01


@settings(max_examples=25, deadline=None)
@given(extra=st.floats(min_value=0.0, max_value=5.0))
def test_larger_setbacks_never_grow_the_area(extra: float) -> None:
    def area(distance: float) -> float:
        rules = [
            *[r for r in ub_rules() if r.kind != "setback_side"],
            rule("setback_side", {"min_m": distance}),
        ]
        return derive_envelope(envelope_input(zones=[zone(rules=rules)])).contours["lenient"].area_m2

    assert area(3.0 + extra) <= area(3.0) + 1e-6


def test_result_is_deterministic() -> None:
    first = derive_envelope(envelope_input())
    second = derive_envelope(envelope_input())
    assert first.contours["strict"].area_m2 == second.contours["strict"].area_m2
    assert first.warnings == second.warnings
    assert math.isclose(first.contours["lenient"].geometry.area, second.contours["lenient"].geometry.area)
