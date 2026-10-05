"""Template-Entwurf und Importbericht aus dem gelesenen Modell (docs/PLAN_HAUSMODELL.md 3.6, P 12.3,
P 12.4).

Ablauf je Geschoss (E-HM-63: alle Geschosse mit derselben Bezugskontur):

1. Wände vereinigen (Lücken bis 1 mm geschlossen). Außen ist eine Wand, die auf dem äußeren Rand liegt;
   `IsExternal` dient nur zum Vergleich (P 12.3).
2. Bezugskontur = Loch der vereinigten Außenwände: ihre Innenseite (E-HM-24). Dicken, Schichten und
   Materialien der Platzhalter werden nicht gelesen (3.6).
3. Räume = Löcher aller Wände; Zonen liefern nur den Typ (Zuordnung über „mehr als die Hälfte“, 3.6 Nr. 4).
4. Innenwände als Achsen, an Anschlüssen auf die Achse der anderen Wand bzw. die Bezugskontur gezogen und
   dort geteilt, damit jedes Stück höchstens zwei Räume trennt.
5. Öffnungen auf ihrem Host mit Abstand vom Anfang bis zur Mitte; Typ aus dem Katalog über Maße (E-HM-37).
6. Platten: Bodenplatte zur Kontrolle und für ihre Dicke, je Obergeschoss die Decke darunter (Oberkante auf
   der Höhe des Geschosses).

Danach das Dach über dem obersten Geschoss: Flachdach mit Auflagerhöhe, Dachdecke, Attika (Oberkante
Außenwände über Dachdecke) und Überstand; ein geneigtes Dach erkennt `roof.py` mit dem Kern. Fassadenrollen
setzt das Büro am Erdgeschoss, die Obergeschosse übernehmen sie je Kante.

Koordinaten des Templates: Ursprung in der linken unteren Ecke der Bezugskontur, gerundet auf 0,1 mm (P 4).
"""

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Literal

from pydantic import ValidationError
from shapely import LineString, Point, Polygon, oriented_envelope, unary_union
from shapely.affinity import translate
from shapely.geometry.base import BaseGeometry

from app.house.contract import (
    FLAT_DESIGN,
    HouseCatalog,
    HouseOptionValue,
    HouseSourceIfc,
    HouseTemplate,
    HouseText,
)
from app.house.domain.draft import (
    IGNORE,
    HouseDoorChoice,
    HouseDraftDecisions,
    HouseImportFinding,
    HouseImportOpening,
    HouseImportReport,
    HouseImportSummary,
    HouseImportZone,
    HouseImportZoneSource,
    Severity,
)
from app.house.domain.raw import Polygon2, RawModel, RawOpening, RawRoof, RawSpace, RawStorey, RawWall
from app.house.domain.roof import NotRecognized, RoofBuilder, recognize, underside
from app.house.domain.zones import SourceValue, ZoneMatch, classify

TOL = 0.001
"""Toleranz des Templates (P 4, P 20.3): 1 mm."""
DIGITS = 4
"""Ausgabe auf 0,1 mm."""
SMALL_AREA = 0.01
"""Kleinere Flächen zwischen Wänden sind Zeichenungenauigkeiten, keine Räume."""
OUTDATED = 0.01
"""Zonen eines Raums weichen um mehr als 1 % seiner Fläche ab: „Zone nicht aktualisiert“ (3.6 Nr. 4)."""
FLAT_DEG = 1.0
"""Flächen bis 1° gelten als waagerecht, ab 89° als senkrecht."""
UNASSIGNED = "unassigned"
"""Raumtyp eines Raums, den das Büro noch zuweisen muss; die Veröffentlichung verhindert der offene Punkt."""
DEFAULT_GROUND_FLOOR_OFFSET = 0.20


@dataclass
class Findings:
    items: list[HouseImportFinding] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        code: str,
        *,
        element_id: str | None = None,
        ifc_guid: str | None = None,
        counts: Mapping[str, int] | None = None,
        **params: str | float | None,
    ) -> None:
        values: dict[str, str | float | None] = {**params, **{k: float(v) for k, v in (counts or {}).items()}}
        self.items.append(
            HouseImportFinding(
                severity=severity, code=code, element_id=element_id, ifc_guid=ifc_guid, params=values
            )
        )

    def has_blocking(self) -> bool:
        return any(f.severity in ("error", "open") for f in self.items)


def _r(value: float) -> float:
    return round(value, DIGITS) + 0.0


def _polygon(rings: Polygon2) -> Polygon:
    return Polygon(rings[0], rings[1:]).buffer(0)


def _parts(geometry: BaseGeometry) -> list[Polygon]:
    parts = list(getattr(geometry, "geoms", [geometry]))
    return [p for p in parts if isinstance(p, Polygon) and not p.is_empty]


def _close(polygons: Iterable[BaseGeometry]) -> BaseGeometry:
    """Vereinigung mit geschlossenen Fugen bis 1 mm (Wände berühren sich nur mit Rundungsrauschen)."""
    grown = [p.buffer(TOL / 2, join_style="mitre") for p in polygons]
    return unary_union(grown).buffer(-TOL / 2, join_style="mitre")


