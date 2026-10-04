"""Haustyp aus IFC (docs/PLAN_HAUSMODELL.md 3.5, 3.6; HM3): Upload, Import im Job, Entwurf, Prüfung über
`engine`, Freigabe. Katalogversionen kommen in HM3 nur über die CLI (`house-catalog-import`).

Ablauf einer Templateversion: `draft` (Import und Entwurf) → Prüfen → `reviewed` (Kompatibilität mit der
Katalogversion des Entwurfs bestätigt) → Veröffentlichen (Freigabe durch `catalog_admin`) → `published` →
`retired`. Jede Änderung am Entwurf führt eine geprüfte Version zurück nach `draft`; `rejected` verwirft.

Der Entwurf entsteht immer neu aus dem gelesenen Modell (`raw`), den Angaben des Büros (`decisions`) und der
zuletzt veröffentlichten Katalogversion des Markts (3.6 Nr. 3), ohne die Datei erneut zu lesen. Ergänzt das
Büro im Katalog eine Zonenkategorie, erkennt der nächste Schritt am Entwurf die Zone.
"""

import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from pathlib import PurePosixPath
from typing import Any

import httpx2
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.house import engine
from app.house.contract import HouseCatalog, HouseSourceIfc, HouseTemplate
from app.house.domain.assemble import assemble
from app.house.domain.draft import (
    EMPTY_DECISIONS,
    HouseDraftDecisions,
    HouseImportFinding,
    HouseImportReport,
    HouseImportSummary,
)
from app.house.domain.raw import RawModel
from app.house.ifc_process import IfcReadError, read_ifc
from app.house.models import (
    HouseCatalogCompatibility,
    HouseCatalogRecord,
    HouseCatalogVersion,
    HouseTemplateRecord,
    HouseTemplateVersion,
)
from app.house.schemas import (
    HouseCatalogChoicesOut,
    HouseCatalogVersionOut,
    HouseChoiceOut,
    HouseCompatibilityOut,
    HouseJobOut,
    HouseSlotChoiceOut,
    HouseTemplateSummaryOut,
    HouseTemplateVersionOut,
    HouseTemplateVersionSummaryOut,
)
from app.platform import audit, storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.models import Job, StaffUser
from app.platform.problems import Problem

MARKET = "FR"
IFC_HEADER = b"ISO-10303-21;"
"""Beginn einer IFC-Datei im STEP-Format; IFC-ZIP und ifcXML liest der Import nicht."""
EDITABLE = ("draft", "reviewed")
EMPTY_SUMMARY = HouseImportSummary(
    storeys=0,
    roof_levels=0,
    exterior_walls=0,
    interior_walls=0,
    windows=0,
    doors=0,
    rooms=0,
    zones=0,
    inner_width=None,
    inner_depth=None,
    inner_area=None,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]


def ifc_key(sha256: str) -> str:
    return f"house/ifc/{sha256}.ifc"


def _file_name(name: str) -> str:
    """Nur der Dateiname, auch wenn der Browser einen Windows-Pfad schickt."""
    return PurePosixPath(name.replace("\\", "/")).name.strip()[:255]


def current_catalog_version(db: Session) -> HouseCatalogVersion | None:
    """Zuletzt veröffentlichte Katalogversion des Markts; der Import nimmt sie (3.6 Nr. 3)."""
    return db.scalar(
        select(HouseCatalogVersion)
        .join(HouseCatalogRecord, HouseCatalogRecord.current_version_id == HouseCatalogVersion.id)
        .where(HouseCatalogRecord.market == MARKET)
    )


# --- Upload und Import -----------------------------------------------------------------------------------


