"""Schnitte quer über das Grundstück (docs/PLAN_AN3_GABARIT.md 3.3).

A–A läuft von der Hauptstraße nach hinten, B–B rechtwinklig dazu, von der Straße aus gesehen von links nach
rechts; beide durch die bebaubare Fläche. Lage `s` in Metern ab der ersten Grenze, Höhe über der Bezugshöhe
der Regeln; seit AN5 mit Geländeprofil, wenn Gelände vorliegt (die Stufen bleiben über der mittleren Höhe,
E-AN5-4). Geometrie in Lambert-93 wie der Baurahmen; der Dienst rechnet in lokale
Meter um.
"""

import math
from dataclasses import dataclass, field, replace

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from app.analysis.domain.gabarit import Gabarit
from app.analysis.domain.terrain_profile import profile
from app.envelope.domain import tolerances as tol
from app.envelope.domain.derive import READINGS, EdgeResult, Envelope, PartResult
from app.envelope.domain.heights import Heights
from app.envelope.domain.inputs import EnvelopeInput
from app.envelope.domain.setbacks import Setback, at_height, distances

MIN_ANGLE_DEG = 15.0
"""Unter diesem Winkel zwischen Schnitt und Grenze keine Abstandslinie: `1 / sin θ` wüchse über alle Maßen."""
PROSPECT_STEP_M = 0.25
"""Raster der Abstandslinie zwischen den Knickhöhen (7.1 Nr. 8)."""
MIN_INTERVAL_M = 0.01
EDGE_MATCH_M = 0.05
"""Höchster Abstand eines Grenzübergangs zu seiner Kante."""
DECIMALS = 3

Vector = tuple[float, float]
Interval = tuple[float, float]


@dataclass(frozen=True)
class Crossing:
    s: float
    edge_seq: int | None
    kind: str | None
    inward: int
    """+1: Das Grundstück liegt bei größerem `s`, −1: bei kleinerem."""


@dataclass(frozen=True)
class SectionLevel:
    from_m: float
    to_m: float
    intervals: dict[str, list[Interval]]
    roof: bool


@dataclass(frozen=True)
class HeightLine:
    zone_code: str
    kind: str
    """`eave`, `ridge` oder `parapet`."""
    height_m: float
    start: float
    end: float
    derived: bool
    """Aus einer Geschossangabe umgerechnet (Annahme)."""


@dataclass(frozen=True)
class Prospect:
    edge_seq: int
    reading: str
    points: list[tuple[float, float]]
    """(s, Höhe): Grenze der zulässigen Bebauung an dieser Kante, `x = d(h)` auf den Schnitt umgerechnet."""


@dataclass(frozen=True)
class Section:
    key: str
    start: tuple[float, float]
    end: tuple[float, float]
    length_m: float
    parcel: list[Interval]
    crossings: list[Crossing]
    levels: list[SectionLevel]
    height_lines: list[HeightLine]
    prospects: list[Prospect] = field(default_factory=list)
    terrain: list[tuple[float, float]] = field(default_factory=list)
    """(s, Höhe über der Bezugshöhe): Geländeprofil aus den Stichproben (AN5); leer ohne Gelände (eben)."""


# ---------------------------------------------------------------------------
# Richtung und Lage
# ---------------------------------------------------------------------------


def _unit(dx: float, dy: float) -> Vector:
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > 0 else (0.0, 1.0)


def _inward(edge_geometry: BaseGeometry, site: BaseGeometry) -> Vector | None:
    """Innennormale der Kante, geprüft am Grundstück statt über die Laufrichtung."""
    coords = list(edge_geometry.coords)
    if len(coords) < 2:
        return None
    ux, uy = _unit(coords[-1][0] - coords[0][0], coords[-1][1] - coords[0][1])
    middle = edge_geometry.interpolate(0.5, normalized=True)
    for nx, ny in ((-uy, ux), (uy, -ux)):
        if site.contains(Point(middle.x + nx * 0.1, middle.y + ny * 0.1)):
            return (nx, ny)
    return None


def _directions(data: EnvelopeInput) -> tuple[Vector, Vector]:
    """A–A in Richtung der Innennormalen der Hauptstraße, sonst entlang der langen Seite des kleinsten
    umschließenden Rechtecks (nach Norden); B–B rechts davon, von A–A aus gesehen."""
    site = data.site
    main = next((e for e in site.edges if e.seq == site.main_street_seq), None)
    along = _inward(main.geometry, site.polygon) if main is not None else None
    if along is None:
        corners = list(site.polygon.minimum_rotated_rectangle.exterior.coords)
        sides = [(corners[i], corners[i + 1]) for i in range(len(corners) - 1)]
        a, b = max(sides, key=lambda side: math.dist(side[0], side[1]))
        along = _unit(b[0] - a[0], b[1] - a[1])
        if along[1] < 0 or (along[1] == 0 and along[0] < 0):
            along = (-along[0], -along[1])
    return along, (along[1], -along[0])


