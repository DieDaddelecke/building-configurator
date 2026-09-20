"""Reine Fachlogik von H3: Auswahl, Kosten, Energie, Himmelsrichtung, Terrasse, Carport, Flächen, Prüfungen.

Parität mit dem Mockup nach Spez. 11.2 (Korridor ohne Mehrwertsteuer). Testgrundstück 20 × 31 m, Straße im
Norden, Zone UB mit festen Abständen; Ligne 12 × 8 m mit Straßenfassade im Norden und Gartenfassade im Süden.
"""

import dataclasses

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.catalog.domain.offer import EnergyFinding
from app.catalog.domain.options import OptionParamsInvalid, normalize_params, normalize_regulatory
from app.configuration.domain.costs import compute_costs, round_thousand
from app.configuration.domain.design import evaluate_design
from app.configuration.domain.energy import energy_status
from app.configuration.domain.geometry import place
from app.configuration.domain.options import Selection, resolve
from app.configuration.domain.orientation import convergence_deg, orientation
from app.configuration.domain.outbuildings import (
    CarportSpec,
    carport_spec,
    place_carport,
    terrace_polygon,
    terrace_spec,
)
from app.configuration.domain.placement import Placement, check_placement
from tests.configuration_support import (
    context,
    house,
    mockup_offer,
    option_offer,
    package_offer,
    type_offer,
    ub_with,
)
from tests.envelope_support import edges_of_rectangle, rectangle, rule, site, ub_rules, zone

# ---------------------------------------------------------------------------
# Art und Maße einer Option
# ---------------------------------------------------------------------------


def test_terrace_params_are_filled_with_defaults() -> None:
    assert normalize_params("terrace", {}) == {
        "depth_m": 3.0,
        "height_above_terrain_m": 0.3,
        "sealing_factor": 1.0,
    }
    assert normalize_params("terrace", {"depth_m": 2.5})["depth_m"] == 2.5


def test_carport_needs_one_or_two_spaces_and_gets_default_size() -> None:
    single = normalize_params("carport", {"spaces": 1})
    double = normalize_params("carport", {"spaces": 2})
    assert (single["width_m"], single["depth_m"]) == (3.0, 5.0)
    assert (double["width_m"], double["depth_m"]) == (6.0, 5.0)
    for bad in ({}, {"spaces": 3}, {"spaces": True}, {"spaces": 1, "width_m": 30}, {"spaces": 1, "rot": 1}):
        with pytest.raises(OptionParamsInvalid):
            normalize_params("carport", bad)


def test_plain_option_has_no_dimensions_and_unknown_kinds_fail() -> None:
    assert normalize_params("plain", {}) == {}
    with pytest.raises(OptionParamsInvalid):
        normalize_params("plain", {"depth_m": 3})
    with pytest.raises(OptionParamsInvalid):
        normalize_params("pergola", {})


def test_regulatory_material_comes_from_the_rule_vocabulary() -> None:
    assert normalize_regulatory({"facade_material": "wood", "roof_material": ""}) == {
        "facade_material": "wood"
    }
    with pytest.raises(OptionParamsInvalid):
        normalize_regulatory({"facade_material": "gold"})
    with pytest.raises(OptionParamsInvalid):
        normalize_regulatory({"colour": "wood"})


# ---------------------------------------------------------------------------
# Auswahl
# ---------------------------------------------------------------------------


def test_option_without_price_row_is_not_offered() -> None:
    offer = type_offer(options=(option_offer("keller", None),))
    resolved = resolve(offer, Selection(None, ("keller",)))
    assert [(r.code, r.slug) for r in resolved.invalid] == [("not_offered", "keller")]
    assert resolved.effective == ()


def test_unknown_slugs_and_missing_catalog_are_reasons_not_silent() -> None:
    resolved = resolve(type_offer(), Selection("gold", ("nix",)))
    assert {(r.code, r.slug) for r in resolved.invalid} == {
        ("unknown_package", "gold"),
        ("unknown_option", "nix"),
    }
    offline = resolve(type_offer(catalog=False), Selection("base", ("pv",)))
    assert {r.code for r in offline.invalid} == {"catalog_unavailable"}


