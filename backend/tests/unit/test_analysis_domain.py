"""Reine Fachlogik der Analyse (AN3, docs/PLAN_AN3_ANALYSE.md 3): Grundfläche, Geschosse, Nutzfläche,
Vergleich der Zusatzdokumente. Grundstück wie in G3: 20 × 31 m mit den Regeln der Zone UB."""

from dataclasses import replace

import pytest

from app.analysis.domain.analyse import Analysis, SupplementInput, analyse, round_m2
from app.analysis.domain.compare import compare, compare_rule, stricter_kinds
from app.analysis.domain.floor_area import part_floor_area
from app.analysis.domain.footprint import Footprint
from app.analysis.domain.parameters import DEFAULTS, Parameters, Span
from app.analysis.domain.storeys import storeys_for
from app.envelope.domain.derive import derive_envelope
from app.envelope.domain.inputs import EnvelopeInput, RuleInput
from tests.envelope_support import edges_of_rectangle, envelope_input, rectangle, rule, site, ub_rules, zone


def _with(rules: list[RuleInput], kind: str, replacement: RuleInput | None) -> list[RuleInput]:
    kept = [r for r in rules if r.kind != kind]
    return [*kept, replacement] if replacement is not None else kept


def _run(
    rules: list[RuleInput] | None = None,
    *,
    width: float = 20.0,
    depth: float = 31.0,
    params: Parameters = DEFAULTS,
    supplements: list[SupplementInput] | None = None,
    zone_status: str = "simulated",
) -> Analysis:
    outline = rectangle(width, depth)
    data = envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(width, depth)),
        zones=[zone(polygon=outline, rules=rules if rules is not None else ub_rules(), status=zone_status)],
    )
    return analyse(data, derive_envelope(data), params, supplements or [])


# ---------------------------------------------------------------------------
# Bindende Grundfläche (3.1)
# ---------------------------------------------------------------------------


def test_ratio_binds_when_it_is_smaller_than_the_contour() -> None:
    result = _run()
    part = result.parts[0]
    # 20 × 31 m, Abstände 5/3/5/3 m: Kontur 14 × 21 = 294 m²; 40 % von 620 m² = 248 m²
    assert {c.source: c.value_m2 for c in part.footprint["strict"].candidates} == {
        "contour": 294.0,
        "ratio": 248.0,
    }
    assert part.footprint["strict"].binding == "ratio"
    assert result.footprint["strict"].value_m2 == 248.0
    assert result.footprint["lenient"].value_m2 == 248.0
    assert result.footprint["strict"].complete


def test_contour_binds_when_the_ratio_allows_more() -> None:
    result = _run(_with(ub_rules(), "max_footprint_ratio", rule("max_footprint_ratio", {"ratio": 0.6})))
    footprint = result.parts[0].footprint["lenient"]
    assert (footprint.value_m2, footprint.binding) == (294.0, "contour")


def test_absolute_footprint_cap_from_max_area() -> None:
    rules = [*ub_rules(), rule("max_area", {"footprint_m2": 200.0}, building_kind="any")]
    footprint = _run(rules).parts[0].footprint["strict"]
    assert (footprint.value_m2, footprint.binding) == (200.0, "absolute")


def test_missing_ratio_leaves_an_upper_bound() -> None:
    result = _run(_with(ub_rules(), "max_footprint_ratio", None))
    footprint = result.parts[0].footprint["strict"]
    assert (footprint.value_m2, footprint.binding) == (294.0, "contour")
    assert not footprint.complete
    assert footprint.reasons == ["footprint_ratio_unknown"]
    assert not result.footprint["strict"].complete


def test_not_regulated_ratio_is_a_complete_answer() -> None:
    not_regulated = rule("max_footprint_ratio", status="not_regulated")
    footprint = _run(_with(ub_rules(), "max_footprint_ratio", not_regulated)).parts[0].footprint["strict"]
    assert (footprint.value_m2, footprint.binding, footprint.complete) == (294.0, "contour", True)


def test_no_figures_while_the_rules_are_evaluated() -> None:
    result = _run(zone_status="in_progress")
    assert result.status == "in_progress"
    assert result.parts == [] and result.floor_area is None


# ---------------------------------------------------------------------------
# Vollgeschosse (3.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"storeys": "R+1+C", "eave_m": 6.0}, (2, 2, "attic", True, "storeys")),
        ({"storeys": "R+2+A"}, (3, 3, "attique", True, "storeys")),
        ({"storeys": "R"}, (1, 1, "none", False, "storeys")),
        ({"eave_m": 7.0, "ridge_m": 10.0}, (2, 2, "attic", False, "eave")),
        ({"eave_m": 8.2, "ridge_m": 11.0}, (2, 3, "attic", False, "eave")),
        ({"eave_m": 6.0, "ridge_m": 7.0}, (2, 2, "none", False, "eave")),
        ({"parapet_m": 9.0}, (3, 3, "none", False, "parapet")),
        ({"ridge_m": 10.0}, (1, 3, "none", False, "ridge")),
    ],
)
def test_storeys_from_the_height_rule(params: dict[str, object], expected: tuple[object, ...]) -> None:
    storeys = storeys_for(rule("max_height", params), DEFAULTS)
    assert (
        storeys.full_min,
        storeys.full_max,
        storeys.top,
        storeys.top_certain,
        storeys.source,
    ) == expected


