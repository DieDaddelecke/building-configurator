"""Import der Kataster-Massendaten je Gemeinde (Plan 3.3 „Massendaten-Import“, 6.6).

Ablauf: Stand ermitteln → herunterladen → Zwischentabelle → Plausibilität → Tausch in einer Transaktion.
Leser sehen bis zum Commit den alten Stand (MVCC). Bestätigte Grundstücke behalten ihre Kopie in `parcel`.
"""

import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import shapely
from shapely.geometry import LineString
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.etalab_cadastre import CadastreSource, Download
from app.integrations.http import ExternalServiceError
from app.integrations.ign_bdtopo import RoadSegment, RoadSource
from app.platform.db import utcnow
from app.platform.logging import get_logger
from app.site.models import RefImport, RefParcel

log = get_logger("cadastre_import")
SOURCE = "etalab_cadastre"
BATCH = 500
MAX_INVALID_RATIO = 0.005


class ImportRejected(Exception):
    """Plausibilitätsprüfung nicht bestanden; der alte Stand bleibt."""


@dataclass
class ImportResult:
    commune: str
    status: Literal["succeeded", "skipped", "failed"]
    release: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


_L93 = "ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326), 2154)"
_FIXED = f"ST_Multi(ST_CollectionExtract(ST_MakeValid({_L93}), 3))"

_INSERT_PARCEL = text(
    f"""
    INSERT INTO ref_parcel_staging
        (import_id, idu, commune_insee, prefix, section, number, area_official_m2, geometry,
         source_updated, valid_source)
    SELECT :import_id, :idu, :commune, :prefix, :section, :number, :area, fixed, :updated,
           ST_IsValid({_L93})
    FROM (SELECT {_FIXED} AS fixed) AS g
    WHERE NOT ST_IsEmpty(fixed)
    ON CONFLICT DO NOTHING
    """  # noqa: S608  feste Ausdrücke, Werte gebunden
)
_INSERT_BUILDING = text(
    f"""
    INSERT INTO ref_building_staging (import_id, commune_insee, kind, geometry)
    SELECT :import_id, :commune, :kind, fixed FROM (SELECT {_FIXED} AS fixed) AS g
    WHERE NOT ST_IsEmpty(fixed)
    """  # noqa: S608
)


