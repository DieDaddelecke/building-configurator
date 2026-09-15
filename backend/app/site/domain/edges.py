"""Grundstückskanten bilden und einordnen (Spez. 5.1.4, Plan 3.3).

Drei Schritte, damit eine Korrektur ohne erneutes Laden der Nachbarn neu eingeordnet werden kann:

1. `split_edges` – Umriss in Kanten zerlegen (nur Geometrie).
2. `edge_facts` – Beobachtungen je Kante aus den Nachbarparzellen; werden gespeichert.
3. `classify` – Kantenarten aus Geometrie, Beobachtungen und Korrekturen; deterministisch.

Koordinaten Lambert-93 in Metern. Richtungen als Azimut: 0° = Norden, im Uhrzeigersinn.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

import shapely
import shapely.ops
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.site.domain import tolerances as tol

EdgeKind = Literal["street", "side", "rear", "other"]
OverrideKind = Literal["street", "not_street", "side", "rear", "other"]
ClassificationSource = Literal["auto", "customer", "architect"]
StreetCandidate = Literal["none", "public", "private_road", "road"]
NeighbourCoverage = Literal["complete", "partial", "none"]
"""Liegt die Umgebung (Suchradius) vollständig, teilweise oder gar nicht im importierten Kataster?"""
Coord = tuple[float, float]


@dataclass(frozen=True)
class EdgeGeometry:
    seq: int
    ring: int
    """0 = äußerer Ring, ab 1 Löcher."""
    coords: tuple[Coord, ...]

    @property
    def start(self) -> Coord:
        return self.coords[0]

    @property
    def end(self) -> Coord:
        return self.coords[-1]

    @property
    def length_m(self) -> float:
        return float(LineString(self.coords).length)

    @property
    def direction_deg(self) -> float:
        """Azimut der Sehne vom Anfang zum Ende."""
        return azimuth(self.start, self.end)

    @property
    def normal_azimuth_deg(self) -> float:
        """Azimut der Außennormalen. Das Grundstück liegt links der Laufrichtung (`orient`)."""
        return (self.direction_deg + 90.0) % 360.0


@dataclass(frozen=True)
class NeighbourParcel:
    idu: str
    geometry: BaseGeometry
    has_building: bool


@dataclass(frozen=True)
class RoadLine:
    """Straßenachse (BD TOPO) in Lambert-93."""

    name: str | None
    geometry: LineString


@dataclass(frozen=True)
class EdgeFacts:
    neighbour_share: float
    """Anteil der Kantenlänge innerhalb `NEIGHBOUR_DISTANCE_M` einer Nachbarparzelle."""
    adjacent: tuple[str, ...]
    street_candidate: StreetCandidate
    probe_in_parcel: bool
    """Ein Punkt `PROBE_OFFSET_M` außerhalb der Kantenmitte liegt in einer Parzelle."""
    road_share: float | None = None
    """Anteil der Kante mit Straßenachse außen in höchstens `ROAD_DISTANCE_M`; None ohne Straßendaten."""
    street_name: str | None = None


@dataclass(frozen=True)
class Override:
    kind: OverrideKind
    source: Literal["customer", "architect"]


@dataclass(frozen=True)
class ClassifiedEdge:
    geometry: EdgeGeometry
    facts: EdgeFacts
    kind: EdgeKind
    kind_auto: EdgeKind
    source: ClassificationSource
    confidence: float
    override: OverrideKind | None


@dataclass(frozen=True)
class Classification:
    edges: tuple[ClassifiedEdge, ...]
    main_street_seq: int | None
    street_azimuth_deg: float | None
    garden_azimuth_deg: float | None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def binding(self) -> bool:
        """Kundenkorrekturen ohne Bestätigung durch den Architekten machen den Baurahmen nicht bindend."""
        return not any(e.source == "customer" for e in self.edges)


# ---------------------------------------------------------------------------
# Winkel
# ---------------------------------------------------------------------------


def azimuth(a: Coord, b: Coord) -> float:
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.0


def turn_deg(a: float, b: float) -> float:
    """Richtungsänderung zwischen zwei gerichteten Azimuten, 0–180°."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def axis_angle_deg(a: float, b: float) -> float:
    """Winkel zwischen zwei ungerichteten Achsen, 0–90°."""
    diff = turn_deg(a, b)
    return min(diff, 180.0 - diff)


# ---------------------------------------------------------------------------
# 1. Kanten bilden
# ---------------------------------------------------------------------------


