"""Fachlogik von H2: Parität mit dem Mockup (Spez. 11.2), Fläche zulässiger Ursprünge, Prüfung je Kante,
Schnellstellungen, Zulässigkeit und Eigenschaften (Spez. 11.1).

Testgrundstück: 20 × 31 m, Straße im Norden bei y = 31, Regeln der Zone UB (5 m Straße, je 3 m seitlich, 5 m
hinten). Lokaler Ursprung ist die Südwestecke.
"""

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from shapely.geometry import Point, Polygon

from app.configuration.domain.checks import parse_storeys, storeys_fit
from app.configuration.domain.context import build_context
from app.configuration.domain.fit import evaluate_type, with_suggestions
from app.configuration.domain.placement import Placement, check_placement
from app.configuration.domain.presets import all_presets, compute
from app.configuration.domain.rotations import (
    allowed_rotations,
    candidate_rotations,
    is_allowed_rotation,
)
from app.configuration.domain.surface import edge_requirement, part_surface
from app.envelope.domain.derive import derive_envelope
from tests.configuration_support import (
    _derive,
    context,
    house,
    ligne,
    plateau,
    plateau_adapte,
    ub_with,
)
from tests.envelope_support import constraint, edges_of_rectangle, rectangle, rule, site, ub_rules, zone


def codes(checks: list, only: str = "fail") -> list[str]:  # type: ignore[type-arg]
    return sorted(c.code for c in checks if c.status == only)


def surface_of(house_type, ctx, rotation: float = 0.0, **kw):  # type: ignore[no-untyped-def]
    return part_surface(house_type, ctx.parts[0], rotation, ctx, kw.pop("boundary", {}), **kw)


# ---------------------------------------------------------------------------
# A – Parität mit dem Mockup (Spez. 11.2)
# ---------------------------------------------------------------------------


def test_ligne_surface_is_the_setback_rectangle() -> None:
    """Haus 12 × 8 in 14 × 21: Ursprünge liegen in [3, 5] × [5, 18] (mit 1 cm Toleranz)."""
    ctx = context()
    min_x, min_y, max_x, max_y = surface_of(ligne(), ctx).bounds
    assert (min_x, min_y, max_x, max_y) == pytest.approx((2.99, 4.99, 5.01, 18.01), abs=0.005)
    exact = surface_of(ligne(), ctx, exact=True)
    assert exact.bounds == pytest.approx((3.0, 5.0, 5.0, 18.0), abs=0.001)


def test_ligne_street_near_matches_the_mockup() -> None:
    """„Ligne straßennah“: Straße 5,00 · West 4,00 · Ost 4,00 · hinten 18,00 m."""
    ctx = context()
    placement = compute(ligne(), ctx, "street_near", {})
    assert placement is not None
    assert placement.rotation_deg == pytest.approx(0.0)
    assert placement.origin == pytest.approx((4.0, 18.0), abs=0.01)
    result = check_placement(ligne(), placement, ctx, {})
    assert result.valid
    by_seq = {m.seq: m.measured_m for m in result.edges}
    # Kanten: 1 hinten (Süden), 2 Osten, 3 Straße (Norden), 4 Westen
    assert by_seq[3] == pytest.approx(5.0, abs=0.01)
    assert by_seq[4] == pytest.approx(4.0, abs=0.01)
    assert by_seq[2] == pytest.approx(4.0, abs=0.01)
    assert by_seq[1] == pytest.approx(18.0, abs=0.01)


def test_set_back_centres_the_house_in_the_depth() -> None:
    ctx = context()
    placement = compute(ligne(), ctx, "set_back", {})
    assert placement is not None
    assert placement.origin[1] == pytest.approx((5.0 + 18.0) / 2.0, abs=0.3)
    assert placement.origin[0] == pytest.approx(4.0, abs=0.3)


def test_garden_max_pushes_the_house_to_the_street() -> None:
    ctx = context()
    placement = compute(ligne(), ctx, "garden_max", {})
    assert placement is not None
    assert placement.origin[1] == pytest.approx(18.0, abs=0.3)


def test_presets_return_none_when_nothing_fits() -> None:
    ctx = context()
    assert all_presets(house(width=30.0), ctx, {}) == {
        "street_near": None,
        "set_back": None,
        "garden_max": None,
    }


