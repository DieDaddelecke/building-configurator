"""Endpunkte des Moduls G1 (Spez. 6.3, 6.4; Plan 3.3).

Kundenendpunkte laufen hinter dem Feature-Flag `site_selection` (Plan 4.2). Büroendpunkte brauchen die
Rolle `architect` (Kanten) bzw. `ops` (Katasterimport).
"""

import uuid
from dataclasses import asdict
from datetime import timedelta
from typing import Annotated, Any, Literal

import httpx2
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import geoplateforme
from app.integrations.http import ExternalServiceError, shared_client
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    public,
    require_project_access,
    require_roles,
)
from app.platform.auth.tokens import keyed_digest
from app.platform.db import get_db, utcnow
from app.platform.jobs import enqueue
from app.platform.problems import Problem
from app.site import service
from app.site.domain.edges import OverrideKind
from app.site.jobs import latest_imports
from app.site.models import GeocodeCache
from app.site.schemas import (
    AddressOut,
    ArchitectEdgeIn,
    CommuneOut,
    CustomerEdgeIn,
    ImportRequestIn,
    ImportStatusOut,
    LookupIn,
    LookupOut,
    SiteIn,
    SiteOut,
    SiteReviewItem,
)

router = APIRouter(tags=["site"])


def require_site_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    """Freischaltung intern → Beta → öffentlich über `site_selection` (Plan 4.2)."""
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


def _if_match(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip().strip('"').removeprefix("W/").strip('"'))
    except ValueError:
        raise Problem(412, "invalid_if_match") from None


Feature = Depends(require_site_feature)


# ---------------------------------------------------------------------------
# Öffentlich (hinter Flag)
# ---------------------------------------------------------------------------


@router.get("/geocode", response_model=list[AddressOut], dependencies=[Depends(public), Feature])
def geocode(
    request: Request,
    q: Annotated[str, Query(min_length=3, max_length=200)],
    db: Session = Depends(get_db),
    client: httpx2.Client = Depends(shared_client),
) -> list[AddressOut]:
    """Adressvorschläge der Géoplateforme mit Cache (Plan 3.3 Schritt 1)."""
    settings = get_settings()
    rate_limit.check(request, "geocode", settings.geocode_limit_per_minute, 60)
    normalized = " ".join(q.lower().split())
    key = keyed_digest(settings.secret_key.get_secret_value(), f"geocode:{normalized}")
    cached = db.get(GeocodeCache, key)
    if cached is not None and utcnow() - cached.fetched_at < timedelta(hours=settings.geocode_cache_hours):
        raw = cached.response
    else:
        try:
            candidates = geoplateforme.search_addresses(client, settings, normalized, limit=5)
        except ExternalServiceError:
            raise Problem(503, "geocoding_unavailable") from None
        raw = [asdict(c) for c in candidates]
        db.execute(
            insert(GeocodeCache)
            .values(key=key, response=raw, fetched_at=utcnow())
            .on_conflict_do_update(index_elements=["key"], set_={"response": raw, "fetched_at": utcnow()})
        )
        db.commit()
    served = service.communes_in_service_area(db, {item["citycode"] for item in raw})
    return [
        AddressOut(
            label=item["label"],
            kind=item["kind"],
            lon=item["lon"],
            lat=item["lat"],
            citycode=item["citycode"],
            postcode=item.get("postcode"),
            city=item["city"],
            in_service_area=item["citycode"] in served,
        )
        for item in raw
    ]


@router.get(
    "/cadastre/service-area", response_model=list[CommuneOut], dependencies=[Depends(public), Feature]
)
def cadastre_service_area(db: Session = Depends(get_db)) -> list[CommuneOut]:
    """Gemeinden mit importiertem Kataster; außerhalb gibt es keine Parzellenwahl (Plan 3.3)."""
    return service.service_area(db)