def _batches(rows: Iterable[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def _parcel_rows(import_id: uuid.UUID, commune: str, download: Download) -> Iterator[dict[str, Any]]:
    for feature in download.features:
        props = feature.get("properties") or {}
        idu = str(props.get("id", ""))
        if len(idu) != 14 or not idu.startswith(commune) or not feature.get("geometry"):
            continue
        updated = props.get("updated")
        yield {
            "import_id": import_id,
            "idu": idu,
            "commune": commune,
            # Aus der IDU statt aus `section`/`numero`: dort fehlen führende Nullen je nach Stand
            "prefix": idu[5:8],
            "section": idu[8:10],
            "number": idu[10:14],
            "area": props.get("contenance"),
            "updated": date.fromisoformat(updated) if updated else None,
            "geometry": json.dumps(feature["geometry"]),
        }


def _building_rows(import_id: uuid.UUID, commune: str, download: Download) -> Iterator[dict[str, Any]]:
    for feature in download.features:
        if not feature.get("geometry"):
            continue
        props = feature.get("properties") or {}
        yield {
            "import_id": import_id,
            "commune": commune,
            "kind": props.get("type"),
            "geometry": json.dumps(feature["geometry"]),
        }


def _cleanup_stale(session: Session) -> None:
    session.execute(
        text(
            "UPDATE ref_import SET status = 'failed', error = 'abandoned', finished_at = now() "
            "WHERE status = 'running' AND created_at < now() - interval '2 hours'"
        )
    )
    for table in ("ref_parcel_staging", "ref_building_staging"):
        session.execute(
            text(
                f"DELETE FROM {table} WHERE import_id NOT IN "  # noqa: S608  Tabellenname fest
                "(SELECT id FROM ref_import WHERE status = 'running')"
            )
        )
    session.commit()


def import_commune(
    session: Session,
    source: CadastreSource,
    settings: Settings,
    commune: str,
    *,
    force: bool = False,
    roads: RoadSource | None = None,
) -> ImportResult:
    """Importiert Parzellen, Gebäude, Gemeindegrenze und (mit `roads`) Straßenachsen einer Gemeinde.

    Idempotent je Katasterstand. Fehlten beim letzten Import die Straßenachsen (`counts.roads = -1`),
    wird derselbe Stand erneut importiert.
    """
    _cleanup_stale(session)
    release = source.latest_release(commune)
    already = session.execute(
        select(RefImport.counts).where(
            RefImport.source == SOURCE,
            RefImport.commune_insee == commune,
            RefImport.release == release,
            RefImport.status == "succeeded",
        )
    ).first()
    roads_missing = already is not None and roads is not None and int(already.counts.get("roads", -1)) < 0
    if already and not force and not roads_missing:
        return ImportResult(commune, "skipped", release)

    record = RefImport(source=SOURCE, commune_insee=commune, release=release, created_by="system:import")
    session.add(record)
    session.commit()
    import_id = record.id
    try:
        result = _run(session, source, settings, commune, release, import_id, force, roads)
    except (ImportRejected, ExternalServiceError, ValueError) as exc:
        session.rollback()
        _finish_failed(session, import_id, str(exc))
        log.warning("cadastre_import_failed", commune=commune, release=release, error=str(exc))
        return ImportResult(commune, "failed", release, error=str(exc))
    except Exception as exc:
        session.rollback()
        _finish_failed(session, import_id, f"{type(exc).__name__}: {exc}")
        raise
    log.info("cadastre_import_succeeded", commune=commune, release=release, **result.counts)
    return result


def _finish_failed(session: Session, import_id: uuid.UUID, error: str) -> None:
    for table in ("ref_parcel_staging", "ref_building_staging"):
        session.execute(
            text(f"DELETE FROM {table} WHERE import_id = :id"),  # noqa: S608  Tabellenname fest
            {"id": import_id},
        )
    session.execute(
        text("UPDATE ref_import SET status = 'failed', error = :error, finished_at = now() WHERE id = :id"),
        {"id": import_id, "error": error[:2000]},
    )
    session.commit()


def _run(
    session: Session,
    source: CadastreSource,
    settings: Settings,
    commune: str,
    release: str,
    import_id: uuid.UUID,
    force: bool,
    road_source: RoadSource | None,
) -> ImportResult:
    communes = source.fetch(commune, "communes", release)
    boundary = next((f for f in communes.features if (f.get("properties") or {}).get("id") == commune), None)
    if boundary is None:
        raise ImportRejected("commune_boundary_missing")
    parcels = source.fetch(commune, "parcelles", release)
    buildings = source.fetch(commune, "batiments", release)

    roads: list[RoadSegment] | None = None
    if road_source is not None:
        bbox = session.execute(
            text(
                "SELECT ST_XMin(b), ST_YMin(b), ST_XMax(b), ST_YMax(b) "  # noqa: S608  fester Ausdruck
                f"FROM (SELECT Box2D({_L93}) AS b) AS e"
            ),
            {"geometry": json.dumps(boundary["geometry"])},
        ).one()
        try:
            roads = road_source.fetch(commune, (bbox[0], bbox[1], bbox[2], bbox[3]))
        except ExternalServiceError as exc:
            # Parzellen sind nutzbar; ohne Achsen ordnet die Kantenerkennung wie zuvor ein
            log.warning("road_import_failed", commune=commune, error=str(exc))

    for batch in _batches(_parcel_rows(import_id, commune, parcels)):
        session.execute(_INSERT_PARCEL, batch)
    for batch in _batches(_building_rows(import_id, commune, buildings)):
        session.execute(_INSERT_BUILDING, batch)
    session.commit()

    staged = session.execute(
        text(
            "SELECT count(*) AS n, count(*) FILTER (WHERE NOT valid_source) AS repaired "
            "FROM ref_parcel_staging WHERE import_id = :id"
        ),
        {"id": import_id},
    ).one()
    staged_buildings = session.execute(
        text("SELECT count(*) FROM ref_building_staging WHERE import_id = :id"), {"id": import_id}
    ).scalar_one()
    source_count = len(parcels.features)
    dropped = source_count - staged.n
    previous = session.execute(
        select(func.count()).select_from(RefParcel).where(RefParcel.commune_insee == commune)
    ).scalar_one()

    if staged.n == 0:
        raise ImportRejected("no_parcels")
    if dropped > MAX_INVALID_RATIO * source_count:
        raise ImportRejected(f"too_many_unusable_parcels:{dropped}/{source_count}")
    allowed = max(
        settings.cadastre_max_count_change_ratio * previous, settings.cadastre_max_count_change_absolute
    )
    if previous and abs(staged.n - previous) > allowed and not force:
        raise ImportRejected(f"parcel_count_change:{previous}->{staged.n}")

    counts = {
        "parcels": int(staged.n),
        "parcels_previous": int(previous),
        "parcels_repaired": int(staged.repaired),
        "parcels_dropped": int(dropped),
        "buildings": int(staged_buildings),
        "roads": len(roads) if roads is not None else -1,
    }
    params = {"id": import_id, "commune": commune, "release": release}
    session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"cadastre_import:{commune}"))))
    session.execute(text("DELETE FROM ref_parcel WHERE commune_insee = :commune"), params)
    session.execute(
        text(
            "INSERT INTO ref_parcel (idu, commune_insee, prefix, section, number, area_official_m2, "
            "geometry, source_updated, release) "
            "SELECT idu, commune_insee, prefix, section, number, area_official_m2, geometry, source_updated, "
            ":release FROM ref_parcel_staging WHERE import_id = :id"
        ),
        params,
    )
    session.execute(text("DELETE FROM ref_building WHERE commune_insee = :commune"), params)
    session.execute(
        text(
            "INSERT INTO ref_building (commune_insee, kind, geometry) "
            "SELECT commune_insee, kind, geometry FROM ref_building_staging WHERE import_id = :id"
        ),
        params,
    )
    session.execute(
        text(
            f"""
            INSERT INTO ref_commune (insee, name, geometry, release, imported_at)
            VALUES (:commune, :name, ST_Multi(ST_CollectionExtract(ST_MakeValid({_L93}), 3)), :release, now())
            ON CONFLICT (insee) DO UPDATE SET name = EXCLUDED.name, geometry = EXCLUDED.geometry,
                release = EXCLUDED.release, imported_at = EXCLUDED.imported_at
            """  # noqa: S608
        ),
        {
            **params,
            "name": str((boundary.get("properties") or {}).get("nom", commune)),
            "geometry": json.dumps(boundary["geometry"]),
        },
    )
    if roads is not None:
        session.execute(text("DELETE FROM ref_road WHERE commune_insee = :commune"), params)
        for batch in _batches(
            {
                "commune": commune,
                "cleabs": r.cleabs[:30],
                "name": r.name[:200] if r.name else None,
                "nature": r.nature[:60],
                "private": r.private,
                "width": r.width_m,
                "wkb": shapely.to_wkb(LineString(r.coords)),
            }
            for r in roads
        ):
            session.execute(
                text(
                    "INSERT INTO ref_road (commune_insee, cleabs, name, nature, private, width_m, geometry) "
                    "VALUES (:commune, :cleabs, :name, :nature, :private, :width, ST_GeomFromWKB(:wkb, 2154))"
                ),
                batch,
            )
    session.execute(text("DELETE FROM ref_parcel_staging WHERE import_id = :id"), params)
    session.execute(text("DELETE FROM ref_building_staging WHERE import_id = :id"), params)
    record = session.get(RefImport, import_id)
    assert record is not None
    record.status = "succeeded"
    record.counts = counts
    record.sha256 = {"parcelles": parcels.sha256, "batiments": buildings.sha256, "communes": communes.sha256}
    record.finished_at = utcnow()
    session.commit()
    return ImportResult(commune, "succeeded", release, counts)