def test_plateau_is_blocked_by_the_roof_form_only() -> None:
    """Plateau (16,5 × 8, Flachdach): gesperrt wegen der Dachform. Kein Grund „passt nicht“: um 90° gedreht
    liegt es innerhalb von 14 × 21 m (Spez. 11.2)."""
    ctx = context()
    fit = evaluate_type(plateau(), ctx)
    assert not fit.allowed
    assert [c.code for c in fit.reasons] == ["roof_form"]
    assert 90.0 in candidate_rotations(plateau(), ctx)


def test_plateau_gets_the_adapted_type_as_suggestion() -> None:
    ctx = context()
    fits = with_suggestions([evaluate_type(t, ctx) for t in (plateau(), plateau_adapte(), ligne())])
    plateau_fit = next(f for f in fits if f.house.slug == "plateau")
    assert plateau_fit.suggestions == ["plateau_adapte"]
    assert next(f for f in fits if f.house.slug == "ligne").allowed


def test_gable_wide_house_with_ridge_parallel_to_street_does_not_fit() -> None:
    """First parallel zur Straße erzwingt 16,5 m Breite: dazu kommt der Grund „passt nicht“."""
    wide = house("wide", width=16.5)
    rules = ub_with(roof={"allowed_forms": ["gable", "hip"], "ridge_orientation": "parallel_to_street"})
    ctx = context(rules)
    fit = evaluate_type(wide, ctx)
    assert not fit.allowed
    assert "no_valid_position" in [c.code for c in fit.reasons]
    # Ohne die Vorgabe passt es um 90° gedreht
    assert evaluate_type(wide, context()).allowed


def test_north_crossing_reports_the_street_setback() -> None:
    ctx = context()
    result = check_placement(ligne(), Placement((4.0, 19.0), 0.0), ctx, {})
    assert not result.valid
    assert codes(result.checks) == ["setback_street"]
    assert next(c for c in result.checks if c.status == "fail").edge_seq == 3


def test_north_west_corner_reports_two_violations() -> None:
    ctx = context()
    result = check_placement(ligne(), Placement((1.0, 19.0), 0.0), ctx, {})
    assert codes(result.checks) == ["setback_side", "setback_street"]


def test_placement_outside_the_site_is_a_violation() -> None:
    ctx = context()
    result = check_placement(ligne(), Placement((30.0, 5.0), 0.0), ctx, {})
    assert "outside_site" in codes(result.checks)


# ---------------------------------------------------------------------------
# B – Abstände, Grenze, Höhen
# ---------------------------------------------------------------------------


def test_setback_uses_the_height_of_the_house() -> None:
    """`max(min_m, faktor × H)` mit der Höhe des Typs, nicht der Zone (Spez. 5.3.2)."""
    rules = ub_with(setback_side={"min_m": 3.0, "height_factor": 0.5, "height_basis": "ridge"})
    ctx = context(rules)
    edge = next(e for e in ctx.edges if e.kind == "side")
    req = edge_requirement(edge, ctx.parts[0], ligne(), {})
    assert req.distance_m == pytest.approx(4.2)  # 8,4 m / 2
    low = edge_requirement(edge, ctx.parts[0], house(ridge_height_m=5.0, eave_height_m=3.0), {})
    assert low.distance_m == pytest.approx(3.0)


def test_building_on_the_boundary_is_an_explicit_choice() -> None:
    rules = ub_with(setback_side={"min_m": 3.0, "allow_on_boundary": True})
    ctx = context(rules)
    west = next(e for e in ctx.edges if e.seq == 4)
    plain = surface_of(ligne(), ctx, exact=True)
    with_option = surface_of(ligne(), ctx, exact=True, boundary={4: True})
    assert plain.bounds[0] == pytest.approx(3.0, abs=0.001)
    assert with_option.bounds[0] == pytest.approx(0.0, abs=0.001)
    result = check_placement(ligne(), Placement((0.0, 10.0), 0.0), ctx, {})
    assert "setback_side" in codes(result.checks)
    on_boundary = check_placement(ligne(), Placement((0.0, 10.0), 0.0), ctx, {4: True})
    assert on_boundary.valid
    assert edge_requirement(west, ctx.parts[0], ligne(), {4: True}).on_boundary