def upload_ifc(
    db: Session, slug: str, file_name: str, data: bytes, actor: str
) -> tuple[HouseTemplateVersionOut, bool]:
    """Neue Templateversion aus einer IFC-Datei; der Job `house_ifc_import` liest sie. Dieselbe Datei für
    einen offenen Entwurf ergibt keine neue Version (zweites Wahr: neu angelegt); ist ihr Lesen gescheitert,
    wird sie noch einmal gelesen."""
    name = _file_name(file_name)
    if not name.lower().endswith(".ifc") or not data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").startswith(
        IFC_HEADER
    ):
        raise Problem(422, "ifc_file_invalid")
    catalog_version = current_catalog_version(db)
    if catalog_version is None:
        raise Problem(409, "house_catalog_missing")
    sha256 = hashlib.sha256(data).hexdigest()
    # Vor jeder Sperre ablegen: Der Schlüssel ist die Prüfsumme, doppeltes Ablegen schadet nicht
    storage.put_bytes(ifc_key(sha256), data, "application/x-step")

    db.execute(
        insert(HouseTemplateRecord)
        .values(id=uuid.uuid4(), slug=slug, created_by=actor)
        .on_conflict_do_nothing(index_elements=["slug"])
    )
    record = db.execute(
        select(HouseTemplateRecord).where(HouseTemplateRecord.slug == slug).with_for_update()
    ).scalar_one()
    existing = db.scalars(
        select(HouseTemplateVersion)
        .where(
            HouseTemplateVersion.template_id == record.id,
            HouseTemplateVersion.ifc_sha256 == sha256,
            HouseTemplateVersion.status.in_(EDITABLE),
        )
        .order_by(HouseTemplateVersion.version.desc())
    ).first()
    if existing is not None:
        if existing.raw is None and existing.report is not None:
            existing.report = None
            existing.job_id = _enqueue_import(db, existing, actor, retry=True)
        db.commit()
        return _version_out(db, record, existing), False

    number = (
        db.scalar(
            select(func.max(HouseTemplateVersion.version)).where(
                HouseTemplateVersion.template_id == record.id
            )
        )
        or 0
    ) + 1
    version = HouseTemplateVersion(
        template_id=record.id,
        version=number,
        status="draft",
        catalog_version_id=catalog_version.id,
        ifc_file_name=name,
        ifc_sha256=sha256,
        ifc_key=ifc_key(sha256),
        ifc_size_bytes=len(data),
        decisions=EMPTY_DECISIONS.model_dump(mode="json"),
        created_by=actor,
    )
    db.add(version)
    db.flush()
    version.job_id = _enqueue_import(db, version, actor, retry=False)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="house_template.upload",
        entity_type="house_template_version",
        entity_id=str(version.id),
        after={"slug": slug, "version": number, "file_name": name, "sha256": sha256, "size_bytes": len(data)},
    )
    db.commit()
    return _version_out(db, record, version), True


def _enqueue_import(db: Session, version: HouseTemplateVersion, actor: str, *, retry: bool) -> uuid.UUID:
    import app.house.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    suffix = f":{utcnow():%Y%m%d%H%M%S%f}" if retry else ""
    return enqueue(
        db,
        "house_ifc_import",
        {"version_id": str(version.id)},
        idempotency_key=f"house_ifc_import:{version.id}{suffix}",
        created_by=actor,
    )


def _failure_report(code: str, detail: str | None) -> HouseImportReport:
    params: dict[str, str | float | None] = {"detail": detail[:300]} if detail else {}
    finding = HouseImportFinding(severity="error", code=code, element_id=None, ifc_guid=None, params=params)
    return HouseImportReport(
        findings=[finding], zones=[], openings=[], summary=EMPTY_SUMMARY, publishable=False
    )