def test_included_option_is_effective_and_free() -> None:
    resolved = resolve(mockup_offer(), Selection("confort", ()))
    assert [o.slug for o in resolved.effective] == ["ziegel_dach"]
    assert resolved.charged() == ()


def test_exclusion_between_explicit_options_is_reported_with_both_slugs() -> None:
    resolved = resolve(mockup_offer(), Selection("base", ("holz_sued", "holz_voll")))
    assert [(r.code, r.slug, r.other) for r in resolved.invalid] == [
        ("excluded_by", "holz_voll", "holz_sued")  # der später Gewählte trägt den Grund
    ]


def test_two_options_included_by_the_line_are_ignored_as_data_error() -> None:
    """Im Mockup enthält Signature beide Holzverschalungen, die sich ausschließen (Plan H3 3.1)."""
    assert resolve(mockup_offer(), Selection("signature", ())).invalid == ()


def test_explicit_option_excluded_by_an_included_one_is_reported() -> None:
    resolved = resolve(mockup_offer(), Selection("signature", ("ziegel_eg", "holz_voll")))
    assert resolved.invalid == ()  # holz_voll ist selbst in Signature enthalten
    offer = type_offer(
        packages=(package_offer("p", 0, included=("a",)),),
        options=(option_offer("a", 1, excludes=("b",)), option_offer("b", 1)),
    )
    reasons = resolve(offer, Selection("p", ("b",))).invalid
    assert [(r.code, r.slug, r.other) for r in reasons] == [("excluded_by", "b", "a")]


def test_two_carports_exclude_each_other_without_being_told() -> None:
    offer = type_offer(
        options=(
            option_offer("carport_1", 1, kind="carport", params={"spaces": 1}),
            option_offer("carport_2", 1, kind="carport", params={"spaces": 2, "width_m": 6.0}),
        )
    )
    reasons = resolve(offer, Selection(None, ("carport_1", "carport_2"))).invalid
    assert len(reasons) == 1 and reasons[0].code == "excluded_by"


# ---------------------------------------------------------------------------
# Kosten: Parität Spez. 11.2 ohne Mehrwertsteuer
# ---------------------------------------------------------------------------


def corridor(package: str | None, options: tuple[str, ...] = ()) -> tuple[int, int]:
    offer = mockup_offer()
    resolved = resolve(offer, Selection(package, options))
    energy = energy_status(offer.finding(package))
    display = compute_costs(offer, resolved, energy, {}).display
    assert display is not None
    return display.min_cents // 100, display.max_cents // 100


def test_corridor_ligne_base_includes_re2020_conformity() -> None:
    assert corridor("base") == (338_000, 372_000)


def test_corridor_ligne_confort() -> None:
    assert corridor("confort") == (362_000, 396_000)


def test_corridor_confort_with_larch_and_terrace() -> None:
    assert corridor("confort", ("holz_sued", "terrasse")) == (384_000, 418_000)


def test_options_included_in_the_line_do_not_raise_the_corridor() -> None:
    bare = corridor("signature")
    assert corridor("signature", ("holz_sued", "fenster_sued", "pv")) == bare
    assert bare == (399_000, 433_000)


def test_switching_to_a_line_without_the_option_charges_it_again() -> None:
    assert corridor("signature", ("pv",)) == corridor("signature")
    with_pv = corridor("confort", ("pv",))
    assert with_pv[0] - corridor("confort")[0] == 11_000


def test_terrace_is_priced_per_square_metre_from_its_area() -> None:
    offer = type_offer(options=(option_offer("terrasse", 400, kind="terrace"),))
    resolved = resolve(offer, Selection(None, ("terrasse",)))
    costs = compute_costs(offer, resolved, energy_status(None), {"terrasse": 36.0})
    item = next(i for i in costs.items if i.slug == "terrasse")
    assert (item.quantity, item.unit, item.unit_price_cents) == (36.0, "m2", 40_000)
    assert item.min_cents == item.max_cents == 36 * 40_000