def test_storeys_are_counted_from_the_text_not_from_derived_heights() -> None:
    """`R+1+C` mit einer Traufe von 5 m: Zwei Geschosse gehen nur mit 2,50 m – das wird gemeldet."""
    storeys = storeys_for(rule("max_height", {"storeys": "R+1+C", "eave_m": 5.0}), DEFAULTS)
    assert (storeys.full_min, storeys.source) == (2, "storeys")
    assert storeys.notes == ["storeys_exceed_eave"]


def test_storeys_unknown_without_an_effective_height_rule() -> None:
    assert storeys_for(None, DEFAULTS).source == "unknown"
    unknown = storeys_for(rule("max_height", status="unknown", reason="missing"), DEFAULTS)
    assert (unknown.full_min, unknown.status) == (None, "unknown")


def test_six_metres_are_two_storeys_of_three_metres() -> None:
    """Gleitkomma: 6,00 / 3,00 darf nicht knapp unter 2 fallen."""
    storeys = storeys_for(rule("max_height", {"eave_m": 6.0}), Parameters(storey_height_m=Span(3.0, 3.0)))
    assert (storeys.full_min, storeys.full_max) == (2, 2)


# ---------------------------------------------------------------------------
# Nutzfläche (3.3)
# ---------------------------------------------------------------------------


def test_floor_area_span_of_zone_ub() -> None:
    """248 m² × (2 + 0,50) × 0,85 = 527 m²; 248 m² × (2 + 0,75) × 0,92 = 627,44 m²."""
    result = _run()
    assert result.floor_area is not None
    assert (result.floor_area.low_m2, result.floor_area.high_m2) == (527, 627)
    assert result.floor_area.complete and not result.floor_area.capped


def test_floor_area_of_the_plan_example() -> None:
    """PLAN_AN3 3.3: 20 × 30 m, GRZ 25 %, Traufe 7 m, First 10 m → 255 bis 380 m²."""
    rules = _with(ub_rules(), "max_footprint_ratio", rule("max_footprint_ratio", {"ratio": 0.25}))
    rules = _with(rules, "max_height", rule("max_height", {"eave_m": 7.0, "ridge_m": 10.0}))
    result = _run(rules, depth=30.0)
    assert result.footprint["strict"].value_m2 == 150.0
    assert result.floor_area is not None
    assert (result.floor_area.low_m2, result.floor_area.high_m2) == (255, 380)


def test_sdp_cap_binds_both_ends() -> None:
    rules = [*ub_rules(), rule("max_area", {"sdp_m2": 200.0}, building_kind="any")]
    result = _run(rules)
    part = result.parts[0].floor_area
    assert (part.low_m2, part.high_m2, part.cap_m2, part.capped) == (200.0, 200.0, 200.0, True)
    assert result.floor_area is not None and result.floor_area.capped


def test_floor_area_needs_a_height() -> None:
    result = _run(_with(ub_rules(), "max_height", None))
    assert result.floor_area is not None
    assert result.floor_area.low_m2 is None
    assert "height_unknown" in result.floor_area.reasons


def test_assumptions_change_the_span() -> None:
    params = Parameters(storey_height_m=Span(3.0, 3.0), wall_share=Span(0.1, 0.1), attic_share=Span(0.6, 0.6))
    result = _run(params=params)
    assert result.floor_area is not None
    # 248 × 2,6 × 0,9 = 580,32
    assert (result.floor_area.low_m2, result.floor_area.high_m2) == (580, 580)


def test_possible_attic_counts_only_at_the_upper_end() -> None:
    storeys = storeys_for(rule("max_height", {"eave_m": 7.0, "ridge_m": 10.0}), DEFAULTS)
    footprint = Footprint(100.0, "ratio", True)
    floor = part_floor_area(footprint, footprint, storeys, None, DEFAULTS)
    assert (floor.low_m2, floor.high_m2) == (170.0, 253.0)


def test_rounding_is_half_up() -> None:
    assert round_m2(379.49999999999997) == 380
    assert round_m2(378.5) == 379


def test_parameters_round_trip_and_defaults_for_missing_entries() -> None:
    params = Parameters(wall_share=Span(0.1, 0.2))
    assert Parameters.from_json(params.as_json()) == params
    assert Parameters.from_json({"wall_share": [0.1, 0.2]}) == params
    assert Parameters.from_json(None) == DEFAULTS


# ---------------------------------------------------------------------------
# Vergleich mit Zusatzdokumenten (3.8)
# ---------------------------------------------------------------------------


def _verdict(supplement: RuleInput, plu: RuleInput | None) -> str:
    return compare_rule(supplement, plu).verdict


