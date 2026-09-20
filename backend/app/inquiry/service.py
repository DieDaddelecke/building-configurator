"""Ablauf des Moduls A: Kontakt, E-Mail-Bestätigung, Anfrage mit Snapshot (Plan 3.6,
docs/PLAN_A_ANFRAGE.md 4.2). Prüfung der Simulation selbst läuft über die bestehenden Endpunkte von
G1 (Kanten), G2 (Regel-Overrides) und G3 (Baurahmen) – hier entsteht nur die Anfrage, die sie zusammenfasst.

V (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.8) ergänzt den Vorgang um Fassungen aus dem Konfigurator
(`app.submission`), Nachrichten zwischen Büro und Kunde, neue Zustände und das Zurückziehen.
"""

import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.configuration.models import Configuration
from app.envelope import service as envelope_service
from app.inquiry.access import access_url, customer_locale
from app.inquiry.models import Consent, Customer, Inquiry, InquiryMessage
from app.inquiry.schemas import (
    ConfirmIn,
    ConfirmOut,
    ConsentOut,
    ContactIn,
    ContactOut,
    CustomerOut,
    ExportOut,
    ExportSubmissionOut,
    InquiryDetailOut,
    InquiryListItem,
    MessageOut,
    MyInquiryOut,
    MySubmissionOut,
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
from app.submission import views as submission_views
from app.submission.models import Submission

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
    customer.locale = locale
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


def consent_versions(
    db: Session, locale: Locale, kinds: dict[str, str] = CONSENT_TEXTS
) -> dict[str, ConsentOut]:
    """Aktuelle Version der Rechtstexte je Art der Einwilligung; fehlt einer, `503 legal_text_missing`."""
    texts = {t.key: t for t in current_texts(db, locale, keys=list(kinds.values()))}
    missing = [key for key in kinds.values() if key not in texts]
    if missing:
        raise Problem(503, "legal_text_missing", detail=", ".join(missing))
    return {
        kind: ConsentOut(
            kind=kind,
            legal_text_key=key,
            legal_text_version=texts[key].version,
            confirmed_at=utcnow(),
        )
        for kind, key in kinds.items()
    }


def next_number(db: Session) -> str:
    seq = db.execute(select(func.nextval("inquiry_number_seq"))).scalar_one()
    return f"EMP-{utcnow().year}-{seq:06d}"


def verify_code(db: Session, customer: Customer | None, code: str | None) -> Customer:
    """Code aus dem Kontaktformular prüfen (Plan A 3.2); ein falscher Code zählt als Versuch."""
    settings = get_settings()
    if customer is None or customer.email_code_hash is None:
        raise Problem(409, "inquiry_contact_missing")
    if customer.email_code_attempts >= settings.inquiry_code_max_attempts:
        raise Problem(429, "inquiry_code_too_many_attempts")
    assert customer.email_code_expires_at is not None  # gesetzt zusammen mit email_code_hash
    if utcnow() > customer.email_code_expires_at:
        raise Problem(409, "inquiry_code_expired")
    customer.email_code_attempts += 1
    if code is None or hash_token(code) != customer.email_code_hash:
        db.commit()
        raise Problem(400, "inquiry_code_invalid")
    customer.verified_at = utcnow()
    customer.email_code_hash = None
    return customer


def build_snapshot(db: Session, project_id: uuid.UUID, customer: Customer) -> dict[str, Any]:
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
    customer = verify_code(db, customer, body.code)

    consents = consent_versions(db, locale)
    number = next_number(db)
    db.flush()

    snapshot = build_snapshot(db, project_id, customer)
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
        params={"number": number, "access_url": access_url(project_id)},
        project_id=project_id,
        created_by="customer",
    )
    db.commit()
    return ConfirmOut(number=number)


def _submissions(db: Session, inquiry_id: uuid.UUID) -> list[Submission]:
    """Fassungen eines Vorgangs, jüngste zuerst."""
    query = select(Submission).where(Submission.inquiry_id == inquiry_id).order_by(Submission.sequence.desc())
    return list(db.execute(query).scalars())


def _messages(db: Session, inquiry_id: uuid.UUID) -> list[MessageOut]:
    rows = db.execute(
        select(InquiryMessage)
        .where(InquiryMessage.inquiry_id == inquiry_id)
        .order_by(InquiryMessage.created_at, InquiryMessage.id)
    ).scalars()
    return [MessageOut(id=m.id, author=m.author, body=m.body, created_at=m.created_at) for m in rows]


