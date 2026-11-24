"""Messung an echten Reglements ohne Modell (BESTANDSAUFNAHME_PLU_PIPELINE S1, S2): Gliederung und
Erreichbarkeit der Sollwerte von Paris UG und Rennes UD1a/UD1h.

Die PDFs liegen nicht in Git (`plu-proben/`, wie `ifc-proben/`); ohne sie werden die Tests übersprungen.
Ordner über `EMPRISE_PLU_PROBEN` oder `plu-proben/` im Wurzelordner des Repositorys. Laufzeit etwa 10 s je
Dokument (pypdf liest wie das Produkt).
"""

import os
from functools import cache
from pathlib import Path

import pytest

from app.rules import pdf, reference
from app.rules.domain.chapters import Structure, detect_structure
from app.rules.domain.evaluation import evaluate_structure

SAMPLES = Path(os.environ.get("EMPRISE_PLU_PROBEN", Path(__file__).resolve().parents[3] / "plu-proben"))
PARIS = "paris_plu_reglement_tome1_2025-12.pdf"
RENNES = "rennes_metropole_plui_reglement_mod2_2025-06.pdf"


@cache
def _read(name: str) -> tuple[dict[int, str], Structure]:
    path = SAMPLES / name
    if not path.exists():
        pytest.skip(f"Probedatei fehlt: {path}")
    pages = pdf.read_text(path.read_bytes()).pages
    return pages, detect_structure(pages)


def test_paris_structure() -> None:
    _pages, structure = _read(PARIS)
    assert structure.method == "running_headers"
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [
        ("UG", 38, 124),
        ("UGSU", 125, 170),
        ("UV", 171, 200),
        ("N", 201, 222),
    ]
    assert structure.common_pages == list(range(20, 37))
    # Hauptbaubande (S. 25) und Modalités gehen mit jeder Zone an das Modell
    assert set(range(6, 37)) <= set(structure.general_pages)


def test_rennes_structure() -> None:
    _pages, structure = _read(RENNES)
    assert structure.method == "running_headers"
    assert len(structure.chapters) == 31
    chapters = {c.code: (c.first_page, c.last_page) for c in structure.chapters}
    assert chapters["UA1"] == (138, 140) and chapters["UD1"] == (152, 156) and chapters["NP"] == (200, 201)
    # Titre IV „Règles littérales applicables à toutes les zones“ (S. 93–136) gehört zu den Regeln für alle
    assert set(range(93, 137)) <= set(structure.common_pages)


@pytest.mark.parametrize(
    ("name", "lists"),
    [(PARIS, ["paris_ug.json"]), (RENNES, ["rennes_ud1a.json", "rennes_ud1h.json"])],
)
def test_every_reference_entry_is_reachable(name: str, lists: list[str]) -> None:
    """Jeder Sollwert, auch jede Variante, ist belegt und der Zone zugeordnet (Kapitel oder alle Zonen)."""
    pages, structure = _read(name)
    for list_name in lists:
        ref = reference.load_file(reference.SEED_DIR / list_name)
        report = evaluate_structure(pages, structure, ref.sector, ref.entries)
        problems = [(r.entry.page, r.problem) for r in report.results if r.problem]
        assert not problems, f"{list_name}: {problems}"
        assert report.counts["reachable"] == len(ref.entries)
