"""Lageplan einer Fassung: Snapshot (V 3.7) → `Plan` aus `app/plan/geometry.py`.

Die Geometrie selbst und der DXF-Schreiber liegen seit dem Produktschnitt (AN0) im Kern, weil beide
Produkte sie brauchen. Hier bleibt nur das Lesen des Snapshots einer Fassung – die einzige Stelle mit
Wissen über dessen Aufbau.
"""

from typing import Any

from app.plan.geometry import Edge, Plan, ring, rings


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
        parcel=rings(site.get("outline_local")),
        edges=[
            Edge(
                seq=int(e["seq"]),
                kind=str(e["kind"]),
                coords=[(float(x), float(y)) for x, y in e["coords_local"]],
            )
            for e in site.get("edges") or []
            if e.get("coords_local")
        ],
        neighbour_parcels=rings(context.get("parcels")),
        neighbour_buildings=rings(context.get("buildings")),
        lenient=rings((contours.get("lenient") or {}).get("rings_local")),
        strict=rings((contours.get("strict") or {}).get("rings_local")),
        facade=ring(evaluation.get("facade_local")),
        projection=ring(evaluation.get("projection_local")),
        terrace=ring((outbuildings.get("terrace") or {}).get("polygon_local")),
        carport=ring((outbuildings.get("carport") or {}).get("polygon_local")),
        driveways=rings([d.get("polygon_local") for d in outbuildings.get("driveways") or []]),
        house_origin=(
            (float(placement["origin"]["e"]), float(placement["origin"]["n"])) if placement else None
        ),
        rotation_deg=float(placement["rotation_deg"]) if placement else None,
        convergence_deg=float(orientation["convergence_deg"]) if orientation else None,
    )