def test_gross_display_uses_the_vat_rate_of_the_catalog() -> None:
    offer = type_offer(vat_rate=0.2, base_eur=(300_000, 350_000))
    costs = compute_costs(offer, resolve(offer, Selection()), energy_status(None), {})
    assert costs.net is not None and costs.gross is not None and costs.display is not None
    assert costs.gross.min_cents == 36_000_000
    assert costs.display.min_cents == 36_000_000 and costs.display.max_cents == 42_000_000


def test_rounding_is_commercial_to_thousands() -> None:
    assert round_thousand(33_750_000) == 33_800_000  # 337.500 € → 338.000 €
    assert round_thousand(33_749_999) == 33_700_000
    assert round_thousand(0) == 0


def test_costs_are_unavailable_without_catalog_or_base_price() -> None:
    off = type_offer(catalog=False)
    missing = type_offer(base_eur=None)
    for offer, reason in ((off, "catalog_unavailable"), (missing, "base_price_missing")):
        costs = compute_costs(offer, resolve(offer, Selection()), energy_status(None), {})
        assert (costs.available, costs.reason, costs.net, costs.display) == (False, reason, None, None)


def test_corridor_never_inverts() -> None:
    offer = mockup_offer()
    everything = tuple(o.slug for o in offer.options if o.slug not in ("holz_voll",))
    resolved = resolve(offer, Selection("base", everything))
    costs = compute_costs(offer, resolved, energy_status(offer.finding("base")), {})
    assert costs.net is not None and costs.net.min_cents <= costs.net.max_cents


def test_no_item_carries_a_total() -> None:
    offer = mockup_offer()
    costs = compute_costs(offer, resolve(offer, Selection("confort")), energy_status(None), {})
    assert {i.kind for i in costs.items} <= {"base", "package", "option", "energy"}


# ---------------------------------------------------------------------------
# Energie
# ---------------------------------------------------------------------------


def test_energy_status_from_the_finding() -> None:
    assert energy_status(None).status == "not_assessed"
    assert energy_status(EnergyFinding("x", "H2b", "ok", True)).status == "compliant"
    action = energy_status(EnergyFinding("x", "H2b", "knapp", False, 950_000, "Dämmung"))
    assert (action.status, action.surcharge_cents, action.measures) == ("action", 950_000, "Dämmung")


# ---------------------------------------------------------------------------
# Himmelsrichtung
# ---------------------------------------------------------------------------


def test_convergence_is_zero_on_the_central_meridian() -> None:
    assert convergence_deg(700_000.0, 6_600_000.0) == pytest.approx(0.0, abs=1e-9)


def test_convergence_at_nantes_matches_the_cone_formula() -> None:
    """Gegenprobe: n·(λ − λ₀) mit n = 0,7256 und λ = −1,55° ergibt −3,30°."""
    gamma = convergence_deg(355_000.0, 6_689_000.0)
    assert gamma == pytest.approx(0.7256077650532670 * (-1.55 - 3.0), abs=0.05)
    assert -3.4 < gamma < -3.2
    assert convergence_deg(1_000_000.0, 6_600_000.0) > 0  # östlich des Mittelmeridians positiv


def test_true_azimuth_is_grid_plus_convergence() -> None:
    result = orientation(house(), 0.0, (355_000.0, 6_689_000.0))
    assert result.facades["street"] == pytest.approx(360.0 + result.convergence_deg, abs=0.1)
    assert result.facades["garden"] == pytest.approx(180.0 + result.convergence_deg, abs=0.1)
    turned = orientation(house(), 90.0, (355_000.0, 6_689_000.0))
    assert turned.facades["garden"] == pytest.approx(270.0 + turned.convergence_deg, abs=0.1)


# ---------------------------------------------------------------------------
# Terrasse
# ---------------------------------------------------------------------------


def test_terrace_spans_the_garden_facade_and_lies_outside_the_house() -> None:
    spec = terrace_spec(option_offer("terrasse", 1, kind="terrace"), house())
    assert spec.width_m == pytest.approx(12.0) and spec.area_m2 == pytest.approx(36.0)
    placement = Placement(origin=(4.0, 8.0), rotation_deg=0.0)
    polygon = terrace_polygon(spec, placement)
    assert polygon is not None
    assert polygon.area == pytest.approx(36.0)
    body = place(house().facade, placement.origin, 0.0)
    assert polygon.intersection(body).area == pytest.approx(0.0, abs=1e-9)
    assert polygon.bounds == pytest.approx((4.0, 5.0, 16.0, 8.0))  # südlich des Hauses


