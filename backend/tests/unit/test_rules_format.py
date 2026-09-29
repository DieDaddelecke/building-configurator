"""Werte der Regeln als Text (app/rules/format.py), gleich wie `frontend/src/rules/format.ts`."""

import pytest

from app.rules.format import number, reason_text, rule_value


def test_numbers_drop_trailing_zeros_and_group_like_intl() -> None:
    assert number(20, "de") == "20"
    assert number(3.5, "fr") == "3,5"
    assert number(0.125, "de") == "0,13"
    assert number(-0.75, "de") == "-0,75"
    assert number(1250, "de", 0) == "1.250"
    assert number(1250, "fr", 0) == "1 250"
    assert number(None, "de") == "?"


@pytest.mark.parametrize(
    ("kind", "params", "expected"),
    [
        ("setback_street", {"mode": "range", "min_m": 5, "max_m": 20, "band": "building"}, "5–20 m"),
        (
            "setback_street",
            {"mode": "alignment", "measured_from": "roof_edge"},
            "an der Straßenflucht · ab Dachkante gemessen",
        ),
        ("setback_street", {"mode": "fixed", "min_m": 4}, "genau 4 m"),
        ("setback_street", {"min_m": 3}, "≥ 3 m"),
        (
            "setback_side",
            {"min_m": 3, "height_factor": 0.5, "height_basis": "eave", "allow_on_boundary": True},
            "auf der Grenze oder ≥ 3 m · 0,5 × Traufhöhe",
        ),
        (
            "setback_rear",
            {"height_factor": 0.5, "on_boundary_max_height_m": 3.5},
            "0,5 × Höhe · auf der Grenze höchstens 3,5 m hoch",
        ),
        ("max_footprint_ratio", {"ratio": 0.25}, "≤ 25 %"),
        (
            "max_height",
            {
                "eave_m": 7,
                "ridge_m": 10.5,
                "storeys": "R+1",
                "reference": "natural_terrain",
                "measured_at": "mean",
            },
            "Traufe ≤ 7 m · First ≤ 10,5 m · R+1 · im Mittel gemessen",
        ),
        (
            "roof",
            {
                "allowed_forms": ["gable", "hip"],
                "pitch_min_deg": 35,
                "flat_roof": "green_only",
                "ridge_orientation": "parallel_to_street",
                "materials_allowed": ["clay_tile", "slate"],
            },
            "Satteldach, Walmdach · 35–…° · Flachdach nur begrünt · First parallel zur Straße"
            " · Deckung: Tondachziegel, Schiefer",
        ),
        (
            "facade",
            {
                "materials_allowed": ["render"],
                "materials_forbidden": ["metal"],
                "color_families_allowed": ["light", "beige"],
            },
            "Putz · nicht Metall · hell, beige",
        ),
        ("unsealed_min", {"ratio": 0.3, "full_soil_ratio": 0.2}, "≥ 30 % · davon offener Boden 20 %"),
        (
            "parking",
            {"spaces_per_dwelling": 2, "spaces_per_m2_sdp": 0.02, "min_dimensions": "2,5 × 5 m"},
            "2 je Wohnung · 1 je 50 m² Geschossfläche · Maße 2,5 × 5 m",
        ),
        ("annex", {"max_footprint_m2": 20, "max_height_m": 3.5}, "≤ 20 m² · Höhe ≤ 3,5 m"),
        ("planting", {"min_green_ratio": 0.2, "trees_per_m2": 0.01}, "≥ 20 % · 1 Bäume je 100 m²"),
        ("fence", {"max_height_m": 1.6, "materials": ["wood", "vegetation"]}, "≤ 1,6 m · Holz, Begrünung"),
        (
            "max_area",
            {"sdp_m2": 250, "footprint_m2": 180.4},
            "Nutzfläche (SDP) ≤ 250 m² · Grundfläche ≤ 180 m²",
        ),
        ("text_only", {"summary": "Clôtures végétalisées"}, "Clôtures végétalisées"),
    ],
)
def test_effective_rules_read_like_the_interface(kind: str, params: dict[str, object], expected: str) -> None:
    assert rule_value(kind, "effective", None, params, "de") == expected


def test_french_texts_and_status() -> None:
    assert rule_value("max_height", "effective", None, {"ridge_m": 9}, "fr").endswith("≤ 9 m")
    assert rule_value("roof", "effective", None, {}, "de") == "wirksam"
    assert rule_value("max_height", "not_regulated", None, {}, "de") == "nicht geregelt"
    assert (
        rule_value("max_height", "unknown", "quote_unverified", {}, "de")
        == "nicht ermittelt: Fundstelle nicht bestätigt"
    )
    assert reason_text(None, "de") == "nicht ermittelt"
    assert reason_text("no_such_reason", "fr") == rule_value("roof", "unknown", None, {}, "fr")
