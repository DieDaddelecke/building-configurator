"""Hausbeschreibung des Kerns auf dem Grundstück (docs/PLAN_HAUSMODELL.md 3.1, 3.7; HM4, HM5): Abbildung
auf `HouseType`, Dachformen in den Begriffen der PLU-Regeln, Ergebnisarten und Status, Rundung der
Kundenpreise und die Grundstücksszenarien P 19.6/19.7.

Die Hausbeschreibungen stammen aus dem Kern selbst (`evaluations.json` der Testdaten des Demohauses,
`pnpm run evaluations`). Das Demo-PLU aus P 19.6 nennt für Überbauung und Grenzabstand das Ergebnis „Warnung“;
nach 3.7 ist die Verletzung einer wirksamen Regel eine Abweichung (E-HM-6).
"""

from functools import cache
from typing import Any

import pytest
from shapely.geometry import Point, Polygon

from app.configuration.domain.checks import FAIL, HINT, PASS, UNKNOWN, Check
from app.configuration.domain.compliance import MaterialSubject
from app.configuration.domain.context import SiteContext
from app.configuration.domain.facts import FactsError, house_type, outbuilding_specs, storeys_text
from app.configuration.domain.geometry import turn
from app.configuration.domain.house import HouseType
from app.configuration.domain.outcomes import combined_status, round_amount, site_outcome
from app.configuration.domain.placement import Placement, check_placement
from app.configuration.domain.rotations import candidate_rotations
from app.configuration.domain.site_check import SiteCheck, evaluate_site, placement_surfaces
from app.envelope.domain.inputs import RuleInput
from app.house.contract import HouseEvaluation, HouseFacts, HousePoint
from tests.configuration_support import context
from tests.envelope_support import edges_of_rectangle, rule, site, zone
from tests.house_support import fixture

SITE = (18.0, 12.0)
"""Grundstück P 19.6: 18 × 12 m, Straße im Norden (Kanten: 1 hinten, 2 und 4 seitlich, 3 Straße)."""


@cache
def _evaluations() -> dict[str, Any]:
    return fixture("evaluations")


def facts(case: str = "standard") -> HouseFacts:
    return HouseEvaluation.model_validate(_evaluations()[case]["evaluation"]).facts


def demo(case: str = "standard") -> HouseType:
    return house_type(
        facts(case), slug="demo_house", version=1, version_id="v1", name="Maison de démonstration"
    )


def materials(case: str = "standard") -> list[MaterialSubject]:
    found = facts(case)
    return [
        MaterialSubject(
            "house",
            "demo_house",
            {"facade_material": found.facade_material_class, "roof_material": found.roof_material_class},
        )
    ]


def demo_plu(
    *,
    ratio: float = 0.55,
    street: float = 1.5,
    other: float = 1.5,
    roof: RuleInput | None = None,
    height: RuleInput | None = None,
    extra: tuple[RuleInput, ...] = (),
    size: tuple[float, float] = SITE,
) -> SiteContext:
    """Demo-PLU P 19.6: Überbauung höchstens 55 %, Grenzabstände mindestens 1,50 m; Dach, Höhe und
    unversiegelte Fläche ungeregelt, damit nur diese Regeln zählen."""
    polygon = Polygon([(0.0, 0.0), (size[0], 0.0), (size[0], size[1]), (0.0, size[1])])
    rules = [
        rule("setback_street", {"min_m": street, "mode": "min", "measured_from": "facade"}),
        rule("setback_side", {"min_m": other, "allow_on_boundary": False, "measured_from": "facade"}),
        rule("setback_rear", {"min_m": other, "allow_on_boundary": False, "measured_from": "facade"}),
        rule("max_footprint_ratio", {"ratio": ratio}),
        roof or rule("roof", status="not_regulated"),
        height or rule("max_height", status="not_regulated"),
        rule("unsealed_min", status="not_regulated"),
        *extra,
    ]
    return context(
        site_input=site(polygon=polygon, edges=edges_of_rectangle(*size)),
        zones=[zone(polygon=polygon, rules=rules)],
    )


