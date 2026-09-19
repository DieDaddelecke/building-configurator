"""Endpunkte des Moduls H2 (Spez. 6.3; Plan H2 4.3).

Kunden arbeiten hinter dem Feature-Flag `configurator`; er setzt die Flags von G1 bis G3 nicht voraus, braucht
aber deren Daten. Das Büro liest dieselbe Konfiguration beim Prüfen einer Anfrage (Modul A, später V).
Alle Antworten sind Simulation (D11, L7); keine Büroaktion ist Voraussetzung.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.configuration import service
from app.configuration.schemas import (
    ConfigurationOut,
    ConfigurationPatch,
    PlacementAreaOut,
    PresetsOut,
    TypesOut,
)
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.problems import Problem

router = APIRouter(tags=["configuration"])


def require_configurator_feature(
    auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)
) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


Feature = Depends(require_configurator_feature)
Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))
TypeQuery = Annotated[str | None, Query(alias="type", pattern=r"^[a-z][a-z0-9_]{1,59}$")]


def _limit(request: Request, name: str) -> None:
    rate_limit.check(request, name, get_settings().configuration_limit_per_minute, 60)


def _revision(if_match: str | None) -> int | None:
    """`If-Match: 3` oder `"3"`; ohne Header wird nicht auf Änderungen geprüft."""
    if if_match is None:
        return None
    value = if_match.strip().strip('"')
    if not value.isdigit():
        raise Problem(422, "validation_error", detail="If-Match muss eine Revisionsnummer sein")
    return int(value)


@router.get("/projects/{project_id}/catalog/types", response_model=TypesOut, dependencies=[Feature])
def list_types(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> TypesOut:
    """Veröffentlichte Typen mit Zulässigkeit, allen Gründen und Vorschlägen (Spez. 5.4.6)."""
    _limit(request, "configuration_types")
    return service.list_types(db, project_id)


@router.get("/projects/{project_id}/configuration", response_model=ConfigurationOut, dependencies=[Feature])
def get_configuration(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ConfigurationOut:
    _limit(request, "configuration_read")
    return service.get_configuration(db, project_id)


@router.patch("/projects/{project_id}/configuration", response_model=ConfigurationOut, dependencies=[Feature])
def patch_configuration(
    request: Request,
    body: ConfigurationPatch,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header()] = None,
) -> ConfigurationOut:
    """Typ, Lage oder Grenzschalter ändern. `If-Match` mit der Revision schützt vor überschriebenen
    Änderungen (409). Ein gesperrter Typ oder eine Lage mit bindendem Verstoß wird nicht gespeichert (422)."""
    _limit(request, "configuration_write")
    return service.patch_configuration(db, project_id, body, if_match=_revision(if_match), actor="customer")


@router.get(
    "/projects/{project_id}/configuration/placement-area",
    response_model=PlacementAreaOut,
    dependencies=[Feature],
)
def get_placement_area(
    request: Request,
    type_slug: TypeQuery = None,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> PlacementAreaOut:
    """Fläche zulässiger Ursprünge je erlaubter Drehung; das Frontend prüft beim Ziehen lokal dagegen."""
    _limit(request, "configuration_area")
    return service.placement_area(db, project_id, type_slug)


@router.post(
    "/projects/{project_id}/configuration/placement-presets",
    response_model=PresetsOut,
    dependencies=[Feature],
)
def post_placement_presets(
    request: Request,
    type_slug: TypeQuery = None,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> PresetsOut:
    """Schnellstellungen `street_near`, `set_back`, `garden_max` (Spez. 5.3.5)."""
    _limit(request, "configuration_presets")
    return service.presets(db, project_id, type_slug)


@router.get("/admin/projects/{project_id}/configuration", response_model=ConfigurationOut)
def get_configuration_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> ConfigurationOut:
    """Konfiguration für die Prüfung einer Anfrage; ohne Feature-Flag, nur mit Rolle."""
    return service.get_configuration(db, project_id)
