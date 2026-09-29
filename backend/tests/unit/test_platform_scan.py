"""Seiten rendern und Text erkennen (AN7, docs/PLAN_AN7_SCAN.md 4.2): braucht Tesseract mit Französisch."""

import io

import pytest
from PIL import Image

from app.platform import scan
from tests.rules_support import text_pdf
from tests.scan_support import image_bytes, scan_of, text_image

LINES = [
    "ARTICLE UH 10 - HAUTEUR MAXIMALE DES CONSTRUCTIONS",
    "La hauteur des constructions ne peut excéder 7 mètres à l'égout",
    "du toit et 10 mètres au faîtage.",
]


def _words(text: str) -> str:
    return " ".join(text.split()).lower()


def test_recognizes_french_text_on_a_page() -> None:
    page = scan.render(image_bytes(text_image(LINES), dpi=300))
    result = scan.recognize(page)
    text = _words(result.text)
    assert "hauteur maximale des constructions" in text
    assert "excéder 7 mètres" in text
    assert "10 mètres au faîtage" in text
    assert result.confidence > 80


def test_reads_a_page_turned_by_a_quarter() -> None:
    turned = text_image(LINES).rotate(90, expand=True)
    result = scan.recognize(scan.render(image_bytes(turned, dpi=300)))
    assert "hauteur maximale des constructions" in _words(result.text)


def test_blank_page_has_no_text_and_no_confidence() -> None:
    blank = Image.new("L", (1200, 1600), 255)
    result = scan.recognize(scan.render(image_bytes(blank, dpi=300)))
    assert result.text.strip() == ""
    assert result.confidence == 0.0


def test_renders_a_scanned_pdf_with_paper_size() -> None:
    data = scan_of(text_pdf(["Première page", "Deuxième page"]), dpi=150)
    assert scan.kind_of(data) == "pdf"
    assert scan.page_count(data) == 2
    page = scan.render(data, 2, dpi=100)
    assert page.paper_mm == pytest.approx((209.9, 297.0), abs=1.0)
    assert page.image.mode == "L"
    assert max(page.image.size) == pytest.approx(297 / 25.4 * 100, abs=2)
    with pytest.raises(scan.ScanProblem, match="page_out_of_range"):
        scan.render(data, 3)


def test_large_page_is_limited_in_pixels() -> None:
    data = scan_of(text_pdf(["x"]), dpi=72)
    page = scan.render(data, dpi=1200, max_side_px=1000)
    assert max(page.image.size) <= 1000


def test_image_paper_size_only_with_reliable_resolution() -> None:
    image = text_image(["Échelle 1/500"], dpi=200)
    measured = scan.render(image_bytes(image, "JPEG", dpi=200))
    assert measured.paper_mm == pytest.approx((210, 148), abs=0.5)
    assert measured.dpi == pytest.approx(200)
    # 72 dpi schreibt fast jede Kamera und jedes Programm: keine Messung (Plan 7.1 Nr. 14)
    assumed = scan.render(image_bytes(image, "JPEG", dpi=72))
    assert assumed.paper_mm is None
    assert scan.render(image_bytes(image)).paper_mm is None


def test_rejects_other_files_and_oversized_images() -> None:
    with pytest.raises(scan.ScanProblem, match="scan_unsupported"):
        scan.render(b"GIF89a")
    with pytest.raises(scan.ScanProblem, match="pdf_unreadable"):
        scan.render(b"%PDF-1.7 kaputt")
    huge = io.BytesIO()
    Image.new("L", (7000, 6000), 255).save(huge, "PNG")
    with pytest.raises(scan.ScanProblem, match="scan_too_large"):
        scan.render(huge.getvalue())


def test_tsv_keeps_lines_and_paragraphs() -> None:
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    rows = [
        "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t96\tARTICLE",
        "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t90\tUH",
        "5\t1\t1\t1\t2\t1\t0\t0\t1\t1\t80\tHauteur",
        "4\t1\t1\t2\t1\t0\t0\t0\t1\t1\t-1\t",
        "5\t1\t1\t2\t1\t1\t0\t0\t1\t1\t50\t7m",
        "5\t1\t1\t2\t1\t2\t0\t0\t1\t1\t95\t ",
    ]
    result = scan.parse_tsv("\n".join([header, *rows]))
    assert result.text == "ARTICLE UH\nHauteur\n\n7m"
    # nach Länge gewichtet: 7×96 + 2×90 + 7×80 + 2×50 = 1512, geteilt durch 18
    assert result.confidence == pytest.approx(84.0)


def test_jpeg_for_the_browser_is_small() -> None:
    page = scan.render(image_bytes(text_image(LINES), dpi=300))
    data, size = scan.to_jpeg(page, max_side_px=800)
    assert data.startswith(b"\xff\xd8\xff")
    assert max(size) == 800
