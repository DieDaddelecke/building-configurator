"""Gemeinsame Hilfen der Eingangswege eines Grundstücks: Umriss speichern, Kanten anlegen, Einordnung
übernehmen, Anreicherung einplanen, Grundstück sperren, Punkte zwischen Lambert-93 und WGS84 umrechnen
(Modul G1; aus `service.py` gelöst, REFACTORING_PLAN S20). Kennt `service.py` nicht."""

import hashlib
import uuid
from typing import Any

import shapely
from geoalchemy2.shape import from_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.platform.jobs import enqueue
from app.platform.problems import Problem
from app.site.domain import position
from app.site.domain import tolerances as tol
from app.site.domain.edges import (
    Classification,
)
from app.site.models import L93, Site, SiteEdge, SiteParcel, SiteRisk, Terrain


def hash_outline(geometry: BaseGeometry) -> str:
    return hashlib.sha256(shapely.to_wkb(geometry, hex=False)).hexdigest()


def renewed_site(db: Session, site: Site | None, project_id: uuid.UUID, actor: str) -> Site:
    """Neues Grundstück anlegen oder das vorhandene für einen neuen Umriss leeren (nächste Revision)."""
    if site is None:
        site = Site(project_id=project_id, created_by=actor, revision=1)
        db.add(site)
        return site
    site.revision += 1
    for model in (SiteParcel, SiteEdge, Terrain, SiteRisk):
        db.execute(delete(model).where(model.site_id == site.id))
    return site


def add_edges(db: Session, site: Site, classification: Classification, actor: str) -> None:
    """Kanten mit automatischer Einordnung speichern; für einen neuen Umriss gibt es keine Korrekturen."""
    for edge in classification.edges:
        geometry = edge.geometry
        db.add(
            SiteEdge(
                site_id=site.id,
                seq=geometry.seq,
                ring=geometry.ring,
                geometry=from_shape(shapely.LineString(geometry.coords), srid=L93),
                length_m=round(geometry.length_m, tol.STORAGE_DECIMALS),
                normal_azimuth_deg=round(geometry.normal_azimuth_deg, 2),
                kind=edge.kind,
                kind_auto=edge.kind_auto,
                override_kind=None,
                classification_source="auto",
                confidence=edge.confidence,
                neighbour_share=edge.facts.neighbour_share,
                street_candidate=edge.facts.street_candidate,
                probe_in_parcel=edge.facts.probe_in_parcel,
                road_share=edge.facts.road_share,
                street_name=edge.facts.street_name,
                adjacent=list(edge.facts.adjacent),
                created_by=actor,
            )
        )


def db_now(db: Session) -> Any:
    """Zeitstempel der Datenbank, damit `updated_at` und Transaktionszeit übereinstimmen."""
    return db.execute(text("SELECT now()")).scalar_one()


def apply_classification(site: Site, classification: Classification, warnings: list[str]) -> None:
    site.main_street_seq = classification.main_street_seq
    site.street_azimuth_deg = classification.street_azimuth_deg
    site.garden_azimuth_deg = classification.garden_azimuth_deg
    site.warnings = list(dict.fromkeys(warnings))


def enqueue_enrichment(db: Session, site: Site, project_id: uuid.UUID, actor: str) -> None:
    enqueue(
        db,
        "site_enrich",
        {"site_id": str(site.id), "outline_hash": site.outline_hash},
        idempotency_key=f"site_enrich:{site.id}:{site.revision}",
        project_id=project_id,
        created_by=actor,
    )


def l93_and_convergence(db: Session, lon: float, lat: float) -> tuple[tuple[float, float], float]:
    """Punkt in Lambert-93 und Gitterkonvergenz γ dort: Gitterazimut der Strecke 100 m nach Norden."""
    row = db.execute(
        text(
            "WITH p AS (SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS g), "
            "t AS (SELECT ST_Transform(g, 2154) AS a, "
            "ST_Transform(ST_Project(g::geography, 100, 0)::geometry, 2154) AS b FROM p) "
            "SELECT ST_X(a) AS ax, ST_Y(a) AS ay, ST_X(b) AS bx, ST_Y(b) AS by FROM t"
        ),
        {"lon": lon, "lat": lat},
    ).one()
    start = (float(row.ax), float(row.ay))
    return start, position.signed(position.azimuth(start, (float(row.bx), float(row.by))))


def wgs84_of(db: Session, point: tuple[float, float]) -> tuple[float, float]:
    row = db.execute(
        text(
            "SELECT ST_X(g) AS lon, ST_Y(g) AS lat FROM "
            "(SELECT ST_Transform(ST_SetSRID(ST_MakePoint(:x, :y), 2154), 4326) AS g) AS s"
        ),
        {"x": point[0], "y": point[1]},
    ).one()
    return float(row.lon), float(row.lat)


def locked_site(db: Session, project_id: uuid.UUID, expected_revision: int | None) -> Site:
    site = db.execute(
        select(Site).where(Site.project_id == project_id).with_for_update()
    ).scalar_one_or_none()
    if site is None:
        raise Problem(404, "site_not_found")
    if expected_revision is not None and expected_revision != site.revision:
        raise Problem(409, "revision_conflict", revision=site.revision)
    return site