def test_terrace_follows_the_rotation() -> None:
    spec = terrace_spec(option_offer("terrasse", 1, kind="terrace"), house())
    polygon = terrace_polygon(spec, Placement(origin=(10.0, 10.0), rotation_deg=180.0))
    assert polygon is not None
    assert polygon.centroid.y > place(house().facade, (10.0, 10.0), 180.0).centroid.y  # nun nördlich


def test_house_without_garden_role_cannot_have_a_terrace() -> None:
    spec = terrace_spec(option_offer("terrasse", 1, kind="terrace"), house(roles=False))
    assert spec.width_m is None and spec.area_m2 == 0.0
    assert terrace_polygon(spec, Placement((4.0, 8.0), 0.0)) is None


# ---------------------------------------------------------------------------
# Carport
# ---------------------------------------------------------------------------

SINGLE = CarportSpec("carport_1", 1, 3.0, 5.0, 2.7)
DOUBLE = CarportSpec("carport_2", 2, 6.0, 5.0, 2.7)


def placed_house(origin: tuple[float, float] = (4.0, 8.0)):
    return place(house().projection, origin, 0.0)


def test_carport_stands_at_the_street_setback_and_not_in_the_house() -> None:
    ctx = context()
    result = place_carport(SINGLE, ctx, placed_house())
    assert result is not None
    street = ctx.edges[2].geometry
    assert result.polygon.distance(street) == pytest.approx(
        5.0, abs=0.02
    )  # Abstand des Hauptbaus als Annahme
    assert result.polygon.intersection(placed_house()).area == pytest.approx(0.0, abs=1e-9)
    assert ctx.polygon.covers(result.polygon)
    assert result.setback == "assumed"
    assert result.polygon.area == pytest.approx(15.0)


def test_double_carport_is_twice_as_wide() -> None:
    result = place_carport(DOUBLE, context(), placed_house())
    assert result is not None and result.polygon.area == pytest.approx(30.0)
    minx, miny, maxx, maxy = result.polygon.bounds
    assert (maxx - minx, maxy - miny) == pytest.approx((6.0, 5.0))


def test_carport_with_a_rule_for_annexes_uses_it_and_is_known() -> None:
    rules = [
        *ub_rules(),
        rule("setback_street", {"min_m": 2.0, "mode": "min"}, building_kind="annex"),
        rule("setback_side", {"min_m": 1.0, "allow_on_boundary": False}, building_kind="annex"),
        rule("setback_rear", {"min_m": 1.0, "allow_on_boundary": False}, building_kind="annex"),
    ]
    ctx = context(rules)
    result = place_carport(SINGLE, ctx, placed_house())
    assert result is not None and result.setback == "known"
    assert result.polygon.distance(ctx.edges[2].geometry) == pytest.approx(2.0, abs=0.02)


def test_carport_falls_back_to_no_setbacks_when_the_main_ones_leave_no_room() -> None:
    narrow = rectangle(8.0, 31.0)
    ctx = context(
        site_input=site(polygon=narrow, edges=edges_of_rectangle(8.0, 31.0)), zones=[zone(polygon=narrow)]
    )
    result = place_carport(SINGLE, ctx, None)
    assert result is not None and result.setback == "relaxed"
    assert ctx.polygon.buffer(0.02).covers(result.polygon)


def test_carport_that_cannot_fit_anywhere_has_no_position() -> None:
    tiny = rectangle(2.0, 31.0)
    ctx = context(
        site_input=site(polygon=tiny, edges=edges_of_rectangle(2.0, 31.0)), zones=[zone(polygon=tiny)]
    )
    assert place_carport(SINGLE, ctx, None) is None


