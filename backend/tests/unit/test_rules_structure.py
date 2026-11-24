"""Gliederung über laufende Kopfzeilen, Zonenbeschränkung von Absätzen, Zitate über den Seitenwechsel und
Erreichbarkeit der Sollwerte (BESTANDSAUFNAHME_PLU_PIPELINE S2, S7; Erstbefund Paris und Rennes)."""

from app.rules.domain.chapters import (
    Structure,
    detect_structure,
    scope_applies,
    structure_from_running_headers,
    zone_scope,
)
from app.rules.domain.evaluation import evaluate_structure
from app.rules.domain.reference import parse_entries
from app.rules.domain.text import verify_quote

BODY = "Les constructions doivent être implantées à 3 mètres minimum des limites séparatives.\n"


def _paris_page(number: int, label: str, body: str = BODY) -> str:
    # pypdf zerreißt die großen Anfangsbuchstaben der Kopfzeile („Z ONE“, „D ÉCEMBRE“)
    return f"RÈGLEMENT TOME 1 {label} \nPLU DE PARIS {number} / 40 D ÉCEMBRE 2025 \n{body}"


def _paris() -> dict[int, str]:
    pages: dict[int, str] = {1: "PROJET POUR APPROBATION"}
    layout = [
        (2, 3, "S OMMAIRE"),
        (4, 9, "M ODALITÉS D’APPLICATION DU RÈGLEMENT"),
        (10, 15, "D ISPOSITIONS GÉNÉRALES"),
        (16, 30, "Z ONE URBAINE GÉNÉRALE (UG)"),
        (31, 36, "Z ONE NATURELLE ET FORESTIÈRE (N)"),
        (37, 40, "F IGURES"),
    ]
    for first, last, label in layout:
        for number in range(first, last + 1):
            pages[number] = _paris_page(number, label)
    pages[16] = _paris_page(16, "Z ONE URBAINE GÉNÉRALE (UG)", "ZONE URBAINE GÉNÉRALE (UG)\n")
    return pages


def _rennes_page(number: int, label: str, body: str = BODY) -> str:
    return (
        f"PLUi Règlement littéral {label} \n Modification n°2 I Approbation I Juin 2025 I Rennes Métropole I "
        f"{number} \n{body}"
    )


def _rennes() -> dict[int, str]:
    toc = (
        "SOMMAIRE\nTITRE IV RÈGLES LITTÉRALES APPLICABLES À TOUTES LES ZONES ........ 5\n"
        "ZONE UA1 ................................ 12\n"
        "1. Présentation de la zone .............. 12\n"
        "2. Implantation des constructions ........ 13\n"
        "ZONE UD1 ................................ 15\n"
        "1. Présentation de la zone .............. 15\n"
        "2. Implantation des constructions ........ 16\n"
        "3. Hauteur des constructions ............. 17\n"
        "TITRE VI DÉFINITIONS ..................... 19\n"
    )
    pages = {1: "Élaboration approuvée", 2: _rennes_page(2, "Présentation", toc)}
    for number in range(3, 5):
        pages[number] = _rennes_page(number, "Modalités")
    for number in range(5, 12):
        pages[number] = _rennes_page(number, "Toutes zones")
    pages[9] = _rennes_page(
        9,
        "Toutes zones",
        "Dans les zones UB1 et UD1, les dalles de couverture comportent une épaisseur de terre de 0,60 m.\n"
        "En zone UA1, la hauteur des clôtures ne peut excéder 1,50 m.\n",
    )
    for number in range(12, 15):
        pages[number] = _rennes_page(number, "Zone UA1")
    pages[12] = _rennes_page(12, "Zone UA1", "ZONE UA1\n1. Présentation de la zone\n")
    for number in range(15, 19):
        pages[number] = _rennes_page(number, "Zone UD1")
    pages[15] = _rennes_page(15, "Zone UD1", "ZONE UD1\n1. Présentation de la zone\n")
    pages[16] = _rennes_page(16, "Zone UD1", "2. Implantation des constructions\n" + BODY)
    pages[17] = "\n"  # Abbildung ohne Text mitten im Kapitel
    for number in range(19, 22):
        pages[number] = _rennes_page(number, "Définitions")
    return pages


def test_running_headers_find_paris_zones_with_code_in_parentheses() -> None:
    """Paris: Code in Klammern hinter dem Namen, „Z ONE“ zerrissen; heute 0 Kapitel (Erstbefund 1)."""
    structure = detect_structure(_paris())
    assert structure.method == "running_headers"
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [
        ("UG", 16, 30),
        ("N", 31, 36),
    ]
    assert structure.common_pages == list(range(10, 16))
    assert structure.general_pages == list(range(4, 16))
    kinds = {(p.kind, p.first_page, p.last_page) for p in structure.parts}
    assert ("application", 4, 9) in kinds and ("other", 37, 40) in kinds
    assert next(p for p in structure.parts if p.kind == "common").label == "DISPOSITIONS GÉNÉRALES"


