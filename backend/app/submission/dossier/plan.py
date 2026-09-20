"""Geometrie des Lageplans aus dem Snapshot einer Fassung (V 3.7), für PDF und DXF gleich.

Alle Koordinaten sind lokale Meter (Ost, Nord) relativ zu `site.local_origin`; Lambert-93 ist lokal plus
Ursprung (reine Verschiebung, `envelope/domain/local.py`). Für Weg E hat der Ursprung keine geografische
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
class Plan:
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

    def bounds(self) -> tuple[float, float, float, float]:
        """Ausschnitt: Grundstück und Baukörper, nicht die Nachbarschaft."""
        points = [p for ring in [*self.parcel, *self.own_rings()] for p in ring]
        if not points:
            return (0.0, 0.0, 10.0, 10.0)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return (min(xs) - MARGIN_M, min(ys) - MARGIN_M, max(xs) + MARGIN_M, max(ys) + MARGIN_M)

    def own_rings(self) -> list[Ring]:
        return [r for r in (self.facade, self.projection, self.terrace, self.carport, *self.driveways) if r]


def _ring(raw: Any) -> Ring | None:
    if not raw or len(raw) < 3:
        return None
    return [(float(p[0]), float(p[1])) for p in raw]


def _rings(raw: Any) -> list[Ring]:
    return [ring for ring in (_ring(r) for r in raw or []) if ring]


def from_snapshot(snapshot: dict[str, Any]) -> Plan:
    site = snapshot.get("site") or {}
    envelope = snapshot.get("envelope") or {}
    configuration = snapshot.get("configuration") or {}
    evaluation = configuration.get("evaluation") or {}
    outbuildings = configuration.get("outbuildings") or {}
    contours = envelope.get("contours") or {}
    context = site.get("context") or {}
    origin = site.get("local_origin") or {"e": 0.0, "n": 0.0}
    placement = configuration.get("placement")
    orientation = configuration.get("orientation")
    return Plan(
        origin=(float(origin["e"]), float(origin["n"])),
        georeferenced=site.get("origin") == "parcel",
        parcel=_rings(site.get("outline_local")),
        edges=[
            Edge(
                seq=int(e["seq"]),
                kind=str(e["kind"]),
                coords=[(float(x), float(y)) for x, y in e["coords_local"]],
            )
            for e in site.get("edges") or []
            if e.get("coords_local")
        ],
        neighbour_parcels=_rings(context.get("parcels")),
        neighbour_buildings=_rings(context.get("buildings")),
        lenient=_rings((contours.get("lenient") or {}).get("rings_local")),
        strict=_rings((contours.get("strict") or {}).get("rings_local")),
        facade=_ring(evaluation.get("facade_local")),
        projection=_ring(evaluation.get("projection_local")),
        terrace=_ring((outbuildings.get("terrace") or {}).get("polygon_local")),
        carport=_ring((outbuildings.get("carport") or {}).get("polygon_local")),
        driveways=_rings([d.get("polygon_local") for d in outbuildings.get("driveways") or []]),
        house_origin=(
            (float(placement["origin"]["e"]), float(placement["origin"]["n"])) if placement else None
        ),
        rotation_deg=float(placement["rotation_deg"]) if placement else None,
        convergence_deg=float(orientation["convergence_deg"]) if orientation else None,
    )


def choose_scale(plan: Plan) -> int:
    """Kleinster Maßstab aus `SCALES`, bei dem der Ausschnitt auf `PLAN_MM` passt."""
    min_x, min_y, max_x, max_y = plan.bounds()
    for scale in SCALES:
        if (max_x - min_x) * 1000 / scale <= PLAN_MM[0] and (max_y - min_y) * 1000 / scale <= PLAN_MM[1]:
            return scale
    return SCALES[-1]
