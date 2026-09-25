"""Planunterlagen als PDF: Seitentexte lesen und Seitenauszüge für das Sprachmodell bilden (Spez. 5.2.3).

`pypdf` (BSD) statt PyMuPDF (AGPL, Spez. 5.2.3 Schritt 1), weil Emprise ein öffentlich erreichbarer
Dienst ist (Annahme in docs/ANNAHMEN.md). PDFs gelten als nicht vertrauenswürdig (Spez. 10.1): Größe und
Seitenzahl sind begrenzt, eingebettete Inhalte werden nicht ausgeführt.
OCR für Seiten ohne Textschicht ist noch nicht eingebaut; solche Seiten zählen als leer und das Modell
liest sie aus dem PDF selbst, die Zitatprüfung scheitert dann aber (Regel `unknown`).
"""

import io
import logging
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PAGES = 1500
EMPTY_PAGE_CHARS = 40

logging.getLogger("pypdf").setLevel(logging.ERROR)


class PdfProblem(ValueError):
    pass


@dataclass(frozen=True)
class PdfText:
    pages: dict[int, str]
    """Seite (1-basiert) → Text."""
    empty_pages: list[int]


def check(data: bytes) -> int:
    """Schnelle Prüfung eines hochgeladenen Reglements, ohne Text zu lesen (AN2): Größe, Kennung,
    Verschlüsselung, Seitenzahl. Liefert die Seitenzahl; den Text liest der Job `rules_document_read`."""
    if len(data) > MAX_PDF_BYTES:
        raise PdfProblem("pdf_too_large")
    if not data.startswith(b"%PDF"):
        raise PdfProblem("not_a_pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        encrypted = reader.is_encrypted
        count = 0 if encrypted else len(reader.pages)
    except Exception as exc:  # Datei aus fremder Hand: jeder Lesefehler heißt „nicht lesbar“
        raise PdfProblem("pdf_unreadable") from exc
    if encrypted:
        raise PdfProblem("pdf_encrypted")
    if count > MAX_PAGES:
        raise PdfProblem("pdf_too_many_pages")
    if count == 0:
        raise PdfProblem("pdf_unreadable")
    return count


def read_text(data: bytes) -> PdfText:
    if len(data) > MAX_PDF_BYTES:
        raise PdfProblem("pdf_too_large")
    if not data.startswith(b"%PDF"):
        raise PdfProblem("not_a_pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfProblem("pdf_encrypted")
        if len(reader.pages) > MAX_PAGES:
            raise PdfProblem("pdf_too_many_pages")
        pages: dict[int, str] = {}
        for index, page in enumerate(reader.pages, start=1):
            try:
                pages[index] = page.extract_text() or ""
            except Exception:
                pages[index] = ""
    except PdfReadError as exc:
        raise PdfProblem("pdf_unreadable") from exc
    empty = [n for n, text in pages.items() if len(text.strip()) < EMPTY_PAGE_CHARS]
    return PdfText(pages, empty)


def extract_pages(data: bytes, pages: list[int]) -> bytes:
    """Neues PDF aus den angegebenen Seiten (1-basiert, in dieser Reihenfolge)."""
    if not pages:
        raise PdfProblem("no_pages")
    try:
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for number in pages:
            if not 1 <= number <= len(reader.pages):
                raise PdfProblem(f"page_out_of_range:{number}")
            writer.add_page(reader.pages[number - 1])
        writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
        buffer = io.BytesIO()
        writer.write(buffer)
    except PdfReadError as exc:
        raise PdfProblem("pdf_unreadable") from exc
    return buffer.getvalue()
