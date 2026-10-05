"""Geneigtes Dach aus den Dachflächen des IFC (docs/PLAN_HAUSMODELL.md 3.6, Ergänzung 11; E-HM-65).

Das Dach im IFC ist ein Platzhalter: Der Kern erzeugt es aus Form und Parametern (`engine /roof`), weil sich
der Umriss mit dem Wandprofil ändert. Der Import leitet Form und Parameter aus der Unterseite des Dachkörpers
ab und vergleicht das Dach des Kerns mit ihr:

1. Unterseite: die nach unten zeigenden Dreiecke in Koordinaten des Templates (Höhen über ±0,00).
2. Je Kante der Bezugskontur die Unterseite auf der Kante: überall gleich hoch und von einer Fläche, die von
   der Kante aus senkrecht nach innen steigt → Traufe, sonst Giebel. Die Höhe der Traufen ist das Auflager,
   ihre Neigung die des Dachs.
3. Weitere Flächen: über der Mitte eines Giebels ein Krüppelwalm (Krüppelhöhe dort, wo seine Ebene die
   Kontur trifft), an eine Traufebene anschließend und flacher der obere Abschnitt einer Mansarde (Knickhöhe
   im Schnitt mit der Traufebene).
4. Überstände: Abstand der Dachkante von der Außenseite der Wand, je Traufe bzw. Giebel gleich. Ohne Giebel
   gilt der Traufüberstand auch am Ortgang.
5. Form aus Kantenarten und Flächen; die Drehung ist die, mit der der Kern dieselben Kantenarten erzeugt.
6. Vergleich der Unterseiten: Umriss und Höhen auf 1 mm, dazu der Rundungsfehler der Neigung (0,01°).

Was nicht passt, ist nicht erkannt (`NotRecognized` mit Grund); das Büro setzt das Dach dann im Entwurf.
"""

import math
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from statistics import fmean, median
from typing import Any

from pydantic import ValidationError
from shapely import LineString, Point, Polygon, unary_union
from shapely.geometry.base import BaseGeometry

from app.house.contract import HouseRoofGeometry, HouseRoofRequest
from app.house.domain.raw import RawRoof

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]

RoofBuilder = Callable[[HouseRoofRequest], HouseRoofGeometry | str]
"""Dach des Kerns (`engine /roof`); ein String ist der Grund, aus dem der Kern die Form ablehnt."""

TOL = 0.001
"""Toleranz des Templates: 1 mm."""
STEEP = math.sin(math.radians(1.0))
"""Flächen ab 89° gelten als senkrecht (Ränder des Dachkörpers, Giebel)."""
FLAT = math.tan(math.radians(1.0))
"""Flächen bis 1° gelten als waagerecht."""
ALIGNED = math.cos(math.radians(0.2))
"""Eine Fläche steigt senkrecht zu einer Kante, wenn ihre Richtung um höchstens 0,2° abweicht."""
NUDGE = 0.001
"""Punkte auf der Kontur: die Fläche darüber wird 1 mm innen gesucht, die Höhe gilt auf der Kontur."""
SAMPLES = (0.01, 0.25, 0.5, 0.75, 0.99)
"""Stellen je Kante der Bezugskontur, als Anteil ihrer Länge."""
REACH = 50.0
"""Längster Weg von der Kontur nach außen bis zur Dachkante, m."""
THICKNESS = 0.3
"""Dicke für die Anfrage an den Kern: Sie hebt nur die Oberseite; verglichen wird die Unterseite."""
PITCH_DIGITS = 2
ROTATIONS: dict[str, tuple[int, ...]] = {
    "hip": (0,),
    "mansard": (0,),
    "gable": (0, 90),
    "half_hip": (0, 90),
    "mansard_gable": (0, 90),
    "mono_pitch": (0, 90, 180, 270),
}
"""Drehungen, die je Form verschiedene Dächer ergeben (bei Sattelformen gleicht 180 der 0)."""


def _r(value: float) -> float:
    return round(value, 4) + 0.0