def split_edges(polygon: Polygon) -> list[EdgeGeometry]:
    """Zerlegt die Ringe in Kanten. Aufeinanderfolgende Segmente, deren Richtung um weniger als
    `MERGE_ANGLE_DEG` von der Sehne der laufenden Kante abweicht, bilden eine Kante.

    Ein Ring beginnt am Eckpunkt mit der größten Richtungsänderung; damit ist die Zerlegung
    unabhängig vom Startpunkt der Quelldaten.
    """
    edges: list[EdgeGeometry] = []
    rings = [polygon.exterior, *polygon.interiors]
    for ring_index, ring in enumerate(rings):
        for coords in _ring_edges(list(ring.coords)):
            edges.append(EdgeGeometry(seq=len(edges) + 1, ring=ring_index, coords=tuple(coords)))
    return edges


def _ring_edges(ring: list[tuple[float, ...]]) -> list[list[Coord]]:
    points: list[Coord] = []
    for raw in ring[:-1]:
        point = (float(raw[0]), float(raw[1]))
        if not points or math.dist(points[-1], point) > tol.MIN_SEGMENT_M:
            points.append(point)
    if len(points) > 1 and math.dist(points[0], points[-1]) <= tol.MIN_SEGMENT_M:
        points.pop()
    count = len(points)
    if count < 3:
        return [[*points, points[0]]] if points else []

    def turn_at(i: int) -> float:
        return turn_deg(azimuth(points[i - 1], points[i]), azimuth(points[i], points[(i + 1) % count]))

    start = max(range(count), key=lambda i: (round(turn_at(i), 6), -i))
    ordered = points[start:] + points[:start]
    result: list[list[Coord]] = []
    current = [ordered[0], ordered[1]]
    for index in range(2, count + 1):
        nxt = ordered[index % count]
        chord = azimuth(current[0], current[-1])
        segment = azimuth(current[-1], nxt)
        if turn_deg(chord, segment) < tol.MERGE_ANGLE_DEG:
            current.append(nxt)
        else:
            result.append(current)
            current = [current[-1], nxt]
    result.append(current)
    return result


# ---------------------------------------------------------------------------
# 2. Beobachtungen aus der Umgebung
# ---------------------------------------------------------------------------


def edge_facts(
    edges: Sequence[EdgeGeometry],
    neighbours: Sequence[NeighbourParcel],
    roads: Sequence[RoadLine] | None = None,
    site: Polygon | None = None,
) -> list[EdgeFacts]:
    """Grenzt die Kante an Nachbarparzellen, liegt außen eine Straßenachse, ist ein Nachbar ein Weg?

    `roads=None` heißt: keine Straßendaten für das Gebiet (nicht: keine Straße in der Nähe).
    """
    raw = [n.geometry for n in neighbours]
    buffered = [g.buffer(tol.NEIGHBOUR_DISTANCE_M) for g in raw]
    buffered_tree = shapely.STRtree(buffered)
    raw_tree = shapely.STRtree(raw)
    built = shapely.unary_union([n.geometry for n in neighbours if n.has_building]) if neighbours else None
    road_tree = shapely.STRtree([r.geometry for r in roads]) if roads else None
    facts: list[EdgeFacts] = []
    for edge in edges:
        line = LineString(edge.coords)
        length = float(line.length)
        shares: list[tuple[float, str, int]] = []
        touching: list[BaseGeometry] = []
        for index in buffered_tree.query(line):
            part = line.intersection(buffered[int(index)])
            if part.is_empty:
                continue
            touching.append(buffered[int(index)])
            shares.append((float(part.length) / length, neighbours[int(index)].idu, int(index)))
        share = float(line.intersection(shapely.unary_union(touching)).length) / length if touching else 0.0
        adjacent = tuple(
            idu
            for part_share, idu, _ in sorted(shares, key=lambda s: (-s[0], s[1]))
            if part_share >= tol.ADJACENT_SHARE_MIN or part_share * length >= tol.ADJACENT_LENGTH_MIN_M
        )
        probe = _outward_probe(edge)
        probe_in_parcel = any(raw[int(i)].contains(probe) for i in raw_tree.query(probe))
        road_share, street_name = (None, None)
        if roads is not None:
            road_share, street_name = _road_share(edge, roads, road_tree, site, built)

        candidate: StreetCandidate = "none"
        if road_share is not None and road_share >= tol.ROAD_SHARE_MIN:
            candidate = "road"
        elif share < tol.NEIGHBOUR_SHARE_STREET_MAX:
            candidate = "public"
        elif shares:
            dominant = neighbours[max(shares, key=lambda s: (s[0], s[1]))[2]]
            if not dominant.has_building and _max_width_m(dominant.geometry) < tol.PRIVATE_ROAD_MAX_WIDTH_M:
                candidate = "private_road"
        facts.append(
            EdgeFacts(
                neighbour_share=round(min(share, 1.0), 4),
                adjacent=adjacent,
                street_candidate=candidate,
                probe_in_parcel=probe_in_parcel,
                road_share=road_share,
                street_name=street_name,
            )
        )
    return facts


