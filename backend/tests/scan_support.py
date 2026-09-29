"""Gescannte PDFs und Bilder für die Tests von AN7 (docs/PLAN_AN7_SCAN.md 5), ohne Binärdateien im
Repository: ein PDF mit Textschicht wird gerendert und als reines Bild-PDF wieder zusammengesetzt, wie es ein
Scanner liefert.
"""

import io
from collections.abc import Iterable

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _pages_as_images(pdf: bytes, dpi: int, rotate: float) -> list[Image.Image]:
    document = pdfium.PdfDocument(pdf)
    images: list[Image.Image] = []
    try:
        for index in range(len(document)):
            image = document[index].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
            if rotate:
                image = image.rotate(rotate, expand=True, fillcolor=255)
            # Etwas unscharf wie ein Scanner; JPEG-Artefakte entstehen beim Speichern als PDF
            images.append(image.filter(ImageFilter.GaussianBlur(0.4)))
    finally:
        document.close()
    return images


def scan_of(pdf: bytes, *, dpi: int = 200, rotate: float = 0.0) -> bytes:
    """Dasselbe Dokument als Scan: jede Seite ein Bild, keine Textschicht."""
    images = _pages_as_images(pdf, dpi, rotate)
    buffer = io.BytesIO()
    images[0].save(buffer, "PDF", resolution=dpi, save_all=True, append_images=images[1:])
    return buffer.getvalue()


def with_scanned_pages(pdf: bytes, pages: Iterable[int], *, dpi: int = 200) -> bytes:
    """Dokument mit Textschicht, in dem einzelne Seiten (1-basiert) als Scan eingefügt sind."""
    wanted = set(pages)
    scanned = PdfReader(io.BytesIO(scan_of(pdf, dpi=dpi)))
    original = PdfReader(io.BytesIO(pdf))
    writer = PdfWriter()
    for number, page in enumerate(original.pages, start=1):
        writer.add_page(scanned.pages[number - 1] if number in wanted else page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size_px)
        except OSError:
            continue
    return ImageFont.load_default(size=size_px)


def text_image(
    lines: list[str], *, dpi: int = 300, width_mm: float = 210, height_mm: float = 148
) -> Image.Image:
    """Blatt mit Text in 11 pt, weiß auf schwarz umgekehrt wie gedruckt."""
    width, height = round(width_mm / 25.4 * dpi), round(height_mm / 25.4 * dpi)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    size = round(11 / 72 * dpi)
    face = font(size)
    y = round(20 / 25.4 * dpi)
    for line in lines:
        draw.text((round(20 / 25.4 * dpi), y), line, fill=0, font=face)
        y += round(size * 1.5)
    return image


def image_bytes(image: Image.Image, fmt: str = "PNG", *, dpi: int | None = None) -> bytes:
    buffer = io.BytesIO()
    if dpi is None:
        image.save(buffer, fmt)
    else:
        image.save(buffer, fmt, dpi=(dpi, dpi))
    return buffer.getvalue()