def _ring(coords: Sequence[Any]) -> list[tuple[float, float]]:
    """Ring ohne Doppelpunkte und Punkte auf einer Geraden, gegen den Uhrzeigersinn, Start links unten."""
    points: list[tuple[float, float]] = []
    for x, y in list(coords)[:-1] if tuple(coords[0]) == tuple(coords[-1]) else list(coords):
        point = (_r(x), _r(y))
        if not points or point != points[-1]:
            points.append(point)
    while len(points) > 1 and points[0] == points[-1]:
        points.pop()
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i in range(len(points)):
            a, b, c = points[i - 1], points[i], points[(i + 1) % len(points)]
            length = math.dist(a, c)
            if (
                length == 0
                or abs((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / length < 1e-4
            ):
                points.pop(i)
                changed = True
                break
    area = sum(points[i - 1][0] * p[1] - p[0] * points[i - 1][1] for i, p in enumerate(points))
    if area < 0:
        points.reverse()
    start = min(range(len(points)), key=lambda i: (points[i][1], points[i][0]))
    return points[start:] + points[:start]


def _xy(points: Iterable[tuple[float, float]]) -> list[dict[str, float]]:
    return [{"x": x, "y": y} for x, y in points]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length else (0.0, 0.0)


@dataclass
class Zone:
    space: RawSpace
    match: ZoneMatch
    decided: bool
    polygon: Polygon | None
    room_index: int | None = None
    share: float | None = None
    room_id: str | None = None


@dataclass
class Room:
    id: str
    polygon: Polygon
    room_type_id: str
    source_guid: str | None


@dataclass
class Axis:
    guid: str
    a: tuple[float, float]
    b: tuple[float, float]
    thickness: float

    @property
    def length(self) -> float:
        return math.dist(self.a, self.b)

    @property
    def direction(self) -> tuple[float, float]:
        return _unit(self.b[0] - self.a[0], self.b[1] - self.a[1])


@dataclass
class Piece:
    id: str
    guid: str
    a: tuple[float, float]
    b: tuple[float, float]
    thickness: float
    rooms: list[str]


@dataclass
class Edge:
    id: str
    guid: str | None
    a: tuple[float, float]
    b: tuple[float, float]


class Assembler:
    def __init__(
        self,
        raw: RawModel,
        decisions: HouseDraftDecisions,
        catalog: HouseCatalog,
        source: HouseSourceIfc,
        slug: str,
        default_name: str,
        build_roof: RoofBuilder,
    ) -> None:
        self.raw = raw
        self.build_roof = build_roof
        self.decisions = decisions
        self.catalog = catalog
        self.source = source
        self.slug = slug
        self.default_name = default_name
        self.findings = Findings()
        self.zones: list[Zone] = []
        self.report_openings: list[HouseImportOpening] = []
        self.origin = (0.0, 0.0)
        self.summary = HouseImportSummary(
            storeys=0,
            roof_levels=0,
            exterior_walls=0,
            interior_walls=0,
            windows=0,
            doors=0,
            rooms=0,
            zones=0,
            inner_width=None,
            inner_depth=None,
            inner_area=None,
        )

    # --- Geschosse --------------------------------------------------------------------------------------

    def storeys(self) -> list[str]:
        """Geschosse mit Wänden oder Zonen, von unten nach oben; eines nur mit Dach ist die Dachebene
        (3.6)."""
        used = {w.storey_guid for w in self.raw.walls} | {s.storey_guid for s in self.raw.spaces}
        counting = [s for s in sorted(self.raw.storeys, key=lambda s: s.z) if s.guid in used]
        for storey in self.raw.storeys:
            if storey.guid not in used and any(r.storey_guid == storey.guid for r in self.raw.roofs):
                self.findings.add("info", "roof_level", ifc_guid=storey.guid, name=storey.name)
        elements: list[RawWall | RawSpace | RawOpening] = [
            *self.raw.walls,
            *self.raw.spaces,
            *self.raw.openings,
        ]
        for element in elements:
            if element.storey_guid is None:
                self.findings.add("warning", "element_without_storey", ifc_guid=element.guid)
        return [s.guid for s in counting]

    # --- Wände, Kontur, Räume ---------------------------------------------------------------------------

    def walls(self, storey: str) -> tuple[list[RawWall], list[RawWall], BaseGeometry] | None:
        candidates = [w for w in self.raw.walls if w.storey_guid == storey]
        polygons = {w.guid: _polygon(w.footprint) for w in candidates}
        union = _close(polygons.values())
        parts = sorted(_parts(union), key=lambda p: -p.area)
        if not parts:
            self.findings.add("error", "envelope_not_closed", areas=0.0)
            return None
        main = parts[0]
        walls = [w for w in candidates if polygons[w.guid].buffer(TOL).intersects(main)]
        for wall in candidates:
            if wall not in walls:
                self.findings.add("warning", "wall_disconnected", ifc_guid=wall.guid)
        exterior: list[RawWall] = []
        interior: list[RawWall] = []
        for wall in walls:
            on_rim = polygons[wall.guid].buffer(TOL).intersection(main.exterior).length > 10 * TOL
            (exterior if on_rim else interior).append(wall)
        return exterior, interior, main

    def contour(self, exterior: list[RawWall]) -> Polygon | None:
        """Genau eine Fläche innerhalb der Außenwände. Fehlt eine Außenwand, liegen Innenwände auf dem Rand
        und zählen als außen; dann umschließen sie keine oder mehrere Flächen (`areas`)."""
        shell = _close(_polygon(w.footprint) for w in exterior)
        holes = sorted(
            (Polygon(ring) for part in _parts(shell) for ring in part.interiors), key=lambda p: -p.area
        )
        areas = [h for h in holes if h.area >= SMALL_AREA]
        if len(areas) != 1:
            self.findings.add("error", "envelope_not_closed", areas=float(len(areas)))
            return None
        return areas[0]

    def compare_flags(self, exterior: list[RawWall], interior: list[RawWall]) -> None:
        """`IsExternal` nur zum Vergleich (P 12.3); erst bei geschlossener Hülle, sonst wäre jede Meldung
        eine Folge der offenen Hülle."""
        for wall, on_rim in [*((w, True) for w in exterior), *((w, False) for w in interior)]:
            if wall.is_external is not None and wall.is_external != on_rim:
                self.findings.add(
                    "warning",
                    "is_external_mismatch",
                    ifc_guid=wall.guid,
                    is_external=str(wall.is_external).lower(),
                )

    def zone_matches(self, storey: str) -> list[Zone]:
        """Zonen des Geschosses mit ihrem Raumtyp; der Bericht nennt alle (`self.zones`)."""
        table = self.catalog.zone_table()
        room_types = {t.id for t in self.catalog.room_types}
        zones: list[Zone] = []
        for space in self.raw.spaces:
            if space.storey_guid != storey:
                continue
            decision = self.decisions.zone_types.get(space.guid)
            if decision == IGNORE:
                match = ZoneMatch("ignored", None, None, None, ())
            elif decision in room_types:
                match = ZoneMatch("room", decision, None, None, ())
            else:
                if decision is not None:
                    self.findings.add("open", "decision_invalid", ifc_guid=space.guid, value=decision)
                values = [SourceValue(s.kind, s.raw) for s in space.sources]
                match = classify(values, table)
                for conflict in match.conflicts:
                    self.findings.add(
                        "warning",
                        "zone_type_conflict",
                        ifc_guid=space.guid,
                        source=conflict.kind,
                        raw=conflict.raw,
                        room_type=conflict.room_type_id,
                        chosen=match.room_type_id,
                    )
            polygon = None
            if space.footprint is not None:
                polygon = translate(_polygon(space.footprint), -self.origin[0], -self.origin[1])
            decided = decision in room_types or decision == IGNORE
            zones.append(Zone(space, match, decided, polygon))
        self.zones += zones
        return zones

    def rooms(self, storey_index: int, holes: list[Polygon], zones: list[Zone]) -> list[Room]:
        """Räume zwischen den Wänden mit ihrem Typ aus den Zonen (3.6 Nr. 4)."""
        for zone in zones:
            if zone.match.result == "ignored":
                continue
            if zone.polygon is None or zone.polygon.area <= 0:
                self.findings.add("error", "zone_without_geometry", ifc_guid=zone.space.guid)
                continue
            overlaps = [zone.polygon.intersection(hole).area for hole in holes]
            best = max(range(len(holes)), key=lambda i: overlaps[i]) if holes else None
            share = overlaps[best] / zone.polygon.area if best is not None else 0.0
            zone.share = round(share, 4)
            if best is None or share <= 0.5:
                self.findings.add(
                    "error", "zone_outside_rooms", ifc_guid=zone.space.guid, share=round(share, 3)
                )
                continue
            zone.room_index = best

        rooms: list[Room] = []
        for index, hole in enumerate(holes):
            mine = [z for z in zones if z.room_index == index]
            if mine:
                covered = unary_union([z.polygon for z in mine if z.polygon is not None])
                deviation = hole.symmetric_difference(covered).area / hole.area
                if deviation > OUTDATED:
                    largest = max(mine, key=lambda z: z.polygon.area if z.polygon else 0)
                    self.findings.add(
                        "warning",
                        "zone_outdated",
                        element_id=f"room-{largest.space.guid}",
                        ifc_guid=largest.space.guid,
                        deviation=round(deviation, 4),
                    )
            rooms += self.typed_rooms(storey_index, hole, mine)
        return rooms

    def typed_rooms(self, storey_index: int, hole: Polygon, zones: list[Zone]) -> list[Room]:
        if not zones:
            x, y = _ring(hole.exterior.coords)[0]
            room_id = f"room-{storey_index}-x{round(x * 100)}-y{round(y * 100)}"
            decision = self.decisions.room_types.get(room_id)
            if decision == IGNORE:
                self.findings.add("info", "room_ignored", element_id=room_id)
                return []
            if decision in {t.id for t in self.catalog.room_types}:
                return [Room(room_id, hole, decision, None)]
            self.findings.add("open", "room_without_zone", element_id=room_id, area=round(hole.area, 2))
            return [Room(room_id, hole, UNASSIGNED, None)]

        zones = sorted(zones, key=lambda z: -(z.polygon.intersection(hole).area if z.polygon else 0))
        base = f"room-{zones[0].space.guid}"
        typed = [z for z in zones if z.match.result == "room"]
        for zone in zones:
            zone.room_id = base
            if zone.match.result == "unrecognized":
                self.findings.add("open", "zone_unrecognized", element_id=base, ifc_guid=zone.space.guid)
        if len(typed) < len(zones) or len({z.match.room_type_id for z in typed}) == 1:
            room_type = typed[0].match.room_type_id if typed else None
            return [Room(base, hole, room_type or UNASSIGNED, zones[0].space.guid)]

        parts = self.split(hole, typed)
        if parts is None:
            self.findings.add("open", "room_split_failed", element_id=base)
            return [Room(base, hole, typed[0].match.room_type_id or UNASSIGNED, zones[0].space.guid)]
        if base not in self.decisions.confirmed_splits:
            self.findings.add("open", "room_split_unconfirmed", element_id=base, parts=float(len(parts)))
        rooms = []
        for zone, polygon in parts:
            zone.room_id = f"room-{zone.space.guid}"
            rooms.append(Room(zone.room_id, polygon, zone.match.room_type_id or UNASSIGNED, zone.space.guid))
        return rooms

    @staticmethod
    def split(hole: Polygon, zones: list[Zone]) -> list[tuple[Zone, Polygon]] | None:
        """Teilt einen Raum entlang seiner Zonen; Reste gehen an den Teil mit der längsten gemeinsamen
        Kante."""
        pieces: list[tuple[Zone, BaseGeometry]] = []
        used: BaseGeometry = Polygon()
        for zone in zones:
            assert zone.polygon is not None
            piece = hole.intersection(zone.polygon).difference(used)
            pieces.append((zone, piece))
            used = used.union(piece)
        for rest in _parts(hole.difference(used)):
            if rest.area < 1e-8:
                continue
            target = max(range(len(pieces)), key=lambda i: rest.buffer(TOL).intersection(pieces[i][1]).area)
            pieces[target] = (pieces[target][0], pieces[target][1].union(rest))
        result = []
        for zone, piece in pieces:
            cleaned = [p for p in _parts(_close([piece])) if p.area >= SMALL_AREA]
            if len(cleaned) != 1 or cleaned[0].interiors:
                return None
            result.append((zone, cleaned[0]))
        return result

    # --- Innenwände -------------------------------------------------------------------------------------

    def axes(self, interior: list[RawWall]) -> list[Axis]:
        axes = []
        for wall in interior:
            polygon = translate(_polygon(wall.footprint), -self.origin[0], -self.origin[1])
            box = oriented_envelope(polygon)
            if not isinstance(box, Polygon) or polygon.area < 0.9 * box.area:
                self.findings.add("error", "wall_not_straight", ifc_guid=wall.guid)
                continue
            c = list(box.exterior.coords)[:4]
            first, second = math.dist(c[0], c[1]), math.dist(c[1], c[2])
            if first >= second:
                ends = ((c[1], c[2]), (c[3], c[0]))
                thickness = second
            else:
                ends = ((c[0], c[1]), (c[2], c[3]))
                thickness = first
            a = ((ends[0][0][0] + ends[0][1][0]) / 2, (ends[0][0][1] + ends[0][1][1]) / 2)
            b = ((ends[1][0][0] + ends[1][1][0]) / 2, (ends[1][0][1] + ends[1][1][1]) / 2)
            # Anfang links bzw. unten: Nummern geteilter Stücke hängen nicht von der Zeichenrichtung ab
            if b[0] < a[0] - TOL or (abs(b[0] - a[0]) <= TOL and b[1] < a[1]):
                a, b = b, a
            axes.append(Axis(wall.guid, a, b, thickness))
        return axes

    @staticmethod
    def _intersection(
        p: tuple[float, float], d: tuple[float, float], q: tuple[float, float], e: tuple[float, float]
    ) -> tuple[float, float] | None:
        cross = d[0] * e[1] - d[1] * e[0]
        if abs(cross) < 0.1:
            return None
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / cross
        return (p[0] + t * d[0], p[1] + t * d[1])

    def snap(self, axes: list[Axis], contour: Polygon) -> None:
        """Enden auf die Achse der anstoßenden Wand oder auf die Bezugskontur ziehen."""
        original = [(axis.a, axis.b) for axis in axes]
        rim = contour.exterior
        for i, axis in enumerate(axes):
            for end in ("a", "b"):
                p = original[i][0] if end == "a" else original[i][1]
                other = original[i][1] if end == "a" else original[i][0]
                d = _unit(p[0] - other[0], p[1] - other[1])
                best: tuple[float, tuple[float, float]] | None = None
                for j, wall in enumerate(axes):
                    if j == i:
                        continue
                    qa, qb = original[j]
                    e = _unit(qb[0] - qa[0], qb[1] - qa[1])
                    hit = self._intersection(p, d, qa, e)
                    if hit is None:
                        continue
                    s = (hit[0] - p[0]) * d[0] + (hit[1] - p[1]) * d[1]
                    u = (hit[0] - qa[0]) * e[0] + (hit[1] - qa[1]) * e[1]
                    reach = axis.thickness / 2 + TOL
                    if (
                        abs(s) <= wall.thickness / 2 + TOL
                        and -reach <= u <= math.dist(qa, qb) + reach
                        and (best is None or abs(s) < best[0])
                    ):
                        best = (abs(s), hit)
                ray = LineString(
                    [(p[0] - d[0] * 100, p[1] - d[1] * 100), (p[0] + d[0] * 100, p[1] + d[1] * 100)]
                )
                for hit_point in _points(ray.intersection(rim)):
                    s = (hit_point[0] - p[0]) * d[0] + (hit_point[1] - p[1]) * d[1]
                    if -0.6 <= s <= TOL and (best is None or abs(s) < best[0]):
                        best = (abs(s), hit_point)
                if best is not None:
                    setattr(axis, end, best[1])

    def pieces(self, axes: list[Axis], rooms: list[Room]) -> list[Piece]:
        """Teilt jede Achse an Anschlüssen und Kreuzungen; je Stück die Räume links und rechts."""
        pieces = []
        for i, axis in enumerate(axes):
            d = axis.direction
            length = axis.length
            cuts = {0.0, length}
            for j, other in enumerate(axes):
                if j == i:
                    continue
                for q in (other.a, other.b):
                    distance = abs((q[0] - axis.a[0]) * d[1] - (q[1] - axis.a[1]) * d[0])
                    u = (q[0] - axis.a[0]) * d[0] + (q[1] - axis.a[1]) * d[1]
                    if distance <= TOL and TOL < u < length - TOL:
                        cuts.add(u)
                e = other.direction
                hit = self._intersection(axis.a, d, other.a, e)
                if hit is not None:
                    u = (hit[0] - axis.a[0]) * d[0] + (hit[1] - axis.a[1]) * d[1]
                    v = (hit[0] - other.a[0]) * e[0] + (hit[1] - other.a[1]) * e[1]
                    if TOL < u < length - TOL and TOL < v < other.length - TOL:
                        cuts.add(u)
            ordered = sorted(cuts)
            merged = [ordered[0]]
            for u in ordered[1:]:
                if u - merged[-1] > TOL:
                    merged.append(u)
            merged[-1] = length
            spans = list(pairwise(merged))
            for k, (u0, u1) in enumerate(spans, start=1):
                a = (_r(axis.a[0] + d[0] * u0), _r(axis.a[1] + d[1] * u0))
                b = (_r(axis.a[0] + d[0] * u1), _r(axis.a[1] + d[1] * u1))
                piece_id = f"wall-{axis.guid}" if len(spans) == 1 else f"wall-{axis.guid}-{k}"
                pieces.append(Piece(piece_id, axis.guid, a, b, _r(axis.thickness), []))
        for piece in pieces:
            mid = ((piece.a[0] + piece.b[0]) / 2, (piece.a[1] + piece.b[1]) / 2)
            dx, dy = _unit(piece.b[0] - piece.a[0], piece.b[1] - piece.a[1])
            offset = piece.thickness / 2 + 0.05
            for side in (1, -1):
                found = _room_at(rooms, (mid[0] - dy * offset * side, mid[1] + dx * offset * side))
                if found is not None and found not in piece.rooms:
                    piece.rooms.append(found)
        return pieces

    # --- Öffnungen --------------------------------------------------------------------------------------

    def openings(
        self,
        storey: str,
        storey_z: float,
        edges: list[Edge],
        pieces: list[Piece],
        exterior: set[str],
        interior: set[str],
        walls: dict[str, Polygon],
        rooms: list[Room],
        ignored_rooms: list[Polygon],
    ) -> list[dict[str, Any]]:
        result = []
        for raw in self.raw.openings:
            if raw.storey_guid != storey:
                continue
            center = (raw.center[0] - self.origin[0], raw.center[1] - self.origin[1])
            host = raw.host_guid if raw.host_guid in exterior | interior else None
            if host is None:
                # Rückfall über die Geometrie (P 12.3): die Wand, in der die Mitte der Öffnung liegt
                host = next((g for g, p in walls.items() if p.buffer(0.01).contains(Point(center))), None)
                if host is None:
                    self.findings.add("error", "opening_without_host", ifc_guid=raw.guid)
                    continue
                self.findings.add("warning", "opening_host_by_geometry", ifc_guid=raw.guid)
            prefix = "win" if raw.kind == "window" else "door"
            opening_id = f"{prefix}-{raw.guid}"
            placed = (
                self.on_edge(raw, opening_id, center, edges, rooms, ignored_rooms)
                if host in exterior
                else self.on_piece(
                    raw, opening_id, center, [p for p in pieces if p.guid == host], rooms, ignored_rooms
                )
            )
            if placed is None:
                continue
            host_kind, host_id, offset, adjacent = placed
            result.append(
                {
                    "id": opening_id,
                    "source_ifc_guid": raw.guid,
                    "kind": raw.kind,
                    "host_kind": host_kind,
                    "host_id": host_id,
                    "offset_along_host": _r(offset),
                    "adjacent_room_ids": adjacent,
                }
            )
            self.report_openings.append(self.dimensions(raw, opening_id, storey_z))
        return result

    def _rooms_or_finding(
        self,
        raw: RawOpening,
        opening_id: str,
        points: list[tuple[float, float]],
        rooms: list[Room],
        ignored: list[Polygon],
    ) -> list[str] | None:
        found: list[str] = []
        for point in points:
            room = _room_at(rooms, point)
            if room is not None and room not in found:
                found.append(room)
        if found:
            return found
        in_ignored = any(p.buffer(TOL).contains(Point(q)) for p in ignored for q in points)
        self.findings.add(
            "open" if in_ignored else "error",
            "opening_in_ignored_room" if in_ignored else "opening_without_room",
            element_id=opening_id,
            ifc_guid=raw.guid,
        )
        return None

    def on_edge(
        self,
        raw: RawOpening,
        opening_id: str,
        center: tuple[float, float],
        edges: list[Edge],
        rooms: list[Room],
        ignored: list[Polygon],
    ) -> tuple[str, str, float, list[str]] | None:
        best: tuple[float, Edge, float] | None = None
        for edge in edges:
            length = math.dist(edge.a, edge.b)
            d = _unit(edge.b[0] - edge.a[0], edge.b[1] - edge.a[1])
            u = (center[0] - edge.a[0]) * d[0] + (center[1] - edge.a[1]) * d[1]
            if not -TOL <= u <= length + TOL:
                continue
            distance = abs((center[0] - edge.a[0]) * d[1] - (center[1] - edge.a[1]) * d[0])
            if best is None or distance < best[0]:
                best = (distance, edge, min(max(u, 0.0), length))
        if best is None or best[0] > 1.0:
            self.findings.add("error", "opening_outside_host", element_id=opening_id, ifc_guid=raw.guid)
            return None
        _, edge, u = best
        d = _unit(edge.b[0] - edge.a[0], edge.b[1] - edge.a[1])
        point = (edge.a[0] + d[0] * u - d[1] * 0.05, edge.a[1] + d[1] * u + d[0] * 0.05)
        adjacent = self._rooms_or_finding(raw, opening_id, [point], rooms, ignored)
        return None if adjacent is None else ("envelope_segment", edge.id, u, adjacent)

    def on_piece(
        self,
        raw: RawOpening,
        opening_id: str,
        center: tuple[float, float],
        pieces: list[Piece],
        rooms: list[Room],
        ignored: list[Polygon],
    ) -> tuple[str, str, float, list[str]] | None:
        best: tuple[float, Piece, float] | None = None
        for piece in pieces:
            length = math.dist(piece.a, piece.b)
            d = _unit(piece.b[0] - piece.a[0], piece.b[1] - piece.a[1])
            u = (center[0] - piece.a[0]) * d[0] + (center[1] - piece.a[1]) * d[1]
            distance = abs((center[0] - piece.a[0]) * d[1] - (center[1] - piece.a[1]) * d[0])
            if (
                -TOL <= u <= length + TOL
                and distance <= piece.thickness / 2 + 0.2
                and (best is None or distance < best[0])
            ):
                best = (distance, piece, min(max(u, 0.0), length))
        if best is None:
            self.findings.add("error", "opening_outside_host", element_id=opening_id, ifc_guid=raw.guid)
            return None
        _, piece, u = best
        d = _unit(piece.b[0] - piece.a[0], piece.b[1] - piece.a[1])
        base = (piece.a[0] + d[0] * u, piece.a[1] + d[1] * u)
        offset = piece.thickness / 2 + 0.05
        points = [(base[0] - d[1] * offset * s, base[1] + d[0] * offset * s) for s in (1, -1)]
        adjacent = self._rooms_or_finding(raw, opening_id, points, rooms, ignored)
        return None if adjacent is None else ("interior_wall", piece.id, u, adjacent)

    @staticmethod
    def dimensions(raw: RawOpening, opening_id: str, storey_z: float) -> HouseImportOpening:
        head = None
        box = 0.0
        if raw.sill is not None and raw.height is not None:
            head = _r(raw.sill - storey_z + raw.height)
            if raw.kind == "window" and raw.top - storey_z - head > 0.005:
                box = _r(raw.top - storey_z - head)
        return HouseImportOpening(
            element_id=opening_id,
            ifc_guid=raw.guid,
            kind=raw.kind,
            width=None if raw.width is None else _r(raw.width),
            height=None if raw.height is None else _r(raw.height),
            head_height=head,
            shutter_box_height=box,
            slot_id=None,
            option_value_id=None,
            source=None,
        )

    # --- Typen und Standardwerte ------------------------------------------------------------------------

    def match_types(self, roof_form: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """Typ je Öffnung über die Maße (E-HM-37), Standard je Slot; liefert `defaults` und
        `element_defaults`."""
        options = {o.id: o for o in self.catalog.option_values}
        chosen: dict[str, tuple[str, str]] = {}
        matched: list[HouseImportOpening] = []
        for opening in self.report_openings:
            given = self.decisions.element_defaults.get(opening.element_id)
            if given:
                valid = {s: v for s, v in given.items() if v in options and options[v].slot_id == s}
                if len(valid) != len(given):
                    self.findings.add("open", "decision_invalid", element_id=opening.element_id)
                if valid:
                    slot_id, value_id = sorted(valid.items())[0]
                    chosen[opening.element_id] = (slot_id, value_id)
                    matched.append(
                        opening.model_copy(
                            update={"slot_id": slot_id, "option_value_id": value_id, "source": "office"}
                        )
                    )
                    continue
            candidates = self.candidates(opening)
            if len(candidates) == 1:
                option = candidates[0]
                chosen[opening.element_id] = (option.slot_id, option.id)
                matched.append(
                    opening.model_copy(
                        update={"slot_id": option.slot_id, "option_value_id": option.id, "source": "catalog"}
                    )
                )
                continue
            self.findings.add(
                "open",
                "opening_type_ambiguous" if candidates else "opening_type_unmatched",
                element_id=opening.element_id,
                ifc_guid=opening.ifc_guid,
                width=opening.width,
                height=opening.height,
                head_height=opening.head_height,
                shutter_box_height=opening.shutter_box_height,
            )
            matched.append(opening)
        self.report_openings = matched

        defaults = self.slot_defaults(chosen, roof_form)
        element_defaults: dict[str, dict[str, str]] = {}
        for element_id, (slot_id, value_id) in sorted(chosen.items()):
            if defaults.get(slot_id) != value_id:
                element_defaults.setdefault(element_id, {})[slot_id] = value_id
        return defaults, element_defaults

    def slot_defaults(self, chosen: Mapping[str, tuple[str, str]], roof_form: str) -> dict[str, str]:
        """Angabe des Büros, sonst der häufigste erkannte Wert, sonst der erste Wert des Slots, der zum Dach
        passt: Dachform mit der Form des Templates, Dachaufbau flach bzw. geneigt (E-HM-65)."""
        options = {o.id: o for o in self.catalog.option_values}
        shapes = {s.id: s.form for s in self.catalog.roof_shapes}
        kinds = {t.id: t.kind for t in self.catalog.roof_types}

        def fits(option: HouseOptionValue) -> bool:
            shape, roof_type = option.assigns.roof_shape_id, option.assigns.roof_type_id
            if shape is not None:
                return shapes.get(shape) == roof_form
            if roof_type is not None:
                return kinds.get(roof_type) == ("flat" if roof_form == "flat" else "pitched")
            return True

        by_slot: dict[str, Counter[str]] = {}
        for slot_id, value_id in chosen.values():
            by_slot.setdefault(slot_id, Counter())[value_id] += 1
        order = {o.id: (o.sort_order, o.id) for o in self.catalog.option_values}
        defaults: dict[str, str] = {}
        for slot in sorted(self.catalog.slots, key=lambda s: (s.sort_order, s.id)):
            given = self.decisions.defaults.get(slot.id)
            if given is not None:
                if given in options and options[given].slot_id == slot.id:
                    defaults[slot.id] = given
                    continue
                self.findings.add("open", "decision_invalid", value=given, slot=slot.id)
            counts = by_slot.get(slot.id)
            if counts:
                defaults[slot.id] = min(counts, key=lambda v: (-counts[v], order[v]))
                continue
            values = sorted(
                (o for o in self.catalog.option_values if o.slot_id == slot.id), key=lambda o: order[o.id]
            )
            fitting = [o for o in values if fits(o)] or values
            if fitting:
                defaults[slot.id] = fitting[0].id
        return defaults

    def candidates(self, opening: HouseImportOpening) -> list[HouseOptionValue]:
        def close(a: float | None, b: float) -> bool:
            return a is not None and abs(a - b) <= TOL + 1e-9

        if opening.kind == "window":
            types = {
                t.id
                for t in self.catalog.window_types
                if close(opening.width, t.width)
                and close(opening.height, t.height)
                and close(opening.head_height, t.head_height)
                and close(opening.shutter_box_height, t.shutter_box_height)
            }
            return [o for o in self.catalog.option_values if o.assigns.window_type_id in types]
        types = {
            t.id
            for t in self.catalog.door_types
            if close(opening.width, t.width) and close(opening.height, t.height)
        }
        return [o for o in self.catalog.option_values if o.assigns.door_type_id in types]

    # --- Platten und Dach -------------------------------------------------------------------------------

    def ground_slab(self, storey: str, storey_z: float, contour: Polygon) -> dict[str, Any] | None:
        slabs = [
            s
            for s in self.raw.slabs
            if s.storey_guid == storey
            and s.predefined_type in ("FLOOR", "BASESLAB", None, "NOTDEFINED")
            and abs(s.z_max - storey_z) <= 0.1
        ]
        if not slabs:
            self.findings.add("error", "ground_slab_missing")
            return None
        slab = max(slabs, key=lambda s: _polygon(s.footprint).area)
        if abs(slab.z_max - storey_z) > TOL:
            self.findings.add(
                "warning", "ground_slab_offset", ifc_guid=slab.guid, offset=_r(slab.z_max - storey_z)
            )
        area = _polygon(slab.footprint).area
        if abs(area - contour.area) > OUTDATED * contour.area:
            self.findings.add(
                "warning",
                "ground_slab_area_mismatch",
                ifc_guid=slab.guid,
                area=round(area, 2),
                contour=round(contour.area, 2),
            )
        return {
            "id": f"slab-{slab.guid}",
            "source_ifc_guid": slab.guid,
            "kind": "ground",
            "thickness": _r(slab.z_max - slab.z_min),
        }

    def floor_slab(self, storey: RawStorey, contour: Polygon) -> dict[str, Any] | None:
        """Decke unter einem Obergeschoss: Oberkante auf der Höhe des Geschosses (±0,10 m), über mehr als der
        Hälfte der Kontur (Treppenloch erlaubt), gleich welchem Geschoss sie zugeordnet ist."""
        slabs = [
            s
            for s in self.raw.slabs
            if s.predefined_type in ("FLOOR", None, "NOTDEFINED")
            and abs(s.z_max - storey.z) <= 0.1
            and _polygon(s.footprint).intersection(contour).area > 0.5 * contour.area
        ]
        if not slabs:
            self.findings.add("error", "floor_slab_missing", ifc_guid=storey.guid, name=storey.name)
            return None
        slab = max(slabs, key=lambda s: _polygon(s.footprint).area)
        if abs(slab.z_max - storey.z) > TOL:
            self.findings.add(
                "warning", "floor_slab_offset", ifc_guid=slab.guid, offset=_r(slab.z_max - storey.z)
            )
        return {
            "id": f"slab-{slab.guid}",
            "source_ifc_guid": slab.guid,
            "kind": "floor",
            "thickness": _r(slab.z_max - slab.z_min),
        }

    def roof(
        self,
        ground_z: float,
        exterior: list[RawWall],
        contour_world: Polygon,
        ring: list[tuple[float, float]],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Dach über dem obersten Geschoss (`exterior`, `contour_world`): Angabe des Büros, sonst aus dem IFC
        ein Flachdach (E-HM-35) oder ein geneigtes Dach (`roof.py`). Ohne erkanntes Dach ein Platzhalter."""
        decided = self.decisions.roof
        if decided is not None:
            self.findings.add("info", "roof_set_by_office", form=decided.design.form)
            return decided.model_dump(mode="json"), None
        shell = _close(_polygon(w.footprint) for w in exterior)
        top_of_walls = max((w.z_max for w in exterior), default=ground_z)
        fallback = {
            "bearing_height": _r(top_of_walls - ground_z),
            "parapet_height": 0.0,
            "eave_overhang": 0.0,
            "verge_overhang": 0.0,
            "design": FLAT_DESIGN,
        }
        if not self.raw.roofs:
            self.findings.add("error", "roof_missing")
            return fallback, None
        if len(self.raw.roofs) > 1:
            self.findings.add("error", "roof_multiple", count=float(len(self.raw.roofs)))
            return fallback, None
        roof = self.raw.roofs[0]
        faces = _faces(roof)
        if any(FLAT_DEG < slope < 90 - FLAT_DEG for slope, _, _ in faces):
            result = recognize(
                underside(roof, self.origin, ground_z),
                ring,
                translate(shell, -self.origin[0], -self.origin[1]),
                self.build_roof,
            )
            if isinstance(result, NotRecognized):
                self.findings.add("open", "roof_form_not_recognized", ifc_guid=roof.guid, **result.params)
                return fallback, None
            return result.placement, None
        up: defaultdict[float, float] = defaultdict(float)
        down: defaultdict[float, float] = defaultdict(float)
        for slope, normal_z, (z, area) in faces:
            if slope <= FLAT_DEG:
                (up if normal_z > 0 else down)[round(z, 3)] += area
        if not up or not down:
            self.findings.add(
                "open", "roof_form_not_recognized", ifc_guid=roof.guid, reason="flat", slopes=""
            )
            return fallback, None
        z_top = max(up, key=lambda z: up[z])
        z_bottom = max(down, key=lambda z: down[z])
        if z_top <= z_bottom:
            self.findings.add(
                "open", "roof_form_not_recognized", ifc_guid=roof.guid, reason="flat", slopes=""
            )
            return fallback, None
        footprint = unary_union(
            [
                p
                for a, b, c in roof.triangles
                if (p := Polygon([roof.vertices[a][:2], roof.vertices[b][:2], roof.vertices[c][:2]])).area
                > 1e-9
            ]
        ).buffer(0)
        outer = unary_union([Polygon(part.exterior) for part in _parts(shell)])
        overhang = 0.0
        if not footprint.difference(outer).is_empty:
            overhang = max(
                outer.boundary.distance(Point(x, y))
                for part in _parts(footprint)
                for x, y in part.exterior.coords
                if not outer.covers(Point(x, y))
            )
        if contour_world.difference(footprint).area > OUTDATED * contour_world.area:
            self.findings.add("warning", "roof_incomplete", ifc_guid=roof.guid)
        parapet = top_of_walls - z_top
        placement = {
            "bearing_height": _r(z_bottom - ground_z),
            "parapet_height": _r(parapet) if parapet > TOL else 0.0,
            "eave_overhang": _r(overhang) if overhang > TOL else 0.0,
            "verge_overhang": _r(overhang) if overhang > TOL else 0.0,
            "design": FLAT_DESIGN,
        }
        slab = {
            "id": f"slab-{roof.guid}",
            "source_ifc_guid": roof.guid,
            "kind": "roof",
            "thickness": _r(z_top - z_bottom),
        }
        return placement, slab

    # --- Gesamt -----------------------------------------------------------------------------------------

    def door_choice(
        self,
        choice: HouseDoorChoice | None,
        role: Literal["entrance", "garage_door"],
        openings: list[dict[str, Any]],
        rooms: list[Room],
    ) -> str | None:
        """Vorschlag: die einzige Außentür in einen Raum, dessen Typ die Rolle trägt (E-HM-13)."""
        exterior_doors = [o for o in openings if o["kind"] == "door" and o["host_kind"] == "envelope_segment"]
        code = "entrance" if role == "entrance" else "garage_door"
        if choice is not None:
            if choice.opening_id is None or choice.opening_id in {o["id"] for o in exterior_doors}:
                return str(choice.opening_id) if choice.opening_id is not None else None
            self.findings.add("open", "decision_invalid", element_id=choice.opening_id, value=code)
        typed = {t.id: t.exterior_door_role for t in self.catalog.room_types}
        room_type = {r.id: r.room_type_id for r in rooms}
        candidates = [
            o["id"]
            for o in exterior_doors
            if any(typed.get(room_type.get(r, "")) == role for r in o["adjacent_room_ids"])
        ]
        if len(candidates) == 1:
            return str(candidates[0])
        if len(candidates) > 1:
            self.findings.add(
                "open",
                "entrance_ambiguous" if role == "entrance" else "garage_door_ambiguous",
                count=float(len(candidates)),
            )
        elif role == "entrance":
            self.findings.add("open", "entrance_missing")
        return None

    def run(self) -> tuple[HouseTemplate | None, HouseImportReport]:
        template = self.build()
        if template is None and not any(f.severity == "error" for f in self.findings.items):
            self.findings.add("error", "template_not_built")
        report = HouseImportReport(
            findings=self.findings.items,
            zones=[self.zone_report(z) for z in self.zones],
            openings=self.report_openings,
            summary=self.summary,
            publishable=template is not None and not self.findings.has_blocking(),
        )
        return template, report

    def zone_report(self, zone: Zone) -> HouseImportZone:
        return HouseImportZone(
            ifc_guid=zone.space.guid,
            result=zone.match.result,
            room_type_id=zone.match.room_type_id,
            source="office" if zone.decided else zone.match.source,
            raw=zone.match.raw,
            values=[HouseImportZoneSource(kind=s.kind, raw=s.raw) for s in zone.space.sources],
            room_id=zone.room_id,
            share=zone.share,
        )

    def build(self) -> HouseTemplate | None:
        for guid in self.raw.failed:
            self.findings.add("warning", "geometry_failed", ifc_guid=guid)
        if self.raw.skipped:
            self.findings.add("info", "elements_not_read", counts=self.raw.skipped)
        storeys = self.storeys()
        roof_levels = sum(1 for f in self.findings.items if f.code == "roof_level")
        self.summary = self.summary.model_copy(
            update={
                "storeys": len(storeys),
                "roof_levels": roof_levels,
                "windows": sum(o.kind == "window" for o in self.raw.openings),
                "doors": sum(o.kind == "door" for o in self.raw.openings),
                "zones": len(self.raw.spaces),
            }
        )
        if not storeys:
            self.findings.add("error", "no_storey")
            return None
        by_guid = {s.guid: s for s in self.raw.storeys}
        ground = by_guid[storeys[0]]

        levels: list[dict[str, Any]] = []
        envelope: list[dict[str, Any]] = []
        interior_walls: list[dict[str, Any]] = []
        openings: list[dict[str, Any]] = []
        slabs: list[dict[str, Any]] = []
        rooms: list[Room] = []
        room_levels: dict[str, str] = {}
        ring: list[tuple[float, float]] = []
        roles: list[str | None] = []
        counts: Counter[str] = Counter()
        top: tuple[str, list[RawWall], Polygon] | None = None
        for index, guid in enumerate(storeys):
            storey = by_guid[guid]
            level_id = f"level-{guid}"
            found = self.walls(guid)
            if found is None:
                return None
            exterior, interior, main = found
            contour_world = self.contour(exterior)
            if contour_world is None:
                return None
            self.compare_flags(exterior, interior)
            if index == 0:
                minx, miny, maxx, maxy = contour_world.bounds
                self.origin = (minx, miny)
                self.summary = self.summary.model_copy(
                    update={
                        "inner_width": _r(maxx - minx),
                        "inner_depth": _r(maxy - miny),
                        "inner_area": round(contour_world.area, 2),
                    }
                )
            ox, oy = self.origin
            contour = translate(contour_world, -ox, -oy)
            own = _ring(contour.exterior.coords)
            if index == 0:
                ring = own
            elif not _same_ring(own, ring):
                # Alle Geschosse haben dieselbe Bezugskontur (E-HM-63); weiter mit der des Erdgeschosses
                self.findings.add("error", "storey_contour_differs", ifc_guid=guid, name=storey.name)
            counts.update(exterior=len(exterior), interior=len(interior))

            holes = [translate(Polygon(r), -ox, -oy) for part in _parts(main) for r in part.interiors]
            small = [h for h in holes if h.area < SMALL_AREA]
            if small:
                self.findings.add("warning", "small_area_ignored", count=float(len(small)))
            holes = [h for h in holes if h.area >= SMALL_AREA]
            storey_rooms = self.rooms(index, holes, self.zone_matches(guid))
            ignored_rooms = [
                h for h in holes if not any(r.polygon.representative_point().within(h) for r in storey_rooms)
            ]
            walls_local = {w.guid: translate(_polygon(w.footprint), -ox, -oy) for w in [*exterior, *interior]}
            edges = self.edges(ring, exterior, walls_local, index)
            axes = self.axes(interior)
            self.snap(axes, contour)
            pieces = self.pieces(axes, storey_rooms)
            openings += self.openings(
                guid,
                storey.z,
                edges,
                pieces,
                {w.guid for w in exterior},
                {w.guid for w in interior},
                walls_local,
                storey_rooms,
                ignored_rooms,
            )

            if index == 0:
                # Rollen setzt das Büro am Erdgeschoss; die Obergeschosse übernehmen sie je Kante
                roles = [self.decisions.facade_roles.get(edge.id) for edge in edges]
                if not any(roles):
                    self.findings.add("warning", "facade_roles_missing")
            levels.append(
                {
                    "id": level_id,
                    "name": storey.name or ("RDC" if index == 0 else f"R+{index}"),
                    "elevation": _r(storey.z - ground.z),
                }
            )
            envelope.append(
                {
                    "level_id": level_id,
                    "inner_polygon": _xy(ring),
                    "segments": [
                        {
                            "id": edge.id,
                            "source_ifc_guid": edge.guid,
                            "facade_role": roles[i] if i < len(roles) else None,
                        }
                        for i, edge in enumerate(edges)
                    ],
                }
            )
            interior_walls += [
                {
                    "id": p.id,
                    "source_ifc_guid": p.guid,
                    "level_id": level_id,
                    "axis": _xy([p.a, p.b]),
                    "thickness": p.thickness,
                    "adjacent_room_ids": p.rooms,
                }
                for p in pieces
            ]
            rooms += storey_rooms
            room_levels |= {r.id: level_id for r in storey_rooms}
            slab = (
                self.ground_slab(guid, storey.z, contour_world)
                if index == 0
                else self.floor_slab(storey, contour_world)
            )
            if slab is not None:
                slabs.append(slab | {"level_id": level_id})
            top = (level_id, exterior, contour_world)

        assert top is not None
        top_level, top_exterior, top_contour = top
        self.summary = self.summary.model_copy(
            update={
                "exterior_walls": counts["exterior"],
                "interior_walls": counts["interior"],
                "rooms": len(rooms),
            }
        )
        roof, roof_slab = self.roof(ground.z, top_exterior, top_contour, ring)
        if roof_slab is not None:
            slabs.append(roof_slab | {"level_id": top_level})
        defaults, element_defaults = self.match_types(roof["design"]["form"])

        offset = self.decisions.ground_floor_offset
        if offset is None:
            offset = self.raw.ground_floor_offset
            if offset is not None and not -5 <= offset <= 5:
                self.findings.add("warning", "ground_floor_offset_invalid", value=offset)
                offset = None
            if offset is None:
                offset = DEFAULT_GROUND_FLOOR_OFFSET
                self.findings.add("info", "ground_floor_offset_default", value=offset)

        entrance = self.door_choice(self.decisions.entrance, "entrance", openings, rooms)
        garage = self.door_choice(self.decisions.garage_door, "garage_door", openings, rooms)
        name = self.decisions.name or HouseText(fr=self.default_name, de=self.default_name)
        document = {
            "schema_version": 2,
            "slug": self.slug,
            "name": name.model_dump(),
            "source_ifc": self.source.model_dump(mode="json"),
            "ground_floor_offset": offset,
            "levels": levels,
            "envelope": envelope,
            "interior_walls": interior_walls,
            "openings": openings,
            "slabs": slabs,
            "roof": roof,
            "rooms": [
                {
                    "id": r.id,
                    "source_ifc_guid": r.source_guid,
                    "level_id": room_levels[r.id],
                    "room_type_id": r.room_type_id,
                    "polygon": _xy(_ring(r.polygon.exterior.coords)),
                }
                for r in rooms
            ],
            "entrance_opening_id": entrance,
            "garage_door_opening_id": garage,
            "defaults": defaults,
            "element_defaults": element_defaults,
        }
        try:
            return HouseTemplate.model_validate(document)
        except ValidationError as exc:
            self.findings.add("error", "template_invalid", detail=str(exc.errors()[0]["msg"])[:200])
            return None

    def edges(
        self,
        ring: list[tuple[float, float]],
        exterior: list[RawWall],
        walls: dict[str, Polygon],
        storey_index: int,
    ) -> list[Edge]:
        """Ein Segment je Kante der Bezugskontur; Kennung aus der Wand, die die Kante am längsten trägt."""
        owners: list[str | None] = []
        for i, a in enumerate(ring):
            b = ring[(i + 1) % len(ring)]
            line = LineString([a, b])
            lengths = {w.guid: walls[w.guid].buffer(0.002).intersection(line).length for w in exterior}
            best = max(lengths, key=lambda g: lengths[g]) if lengths else None
            owners.append(best if best is not None and lengths[best] > 0 else None)
        counts = Counter(owners)
        seen: Counter[str | None] = Counter()
        # Ohne tragende Wand eigene Kennungen je Geschoss, damit sie über die Geschosse eindeutig bleiben
        anonymous = "seg" if storey_index == 0 else f"seg-s{storey_index}"
        edges = []
        for i, a in enumerate(ring):
            owner = owners[i]
            seen[owner] += 1
            base = f"seg-{owner}" if owner is not None else anonymous
            edge_id = base if counts[owner] == 1 and owner is not None else f"{base}-{seen[owner]}"
            edges.append(Edge(edge_id, owner, a, ring[(i + 1) % len(ring)]))
        return edges


def _same_ring(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> bool:
    """Gleiche Ringe bis 1 mm, gleich mit welchem Punkt sie beginnen."""
    if len(a) != len(b):
        return False
    return any(all(math.dist(a[(i + k) % len(a)], q) <= TOL for i, q in enumerate(b)) for k in range(len(a)))


def _points(geometry: BaseGeometry) -> list[tuple[float, float]]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [(geometry.x, geometry.y)]
    result: list[tuple[float, float]] = []
    for part in getattr(geometry, "geoms", []):
        result += _points(part)
    if isinstance(geometry, LineString):
        result += [(x, y) for x, y in geometry.coords]
    return result


def _room_at(rooms: list[Room], point: tuple[float, float]) -> str | None:
    target = Point(point)
    for room in rooms:
        if room.polygon.buffer(TOL).contains(target):
            return room.id
    return None


def _faces(roof: RawRoof) -> list[tuple[float, float, tuple[float, float]]]:
    """Je Dreieck: Neigung in Grad, z-Anteil der Normalen, (Höhe, Grundrissfläche)."""
    faces = []
    for a, b, c in roof.triangles:
        p, q, r = roof.vertices[a], roof.vertices[b], roof.vertices[c]
        u = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
        v = (r[0] - p[0], r[1] - p[1], r[2] - p[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        if length < 1e-9:
            continue
        nz = n[2] / length
        slope = math.degrees(math.acos(min(1.0, abs(nz))))
        faces.append((slope, nz, ((p[2] + q[2] + r[2]) / 3, length / 2)))
    return faces


def assemble(
    raw: RawModel,
    decisions: HouseDraftDecisions,
    catalog: HouseCatalog,
    source: HouseSourceIfc,
    slug: str,
    default_name: str,
    build_roof: RoofBuilder,
) -> tuple[HouseTemplate | None, HouseImportReport]:
    """`build_roof` erzeugt ein geneigtes Dach mit dem Kern (`engine /roof`); nur bei geneigten Dächern
    gerufen."""
    return Assembler(raw, decisions, catalog, source, slug, default_name, build_roof).run()
