"""Parzelle aus einem vektoriellen PDF, ohne Datenbank (UP13–UP16, UP19, `app/site/domain/pdfplan.py`)."""

import pytest

from app.site.domain import pdfplan
from tests.site_pdf_support import extract_pdf, filled, label, plan_pdf, polygon, rect


def by_name(plan: pdfplan.PdfPlan) -> dict[str | None, float]:
    return {face.name: round(face.polygon.area, 1) for face in plan.faces}


def test_cadastre_extract_uses_the_edition_scale_and_names_parcels() -> None:
    plan = pdfplan.read_plan(extract_pdf())
    assert (plan.scale, plan.scale_source, plan.page) == (500, "file", 1)
    areas = by_name(plan)
    assert areas["65"] == pytest.approx(600.0, rel=0.002)
    assert areas["66"] == pytest.approx(360.0, rel=0.002)
    # Das Haus ist eine eigene Fläche ohne Nummer; die Parzelle bleibt trotz Haus ganz (Außenring)
    assert areas[None] == pytest.approx(48.0, rel=0.005)
    # Beschriftete Flächen stehen vorn
    assert [face.name for face in plan.faces] == ["65", "66", None]


def test_given_scale_wins_over_the_text() -> None:
    plan = pdfplan.read_plan(extract_pdf(), scale=1000)
    assert (plan.scale, plan.scale_source) == (1000, "input")
    assert by_name(plan)["65"] == pytest.approx(2400.0, rel=0.002)


def test_without_scale_the_plan_cannot_be_measured() -> None:
    with pytest.raises(pdfplan.ScaleMissing):
        pdfplan.read_plan(extract_pdf(header="Plan de situation"))


def test_two_scales_without_edition_are_ambiguous() -> None:
    with pytest.raises(pdfplan.ScaleAmbiguous) as caught:
        pdfplan.read_plan(extract_pdf(header="Plan 1/500 – Situation 1/2000"))
    assert caught.value.scales == [500, 2000]


def test_a_pdf_without_lines_is_taken_for_a_scan() -> None:
    with pytest.raises(pdfplan.PdfWithoutLines):
        pdfplan.read_plan(plan_pdf([label(20, 20, "65")], "Échelle 1/500"))


def test_sheet_frame_is_not_a_candidate() -> None:
    """Ein Blattrahmen umschließt alle Parzellen und fällt deshalb weg (NESTED_MAX)."""
    grid = [rect(20 + 20 * col, 20 + 20 * row, 20, 20) for row in range(4) for col in range(4)]
    plan = pdfplan.read_plan(plan_pdf([rect(10, 10, 100, 100), *grid], "Échelle 1/500"))
    # 16 Parzellen zu je 10 × 10 m; die Fläche zwischen Rahmen und Parzellen hat den Rahmen als
    # Außenring und fällt mit ihm weg
    assert sorted(round(face.polygon.area) for face in plan.faces) == [100] * 16
    assert all(face.polygon.area < 2500 for face in plan.faces)


def test_geometer_plan_with_a_slanted_parcel() -> None:
    """Ein schiefes Viereck wie auf einem Bornage-Plan, bei 1:200."""
    points = [(20, 20), (95, 25), (100, 90), (15, 80)]
    plan = pdfplan.read_plan(plan_pdf([polygon(points), label(55, 50, "AB 12")], "Échelle : 1/200"))
    # Gaußsche Trapezformel in Millimetern auf dem Papier, dann (0,2 m/mm)²
    xs, ys = zip(*points, strict=True)
    paper = abs(sum(xs[i] * ys[(i + 1) % 4] - xs[(i + 1) % 4] * ys[i] for i in range(4))) / 2
    assert by_name(plan)["AB 12"] == pytest.approx(paper * 0.2 * 0.2, rel=0.002)


def test_lettering_drawn_as_outlines_does_not_notch_the_parcel() -> None:
    """Auf der Südgrenze von 65 (y = 80 mm) je eine Form, 2 mm in die Parzelle hinein (bei 1:500 1 m): Der
    kleine schwarze Buchstabe zählt nicht (UP19); die große schwarze Form (24 mm) und die farbige (Gebäude)
    schon."""
    extra = [filled(22, 78, 3, 4, "black"), filled(28, 78, 24, 4, "black"), filled(54, 78, 3, 4, "#fc3")]
    plan = pdfplan.read_plan(extract_pdf(extra=extra))
    # 600 m² ohne die Kerben der großen Form (12 × 1 m) und des Gebäudes (1,5 × 1 m)
    assert by_name(plan)["65"] == pytest.approx(600.0 - 12.0 - 1.5, rel=0.002)


def test_lettering_counts_when_nothing_else_forms_a_face() -> None:
    # Nur eine schwarze Fläche von 9 mm; bei 1:5000 sind das 45 × 45 m
    plan = pdfplan.read_plan(plan_pdf([filled(20, 20, 9, 9, "black")], "Échelle 1/5000"))
    assert [round(face.polygon.area) for face in plan.faces] == [2025]


@pytest.mark.parametrize(
    ("colour", "dark"),
    [
        (None, True),
        (0.0, True),
        (0.2, True),
        (0.5, False),
        ((0.0, 0.0, 0.0), True),
        ((1.0, 0.8, 0.2), False),
        ((1.0, 0.898, 0.6), False),
        ((0.0, 0.0, 0.0, 1.0), True),
        ((0.0, 0.0, 0.0, 0.0), False),
        ("P0", False),
    ],
)
def test_dark_fill_colours(colour: object, dark: bool) -> None:
    assert pdfplan._is_dark(colour) is dark


@pytest.mark.parametrize(
    ("text", "found", "edition"),
    [
        ("Échelle 1/500", [500], None),
        ("Echelle : 1 : 1 000", [1000], None),
        ("Échelle d'origine : 1/1000\nÉchelle d'édition : 1/500", [1000, 500], 500),
        ("Édité le 21/09/2026 – 1/10", [], None),
        ("Plan 1/250e", [250], None),
    ],
)
def test_scales_in_text(text: str, found: list[int], edition: int | None) -> None:
    assert pdfplan.scales_in_text(text) == (found, edition)


def test_broken_pdf_is_rejected() -> None:
    with pytest.raises(pdfplan.PdfInvalid):
        pdfplan.read_plan(b"%PDF-1.7\nkaputt")
