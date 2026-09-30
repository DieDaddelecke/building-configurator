"""Eine Änderung der Konfiguration prüfen, ohne Datenbank (REFACTORING_PLAN S14, Plan H3 3.1, 3.9; D12).

Testgrundstück wie in `test_configuration_domain.py`: 20 × 31 m, Straße im Norden, Zone UB; Ligne 12 × 8 m.
"""

import pytest

from app.configuration.domain.change import (
    Change,
    ChangeRejected,
    Stored,
    decide_change,
    option_states,
)
from app.configuration.domain.options import Reason, Selection
from app.configuration.domain.placement import Placement
from tests.configuration_support import (
    context,
    ligne,
    mockup_offer,
    option_offer,
    package_offer,
    plateau,
    type_offer,
)

NOTHING_STORED = Stored(None, {}, Selection())


def rejected(change: Change, stored: Stored = NOTHING_STORED, house_type=None) -> ChangeRejected:  # type: ignore[no-untyped-def]
    with pytest.raises(ChangeRejected) as caught:
        decide_change(house_type or ligne(), context(), mockup_offer(), change, stored)
    return caught.value


def test_without_a_placement_the_house_goes_near_the_street() -> None:
    decision = decide_change(
        ligne(), context(), mockup_offer(), Change({}, Selection("base"), None), NOTHING_STORED
    )
    assert decision.placement is not None
    assert decision.placement.origin == pytest.approx((4.0, 18.0), abs=0.01)
    assert (decision.selection, decision.dropped) == (Selection("base"), [])


def test_requested_rotation_snaps_to_an_allowed_one_or_is_rejected() -> None:
    change = Change({}, Selection(), Placement((4.0, 18.0), 0.03), place=True)
    decision = decide_change(ligne(), context(), mockup_offer(), change, NOTHING_STORED)
    assert decision.placement == Placement((4.0, 18.0), 0.0)
    error = rejected(Change({}, Selection(), Placement((4.0, 18.0), 45.0), place=True))
    assert error.code == "rotation_not_allowed" and 0.0 in error.allowed


def test_no_placement_is_a_valid_request() -> None:
    decision = decide_change(
        ligne(), context(), mockup_offer(), Change({}, Selection(), None, place=True), NOTHING_STORED
    )
    assert decision.placement is None


def test_placement_outside_the_site_is_rejected_with_its_checks() -> None:
    error = rejected(Change({}, Selection(), Placement((30.0, 5.0), 0.0), place=True))
    assert error.code == "placement_violation"
    assert error.result is not None and "outside_site" in {c.code for c in error.result.checks}


def test_blocked_type_counts_only_when_type_or_boundary_is_requested() -> None:
    error = rejected(Change({}, Selection(), None, new_type=True), house_type=plateau())
    assert error.code == "type_blocked" and [c.code for c in error.checks] == ["roof_form"]
    # Nur die Auswahl ändert sich: Der gespeicherte Typ bleibt, wie er ist
    decide_change(plateau(), context(), mockup_offer(), Change({}, Selection(), None), NOTHING_STORED)


def test_boundary_switch_only_where_the_rule_allows_it() -> None:
    error = rejected(Change({4: True}, Selection(), None, type_or_boundary=True))
    assert (error.code, error.edges) == ("boundary_not_allowed", [4])


def test_only_new_exclusions_reject_a_selection() -> None:
    both = Selection("base", ("holz_sued", "holz_voll"))
    error = rejected(Change({}, both, None, selection_changed=True), Stored(None, {}, Selection("base")))
    assert error.code == "invalid_selection"
    assert error.reasons == [Reason("excluded_by", "holz_voll", "holz_sued")]
    # Stand schon gespeichert (etwa nach einem Katalogwechsel): kein neuer Grund, also kein Fehler
    decide_change(
        ligne(),
        context(),
        mockup_offer(),
        Change({}, both, None, selection_changed=True),
        Stored(None, {}, both),
    )


def test_new_type_drops_what_it_does_not_offer() -> None:
    offer = type_offer(packages=(package_offer("base"),), options=(option_offer("pv"),))
    change = Change({}, Selection("confort", ("pv", "keller")), None, new_type=True)
    decision = decide_change(ligne(), context(), offer, change, NOTHING_STORED)
    assert decision.selection == Selection(None, ("pv",))
    assert decision.dropped == ["confort", "keller"]


def test_option_states_show_what_the_customer_can_still_choose() -> None:
    states = {
        s.option.slug: s
        for s in option_states(
            ligne(), None, {}, context(), mockup_offer(), Selection("confort", ("holz_sued",))
        )
    }
    assert states["ziegel_dach"].state == "included"
    assert states["holz_sued"].state == "selected"
    assert states["pv"].state == "available"
    blocked = states["holz_voll"]
    assert blocked.state == "blocked"
    assert blocked.reasons == [Reason("excluded_by", "holz_voll", "holz_sued")]