def test_boundary_choice_is_ignored_where_the_rule_forbids_it() -> None:
    ctx = context()
    west = next(e for e in ctx.edges if e.seq == 4)
    req = edge_requirement(west, ctx.parts[0], ligne(), {4: True})
    assert req.distance_m == pytest.approx(3.0) and not req.on_boundary


def test_boundary_height_limit_is_checked() -> None:
    rules = ub_with(setback_side={"min_m": 3.0, "allow_on_boundary": True, "on_boundary_max_height_m": 3.5})
    ctx = context(rules)
    result = check_placement(ligne(), Placement((0.0, 10.0), 0.0), ctx, {4: True})
    assert "on_boundary_height" in codes(result.checks)


def test_unknown_rule_is_a_hint_and_blocks_nothing() -> None:
    rules = [r for r in ub_rules() if r.kind != "setback_side"] + [
        rule("setback_side", status="unknown", reason="quote_unverified")
    ]
    ctx = context(rules)
    assert surface_of(ligne(), ctx, exact=True).bounds[0] == pytest.approx(0.0, abs=0.001)
    result = check_placement(ligne(), Placement((0.5, 10.0), 0.0), ctx, {})
    assert result.valid
    assert "setback_side_unknown" in codes(result.checks, "unknown")


def test_not_regulated_rule_needs_no_distance() -> None:
    rules = [r for r in ub_rules() if r.kind != "setback_rear"] + [
        rule("setback_rear", status="not_regulated")
    ]
    ctx = context(rules)
    assert surface_of(ligne(), ctx, exact=True).bounds[1] == pytest.approx(0.0, abs=0.001)


def test_overhang_is_measured_where_the_rule_says_so() -> None:
    """Straße ab Fassade, seitlich ab Dachüberstand: der Überstand darf nicht auf fremden Grund ragen."""
    rules = ub_with(setback_side={"min_m": 3.0, "measured_from": "any_projection"})
    ctx = context(rules)
    overhung = house(overhang=0.5)
    exact = surface_of(overhung, ctx, exact=True)
    assert exact.bounds[0] == pytest.approx(3.5, abs=0.001)  # 3 m + 0,5 m Überstand
    assert exact.bounds[1] == pytest.approx(5.0 + 0.0, abs=0.6)


def test_heights_of_the_type_against_the_zone() -> None:
    ctx = context()
    tall = house(ridge_height_m=9.6, eave_height_m=6.4)
    fit = evaluate_type(tall, ctx)
    assert not fit.allowed
    assert {c.code for c in fit.reasons} == {"height_ridge", "height_eave"}
    assert evaluate_type(ligne(), ctx).allowed


def test_storeys_are_compared_as_a_sequence() -> None:
    assert parse_storeys("R+1+C") == (1, "C")
    assert parse_storeys("R") == (0, "")
    assert storeys_fit("R+1", "R+1+C")
    assert storeys_fit("R+1+C", "R+1+C")
    assert not storeys_fit("R+2", "R+1+C")
    assert not storeys_fit("R+1+C", "R+1")
    assert not storeys_fit("xyz", "R+1")


def test_pitch_range_uses_the_tolerance() -> None:
    ctx = context()
    edge_case = house(pitch_deg=34.95)
    assert evaluate_type(edge_case, ctx).allowed  # 35° Mindestneigung, 0,1° Toleranz
    steep = house(pitch_deg=47.0)
    assert [c.code for c in evaluate_type(steep, ctx).reasons] == ["roof_pitch"]


def test_footprint_ratio_is_checked_per_part() -> None:
    rules = ub_with(max_footprint_ratio={"ratio": 0.1})  # 62 m² auf 620 m²
    fit = evaluate_type(ligne(), context(rules))
    assert [c.code for c in fit.reasons] == ["footprint"]


def test_steep_terrain_makes_heights_unverifiable_not_blocking() -> None:
    ctx = context(site_input=site(slope_percent=8.0))
    tall = house(ridge_height_m=9.6, eave_height_m=6.4)
    fit = evaluate_type(tall, ctx)
    assert fit.allowed
    assert "height_unverifiable" in [c.code for c in fit.hints]


