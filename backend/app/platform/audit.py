"""Audit-Log für Freigaben, Veröffentlichungen, Statuswechsel, Löschungen, Anmeldungen (Spez. 10.1).

Der Eintrag entsteht in der Transaktion der Änderung und wird mit ihr bestätigt.
"""

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.platform.logging import request_id_var
from app.platform.models import AuditLog

ActorType = Literal["staff", "customer", "system", "api_key"]


def record(
    session: Session,
    *,
    actor_type: ActorType,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    if actor_id is not None and actor_id.startswith("api_key:"):
        # Fachmodule übergeben für Architekten und API-Schlüssel dieselbe Art (AN6, PLAN_AN6_MANDANTEN 3.6)
        actor_type = "api_key"
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            request_id=request_id_var.get(),
        )
    )
