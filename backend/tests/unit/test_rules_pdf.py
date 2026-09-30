"""Scan-Erkennung beim Lesen eines Reglements, ohne PDF (SC01; REFACTORING_PLAN S17)."""

from app.rules import pdf

TEXT = "Article UB 6 – Implantation des constructions par rapport aux voies"


def test_short_pages_count_as_empty() -> None:
    pages = {1: TEXT, 2: "", 3: "  page 3  ", 4: TEXT}
    assert pdf.empty_pages(pages) == [2, 3]


def test_a_scan_has_more_than_half_of_its_pages_without_text() -> None:
    assert not pdf.is_scan({1: TEXT, 2: ""})  # genau die Hälfte: lesbar, Erkennung auf Wunsch
    assert pdf.is_scan({1: TEXT, 2: "", 3: ""})
    assert pdf.is_scan({})