def _road_share(
    edge: EdgeGeometry,
    roads: Sequence[RoadLine],
    tree: shapely.STRtree | None,
    site: Polygon | None,
    built: BaseGeometry | None,
) -> tuple[float, str | None]:
    """Anteil der Stichproben entlang der Kante, von denen aus eine Straßenachse außen, in höchstens
    `ROAD_DISTANCE_M` und ohne Weg durch das Grundstück oder ein bebautes Nachbargrundstück erreichbar ist."""
    if tree is None or not roads:
        return 0.0, None
    line = LineString(edge.coords)
    count = max(3, min(tol.ROAD_SAMPLES_MAX, math.ceil(float(line.length) / tol.ROAD_SAMPLE_SPACING_M)))
    normal = math.radians(edge.normal_azimuth_deg)
    outward = (math.sin(normal), math.cos(normal))
    hits = 0
    names: dict[str, int] = {}
    for i in range(count):
        sample = line.interpolate((i + 0.5) / count, normalized=True)
        candidates = tree.query(sample.buffer(tol.ROAD_DISTANCE_M))
        best: tuple[float, int, Point] | None = None
        for index in candidates:
            road = roads[int(index)].geometry
            nearest = shapely.ops.nearest_points(sample, road)[1]
            distance = float(sample.distance(nearest))
            if distance > tol.ROAD_DISTANCE_M:
                continue
            dx, dy = nearest.x - sample.x, nearest.y - sample.y
            if dx * outward[0] + dy * outward[1] <= 0:
                continue
            path = LineString([sample, nearest])
            if site is not None and float(path.intersection(site).length) > tol.SITE_CROSSING_MAX_M:
                continue
            if built is not None and float(path.intersection(built).length) > tol.BUILT_CROSSING_MAX_M:
                continue
            if best is None or distance < best[0]:
                best = (distance, int(index), nearest)
        if best is not None:
            hits += 1
            name = roads[best[1]].name
            if name:
                names[name] = names.get(name, 0) + 1
    share = round(hits / count, 4)
    # Name nur, wenn die Achse die Kante tatsächlich begleitet; ein Streifkontakt an der Ecke zählt nicht
    street_name = (
        max(sorted(names), key=lambda n: names[n]) if names and share >= tol.ROAD_SHARE_MIN else None
    )
    return share, street_name


def _outward_probe(edge: EdgeGeometry) -> Point:
    line = LineString(edge.coords)
    middle = line.interpolate(0.5, normalized=True)
    normal = math.radians(edge.normal_azimuth_deg)
    return Point(
        middle.x + tol.PROBE_OFFSET_M * math.sin(normal), middle.y + tol.PROBE_OFFSET_M * math.cos(normal)
    )


def _max_width_m(geometry: BaseGeometry) -> float:
    """Durchmesser des größten Inkreises: Breite eines Weges unabhängig von Knicken."""
    radius = shapely.maximum_inscribed_circle(geometry, tolerance=0.05)
    return 2.0 * float(radius.length)


# ---------------------------------------------------------------------------
# 3. Einordnen
# ---------------------------------------------------------------------------


def classify(
    edges: Sequence[EdgeGeometry],
    facts: Sequence[EdgeFacts],
    overrides: Mapping[int, Override] | None = None,
    *,
    site_area_m2: float,
    neighbour_coverage: "NeighbourCoverage" = "complete",
) -> Classification:
    """Ordnet jede Kante als `street`, `side`, `rear` oder `other` ein (Spez. 5.1.4).

    Korrekturen: `street` und `not_street` (Kunde) legen nur fest, ob eine Kante Straße ist; Seite
    und Hinten werden daraus abgeleitet. `side`, `rear`, `other` (Architekt) gelten wörtlich.
    """
    overrides = overrides or {}
    automatic = _classify(edges, facts, {}, site_area_m2, neighbour_coverage)
    if not overrides:
        return automatic
    corrected = _classify(edges, facts, overrides, site_area_m2, neighbour_coverage)
    auto_kinds = {e.geometry.seq: e.kind for e in automatic.edges}
    return Classification(
        edges=tuple(
            ClassifiedEdge(
                geometry=e.geometry,
                facts=e.facts,
                kind=e.kind,
                kind_auto=auto_kinds[e.geometry.seq],
                source=e.source,
                confidence=e.confidence,
                override=e.override,
            )
            for e in corrected.edges
        ),
        main_street_seq=corrected.main_street_seq,
        street_azimuth_deg=corrected.street_azimuth_deg,
        garden_azimuth_deg=corrected.garden_azimuth_deg,
        warnings=corrected.warnings,
    )