def test_carport_avoids_the_house_even_when_the_street_frontage_is_taken() -> None:
    """Steht das Haus vor der Straße, weicht der Carport aus, statt es zu berühren."""
    ctx = context()
    front = placed_house((4.0, 15.0))  # Haus bis y = 23, Straßenabstand 8 m
    result = place_carport(SINGLE, ctx, front)
    assert result is not None
    assert result.polygon.intersection(front).area == pytest.approx(0.0, abs=1e-9)
    assert result.polygon.distance(front) >= 0.49  # Abstand zum Haus


# ---------------------------------------------------------------------------
# Auswertung: Flächen und Prüfungen
# ---------------------------------------------------------------------------

HOUSE_AT = Placement(origin=(4.0, 8.0), rotation_deg=0.0)


def design_for(
    package: str | None, options: tuple[str, ...], *, rules=None, offer=None, origin=None, rotation=0.0
):
    ctx = context(rules)
    the_house = house()
    placement = Placement(origin=origin or (4.0, 8.0), rotation_deg=rotation)
    result = check_placement(the_house, placement, ctx, {})
    catalog = offer or type_offer(
        packages=(package_offer("confort", 34_000),),
        options=(
            option_offer("terrasse", 400, kind="terrace"),
            option_offer("carport_1", 14_500, kind="carport", params={"spaces": 1}),
            option_offer("carport_2", 14_500, kind="carport", params={"spaces": 2, "width_m": 6.0}),
            option_offer("pv", 11_200),
        ),
    )
    design = evaluate_design(the_house, placement, ctx, result, catalog, Selection(package, options))
    return design, ctx


def test_without_options_only_house_and_paths_are_sealed() -> None:
    design, _ = design_for(None, ())
    areas = design.areas
    assert areas is not None
    assert areas.site_m2 == pytest.approx(620.0)
    assert areas.house_m2 == pytest.approx(96.0)
    assert areas.sealed_m2 == pytest.approx(96.0 + 10.0)
    assert areas.unsealed_m2 == pytest.approx(620.0 - 106.0)
    assert design.terrace is None and design.carport is None and design.driveways == ()


def test_areas_with_carport_terrace_and_driveway_count_overlaps_once() -> None:
    design, _ = design_for("confort", ("terrasse", "carport_1"))
    areas = design.areas
    assert areas is not None and design.carport is not None
    assert areas.terrace_m2 == pytest.approx(36.0) and areas.carport_m2 == pytest.approx(15.0)
    (drive,) = design.driveways
    assert drive.source == "carport" and drive.length_m == pytest.approx(5.0, abs=0.02)
    assert areas.driveway_m2 == pytest.approx(3.0 * drive.length_m, abs=0.05)
    sealed = 96.0 + 15.0 + 36.0 + areas.driveway_m2 + 10.0
    assert areas.sealed_m2 == pytest.approx(sealed, abs=0.05)
    assert areas.sealed_m2 + areas.unsealed_m2 == pytest.approx(areas.site_m2, abs=0.01)
    assert areas.emprise_m2 == pytest.approx(96.0 + 15.0)  # Terrasse 0,3 m < 0,6 m zählt nicht


def test_terrace_above_the_limit_height_counts_to_the_footprint() -> None:
    offer = type_offer(
        options=(option_offer("terrasse", 400, kind="terrace", params={"height_above_terrain_m": 0.8}),)
    )
    design, _ = design_for(None, ("terrasse",), offer=offer)
    assert design.areas is not None
    assert design.areas.emprise_m2 == pytest.approx(96.0 + 36.0)


def test_sealing_factor_reduces_the_sealed_terrace_area() -> None:
    offer = type_offer(
        options=(option_offer("terrasse", 400, kind="terrace", params={"sealing_factor": 0.5}),)
    )
    design, _ = design_for(None, ("terrasse",), offer=offer)
    assert design.areas is not None
    assert design.areas.sealed_m2 == pytest.approx(96.0 + 0.5 * 36.0 + 10.0)


def codes(design) -> dict[str, str]:
    return {c.code: c.status for c in design.checks}


def test_footprint_total_blocks_when_house_and_carport_exceed_the_ratio() -> None:
    rules = ub_with(
        max_footprint_ratio={"ratio": 0.17}
    )  # 620 × 0.17 = 105,4 m²: Haus 96 + Carport 15 zu viel
    design, _ = design_for("confort", ("carport_1",), rules=rules)
    assert codes(design)["footprint_total"] == "fail"
    assert any(c.code == "footprint_total" for c in design.blocking)
    ok, _ = design_for("confort", (), rules=rules)
    assert "footprint_total" not in codes(ok)  # Haus allein prüft H2


