"""Übergabe des Vorentwurfs (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.2–3.7).

Der Kunde übergibt, was er zuletzt gesehen hat: Der Server rechnet neu (derselbe Code wie
`GET …/configuration`), vergleicht den Prüfstempel und legt erst dann eine Fassung an. Vorgang, Kontakt und
Einwilligungen kommen aus Modul A (`app.inquiry.service`); diese Datei baut die Fassung mit Snapshot und stößt
das Dossier an.
"""

import hashlib
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.configuration import review as review_rules
from app.configuration import service as configuration_service
from app.configuration.domain import ENGINE_VERSION
from app.configuration.schemas import CheckOut, ConfigurationOut
from app.envelope import service as envelope_service
from app.inquiry import service as inquiry_service
from app.inquiry.access import access_url
from app.inquiry.models import Consent, Customer, Inquiry
from app.inquiry.schemas import ConsentOut, InquiryDetailOut
from app.platform import audit, storage
from app.platform.db import utcnow
from app.platform.i18n import Locale
from app.platform.jobs import enqueue
from app.platform.mail import queue_mail
from app.platform.models import Project
from app.platform.problems import Problem
from app.rules import service as rules_service
from app.site import service as site_service
from app.submission.dossier import DOSSIER_VERSION
from app.submission.dossier import format as fmt
from app.submission.models import Submission
from app.submission.schemas import SubmitIn, SubmitOut

FEATURE_FLAG = "submission"
SNAPSHOT_SCHEMA_VERSION = 2
CONSENT_TEXTS: dict[str, str] = {
    "design_confirmation": "notice.design_confirmation",
    "transmission_design": "consent.transmission_design",
}


def _locked_project(db: Session, project_id: uuid.UUID) -> Project:
    """Sperre auf der Projektzeile: gleichzeitige Übergaben laufen nacheinander (Doppelklick, V 3.2)."""
    project = db.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise Problem(404, "not_found")
    return project


def _missing(review: configuration_service.DesignReview) -> list[str]:
    out = review.out
    missing = []
    if out.type is None:
        missing.append("type")
    if out.placement is None:
        missing.append("placement")
    if review.lines_offered and (out.selection is None or out.selection.package_slug is None):
        missing.append("package")
    return missing


def _current(db: Session, inquiry_id: uuid.UUID) -> Submission | None:
    return db.execute(
        select(Submission).where(Submission.inquiry_id == inquiry_id, Submission.status == "current")
    ).scalar_one_or_none()


