"""Transaktionsmails als Job: Die Mail wird mit der Fachänderung vorgemerkt und danach zugestellt.

Vorlagen sind Übersetzungsschlüssel `mail.<vorlage>.subject` und `mail.<vorlage>.body`.
Die Empfängeradresse steht nur in der Jobtabelle, nie im Log.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import smtp
from app.platform.i18n import Locale, translate
from app.platform.jobs import JobContext, enqueue, job


def queue_mail(
    session: Session,
    *,
    to: str,
    template: str,
    locale: Locale,
    params: dict[str, str] | None = None,
    project_id: uuid.UUID | None = None,
    created_by: str | None = None,
) -> uuid.UUID:
    return enqueue(
        session,
        "mail_send",
        {"to": to, "template": template, "locale": locale, "params": params or {}},
        project_id=project_id,
        created_by=created_by,
    )


@job("mail_send", max_attempts=5, timeout_seconds=60)
def mail_send(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    locale: Locale = payload["locale"]
    params = payload.get("params") or {}
    template = payload["template"]
    subject = translate(f"mail.{template}.subject", locale, **params)
    body = translate(f"mail.{template}.body", locale, **params)
    message_id = smtp.send(
        settings, to=payload["to"], subject=subject, body=body, message_id_key=f"job-{ctx.job_id}"
    )
    return {"message_id": message_id}