def test_unsealed_minimum_blocks_the_option_that_breaks_it() -> None:
    rules = ub_with(unsealed_min={"ratio": 0.8})  # unversiegelt ≥ 496 m²
    without, _ = design_for("confort", (), rules=rules)
    assert codes(without)["unsealed_min"] == "pass"  # 514 m² frei
    with_terrace, _ = design_for("confort", ("terrasse",), rules=rules)
    assert codes(with_terrace)["unsealed_min"] == "fail" and with_terrace.blocking


def test_unknown_unsealed_rule_is_a_hint_and_never_blocks() -> None:
    rules = [r for r in ub_rules() if r.kind != "unsealed_min"]
    design, _ = design_for("confort", ("terrasse",), rules=rules)
    assert codes(design)["unsealed_min_unknown"] == "unknown"
    assert design.blocking == []


def test_effective_annex_rule_blocks_the_double_carport_but_not_the_single() -> None:
    rules = [*ub_rules(), rule("annex", {"max_footprint_m2": 20.0, "max_height_m": 3.0}, building_kind="any")]
    double, _ = design_for("confort", ("carport_2",), rules=rules)
    assert codes(double)["annex_footprint"] == "fail" and double.blocking
    single, _ = design_for("confort", ("carport_1",), rules=rules)
    assert codes(single)["annex_footprint"] == "pass" and codes(single)["annex_height"] == "pass"
    assert single.blocking == []


def test_annex_rule_that_is_not_effective_only_hints() -> None:
    rules = [*ub_rules(), rule("annex", {"max_footprint_m2": 5.0}, status="unknown", building_kind="any")]
    design, _ = design_for("confort", ("carport_2",), rules=rules)
    assert codes(design)["annex_unknown"] == "unknown" and design.blocking == []


def test_missing_annex_rule_is_only_a_hint_about_assumed_setbacks() -> None:
    design, _ = design_for("confort", ("carport_1",))
    check = next(c for c in design.checks if c.code == "carport_setback_assumed")
    assert (check.status, check.binding) == ("hint", False)
    assert design.blocking == []


def test_carport_without_room_is_a_binding_geometry_failure() -> None:
    tiny = rectangle(6.0, 31.0)
    ctx = context(
        site_input=site(polygon=tiny, edges=edges_of_rectangle(6.0, 31.0)), zones=[zone(polygon=tiny)]
    )
    the_house = house(width=4.0, depth=4.0)
    placement = Placement(origin=(1.0, 10.0), rotation_deg=0.0)
    result = check_placement(the_house, placement, ctx, {})
    offer = type_offer(
        options=(option_offer("carport_2", 1, kind="carport", params={"spaces": 2, "width_m": 6.0}),)
    )
    design = evaluate_design(the_house, placement, ctx, result, offer, Selection(None, ("carport_2",)))
    assert [c.code for c in design.blocking] == ["no_valid_position"]
    assert design.blocking[0].params["subject"] == "carport_2"


def test_terrace_without_garden_facade_is_blocked_with_its_reason() -> None:
    ctx = context()
    the_house = house(roles=False)
    placement = Placement(origin=(4.0, 8.0), rotation_deg=0.0)
    result = check_placement(the_house, placement, ctx, {})
    offer = type_offer(options=(option_offer("terrasse", 1, kind="terrace"),))
    design = evaluate_design(the_house, placement, ctx, result, offer, Selection(None, ("terrasse",)))
    assert [c.code for c in design.blocking] == ["no_garden_facade"]


def test_terrace_leaving_the_site_is_blocked() -> None:
    design, _ = design_for("confort", ("terrasse",), origin=(4.0, 5.0))  # Terrasse ab y = 2 ok
    assert "terrace_outside_site" not in codes(design)
    ctx = context()
    the_house = house()
    placement = Placement(origin=(4.0, 5.0), rotation_deg=0.0)
    result = check_placement(the_house, placement, ctx, {})
    deep = type_offer(options=(option_offer("terrasse", 1, kind="terrace", params={"depth_m": 6.0}),))
    outside = evaluate_design(the_house, placement, ctx, result, deep, Selection(None, ("terrasse",)))
    assert "terrace_outside_site" in {c.code for c in outside.blocking}