def submit(db: Session, project_id: uuid.UUID, body: SubmitIn, locale: Locale) -> SubmitOut:
    """Vorentwurf übergeben (V 3.2). Reihenfolge der Prüfungen: Bestätigungen, Vollständigkeit, Stempel,
    Abweichungen, erst dann der Code – eine geänderte Auswertung verbraucht keinen Code (Plan V 9.1 Nr. 3)."""
    if not (body.design_confirmation and body.transmission_design):
        raise Problem(400, "consent_required")
    project = _locked_project(db, project_id)
    review = configuration_service.design_review(db, project_id)
    missing = _missing(review)
    if missing:
        raise Problem(409, "submission_incomplete", missing=missing)
    out = review.out
    stamp = out.review_stamp
    assert stamp is not None  # mit Typ immer gesetzt
    if body.review_stamp != stamp:
        raise Problem(
            409, "review_changed", changes=review_rules.changes(body.review_stamp, stamp), review_stamp=stamp
        )

    inquiry = db.execute(select(Inquiry).where(Inquiry.project_id == project_id)).scalar_one_or_none()
    current = _current(db, inquiry.id) if inquiry else None
    if inquiry is not None and current is not None and current.review_stamp == stamp:
        return SubmitOut(number=inquiry.number, sequence=current.sequence)

    deviations = review_rules.deviations(out)
    if deviations and not body.deviations_acknowledged:
        raise Problem(
            409, "deviations_not_acknowledged", checks=[c.model_dump(mode="json") for c in deviations]
        )

    customer = db.execute(select(Customer).where(Customer.project_id == project_id)).scalar_one_or_none()
    if inquiry is None:
        customer = inquiry_service.verify_code(db, customer, body.code)
    assert customer is not None  # ein Vorgang hat immer einen bestätigten Kunden
    consents = inquiry_service.consent_versions(db, locale, CONSENT_TEXTS)
    customer.locale = locale

    if inquiry is None:
        inquiry = Inquiry(
            project_id=project_id,
            customer_id=customer.id,
            number=inquiry_service.next_number(db),
            snapshot=inquiry_service.build_snapshot(db, project_id, customer),
            snapshot_schema_version=inquiry_service.SNAPSHOT_SCHEMA_VERSION,
            created_by="customer",
        )
        db.add(inquiry)
        db.flush()
        audit.record(
            db,
            actor_type="customer",
            actor_id=str(project_id),
            action="inquiry.create",
            entity_type="inquiry",
            entity_id=str(inquiry.id),
            after={"number": inquiry.number, "via": "submission"},
        )

    sequence = (
        db.execute(
            select(func.max(Submission.sequence)).where(Submission.inquiry_id == inquiry.id)
        ).scalar_one_or_none()
        or 0
    ) + 1
    if current is not None:
        # Vor dem Einfügen: Der Teilindex erlaubt nur eine aktuelle Fassung je Vorgang
        current.status = "superseded"
        current.updated_at = utcnow()
        db.flush()

    open_points = review_rules.open_points(out)
    snapshot = build_snapshot(
        db,
        project_id,
        number=inquiry.number,
        sequence=sequence,
        locale=locale,
        customer=customer,
        consents=list(consents.values()),
        review=review,
        deviations=deviations,
        acknowledged=bool(deviations) and body.deviations_acknowledged,
        open_points=open_points,
    )
    row = Submission(
        project_id=project_id,
        inquiry_id=inquiry.id,
        sequence=sequence,
        status="current",
        snapshot=snapshot,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        configuration_revision=out.revision,
        review_stamp=stamp,
        deviations_acknowledged=bool(deviations) and body.deviations_acknowledged,
        deviation_count=len(deviations),
        open_points=open_points,
        supersedes_id=current.id if current else None,
        created_by="customer",
    )
    db.add(row)
    db.flush()
    for consent in consents.values():
        db.add(
            Consent(
                project_id=project_id,
                submission_id=row.id,
                kind=consent.kind,
                legal_text_key=consent.legal_text_key,
                legal_text_version=consent.legal_text_version,
                created_by="customer",
            )
        )
    inquiry_service.change_status(db, inquiry, "neu", "customer", str(project_id))
    project.status = "submitted"
    audit.record(
        db,
        actor_type="customer",
        actor_id=str(project_id),
        action="submission.create",
        entity_type="submission",
        entity_id=str(row.id),
        after={"number": inquiry.number, "sequence": sequence, "deviations": len(deviations)},
    )
    enqueue(
        db,
        "dossier_generate",
        {"submission_id": str(row.id)},
        idempotency_key=f"dossier:{row.id}",
        project_id=project_id,
        created_by="customer",
    )
    _queue_mails(db, project_id, inquiry, customer, row, out, locale)
    db.commit()
    return SubmitOut(number=inquiry.number, sequence=sequence)


def _queue_mails(
    db: Session,
    project_id: uuid.UUID,
    inquiry: Inquiry,
    customer: Customer,
    row: Submission,
    out: ConfigurationOut,
    locale: Locale,
) -> None:
    settings = get_settings()
    catalog = row.snapshot["catalog"]
    package = catalog.get("package") or {}
    queue_mail(
        db,
        to=settings.office_email,
        template="submission_office",
        locale=locale,
        params={
            "number": inquiry.number,
            "sequence": str(row.sequence),
            "parcels": fmt.parcels(row.snapshot.get("site") or {}),
            "type": (catalog.get("type") or {}).get("name") or "–",
            "package": fmt.label(package, locale) or "–",
            "costs": fmt.costs_text(out.costs.model_dump(mode="json") if out.costs else None, locale),
            "deviations": str(row.deviation_count),
            "open_points": str(row.open_points),
            "portal_url": inquiry_service.portal_url(project_id),
        },
        project_id=project_id,
        created_by="customer",
    )
    queue_mail(
        db,
        to=customer.email,
        template="submission_customer",
        locale=locale,
        params={
            "number": inquiry.number,
            "sequence": str(row.sequence),
            "access_url": access_url(project_id),
        },
        project_id=project_id,
        created_by="customer",
    )


