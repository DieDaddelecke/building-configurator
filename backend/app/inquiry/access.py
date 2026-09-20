"""Zugangslink für Kunden mit Vorgang (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.9; schließt AF12 Punkt 1).

Der Link `…/zugang#t=<Token>` trägt Projekt und Ablauf, signiert mit `secret_key`; er enthält keine
personenbezogenen Daten (Spez. 5.10.7) und steht im Fragment, damit er in keinem Serverlog erscheint.
Weil vom Projekttoken nur der Hash gespeichert ist, gibt das Einlösen ein **neues** Token aus: Andere
Geräte verlieren den Zugang, bis sie den Link ebenfalls öffnen (Plan V 8, E-V5).
"""

import base64
import hashlib
import hmac
import uuid
from datetime import timedelta

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inquiry.models import Customer, Inquiry
from app.platform import audit
from app.platform.auth.tokens import PROJECT_COOKIE, hash_token, new_token
from app.platform.db import utcnow
from app.platform.i18n import SUPPORTED, Locale
from app.platform.mail import queue_mail
from app.platform.models import Project
from app.platform.problems import Problem

PURPOSE = b"project_access|"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(payload: bytes) -> bytes:
    secret = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(secret, PURPOSE + payload, hashlib.sha256).digest()[:16]


def make_token(project_id: uuid.UUID) -> str:
    expires = int((utcnow() + timedelta(days=get_settings().access_link_days)).timestamp())
    payload = project_id.bytes + expires.to_bytes(8, "big")
    return f"{_b64(payload)}.{_b64(_signature(payload))}"


def access_url(project_id: uuid.UUID) -> str:
    return f"{get_settings().public_base_url}/zugang#t={make_token(project_id)}"


def read_token(token: str) -> uuid.UUID:
    """Projekt aus einem gültigen, nicht abgelaufenen Token; sonst `400 access_link_invalid`."""
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload, signature = _unb64(encoded_payload), _unb64(encoded_signature)
    except ValueError:
        raise Problem(400, "access_link_invalid") from None
    if len(payload) != 24 or not hmac.compare_digest(signature, _signature(payload)):
        raise Problem(400, "access_link_invalid")
    if int.from_bytes(payload[16:], "big") < utcnow().timestamp():
        raise Problem(400, "access_link_invalid", reason="expired")
    return uuid.UUID(bytes=payload[:16])


def redeem(db: Session, token: str, response: Response) -> uuid.UUID:
    """Link einlösen: neues Projekttoken, Cookie wie bei der Projektanlage (`platform/projects.py`)."""
    settings = get_settings()
    project_id = read_token(token)
    project = db.get(Project, project_id)
    has_inquiry = db.execute(select(Inquiry.id).where(Inquiry.project_id == project_id)).first()
    if project is None or has_inquiry is None:
        raise Problem(400, "access_link_invalid")
    fresh = new_token()
    project.access_token_hash = hash_token(fresh)
    project.last_activity_at = utcnow()
    audit.record(
        db,
        actor_type="customer",
        actor_id=str(project_id),
        action="project.access_link",
        entity_type="project",
        entity_id=str(project_id),
    )
    db.commit()
    response.set_cookie(
        PROJECT_COOKIE,
        fresh,
        max_age=settings.project_retention_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return project_id


def request_links(db: Session, email: str) -> None:
    """Je Projekt mit Vorgang und bestätigtem Kunden dieser Adresse eine Mail mit Link. Die Antwort verrät
    nicht, ob die Adresse bekannt ist (die API antwortet immer 202)."""
    rows = db.execute(
        select(Customer, Inquiry)
        .join(Inquiry, Inquiry.customer_id == Customer.id)
        .where(Customer.email == email.strip().lower(), Customer.verified_at.is_not(None))
    ).all()
    for customer, inquiry in rows:
        queue_mail(
            db,
            to=customer.email,
            template="access_link",
            locale=customer_locale(customer),
            params={"number": inquiry.number, "access_url": access_url(inquiry.project_id)},
            project_id=inquiry.project_id,
            created_by="customer",
        )
    db.commit()


def customer_locale(customer: Customer) -> Locale:
    return customer.locale if customer.locale in SUPPORTED else "fr"
