"""Regeln für ein Grundstück auflösen, ohne Datenbank (REFACTORING_PLAN S12): Splitter, Stand je Zone und
Grundstück, Rückfall auf den vorigen Planstand, Projektkorrekturen."""

from dataclasses import dataclass
from typing import Any, Literal

import pytest

from app.rules.domain.resolve import (
    ZoneState,
    apply_override,
    overall_status,
    split_slivers,
    use_older,
    zone_state,
)
from app.rules.schemas import RuleOut


@dataclass(frozen=True)
class Part:
    code: str
    area: float


def test_slivers_below_one_square_metre_or_one_percent_are_ignored() -> None:
    parts = [Part("Uh", 480.0), Part("A", 15.0), Part("N", 4.9), Part("Ub", 0.8)]
    split = split_slivers(parts, 500.0)
    assert [p.code for p in split.relevant] == ["Uh", "A"]
    assert [p.code for p in split.ignored] == ["N", "Ub"]
    assert split.warnings == ["multiple_zones"]
    assert split.uncovered_share == 0.0


def test_uncovered_share_warns_from_one_percent() -> None:
    split = split_slivers([Part("Uh", 495.0)], 500.0)
    assert split.uncovered_share == 0.01
    assert split.warnings == ["zone_coverage_incomplete"]
    assert split_slivers([Part("Uh", 495.5)], 500.0).warnings == []


def test_without_parts_nothing_counts_as_uncovered() -> None:
    split = split_slivers([], 500.0)
    assert (split.relevant, split.ignored, split.uncovered_share, split.warnings) == ([], [], 0.0, [])


@pytest.mark.parametrize(
    ("version", "chapter", "options", "expected"),
    [
        ("simulated", "succeeded", {}, ZoneState("simulated")),
        ("office_reviewed", "extracting", {}, ZoneState("office_reviewed", updating=True)),
        ("simulated", None, {}, ZoneState("simulated")),
        # Frühere Version zum Vergleich: nach Herkunft, nicht `retired` (PLAN_AN4 7.1 Nr. 4)
        ("retired", "pending", {"pinned": True, "version_origin": "office"}, ZoneState("office_reviewed")),
        ("retired", "succeeded", {"pinned": True, "version_origin": "extraction"}, ZoneState("simulated")),
        (None, None, {}, ZoneState("unavailable", "chapter_not_found")),
        (None, "pending", {}, ZoneState("in_progress")),
        (None, "extracting", {}, ZoneState("in_progress")),
        (None, "failed", {"chapter_error": "refusal"}, ZoneState("unavailable", "refusal")),
        (None, "failed", {}, ZoneState("unavailable", "failed")),
    ],
)
def test_zone_state(
    version: str | None, chapter: str | None, options: dict[str, Any], expected: ZoneState
) -> None:
    assert zone_state(version, chapter, **options) == expected


@pytest.mark.parametrize(
    ("zones", "expected"),
    [
        ([], ("unavailable", "no_zone")),
        ([ZoneState("simulated"), ZoneState("office_reviewed")], ("ok", None)),
        ([ZoneState("in_progress"), ZoneState("unavailable", "refusal")], ("in_progress", None)),
        ([ZoneState("simulated"), ZoneState("in_progress")], ("partial", None)),
        ([ZoneState("simulated"), ZoneState("unavailable", "chapter_not_found")], ("partial", None)),
        (
            [ZoneState("unavailable", "chapter_not_found"), ZoneState("unavailable", "refusal")],
            ("unavailable", "chapter_not_found"),
        ),
    ],
)
def test_overall_status(zones: list[ZoneState], expected: tuple[str, str | None]) -> None:
    assert overall_status(zones) == expected


@pytest.mark.parametrize(
    ("current", "older", "expected"),
    [
        (None, "ok", True),
        ("partial", "ok", True),
        ("unavailable", "partial", True),
        (None, "partial", True),
        ("partial", "partial", False),
        ("in_progress", "unavailable", False),
    ],
)
def test_older_plan_counts_while_it_has_more_rules(current: str | None, older: str, expected: bool) -> None:
    assert use_older(current, older) is expected


def _rule(
    kind: str, building_kind: str, origin: Literal["extraction", "office", "project"] = "extraction"
) -> RuleOut:
    return RuleOut(
        kind=kind,
        building_kind=building_kind,
        status="effective",
        reason=None,
        params={"min_m": 3},
        page=7,
        quote="q",
        quote_verified=True,
        source_url=None,
        confidence=0.9,
        notes=None,
        origin=origin,
    )


def _apply(rules: list[RuleOut], kind: str, building_kind: str) -> list[RuleOut]:
    return apply_override(
        rules,
        _rule(kind, building_kind, "project"),
        lambda rule, other: rule.model_copy(update={"building_kind": other}),
    )


def test_project_override_for_main_building_narrows_general_rule() -> None:
    rules = [_rule("setback_side", "any"), _rule("max_footprint_ratio", "any")]
    side = _apply(rules, "setback_side", "main")
    assert sorted((r.kind, r.building_kind, r.origin) for r in side) == [
        ("max_footprint_ratio", "any", "extraction"),
        ("setback_side", "annex", "extraction"),
        ("setback_side", "main", "project"),
        ("setback_side", "pool", "extraction"),
    ]
    footprint = _apply(rules, "max_footprint_ratio", "main")
    assert [(r.kind, r.building_kind, r.origin) for r in footprint if r.kind == "max_footprint_ratio"] == [
        ("max_footprint_ratio", "main", "project")
    ]
    everything = _apply(side, "setback_side", "any")
    assert [(r.kind, r.building_kind) for r in everything if r.kind == "setback_side"] == [
        ("setback_side", "any")
    ]


def test_specific_rule_already_present_is_not_duplicated() -> None:
    rules = [_rule("max_height", "any"), _rule("max_height", "annex")]
    result = _apply(rules, "max_height", "main")
    assert sorted((r.building_kind, r.origin) for r in result) == [
        ("annex", "extraction"),
        ("main", "project"),
        ("pool", "extraction"),
    ]
