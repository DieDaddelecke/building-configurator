"""Gabarit und Schnitt (AN3, docs/PLAN_AN3_GABARIT.md): Abstand je Höhenstufe, Stufen, Nutzfläche je Geschoss,
Schnitte. Grundstück wie in G3: 20 × 31 m, Straße im Norden, Nachbarn Ost und West."""

import pytest

from app.analysis.domain.analyse import Analysis, analyse
from app.analysis.domain.parameters import DEFAULTS, Parameters, Span
from app.envelope.domain.derive import contour_at_height, derive_envelope
from app.envelope.domain.heights import Heights
from app.envelope.domain.inputs import EnvelopeInput, RuleInput
from app.envelope.domain.setbacks import Setback, at_height
from tests.envelope_support import edges_of_rectangle, envelope_input, rectangle, rule, site, ub_rules, zone

SIDE = {
    "min_m": 3.0,
    "height_factor": 0.5,
    "height_basis": "eave",
    "allow_on_boundary": True,
    "on_boundary_max_height_m": 3.5,
}


def example_rules(*, ratio: float = 0.6, height: dict[str, object] | None = None) -> list[RuleInput]:
    """Beispiel aus PLAN_AN3_GABARIT 3.2: Seiten H/2 an der Traufe, mindestens 3 m, auf der Grenze bis 3,5 m
    Höhe."""
    rules = [
        rule("setback_street", {"min_m": 5.0, "mode": "min"}),
        rule("setback_side", dict(SIDE)),
        rule("setback_rear", {"min_m": 5.0}),
        rule("max_footprint_ratio", {"ratio": ratio}),
    ]
    if height is not None:
        rules.append(rule("max_height", height))
    return rules


EXAMPLE_HEIGHT = {"eave_m": 7.0, "ridge_m": 10.0}


def uh_rules() -> list[RuleInput]:
    """Zone Uh des Testreglements (tests/rules_support.uh_output)."""
    return [
        rule("setback_street", {"mode": "range", "min_m": 5, "max_m": 20, "band": "building"}),
        rule("setback_side", {"min_m": 3, "allow_on_boundary": True}),
        rule("setback_rear", {"min_m": 3, "allow_on_boundary": True}),
        rule("max_footprint_ratio", {"ratio": 0.25}),
        rule("max_height", {"eave_m": 7, "ridge_m": 10}),
    ]


def _data(rules: list[RuleInput], *, width: float = 20.0, depth: float = 31.0) -> EnvelopeInput:
    outline = rectangle(width, depth)
    return envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(width, depth)),
        zones=[zone(polygon=outline, rules=rules)],
    )


def _analysis(rules: list[RuleInput], params: Parameters = DEFAULTS, **size: float) -> Analysis:
    data = _data(rules, **size)
    return analyse(data, derive_envelope(data), params, [])


# ---------------------------------------------------------------------------
# Abstand je Stufe (3.1)
# ---------------------------------------------------------------------------


def _side(params: dict[str, object], status: str = "effective") -> Setback:
    return Setback(
        zone_code="UB",
        kind="setback_side",
        building_kind="main",
        status=status,
        reason=None,
        lenient_m=None,
        strict_m=None,
        params=params,
    )


@pytest.mark.parametrize(
    ("height", "lenient", "strict"),
    [(3.5, 0.0, 3.0), (3.6, 3.0, 3.0), (6.5, 3.25, 3.25), (7.0, 3.5, 3.5), (9.0, 3.5, 3.5)],
)
def test_distance_for_a_level(height: float, lenient: float, strict: float) -> None:
    result = at_height(_side(dict(SIDE)), Heights(eave_m=7.0, ridge_m=10.0), height)
    assert (result.lenient_m, result.strict_m) == pytest.approx((lenient, strict))


def test_ridge_basis_keeps_growing_above_the_eave() -> None:
    params = {**SIDE, "height_basis": "ridge", "allow_on_boundary": False}
    result = at_height(_side(params), Heights(eave_m=7.0, ridge_m=10.0), 9.0)
    assert (result.lenient_m, result.strict_m) == (4.5, 4.5)