def centred(house: HouseType, ctx: SiteContext, size: tuple[float, float] = SITE) -> Placement:
    """Haus mittig, Straßenfassade zur Straße: die Längsseite liegt parallel zur 18-m-Seite (P 19.6)."""
    rotation = candidate_rotations(house, ctx)[0]
    centre = turn(house.facade, rotation).centroid
    return Placement(
        origin=(size[0] / 2 - float(centre.x), size[1] / 2 - float(centre.y)), rotation_deg=rotation
    )


def outcomes(result: SiteCheck) -> dict[str, str]:
    return {c.code: outcome for c in result.checks if (outcome := site_outcome(c)) is not None}


# --- Hausbeschreibung → HouseType -------------------------------------------------------------------------


def test_facts_become_a_house_type_measured_above_terrain() -> None:
    found = facts()
    house = demo()
    assert house.storeys == "R"
    assert house.roof_form == "flat"
    assert house.pitch_deg is None and house.ridge_direction is None
    # Höhen über Gelände: über ±0,00 plus Erdgeschoss über Gelände (E-HM-11)
    assert house.ridge_height_m == pytest.approx(found.top_height + 0.2)
    assert house.eave_height_m == pytest.approx(found.eave_height + 0.2)
    assert round(house.facade.area, 2) == 110.92
    min_x, min_y, max_x, max_y = house.facade.bounds
    assert (round(max_x - min_x, 2), round(max_y - min_y, 2)) == (12.72, 8.72)
    # Kanten des Fassadenumrisses gegen den Uhrzeigersinn: Süd, Ost, Nord, West wie die Segmente
    assert house.facade_roles == {0: "street", 1: "side_right", 2: "garden", 3: "side_left"}
    assert house.living_area_m2 == round(found.floor_area, 2)


@pytest.mark.parametrize(("case", "size"), [("brick", (12.96, 8.96)), ("wood", (12.88, 8.88))])
def test_wall_profile_changes_the_outline(case: str, size: tuple[float, float]) -> None:
    min_x, min_y, max_x, max_y = demo(case).facade.bounds
    assert (round(max_x - min_x, 2), round(max_y - min_y, 2)) == size


def test_clockwise_or_broken_outline_is_outside_the_contract() -> None:
    found = facts()
    with pytest.raises(FactsError):
        house_type(
            found.model_copy(update={"facade_outline": list(reversed(found.facade_outline))}),
            slug="demo_house",
            version=1,
            version_id="v1",
            name="Demo",
        )
    bow_tie = [HousePoint(x=0, y=0), HousePoint(x=2, y=2), HousePoint(x=2, y=0), HousePoint(x=0, y=2)]
    with pytest.raises(FactsError):
        house_type(
            found.model_copy(update={"facade_outline": bow_tie}),
            slug="demo_house",
            version=1,
            version_id="v1",
            name="Demo",
        )


@pytest.mark.parametrize(("storeys", "text"), [(1, "R"), (2, "R+1"), (3, "R+2")])
def test_storeys_in_the_notation_of_the_rules(storeys: int, text: str) -> None:
    assert storeys_text(storeys) == text


@pytest.mark.parametrize(
    ("case", "form", "readings", "pitch", "pitches", "direction"),
    [
        ("r1_standard", "gable", (), 35.0, (), "laengs"),
        ("r1_turned", "gable", (), 35.0, (), "quer"),
        ("r1_hip", "hip", (), 30.0, (), "laengs"),
        ("r1_half_hip", "half_hip", ("gable", "hip", "other"), None, (40.0, 60.0), "laengs"),
        ("r1_mansard", "mansard", (), None, (25.0, 70.0), "laengs"),
    ],
)
def test_roof_forms_of_the_core_in_the_terms_of_the_rules(
    case: str,
    form: str,
    readings: tuple[str, ...],
    pitch: float | None,
    pitches: tuple[float, ...],
    direction: str,
) -> None:
    """E-HM-61: Form des Kerns → Begriff der PLU-Regeln (Krüppelwalm mit seinen Lesarten), eine Neigung nur
    bei gleich geneigten Flächen, Firstachse des Kerns → längs oder quer zum Umriss."""
    house = demo(case)
    assert house.storeys == "R+1"
    assert (house.roof_form, house.roof_form_readings) == (form, readings)
    assert (house.pitch_deg, house.roof_pitches_deg) == (pitch, pitches)
    assert house.ridge_direction == direction


