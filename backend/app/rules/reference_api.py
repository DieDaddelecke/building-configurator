"""Gemeinsame Verwaltung: Referenzlisten (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10, VA10).

In beiden Produkten eingehängt; Listen liegen in der gemeinsamen Datenbank, gemessen wird die Auswertung der
jeweiligen Instanz. Lesen und Schreiben: `ops`, `rules_admin` – nicht an ein Büro gebunden.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform.auth.context import Role, StaffPrincipal, require_roles
from app.platform.db import get_db
from app.platform.shared import get_shared_db
from app.rules import reference_store as store
from app.rules.schemas import (
    ReferenceCandidateOut,
    ReferenceEntryIn,
    ReferenceListDetailOut,
    ReferenceListIn,
    ReferenceListOut,
    ReferenceListPatch,
    ReferenceMeasurementOut,
)

router = APIRouter(tags=["reference"])
Admin = Depends(require_roles(Role.ops, Role.rules_admin))


def _name(staff: StaffPrincipal) -> str:
    return staff.display_name or staff.email


@router.get("/admin/reference-lists", response_model=list[ReferenceListOut])
def list_reference_lists(
    staff: StaffPrincipal = Admin, db: Session = Depends(get_db), shared_db: Session = Depends(get_shared_db)
) -> list[ReferenceListOut]:
    """Alle Listen mit der Messung der aktuellen Auswertung dieser Instanz, wo das Dokument hier vorliegt."""
    return store.lists_out(db, shared_db)


@router.get("/admin/reference-lists/candidates", response_model=list[ReferenceCandidateOut])
def reference_candidates(
    staff: StaffPrincipal = Admin, db: Session = Depends(get_db)
) -> list[ReferenceCandidateOut]:
    """Ausgewertete Dokumente dieser Instanz mit ihren Sektoren."""
    return store.candidates(db)


@router.post("/admin/reference-lists", response_model=ReferenceListDetailOut, status_code=201)
def create_reference_list(
    body: ReferenceListIn,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.create_list(db, shared_db, get_settings(), body, staff.actor_id, _name(staff))


@router.post("/admin/reference-lists/import", response_model=ReferenceListDetailOut, status_code=201)
def import_reference_list(
    body: dict[str, Any],
    replace: bool = Query(default=False),
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    """Datei im Format `emprise-reference/1`; eine vorhandene Liste nur mit `replace=true`."""
    return store.import_list(db, shared_db, get_settings(), body, replace, staff.actor_id, _name(staff))


@router.get("/admin/reference-lists/{list_id}", response_model=ReferenceListDetailOut)
def get_reference_list(
    list_id: uuid.UUID,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.detail_out(db, shared_db, list_id)


@router.patch("/admin/reference-lists/{list_id}", response_model=ReferenceListDetailOut)
def patch_reference_list(
    list_id: uuid.UUID,
    body: ReferenceListPatch,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.update_list(db, shared_db, get_settings(), list_id, body, staff.actor_id, _name(staff))


@router.delete("/admin/reference-lists/{list_id}", status_code=204)
def delete_reference_list(
    list_id: uuid.UUID, staff: StaffPrincipal = Admin, shared_db: Session = Depends(get_shared_db)
) -> Response:
    store.delete_list(shared_db, get_settings(), list_id, staff.actor_id, _name(staff))
    return Response(status_code=204)


@router.post(
    "/admin/reference-lists/{list_id}/entries", response_model=ReferenceListDetailOut, status_code=201
)
def add_reference_entry(
    list_id: uuid.UUID,
    body: ReferenceEntryIn,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.put_entry(db, shared_db, get_settings(), list_id, body, staff.actor_id, _name(staff))


@router.put("/admin/reference-lists/{list_id}/entries/{entry_id}", response_model=ReferenceListDetailOut)
def change_reference_entry(
    list_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: ReferenceEntryIn,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.put_entry(
        db, shared_db, get_settings(), list_id, body, staff.actor_id, _name(staff), entry_id
    )


@router.delete("/admin/reference-lists/{list_id}/entries/{entry_id}", response_model=ReferenceListDetailOut)
def delete_reference_entry(
    list_id: uuid.UUID,
    entry_id: uuid.UUID,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    return store.delete_entry(db, shared_db, get_settings(), list_id, entry_id, staff.actor_id, _name(staff))


@router.post("/admin/reference-lists/{list_id}/from-evaluation", response_model=ReferenceListDetailOut)
def reference_from_evaluation(
    list_id: uuid.UUID,
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceListDetailOut:
    """Einträge durch die aktuelle Auswertung dieser Instanz ersetzen (Entwurf zum Nachprüfen)."""
    return store.from_evaluation(db, shared_db, get_settings(), list_id, staff.actor_id, _name(staff))


@router.get("/admin/reference-lists/{list_id}/measurement", response_model=ReferenceMeasurementOut)
def measure_reference_list(
    list_id: uuid.UUID,
    version: int | None = Query(default=None, ge=1),
    staff: StaffPrincipal = Admin,
    db: Session = Depends(get_db),
    shared_db: Session = Depends(get_shared_db),
) -> ReferenceMeasurementOut:
    """Auswertung dieser Instanz an der Liste messen, ohne Aufruf des Modells; ohne `version` die aktuelle."""
    return store.measurement(db, shared_db, list_id, version)


@router.get("/admin/reference-lists/{list_id}/export")
def export_reference_list(
    list_id: uuid.UUID, staff: StaffPrincipal = Admin, shared_db: Session = Depends(get_shared_db)
) -> dict[str, Any]:
    """Liste als Datei (`emprise-reference/1`), wie `app/rules/reference_seed`."""
    return store.export(shared_db, list_id)