def _corner_lot(
    by_seq: Mapping[int, tuple[EdgeGeometry, EdgeFacts]],
    street_conf: Mapping[int, float],
    ring_members: Mapping[int, list[int]],
) -> bool:
    """Zwei sichere Straßenfronten von je mindestens `CORNER_MIN_EDGE_M` mit `CORNER_ANGLE_DEG` Unterschied.

    Liegen beide an einem durchgehenden Straßenabschnitt, darf zwischen ihnen nur ein kurzer Eckabschnitt
    (abgeschrägte Ecke, Knick der Katastergrenze, zusammen höchstens `CORNER_CUT_MAX_M`) liegen. So bleiben
    Kurven derselben Straße und kleine Vorsprünge ohne Warnung.
    """
    confident = {s for s, c in street_conf.items() if c >= tol.REVIEW_CONFIDENCE_BELOW}
    for members in ring_members.values():
        count = len(members)
        fronts = [
            i
            for i, s in enumerate(members)
            if s in confident and by_seq[s][0].length_m >= tol.CORNER_MIN_EDGE_M
        ]
        for a_index, a_pos in enumerate(fronts):
            for b_pos in fronts[a_index + 1 :]:
                a, b = by_seq[members[a_pos]][0], by_seq[members[b_pos]][0]
                if axis_angle_deg(a.direction_deg, b.direction_deg) < tol.CORNER_ANGLE_DEG:
                    continue
                # Beide Richtungen um den Ring prüfen: Verbindung nur über kurze Straßenkanten?
                for step in (1, -1):
                    between: list[EdgeGeometry] = []
                    position = (a_pos + step) % count
                    while position != b_pos:
                        between.append(by_seq[members[position]][0])
                        position = (position + step) % count
                    if not between:
                        return True
                    if all(
                        members[(a_pos + step * (k + 1)) % count] in street_conf for k in range(len(between))
                    ) and (
                        all(e.length_m < tol.CORNER_MIN_EDGE_M for e in between)
                        and sum(e.length_m for e in between) <= tol.CORNER_CUT_MAX_M
                    ):
                        return True
                # Getrennte Straßenabschnitte in verschiedenen Richtungen, z. B. Ecke mit Nachbarsplitter
                if not _same_street_run(members, street_conf, a_pos, b_pos):
                    return True
    return False


def _same_street_run(members: list[int], street_conf: Mapping[int, float], a_pos: int, b_pos: int) -> bool:
    """Liegen a und b in einem zusammenhängenden Lauf von Straßenkanten (in einer der beiden Richtungen)?"""
    count = len(members)
    for step in (1, -1):
        position = a_pos
        while members[position] in street_conf:
            if position == b_pos:
                return True
            position = (position + step) % count
            if position == a_pos:
                return True
    return False