@router.get("/cadastre/parcels", dependencies=[Depends(public), Feature])
def cadastre_parcels(
    request: Request,
    bbox: Annotated[
        str,
        Query(pattern=r"^-?\d+(\.\d+)?(,-?\d+(\.\d+)?){3}$", description="min_lon,min_lat,max_lon,max_lat"),
    ],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Parzellen im Kartenausschnitt als GeoJSON (WGS84), höchstens 4000."""
    rate_limit.check(request, "cadastre_parcels", get_settings().cadastre_limit_per_minute, 60)
    x0, y0, x1, y1 = (float(v) for v in bbox.split(","))
    return service.parcels_in_bbox(db, (x0, y0, x1, y1))


# ---------------------------------------------------------------------------
# Kunde (Projekt-Cookie, hinter Flag)
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/parcels/lookup", response_model=LookupOut, dependencies=[Feature])
def lookup_parcels(
    request: Request,
    body: LookupIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> LookupOut:
    rate_limit.check(request, "cadastre_parcels", get_settings().cadastre_limit_per_minute, 60)
    return service.lookup(db, body)


@router.put("/projects/{project_id}/site", response_model=SiteOut, dependencies=[Feature])
def put_site(
    request: Request,
    body: SiteIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> SiteOut:
    """Grundstück aus einer oder mehreren zusammenhängenden Parzellen bilden (Spez. 5.1.3)."""
    rate_limit.check(request, "site_write", get_settings().site_write_limit_per_hour, 3600)
    return service.form_site(db, project_id, body.parcel_idus, actor=f"project:{project_id}")


@router.get("/projects/{project_id}/site", response_model=SiteOut, dependencies=[Feature])
def get_site(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> SiteOut:
    return service.load_site(db, project_id)


@router.patch("/projects/{project_id}/site/edges/{seq}", response_model=SiteOut, dependencies=[Feature])
def patch_edge_customer(
    request: Request,
    seq: int,
    body: CustomerEdgeIn,
    project_id: uuid.UUID = Depends(require_project_access),
    if_match: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> SiteOut:
    """Kunde ordnet eine Kante als Straße oder Nachbar ein; nicht bindend bis zur Bestätigung (Plan 3.3)."""
    rate_limit.check(request, "site_write", get_settings().site_write_limit_per_hour, 3600)
    kind: OverrideKind | None = None
    if body.kind is not None:
        kind = "street" if body.kind == "street" else "not_street"
    actor = service.Actor(type="customer", id=f"project:{project_id}", role="customer")
    return service.correct_edge(db, project_id, seq, kind, actor, _if_match(if_match))


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------

Architect = Depends(require_roles(Role.architect))


@router.get("/admin/sites/review", response_model=list[SiteReviewItem])
def site_review_queue(
    scope: Annotated[Literal["corrections", "all"], Query()] = "corrections",
    staff: StaffPrincipal = Architect,
    db: Session = Depends(get_db),
) -> list[SiteReviewItem]:
    """Unbestätigte Kundenkorrekturen; mit `scope=all` zusätzlich unsichere Einordnungen und Sonderfälle."""
    return service.review_queue(db, only_corrections=scope == "corrections")


@router.get("/admin/projects/{project_id}/site", response_model=SiteOut)
def get_site_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Architect, db: Session = Depends(get_db)
) -> SiteOut:
    return service.load_site(db, project_id)


@router.patch("/admin/projects/{project_id}/site/edges/{seq}", response_model=SiteOut)
def patch_edge_architect(
    project_id: uuid.UUID,
    seq: int,
    body: ArchitectEdgeIn,
    if_match: Annotated[str | None, Header()] = None,
    staff: StaffPrincipal = Architect,
    db: Session = Depends(get_db),
) -> SiteOut:
    actor = service.Actor(type="staff", id=staff.actor_id, role="architect")
    return service.correct_edge(db, project_id, seq, body.kind, actor, _if_match(if_match))


@router.post("/admin/projects/{project_id}/site/edges/confirm", response_model=SiteOut)
def confirm_edges(
    project_id: uuid.UUID,
    if_match: Annotated[str | None, Header()] = None,
    staff: StaffPrincipal = Architect,
    db: Session = Depends(get_db),
) -> SiteOut:
    actor = service.Actor(type="staff", id=staff.actor_id, role="architect")
    return service.confirm_customer_edges(db, project_id, actor, _if_match(if_match))


@router.get("/admin/cadastre/imports", response_model=list[ImportStatusOut])
def cadastre_imports(
    staff: StaffPrincipal = Depends(require_roles(Role.ops)), db: Session = Depends(get_db)
) -> list[ImportStatusOut]:
    """Letzter Import je Gemeinde: Stand, Anzahl, Fehler (Plan 6.8 „Alter der Katasterdaten“)."""
    configured = set(get_settings().cadastre_communes)
    rows = {r.commune_insee: r for r in latest_imports(db)}
    result = [
        ImportStatusOut(
            commune_insee=r.commune_insee,
            status=r.status,
            release=r.release,
            counts=r.counts,
            error=r.error,
            created_at=r.created_at,
            finished_at=r.finished_at,
        )
        for r in rows.values()
    ]
    now = utcnow()
    result += [
        ImportStatusOut(
            commune_insee=c,
            status="never",
            release=None,
            counts={},
            error=None,
            created_at=now,
            finished_at=None,
        )
        for c in sorted(configured - rows.keys())
    ]
    return sorted(result, key=lambda r: r.commune_insee)


@router.post("/admin/cadastre/imports", status_code=202)
def start_cadastre_import(
    body: ImportRequestIn,
    staff: StaffPrincipal = Depends(require_roles(Role.ops)),
    db: Session = Depends(get_db),
) -> dict[str, uuid.UUID]:
    job_id = enqueue(db, "cadastre_import", {"force": body.force}, created_by=staff.actor_id)
    db.commit()
    return {"job_id": job_id}


@router.post("/admin/sites/enrich-retry", status_code=202)
def retry_site_enrichment(
    staff: StaffPrincipal = Depends(require_roles(Role.ops)), db: Session = Depends(get_db)
) -> dict[str, int]:
    """Nach einem Ausfall von Höhendienst oder Géorisques: nicht abgefragte Grundstücke erneut anstoßen."""
    return {"sites": service.retry_enrichment(db, staff.actor_id)}
