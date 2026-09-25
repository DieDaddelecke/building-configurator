"""Parzelle aus einem vektoriellen PDF lesen: Katasterauszug, Plan des Geometers (UP13–UP16).

Rein: Bytes hinein, Ringe in Metern heraus. Ein Plan-PDF enthält die Grenzen als Zeichenpfade; aus allen
Linien der ersten Seite mit Linien entstehen über `polygonize` die Flächen des Plans (Parzellen, Gebäude,
Rahmen). Kandidaten sind ihre Außenringe; der Rahmen fällt weg, weil er viele andere Flächen enthält.
Kurze Texte mit einer Ziffer (Parzellennummern) werden der kleinsten Fläche zugeordnet, in der sie stehen.

Der Maßstab kommt aus dem Text („Échelle d'édition : 1/500“, „1:500“) oder von Hand; ohne Maßstab gibt es
keine Meter. Norden gilt als oben auf dem Blatt, eine Lage in Lambert-93 entsteht nicht (UP15).

`pdfminer.six` (MIT) statt PyMuPDF (AGPL) aus demselben Grund wie in `app/rules/pdf.py`. Gescannte PDFs
enthalten keine Linien und werden mit `upload_pdf_no_vector` abgewiesen (UP16).
"""

import io
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Literal

import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from app.site.domain import tolerances as tol

POINT_M = 0.0254 / 72
"""Ein PDF-Punkt auf dem Papier in Metern; mal Maßstabszahl ergibt Meter in der Natur."""
MAX_PAGES = 3
MAX_SEGMENTS = 60_000
MAX_CANDIDATES = 150
NESTED_MAX = 12
"""Enthält eine Fläche mehr Kandidaten, ist sie Blattrahmen oder Kartenausschnitt, keine Parzelle."""
SNAP_PT = 0.01
"""Koordinaten auf 1/100 Punkt runden (1:500 ≈ 2 mm), damit fast gleiche Endpunkte zusammenfallen."""
SCALE_RANGE = (50, 10_000)
LABEL_MAX_CHARS = 10
SCALE_PATTERN = re.compile(r"(?<![\d/])1\s*[/:]\s*(\d{1,2}(?:[ \u00a0\u202f.]?\d{3})|\d{2,5})(?![\d/])")
EDITION_WORDS = ("dition", "impression")
"""„Échelle d'édition“, „Edition“, „Échelle d'impression“: der Maßstab des Papiers, nicht der Erfassung."""


class PdfInvalid(ValueError):
    """Grund, warum das PDF keine Parzelle liefert; `code` wird zum Fehlercode der API."""

    code = "upload_invalid"


class PdfWithoutLines(PdfInvalid):
    code = "upload_pdf_no_vector"


class ScaleMissing(PdfInvalid):
    code = "upload_scale_missing"


class ScaleAmbiguous(PdfInvalid):
    code = "upload_scale_ambiguous"

    def __init__(self, scales: list[int]) -> None:
        super().__init__("Mehrere Maßstäbe im Plan: " + ", ".join(f"1:{s}" for s in scales))
        self.scales = scales


@dataclass(frozen=True)
class Label:
    text: str
    x: float
    y: float


@dataclass
class PdfPage:
    number: int
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    text: str = ""


@dataclass(frozen=True)
class PdfFace:
    polygon: Polygon
    """Außenring in Metern, Nullpunkt unten links auf dem Blatt."""
    name: str | None


@dataclass(frozen=True)
class PdfPlan:
    faces: list[PdfFace]
    scale: int
    scale_source: Literal["file", "input"]
    page: int


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def _snap(point: Iterable[float]) -> tuple[float, float]:
    x, y = tuple(point)[:2]
    return (round(x / SNAP_PT) * SNAP_PT, round(y / SNAP_PT) * SNAP_PT)


