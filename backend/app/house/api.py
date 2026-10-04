"""Büro-API des Hausmodells (docs/PLAN_HAUSMODELL.md 3.6; HM3): Haustypen aus IFC, Entwurf, Prüfung,
Freigabe; Katalogversionen nur lesend (sie kommen in HM3 über die CLI).

Rollen: `architect` und `ops` lesen mit, `catalog_admin` lädt hoch, bearbeitet den Entwurf und gibt frei
(3.5, 3.6).
"""

from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, File, Path, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import get_settings
from app.house import service
from app.house.domain.draft import HouseDraftDecisions
from app.house.engine import engine_client
from app.house.schemas import (
    SLUG_PATTERN,
    HouseCatalogVersionOut,
    HouseTemplateSummaryOut,
    HouseTemplateVersionOut,
)
from app.platform.auth.context import Role, StaffPrincipal, require_roles
from app.platform.db import get_db
from app.platform.uploads import read_limited

router = APIRouter(tags=["house"])

Reader = Depends(require_roles(Role.architect, Role.catalog_admin, Role.ops))
Editor = Depends(require_roles(Role.catalog_admin))
SlugPath = Annotated[str, Path(pattern=SLUG_PATTERN)]
VERSION = "/admin/house/templates/{slug}/versions/{version}"


@router.get("/admin/house/templates", response_model=list[HouseTemplateSummaryOut])
def list_templates(
    staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> list[HouseTemplateSummaryOut]:
    return service.list_templates(db)


@router.post(
    "/admin/house/templates/{slug}/versions", response_model=HouseTemplateVersionOut, status_code=201
)
async def upload_ifc(
    slug: SlugPath,
    response: Response,
    file: UploadFile = File(...),
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> HouseTemplateVersionOut:
    """Neue Version eines Haustyps aus einer IFC-Datei (Importvertrag); der Import läuft im Hintergrund.
    Dieselbe Datei für einen offenen Entwurf liefert diesen mit 200."""
    data = await read_limited(file, get_settings().house_ifc_max_bytes)
    out, created = await run_in_threadpool(
        service.upload_ifc, db, slug, file.filename or "", data, staff.actor_id
    )
    if not created:
        response.status_code = 200
    return out


@router.get(VERSION, response_model=HouseTemplateVersionOut)
def get_version(
    slug: SlugPath, version: int, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> HouseTemplateVersionOut:
    return service.get_version(db, slug, version)


@router.put(VERSION + "/decisions", response_model=HouseTemplateVersionOut)
def set_decisions(
    slug: SlugPath,
    version: int,
    body: HouseDraftDecisions,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> HouseTemplateVersionOut:
    """Angaben des Büros zum Entwurf (Raumtypen, Rollen, Eingang, Höhe über Gelände, Standards)."""
    return service.set_decisions(db, slug, version, body, staff.actor_id)


@router.post(VERSION + "/check", response_model=HouseTemplateVersionOut)
def check_version(
    slug: SlugPath,
    version: int,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
    client: httpx2.Client = Depends(engine_client),
) -> HouseTemplateVersionOut:
    """Kompatibilität mit der Katalogversion über `engine` prüfen; kompatibel → `reviewed`."""
    return service.check_version(db, client, slug, version, staff.actor_id)


@router.post(VERSION + "/publish", response_model=HouseTemplateVersionOut)
def publish_version(
    slug: SlugPath, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> HouseTemplateVersionOut:
    """Freigabe des Prüfbefunds und Veröffentlichung; danach unveränderlich (L4)."""
    return service.publish_version(db, slug, version, staff.actor_id)


@router.post(VERSION + "/reject", response_model=HouseTemplateVersionOut)
def reject_version(
    slug: SlugPath, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> HouseTemplateVersionOut:
    return service.reject_version(db, slug, version, staff.actor_id)


@router.post(VERSION + "/retire", response_model=HouseTemplateVersionOut)
def retire_version(
    slug: SlugPath, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> HouseTemplateVersionOut:
    return service.retire_version(db, slug, version, staff.actor_id)


@router.get("/admin/house/catalogs", response_model=list[HouseCatalogVersionOut])
def list_catalog_versions(
    staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> list[HouseCatalogVersionOut]:
    return service.list_catalog_versions(db)
