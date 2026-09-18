"""Ablauf des Moduls A: Kontakt, E-Mail-Bestätigung, Anfrage mit Snapshot (Plan 3.6,
docs/PLAN_A_ANFRAGE.md 4.2). Prüfung der Simulation selbst läuft über die bestehenden Endpunkte von
G1 (Kanten), G2 (Regel-Overrides) und G3 (Baurahmen) – hier entsteht nur die Anfrage, die sie zusammenfasst.
"""

import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.envelope import service as envelope_service
from app.inquiry.models import Consent, Customer, Inquiry
from app.inquiry.schemas import (
    ConfirmIn,
    ConfirmOut,
    ConsentOut,
    ContactIn,
    ContactOut,
    CustomerOut,
    ExportOut,
    InquiryDetailOut,
    InquiryListItem,
    MyInquiryOut,
)
from app.platform import audit, rate_limit
from app.platform.auth.tokens import hash_token
from app.platform.db import utcnow
from app.platform.i18n import Locale
from app.platform.legal import current_texts
from app.platform.mail import queue_mail
from app.platform.models import Project
from app.platform.problems import Problem
from app.rules import service as rules_service
from app.site import service as site_service
from app.site.models import Site

FEATURE_FLAG = "inquiry"
SNAPSHOT_SCHEMA_VERSION = 1
CONSENT_TEXTS: dict[str, str] = {
    "simulation_confirmation": "notice.simulation_confirmation",
    "transmission_office": "consent.transmission_office",
}


def _require_site(db: Session, project_id: uuid.UUID) -> None:
    exists = db.execute(select(Site.id).where(Site.project_id == project_id)).first()
    if exists is None:
        raise Problem(404, "site_not_found")


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def submit_contact(db: Session, project_id: uuid.UUID, body: ContactIn, locale: Locale) -> ContactOut:
    """Kontaktformular (3.1). Kann wiederholt aufgerufen werden, solange die Adresse unbestätigt ist –
    ein neuer Code ersetzt den vorigen (Tippfehler, abgelaufener Code)."""
    settings = get_settings()
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    _require_site(db, project_id)
    if db.execute(select(Inquiry.id).where(Inquiry.project_id == project_id)).first() is not None:
        raise Problem(409, "inquiry_already_exists")

    email = body.email.strip().lower()
    rate_limit.check_value(
        "inquiry_contact_email", email, settings.inquiry_contact_limit_per_hour_email, 3600
    )

    customer = db.execute(select(Customer).where(Customer.project_id == project_id)).scalar_one_or_none()
    if customer is None:
        customer = Customer(project_id=project_id, created_by="customer")
        db.add(customer)
    customer.name = body.name
    customer.email = email
    customer.phone = body.phone
    customer.desired_start = body.desired_start
    customer.financing_clarified = body.financing_clarified
    customer.lotissement = body.lotissement
    code = _new_code()
    customer.email_code_hash = hash_token(code)
    customer.email_code_expires_at = utcnow() + timedelta(minutes=settings.inquiry_code_ttl_minutes)
    customer.email_code_attempts = 0
    db.flush()

    queue_mail(
        db,
        to=email,
        template="inquiry_code",
        locale=locale,
        params={"code": code, "ttl_minutes": str(settings.inquiry_code_ttl_minutes)},
        project_id=project_id,
        created_by="customer",
    )
    db.commit()
    return ContactOut(code_expires_in_minutes=settings.inquiry_code_ttl_minutes)


def _consent_versions(db: Session, locale: Locale) -> dict[str, ConsentOut]:
    texts = {t.key: t for t in current_texts(db, locale, keys=list(CONSENT_TEXTS.values()))}
    missing = [key for key in CONSENT_TEXTS.values() if key not in texts]
    if missing:
        raise Problem(503, "legal_text_missing", detail=", ".join(missing))
    return {
        kind: ConsentOut(
            kind=kind,
            legal_text_key=key,
            legal_text_version=texts[key].version,
            confirmed_at=utcnow(),
        )
        for kind, key in CONSENT_TEXTS.items()
    }