def run_import(sessions: SessionFactory, settings: Settings, version_id: uuid.UUID) -> dict[str, Any]:
    """Job `house_ifc_import`: Datei im Kindprozess lesen (E-HM-19), ohne Sperre; danach Entwurf und Bericht
    unter Sperre schreiben. Eine unlesbare Datei ist ein Ergebnis (Bericht mit Fehler), kein Fehlschlag."""
    with sessions() as db:
        version = db.get(HouseTemplateVersion, version_id)
        if version is None or version.status != "draft" or version.report is not None:
            return {"status": "skipped"}
        path = storage.path_for(version.ifc_key)
    raw: RawModel | None = None
    failure: IfcReadError | None = None
    try:
        raw = read_ifc(
            path,
            timeout_seconds=settings.house_ifc_timeout_seconds,
            max_memory_bytes=settings.house_ifc_max_memory_mb * 1024 * 1024,
        )
    except IfcReadError as exc:
        failure = exc

    with sessions() as db:
        version = db.execute(
            select(HouseTemplateVersion).where(HouseTemplateVersion.id == version_id).with_for_update()
        ).scalar_one_or_none()
        if version is None or version.status != "draft" or version.report is not None:
            return {"status": "skipped"}
        if raw is None:
            assert failure is not None
            version.report = _failure_report(failure.code, failure.detail).model_dump(mode="json")
            result: dict[str, Any] = {"status": "unreadable", "code": failure.code}
        else:
            version.raw = raw.model_dump(mode="json")
            record = db.get_one(HouseTemplateRecord, version.template_id)
            _, report, _ = _assemble(db, record, version)
            result = {"status": "imported", "publishable": report.publishable}
        db.commit()
    return result


def mark_import_failed(sessions: SessionFactory, version_id: uuid.UUID, error: str) -> None:
    """Letzter Versuch des Jobs gescheitert: Der Bericht sagt es, statt dass der Import ewig läuft."""
    with sessions() as db:
        version = db.execute(
            select(HouseTemplateVersion).where(HouseTemplateVersion.id == version_id).with_for_update()
        ).scalar_one_or_none()
        if version is None or version.status != "draft" or version.report is not None:
            return
        version.report = _failure_report("import_failed", error).model_dump(mode="json")
        db.commit()


def _assemble(
    db: Session, record: HouseTemplateRecord, version: HouseTemplateVersion
) -> tuple[HouseTemplate | None, HouseImportReport, HouseCatalog]:
    """Entwurf und Bericht neu aus `raw` und `decisions`, mit der zuletzt veröffentlichten Katalogversion."""
    catalog_version = current_catalog_version(db) or db.get_one(
        HouseCatalogVersion, version.catalog_version_id
    )
    catalog = HouseCatalog.model_validate(catalog_version.document)
    raw = RawModel.model_validate(version.raw)
    source = HouseSourceIfc(
        file_name=version.ifc_file_name,
        sha256=version.ifc_sha256,
        ifc_schema=raw.ifc_schema[:20],
        imported_at=version.created_at,
    )
    name = PurePosixPath(version.ifc_file_name).stem or record.slug
    template, report = assemble(
        raw, HouseDraftDecisions.model_validate(version.decisions), catalog, source, record.slug, name
    )
    version.catalog_version_id = catalog_version.id
    version.document = template.model_dump(mode="json") if template is not None else None
    version.report = report.model_dump(mode="json")
    return template, report, catalog


# --- Entwurf, Prüfung, Freigabe ---------------------------------------------------------------------------


def _version(
    db: Session, slug: str, number: int, *, lock: bool = False
) -> tuple[HouseTemplateRecord, HouseTemplateVersion]:
    """Haustyp und Version; mit `lock` beide gesperrt (Version ändern, aktuelle Version umsetzen)."""
    query = (
        select(HouseTemplateRecord, HouseTemplateVersion)
        .join(HouseTemplateVersion, HouseTemplateVersion.template_id == HouseTemplateRecord.id)
        .where(HouseTemplateRecord.slug == slug, HouseTemplateVersion.version == number)
    )
    row = db.execute(query.with_for_update() if lock else query).first()
    if row is None:
        raise Problem(404, "house_version_not_found")
    return row[0], row[1]