# --- Ergebnisarten, Status, Rundung (3.7, 3.8) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "binding", "outcome"),
    [
        (FAIL, True, "deviation"),
        (FAIL, False, "warning"),
        (UNKNOWN, False, "warning"),
        (HINT, False, "info"),
        (PASS, True, None),
        ("not_applicable", True, None),
    ],
)
def test_outcome_of_a_site_check(status: str, binding: bool, outcome: str | None) -> None:
    assert site_outcome(Check(code="x", kind="x", status=status, binding=binding)) == outcome


@pytest.mark.parametrize(
    ("catalog", "found", "status"),
    [
        ("valid", [], "valid"),
        ("valid", ["info"], "valid"),
        ("valid", ["warning", "info"], "valid_with_warnings"),
        ("valid_with_warnings", [], "valid_with_warnings"),
        ("valid_with_warnings", ["deviation"], "with_deviations"),
        ("blocked", ["deviation"], "blocked"),
        ("valid", ["deviation", "warning"], "with_deviations"),
    ],
)
def test_status_order(catalog: str, found: list[str], status: str) -> None:
    assert combined_status(catalog, found) == status


@pytest.mark.parametrize(
    ("value", "step", "rounded"),
    [
        (515_194.2144, 1000, 515_000.0),
        (523_547.5584, 1000, 524_000.0),
        (500.0, 1000, 1000.0),
        (499.99, 1000, 0.0),
        (8_353.344, 100, 8_400.0),
        (9_741.864, 100, 9_700.0),
        (-777.6, 100, -800.0),
        (-50.0, 100, -100.0),
        (-49.99, 100, 0.0),
        (0.0, 100, 0.0),
    ],
)
def test_customer_amounts_round_half_away_from_zero(value: float, step: float, rounded: float) -> None:
    result = round_amount(value, step)
    assert result == rounded
    assert str(result) != "-0.0"


# --- Grundstücksszenarien P 19.6/19.7 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "near", "far", "coverage"),
    [("standard", 1.64, 2.64, 51.35), ("brick", 1.52, 2.52, 53.76), ("wood", 1.56, 2.56, 52.95)],
)
def test_site_scenarios_of_p19_7(case: str, near: float, far: float, coverage: float) -> None:
    house, ctx = demo(case), demo_plu()
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials(case))
    assert result.result is not None and result.areas is not None
    assert {e.seq: round(e.measured_m, 2) for e in result.result.edges} == {1: near, 2: far, 3: near, 4: far}
    assert round(100 * result.areas.emprise_m2 / result.areas.site_m2, 2) == coverage
    assert result.areas.site_m2 == 216.0
    assert "deviation" not in outcomes(result).values()
    assert combined_status("valid", outcomes(result).values()) == "valid"


@pytest.mark.parametrize(("case", "deviates"), [("standard", False), ("wood", True), ("brick", True)])
def test_coverage_limit_of_52_percent(case: str, deviates: bool) -> None:
    """P 20.1: Mit 52 % ist Standard zulässig, Holz (52,95 %) und Ziegel (53,76 %) nicht."""
    house, ctx = demo(case), demo_plu(ratio=0.52)
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials(case))
    footprint = next(c for c in result.checks if c.code == "footprint")
    assert footprint.limit == pytest.approx(112.32)
    assert site_outcome(footprint) == ("deviation" if deviates else None)
    assert combined_status("valid", outcomes(result).values()) == ("with_deviations" if deviates else "valid")
    # Keine Lage behebt die Überbauung: kein Vorschlag, der Typ ist mit dieser Auswahl gesperrt
    assert result.suggestion is None
    assert result.fit.allowed is not deviates