def _next_number(db: Session) -> str:
    seq = db.execute(select(func.nextval("inquiry_number_seq"))).scalar_one()
    return f"EMP-{utcnow().year}-{seq:06d}"


def _build_snapshot(db: Session, project_id: uuid.UUID, customer: Customer) -> dict[str, Any]:
    site = site_service.load_site(db, project_id)
    rules = rules_service.project_rules(db, project_id)
    envelope = envelope_service.project_envelope(db, project_id)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "site": site.model_dump(mode="json"),
        "rules": rules.model_dump(mode="json"),
        "envelope": envelope.model_dump(mode="json"),
        "lotissement": customer.lotissement,
    }


def confirm_contact(db: Session, project_id: uuid.UUID, body: ConfirmIn, locale: Locale) -> ConfirmOut:
    """Code prüfen, dann Anfrage anlegen (3.1/3.2). Beide Bestätigungen sind Pflicht (3.10)."""
    settings = get_settings()
    if not (body.simulation_confirmation and body.transmission_office):
        raise Problem(400, "consent_required")
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    customer = db.execute(select(Customer).where(Customer.project_id == project_id)).scalar_one_or_none()
    if customer is None or customer.email_code_hash is None:
        raise Problem(409, "inquiry_contact_missing")
    if customer.email_code_attempts >= settings.inquiry_code_max_attempts:
        raise Problem(429, "inquiry_code_too_many_attempts")
    assert customer.email_code_expires_at is not None  # gesetzt zusammen mit email_code_hash
    if utcnow() > customer.email_code_expires_at:
        raise Problem(409, "inquiry_code_expired")
    customer.email_code_attempts += 1
    if hash_token(body.code) != customer.email_code_hash:
        db.commit()
        raise Problem(400, "inquiry_code_invalid")

    consents = _consent_versions(db, locale)
    number = _next_number(db)
    customer.verified_at = utcnow()
    customer.email_code_hash = None
    db.flush()

    snapshot = _build_snapshot(db, project_id, customer)
    inquiry = Inquiry(
        project_id=project_id,
        customer_id=customer.id,
        number=number,
        snapshot=snapshot,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        created_by="customer",
    )
    db.add(inquiry)
    for consent in consents.values():
        db.add(
            Consent(
                project_id=project_id,
                kind=consent.kind,
                legal_text_key=consent.legal_text_key,
                legal_text_version=consent.legal_text_version,
                created_by="customer",
            )
        )
    project.status = "submitted"
    db.flush()
    audit.record(
        db,
        actor_type="customer",
        actor_id=str(project_id),
        action="inquiry.create",
        entity_type="inquiry",
        entity_id=str(inquiry.id),
        after={"number": number},
    )

    envelope_status = snapshot["envelope"]["status"]
    queue_mail(
        db,
        to=settings.office_email,
        template="inquiry_office",
        locale=locale,
        params={
            "number": number,
            "envelope_status": envelope_status,
            "portal_url": f"{settings.public_base_url}/buero/anfragen/{project_id}",
        },
        project_id=project_id,
        created_by="customer",
    )
    queue_mail(
        db,
        to=customer.email,
        template="inquiry_customer_copy",
        locale=locale,
        params={"number": number},
        project_id=project_id,
        created_by="customer",
    )
    db.commit()
    return ConfirmOut(number=number)


def my_inquiry(db: Session, project_id: uuid.UUID) -> MyInquiryOut:
    inquiry = db.execute(select(Inquiry).where(Inquiry.project_id == project_id)).scalar_one_or_none()
    if inquiry is None:
        return MyInquiryOut(exists=False)
    return MyInquiryOut(exists=True, number=inquiry.number, status=inquiry.status)