def test_missing_rules_only_give_hints() -> None:
    rules = [r for r in ub_rules() if r.kind not in ("roof", "max_height")]
    fit = evaluate_type(plateau(), context(rules))
    assert fit.allowed
    assert {"roof_unknown", "max_height_unknown"} <= {c.code for c in fit.hints}


# ---------------------------------------------------------------------------
# C – Bauband, Bauverbot, Zonen
# ---------------------------------------------------------------------------


def test_band_for_the_whole_building_limits_the_area() -> None:
    rules = ub_with(setback_street={"min_m": 5.0, "max_m": 16.0, "mode": "range", "band": "building"})
    ctx = context(rules)
    exact = surface_of(ligne(), ctx, exact=True)
    assert exact.bounds[1] == pytest.approx(15.0, abs=0.01)  # Süd­kante des Hauses bei y ≥ 31 − 16
    far = check_placement(ligne(), Placement((4.0, 8.0), 0.0), ctx, {})
    assert "band_building" in codes(far.checks)


def test_band_for_the_facade_only_asks_for_the_street_side() -> None:
    rules = ub_with(setback_street={"min_m": 5.0, "max_m": 6.0, "mode": "range", "band": "facade"})
    ctx = context(rules)
    exact = surface_of(ligne(), ctx, exact=True)
    assert exact.bounds[1] == pytest.approx(17.0, abs=0.01)  # Straßenfassade bei y + 8 ≥ 31 − 6
    assert exact.bounds[3] == pytest.approx(18.0, abs=0.01)
    far = check_placement(ligne(), Placement((4.0, 10.0), 0.0), ctx, {})
    assert "band_facade" in codes(far.checks)
    near = check_placement(ligne(), Placement((4.0, 17.5), 0.0), ctx, {})
    assert near.valid


def test_unclear_band_is_a_hint() -> None:
    rules = ub_with(setback_street={"min_m": 5.0, "max_m": 6.0, "mode": "range"})
    ctx = context(rules)
    result = check_placement(ligne(), Placement((4.0, 10.0), 0.0), ctx, {})
    assert result.valid
    assert "band_unclear" in codes(result.checks, "hint")


def test_no_build_area_is_excluded_from_the_surface() -> None:
    blocked = Polygon([(0.0, 10.0), (20.0, 10.0), (20.0, 14.0), (0.0, 14.0)])
    ctx = context(constraints=[constraint(blocked)])
    exact = surface_of(ligne(), ctx, exact=True)
    assert exact.intersection(Point(4.0, 12.0).buffer(0.01)).is_empty
    result = check_placement(ligne(), Placement((4.0, 12.0), 0.0), ctx, {})
    assert "no_build_area" in codes(result.checks)


def test_zone_without_rules_gives_a_free_context() -> None:
    data, envelope = _derive(
        zones=[zone(status="unavailable", reason="no_plan", rules=[])], rules_status="unavailable"
    )
    ctx = build_context(data, envelope)
    assert ctx.is_free and ctx.free_reason == "rules_unavailable"
    assert check_placement(ligne(), Placement((3.0, 3.0), 0.0), ctx, {}).valid


def test_house_must_stay_in_one_zone() -> None:
    north = Polygon([(0.0, 15.5), (20.0, 15.5), (20.0, 31.0), (0.0, 31.0)])
    south = Polygon([(0.0, 0.0), (20.0, 0.0), (20.0, 15.5), (0.0, 15.5)])
    zones = [
        zone("UA", polygon=north, rules=ub_rules(), share=0.5),
        zone("UB", polygon=south, rules=ub_rules(), share=0.5),
    ]
    ctx = context(zones=zones)
    assert len(ctx.parts) == 2
    across = check_placement(ligne(), Placement((4.0, 10.0), 0.0), ctx, {})
    assert "crosses_zones" in codes(across.checks)
    inside = check_placement(ligne(), Placement((4.0, 6.0), 0.0), ctx, {})
    assert inside.valid and inside.part is not None and inside.part.zone_code == "UB"


# ---------------------------------------------------------------------------
# D – Drehung
# ---------------------------------------------------------------------------