def _path_segments(item: Any) -> Iterator[tuple[tuple[float, float], tuple[float, float]]]:
    """Strecken eines Zeichenpfads; Kurven werden durch ihre Endpunkte ersetzt (Grenzen sind gerade)."""
    path = getattr(item, "original_path", None)
    if not path:
        points = [_snap(p) for p in getattr(item, "pts", [])]
        closed = bool(getattr(item, "fill", False)) or type(item).__name__ == "LTRect"
        yield from _polyline(points, closed)
        return
    current: list[tuple[float, float]] = []
    for op in path:
        kind = op[0]
        if kind == "m":
            yield from _polyline(current, False)
            current = [_snap(op[-1])]
        elif kind in ("l", "c", "v", "y"):
            current.append(_snap(op[-1]))
        elif kind == "h":
            yield from _polyline(current, True)
            current = current[:1]
    yield from _polyline(current, bool(getattr(item, "fill", False)))


def _polyline(
    points: list[tuple[float, float]], closed: bool
) -> Iterator[tuple[tuple[float, float], tuple[float, float]]]:
    sequence = [*points, points[0]] if closed and len(points) > 2 else points
    for a, b in pairwise(sequence):
        if a != b:
            yield (a, b)


def read_pages(data: bytes) -> list[PdfPage]:
    """Linien und Texte der ersten Seiten. Hebt `PdfInvalid`, wenn das PDF nicht lesbar ist."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTCurve, LTTextLine
    from pdfminer.pdfparser import PDFSyntaxError
    from pdfminer.psexceptions import PSException

    pages: list[PdfPage] = []
    segments = 0

    def walk(node: Any, page: PdfPage) -> None:
        nonlocal segments
        if isinstance(node, LTCurve):
            for segment in _path_segments(node):
                page.segments.append(segment)
                segments += 1
                if segments > MAX_SEGMENTS:
                    raise PdfInvalid("Der Plan enthält zu viele Linien")
            return
        if isinstance(node, LTTextLine):
            text = node.get_text().strip()
            page.text += text + "\n"
            if 0 < len(text) <= LABEL_MAX_CHARS and any(c.isdigit() for c in text):
                x0, y0, x1, y1 = node.bbox
                page.labels.append(Label(text, (x0 + x1) / 2, (y0 + y1) / 2))
            return
        if hasattr(node, "__iter__"):
            for child in node:
                walk(child, page)

    try:
        for number, layout in enumerate(
            extract_pages(io.BytesIO(data), maxpages=MAX_PAGES, laparams=LAParams(all_texts=True)), start=1
        ):
            page = PdfPage(number=number)
            walk(layout, page)
            pages.append(page)
    except (PDFSyntaxError, PSException, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, PdfInvalid):
            raise
        raise PdfInvalid("Die Datei ist kein lesbares PDF") from None
    if not pages:
        raise PdfInvalid("Das PDF hat keine Seite")
    return pages


# ---------------------------------------------------------------------------
# Maßstab
# ---------------------------------------------------------------------------


def scales_in_text(text: str) -> tuple[list[int], int | None]:
    """Alle plausiblen Maßstabszahlen im Text und – falls benannt – der Maßstab der Ausgabe.

    Katasterauszüge nennen zwei: „Échelle d'origine : 1/1000“ (Erfassung) und „Échelle d'édition :
    1/500“ (Papier). Maßgeblich für die Geometrie im PDF ist die Ausgabe."""
    found: list[int] = []
    edition: int | None = None
    for match in SCALE_PATTERN.finditer(text):
        value = int(re.sub(r"\D", "", match.group(1)))
        if not SCALE_RANGE[0] <= value <= SCALE_RANGE[1]:
            continue
        if value not in found:
            found.append(value)
        # Das letzte Stichwort vor der Zahl entscheidet: „d'édition : 1/500“ gegen „d'origine : 1/1000“
        before = text[max(0, match.start() - 40) : match.start()].lower()
        if max(before.rfind(word) for word in EDITION_WORDS) > before.rfind("origine"):
            edition = value
    return found, edition


def resolve_scale(pages: list[PdfPage], given: int | None) -> tuple[int, Literal["file", "input"]]:
    if given is not None:
        if not SCALE_RANGE[0] <= given <= SCALE_RANGE[1]:
            raise PdfInvalid("Maßstab außerhalb von 1:50 bis 1:10000")
        return given, "input"
    found, edition = scales_in_text("\n".join(page.text for page in pages))
    if edition is not None:
        return edition, "file"
    if len(found) == 1:
        return found[0], "file"
    if not found:
        raise ScaleMissing("Kein Maßstab im Plan gefunden")
    raise ScaleAmbiguous(sorted(found))


# ---------------------------------------------------------------------------
# Flächen
# ---------------------------------------------------------------------------


def _faces_in_points(page: PdfPage) -> list[Polygon]:
    lines = [LineString(segment) for segment in dict.fromkeys(page.segments)]
    noded = shapely.unary_union(lines)
    polygons = shapely.get_parts(shapely.polygonize(shapely.get_parts(noded)))
    exteriors: dict[bytes, Polygon] = {}
    for polygon in polygons:
        if polygon.is_empty or polygon.area <= 0:
            continue
        outer = Polygon(polygon.exterior)
        key = shapely.to_wkb(shapely.normalize(shapely.set_precision(outer, SNAP_PT)))
        exteriors.setdefault(key, outer)
    return list(exteriors.values())


def _without_frames(polygons: list[Polygon]) -> list[int]:
    """Indizes ohne Blattrahmen und Kartenausschnitte: Die enthalten viele Flächen, eine Parzelle höchstens
    ihre Gebäude."""
    tree = STRtree(polygons)
    return [
        i
        for i, polygon in enumerate(polygons)
        if sum(1 for j in tree.query(polygon, predicate="contains_properly") if j != i) <= NESTED_MAX
    ]


def _name_faces(polygons: list[Polygon], labels: list[Label]) -> list[str | None]:
    """Jede Beschriftung gehört zur kleinsten Fläche, in der sie steht."""
    names: list[list[str]] = [[] for _ in polygons]
    order = sorted(range(len(polygons)), key=lambda i: polygons[i].area)
    for label in labels:
        point = Point(label.x, label.y)
        for i in order:
            if polygons[i].contains(point):
                names[i].append(label.text)
                break
    return [" ".join(sorted(set(n)))[:40] or None for n in names]


def read_plan(data: bytes, scale: int | None = None) -> PdfPlan:
    """Kandidaten aus der ersten Seite mit Linien, in Metern (Maßstab aus dem Text oder von Hand)."""
    pages = read_pages(data)
    page = next((p for p in pages if len(p.segments) >= 3), None)
    if page is None:
        raise PdfWithoutLines("Das PDF enthält keine Linien – vermutlich ein Scan")
    value, source = resolve_scale(pages, scale)
    factor = POINT_M * value

    polygons = _faces_in_points(page)
    # Fläche erst in Metern prüfen: dieselbe Schranke wie bei Weg E und den übrigen Uploads (G28)
    in_metres = [affinity.scale(p, factor, factor, origin=(0, 0)) for p in polygons]
    plausible = [
        (points, metres)
        for points, metres in zip(polygons, in_metres, strict=True)
        if tol.MANUAL_MIN_AREA_M2 <= metres.area <= tol.MANUAL_MAX_AREA_M2
    ]
    if not plausible:
        raise PdfInvalid(
            f"Bei 1:{value} ergibt keine geschlossene Fläche eine plausible Parzelle (20–50 000 m²)"
        )
    kept = [plausible[i] for i in _without_frames([points for points, _ in plausible])]
    names = _name_faces([points for points, _ in kept], page.labels)
    faces = [PdfFace(polygon=metres, name=name) for (_, metres), name in zip(kept, names, strict=True)]
    # Beschriftete Flächen (Parzellennummern) zuerst, dann nach Größe; zu viele Kandidaten kappen
    faces.sort(key=lambda f: (f.name is None, -f.polygon.area))
    return PdfPlan(faces=faces[:MAX_CANDIDATES], scale=value, scale_source=source, page=page.number)
