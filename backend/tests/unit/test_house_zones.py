"""Zonenerkennung (docs/PLAN_HAUSMODELL.md 3.6 Nr. 1–3, E-HM-23): Schreibweisen, Quellen und
Zuordnungstabelle."""

import pytest

from app.house.domain.zones import SourceKind, SourceValue, ZoneTable, classify, normalize

TABLE = ZoneTable.build(
    [
        ("living", ["SEJOUR", "SALON", "SEJOUR/CUISINE", "PIECE DE VIE"]),
        ("kitchen", ["CUISINE"]),
        ("bedroom", ["CHAMBRE", "SUITE PARENTALE"]),
        ("bathroom", ["SALLE DE BAIN", "SALLE D'EAU", "SALLE D'EAU/WC", "WC"]),
        ("corridor", ["ENTREE", "DEGAGEMENT"]),
    ],
    ["SDP", "SHAB", "Surface de plancher", "Emprise au sol"],
)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("CHAMBRE 1", "CHAMBRE"),
        ("Chambre_02", "CHAMBRE"),
        ("chambre n°3", "CHAMBRE"),
        ("Chambre N° 4", "CHAMBRE"),
        ("CHAMBRE1", "CHAMBRE"),
        ("chambre no 5", "CHAMBRE"),
        ("Séjour", "SEJOUR"),
        ("  Entrée  ", "ENTREE"),
        ("Dégagement", "DEGAGEMENT"),
        ("Pièce de vie", "PIECE DE VIE"),
        ("Cuisine + Séjour", "CUISINE/SEJOUR"),
        ("SEJOUR/CUISINE", "CUISINE/SEJOUR"),
        ("séjour & cuisine", "CUISINE/SEJOUR"),
        ("Séjour et cuisine", "CUISINE/SEJOUR"),
        ("Salle d'eau", "SALLE D EAU"),
        ("SALLE D'EAU / WC", "SALLE D EAU/WC"),
        ("wc - salle d’eau", "WC SALLE D EAU"),
        ("Suite parentale (étage)", "SUITE PARENTALE ETAGE"),
        ("CABINET", "CABINET"),
        ("NORD 1", "NORD"),
        ("001", ""),
        ("", ""),
    ],
)
def test_spellings_normalize(raw: str, key: str) -> None:
    assert normalize(raw) == key


@pytest.mark.parametrize(
    ("values", "result", "room_type", "source"),
    [
        # Archicad IFC4: Kategorie als Name des IfcSpaceType, Zonenname „SDP“ (Probedateien 1 und 2)
        ([("type", "CHAMBRE 1"), ("long_name", "SDP"), ("name", "002")], "room", "bedroom", "type"),
        ([("category", "Séjour"), ("long_name", "Cuisine")], "room", "living", "category"),
        ([("object_type", "Salle d'eau")], "room", "bathroom", "object_type"),
        ([("long_name", "Chambre_02"), ("name", "Chambre")], "room", "bedroom", "long_name"),
        ([("name", "Entrée")], "room", "corridor", "name"),
        ([("classification", "Salon")], "room", "living", "classification"),
        # Reihenfolge der Quellen, nicht der Liste
        ([("name", "Cuisine"), ("type", "Séjour")], "room", "living", "type"),
        # Kategorien ohne Raum nur über Typ und Category
        ([("type", "SDP"), ("long_name", "Cuisine")], "ignored", None, "type"),
        ([("category", "Surface de plancher")], "ignored", None, "category"),
        ([("long_name", "SDP"), ("name", "Cuisine")], "room", "kitchen", "name"),
        # Leere und unbekannte Werte überspringen
        ([("type", "001"), ("long_name", "Cuisine")], "room", "kitchen", "long_name"),
        ([("type", "Garage"), ("long_name", "SDP"), ("name", "12")], "unrecognized", None, None),
        ([], "unrecognized", None, None),
    ],
)
def test_first_source_in_table_decides(
    values: list[tuple[SourceKind, str]], result: str, room_type: str | None, source: SourceKind | None
) -> None:
    match = classify([SourceValue(kind, raw) for kind, raw in values], TABLE)
    assert (match.result, match.room_type_id, match.source) == (result, room_type, source)


def test_later_sources_with_other_type_are_conflicts() -> None:
    match = classify(
        [
            SourceValue("type", "Chambre 1"),
            SourceValue("long_name", "Bureau"),
            SourceValue("name", "Cuisine"),
        ],
        TABLE,
    )
    assert match.room_type_id == "bedroom"
    assert [(c.kind, c.raw, c.room_type_id) for c in match.conflicts] == [("name", "Cuisine", "kitchen")]
    same = classify([SourceValue("type", "Chambre 1"), SourceValue("name", "chambre n°2")], TABLE)
    assert same.conflicts == ()
    ignored = classify([SourceValue("type", "SHAB"), SourceValue("name", "Séjour")], TABLE)
    assert ignored.result == "ignored"
    assert [c.room_type_id for c in ignored.conflicts] == ["living"]


@pytest.mark.parametrize(
    ("room_types", "ignored", "message"),
    [
        ([("living", ["12"])], [], "leer"),
        ([("living", ["Séjour"]), ("kitchen", ["SEJOUR"])], [], "gehört zu living und kitchen"),
        ([("living", ["Cuisine + Séjour"]), ("kitchen", ["séjour/cuisine"])], [], "gehört zu"),
        ([("living", ["SDP"])], ["sdp"], "Kategorie ohne Raum"),
        ([], ["N° 3"], "leer"),
    ],
)
def test_table_must_be_unique(
    room_types: list[tuple[str, list[str]]], ignored: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ZoneTable.build(room_types, ignored)


def test_same_alias_twice_in_one_type_is_allowed() -> None:
    table = ZoneTable.build([("living", ["Séjour", "SEJOUR"])], [])
    assert dict(table.aliases) == {"SEJOUR": "living"}
