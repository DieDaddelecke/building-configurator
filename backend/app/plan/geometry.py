"""Geometrie eines Lageplans, für PDF und DXF gleich (V 3.7, seit AN0 im Kern).

Alle Koordinaten sind lokale Meter (Ost, Nord) relativ zu `site.local_origin`; Lambert-93 ist lokal plus
Ursprung (reine Verschiebung, `site/domain/local.py`). Für Weg E hat der Ursprung keine geografische
Bedeutung (G27): `georeferenced` ist dann falsch, und es entsteht keine Lambert-93-Datei.
"""

from dataclasses import dataclass, field
from typing import Any

Point = tuple[float, float]
Ring = list[Point]

SCALES = (200, 250, 500, 1000, 2000)
"""Maßstäbe 1:n, der kleinste passende wird genommen (Spez. 5.10.5 nennt 1:500)."""
PLAN_MM = (170.0, 150.0)
MARGIN_M = 3.0


@dataclass(frozen=True)
class Edge:
    seq: int
    kind: str
    coords: Ring


@dataclass(frozen=True)
class Area:
    """Fläche mit Löchern; für Körper, die Ringe allein nicht beschreiben (AN5)."""

    exterior: Ring
    holes: list[Ring] = field(default_factory=list)


@dataclass(frozen=True)
class Stage:
    """Stufe des Gabarits in einer Auslegung (AN5 3.4): Kontur, Unter- und Oberkante über ±0,00."""

    reading: str
    """`lenient` oder `strict`."""
    from_m: float
    to_m: float
    roof: bool
    areas: list[Area]


@dataclass(frozen=True)
class Constraint:
    """Vorgabe des Planwerks: `no_build` oder `restricts`; Flächen und Linien."""

    effect: str
    label: str
    rings: list[Ring] = field(default_factory=list)
    lines: list[Ring] = field(default_factory=list)


@dataclass(frozen=True)
class Cut:
    """Schnittlinie A–A oder B–B."""

    key: str
    start: Point
    end: Point


@dataclass(frozen=True)
class Plan:
    """Lageplan. V füllt die Felder bis `convergence_deg`; die Analyse (AN5) die übrigen."""

    origin: Point
    georeferenced: bool
    parcel: list[Ring]
    edges: list[Edge]
    neighbour_parcels: list[Ring] = field(default_factory=list)
    neighbour_buildings: list[Ring] = field(default_factory=list)
    lenient: list[Ring] = field(default_factory=list)
    strict: list[Ring] = field(default_factory=list)
    facade: Ring | None = None
    projection: Ring | None = None
    terrace: Ring | None = None
    carport: Ring | None = None
    driveways: list[Ring] = field(default_factory=list)
    house_origin: Point | None = None
    rotation_deg: float | None = None
    convergence_deg: float | None = None
    bands: list[Ring] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    cuts: list[Cut] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)
    reference_ngf: float | None = None
    """±0,00 in m NGF; die Lambert-93-Datei trägt Z dann in NGF (E-AN5-2)."""

    def bounds(self) -> tuple[float, float, float, float]:
        """Ausschnitt: Grundstück und Baukörper, nicht die Nachbarschaft."""
        points = [p for ring in [*self.parcel, *self.own_rings()] for p in ring]
        if not points:
            return (0.0, 0.0, 10.0, 10.0)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return (min(xs) - MARGIN_M, min(ys) - MARGIN_M, max(xs) + MARGIN_M, max(ys) + MARGIN_M)

    def own_rings(self) -> list[Ring]:
        return [r for r in (self.facade, self.projection, self.terrace, self.carport, *self.driveways) if r]


def ring(raw: Any) -> Ring | None:
    """Rohe Koordinatenliste in einen Ring; zu kurze oder leere Listen ergeben nichts."""
    if not raw or len(raw) < 3:
        return None
    return [(float(p[0]), float(p[1])) for p in raw]


def rings(raw: Any) -> list[Ring]:
    return [r for r in (ring(item) for item in raw or []) if r]


def choose_scale(plan: Plan) -> int:
    """Kleinster Maßstab aus `SCALES`, bei dem der Ausschnitt auf `PLAN_MM` passt."""
    min_x, min_y, max_x, max_y = plan.bounds()
    for scale in SCALES:
        if (max_x - min_x) * 1000 / scale <= PLAN_MM[0] and (max_y - min_y) * 1000 / scale <= PLAN_MM[1]:
            return scale
    return SCALES[-1]
