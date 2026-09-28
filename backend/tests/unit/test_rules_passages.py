"""Stellen mit Vorschriftscharakter, Abdeckung und Alternativbezeichnungen (PLAN_G2_VOLLSTAENDIGKEIT 3.3–3.4).

Seitentext: PLU Beyenes, Modification n°1, Kapitel UC (S. 9–20) und allgemeine Seiten (S. 5–8).
"""

from app.rules.domain import lexicon
from app.rules.domain.passages import (
    Passage,
    chapter_passages,
    coverage,
    for_search,
    normative,
    running_lines,
    split_passages,
)
from tests.rules_support import fixture_json

PAGES: dict[int, str] = {int(k): v for k, v in fixture_json("beyenes-uc-pages.json")["pages"].items()}
CHAPTER = list(range(9, 21))


def _texts(passages: list[Passage]) -> list[str]:
    return [p.text for p in passages]


def test_headers_headings_and_labels_are_no_passages() -> None:
    skip = running_lines(PAGES, CHAPTER)
    passages = chapter_passages(PAGES, CHAPTER)
    texts = _texts(passages)
    assert not any("dossier approbation" in t for t in texts)
    assert not any(t.startswith(("ARTICLE", "ZONE UC", "L’ EMPRISE")) for t in texts)
    assert "modificationn°#duplu-dossierapprobation#" in skip and "zoneuc" in skip
    assert normative("Modification n°1 du PLU – dossier approbation 14") == (False, False)
    assert normative("3 m voie publique")[1] and not split_passages(14, "3 m voie publique")


def test_list_items_stay_with_their_lead_in() -> None:
    """Die Staffel der Grundfläche ist eine Stelle, nicht drei Aufzählungspunkte ohne Zusammenhang."""
    page14 = [p for p in chapter_passages(PAGES, CHAPTER) if p.page == 14]
    staffel = next(p for p in page14 if p.text.startswith("Si la surface du terrain est supérieure à 200 m²"))
    assert staffel.has_number and "- de 20 % pour les m² suivants." in staffel.text
    assert any(p.text.startswith("La hauteur maximale des constructions est de 9 mètres") for p in page14)


def test_quotes_cover_passages_and_the_rest_stays_open() -> None:
    passages = chapter_passages(PAGES, [14])
    quotes = [
        (14, "La hauteur maximale des constructions est de 9 mètres au faîtage et de 7 mètres à l'acrotère"),
        (
            None,
            "l’emprise au sol maximale des constructions ne doit pas excéder 90 % de la superficie totale",
        ),
    ]
    result = coverage(passages, quotes, PAGES)
    open_texts = _texts(result.open)
    assert result.total == len(passages) and result.assigned == 2
    assert any(
        t.startswith("Les constructions implantées sur la limite séparative de fond") for t in open_texts
    )
    assert any(t.startswith("Si la surface du terrain est supérieure à 200 m²") for t in open_texts)
    assert not any(t.startswith("La hauteur maximale") for t in open_texts)


def test_passages_with_numbers_come_first_for_the_search() -> None:
    passages = [Passage(9, "a doit", False), Passage(9, "b 6 m", True), Passage(10, "c doit", False)]
    assert _texts(for_search(passages, 2)) == ["a doit", "b 6 m"]
    assert _texts(for_search(passages, 1)) == ["b 6 m"]


def test_lexicon_finds_kinds_building_kinds_and_extra_pages() -> None:
    chapter_text = "\n".join(PAGES[p] for p in CHAPTER)
    mentioned = lexicon.kinds_mentioned(chapter_text)
    assert {"fence", "parking", "planting", "max_footprint_ratio", "setback_between_buildings"} <= mentioned
    assert lexicon.building_kinds_mentioned(chapter_text) == {"annex", "pool"}
    assert lexicon.mentions("La hauteur totale d’une CLÔTURE", lexicon.terms_for("fence")) == 1
    assert "piscine" in lexicon.terms_for("setback_side", "pool")
    # Allgemeine Seiten 5–8: S. 6 (Risiken) und 7 (Verbote) nennen „grande hauteur“, S. 5 und 8 nicht
    pages = lexicon.extra_pages(PAGES, [5, 6, 7, 8], ["hauteur", "grande hauteur"], chapter_text, 15)
    assert pages == [6, 7]
    assert lexicon.extra_pages(PAGES, [5, 6, 7, 8], ["hauteur"], chapter_text, 1) == [6]
    assert lexicon.extra_pages(PAGES, [5, 6, 7, 8], ["clôture"], chapter_text, 15) == []


def test_permissions_and_derogations_are_passages() -> None:
    page15 = [p.text for p in chapter_passages(PAGES, CHAPTER) if p.page == 15]
    assert any("parti pris architectural contemporain" in text for text in page15)
