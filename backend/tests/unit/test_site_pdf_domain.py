"""Parzelle aus einem vektoriellen PDF, ohne Datenbank (UP13–UP16, `app/site/domain/pdfplan.py`)."""

import pytest

from app.site.domain import pdfplan
from tests.site_pdf_support import extract_pdf, label, plan_pdf, polygon, rect


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
