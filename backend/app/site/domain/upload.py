"""Parzelle aus einer Datei lesen: DXF, GeoJSON und vektorielles PDF (AN1, docs/PLAN_AN1_PARZELLE.md 3.2, 8).

Rein: Bytes hinein, Ringe heraus – keine Datenbank, kein Netz. Das Koordinatensystem wird an der
Größenordnung erkannt (E-AN1-3); wird keines erkannt, gilt der Umriss als Zeichnung ohne geografischen
Bezug (wie Weg E, G26). Die Umrechnung von WGS84 nach Lambert-93 macht PostGIS, wie überall im Modul:
`build_candidates` bekommt sie als Funktion übergeben. PDFs liest `pdfplan` – dort braucht es einen
Maßstab, und ihre Flächen haben nie eine Lage.

Was bewusst fehlt: DWG (E-A2), gescannte PDFs (UP16), Löcher im Umriss, das Zusammenführen mehrerer
Konturen zu einem Grundstück (E-A3).
"""

import io
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from app.site.domain import tolerances as tol

Crs = Literal["EPSG:2154", "EPSG:4326", "local"]
Coord = tuple[float, float]
ToMetres = Callable[[list[Coord]], list[Coord]]
"""Rechnet WGS84-Punkte in Lambert-93-Meter um (in der Anwendung PostGIS `ST_Transform`)."""

MAX_VERTICES = 2000
"""Stützpunkte je Kontur. `split_edges` fasst zusammen, deshalb ist die Kantenzahl nicht begrenzt."""
MAX_CANDIDATES = 50
L93_BOUNDS = (100_000.0, 6_000_000.0, 1_300_000.0, 7_200_000.0)
"""Lambert-93 über Frankreich (x, y): alles darin gilt als georeferenziert."""
WGS84_BOUNDS = (-5.5, 41.0, 10.0, 51.5)
"""Wie `LookupIn` in den Schemas: Festland und Korsika."""
DXF_UNIT_FACTOR: dict[int, float] = {0: 1.0, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 21: 0.3048}
"""`$INSUNITS` → Meter. 0 = ohne Angabe, dann Meter angenommen."""