def _centre(data: EnvelopeInput, envelope: Envelope) -> Point:
    """Schwerpunkt der engsten, sonst der weitesten Kontur, sonst des Grundstücks; liegt er außerhalb der
    Fläche (L-Form), ein Punkt darin (7.1 Nr. 6)."""
    for reading in ("strict", "lenient"):
        contour = envelope.contours.get(reading)
        if contour is not None and not contour.geometry.is_empty:
            return _inside(contour.geometry)
    return _inside(data.site.polygon)


def _inside(geometry: BaseGeometry) -> Point:
    centroid = geometry.centroid
    return centroid if geometry.contains(centroid) else geometry.representative_point()


# ---------------------------------------------------------------------------
# Schnitt
# ---------------------------------------------------------------------------


class _Line:
    """Schnittlinie mit Lage `s` ab einem Nullpunkt."""

    def __init__(self, centre: Point, direction: Vector, reach: float) -> None:
        self.direction = direction
        self.geometry = LineString(
            [
                (centre.x - direction[0] * reach, centre.y - direction[1] * reach),
                (centre.x + direction[0] * reach, centre.y + direction[1] * reach),
            ]
        )
        self.zero = 0.0

    def intervals(self, area: BaseGeometry) -> list[Interval]:
        """Abschnitte der Linie in einer Fläche, als `s` (nach `zero`)."""
        if area.is_empty:
            return []
        cut = self.geometry.intersection(area)
        parts = [cut] if isinstance(cut, LineString) else list(getattr(cut, "geoms", []))
        pieces = [g for g in parts if isinstance(g, LineString)]
        result: list[Interval] = []
        for piece in pieces:
            if piece.is_empty or piece.length < MIN_INTERVAL_M:
                continue
            a = self.geometry.project(Point(piece.coords[0])) - self.zero
            b = self.geometry.project(Point(piece.coords[-1])) - self.zero
            result.append((round(min(a, b), DECIMALS), round(max(a, b), DECIMALS)))
        return _merge(sorted(result))

    def point(self, s: float) -> Point:
        return self.geometry.interpolate(s + self.zero)