def test_street_and_unknown_distances_stay() -> None:
    street = Setback("UB", "setback_street", "main", "effective", None, 5.0, 5.0, {"min_m": 5.0})
    unknown = _side({}, status="unknown")
    heights = Heights(eave_m=7.0)
    assert at_height(street, heights, 6.0) == street
    assert at_height(unknown, heights, 6.0) == unknown


@pytest.mark.parametrize("rules", [ub_rules(), example_rules(height=EXAMPLE_HEIGHT), uh_rules()])
def test_levels_reproduce_both_contours_of_the_envelope(rules: list[RuleInput]) -> None:
    data = _data(rules)
    envelope = derive_envelope(data)
    heights = envelope.parts[0].heights
    top = heights.for_basis("eave")
    assert top is not None
    strict = contour_at_height(data, envelope, top, "strict")
    lenient = contour_at_height(data, envelope, 0.0, "lenient")
    assert strict.area_m2 == envelope.contours["strict"].area_m2
    assert lenient.area_m2 == envelope.contours["lenient"].area_m2


def test_nothing_above_the_maximum_height() -> None:
    data = _data(example_rules(height=EXAMPLE_HEIGHT))
    envelope = derive_envelope(data)
    assert contour_at_height(data, envelope, 10.0, "lenient").area_m2 == 273.0
    assert contour_at_height(data, envelope, 10.5, "lenient").geometry.is_empty


# ---------------------------------------------------------------------------
# Stufen (3.2)
# ---------------------------------------------------------------------------


def _levels(result: Analysis) -> list[tuple[float, float, float, float, bool]]:
    assert result.gabarit is not None
    return [
        (
            level.from_m,
            level.to_m,
            level.contours["lenient"].area_m2,
            level.contours["strict"].area_m2,
            level.roof,
        )
        for level in result.gabarit.levels
    ]


def test_levels_of_the_plan_example() -> None:
    result = _analysis(example_rules(height=EXAMPLE_HEIGHT))
    assert _levels(result) == [
        (0.0, 3.5, 420.0, 294.0, False),
        (3.5, 6.0, 294.0, 294.0, False),
        (6.0, 7.0, 273.0, 273.0, False),
        (7.0, 10.0, 273.0, 273.0, True),
    ]
    assert result.gabarit is not None
    assert (result.gabarit.status, result.gabarit.top_m, result.gabarit.storey_height_m) == ("ok", 10.0, None)


def test_gabarit_confirms_the_envelope_without_height_dependent_rules() -> None:
    result = _analysis(uh_rules(), depth=30.0)
    assert _levels(result) == [(0.0, 7.0, 300.0, 210.0, False), (7.0, 10.0, 300.0, 210.0, True)]
    assert result.floor_area is not None
    assert (result.floor_area.low_m2, result.floor_area.high_m2) == (255, 380)
    assert result.parts[0].floor_area.notes == []


def test_storeys_only_are_converted_with_the_storey_height_of_the_assumptions() -> None:
    params = Parameters(storey_height_m=Span(3.5, 3.5))
    result = _analysis(example_rules(height={"storeys": "R+1+C"}), params)
    assert result.gabarit is not None
    assert (result.gabarit.top_m, result.gabarit.storey_height_m) == (12.0, 3.5)
    assert result.gabarit.heights["UB"].eave_m == 7.0
    floor = result.parts[0].floor_area
    # zwei Vollgeschosse an beiden Enden, keins fällt über der umgerechneten Traufe weg
    assert [s.level_m for s in floor.storeys_low if s.share == 1.0] == [3.5, 7.0]
    assert [s.level_m for s in floor.storeys_high if s.share == 1.0] == [3.5, 7.0]


def test_without_height_there_is_no_gabarit() -> None:
    result = _analysis(example_rules())
    assert result.gabarit is not None
    assert (result.gabarit.status, result.gabarit.reason, result.gabarit.levels) == (
        "unavailable",
        "height_unknown",
        [],
    )
    assert result.sections == []
    floor = result.parts[0].floor_area
    assert (floor.low_m2, floor.high_m2) == (None, None) and "height_unknown" in floor.reasons


