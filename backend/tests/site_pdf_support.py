"""Vektorielle Plan-PDFs für die Tests des PDF-Uploads (UP13–UP16), gesetzt mit WeasyPrint.

Die Zeichnung ist in Millimetern auf dem Papier angegeben: Bei 1:500 ist 1 mm = 0,5 m in der Natur. So sind
die erwarteten Flächen exakt bekannt, ohne Beispieldateien im Repository.
"""

from collections.abc import Sequence

from weasyprint import HTML


def rect(x: float, y: float, w: float, h: float, *, fill: str = "none", width: float = 0.3) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="black" '
        f'stroke-width="{width}"/>'
    )


def polygon(points: list[tuple[float, float]], *, width: float = 0.3) -> str:
    coords = " ".join(f"{x},{y}" for x, y in points)
    return f'<polygon points="{coords}" fill="none" stroke="black" stroke-width="{width}"/>'


def label(x: float, y: float, text: str) -> str:
    return f'<text x="{x}" y="{y}" font-size="3.5">{text}</text>'


def plan_pdf(shapes: list[str], header: str = "", width_mm: int = 180, height_mm: int = 150) -> bytes:
    """Ein Blatt mit Kopfzeile (etwa dem Maßstab) und einer Zeichnung in Millimetern."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" '
        f'viewBox="0 0 {width_mm} {height_mm}">{"".join(shapes)}</svg>'
    )
    html = f'<html><body style="margin:0"><p style="font-size:9pt">{header}</p>{svg}</body></html>'
    return HTML(string=html).write_pdf()


EXTRACT_HEADER = "Échelle d'origine : 1/1000 · Échelle d'édition : 1/500"
"""Wie auf einem Auszug von cadastre.gouv.fr: Erfassungs- und Ausgabemaßstab."""


def extract_pdf(header: str = EXTRACT_HEADER, extra: Sequence[str] = ()) -> bytes:
    """Katasterauszug im Kleinen: Parzelle 65 (20 × 30 m) mit Haus, Nachbar 66 (12 × 30 m), bei 1:500.
    `extra` zeichnet weitere Linien darüber (etwa eine, die Parzelle und Haus zerschneidet)."""
    return plan_pdf(
        [
            polygon([(20, 20), (60, 20), (60, 80), (20, 80)]),
            polygon([(60, 20), (84, 20), (84, 80), (60, 80)]),
            rect(30, 40, 16, 12, fill="#ccc", width=0.2),
            label(38, 30, "65"),
            label(70, 30, "66"),
            *extra,
        ],
        header,
    )