def _require_editable(version: HouseTemplateVersion) -> None:
    if version.status not in EDITABLE:
        raise Problem(409, "house_version_not_editable", version_status=version.status)
    if version.raw is None:
        raise Problem(409, "house_import_incomplete")


def _back_to_draft(db: Session, version: HouseTemplateVersion) -> None:
    """Geänderter Entwurf: Ein Prüfbefund gilt nicht mehr."""
    if version.status == "reviewed":
        version.status, version.reviewed_at, version.reviewed_by = "draft", None, None
    db.execute(
        delete(HouseCatalogCompatibility).where(
            HouseCatalogCompatibility.template_version_id == version.id,
            HouseCatalogCompatibility.approved_at.is_(None),
        )
    )


def _audit(db: Session, actor: str, action: str, target: HouseTemplateVersion, **after: Any) -> None:
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action=f"house_template.{action}",
        entity_type="house_template_version",
        entity_id=str(target.id),
        after=after,
    )


def get_version(db: Session, slug: str, number: int) -> HouseTemplateVersionOut:
    record, version = _version(db, slug, number)
    return _version_out(db, record, version)


def set_decisions(
    db: Session, slug: str, number: int, decisions: HouseDraftDecisions, actor: str
) -> HouseTemplateVersionOut:
    """Angaben des Büros ersetzen (3.6 Nr. 5); Entwurf und Bericht entstehen neu."""
    record, version = _version(db, slug, number, lock=True)
    _require_editable(version)
    before = version.decisions
    after = decisions.model_dump(mode="json")
    if after != before:
        version.decisions = after
        _back_to_draft(db, version)
        _assemble(db, record, version)
        audit.record(
            db,
            actor_type="staff",
            actor_id=actor,
            action="house_template.decisions",
            entity_type="house_template_version",
            entity_id=str(version.id),
            before=before,
            after=after,
        )
        db.commit()
    return _version_out(db, record, version)


def check_version(
    db: Session, client: httpx2.Client, slug: str, number: int, actor: str
) -> HouseTemplateVersionOut:
    """Entwurf ohne offenen Punkt gegen die Katalogversion prüfen (P 2.1 Nr. 5): kompatibel → `reviewed`."""
    record, version = _version(db, slug, number, lock=True)
    _require_editable(version)
    template, report, catalog = _assemble(db, record, version)
    _back_to_draft(db, version)
    if template is None or not report.publishable:
        db.commit()
        raise Problem(409, "house_draft_open")
    result = engine.compatibility(client, template, catalog)
    db.add(
        HouseCatalogCompatibility(
            template_version_id=version.id,
            catalog_version_id=version.catalog_version_id,
            domain_version=result.domain_version[:40],
            supported=result.supported,
            issues=[issue.model_dump(mode="json") for issue in result.issues],
            created_by=actor,
        )
    )
    if result.supported:
        version.status, version.reviewed_at, version.reviewed_by = "reviewed", utcnow(), actor
    _audit(db, actor, "check", version, supported=result.supported, issues=len(result.issues))
    db.commit()
    return _version_out(db, record, version)


def publish_version(db: Session, slug: str, number: int, actor: str) -> HouseTemplateVersionOut:
    """Freigabe: Der Prüfbefund zur aktuellen Katalogversion wird bestätigt, die Version wird die aktuelle
    des Haustyps und ist danach unveränderlich (L4)."""
    record, version = _version(db, slug, number, lock=True)
    if version.status == "published":
        return _version_out(db, record, version)
    if version.status != "reviewed":
        raise Problem(409, "house_version_not_reviewed")
    current = current_catalog_version(db)
    if current is None or current.id != version.catalog_version_id:
        raise Problem(409, "house_catalog_changed")
    compatibility = db.scalar(
        select(HouseCatalogCompatibility)
        .where(
            HouseCatalogCompatibility.template_version_id == version.id,
            HouseCatalogCompatibility.catalog_version_id == current.id,
        )
        .with_for_update()
    )
    if compatibility is None or not compatibility.supported:
        raise Problem(409, "house_version_not_reviewed")
    now = utcnow()
    compatibility.approved_at, compatibility.approved_by = now, actor
    version.status, version.published_at, version.published_by = "published", now, actor
    record.current_version_id = version.id
    _audit(db, actor, "publish", version, slug=slug, version=number, catalog_version=current.version)
    db.commit()
    return _version_out(db, record, version)