def test_brick_too_close_to_the_street_gets_the_nearest_valid_placement() -> None:
    """Ergänzung 9: Eine Wahl, die die Lage unzulässig macht, wird Abweichung mit Vorschlag."""
    standard, brick, ctx = demo(), demo("brick"), demo_plu(street=1.6, other=1.0)
    placement = centred(standard, ctx)
    assert check_placement(standard, placement, ctx, {}).valid
    # Ziegel an derselben Stelle: Die Fassade wächst um 0,12 m je Seite, zur Straße bleiben 1,52 statt 1,60 m
    result = evaluate_site(brick, placement, ctx, {}, materials("brick"))
    assert result.result is not None and not result.result.valid
    assert outcomes(result)["setback_street"] == "deviation"
    suggestion = result.suggestion
    assert suggestion is not None
    assert suggestion.rotation_deg == placement.rotation_deg
    assert check_placement(brick, suggestion, ctx, {}).valid
    moved = abs(suggestion.origin[0] - placement.origin[0]) + abs(suggestion.origin[1] - placement.origin[1])
    assert moved < 0.2


def test_unplaced_house_is_checked_as_a_type_only() -> None:
    house, ctx = demo(), demo_plu()
    result = evaluate_site(house, None, ctx, {}, materials())
    assert result.result is None and result.areas is None and result.suggestion is None
    assert result.fit.allowed
    assert {c.code for c in result.checks} == {"parking_not_shown"}


def _with_outbuildings(size: tuple[float, float] = SITE) -> SiteCheck:
    house = demo("outbuildings")
    ctx = demo_plu(size=size)
    specs = outbuilding_specs(facts("outbuildings"), house)
    return evaluate_site(house, centred(house, ctx, size), ctx, {}, materials("outbuildings"), *specs)


def test_terrace_and_carport_of_the_house_description_are_placed_and_counted() -> None:
    """Ergänzung 7 (HM5): Maße aus dem Kern, Lage wie im heutigen Konfigurator: Terrasse an der längsten
    Gartenkante, Carport nah an der Straße mit Zufahrt; beide zählen in Überbauung und Versiegelung."""
    result = _with_outbuildings((26.0, 20.0))
    assert result.terrace is not None and result.carport is not None and result.areas is not None
    assert result.terrace.bounds == pytest.approx((6.64, 2.64, 19.36, 5.64))
    assert not result.terrace.intersects(result.carport.polygon)
    assert [(d.source, d.length_m) for d in result.driveways] == [("carport", 1.5)]
    areas = result.areas
    assert (areas.terrace_m2, areas.carport_m2, areas.driveway_m2) == pytest.approx((38.16, 15.0, 4.5))
    assert areas.emprise_m2 == pytest.approx(110.92 + 15.0)
    total = next(c for c in result.checks if c.code == "footprint_total")
    assert (total.status, total.measured) == (PASS, pytest.approx(125.92))
    assert outcomes(result) == {"carport_setback_assumed": "info"}


def test_terrace_and_carport_that_do_not_fit_are_deviations() -> None:
    """Auf 18 × 12 m ragt die Terrasse aus dem Grundstück, und für den Carport gibt es keine Stelle."""
    result = _with_outbuildings()
    assert result.carport is None and result.driveways == ()
    assert outcomes(result) == {"terrace_outside_site": "deviation", "no_valid_position": "deviation"}


def test_placement_surface_contains_the_centred_placement() -> None:
    house, ctx = demo(), demo_plu()
    placement = centred(house, ctx)
    surfaces = placement_surfaces(house, ctx, {})
    assert placement.rotation_deg in surfaces
    assert surfaces[placement.rotation_deg].buffer(1e-6).contains(Point(placement.origin))


@pytest.mark.parametrize(("case", "outcome"), [("standard", None), ("brick", "deviation")])
def test_facade_material_class_of_the_wall_profile_is_checked(case: str, outcome: str | None) -> None:
    house = demo(case)
    ctx = demo_plu(extra=(rule("facade", {"materials_allowed": ["render"]}),))
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials(case))
    material = next(c for c in result.checks if c.code == "facade_material")
    assert material.measured == ("render" if case == "standard" else "brick")
    assert material.params["subject_kind"] == "house"
    assert site_outcome(material) == outcome


def _roof_check(case: str, params: dict[str, Any], prefix: str) -> Check:
    house = demo(case)
    ctx = demo_plu(roof=rule("roof", params))
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials(case))
    return next(c for c in result.checks if c.code.startswith(prefix))


