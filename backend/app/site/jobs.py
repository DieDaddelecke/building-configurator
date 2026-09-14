"""Hintergrundjobs des Moduls G1 (Spez. 7, Plan 3.3).

`site_enrich`: Gelände (Höhendienst) und Risiken (Géorisques) nach dem Bilden des Grundstücks. Fällt ein
Dienst nach der letzten Wiederholung aus, gilt „nicht abgefragt“ (`unavailable`), ohne Abbruch.
`cadastre_import`: wöchentliche Prüfung auf neue Katasterstände je Gemeinde des Einzugsgebiets.
"""

import uuid
from datetime import timedelta
from typing import Any

import httpx2
from sqlalchemy import delete, select, text

from app.config import get_settings
from app.integrations import geoplateforme, georisques
from app.integrations.etalab_cadastre import CadastreSource, EtalabCadastre
from app.integrations.http import ExternalServiceError, new_client
from app.integrations.ign_bdtopo import GeoplateformeRoads, RoadSource
from app.platform.jobs import JobContext, job, periodic
from app.platform.jobs.registry import get_job_spec
from app.platform.logging import get_logger
from app.site import cadastre_import
from app.site.domain import terrain as terrain_domain
from app.site.models import Site, SiteRisk, Terrain

log = get_logger("site_jobs")


# Austauschbar für Tests: HTTP-Client und Katasterquelle
def client_factory() -> httpx2.Client:
    return new_client(get_settings())


def cadastre_source_factory(client: httpx2.Client) -> CadastreSource:
    return EtalabCadastre(client, get_settings())


def road_source_factory(client: httpx2.Client) -> RoadSource:
    return GeoplateformeRoads(client, get_settings())