def build_snapshot(
    db: Session,
    project_id: uuid.UUID,
    *,
    number: str,
    sequence: int,
    locale: Locale,
    customer: Customer,
    consents: list[ConsentOut],
    review: configuration_service.DesignReview,
    deviations: list[CheckOut],
    acknowledged: bool,
    open_points: int,
) -> dict[str, Any]:
    """Selbsttragender Stand der Fassung (V 3.6): Das Dossier entsteht allein daraus."""
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "number": number,
        "sequence": sequence,
        "submitted_at": utcnow().isoformat(),
        "locale": locale,
        "customer": {
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "desired_start": customer.desired_start,
            "financing_clarified": customer.financing_clarified,
            "lotissement": customer.lotissement,
        },
        "consents": [c.model_dump(mode="json") for c in consents],
        "site": site_service.load_site(db, project_id).model_dump(mode="json"),
        "rules": rules_service.project_rules(db, project_id).model_dump(mode="json"),
        "envelope": envelope_service.project_envelope(db, project_id).model_dump(mode="json"),
        "configuration": review.out.model_dump(mode="json"),
        "catalog": review.catalog,
        "review_stamp": review.out.review_stamp,
        "deviations": [c.model_dump(mode="json") for c in deviations],
        "deviations_acknowledged": acknowledged,
        "open_points": open_points,
        "engine": {"configuration": ENGINE_VERSION, "dossier": DOSSIER_VERSION},
    }


# ---------------------------------------------------------------------------
# Dateien und Dossier
# ---------------------------------------------------------------------------


def _submission(db: Session, project_id: uuid.UUID, sequence: int) -> Submission:
    row = db.execute(
        select(Submission).where(Submission.project_id == project_id, Submission.sequence == sequence)
    ).scalar_one_or_none()
    if row is None:
        raise Problem(404, "not_found")
    return row


def file_bytes(
    db: Session, project_id: uuid.UUID, sequence: int, name: str, *, pdf_only: bool
) -> tuple[bytes, str]:
    """Datei des Dossiers aus dem Objektspeicher; der Kunde bekommt nur die PDFs (V 3.7)."""
    row = _submission(db, project_id, sequence)
    if row.dossier_status != "ready":
        raise Problem(409, "dossier_not_ready", dossier_status=row.dossier_status)
    entry = next((f for f in row.dossier_files if f["name"] == name), None)
    if entry is None or (pdf_only and entry["kind"] != "pdf"):
        raise Problem(404, "file_not_found")
    return storage.get_bytes(entry["storage_key"]), entry["content_type"]


def regenerate(db: Session, project_id: uuid.UUID, sequence: int, actor: str) -> InquiryDetailOut:
    """Dossier nach endgültigem Fehlschlag neu erzeugen (V 3.7); eigener Idempotenzschlüssel je Auftrag,
    sonst gäbe `enqueue` den gescheiterten Job zurück (Plan V 9.1 Nr. 11)."""
    row = _submission(db, project_id, sequence)
    if row.dossier_status != "failed":
        raise Problem(409, "dossier_not_failed", dossier_status=row.dossier_status)
    row.dossier_status = "pending"
    row.dossier_error = None
    row.updated_at = utcnow()
    enqueue(
        db,
        "dossier_generate",
        {"submission_id": str(row.id)},
        idempotency_key=f"dossier:{row.id}:{utcnow().timestamp()}",
        project_id=project_id,
        created_by=actor,
    )
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="submission.dossier_regenerate",
        entity_type="submission",
        entity_id=str(row.id),
    )
    db.commit()
    return inquiry_service.inquiry_detail(db, project_id)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
