"""Endpunkte des Kundenwegs im Hausmodell (docs/PLAN_HAUSMODELL.md 3.7–3.10; HM4).

Kunden arbeiten hinter dem Feature-Flag `house_model`, getrennt vom Konfigurator der Fahne `configurator`
(Parallelbetrieb 3.12). Das Büro liest dieselbe Konfiguration mit Snapshot ohne Flag, nur mit Rolle. Alle
Antworten sind Simulation (D11, L7); keine Büroaktion ist Voraussetzung.
"""

import uuid
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.configuration import house_service as service
from app.configuration.api import Reader, revision_header
from app.configuration.house_schemas import (
    HouseConfigurationOut,
    HouseConfigurationPatch,
    HouseConfigurationStaffOut,
    HouseDocumentsOut,
    HouseTemplatesOut,
)
from app.configuration.schemas import PlacementAreaOut, PresetsOut
from app.house.engine import engine_client
from app.platform import flags, rate_limit
from app.platform.auth.context import RequestAuth, StaffPrincipal, get_auth, require_project_access
from app.platform.db import get_db
from app.platform.problems import Problem

router = APIRouter(tags=["house-configuration"])


def require_house_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


Feature = Depends(require_house_feature)


def _limit(request: Request, name: str) -> None:
    rate_limit.check(request, name, get_settings().configuration_limit_per_minute, 60)


@router.get(
    "/projects/{project_id}/house/templates", response_model=HouseTemplatesOut, dependencies=[Feature]
)
def list_templates(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
    client: httpx2.Client = Depends(engine_client),
) -> HouseTemplatesOut:
    """Angebotene Haustypen mit Zulässigkeit, allen Gründen, Richtpreis „ab“ und Kennwerten (D12)."""
    _limit(request, "house_templates")
    return service.list_templates(db, client, project_id)


@router.get(
    "/projects/{project_id}/house/configuration", response_model=HouseConfigurationOut, dependencies=[Feature]
)
def get_configuration(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> HouseConfigurationOut:
    """Gespeicherte Konfiguration; Grundstück und Regeln im aktuellen Stand (E-HM-7)."""
    _limit(request, "house_read")
    return service.get_configuration(db, project_id)


@router.patch(
    "/projects/{project_id}/house/configuration", response_model=HouseConfigurationOut, dependencies=[Feature]
)
def patch_configuration(
    request: Request,
    body: HouseConfigurationPatch,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
    client: httpx2.Client = Depends(engine_client),
    if_match: Annotated[str | None, Header()] = None,
) -> HouseConfigurationOut:
    """Haustyp, Auswahl, Lage oder Grenzschalter ändern. `If-Match` mit der Revision schützt vor
    überschriebenen Änderungen (409). Gespeichert wird auch eine Auswahl oder Lage mit Abweichungen (E-HM-6);
    abgelehnt werden ein gesperrter Haustyp (D12), eine Auswahl, die der Kern nicht rechnet, und eine nicht
    vorgesehene Drehung."""
    _limit(request, "house_write")
    return service.patch_configuration(
        db, client, project_id, body, if_match=revision_header(if_match), actor="customer"
    )


@router.get(
    "/projects/{project_id}/house/configuration/documents",
    response_model=HouseDocumentsOut,
    dependencies=[Feature],
)
def get_documents(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> HouseDocumentsOut:
    """Festgehaltenes Template und Katalogversion für den Kern im Browser (E-HM-20)."""
    _limit(request, "house_documents")
    return service.documents(db, project_id)


@router.get(
    "/projects/{project_id}/house/configuration/placement-area",
    response_model=PlacementAreaOut,
    dependencies=[Feature],
)
def get_placement_area(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> PlacementAreaOut:
    """Fläche zulässiger Ursprünge je erlaubter Drehung für das Haus mit der gespeicherten Auswahl."""
    _limit(request, "house_area")
    return service.placement_area(db, project_id)


@router.post(
    "/projects/{project_id}/house/configuration/placement-presets",
    response_model=PresetsOut,
    dependencies=[Feature],
)
def post_placement_presets(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> PresetsOut:
    """Schnellstellungen `street_near`, `set_back`, `garden_max` (Spez. 5.3.5) zur gespeicherten Auswahl."""
    _limit(request, "house_presets")
    return service.presets(db, project_id)


@router.get("/admin/projects/{project_id}/house/configuration", response_model=HouseConfigurationStaffOut)
def get_configuration_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> HouseConfigurationStaffOut:
    """Konfiguration mit festgehaltenen Versionen und Snapshot (exakte Beträge) für die Prüfung einer Anfrage;
    ohne Feature-Flag, nur mit Rolle."""
    return service.get_configuration_staff(db, project_id)