def reject_version(db: Session, slug: str, number: int, actor: str) -> HouseTemplateVersionOut:
    record, version = _version(db, slug, number, lock=True)
    if version.status == "rejected":
        return _version_out(db, record, version)
    if version.status not in EDITABLE:
        raise Problem(409, "house_version_not_editable", version_status=version.status)
    version.status, version.rejected_at, version.rejected_by = "rejected", utcnow(), actor
    _audit(db, actor, "reject", version, slug=slug, version=number)
    db.commit()
    return _version_out(db, record, version)


def retire_version(db: Session, slug: str, number: int, actor: str) -> HouseTemplateVersionOut:
    """Nicht mehr für neue Konfigurationen; aktuell wird die neueste andere veröffentlichte Version."""
    record, version = _version(db, slug, number, lock=True)
    if version.status == "retired":
        return _version_out(db, record, version)
    if version.status != "published":
        raise Problem(409, "house_version_not_published")
    version.status, version.retired_at, version.retired_by = "retired", utcnow(), actor
    db.flush()
    if record.current_version_id == version.id:
        record.current_version_id = db.scalar(
            select(HouseTemplateVersion.id)
            .where(HouseTemplateVersion.template_id == record.id, HouseTemplateVersion.status == "published")
            .order_by(HouseTemplateVersion.version.desc())
            .limit(1)
        )
    _audit(db, actor, "retire", version, slug=slug, version=number)
    db.commit()
    return _version_out(db, record, version)


# --- Ausgaben ---------------------------------------------------------------------------------------------


def list_templates(db: Session) -> list[HouseTemplateSummaryOut]:
    """Haustypen mit ihren Versionen, ohne die großen Dokumente zu laden."""
    rows = db.execute(
        select(
            HouseTemplateVersion.id,
            HouseTemplateVersion.template_id,
            HouseTemplateVersion.version,
            HouseTemplateVersion.status,
            HouseTemplateVersion.ifc_file_name,
            HouseTemplateVersion.created_at,
            HouseTemplateVersion.created_by,
            HouseTemplateVersion.report.is_(None).label("importing"),
            HouseTemplateVersion.report["publishable"].as_boolean().label("publishable"),
            HouseTemplateVersion.document["name"].label("name"),
        ).order_by(HouseTemplateVersion.version.desc())
    ).all()
    by_template: defaultdict[uuid.UUID, list[Any]] = defaultdict(list)
    for row in rows:
        by_template[row.template_id].append(row)
    result = []
    for record in db.scalars(select(HouseTemplateRecord).order_by(HouseTemplateRecord.slug)):
        versions = by_template[record.id]
        current = next((v for v in versions if v.id == record.current_version_id), None)
        named = current or next((v for v in versions if v.name is not None), None)
        result.append(
            HouseTemplateSummaryOut(
                slug=record.slug,
                name=named.name if named is not None else None,
                current_version=current.version if current is not None else None,
                versions=[
                    HouseTemplateVersionSummaryOut(
                        version=v.version,
                        status=v.status,
                        ifc_file_name=v.ifc_file_name,
                        created_at=v.created_at,
                        created_by=v.created_by,
                        importing=v.importing and v.status == "draft",
                        publishable=v.publishable,
                    )
                    for v in versions
                ],
            )
        )
    return result


