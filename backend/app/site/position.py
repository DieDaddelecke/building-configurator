"""Lage eines Grundstücks ohne Kataster setzen (AN5, docs/PLAN_AN5_AUSGABE.md 3.2; aus `service.py`
gelöst, REFACTORING_PLAN S20)."""

import math
import uuid
from typing import cast

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Polygon
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.problems import Problem
from app.site.domain import position
from app.site.models import L93, SiteEdge, SiteRisk, Terrain
from app.site.schemas import (
    PositionIn,
    SiteOut,
)
from app.site.service import (
    SKETCH_ORIGINS,
    load_site,
)
from app.site.store import (
    db_now,
    enqueue_enrichment,
    hash_outline,
    l93_and_convergence,
    locked_site,
    wgs84_of,
)


def position_site(db: Session, project_id: uuid.UUID, body: PositionIn, actor: str) -> SiteOut:
    """Grundstück ohne Kataster verorten oder die Lage korrigieren: starr drehen und verschieben, Maße,
    Fläche und Einordnung der Kanten bleiben. Danach Gelände und Risiken abfragen (3.2, 3.3)."""
    site = locked_site(db, project_id, body.expected_revision)
    if site.origin not in SKETCH_ORIGINS:
        raise Problem(409, "site_position_parcel")
    polygon = cast(Polygon, to_shape(site.geometry))
    centre = position.pivot(polygon)
    map_rotation = 0.0
    if site.georeferenced:
        _, gamma_old = l93_and_convergence(db, *wgs84_of(db, centre))
        map_rotation = -gamma_old
    target, gamma = l93_and_convergence(db, body.lon, body.lat)
    theta = position.rotation(map_rotation, body.rotation_deg, gamma)

    moved = cast(Polygon, position.turn(polygon, centre, target, theta))
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    for edge in edges:
        edge.geometry = from_shape(position.turn(to_shape(edge.geometry), centre, target, theta), srid=L93)
        edge.normal_azimuth_deg = cast(float, position.turn_azimuth(edge.normal_azimuth_deg, theta))
    site.street_azimuth_deg = position.turn_azimuth(site.street_azimuth_deg, theta)
    site.garden_azimuth_deg = position.turn_azimuth(site.garden_azimuth_deg, theta)

    previous = dict((site.source_info or {}).get("position") or {})
    was_georeferenced = site.georeferenced
    turned = float(previous.get("rotation_deg") or 0.0) + body.rotation_deg
    min_x, min_y, _, _ = moved.bounds
    site.geometry = from_shape(moved, srid=L93)
    site.local_origin_e, site.local_origin_n = float(math.floor(min_x)), float(math.floor(min_y))
    site.georeferenced = True
    site.outline_hash = hash_outline(moved)
    site.revision += 1
    site.source_info = {
        **(site.source_info or {}),
        "position": {
            "method": "map",
            "lon": round(body.lon, 7),
            "lat": round(body.lat, 7),
            "rotation_deg": round(position.signed(turned), 2),
            "convergence_deg": round(gamma, 4),
            "at": db_now(db).isoformat(),
            "by": actor,
        },
    }
    for model in (Terrain, SiteRisk):
        db.execute(delete(model).where(model.site_id == site.id))
    site.terrain_status = site.risks_status = "pending"
    site.updated_by = actor
    site.updated_at = db_now(db)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="site.position",
        entity_type="site",
        entity_id=str(site.id),
        before={"georeferenced": was_georeferenced, "position": previous or None},
        after={"position": site.source_info["position"]},
    )
    db.flush()
    enqueue_enrichment(db, site, project_id, actor)
    db.commit()
    return load_site(db, project_id)
