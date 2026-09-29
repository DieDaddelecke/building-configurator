"""Gescannte Unterlagen: Seiten als Bild rendern und Text erkennen (AN7, docs/PLAN_AN7_SCAN.md).

Rein technisch, ohne Datenbank und Fachlogik; genutzt vom Reglement (`rules/ocr.py`) und vom Nachzeichnen
einer Parzelle (`site/service.py`). PDF über `pypdfium2` (BSD-3/Apache-2.0; PyMuPDF bleibt wegen der AGPL
draußen, wie in `rules/pdf.py`), Bilder über Pillow, Texterkennung mit Tesseract als eigener Prozess:
`-l fra --psm 1` liest auch um 90° gedrehte Seiten (gemessen, Plan 2). Dateien kommen aus fremder Hand
(Spez. 10.1): Pixelobergrenze, Zeitlimit je Seite, an Tesseract gehen nur selbst erzeugte PNG.
"""

import io
import os
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

import pypdfium2 as pdfium
from PIL import Image, ImageOps

OCR_DPI = 300
"""Auflösung für die Erkennung; Tesseract liest Fließtext bei 300 dpi am besten."""
MAX_PIXELS = 40_000_000
"""Größtes Bild, das gerendert oder geöffnet wird (A0 bei 150 dpi ≈ 35 Mio. Pixel)."""
MAX_SIDE_PX = 5000
OCR_TIMEOUT_SECONDS = 60
OCR_LANGUAGE = "fra"
MIN_IMAGE_DPI = 150
"""Darunter ist eine dpi-Angabe eine Vorgabe von Kamera oder Programm (72, 96), keine Messung
(Plan 7.1 Nr. 14)."""
PT_MM = 25.4 / 72

Kind = Literal["pdf", "image"]


class ScanProblem(ValueError):
    """Grund, warum eine Seite nicht gerendert oder gelesen werden kann; der Text ist der Fehlercode
    der API."""


@dataclass(frozen=True)
class Page:
    image: Image.Image
    """Graustufen."""
    dpi: float
    """Auflösung des Bilds bezogen auf das Papier; bei Bildern ohne verlässliche Angabe `OCR_DPI`."""
    paper_mm: tuple[float, float] | None
    """Breite und Höhe des Blatts; None, wenn das Bild keine verlässliche Auflösung trägt."""


@dataclass(frozen=True)
class Recognized:
    text: str
    confidence: float
    """Mittlere Sicherheit der erkannten Wörter, 0–100; 0 ohne Wörter."""


def kind_of(data: bytes) -> Kind:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    raise ScanProblem("scan_unsupported")


def _pdf(data: bytes) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        # Passwortschutz und defekte Dateien melden sich gleich; beides heißt „nicht lesbar“
        raise ScanProblem("pdf_unreadable") from exc


def page_count(data: bytes) -> int:
    if kind_of(data) == "image":
        return 1
    document = _pdf(data)
    try:
        return len(document)
    finally:
        document.close()


def render(data: bytes, page: int = 1, *, dpi: float = OCR_DPI, max_side_px: int = MAX_SIDE_PX) -> Page:
    """Seite (1-basiert) als Graustufenbild, höchstens `max_side_px` an der langen Seite."""
    if kind_of(data) == "image":
        if page != 1:
            raise ScanProblem("page_out_of_range")
        return _image(data, max_side_px)
    document = _pdf(data)
    try:
        if not 1 <= page <= len(document):
            raise ScanProblem("page_out_of_range")
        pdf_page = document[page - 1]
        width_pt, height_pt = pdf_page.get_size()
        if width_pt <= 0 or height_pt <= 0:
            raise ScanProblem("pdf_unreadable")
        scale = min(dpi / 72, max_side_px / max(width_pt, height_pt))
        if width_pt * height_pt * scale * scale > MAX_PIXELS:
            scale = (MAX_PIXELS / (width_pt * height_pt)) ** 0.5
        try:
            image = pdf_page.render(scale=scale, grayscale=True).to_pil().convert("L")
        except pdfium.PdfiumError as exc:
            raise ScanProblem("pdf_unreadable") from exc
        return Page(image, scale * 72, (round(width_pt * PT_MM, 1), round(height_pt * PT_MM, 1)))
    finally:
        document.close()