def test_parking_hint_without_carport_or_garage_door() -> None:
    design, _ = design_for("confort", ())
    assert codes(design)["parking_not_shown"] == "hint"
    with_carport, _ = design_for("confort", ("carport_1",))
    assert "parking_not_shown" not in codes(with_carport)


def test_parking_rule_compares_spaces_and_only_warns() -> None:
    rules = [*ub_rules(), rule("parking", {"spaces_per_dwelling": 2.0})]
    single, _ = design_for("confort", ("carport_1",), rules=rules)
    parking = next(c for c in single.checks if c.code == "parking")
    assert (parking.status, parking.binding, parking.measured, parking.limit) == ("hint", False, 1.0, 2.0)
    double, _ = design_for("confort", ("carport_2",), rules=rules)
    assert next(c for c in double.checks if c.code == "parking").status == "pass"


def test_material_of_option_and_line_is_checked_against_facade_and_roof_rules() -> None:
    rules = [
        *ub_rules(),
        rule("roof", {"allowed_forms": ["gable"], "materials_allowed": ["clay_tile"]}),
    ]
    rules = [r for r in rules if not (r.kind == "roof" and "pitch_min_deg" in r.params)]
    offer = type_offer(
        packages=(
            package_offer("confort", 1, regulatory={"facade_material": "wood", "roof_material": "zinc"}),
        ),
        options=(option_offer("stein", 1, regulatory={"facade_material": "stone"}),),
    )
    design, _ = design_for("confort", ("stein",), rules=rules, offer=offer)
    by_subject = {(c.code, c.params["subject"]): c.status for c in design.checks if "subject" in c.params}
    assert by_subject[("facade_material", "confort")] == "pass"  # wood ist erlaubt
    assert by_subject[("roof_material", "confort")] == "fail"  # zinc nicht
    assert by_subject[("facade_material", "stein")] == "fail"  # stone nicht erlaubt (render, wood, brick)
    assert {c.params["subject"] for c in design.blocking} == {"confort", "stein"}


def test_line_without_material_is_unknown_not_passed() -> None:
    offer = type_offer(packages=(package_offer("confort", 1),))
    design, _ = design_for("confort", (), offer=offer)
    unknown = [c for c in design.checks if c.code == "material_unknown"]
    assert unknown and all(c.status == "unknown" and not c.binding for c in unknown)


def test_free_mode_has_geometry_but_no_rule_checks() -> None:
    from app.configuration.domain.context import build_context
    from tests.configuration_support import _derive

    data, envelope = _derive(site_input=site())
    data = dataclasses.replace(data, rules_reason="manual_sketch")
    ctx = build_context(data, envelope)
    assert ctx.is_free
    the_house = house()
    placement = Placement(origin=(4.0, 8.0), rotation_deg=0.0)
    result = check_placement(the_house, placement, ctx, {})
    offer = type_offer(
        options=(option_offer("terrasse", 1, kind="terrace"), option_offer("carport_1", 1, kind="carport"))
    )
    design = evaluate_design(
        the_house, placement, ctx, result, offer, Selection(None, ("terrasse", "carport_1"))
    )
    assert design.terrace is not None and design.carport is not None and design.blocking == []
    assert not {c.code for c in design.checks} & {"unsealed_min", "footprint_total", "annex_footprint"}


def test_evaluation_without_placement_still_prices_the_terrace() -> None:
    ctx = context()
    offer = type_offer(options=(option_offer("terrasse", 400, kind="terrace"),))
    design = evaluate_design(house(), None, ctx, None, offer, Selection(None, ("terrasse",)))
    assert design.areas is None and design.terrace is None
    item = next(i for i in design.type_part.costs.items if i.slug == "terrasse")
    assert item.quantity == pytest.approx(36.0)  # Menge hängt nur vom Typ ab (Plan H3 3.8)