def _choices(catalog_version: HouseCatalogVersion, current: bool) -> HouseCatalogChoicesOut:
    catalog = HouseCatalog.model_validate(catalog_version.document)
    values: defaultdict[str, list[HouseChoiceOut]] = defaultdict(list)
    for value in sorted(catalog.option_values, key=lambda v: v.sort_order):
        values[value.slot_id].append(HouseChoiceOut(id=value.id, name=value.name))
    return HouseCatalogChoicesOut(
        version=catalog_version.version,
        current=current,
        room_types=[HouseChoiceOut(id=t.id, name=t.name) for t in catalog.room_types],
        slots=[
            HouseSlotChoiceOut(id=s.id, category=s.category, name=s.name, values=values[s.id])
            for s in sorted(catalog.slots, key=lambda s: s.sort_order)
        ],
    )


def _people(db: Session, actors: Iterable[str | None]) -> dict[str, str]:
    """Wer hochgeladen, geprüft, freigegeben hat: Konto-ID → Anzeigename oder E-Mail (Akteure sind Konto-IDs,
    außer `cli`)."""
    ids: set[uuid.UUID] = set()
    for actor in actors:
        try:
            ids.add(uuid.UUID(actor or ""))
        except ValueError:
            continue
    if not ids:
        return {}
    rows = db.execute(
        select(StaffUser.id, StaffUser.display_name, StaffUser.email).where(StaffUser.id.in_(ids))
    )
    return {str(row.id): row.display_name or row.email for row in rows}


def _version_out(
    db: Session, record: HouseTemplateRecord, version: HouseTemplateVersion
) -> HouseTemplateVersionOut:
    catalog_version = db.get_one(HouseCatalogVersion, version.catalog_version_id)
    current = current_catalog_version(db)
    compatibility = db.scalar(
        select(HouseCatalogCompatibility).where(
            HouseCatalogCompatibility.template_version_id == version.id,
            HouseCatalogCompatibility.catalog_version_id == version.catalog_version_id,
        )
    )
    job = db.get(Job, version.job_id) if version.job_id is not None else None
    actors = [
        version.created_by,
        version.reviewed_by,
        version.published_by,
        version.rejected_by,
        version.retired_by,
        *((compatibility.created_by, compatibility.approved_by) if compatibility is not None else ()),
    ]
    return HouseTemplateVersionOut(
        people=_people(db, actors),
        slug=record.slug,
        version=version.version,
        status=version.status,
        current=record.current_version_id == version.id,
        ifc_file_name=version.ifc_file_name,
        ifc_sha256=version.ifc_sha256,
        ifc_size_bytes=version.ifc_size_bytes,
        created_at=version.created_at,
        created_by=version.created_by,
        reviewed_at=version.reviewed_at,
        reviewed_by=version.reviewed_by,
        published_at=version.published_at,
        published_by=version.published_by,
        rejected_at=version.rejected_at,
        rejected_by=version.rejected_by,
        retired_at=version.retired_at,
        retired_by=version.retired_by,
        job=(
            HouseJobOut(status=job.status, attempts=job.attempts, max_attempts=job.max_attempts)
            if job is not None
            else None
        ),
        decisions=HouseDraftDecisions.model_validate(version.decisions),
        template=HouseTemplate.model_validate(version.document) if version.document is not None else None,
        report=HouseImportReport.model_validate(version.report) if version.report is not None else None,
        catalog=_choices(catalog_version, current is not None and current.id == catalog_version.id),
        compatibility=(
            HouseCompatibilityOut(
                catalog_version=catalog_version.version,
                domain_version=compatibility.domain_version,
                supported=compatibility.supported,
                issues=compatibility.issues,
                checked_at=compatibility.created_at,
                checked_by=compatibility.created_by,
                approved_at=compatibility.approved_at,
                approved_by=compatibility.approved_by,
            )
            if compatibility is not None
            else None
        ),
    )


# --- Katalog -----------------------------------------------------------------------------------------------