# ---------------------------------------------------------------------------
# Nutzfläche je Geschoss (3.4)
# ---------------------------------------------------------------------------


def test_floor_area_of_the_plan_example_is_limited_by_the_gabarit() -> None:
    result = _analysis(example_rules(height=EXAMPLE_HEIGHT))
    floor = result.parts[0].floor_area
    # oben (372 + 294 + 0,75 × 294) × 0,92 = 815,58 statt 372 × 2,75 × 0,92 = 941; unten 2 × 273 × 0,85
    assert (floor.low_m2, floor.high_m2) == (464.1, 815.58)
    assert [(s.level_m, s.area_m2, s.share) for s in floor.storeys_high] == [
        (2.7, 372.0, 1.0),
        (5.4, 294.0, 1.0),
        (5.4, 294.0, 0.75),
    ]
    low = [(s.level_m, s.area_m2, s.share) for s in floor.storeys_low]
    assert low == [(3.0, 273.0, 1.0), (6.0, 273.0, 1.0)]
    assert floor.notes == ["gabarit_limits_storeys"]
    assert result.floor_area is not None
    assert (result.floor_area.low_m2, result.floor_area.high_m2) == (464, 816)


def test_storeys_above_the_maximum_height_count_nowhere() -> None:
    """`R+2` bei 7 m Traufe: Das dritte Geschoss (8,10 bzw. 9,00 m) liegt über der Höchsthöhe."""
    result = _analysis(example_rules(ratio=0.3, height={"storeys": "R+2", "eave_m": 7.0}))
    floor = result.parts[0].floor_area
    assert "storeys_exceed_eave" in result.parts[0].storeys.notes
    assert [s.area_m2 for s in floor.storeys_low] == [186.0, 186.0, 0.0]
    assert floor.low_m2 is not None and floor.high_m2 is not None
    assert floor.low_m2 <= floor.high_m2


# ---------------------------------------------------------------------------
# Schnitte (3.3)
# ---------------------------------------------------------------------------


def test_section_a_runs_from_the_street_to_the_rear() -> None:
    result = _analysis(example_rules(height=EXAMPLE_HEIGHT))
    section = next(s for s in result.sections if s.key == "A")
    assert section.length_m == 31.0 and section.parcel == [(0.0, 31.0)]
    assert [(c.s, c.edge_seq, c.kind, c.inward) for c in section.crossings] == [
        (0.0, 3, "street", 1),
        (31.0, 1, "rear", -1),
    ]
    assert {level.intervals["strict"][0] for level in section.levels} == {(5.0, 26.0)}
    assert [(line.kind, line.height_m) for line in section.height_lines] == [("eave", 7.0), ("ridge", 10.0)]
    street = next(p for p in section.prospects if p.edge_seq == 3 and p.reading == "strict")
    assert street.points == [(5.0, 0.0), (5.0, 10.0)]


def test_section_b_shows_the_steps_and_the_prospect_of_the_sides() -> None:
    result = _analysis(example_rules(height=EXAMPLE_HEIGHT))
    section = next(s for s in result.sections if s.key == "B")
    assert section.length_m == 20.0
    assert [c.kind for c in section.crossings] == ["side", "side"]
    lenient = [(level.from_m, level.intervals["lenient"]) for level in section.levels]
    assert lenient == [
        (0.0, [(0.0, 20.0)]),
        (3.5, [(3.0, 17.0)]),
        (6.0, [(3.5, 16.5)]),
        (7.0, [(3.5, 16.5)]),
    ]
    first = section.crossings[0]
    prospect = next(p for p in section.prospects if p.edge_seq == first.edge_seq and p.reading == "lenient")
    assert prospect.points == [(0.0, 0.0), (0.0, 3.5), (3.0, 3.501), (3.0, 6.0), (3.5, 7.0), (3.5, 10.0)]
    strict = next(p for p in section.prospects if p.edge_seq == first.edge_seq and p.reading == "strict")
    assert strict.points == [(3.0, 0.0), (3.0, 6.0), (3.5, 7.0), (3.5, 10.0)]