WITHDRAWABLE = ("neu", "in_bearbeitung", "rueckfrage", "beantwortet")


def my_inquiry(db: Session, project_id: uuid.UUID) -> MyInquiryOut:
    inquiry = db.execute(select(Inquiry).where(Inquiry.project_id == project_id)).scalar_one_or_none()
    if inquiry is None:
        return MyInquiryOut(exists=False, submissions=[], messages=[], can_withdraw=False)
    return MyInquiryOut(
        exists=True,
        number=inquiry.number,
        status=inquiry.status,
        submissions=[
            MySubmissionOut(
                sequence=s.sequence,
                status=s.status,
                created_at=s.created_at,
                deviation_count=s.deviation_count,
                dossier_status=s.dossier_status,
                files=submission_views.files_out(s, pdf_only=True),
            )
            for s in _submissions(db, inquiry.id)
        ],
        messages=_messages(db, inquiry.id),
        can_withdraw=inquiry.status in WITHDRAWABLE,
    )


def own_inquiry(db: Session, project_id: uuid.UUID, *, lock: bool = False) -> tuple[Inquiry, Customer]:
    query = (
        select(Inquiry, Customer)
        .join(Customer, Customer.id == Inquiry.customer_id)
        .where(Inquiry.project_id == project_id)
    )
    if lock:
        query = query.with_for_update(of=Inquiry)
    row = db.execute(query).first()
    if row is None:
        raise Problem(404, "not_found")
    inquiry, customer = row
    return inquiry, customer


def change_status(
    db: Session, inquiry: Inquiry, status: str, actor_type: audit.ActorType, actor: str
) -> None:
    before = inquiry.status
    inquiry.updated_at = utcnow()
    inquiry.updated_by = actor
    if before == status:
        return
    inquiry.status = status
    audit.record(
        db,
        actor_type=actor_type,
        actor_id=actor,
        action="inquiry.status",
        entity_type="inquiry",
        entity_id=str(inquiry.id),
        before={"status": before},
        after={"status": status},
    )


def portal_url(project_id: uuid.UUID) -> str:
    return f"{get_settings().public_base_url}/buero/anfragen/{project_id}"


def customer_message(db: Session, project_id: uuid.UUID, body: str, locale: Locale) -> MyInquiryOut:
    """Nachricht des Kunden (V 3.8): aus `rueckfrage` wird `in_bearbeitung`, Mail an das Büro."""
    inquiry, customer = own_inquiry(db, project_id, lock=True)
    if inquiry.status == "zurueckgezogen":
        raise Problem(409, "inquiry_withdrawn")
    db.add(InquiryMessage(inquiry_id=inquiry.id, author="customer", body=body, created_by="customer"))
    change_status(
        db,
        inquiry,
        "in_bearbeitung" if inquiry.status == "rueckfrage" else inquiry.status,
        "customer",
        str(project_id),
    )
    customer.locale = locale
    queue_mail(
        db,
        to=get_settings().office_email,
        template="message_office",
        locale=locale,
        params={"number": inquiry.number, "body": body, "portal_url": portal_url(project_id)},
        project_id=project_id,
        created_by="customer",
    )
    db.commit()
    return my_inquiry(db, project_id)


def withdraw(db: Session, project_id: uuid.UUID, locale: Locale) -> MyInquiryOut:
    """Der Kunde zieht den Vorgang zurück (V 3.8); gelöscht wird nichts (D6)."""
    inquiry, _customer = own_inquiry(db, project_id, lock=True)
    if inquiry.status not in WITHDRAWABLE:
        raise Problem(409, "inquiry_not_withdrawable", current_status=inquiry.status)
    change_status(db, inquiry, "zurueckgezogen", "customer", str(project_id))
    queue_mail(
        db,
        to=get_settings().office_email,
        template="withdrawn_office",
        locale=locale,
        params={"number": inquiry.number, "portal_url": portal_url(project_id)},
        project_id=project_id,
        created_by="customer",
    )
    db.commit()
    return my_inquiry(db, project_id)


def _consents_out(db: Session, project_id: uuid.UUID) -> list[ConsentOut]:
    rows = db.execute(
        select(Consent).where(Consent.project_id == project_id).order_by(Consent.confirmed_at, Consent.kind)
    ).scalars()
    return [
        ConsentOut(
            kind=c.kind,
            legal_text_key=c.legal_text_key,
            legal_text_version=c.legal_text_version,
            confirmed_at=c.confirmed_at,
        )
        for c in rows
    ]


