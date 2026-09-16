"""Wirkung überlagernder Vorgaben des GPU auf den Baurahmen (Plan G3 3.4, RW13).

Die Typcodes folgen dem CNIG-Standard für PLU/PLUi (`typepsc`). Sie sind am 16.09.2026 gegen die
aufgezeichneten Antworten für Treillières geprüft; die Liste gehört in `docs/ANNAHMEN.md` und ist vor einer
Erweiterung des Einzugsgebiets erneut zu prüfen (Spez. 0 Punkt 5).

- `no_build`: Bebauung ist ausgeschlossen; die Fläche fehlt in beiden Konturen.
- `restricts`: Bebauung ist eingeschränkt oder an Bedingungen geknüpft; die Fläche fehlt nur in der
  engsten Auslegung und erzeugt einen Hinweis.
- `info`: Hinweis ohne Wirkung auf die Fläche.
"""

NO_BUILD_TYPES: dict[str, str] = {
    "01": "espace_boise_classe",
    "05": "emplacement_reserve",
}
RESTRICTING_TYPES: dict[str, str] = {
    "02": "risque_ou_nuisance",
    "07": "patrimoine_paysage",
    "25": "continuite_ecologique",
    "31": "espace_a_preserver",
}
"""Wirkung im Text des Reglements; die Fläche bleibt bebaubar, aber nicht ohne Bedingungen."""

Effect = str
"""`no_build`, `restricts` oder `info`."""


def effect(category: str, type_code: str | None, is_area: bool) -> Effect:
    """Wirkung einer Vorgabe. Nur flächige Vorschriften können Fläche abziehen; Linien und Punkte
    (Hecken, Baulinien) und alle Informationen und Servituden sind Hinweise."""
    if not is_area or category != "prescription" or type_code is None:
        return "info"
    if type_code in NO_BUILD_TYPES:
        return "no_build"
    if type_code in RESTRICTING_TYPES:
        return "restricts"
    return "info"


def label_key(type_code: str | None) -> str | None:
    """Kurzbezeichnung für Hinweise; `None` bei unbekanntem Typ (Hinweis „Wirkung nicht bewertet“)."""
    if type_code is None:
        return None
    return NO_BUILD_TYPES.get(type_code) or RESTRICTING_TYPES.get(type_code)