def test_running_headers_beat_one_page_chapters_from_the_toc() -> None:
    """Rennes: „2. Implantation“ beendete im Verzeichnis das Kapitel; „Toutes zones“ sind die Regeln für
    alle Zonen; eine Abbildung ohne Kopfzeile bleibt im Kapitel (Erstbefund 2, 4)."""
    structure = detect_structure(_rennes())
    assert structure.method == "running_headers"
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [
        ("UA1", 12, 14),
        ("UD1", 15, 18),
    ]
    assert structure.common_pages == list(range(5, 12))
    assert structure.general_pages == list(range(3, 12)) + list(range(19, 22))


def test_numbered_sub_entries_do_not_end_a_chapter_of_the_toc() -> None:
    pages = _rennes()
    # Ohne Kopfzeilen bleibt nur das Verzeichnis: UD1 reicht bis vor die Definitionen
    plain = {number: text.split("\n", 2)[-1] for number, text in pages.items()}
    structure = detect_structure(plain)
    assert structure.method == "toc"
    ud1 = next(c for c in structure.chapters if c.code == "UD1")
    assert (ud1.first_page, ud1.last_page) == (15, 18)


def test_heading_with_code_in_parentheses() -> None:
    pages = {
        1: "SOMMAIRE",
        2: "ZONE URBAINE GÉNÉRALE (UG)\n" + BODY,
        3: BODY,
        4: "ZONE NATURELLE ET FORESTIÈRE (N)\n" + BODY,
    }
    structure = detect_structure(pages)
    assert structure.method == "headings"
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [("UG", 2, 3), ("N", 4, 4)]


def test_no_running_header_without_a_shared_prefix() -> None:
    assert structure_from_running_headers({1: "ZONE UA\n" + BODY, 2: BODY, 3: "ZONE UB\n" + BODY}) is None


def test_zone_scope_of_paragraphs() -> None:
    codes = ["UA1", "UB1", "UD1", "UD2", "A", "N"]
    assert zone_scope("Dans les zones UB1 et UD1, la hauteur est limitée", codes) == {"UB1", "UD1"}
    assert zone_scope("UD2a Dans une bande d'implantation de 20 m", codes) == {"UD2a"}
    assert zone_scope("En zone A, les constructions sont interdites", codes) == {"A"}
    assert zone_scope("A titre exceptionnel, une hauteur de 12 m", codes) == set()
    assert zone_scope("Les secteurs UD1a et UD1h : 11 m", codes) == {"UD1a", "UD1h"}
    assert scope_applies(set(), "UD1h")
    assert scope_applies({"UB1", "UD1"}, "UD1h")
    assert scope_applies({"UD1a"}, "UD1")
    assert not scope_applies({"UD1a"}, "UD1h")
    assert not scope_applies({"UD2a"}, "UD1a")


def test_quote_across_a_page_break_ignores_running_headers() -> None:
    """Paris S. 66–67: Die Kopfzeile stand mitten im zusammengesetzten Satz (Sollwerte Paris UG, 7)."""
    pages = {
        66: _paris_page(
            66, "Z ONE URBAINE GÉNÉRALE (UG)", "les nus extérieurs de ces façades* doivent, au \n"
        ),
        67: _paris_page(
            67, "Z ONE URBAINE GÉNÉRALE (UG)", "droit de cette baie, être distants de 6 mètres minimum. \n"
        ),
    }
    quote = (
        "les nus extérieurs de ces façades* doivent, au droit de cette baie, être distants de 6 mètres "
        "minimum."
    )
    check = verify_quote(quote, pages, 66)
    assert check.verified and check.page == 66
    with_neighbours = pages | {
        n: _paris_page(n, "Z ONE URBAINE GÉNÉRALE (UG)", "Autre texte sans rapport.") for n in (64, 65, 68)
    }
    assert verify_quote(quote, with_neighbours, 66).verified


def test_evaluation_counts_each_entry_and_the_model_context() -> None:
    pages = _rennes()
    structure = detect_structure(pages)
    entries = parse_entries(
        [
            {
                "kind": "text_only",
                "building_kind": "any",
                "expected": "text_only",
                "page": 9,
                "quote": "Dans les zones UB1 et UD1, les dalles de couverture comportent une épaisseur "
                "de terre de 0,60 m.",
            },
            {
                "kind": "text_only",
                "building_kind": "any",
                "expected": "text_only",
                "page": 9,
                "quote": "En zone UA1, la hauteur des clôtures ne peut excéder 1,50 m.",
            },
            {
                "kind": "setback_side",
                "building_kind": "any",
                "expected": "effective",
                "params": {"min_m": 3.0},
                "page": 16,
                "quote": BODY.strip(),
            },
            {
                "kind": "text_only",
                "building_kind": "any",
                "expected": "text_only",
                "page": 13,
                "quote": "Les constructions doivent être implantées à 3 mètres minimum",
            },
        ]
    )
    report = evaluate_structure(pages, structure, "UD1a", entries)
    layers = [(r.layer, r.reachable) for r in report.results]
    assert layers == [("common", True), ("common", False), ("zone", True), ("other_zone", False)]
    assert report.results[1].problem == "scope:UA1"
    assert report.counts["entries"] == 4 and report.counts["reachable"] == 2
    assert report.counts["in_model"] == 3  # S. 9 liegt in den allgemeinen Seiten, S. 13 nicht

    empty = evaluate_structure(pages, Structure([], [], "none"), "UD1a", entries)
    assert empty.chapter is None and empty.counts["reachable"] == 0