# ---------------------------------------------------------------------------
# Eigenschaften
# ---------------------------------------------------------------------------


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    x=st.floats(min_value=3.0, max_value=5.0),
    y=st.floats(min_value=5.0, max_value=18.0),
    spaces=st.sampled_from([1, 2]),
    depth=st.floats(min_value=3.0, max_value=6.0),
)
def test_property_carport_stays_in_the_site_and_out_of_the_house(
    x: float, y: float, spaces: int, depth: float
) -> None:
    ctx = context()
    the_house = house()
    placement = Placement(origin=(x, y), rotation_deg=0.0)
    result = check_placement(the_house, placement, ctx, {})
    spec = carport_spec(
        option_offer(
            "c", 1, kind="carport", params={"spaces": spaces, "width_m": 3.0 * spaces, "depth_m": depth}
        )
    )
    found = place_carport(spec, ctx, result.projection)
    if found is None:
        return
    assert ctx.polygon.buffer(0.02).covers(found.polygon)
    assert found.polygon.intersection(result.projection).area < 1e-6
    assert found.polygon.area == pytest.approx(spec.area_m2, abs=0.01)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(x=st.floats(min_value=3.0, max_value=5.0), y=st.floats(min_value=5.0, max_value=18.0))
def test_property_sealed_plus_unsealed_is_the_site_area(x: float, y: float) -> None:
    design, _ = design_for("confort", ("terrasse", "carport_1"), origin=(x, y))
    areas = design.areas
    assert areas is not None
    assert areas.sealed_m2 + areas.unsealed_m2 == pytest.approx(areas.site_m2, abs=0.02)
    assert areas.emprise_m2 <= areas.sealed_m2 + 1e-6


def test_carport_is_only_placed_where_its_driveway_does_not_cross_the_house() -> None:
    """Hinter dem Haus ist mit den Abständen des Hauptbaus Platz, aber die Zufahrt liefe durch das Haus: der
    Carport steht deshalb neben dem Haus an der Straße (ohne diese Abstände) und die Zufahrt bleibt frei."""
    narrow = rectangle(14.0, 31.0)
    ctx = context(
        site_input=site(polygon=narrow, edges=edges_of_rectangle(14.0, 31.0)), zones=[zone(polygon=narrow)]
    )
    the_house = house(width=8.0, depth=6.0)
    placement = Placement(origin=(3.0, 20.0), rotation_deg=0.0)
    projection = check_placement(the_house, placement, ctx, {}).projection
    spec = CarportSpec("schmal", 1, 2.4, 5.0, 2.7)
    found = place_carport(spec, ctx, projection)
    assert found is not None and found.setback == "relaxed"
    assert found.polygon.intersection(projection).area == pytest.approx(0.0, abs=1e-9)
    from app.configuration.domain.outbuildings import carport_driveway

    drive = carport_driveway(found, ctx.edges[2].geometry)
    assert drive.polygon.intersection(projection).area == pytest.approx(0.0, abs=1e-9)
    assert found.polygon.centroid.y > 20.0  # nicht hinter dem Haus, sondern auf Höhe der Straßenfassade


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    x=st.floats(min_value=3.0, max_value=8.0),
    y=st.floats(min_value=6.0, max_value=20.0),
    rotation=st.sampled_from([0.0, 90.0, 180.0, 270.0]),
)
def test_property_carport_and_driveway_avoid_house_and_terrace(x: float, y: float, rotation: float) -> None:
    """Im Browser überlappten sich Carport und Terrasse (Plan H3 10.1a Nr. 16): kein Nebenbau überdeckt einen
    anderen."""
    design, _ = design_for("confort", ("terrasse", "carport_1"), origin=(x, y), rotation=rotation)
    if design.carport is None or design.terrace is None:
        return
    assert design.carport.polygon.intersection(design.terrace).area < 1e-6
    for drive in design.driveways:
        assert drive.polygon.intersection(design.terrace).area < 1e-6
    body = place(house().facade, (x, y), rotation)
    assert design.carport.polygon.intersection(body).area < 1e-6
    for drive in design.driveways:
        assert drive.polygon.intersection(body).area < 1e-6
