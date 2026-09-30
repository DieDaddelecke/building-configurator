"""Einzugsgebiet, Parzellen auf der Karte und Suche nach Adresse oder Parzelle (Modul G1, Plan 3.3;
aus `service.py` gelöst, REFACTORING_PLAN S20)."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.problems import Problem
from app.site.domain import tolerances as tol
from app.site.schemas import (
    CommuneOut,
    LookupIn,
    LookupOut,
    ParcelSummary,
)

MAX_BBOX_DEG = (0.03, 0.02)
"""Größte Kartenausdehnung für Parzellen (Längen- und Breitengrad), rund 2,3 × 2,2 km."""


MAX_BBOX_FEATURES = 4000


def service_area(db: Session) -> list[CommuneOut]:
    rows = db.execute(
        text(
            "SELECT insee, name, release, imported_at, ST_XMin(b) AS x0, ST_YMin(b) AS y0, "
            "ST_XMax(b) AS x1, ST_YMax(b) AS y1 "
            "FROM (SELECT *, Box2D(ST_Transform(geometry, 4326)) AS b FROM ref_commune) AS c ORDER BY name"
        )
    ).all()
    return [
        CommuneOut(
            insee=r.insee,
            name=r.name,
            bbox=(round(r.x0, 6), round(r.y0, 6), round(r.x1, 6), round(r.y1, 6)),
            release=r.release,
            imported_at=r.imported_at,
        )
        for r in rows
    ]


def communes_in_service_area(db: Session, codes: set[str]) -> set[str]:
    if not codes:
        return set()
    rows = db.execute(text("SELECT insee FROM ref_commune WHERE insee = ANY(:codes)"), {"codes": list(codes)})
    return {r.insee for r in rows}


def parcels_in_bbox(db: Session, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Parzellen als GeoJSON (WGS84) für die Karte. Dieselben Daten, die ausgewählt werden (Plan 3.3)."""
    x0, y0, x1, y1 = bbox
    if not (x0 < x1 and y0 < y1) or x1 - x0 > MAX_BBOX_DEG[0] or y1 - y0 > MAX_BBOX_DEG[1]:
        raise Problem(422, "bbox_too_large")
    rows = db.execute(
        text(
            """
            WITH env AS (SELECT ST_Transform(ST_MakeEnvelope(:x0, :y0, :x1, :y1, 4326), 2154) AS g)
            SELECT p.idu, p.section, p.number, p.commune_insee, p.area_official_m2,
                   ST_AsGeoJSON(ST_Transform(p.geometry, 4326), 7) AS geojson
            FROM ref_parcel p, env
            WHERE p.geometry && env.g AND ST_Intersects(p.geometry, env.g)
            ORDER BY p.idu
            LIMIT :limit
            """
        ),
        {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "limit": MAX_BBOX_FEATURES + 1},
    ).all()
    truncated = len(rows) > MAX_BBOX_FEATURES
    return {
        "type": "FeatureCollection",
        "truncated": truncated,
        "features": [
            {
                "type": "Feature",
                "id": r.idu,
                "geometry": json.loads(r.geojson),
                "properties": {
                    "idu": r.idu,
                    "section": r.section,
                    "number": r.number,
                    "commune_insee": r.commune_insee,
                    "area_official_m2": r.area_official_m2,
                },
            }
            for r in rows[:MAX_BBOX_FEATURES]
        ],
    }


def lookup(db: Session, body: LookupIn) -> LookupOut:
    """Parzelle am Punkt, sonst alle im Umkreis von 20 m (Adresspunkte liegen oft auf der Straße, 5.1.1)."""
    select_cols = (
        "p.idu, p.commune_insee, p.prefix, p.section, p.number, p.area_official_m2, "
        "ST_AsGeoJSON(ST_Transform(p.geometry, 4326), 7) AS geojson"
    )
    if body.lon is not None and body.lat is not None:
        point = "ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 2154)"
        params: dict[str, Any] = {"lon": body.lon, "lat": body.lat, "radius": tol.LOOKUP_RADIUS_M}
        in_area = bool(
            db.execute(
                text(f"SELECT EXISTS (SELECT 1 FROM ref_commune WHERE ST_Intersects(geometry, {point}))"),  # noqa: S608
                params,
            ).scalar()
        )
        rows = db.execute(
            text(
                f"""
                SELECT {select_cols}, ST_Distance(p.geometry, pt.g) AS distance
                FROM ref_parcel p, (SELECT {point} AS g) AS pt
                WHERE ST_DWithin(p.geometry, pt.g, :radius)
                ORDER BY distance, p.idu LIMIT 10
                """  # noqa: S608  feste Ausdrücke, Werte gebunden
            ),
            params,
        ).all()
    else:
        assert body.commune_insee and body.section and body.number
        params = {
            "commune": body.commune_insee,
            "section": body.section.upper().rjust(2, "0"),
            "number": body.number.rjust(4, "0"),
        }
        in_area = bool(
            db.execute(
                text("SELECT EXISTS (SELECT 1 FROM ref_commune WHERE insee = :commune)"), params
            ).scalar()
        )
        rows = db.execute(
            text(
                f"SELECT {select_cols}, 0.0 AS distance FROM ref_parcel p "  # noqa: S608
                "WHERE p.commune_insee = :commune AND p.section = :section AND p.number = :number "
                "ORDER BY p.prefix LIMIT 10"
            ),
            params,
        ).all()
    candidates = [
        ParcelSummary(
            idu=r.idu,
            commune_insee=r.commune_insee,
            prefix=r.prefix,
            section=r.section,
            number=r.number,
            area_official_m2=r.area_official_m2,
            distance_m=round(float(r.distance), 2),
            geometry_geojson=json.loads(r.geojson),
        )
        for r in rows
    ]
    contained = candidates[0].idu if candidates and candidates[0].distance_m == 0 else None
    return LookupOut(in_service_area=in_area, contained_idu=contained, candidates=candidates)
