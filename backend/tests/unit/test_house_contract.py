"""Vertrag des Hausmodells (PLAN_HAUSMODELL 3.4, E-HM-29): Testdaten und Demo-Seed des Rechenkerns sind
gültige Dokumente, Python liest sie verlustfrei, und die Prüfungen des Vertrags greifen."""

import json
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.house.contract import HouseCatalog, HouseConfiguration, HouseTemplate, MaterialClass
from app.rules.domain.kinds import MATERIALS

# Im Container liegt packages/domain unter /packages/domain (compose.yaml, backend-dev)
DOMAIN = Path(__file__).resolve().parents[3] / "packages" / "domain"
SOURCES = {"fixture": DOMAIN / "test" / "fixtures" / "demo-house", "seed": DOMAIN / "seed" / "demo-house"}


def _load(source: str, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SOURCES[source] / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("source", SOURCES)
def test_demo_house_round_trips(source: str) -> None:
    template = _load(source, "template")
    catalog = _load(source, "catalog")
    assert HouseTemplate.model_validate(template).model_dump(mode="json") == template
    assert HouseCatalog.model_validate(catalog).model_dump(mode="json") == catalog


def test_material_classes_match_rules() -> None:
    """Die Hausbeschreibung nennt Materialklassen, die die PLU-Prüfung kennt (E-HM-4)."""
    assert get_args(MaterialClass) == MATERIALS


def test_unknown_field_is_rejected() -> None:
    template = _load("fixture", "template")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        HouseTemplate.model_validate({**template, "price": 1})


def test_element_ids_are_unique_and_reserved() -> None:
    template = _load("fixture", "template")
    duplicate = {**template, "rooms": [*template["rooms"], template["rooms"][0]]}
    with pytest.raises(ValidationError, match="doppelt"):
        HouseTemplate.model_validate(duplicate)
    reserved = {**template, "rooms": [{**template["rooms"][0], "id": "roof"}, *template["rooms"][1:]]}
    with pytest.raises(ValidationError, match="doppelt"):
        HouseTemplate.model_validate(reserved)


def test_element_defaults_name_known_elements() -> None:
    """Standard eines einzelnen Bauteils (E-HM-37): nur für Elemente des Templates oder das Dach."""
    template = _load("fixture", "template")
    window = template["openings"][0]["id"]
    for element in (window, "roof"):
        HouseTemplate.model_validate({**template, "element_defaults": {element: {"window_type": "x"}}})
    with pytest.raises(ValidationError, match="Element win-unbekannt unbekannt"):
        HouseTemplate.model_validate(
            {**template, "element_defaults": {"win-unbekannt": {"window_type": "x"}}}
        )


@pytest.mark.parametrize(
    ("aliases", "ignored", "message"),
    [
        ({"kitchen": ["CUISINE", "séjour"]}, None, "gehört zu living und kitchen"),
        ({"living": ["SEJOUR", "SDP"]}, None, "Kategorie ohne Raum"),
        ({"living": ["SEJOUR", "N° 2"]}, None, "leer"),
        (None, ["SHAB", "Shab"], None),
    ],
)
def test_zone_table_is_unique_after_normalization(
    aliases: dict[str, list[str]] | None, ignored: list[str] | None, message: str | None
) -> None:
    """Aliasse der Raumtypen und Kategorien ohne Raum, eindeutig nach der Normalisierung (3.6 Nr. 3)."""
    catalog = _load("fixture", "catalog")
    room_types = [{**t, "aliases": (aliases or {}).get(t["id"], t["aliases"])} for t in catalog["room_types"]]
    changed = {
        **catalog,
        "room_types": room_types,
        "ignored_zone_categories": ignored or catalog["ignored_zone_categories"],
    }
    if message is None:
        HouseCatalog.model_validate(changed)
        return
    with pytest.raises(ValidationError, match=message):
        HouseCatalog.model_validate(changed)


def test_envelope_needs_one_segment_per_edge() -> None:
    template = _load("fixture", "template")
    loop = template["envelope"][0]
    broken = {**template, "envelope": [{**loop, "segments": loop["segments"][:-1]}]}
    with pytest.raises(ValidationError, match="genau ein Segment"):
        HouseTemplate.model_validate(broken)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"entry_id": "price.roof.flat"}, "genau eine Preisquelle"),
        ({"quantity_key": None}, "quantity_key genau bei per_unit"),
        ({"method": "percent", "quantity_key": None}, "percent_base genau bei percent"),
        ({"method": "lump_sum", "quantity_key": None}, "lump_sum mit by_target nur für template"),
    ],
)
def test_pricing_rule_is_consistent(change: dict[str, Any], message: str) -> None:
    catalog = _load("fixture", "catalog")
    rules = [{**rule, **change} if rule["id"] == "roof" else rule for rule in catalog["pricing_rules"]]
    with pytest.raises(ValidationError, match=message):
        HouseCatalog.model_validate({**catalog, "pricing_rules": rules})


def test_expression_lists_hold_only_literals() -> None:
    """Listen in Ausdrücken enthalten nur Werte; sonst wäre der Typ rekursiv über Listen (E-HM-34)."""
    catalog = _load("fixture", "catalog")
    rule = catalog["rules"][0]
    nested = {
        **rule,
        "when": {
            "op": "in",
            "left": {"path": "building.roof_kind"},
            "right": [{"path": "selection.roof_type"}],
        },
    }
    with pytest.raises(ValidationError):
        HouseCatalog.model_validate({**catalog, "rules": [nested]})
    flat = {**rule, "when": {"op": "in", "left": {"path": "building.roof_kind"}, "right": ["flat", None]}}
    HouseCatalog.model_validate({**catalog, "rules": [flat]})


def test_configuration_holds_only_choices() -> None:
    """Die Auswahl trägt Werte, keine Ergebnisse (L1, P 2.1 Nr. 9)."""
    selection = {
        "value": {"type": "option", "option_value_id": "window.floor_length"},
        "room_overrides": {},
        "element_overrides": {},
    }
    HouseConfiguration.model_validate({"selections": {"window_type": selection}})
    with pytest.raises(ValidationError):
        HouseConfiguration.model_validate({"selections": {"window_type": selection}, "net_amount": 1})