def test_lower_height_in_the_supplement_is_stricter() -> None:
    plu = rule("max_height", {"ridge_m": 9.0, "eave_m": 6.0})
    assert _verdict(rule("max_height", {"ridge_m": 8.0}), plu) == "stricter"
    assert _verdict(rule("max_height", {"ridge_m": 10.0}), plu) == "looser"
    assert _verdict(rule("max_height", {"ridge_m": 9.0}), plu) == "equal"
    assert _verdict(rule("max_height", {"ridge_m": 8.0, "eave_m": 7.0}), plu) == "mixed"


def test_directions_of_minimums_sets_and_permissions() -> None:
    side = rule("setback_side", {"min_m": 3.0, "allow_on_boundary": False, "measured_from": "facade"})
    assert _verdict(replace(side, params={**side.params, "min_m": 4.0}), side) == "stricter"
    assert _verdict(replace(side, params={**side.params, "allow_on_boundary": True}), side) == "looser"
    assert _verdict(replace(side, params={**side.params, "measured_from": "roof_edge"}), side) == "different"
    roof = rule("roof", {"allowed_forms": ["gable", "hip"]})
    assert _verdict(rule("roof", {"allowed_forms": ["gable"]}), roof) == "stricter"
    assert _verdict(rule("roof", {"allowed_forms": ["gable", "hip", "flat"]}), roof) == "looser"
    assert _verdict(rule("roof", {"allowed_forms": ["flat"]}), roof) == "different"
    facade = rule("facade", {"materials_forbidden": ["metal"]})
    assert _verdict(rule("facade", {"materials_forbidden": ["metal", "wood"]}), facade) == "stricter"
    assert (
        _verdict(rule("max_height", {"storeys": "R+1"}), rule("max_height", {"storeys": "R+1+C"}))
        == "stricter"
    )


def test_extra_parameter_in_the_supplement_restricts() -> None:
    plu = rule("max_height", {"ridge_m": 9.0})
    assert _verdict(rule("max_height", {"ridge_m": 9.0, "eave_m": 6.0}), plu) == "stricter"


def test_status_combinations() -> None:
    area = rule("max_area", {"sdp_m2": 180.0}, building_kind="any")
    assert _verdict(area, None) == "only_supplement"
    assert _verdict(area, rule("max_area", status="unknown")) == "only_supplement"
    street = rule("setback_street", {"min_m": 5.0, "mode": "min"})
    assert _verdict(street, rule("setback_street", status="not_regulated")) == "stricter"
    # „Non réglementé“ im Zusatzdokument: der PLU gilt, nicht 0 m
    assert _verdict(rule("setback_street", status="not_regulated"), street) == "no_own_rule"
    assert _verdict(rule("setback_street", status="unknown", reason="quote_unverified"), street) == "unknown"


def test_compare_uses_the_general_plu_rule_and_skips_hints() -> None:
    plu = [rule("setback_street", {"min_m": 5.0, "mode": "min"}, building_kind="any")]
    supplement = [
        rule("setback_street", {"min_m": 6.0, "mode": "min"}),
        rule("text_only", {"summary": "Servitude de vue"}, status="text_only"),
    ]
    comparisons = compare(supplement, plu)
    assert [(c.kind, c.verdict) for c in comparisons] == [("setback_street", "stricter")]
    assert comparisons[0].plu is not None and comparisons[0].plu.building_kind == "any"


def test_stricter_kinds_only_for_the_figures() -> None:
    comparisons = compare(
        [
            rule("max_height", {"ridge_m": 8.0}),
            rule("fence", {"max_height_m": 1.2}, building_kind="any"),
            rule("max_area", {"sdp_m2": 180.0}, building_kind="any"),
        ],
        ub_rules(),
    )
    assert stricter_kinds(comparisons) == ["max_area", "max_height"]


def test_analysis_reports_stricter_supplements_without_changing_its_figures() -> None:
    supplement = SupplementInput(
        document_id="00000000-0000-0000-0000-000000000001",
        title="Règlement du lotissement",
        du_type="lotissement",
        lot="Lot-12",
        status="simulated",
        reason=None,
        rules=[rule("max_area", {"sdp_m2": 180.0}, building_kind="any")],
    )
    result = _run(supplements=[supplement])
    assert result.supplement_stricter == ["max_area"]
    assert result.warnings == ["supplement_stricter"]
    assert result.floor_area is not None and result.floor_area.high_m2 == 627


def test_supplement_without_rules_yet_is_listed_without_comparison() -> None:
    waiting = SupplementInput("id", "Cahier", "cahier_des_charges", None, "unavailable", "lot_not_chosen")
    result = _run(supplements=[waiting])
    assert result.supplements[0].comparisons == []
    assert result.supplement_stricter == []


def test_without_envelope_the_analysis_is_unavailable() -> None:
    data = EnvelopeInput(site=site(), rules_status="unavailable", rules_reason="upload")
    result = analyse(data, None, DEFAULTS, [])
    assert (result.status, result.reason, result.parts) == ("unavailable", "upload", [])