def export(db: Session, project_id: uuid.UUID) -> ExportOut:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    customer = db.execute(select(Customer).where(Customer.project_id == project_id)).scalar_one_or_none()
    inquiry = db.execute(select(Inquiry).where(Inquiry.project_id == project_id)).scalar_one_or_none()
    consents = list(db.execute(select(Consent).where(Consent.project_id == project_id)).scalars())
    return ExportOut(
        project_id=project_id,
        project_created_at=project.created_at,
        customer=(
            CustomerOut(
                name=customer.name,
                email=customer.email,
                phone=customer.phone,
                desired_start=customer.desired_start,
                financing_clarified=customer.financing_clarified,
                lotissement=customer.lotissement,
            )
            if customer and customer.verified_at
            else None
        ),
        consents=[
            ConsentOut(
                kind=c.kind,
                legal_text_key=c.legal_text_key,
                legal_text_version=c.legal_text_version,
                confirmed_at=c.confirmed_at,
            )
            for c in consents
        ],
        inquiry_number=inquiry.number if inquiry else None,
        inquiry_status=inquiry.status if inquiry else None,
        snapshot=inquiry.snapshot if inquiry else None,
    )


def delete_project(db: Session, project_id: uuid.UUID, actor: str) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    if db.execute(select(Inquiry.id).where(Inquiry.project_id == project_id)).first() is not None:
        raise Problem(409, "deletion_requires_office")
    audit.record(
        db,
        actor_type="customer",
        actor_id=actor,
        action="project.delete",
        entity_type="project",
        entity_id=str(project_id),
    )
    db.delete(project)
    db.commit()


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


def list_inquiries(db: Session, status: str | None, limit: int = 200) -> list[InquiryListItem]:
    query = (
        select(Inquiry, Customer)
        .join(Customer, Customer.id == Inquiry.customer_id)
        .order_by(Inquiry.created_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(Inquiry.status == status)
    rows = db.execute(query).all()
    return [
        InquiryListItem(
            project_id=inquiry.project_id,
            number=inquiry.number,
            status=inquiry.status,
            customer_name=customer.name,
            customer_email=customer.email,
            lotissement=customer.lotissement,
            has_envelope=inquiry.snapshot.get("envelope", {}).get("status") != "unavailable",
            customer_corrections=inquiry.snapshot.get("site", {}).get("customer_corrections", 0),
            created_at=inquiry.created_at,
            updated_at=inquiry.updated_at,
        )
        for inquiry, customer in rows
    ]


def _get_inquiry(db: Session, project_id: uuid.UUID) -> tuple[Inquiry, Customer]:
    row = db.execute(
        select(Inquiry, Customer)
        .join(Customer, Customer.id == Inquiry.customer_id)
        .where(Inquiry.project_id == project_id)
    ).first()
    if row is None:
        raise Problem(404, "not_found")
    inquiry, customer = row
    return inquiry, customer


def inquiry_detail(db: Session, project_id: uuid.UUID) -> InquiryDetailOut:
    inquiry, customer = _get_inquiry(db, project_id)
    consents = list(db.execute(select(Consent).where(Consent.project_id == project_id)).scalars())
    return InquiryDetailOut(
        project_id=project_id,
        number=inquiry.number,
        status=inquiry.status,
        customer=CustomerOut(
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            desired_start=customer.desired_start,
            financing_clarified=customer.financing_clarified,
            lotissement=customer.lotissement,
        ),
        consents=[
            ConsentOut(
                kind=c.kind,
                legal_text_key=c.legal_text_key,
                legal_text_version=c.legal_text_version,
                confirmed_at=c.confirmed_at,
            )
            for c in consents
        ],
        snapshot=inquiry.snapshot,
        snapshot_schema_version=inquiry.snapshot_schema_version,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
    )


def set_status(db: Session, project_id: uuid.UUID, status: str, actor: str) -> InquiryDetailOut:
    inquiry, _customer = _get_inquiry(db, project_id)
    before = inquiry.status
    inquiry.status = status
    inquiry.updated_at = utcnow()
    inquiry.updated_by = actor
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="inquiry.status",
        entity_type="inquiry",
        entity_id=str(inquiry.id),
        before={"status": before},
        after={"status": status},
    )
    db.commit()
    return inquiry_detail(db, project_id)