@pytest.mark.parametrize(
    ("case", "allowed", "code", "status"),
    [
        ("r1_standard", ["gable", "hip"], "roof_form", PASS),
        ("r1_standard", ["flat"], "roof_form", FAIL),
        ("r1_mansard", ["mansard"], "roof_form", PASS),
        ("r1_half_hip", ["gable", "hip", "other"], "roof_form", PASS),
        ("r1_half_hip", ["gable"], "roof_form_open", UNKNOWN),
        ("r1_half_hip", ["flat", "mansard"], "roof_form", FAIL),
    ],
)
def test_roof_form_with_readings_is_decided_only_when_all_agree(
    case: str, allowed: list[str], code: str, status: str
) -> None:
    """Ergänzung 11: Krüppelwalm ist im PLU nicht eindeutig benannt; offen bleibt er nur, wenn seine
    Lesarten verschieden ausgehen (Warnung, bis die Auslegung festgelegt ist)."""
    check = _roof_check(case, {"allowed_forms": allowed}, "roof_form")
    assert (check.code, check.status, check.binding) == (code, status, status != UNKNOWN)
    assert check.measured == ("half_hip" if case == "r1_half_hip" else demo(case).roof_form)
    assert site_outcome(check) == {PASS: None, FAIL: "deviation", UNKNOWN: "warning"}[status]


@pytest.mark.parametrize(
    ("case", "limits", "code", "status", "measured"),
    [
        ("r1_standard", (30, 45), "roof_pitch", PASS, 35.0),
        ("r1_standard", (40, None), "roof_pitch", FAIL, 35.0),
        ("r1_mansard", (20, 75), "roof_pitch", PASS, 70.0),
        ("r1_mansard", (30, 60), "roof_pitch", FAIL, 25.0),
        ("r1_mansard", (20, 45), "roof_pitch_open", UNKNOWN, 70.0),
        ("r1_half_hip", (35, 45), "roof_pitch_open", UNKNOWN, 60.0),
    ],
)
def test_pitch_of_differently_inclined_faces_is_decided_only_when_all_agree(
    case: str, limits: tuple[float | None, float | None], code: str, status: str, measured: float
) -> None:
    """Ergänzung 11: Welche Neigung einer Mansarde (oder eines Krüppelwalms) maßgeblich ist, legt die
    Auslegung fest; entschieden ist die Prüfung, wenn alle Neigungen die Grenzen einhalten oder keine."""
    params = {"pitch_min_deg": limits[0], "pitch_max_deg": limits[1]}
    check = _roof_check(case, {k: v for k, v in params.items() if v is not None}, "roof_pitch")
    assert (check.code, check.status, check.binding) == (code, status, status != UNKNOWN)
    assert check.measured == measured


def test_two_storeys_are_checked_with_eave_ridge_and_storeys() -> None:
    """Zone Uh von AD 65: Traufe 7 m, höchster Punkt 10 m; das R+1 hält beides ein, nicht aber „R“."""
    house = demo("r1_standard")
    ctx = demo_plu(height=rule("max_height", {"eave_m": 7, "ridge_m": 10, "storeys": "R"}), ratio=0.6)
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials("r1_standard"))
    heights = {c.code: (c.measured, c.status) for c in result.checks if c.kind == "max_height"}
    assert heights == {
        "height_ridge": (pytest.approx(9.143, abs=1e-3), PASS),
        "height_eave": (pytest.approx(5.74, abs=1e-3), PASS),
        "height_storeys": ("R+1", FAIL),
    }


def test_roof_material_class_other_is_a_class_of_its_own() -> None:
    """Flachdach mit Klasse `other`: Verlangt die Zone eine Deckung, ist das eine Abweichung, kein offener
    Punkt (Befund HM4, DECISIONS)."""
    house = demo()
    ctx = demo_plu(roof=rule("roof", {"materials_allowed": ["tile"]}))
    result = evaluate_site(house, centred(house, ctx), ctx, {}, materials())
    material = next(c for c in result.checks if c.code == "roof_material")
    assert material.measured == "other" and material.status == FAIL