def list_catalog_versions(db: Session) -> list[HouseCatalogVersionOut]:
    document = HouseCatalogVersion.document
    rows = db.execute(
        select(
            HouseCatalogVersion,
            HouseCatalogRecord.market,
            HouseCatalogRecord.current_version_id,
            func.jsonb_array_length(document["room_types"]).label("room_types"),
            func.jsonb_array_length(document["slots"]).label("slots"),
            func.jsonb_array_length(document["option_values"]).label("option_values"),
        )
        .join(HouseCatalogRecord, HouseCatalogRecord.id == HouseCatalogVersion.catalog_id)
        .order_by(HouseCatalogRecord.market, HouseCatalogVersion.version.desc())
    ).all()
    return [
        HouseCatalogVersionOut(
            market=row.market,
            version=row.HouseCatalogVersion.version,
            status=row.HouseCatalogVersion.status,
            current=row.current_version_id == row.HouseCatalogVersion.id,
            sha256=row.HouseCatalogVersion.sha256,
            source=row.HouseCatalogVersion.source,
            created_at=row.HouseCatalogVersion.created_at,
            created_by=row.HouseCatalogVersion.created_by,
            published_at=row.HouseCatalogVersion.published_at,
            published_by=row.HouseCatalogVersion.published_by,
            room_types=row.room_types,
            slots=row.slots,
            option_values=row.option_values,
        )
        for row in rows
    ]


def catalog_sha256(catalog: HouseCatalog) -> str:
    """Prüfsumme des Dokuments in fester Form: Schlüssel sortiert, ohne Leerraum."""
    text = json.dumps(
        catalog.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def import_catalog(
    db: Session, document: Any, *, source: str, publish: bool, actor: str = "cli"
) -> tuple[HouseCatalogVersion, list[str]]:
    """Katalogversion aus einem Dokument (HM3: Demo-Katalog per CLI). Dasselbe Dokument ergibt keine neue
    Version; `publish` macht es zur aktuellen Version des Markts. Hebt `ValidationError` bei einem
    ungültigen Dokument. Liefert die Version und was geschah (`created`, `published`)."""
    catalog = HouseCatalog.model_validate(document)
    sha256 = catalog_sha256(catalog)
    db.execute(
        insert(HouseCatalogRecord)
        .values(id=uuid.uuid4(), market=catalog.market, created_by=actor)
        .on_conflict_do_nothing(index_elements=["market"])
    )
    record = db.execute(
        select(HouseCatalogRecord).where(HouseCatalogRecord.market == catalog.market).with_for_update()
    ).scalar_one()
    version = db.scalars(
        select(HouseCatalogVersion)
        .where(
            HouseCatalogVersion.catalog_id == record.id,
            HouseCatalogVersion.sha256 == sha256,
            HouseCatalogVersion.status.in_(("draft", "published")),
        )
        .order_by(HouseCatalogVersion.version.desc())
    ).first()
    done: list[str] = []
    if version is None:
        number = (
            db.scalar(
                select(func.max(HouseCatalogVersion.version)).where(
                    HouseCatalogVersion.catalog_id == record.id
                )
            )
            or 0
        ) + 1
        version = HouseCatalogVersion(
            catalog_id=record.id,
            version=number,
            status="draft",
            document=catalog.model_dump(mode="json"),
            sha256=sha256,
            source=source[:300],
            created_by=actor,
        )
        db.add(version)
        db.flush()
        done.append("created")
    if publish and record.current_version_id != version.id:
        if version.status == "draft":
            version.status, version.published_at, version.published_by = "published", utcnow(), actor
        record.current_version_id = version.id
        done.append("published")
    if done:
        audit.record(
            db,
            actor_type="system",
            actor_id=actor,
            action="house_catalog.import",
            entity_type="house_catalog_version",
            entity_id=str(version.id),
            after={"market": catalog.market, "version": version.version, "sha256": sha256, "done": done},
        )
    db.commit()
    return version, done