def _customer_out(customer: Customer) -> CustomerOut:
    return CustomerOut(
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        desired_start=customer.desired_start,
        financing_clarified=customer.financing_clarified,
        lotissement=customer.lotissement,
    )


def export(db: Session, project_id: uuid.UUID) -> ExportOut:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    customer = db.execute(select(Customer).where(Customer.project_id == project_id)).scalar_one_or_none()
    inquiry = db.execute(select(Inquiry).where(Inquiry.project_id == project_id)).scalar_one_or_none()
    submissions = _submissions(db, inquiry.id) if inquiry else []
    return ExportOut(
        project_id=project_id,
        project_created_at=project.created_at,
        customer=_customer_out(customer) if customer and customer.verified_at else None,
        consents=_consents_out(db, project_id),
        inquiry_number=inquiry.number if inquiry else None,
        inquiry_status=inquiry.status if inquiry else None,
        snapshot=inquiry.snapshot if inquiry else None,
        submissions=[
            ExportSubmissionOut(
                sequence=s.sequence,
                status=s.status,
                created_at=s.created_at,
                snapshot=s.snapshot,
                files=[f["name"] for f in s.dossier_files],
            )
            for s in submissions
        ],
        messages=_messages(db, inquiry.id) if inquiry else [],
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
    counts = select(Submission.inquiry_id, func.count().label("n")).group_by(Submission.inquiry_id).subquery()
    current = select(Submission).where(Submission.status == "current").subquery()
    query = (
        select(
            Inquiry,
            Customer,
            counts.c.n,
            current.c.deviation_count,
            current.c.dossier_status,
        )
        .join(Customer, Customer.id == Inquiry.customer_id)
        .outerjoin(counts, counts.c.inquiry_id == Inquiry.id)
        .outerjoin(current, current.c.inquiry_id == Inquiry.id)
        .order_by(Inquiry.updated_at.desc())
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
            submissions=count or 0,
            deviation_count=deviations,
            dossier_status=dossier_status,
            created_at=inquiry.created_at,
            updated_at=inquiry.updated_at,
        )
        for inquiry, customer, count, deviations, dossier_status in rows
    ]


def inquiry_detail(db: Session, project_id: uuid.UUID) -> InquiryDetailOut:
    inquiry, customer = own_inquiry(db, project_id)
    revision = db.execute(
        select(Configuration.revision).where(Configuration.project_id == project_id)
    ).scalar_one_or_none()
    return InquiryDetailOut(
        project_id=project_id,
        number=inquiry.number,
        status=inquiry.status,
        customer=_customer_out(customer),
        consents=_consents_out(db, project_id),
        snapshot=inquiry.snapshot,
        snapshot_schema_version=inquiry.snapshot_schema_version,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
        submissions=[submission_views.staff_out(s) for s in _submissions(db, inquiry.id)],
        messages=_messages(db, inquiry.id),
        configuration_revision=revision,
    )


def set_status(db: Session, project_id: uuid.UUID, status: str, actor: str) -> InquiryDetailOut:
    """Das Büro setzt jeden Zustand außer `zurueckgezogen` (Schema `OfficeStatus`, V 3.8)."""
    inquiry, _customer = own_inquiry(db, project_id, lock=True)
    change_status(db, inquiry, status, "staff", actor)
    db.commit()
    return inquiry_detail(db, project_id)


def office_message(db: Session, project_id: uuid.UUID, body: str, actor: str) -> InquiryDetailOut:
    """Nachricht des Büros (V 3.8): aus `neu` oder `in_bearbeitung` wird `rueckfrage`; Mail an den Kunden
    mit Text und Zugangslink."""
    inquiry, customer = own_inquiry(db, project_id, lock=True)
    db.add(InquiryMessage(inquiry_id=inquiry.id, author="office", body=body, created_by=actor))
    change_status(
        db,
        inquiry,
        "rueckfrage" if inquiry.status in ("neu", "in_bearbeitung") else inquiry.status,
        "staff",
        actor,
    )
    queue_mail(
        db,
        to=customer.email,
        template="message_customer",
        locale=customer_locale(customer),
        params={"number": inquiry.number, "body": body, "access_url": access_url(project_id)},
        project_id=project_id,
        created_by=actor,
    )
    db.commit()
    return inquiry_detail(db, project_id)