def _merge(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + MIN_INTERVAL_M:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _edge_at(point: Point, edges: list[EdgeResult]) -> EdgeResult | None:
    if not edges:
        return None
    nearest = min(edges, key=lambda edge: edge.geometry.distance(point))
    return nearest if nearest.geometry.distance(point) <= EDGE_MATCH_M else None


def _edge_direction(edge: EdgeResult, point: Point) -> Vector:
    """Richtung des Kantenabschnitts am Grenzübergang (Kanten können geknickt sein)."""
    coords = list(edge.geometry.coords)
    segments = [LineString([coords[i], coords[i + 1]]) for i in range(len(coords) - 1)]
    nearest = min(segments, key=lambda segment: segment.distance(point))
    (x1, y1), (x2, y2) = nearest.coords
    return _unit(x2 - x1, y2 - y1)


def _part_at(point: Point, parts: list[PartResult]) -> PartResult | None:
    active = [p for p in parts if p.excluded is None]
    if not active:
        return None
    nearest = min(active, key=lambda part: part.geometry.distance(point))
    return nearest if nearest.geometry.distance(point) <= EDGE_MATCH_M else None


def _prospect_heights(setbacks: list[Setback], heights: Heights, top: float) -> list[float]:
    """Stützstellen der Abstandslinie: Knickhöhen der Regeln und ein Raster (7.1 Nr. 8)."""
    values = {0.0, top}
    values |= {k * PROSPECT_STEP_M for k in range(int(top / PROSPECT_STEP_M) + 1)}
    for setback in setbacks:
        params = setback.params
        limit = params.get("on_boundary_max_height_m")
        if params.get("allow_on_boundary") and isinstance(limit, int | float):
            values |= {float(limit), float(limit) + 0.001}
        cap = heights.for_basis(params.get("height_basis"))
        if cap is not None:
            values.add(cap)
        factor, minimum = params.get("height_factor"), params.get("min_m")
        if isinstance(factor, int | float) and factor > 0 and isinstance(minimum, int | float):
            values.add(float(minimum) / float(factor))
    return sorted(v for v in values if 0 <= v <= top + tol.DISTANCE_EPSILON_M)


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Punkte auf einer Geraden weglassen; Richtungswechsel und Sprünge bleiben."""
    kept: list[tuple[float, float]] = []
    for point in points:
        if kept and math.dist(kept[-1], point) < 1e-6:
            continue
        if len(kept) >= 2:
            (ax, ay), (bx, by) = kept[-2], kept[-1]
            cross = (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)
            if abs(cross) < 1e-6 and (bx - ax) * (point[0] - bx) + (by - ay) * (point[1] - by) >= 0:
                kept[-1] = point
                continue
        kept.append(point)
    return [(round(s, DECIMALS), round(h, DECIMALS)) for s, h in kept]


def _prospects(
    crossing: Crossing, line: _Line, edge: EdgeResult, part: PartResult, heights: Heights
) -> list[Prospect]:
    setbacks = [s for s in edge.setbacks if s.zone_code == part.zone_code]
    top = heights.highest_m
    if not setbacks or top is None or all(s.status != "effective" for s in setbacks):
        return []
    ex, ey = _edge_direction(edge, line.point(crossing.s))
    sine = abs(line.direction[0] * ey - line.direction[1] * ex)
    if sine < math.sin(math.radians(MIN_ANGLE_DEG)):
        return []
    result: list[Prospect] = []
    samples = _prospect_heights(setbacks, heights, top)
    for reading in READINGS:
        points: list[tuple[float, float]] = []
        for height in samples:
            lenient, strict, _ = distances([at_height(s, heights, height) for s in setbacks])
            value = lenient if reading == "lenient" else strict
            if value is None:
                points = []
                break
            points.append((crossing.s + crossing.inward * value / sine, height))
        if points:
            result.append(Prospect(edge.seq, reading, _simplify(points)))
    return result


def _section(
    key: str, data: EnvelopeInput, envelope: Envelope, gabarit: Gabarit, centre: Point, direction: Vector
) -> Section | None:
    minx, miny, maxx, maxy = data.site.polygon.bounds
    line = _Line(centre, direction, math.hypot(maxx - minx, maxy - miny) + 1.0)
    raw = line.intervals(data.site.polygon)
    if not raw:
        return None
    line.zero = raw[0][0]
    parcel = [(round(a - raw[0][0], DECIMALS), round(b - raw[0][0], DECIMALS)) for a, b in raw]
    crossings: list[Crossing] = []
    for start, end in parcel:
        for s, inward in ((start, 1), (end, -1)):
            edge = _edge_at(line.point(s), envelope.edges)
            crossings.append(Crossing(s, edge.seq if edge else None, edge.kind if edge else None, inward))
    levels = [
        SectionLevel(
            from_m=level.from_m,
            to_m=level.to_m,
            intervals={r: line.intervals(level.contours[r].geometry) for r in READINGS},
            roof=level.roof,
        )
        for level in gabarit.levels
    ]
    height_lines: list[HeightLine] = []
    for part in envelope.parts:
        heights = gabarit.heights.get(part.zone_code)
        if part.excluded is not None or heights is None:
            continue
        lines = [("eave", heights.eave_m), ("ridge", heights.ridge_m), ("parapet", heights.parapet_m)]
        for start, end in line.intervals(part.geometry):
            # R+1 ohne Dach: Traufe = First, eine Linie genügt
            seen: set[float] = set()
            for kind, value in lines:
                if value is None or round(value, 2) in seen:
                    continue
                seen.add(round(value, 2))
                height_lines.append(
                    HeightLine(part.zone_code, kind, value, start, end, derived=bool(heights.assumptions))
                )
    prospects: list[Prospect] = []
    edges = {edge.seq: edge for edge in envelope.edges}
    for crossing in crossings:
        if crossing.edge_seq is None:
            continue
        inside = _part_at(line.point(crossing.s + crossing.inward * 0.05), envelope.parts)
        heights = gabarit.heights.get(inside.zone_code) if inside is not None else None
        if inside is not None and heights is not None:
            prospects.extend(_prospects(crossing, line, edges[crossing.edge_seq], inside, heights))
    start, end = line.point(0.0), line.point(parcel[-1][1])
    return Section(
        key=key,
        start=(start.x, start.y),
        end=(end.x, end.y),
        length_m=parcel[-1][1],
        parcel=parcel,
        crossings=crossings,
        levels=levels,
        height_lines=height_lines,
        prospects=prospects,
    )


def sections(data: EnvelopeInput, envelope: Envelope, gabarit: Gabarit) -> list[Section]:
    """Schnitte A–A und B–B; ohne Stufen des Gabarits keine."""
    if not gabarit.levels:
        return []
    along, across = _directions(data)
    centre = _centre(data, envelope)
    result = [_section(key, data, envelope, gabarit, centre, d) for key, d in (("A", along), ("B", across))]
    terrain = data.site.terrain
    return [
        replace(
            section,
            terrain=profile(
                terrain.samples, section.start, section.end, section.parcel, terrain.reference_altitude_ngf
            ),
        )
        if terrain.status == "ok" and terrain.reference_altitude_ngf is not None
        else section
        for section in result
        if section is not None
    ]