def _image(data: bytes, max_side_px: int) -> Page:
    try:
        opened = Image.open(io.BytesIO(data))
        width, height = opened.size
        if width * height > MAX_PIXELS:
            raise ScanProblem("scan_too_large")
        dpi_info = opened.info.get("dpi")
        image = ImageOps.exif_transpose(opened).convert("L")
    except ScanProblem:
        raise
    except Exception as exc:  # Datei aus fremder Hand: jeder Lesefehler heißt „nicht lesbar“
        raise ScanProblem("scan_unreadable") from exc
    dpi = float(dpi_info[0]) if isinstance(dpi_info, tuple) and dpi_info and dpi_info[0] else 0.0
    paper: tuple[float, float] | None = None
    if dpi >= MIN_IMAGE_DPI:
        paper = (round(image.width / dpi * 25.4, 1), round(image.height / dpi * 25.4, 1))
    else:
        dpi = OCR_DPI
    longest = max(image.size)
    if longest > max_side_px:
        factor = max_side_px / longest
        image = image.resize(
            (round(image.width * factor), round(image.height * factor)), Image.Resampling.LANCZOS
        )
        dpi *= factor
    return Page(image, dpi, paper)


def recognize(page: Page) -> Recognized:
    """Text der Seite mit Tesseract. Wörter nach Block, Absatz und Zeile wieder zusammengesetzt; Absätze durch
    eine Leerzeile getrennt, damit die Kapitelsuche Überschriften wie in einer Textschicht findet."""
    program = shutil.which("tesseract")
    if program is None:
        raise ScanProblem("ocr_unavailable")
    buffer = io.BytesIO()
    page.image.save(buffer, "PNG")
    try:
        result = subprocess.run(  # noqa: S603  feste Argumente, Bild über die Standardeingabe
            [
                program,
                "stdin",
                "stdout",
                "-l",
                OCR_LANGUAGE,
                "--psm",
                "1",
                "--dpi",
                str(round(page.dpi)),
                "tsv",
            ],
            input=buffer.getvalue(),
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=True,
            # Mehr Threads bringen kaum etwas und nähmen API und Datenbank Rechenzeit (Plan 3.6)
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        )
    except FileNotFoundError as exc:
        raise ScanProblem("ocr_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScanProblem("ocr_timeout") from exc
    except subprocess.CalledProcessError as exc:
        raise ScanProblem("ocr_failed") from exc
    return parse_tsv(result.stdout.decode("utf-8", errors="replace"))


def parse_tsv(tsv: str) -> Recognized:
    """Ausgabe `tsv` von Tesseract: eine Zeile je Element; Wörter haben Ebene 5 und eine Sicherheit ≥ 0."""
    lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    order: list[tuple[int, int, int]] = []
    confidences: list[tuple[float, int]] = []
    for row in tsv.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or cells[0] != "5":
            continue
        word = cells[11].strip()
        try:
            confidence = float(cells[10])
        except ValueError:
            continue
        if not word or confidence < 0:
            continue
        key = (int(cells[2]), int(cells[3]), int(cells[4]))
        if key not in lines:
            order.append(key)
        lines[key].append(word)
        confidences.append((confidence, len(word)))
    parts: list[str] = []
    previous: tuple[int, int] | None = None
    for key in order:
        paragraph = (key[0], key[1])
        if previous is not None and paragraph != previous:
            parts.append("")
        parts.append(" ".join(lines[key]))
        previous = paragraph
    total = sum(length for _, length in confidences)
    mean = sum(value * length for value, length in confidences) / total if total else 0.0
    return Recognized("\n".join(parts), round(mean, 1))


def to_jpeg(page: Page, *, max_side_px: int = 2500, quality: int = 80) -> tuple[bytes, tuple[int, int]]:
    """Bild für die Anzeige im Browser (Nachzeichnen) und seine Größe in Pixeln."""
    image = page.image
    longest = max(image.size)
    if longest > max_side_px:
        factor = max_side_px / longest
        image = image.resize(
            (round(image.width * factor), round(image.height * factor)), Image.Resampling.LANCZOS
        )
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue(), image.size