class UploadInvalid(ValueError):
    """Die Datei lässt sich nicht als Parzelle lesen. `code` wird zum Fehlercode der API, `extra` zu
    zusätzlichen Feldern der Antwort (etwa die gefundenen Maßstäbe)."""

    def __init__(self, message: str, code: str = "upload_invalid", **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


FileFormat = Literal["dxf", "geojson", "pdf"]


@dataclass(frozen=True)
class ParcelFile:
    """Was aus einer Datei kam: Ringe, Format und – nur bei PDF – Maßstab und Seite."""

    rings: list["RawRing"]
    format: FileFormat
    scale: int | None = None
    scale_source: Literal["file", "input"] | None = None
    page: int | None = None


@dataclass(frozen=True)
class RawRing:
    """Geschlossener Ring, wie er in der Datei steht (DXF bereits in Meter umgerechnet)."""

    index: int
    points: list[Coord]
    crs: Crs
    layer: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class Candidate:
    """Geprüfte Kontur in Metern: gültig, gegen den Uhrzeigersinn, mit Fläche."""

    index: int
    polygon: Polygon
    area_m2: float
    crs: Crs
    layer: str | None = None
    name: str | None = None

    @property
    def georeferenced(self) -> bool:
        return self.crs != "local"


def _bbox(ring: Sequence[Coord]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return (min(xs), min(ys), max(xs), max(ys))


def detect_crs(ring: Sequence[Coord]) -> Crs:
    """Koordinatensystem an der Größenordnung erkennen. Im Zweifel `local`."""
    x0, y0, x1, y1 = _bbox(ring)
    for bounds, crs in ((L93_BOUNDS, "EPSG:2154"), (WGS84_BOUNDS, "EPSG:4326")):
        if bounds[0] <= x0 and bounds[1] <= y0 and x1 <= bounds[2] and y1 <= bounds[3]:
            return crs  # type: ignore[return-value]
    return "local"


def _clean(raw: Sequence[Any], factor: float = 1.0) -> list[Coord] | None:
    """Doppelte und den schließenden Punkt entfernen; nur endliche Zahlen."""
    points: list[Coord] = []
    for item in raw:
        try:
            x, y = float(item[0]) * factor, float(item[1]) * factor
        except (TypeError, ValueError, IndexError, KeyError):
            return None
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        if not points or math.dist(points[-1], (x, y)) > tol.MIN_SEGMENT_M:
            points.append((x, y))
    if len(points) > 1 and math.dist(points[0], points[-1]) <= tol.MIN_SEGMENT_M:
        points.pop()
    if not 3 <= len(points) <= MAX_VERTICES:
        return None
    return points


def _ring(
    index: int, raw: Sequence[Any], *, factor: float = 1.0, layer: str | None = None, name: str | None = None
) -> RawRing | None:
    points = _clean(raw, factor)
    if points is None:
        return None
    return RawRing(index=index, points=points, crs=detect_crs(points), layer=layer, name=name)


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def _geojson_rings(node: Any, found: list[tuple[list[Any], str | None]]) -> None:
    """Sammelt äußere Ringe aus Geometrie, Feature oder FeatureCollection (rekursiv)."""
    if not isinstance(node, dict) or len(found) >= MAX_CANDIDATES:
        return
    kind = node.get("type")
    if kind == "FeatureCollection":
        for feature in node.get("features") or []:
            _geojson_rings(feature, found)
    elif kind == "Feature":
        name = None
        properties = node.get("properties")
        if isinstance(properties, dict):
            name = next(
                (
                    properties[k]
                    for k in ("idu", "name", "nom", "label")
                    if isinstance(properties.get(k), str)
                ),
                None,
            )
        before = len(found)
        _geojson_rings(node.get("geometry"), found)
        for i in range(before, len(found)):
            found[i] = (found[i][0], name)
    elif kind == "Polygon":
        coordinates = node.get("coordinates") or []
        if coordinates:
            found.append((coordinates[0], None))
    elif kind == "MultiPolygon":
        for polygon in node.get("coordinates") or []:
            if polygon:
                found.append((polygon[0], None))
    elif kind == "GeometryCollection":
        for geometry in node.get("geometries") or []:
            _geojson_rings(geometry, found)


def read_geojson(data: bytes) -> list[RawRing]:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UploadInvalid("Die Datei ist kein lesbares GeoJSON") from None
    found: list[tuple[list[Any], str | None]] = []
    _geojson_rings(document, found)
    if not found:
        raise UploadInvalid("Kein Polygon in der Datei")
    rings = [_ring(i, raw, name=name) for i, (raw, name) in enumerate(found)]
    return [r for r in rings if r is not None]


# ---------------------------------------------------------------------------
# DXF
# ---------------------------------------------------------------------------


def read_dxf(data: bytes) -> list[RawRing]:
    import ezdxf  # lokal: nur dieser Weg braucht die Bibliothek
    from ezdxf.entities import LWPolyline, Polyline
    from ezdxf.lldxf.const import DXFError

    document = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            document = ezdxf.read(io.StringIO(data.decode(encoding)))
            break
        except UnicodeDecodeError:
            continue
        except DXFError:
            raise UploadInvalid("Die Datei ist kein lesbares DXF") from None
    if document is None:
        raise UploadInvalid("Die Datei ist kein lesbares DXF")

    factor = DXF_UNIT_FACTOR.get(int(document.header.get("$INSUNITS", 0) or 0))
    if factor is None:
        raise UploadInvalid("Einheit der Zeichnung wird nicht unterstützt")

    found: list[tuple[list[Coord], str | None]] = []
    for entity in document.modelspace():
        if isinstance(entity, LWPolyline) and entity.closed:
            points = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
        elif isinstance(entity, Polyline) and entity.is_closed and not entity.is_poly_face_mesh:
            points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
        else:
            continue
        found.append((points, str(entity.dxf.layer)))
        if len(found) >= MAX_CANDIDATES:
            break
    if not found:
        raise UploadInvalid("Keine geschlossene Polylinie in der Zeichnung")
    rings = [_ring(i, raw, factor=factor, layer=layer) for i, (raw, layer) in enumerate(found)]
    return [r for r in rings if r is not None]


# ---------------------------------------------------------------------------
# Gemeinsamer Eingang
# ---------------------------------------------------------------------------


def read_pdf(data: bytes, scale: int | None) -> ParcelFile:
    """Flächen eines vektoriellen Plans als Ringe in Metern, ohne Lage (UP13–UP16)."""
    from app.site.domain import pdfplan

    try:
        plan = pdfplan.read_plan(data, scale)
    except pdfplan.ScaleAmbiguous as exc:
        raise UploadInvalid(str(exc), exc.code, scales=exc.scales) from None
    except pdfplan.PdfInvalid as exc:
        raise UploadInvalid(str(exc), exc.code) from None
    rings = [
        RawRing(
            index=i,
            points=[(float(x), float(y)) for x, y in face.polygon.exterior.coords[:-1]],
            crs="local",
            name=face.name,
        )
        for i, face in enumerate(plan.faces)
    ]
    return ParcelFile(
        rings=rings, format="pdf", scale=plan.scale, scale_source=plan.scale_source, page=plan.page
    )


def read_parcel_file(file_name: str, data: bytes, scale: int | None = None) -> ParcelFile:
    """Ringe aus der Datei. Hebt `UploadInvalid` bei unbekanntem Format oder unlesbarem Inhalt.

    `scale` (1:n) gilt nur für PDF; DXF und GeoJSON tragen ihre Einheit selbst."""
    suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if suffix == "dxf":
        return ParcelFile(rings=read_dxf(data), format="dxf")
    if suffix in ("geojson", "json"):
        return ParcelFile(rings=read_geojson(data), format="geojson")
    if suffix == "pdf":
        return read_pdf(data, scale)
    raise UploadInvalid("Nur DXF, GeoJSON und PDF werden gelesen")


def build_candidates(rings: Sequence[RawRing], to_metres: ToMetres) -> list[Candidate]:
    """Ringe prüfen und in Meter bringen; benannte zuerst (Parzellennummern aus PDF oder GeoJSON),
    sonst größte Fläche zuerst.

    `to_metres` rechnet WGS84 nach Lambert-93 um und wird nur dafür aufgerufen. Unbrauchbare Ringe
    (ungültig, Fläche außerhalb der Schranken aus G28) fallen weg; bleibt keiner, `UploadInvalid`.
    """
    candidates: list[Candidate] = []
    for raw in rings:
        points = to_metres(raw.points) if raw.crs == "EPSG:4326" else raw.points
        if len(points) < 3:
            continue
        polygon = Polygon(points)
        if not polygon.is_valid or polygon.is_empty:
            continue
        polygon = orient(polygon, sign=1.0)
        area = float(polygon.area)
        if not tol.MANUAL_MIN_AREA_M2 <= area <= tol.MANUAL_MAX_AREA_M2:
            continue
        candidates.append(
            Candidate(
                index=raw.index,
                polygon=polygon,
                area_m2=area,
                crs=raw.crs,
                layer=raw.layer,
                name=raw.name,
            )
        )
    if not candidates:
        raise UploadInvalid("Keine Kontur mit plausibler Fläche gefunden")
    return sorted(candidates, key=lambda c: (c.name is None, -c.area_m2, c.index))