def _wgs84(session: Any, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return []
    rows = session.execute(
        text(
            "SELECT ST_X(g) AS lon, ST_Y(g) AS lat FROM ("
            "SELECT ST_Transform(ST_SetSRID(ST_MakePoint(x, y), 2154), 4326) AS g, ord "
            "FROM unnest(CAST(:xs AS float8[]), CAST(:ys AS float8[])) WITH ORDINALITY AS t(x, y, ord)"
            ") AS s ORDER BY ord"
        ),
        {"xs": [p[0] for p in points], "ys": [p[1] for p in points]},
    ).all()
    return [(float(r.lon), float(r.lat)) for r in rows]


@job("site_enrich", max_attempts=3, timeout_seconds=60)
def site_enrich(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    from geoalchemy2.shape import to_shape

    settings = get_settings()
    final_attempt = ctx.attempt >= get_job_spec("site_enrich").max_attempts
    site_id = uuid.UUID(payload["site_id"])
    outline_hash = payload["outline_hash"]

    # 1. Lesen, dann Transaktion schließen: externe Aufrufe halten keine Verbindung offen
    with ctx.session() as session:
        site = session.get(Site, site_id)
        if site is None or site.outline_hash != outline_hash:
            return {"skipped": "site_changed"}
        polygon = to_shape(site.geometry)
        points = terrain_domain.sample_points(polygon)
        points_wgs84 = _wgs84(session, points)
        anchor = polygon.representative_point()
        anchor_wgs84 = _wgs84(session, [(anchor.x, anchor.y)])[0]
        need_terrain = site.terrain_status != "ok"
        need_risks = site.risks_status != "ok"

    # 2. Externe Dienste
    errors: list[str] = []
    evaluated: terrain_domain.TerrainResult | None = None
    risks: list[georisques.RiskItem] | None = None
    with client_factory() as client:
        if need_terrain:
            try:
                evaluated = terrain_domain.evaluate(
                    points, geoplateforme.elevations(client, settings, points_wgs84)
                )
                if evaluated is None:
                    raise ExternalServiceError(geoplateforme.ALTIMETRY, "too_few_altitudes")
            except ExternalServiceError as exc:
                errors.append(str(exc))
        if need_risks:
            try:
                risks = georisques.site_risks(client, settings, *anchor_wgs84)
            except ExternalServiceError as exc:
                errors.append(str(exc))

    # 3. Schreiben, nur wenn der Umriss noch derselbe ist
    results: dict[str, Any] = {}
    with ctx.session() as session:
        site = session.execute(select(Site).where(Site.id == site_id).with_for_update()).scalar_one_or_none()
        if site is None or site.outline_hash != outline_hash:
            return {"skipped": "site_changed"}
        if need_terrain:
            if evaluated is not None:
                session.execute(delete(Terrain).where(Terrain.site_id == site.id))
                session.add(
                    Terrain(
                        site_id=site.id,
                        method="ign_altimetry",
                        reference_altitude_ngf=evaluated.reference_altitude_ngf,
                        slope_percent=evaluated.slope_percent,
                        samples=[list(s) for s in evaluated.samples],
                        outline_hash=outline_hash,
                        created_by="system:site_enrich",
                    )
                )
                site.terrain_status = results["terrain"] = "ok"
            elif final_attempt:
                site.terrain_status = results["terrain"] = "unavailable"
        if need_risks:
            if risks is not None:
                session.execute(delete(SiteRisk).where(SiteRisk.site_id == site.id))
                for item in risks:
                    session.add(
                        SiteRisk(
                            site_id=site.id,
                            kind=item.kind,
                            level=item.level,
                            scope=item.scope,
                            label=item.label[:300],
                            source=georisques.SERVICE,
                            created_by="system:site_enrich",
                        )
                    )
                site.risks_status = "ok"
                results["risks"] = len(risks)
            elif final_attempt:
                site.risks_status = results["risks"] = "unavailable"
        session.commit()
    if errors and not final_attempt:
        # Teilergebnisse sind gespeichert; die Wiederholung fragt nur ab, was noch fehlt
        raise ExternalServiceError("site_enrich", "; ".join(errors))
    if errors:
        log.warning("site_enrich_unavailable", errors=errors)
    return results


@job("cadastre_import", max_attempts=2, timeout_seconds=3600)
def cadastre_import_job(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Alle Gemeinden des Einzugsgebiets. Ein Fehler bricht die übrigen nicht ab, der Job scheitert dann."""
    settings = get_settings()
    communes = payload.get("communes") or settings.cadastre_communes
    force = bool(payload.get("force", False))
    outcome: dict[str, Any] = {}
    failed: list[str] = []
    with client_factory() as client, ctx.session() as session:
        source = cadastre_source_factory(client)
        roads = road_source_factory(client)
        for commune in communes:
            try:
                result = cadastre_import.import_commune(
                    session, source, settings, commune, force=force, roads=roads
                )
            except ExternalServiceError as exc:
                failed.append(f"{commune}: {exc}")
                outcome[commune] = {"status": "failed", "error": str(exc)}
                continue
            outcome[commune] = {"status": result.status, "release": result.release, **result.counts}
            if result.status == "failed":
                failed.append(f"{commune}: {result.error}")
    if failed:
        raise RuntimeError("cadastre_import_failed: " + "; ".join(failed))
    return outcome


def latest_imports(session: Any) -> list[Any]:
    from app.site.models import RefImport

    subquery = (
        select(RefImport.commune_insee, RefImport.id)
        .distinct(RefImport.commune_insee)
        .order_by(RefImport.commune_insee, RefImport.created_at.desc())
        .subquery()
    )
    return list(
        session.execute(
            select(RefImport).join(subquery, RefImport.id == subquery.c.id).order_by(RefImport.commune_insee)
        ).scalars()
    )


periodic("cadastre_import", kind="cadastre_import", every=timedelta(days=7))


@job("site_housekeeping", max_attempts=1, timeout_seconds=300)
def site_housekeeping(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Abgelaufene Einträge des Adress-Caches entfernen (Aufbewahrung, Plan 6.6)."""
    hours = get_settings().geocode_cache_hours
    with ctx.session() as session:
        deleted = session.execute(
            text("DELETE FROM geocode_cache WHERE fetched_at < now() - make_interval(hours => :hours)"),
            {"hours": hours},
        ).rowcount  # type: ignore[attr-defined]
        session.commit()
    return {"geocode_cache_deleted": deleted}


periodic("site_housekeeping", kind="site_housekeeping", every=timedelta(hours=6))