def _dot(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _inward(a: Point2, b: Point2) -> Point2:
    """Normale nach innen einer Kante der Kontur gegen den Uhrzeigersinn."""
    length = math.dist(a, b)
    return (-(b[1] - a[1]) / length, (b[0] - a[0]) / length)


def _at(a: Point2, b: Point2, t: float) -> Point2:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _union(polygons: Iterable[BaseGeometry]) -> BaseGeometry:
    """Vereinigung mit geschlossenen Fugen bis 1 mm."""
    grown = [p.buffer(TOL / 2, join_style="mitre") for p in polygons]
    return unary_union(grown).buffer(-TOL / 2, join_style="mitre")


@dataclass(frozen=True)
class Plane:
    """Ebene durch `origin` mit Einheitsnormale `normal` (z ≠ 0)."""

    normal: Point3
    origin: Point3

    def height(self, x: float, y: float) -> float:
        nx, ny, nz = self.normal
        ox, oy, oz = self.origin
        return oz - (nx * (x - ox) + ny * (y - oy)) / nz

    @property
    def slope(self) -> float:
        """Tangens der Neigung."""
        return math.hypot(self.normal[0], self.normal[1]) / abs(self.normal[2])

    @property
    def uphill(self) -> Point2:
        """Richtung im Grundriss, in der die Ebene steigt; bei waagerechter Ebene (0, 0)."""
        nx, ny, nz = self.normal
        length = math.hypot(nx, ny)
        if length < 1e-12:
            return (0.0, 0.0)
        sign = -1.0 if nz > 0 else 1.0
        return (sign * nx / length, sign * ny / length)


def _plane(points: Sequence[Point3]) -> Plane | None:
    """Ebene nach Newell, Normale nach unten; `None` für entartete oder senkrechte Polygone."""
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12 or abs(nz) / length < STEEP:
        return None
    sign = -1.0 if nz > 0 else 1.0
    k = len(points)
    origin = (sum(p[0] for p in points) / k, sum(p[1] for p in points) / k, sum(p[2] for p in points) / k)
    return Plane((sign * nx / length, sign * ny / length, sign * nz / length), origin)


@dataclass(frozen=True)
class Face:
    """Dreieck der Unterseite."""

    points: tuple[Point3, Point3, Point3]
    plane: Plane

    def inside(self, x: float, y: float) -> float:
        """Kleinste baryzentrische Koordinate im Grundriss: ab 0 liegt der Punkt im Dreieck."""
        (ax, ay, _), (bx, by, _), (cx, cy, _) = self.points
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            return -math.inf
        u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / det
        v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / det
        return min(u, v, 1 - u - v)

    @property
    def outline(self) -> Polygon:
        return Polygon([(p[0], p[1]) for p in self.points])


def underside(roof: RawRoof, origin: Point2, ground_z: float) -> list[Face]:
    """Nach unten zeigende, nicht senkrechte Dreiecke in Koordinaten des Templates."""
    faces = []
    for a, b, c in roof.triangles:
        p, q, r = (
            (v[0] - origin[0], v[1] - origin[1], v[2] - ground_z)
            for v in (roof.vertices[a], roof.vertices[b], roof.vertices[c])
        )
        ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        if length < 1e-9 or n[2] / length > -STEEP:
            continue
        faces.append(Face((p, q, r), Plane((n[0] / length, n[1] / length, n[2] / length), p)))
    return faces


class Surface:
    """Unterseite als Höhenfeld: Dreiecke, zu Ebenen zusammengefasst."""

    def __init__(self, faces: list[Face]) -> None:
        self.faces = faces
        self.groups = self._group()
        self.footprint = _union(f.outline for f in faces)

    def _group(self) -> list[int]:
        """Je Dreieck die Nummer seiner Ebene (Normale bis 0,05°, Abstand bis 1 mm)."""
        parent = list(range(len(self.faces)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        same = math.cos(math.radians(0.05))
        for i, f in enumerate(self.faces):
            for j in range(i + 1, len(self.faces)):
                g = self.faces[j]
                if sum(a * b for a, b in zip(f.plane.normal, g.plane.normal, strict=True)) < same:
                    continue
                if all(abs(f.plane.height(p[0], p[1]) - p[2]) <= TOL for p in g.points):
                    parent[find(j)] = find(i)
        roots: dict[int, int] = {}
        return [roots.setdefault(find(i), len(roots)) for i in range(len(self.faces))]

    def planes(self) -> list[Plane]:
        """Je Ebene die flächengewichtete Normale durch den Schwerpunkt ihrer Dreiecke."""
        result = []
        for k in range(max(self.groups, default=-1) + 1):
            members = [f for f, g in zip(self.faces, self.groups, strict=True) if g == k]
            weights = [f.outline.area for f in members]
            total = sum(weights) or 1.0
            normal = [
                sum(w * f.plane.normal[i] for f, w in zip(members, weights, strict=True)) for i in range(3)
            ]
            length = math.sqrt(sum(c * c for c in normal))
            centre = [
                sum(w * sum(p[i] for p in f.points) / 3 for f, w in zip(members, weights, strict=True))
                / total
                for i in range(3)
            ]
            result.append(
                Plane(
                    (normal[0] / length, normal[1] / length, normal[2] / length),
                    (centre[0], centre[1], centre[2]),
                )
            )
        return result

    def face_at(self, x: float, y: float) -> int | None:
        best = max(range(len(self.faces)), key=lambda i: self.faces[i].inside(x, y), default=None)
        return best if best is not None and self.faces[best].inside(x, y) >= -1e-9 else None

    def height(self, x: float, y: float, reach: float = 0.0) -> float | None:
        """Höhe unter dem Punkt; außerhalb bis `reach` die Ebene des nächsten Dreiecks."""
        found = self.face_at(x, y)
        if found is not None:
            return self.faces[found].plane.height(x, y)
        point = Point(x, y)
        nearest = min(self.faces, key=lambda f: f.outline.distance(point))
        return nearest.plane.height(x, y) if nearest.outline.distance(point) <= reach else None


@dataclass(frozen=True)
class Recognized:
    placement: dict[str, Any]
    """`HouseRoofPlacement` als Dokument."""


@dataclass(frozen=True)
class NotRecognized:
    reason: str
    params: dict[str, Any]
    """Grund und Kennwerte (Text oder Zahl) für den Befund `roof_form_not_recognized`."""


def _first_exit(geometry: BaseGeometry, start: Point2, direction: Point2) -> float | None:
    """Abstand vom Punkt bis zum ersten Rand der Fläche in Richtung `direction` (ohne den Punkt selbst)."""
    end = (start[0] + direction[0] * REACH, start[1] + direction[1] * REACH)
    hits = LineString([start, end]).intersection(geometry.boundary)
    distances: list[float] = []
    for part in getattr(hits, "geoms", [hits]):
        if isinstance(part, Point) and not part.is_empty:
            distances.append(math.dist(start, (part.x, part.y)))
        elif isinstance(part, LineString):
            distances += [math.dist(start, xy) for xy in part.coords]
    found = [d for d in distances if d > 1e-6]
    return min(found) if found else None


def _spread(values: Sequence[float]) -> float:
    return max(values) - min(values) if values else 0.0


class Recognizer:
    def __init__(
        self, faces: list[Face], ring: list[Point2], shell: BaseGeometry, build: RoofBuilder
    ) -> None:
        self.surface = Surface(faces)
        self.ring = ring
        self.edges = [(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]
        self.shell = shell
        self.build = build

    def slopes(self) -> str:
        degrees = sorted({round(math.degrees(math.atan(p.slope)), 1) for p in self.surface.planes()})
        return ", ".join(f"{d:g}°" for d in degrees)

    def fail(self, reason: str, **params: str | float) -> NotRecognized:
        return NotRecognized(reason, {"reason": reason, "slopes": self.slopes(), **params})

    def run(self) -> Recognized | NotRecognized:
        surface = self.surface
        if not surface.faces or not isinstance(surface.footprint, Polygon):
            return self.fail("underside_missing")
        planes = surface.planes()

        # Kantenarten, Auflager und Neigung aus der Unterseite auf der Kontur
        kinds: list[str] = []
        heights: list[float] = []
        eave_planes: set[int] = set()
        middles: list[int] = []  # je Kante die Ebene über ihrer Mitte
        for a, b in self.edges:
            m = _inward(a, b)
            found: list[tuple[int, float]] = []
            for t in SAMPLES:
                p = _at(a, b, t)
                face = surface.face_at(p[0] + m[0] * NUDGE, p[1] + m[1] * NUDGE)
                if face is None:
                    return self.fail("contour_not_covered")
                found.append((surface.groups[face], surface.faces[face].plane.height(*p)))
            middles.append(found[SAMPLES.index(0.5)][0])
            rising = all(planes[g].slope > FLAT and _dot(planes[g].uphill, m) > ALIGNED for g, _ in found)
            zs = [z for _, z in found]
            if rising and _spread(zs) <= TOL:
                kinds.append("eave")
                heights.append(fmean(zs))
                eave_planes |= {g for g, _ in found}
            else:
                kinds.append("gable")
        if "eave" not in kinds:
            return self.fail("no_eave")
        if _spread(heights) > TOL:
            return self.fail("eave_heights_differ", spread=round(_spread(heights), 4))
        bearing = _r(median(heights))
        slopes = [planes[g].slope for g in eave_planes]
        pitches = [math.degrees(math.atan(s)) for s in slopes]
        if _spread(pitches) > 0.01:
            return self.fail("pitches_differ")
        slope = fmean(slopes)
        pitch = math.degrees(math.atan(slope))

        # Überstände: Dachkante und Außenseite der Wand von der Mitte jeder Kante aus
        reach: list[float] = []
        walls: list[float] = []
        for a, b in self.edges:
            m = _inward(a, b)
            middle = _at(a, b, 0.5)
            edge = _first_exit(surface.footprint, middle, (-m[0], -m[1]))
            wall = _first_exit(self.shell, middle, (-m[0], -m[1]))
            if edge is None or wall is None:
                return self.fail("contour_not_covered")
            reach.append(edge)
            walls.append(wall)
        eave_reach = [d for d, k in zip(reach, kinds, strict=True) if k == "eave"]
        verge_reach = [d for d, k in zip(reach, kinds, strict=True) if k == "gable"]
        if _spread(eave_reach) > TOL or _spread(verge_reach) > TOL:
            return self.fail("overhangs_differ")
        thickness = _r(median(walls))
        eave = _r(median(eave_reach) - thickness)
        verge = _r(median(verge_reach) - thickness) if verge_reach else eave
        if min(eave, verge) < -TOL:
            return self.fail("overhang_negative")
        eave, verge = max(eave, 0.0), max(verge, 0.0)

        # Flächen ohne eigene Traufe: Krüppelwalm über der Mitte eines Giebels, oberer Abschnitt einer
        # Mansarde dort, wo er an die Traufebene anschließt (nicht jede Ebene, die verlängert hinüberreicht)
        hips: Counter[tuple[float, float]] = Counter()
        mansards: Counter[tuple[float, float]] = Counter()
        # Gerundete obere Neigung → gemessene Steigung, für die Toleranz
        measured: dict[float, float] = {}

        def upper(k: int) -> float | None:
            plane = planes[k]
            if k in eave_planes or plane.slope <= FLAT:
                return None
            degrees = round(math.degrees(math.atan(plane.slope)), PITCH_DIGITS)
            measured.setdefault(degrees, plane.slope)
            return degrees

        for (a, b), kind, middle_plane in zip(self.edges, kinds, middles, strict=True):
            m = _inward(a, b)
            middle = _at(a, b, 0.5)
            candidates = [middle_plane] if kind == "gable" else range(len(planes))
            for k in candidates:
                plane = planes[k]
                if _dot(plane.uphill, m) <= ALIGNED or (degrees := upper(k)) is None:
                    continue
                foot = plane.height(*middle) - bearing
                if kind == "gable":
                    if foot > TOL:
                        hips[(degrees, _r(foot))] += 1
                    continue
                if plane.slope >= slope - 1e-9:
                    continue
                run = foot / (slope - plane.slope)
                beyond = surface.face_at(middle[0] + m[0] * (run + NUDGE), middle[1] + m[1] * (run + NUDGE))
                if run > TOL and beyond is not None and surface.groups[beyond] == k:
                    mansards[(degrees, _r(run * slope))] += 1

        gables = "gable" in kinds
        designs: list[tuple[str, float | None, float | None]] = []
        if gables:
            designs += [("half_hip", u, h) for (u, h), _ in hips.most_common(3)]
            designs += [("mansard_gable", u, h) for (u, h), _ in mansards.most_common(3)]
            designs.append(("mono_pitch" if len(planes) == 1 else "gable", None, None))
        else:
            designs += [("mansard", u, h) for (u, h), _ in mansards.most_common(3)]
            designs.append(("hip", None, None))

        # Vergleich mit dem Dach des Kerns; die Rundung der Neigung geht in die Toleranz ein
        rounded = round(pitch, PITCH_DIGITS)
        minx, miny, maxx, maxy = surface.footprint.bounds
        diagonal = math.hypot(maxx - minx, maxy - miny)

        def rounding(deg: float, measured_slope: float) -> float:
            return abs(math.tan(math.radians(deg)) - measured_slope) * diagonal

        refusals: list[str] = []
        best: float | None = None
        for form, upper_pitch, break_height in designs:
            tolerance = TOL + max(
                rounding(rounded, slope),
                rounding(upper_pitch, measured[upper_pitch]) if upper_pitch is not None else 0.0,
            )
            for rotation in ROTATIONS[form]:
                design = {
                    "form": form,
                    "pitch_deg": rounded,
                    "upper_pitch_deg": upper_pitch,
                    "break_height": break_height,
                    "rotation": rotation,
                }
                try:
                    request = HouseRoofRequest.model_validate(
                        {
                            "contour": [{"x": x, "y": y} for x, y in self.ring],
                            "wall_thickness": thickness,
                            "bearing_height": bearing,
                            "eave_overhang": eave,
                            "verge_overhang": verge,
                            "design": design,
                            "thickness": THICKNESS,
                        }
                    )
                except ValidationError:
                    continue
                built = self.build(request)
                if isinstance(built, str):
                    refusals.append(built)
                    continue
                if built.edge_kinds != kinds:
                    continue
                deviation = self.deviation(built)
                if deviation <= tolerance:
                    return Recognized(
                        {
                            "bearing_height": bearing,
                            "parapet_height": 0.0,
                            "eave_overhang": eave,
                            "verge_overhang": verge,
                            "design": design,
                        }
                    )
                best = deviation if best is None else min(best, deviation)
        if best is not None:
            return self.fail("shape_differs", **({"distance": round(best, 4)} if math.isfinite(best) else {}))
        if refusals:
            return self.fail("not_constructible", refusal=refusals[0])
        return self.fail("edges_differ")

    def deviation(self, built: HouseRoofGeometry) -> float:
        """Größte Abweichung der Unterseiten: Umriss im Grundriss und Höhen, m."""
        kernel: list[tuple[Polygon, Plane]] = []
        for face in built.faces:
            points = [(p.x, p.y, p.z) for p in face.polygon]
            plane = _plane(points)
            if plane is not None:
                kernel.append((Polygon([(x, y) for x, y, _ in points]), plane))
        if not kernel:
            return math.inf
        outline = _union(p for p, _ in kernel)
        worst: float = outline.boundary.hausdorff_distance(self.surface.footprint.boundary)

        def kernel_height(x: float, y: float) -> float | None:
            point = Point(x, y)
            polygon, plane = min(kernel, key=lambda k: k[0].distance(point))
            return plane.height(x, y) if polygon.distance(point) <= 2 * TOL else None

        samples: list[Point2] = []
        for triangle in self.surface.faces:
            cx = sum(p[0] for p in triangle.points) / 3
            cy = sum(p[1] for p in triangle.points) / 3
            samples.append((cx, cy))
            samples += [(p[0] + (cx - p[0]) * 0.02, p[1] + (cy - p[1]) * 0.02) for p in triangle.points]
        for polygon, _ in kernel:
            inner = polygon.buffer(-0.002)
            samples.append((polygon.representative_point().x, polygon.representative_point().y))
            if isinstance(inner, Polygon) and not inner.is_empty:
                samples += [(x, y) for x, y in inner.exterior.coords]
        for x, y in samples:
            ifc = self.surface.height(x, y, reach=2 * TOL)
            core = kernel_height(x, y)
            if ifc is None or core is None:
                # Außerhalb eines der Umrisse: Abstand im Grundriss
                point = Point(x, y)
                worst = max(worst, outline.distance(point), self.surface.footprint.distance(point))
            else:
                worst = max(worst, abs(ifc - core))
        return worst


def recognize(
    faces: list[Face], ring: list[Point2], shell: BaseGeometry, build: RoofBuilder
) -> Recognized | NotRecognized:
    """Form und Parameter des Dachs; `ring` ist die Bezugskontur, `shell` die Außenwände des obersten
    Geschosses, beides in Koordinaten des Templates."""
    return Recognizer(faces, ring, shell, build).run()