def test_rotations_are_the_street_orientation_and_three_quarter_turns() -> None:
    ctx = context()
    assert candidate_rotations(ligne(), ctx) == [0.0, 90.0, 180.0, 270.0]
    assert is_allowed_rotation(90.03, [0.0, 90.0]) == 90.0
    assert is_allowed_rotation(45.0, [0.0, 90.0]) is None


def test_ridge_orientation_filters_rotations() -> None:
    rules = ub_with(roof={"allowed_forms": ["gable", "hip"], "ridge_orientation": "parallel_to_street"})
    ctx = context(rules)
    assert allowed_rotations(ligne(), ctx.parts[0], ctx) == [0.0, 180.0]
    perpendicular = ub_with(
        roof={"allowed_forms": ["gable", "hip"], "ridge_orientation": "perpendicular_to_street"}
    )
    ctx2 = context(perpendicular)
    assert allowed_rotations(ligne(), ctx2.parts[0], ctx2) == [90.0, 270.0]
    result = check_placement(ligne(), Placement((4.0, 10.0), 90.0), ctx, {})
    assert "ridge_orientation" in codes(result.checks)


def test_rotated_house_uses_the_clockwise_transform() -> None:
    """Spez. 5.3.4: (x, y) → (e + x·cosθ + y·sinθ, n − x·sinθ + y·cosθ); Modellnorden zeigt nach θ."""
    ctx = context()
    result = check_placement(ligne(), Placement((10.0, 10.0), 90.0), ctx, {})
    min_x, min_y, max_x, max_y = result.facade.bounds
    # 12 × 8 um 90° im Uhrzeigersinn: 8 breit, 12 tief; Punkt (12, 0) → (10, −2)
    assert (min_x, min_y, max_x, max_y) == pytest.approx((10.0, -2.0, 18.0, 10.0), abs=1e-6)


# ---------------------------------------------------------------------------
# E – Weg E und Eigenschaften
# ---------------------------------------------------------------------------


def test_manual_sketch_context_only_checks_the_outline() -> None:
    data, _ = _derive()
    ctx = build_context(data, None)
    assert ctx.is_free and ctx.free_reason == "manual_sketch" and not ctx.edges
    assert check_placement(ligne(), Placement((0.5, 0.5), 0.0), ctx, {}).valid
    outside = check_placement(ligne(), Placement((15.0, 0.5), 0.0), ctx, {})
    assert codes(outside.checks) == ["outside_outline"]
    assert not evaluate_type(house(width=40.0), ctx).allowed


@pytest.mark.parametrize("width,depth", [(12.0, 8.0), (9.5, 9.5), (6.0, 14.0)])
@given(x=st.floats(0.0, 20.0), y=st.floats(0.0, 31.0), quarter=st.integers(0, 3))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_surface_and_check_agree(
    width: float, depth: float, x: float, y: float, quarter: int
) -> None:
    """Jeder Ursprung der Fläche besteht die Prüfung je Kante; Ursprünge deutlich außerhalb nicht."""
    ctx = context()
    typ = house(width=width, depth=depth)
    rotation = candidate_rotations(typ, ctx)[quarter]
    surface = part_surface(typ, ctx.parts[0], rotation, ctx, {})
    valid = check_placement(typ, Placement((x, y), rotation), ctx, {}).valid
    point = Point(x, y)
    if surface.buffer(-0.001).contains(point):
        assert valid, (x, y, rotation)
    if not surface.is_empty and surface.distance(point) > 0.03:
        assert not valid, (x, y, rotation)
    if surface.is_empty:
        assert not valid


def test_engine_matches_g3_contour_for_a_point_like_house() -> None:
    """Ein winziges Haus darf überall stehen, wo der Baurahmen (G3) bebaubar ist."""
    data, envelope = _derive()
    ctx = build_context(data, envelope)
    around_origin = Polygon([(-0.05, -0.05), (0.05, -0.05), (0.05, 0.05), (-0.05, 0.05)])
    tiny = replace(house(), facade=around_origin, projection=around_origin)
    surface = part_surface(tiny, ctx.parts[0], 0.0, ctx, {}, exact=True)
    contour = envelope.contours["strict"].geometry
    assert surface.symmetric_difference(contour.buffer(-0.05, join_style="mitre")).area < 0.05
    assert rectangle().area > 0 and edges_of_rectangle()
    assert derive_envelope(data).status == "ok"