def _classify(
    edges: Sequence[EdgeGeometry],
    facts: Sequence[EdgeFacts],
    overrides: Mapping[int, Override],
    site_area_m2: float,
    neighbour_coverage: "NeighbourCoverage",
) -> Classification:
    by_seq = {e.seq: (e, f) for e, f in zip(edges, facts, strict=True)}
    street_conf: dict[int, float] = {}
    for edge, fact in by_seq.values():
        override = overrides.get(edge.seq)
        if edge.ring > 0 and (override is None or override.source != "architect"):
            continue
        if override is not None:
            if override.kind == "street":
                street_conf[edge.seq] = 1.0
            continue
        if fact.street_candidate == "road":
            # Straßenachse bestätigt; liegt die Straße auf einer eigenen Parzelle, etwas unsicherer
            confirmed = 0.95 if fact.neighbour_share < tol.NEIGHBOUR_SHARE_STREET_MAX else 0.8
            street_conf[edge.seq] = confirmed if neighbour_coverage != "none" else 0.7
            continue
        if neighbour_coverage == "none":
            continue
        if fact.street_candidate == "public":
            if fact.road_share is not None:
                conf = tol.UNCONFIRMED_STREET_CONFIDENCE  # keine Achse in Reichweite: Grünfläche, Bach, Bahn?
            else:
                conf = 0.6 if fact.probe_in_parcel else 0.9
            if neighbour_coverage == "partial":
                conf = min(conf, tol.PARTIAL_COVERAGE_STREET_CONFIDENCE)
            street_conf[edge.seq] = conf
        elif fact.street_candidate == "private_road" and fact.road_share is None:
            # Ohne Straßendaten bleibt ein schmaler, unbebauter Nachbar ein möglicher Weg. Mit Straßendaten
            # und ohne Achse ist er meist Zufahrt oder Grünstreifen: Nachbarkante, unsicher (unten)
            street_conf[edge.seq] = tol.PRIVATE_ROAD_STREET_CONFIDENCE

    streets = [by_seq[s][0] for s in sorted(street_conf)]
    # Hauptstraße: erst die sicheren Straßenkanten, dann die längste. Sonst würde eine lange unsichere Kante
    # (Grünfläche hinter dem Grundstück) Hauptstraße, und Straßen- und Gartenseite wären vertauscht
    main = (
        max(
            streets,
            key=lambda e: (street_conf[e.seq] >= tol.REVIEW_CONFIDENCE_BELOW, round(e.length_m, 3), -e.seq),
        )
        if streets
        else None
    )
    frontage = sum(e.length_m for e in streets)
    flag_lot = (
        bool(streets) and frontage < tol.FLAG_LOT_MAX_FRONTAGE_M and site_area_m2 > tol.FLAG_LOT_MIN_AREA_M2
    )
    ring_members: dict[int, list[int]] = {}
    for edge in edges:
        ring_members.setdefault(edge.ring, []).append(edge.seq)
    corner_lot = _corner_lot(by_seq, street_conf, ring_members)

    result: list[ClassifiedEdge] = []
    for edge, fact in by_seq.values():
        override = overrides.get(edge.seq)
        source: ClassificationSource = override.source if override else "auto"
        kind: EdgeKind
        if edge.seq in street_conf:
            kind, confidence = "street", street_conf[edge.seq]
        elif override is not None and override.kind in ("side", "rear", "other"):
            kind, confidence = cast(EdgeKind, override.kind), 1.0
        elif edge.ring > 0:
            kind, confidence = "other", 1.0
        elif main is None:
            kind, confidence = "other", 0.0
        else:
            members = ring_members[edge.ring]
            position = members.index(edge.seq)
            prev_seq = members[position - 1]
            next_seq = members[(position + 1) % len(members)]
            touches_street = prev_seq in street_conf or next_seq in street_conf
            angle = axis_angle_deg(edge.direction_deg, main.direction_deg)
            if touches_street:
                kind, confidence = "side", (0.85 if angle >= tol.REAR_ANGLE_DEG else 0.6)
            elif angle < tol.REAR_ANGLE_DEG:
                kind, confidence = "rear", 0.8
            else:
                kind, confidence = "side", 0.7
            if flag_lot or (fact.street_candidate == "private_road" and override is None):
                confidence = min(confidence, tol.PRIVATE_ROAD_STREET_CONFIDENCE)
        result.append(
            ClassifiedEdge(
                geometry=edge,
                facts=fact,
                kind=kind,
                kind_auto=kind,
                source=source,
                confidence=confidence,
                override=override.kind if override else None,
            )
        )

    warnings: list[str] = []
    if neighbour_coverage == "none":
        warnings.append("no_neighbour_data")
    elif neighbour_coverage == "partial":
        warnings.append("neighbour_data_incomplete")
    if main is None:
        warnings.append("no_street_edge")
    if corner_lot:
        warnings.append("corner_lot")
    if flag_lot:
        warnings.append("flag_lot")
    if any(e.source == "auto" and e.confidence < tol.REVIEW_CONFIDENCE_BELOW for e in result):
        warnings.append("edges_need_review")
    if any(e.source == "customer" for e in result):
        warnings.append("customer_corrections_unconfirmed")

    street_azimuth = round(main.normal_azimuth_deg, 2) if main else None
    garden_azimuth = round((main.normal_azimuth_deg + 180.0) % 360.0, 2) if main else None
    return Classification(
        edges=tuple(result),
        main_street_seq=main.seq if main else None,
        street_azimuth_deg=street_azimuth,
        garden_azimuth_deg=garden_azimuth,
        warnings=tuple(warnings),
    )
