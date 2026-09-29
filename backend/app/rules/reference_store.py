"""Referenzlisten pflegen und Auswertungen daran messen (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10, VA03, VA10).

Jede Änderung steht im Audit-Log. Einträge prüft dieselbe Funktion wie die Dateien
(`domain.reference.parse_entries`), sodass Import, Formular und Datei dieselben Regeln haben.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.audit import ActorType
from app.platform.db import utcnow
from app.platform.problems import Problem
from app.rules import reference
from app.rules.domain.reference import FoundRule, ReferenceEntry, ReferenceProblem, measure, parse_entries
from app.rules.models import LandUsePlan, RegulationChapter, Rule, RuleSet, SourceFile
from app.rules.reference_models import ReferenceEntry as EntryRow
from app.rules.reference_models import ReferenceList as ListRow
from app.rules.schemas import (
    FoundRuleOut,
    MeasuredEntryOut,
    ReferenceCandidateOut,
    ReferenceEntryIn,
    ReferenceEntryOut,
    ReferenceListDetailOut,
    ReferenceListIn,
    ReferenceListOut,
    ReferenceListPatch,
    ReferenceMeasurementOut,
    ReferenceSummaryOut,
)


def _entry_domain(row: EntryRow) -> ReferenceEntry:
    return ReferenceEntry(
        row.kind, row.building_kind, row.expected, dict(row.params or {}), row.page, row.quote
    )


def _checked(items: list[dict[str, Any]]) -> None:
    try:
        parse_entries(items)
    except ReferenceProblem as problem:
        raise Problem(422, "reference_invalid", detail=str(problem)) from None


def _entries(db: Session, list_id: uuid.UUID) -> list[EntryRow]:
    return list(
        db.execute(
            select(EntryRow).where(EntryRow.list_id == list_id).order_by(EntryRow.position, EntryRow.id)
        ).scalars()
    )


def _row(db: Session, list_id: uuid.UUID) -> ListRow:
    row = db.get(ListRow, list_id)
    if row is None:
        raise Problem(404, "not_found")
    return row


def _found_out(found: FoundRule) -> FoundRuleOut:
    return FoundRuleOut(
        kind=found.kind,
        building_kind=found.building_kind,
        status=found.status,
        reason=found.reason,
        params=found.params,
        page=found.page,
    )


def _measure(
    db: Session, row: ListRow, entries: list[EntryRow], version_no: int | None = None
) -> ReferenceMeasurementOut | None:
    versions = reference.versions_for(db, row.document_sha256, row.sector)
    if not versions:
        return None
    chosen = next((v for v in versions if v.version == version_no), None) if version_no else versions[-1]
    if chosen is None:
        raise Problem(404, "not_found")
    open_passages, dismissed = reference.passages(chosen)
    measured = measure(
        [_entry_domain(e) for e in entries], reference.found_rules(db, chosen), open_passages, dismissed
    )
    return ReferenceMeasurementOut(
        version=chosen.version,
        versions=[v.version for v in versions],
        model=chosen.model,
        created_at=chosen.created_at,
        recall=round(measured.recall, 3),
        counts=measured.counts,
        coverage={k: int(v) for k, v in (chosen.coverage or {}).items()},
        results=[
            MeasuredEntryOut(
                entry_id=entry.id,
                outcome=result.outcome,
                detail=result.detail,
                found=_found_out(result.found) if result.found else None,
            )
            for entry, result in zip(entries, measured.results, strict=True)
        ],
        extra=[_found_out(f) for f in measured.extra],
    )


def _list_out(db: Session, row: ListRow, entries: list[EntryRow]) -> ReferenceListOut:
    measured = _measure(db, row, entries) if entries else None
    return ReferenceListOut(
        id=row.id,
        document_sha256=row.document_sha256,
        document_title=row.document_title,
        sector=row.sector,
        status=row.status,
        note=row.note,
        entries_count=len(entries),
        updated_at=row.updated_at,
        updated_by_name=row.updated_by_name,
        summary=(
            ReferenceSummaryOut(version=measured.version, recall=measured.recall, counts=measured.counts)
            if measured
            else None
        ),
    )


def detail_out(db: Session, list_id: uuid.UUID) -> ReferenceListDetailOut:
    row = _row(db, list_id)
    entries = _entries(db, list_id)
    base = _list_out(db, row, entries)
    return ReferenceListDetailOut(
        **base.model_dump(),
        entries=[
            ReferenceEntryOut(
                id=e.id,
                position=e.position,
                kind=e.kind,
                building_kind=e.building_kind,
                expected=e.expected,
                params=dict(e.params or {}),
                page=e.page,
                quote=e.quote,
                note=e.note,
            )
            for e in entries
        ],
    )


def lists_out(db: Session) -> list[ReferenceListOut]:
    rows = db.execute(select(ListRow).order_by(ListRow.document_title, ListRow.sector)).scalars()
    return [_list_out(db, row, _entries(db, row.id)) for row in rows]


def candidates(db: Session) -> list[ReferenceCandidateOut]:
    """Ausgewertete Dokumente dieser Instanz mit ihren Sektoren (Grundlage einer neuen Liste)."""
    rows = db.execute(
        select(SourceFile.sha256, LandUsePlan.title, RuleSet.zone_code)
        .join(RegulationChapter, RegulationChapter.id == RuleSet.chapter_id)
        .join(SourceFile, SourceFile.id == RegulationChapter.source_file_id)
        .join(LandUsePlan, LandUsePlan.id == RuleSet.land_use_plan_id)
        .where(LandUsePlan.status == "active", RuleSet.current_version_id.is_not(None))
        .order_by(LandUsePlan.title, RuleSet.zone_code)
    ).all()
    grouped: dict[str, ReferenceCandidateOut] = {}
    for sha256, title, sector in rows:
        item = grouped.setdefault(
            sha256, ReferenceCandidateOut(document_sha256=sha256, document_title=title, sectors=[])
        )
        if sector not in item.sectors:
            item.sectors.append(sector)
    return list(grouped.values())


def _touch(row: ListRow, actor_id: str, actor_name: str | None) -> None:
    row.updated_at, row.updated_by, row.updated_by_name = utcnow(), actor_id, actor_name


def _actor_type(actor_id: str) -> ActorType:
    """Befehle der Kommandozeile melden sich als `system:<Befehl>`, alle anderen sind Konten des Büros."""
    return "system" if actor_id.startswith("system:") else "staff"


def create_list(
    db: Session,
    body: ReferenceListIn,
    actor_id: str,
    actor_name: str | None,
) -> ReferenceListDetailOut:
    exists = db.execute(
        select(ListRow.id).where(
            ListRow.document_sha256 == body.document_sha256, ListRow.sector == body.sector
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise Problem(409, "reference_list_exists")
    row = ListRow(
        document_sha256=body.document_sha256,
        document_title=body.document_title,
        sector=body.sector,
        note=body.note,
        status="draft",
        created_by=actor_id,
    )
    _touch(row, actor_id, actor_name)
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_list_created",
        entity_type="reference_list",
        entity_id=str(row.id),
        after={"document": body.document_title, "sector": body.sector},
    )
    db.commit()
    return detail_out(db, row.id)


def update_list(
    db: Session,
    list_id: uuid.UUID,
    body: ReferenceListPatch,
    actor_id: str,
    actor_name: str | None,
) -> ReferenceListDetailOut:
    row = _row(db, list_id)
    before = {"status": row.status, "title": row.document_title}
    changes = body.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(row, key, value)
    _touch(row, actor_id, actor_name)
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_list_changed",
        entity_type="reference_list",
        entity_id=str(row.id),
        before=before,
        after=changes,
    )
    db.commit()
    return detail_out(db, list_id)


def delete_list(db: Session, list_id: uuid.UUID, actor_id: str, actor_name: str | None) -> None:
    row = _row(db, list_id)
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_list_deleted",
        entity_type="reference_list",
        entity_id=str(row.id),
        before={
            "document": row.document_title,
            "sector": row.sector,
            "entries": len(_entries(db, list_id)),
        },
    )
    db.delete(row)
    db.commit()


def put_entry(
    db: Session,
    list_id: uuid.UUID,
    body: ReferenceEntryIn,
    actor_id: str,
    actor_name: str | None,
    entry_id: uuid.UUID | None = None,
) -> ReferenceListDetailOut:
    """Eintrag anlegen (ohne `entry_id`, ans Ende) oder ersetzen. Die Liste wird wieder Entwurf."""
    row = _row(db, list_id)
    item = body.model_dump()
    _checked([item])
    if entry_id is None:
        position = db.execute(
            select(func.coalesce(func.max(EntryRow.position), 0)).where(EntryRow.list_id == list_id)
        ).scalar_one()
        db.add(EntryRow(list_id=list_id, position=position + 1, updated_by=actor_id, **item))
        action = "reference_entry_added"
    else:
        entry = db.get(EntryRow, entry_id)
        if entry is None or entry.list_id != list_id:
            raise Problem(404, "not_found")
        for key, value in item.items():
            setattr(entry, key, value)
        entry.updated_at, entry.updated_by = utcnow(), actor_id
        action = "reference_entry_changed"
    row.status = "draft"
    _touch(row, actor_id, actor_name)
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action=action,
        entity_type="reference_list",
        entity_id=str(list_id),
        after={k: item[k] for k in ("kind", "building_kind", "expected", "page")},
    )
    db.commit()
    return detail_out(db, list_id)


def delete_entry(
    db: Session,
    list_id: uuid.UUID,
    entry_id: uuid.UUID,
    actor_id: str,
    actor_name: str | None,
) -> ReferenceListDetailOut:
    row = _row(db, list_id)
    entry = db.get(EntryRow, entry_id)
    if entry is None or entry.list_id != list_id:
        raise Problem(404, "not_found")
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_entry_deleted",
        entity_type="reference_list",
        entity_id=str(list_id),
        before={"kind": entry.kind, "building_kind": entry.building_kind, "page": entry.page},
    )
    db.delete(entry)
    row.status = "draft"
    _touch(row, actor_id, actor_name)
    db.commit()
    return detail_out(db, list_id)


EXPECTED_FROM_STATUS = {"effective": "effective", "not_regulated": "not_regulated", "text_only": "text_only"}


def entries_from_rules(rules: list[Rule]) -> list[dict[str, Any]]:
    """Entwurf aus einer Auswertung: wirksame, belegt nicht geregelte und nicht abbildbare Regeln und Hinweise
    mit Zitat. Offene Regeln ohne Befund bleiben draußen – sie fehlen der Auswertung, nicht der Liste."""
    items: list[dict[str, Any]] = []
    for rule in rules:
        expected = EXPECTED_FROM_STATUS.get(rule.status)
        if rule.status == "unknown" and rule.reason in ("not_expressible", "graphic_reference"):
            expected = rule.reason
        if expected is None or not (rule.quote or "").strip():
            continue
        items.append(
            {
                "kind": rule.kind,
                "building_kind": rule.building_kind,
                "expected": expected,
                "params": dict(rule.params or {}) if expected == "effective" else {},
                "page": rule.page,
                "quote": rule.quote,
                "note": "",
            }
        )
    return items


def from_evaluation(
    db: Session,
    list_id: uuid.UUID,
    actor_id: str,
    actor_name: str | None,
) -> ReferenceListDetailOut:
    """Einträge durch die aktuelle Auswertung dieser Instanz ersetzen; die Liste wird Entwurf."""
    row = _row(db, list_id)
    versions = reference.versions_for(db, row.document_sha256, row.sector)
    if not versions:
        raise Problem(404, "reference_not_evaluated")
    rules = list(db.execute(select(Rule).where(Rule.rule_set_version_id == versions[-1].id)).scalars())
    _replace_entries(db, row, entries_from_rules(rules), actor_id)
    row.status = "draft"
    _touch(row, actor_id, actor_name)
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_list_from_evaluation",
        entity_type="reference_list",
        entity_id=str(row.id),
        after={"version": versions[-1].version},
    )
    db.commit()
    return detail_out(db, list_id)


def _replace_entries(db: Session, row: ListRow, items: list[dict[str, Any]], actor_id: str) -> None:
    _checked(items)
    for entry in _entries(db, row.id):
        db.delete(entry)
    db.flush()
    for position, item in enumerate(items, start=1):
        db.add(
            EntryRow(
                list_id=row.id,
                position=position,
                kind=item["kind"],
                building_kind=item["building_kind"],
                expected=item["expected"],
                params=dict(item.get("params") or {}),
                page=item.get("page"),
                quote=str(item["quote"]),
                note=str(item.get("note") or ""),
                updated_by=actor_id,
            )
        )


def measurement(db: Session, list_id: uuid.UUID, version: int | None) -> ReferenceMeasurementOut:
    row = _row(db, list_id)
    result = _measure(db, row, _entries(db, list_id), version)
    if result is None:
        raise Problem(404, "reference_not_evaluated")
    return result


def export(db: Session, list_id: uuid.UUID) -> dict[str, Any]:
    """Datei im Format der mitgelieferten Listen (`reference_seed`), zum Sichern und Weitergeben."""
    row = _row(db, list_id)
    return {
        "format": reference.FORMAT,
        "document": {"title": row.document_title, "sha256": row.document_sha256},
        "sector": row.sector,
        "status": row.status,
        "note": row.note,
        "entries": [
            {
                "kind": e.kind,
                "building_kind": e.building_kind,
                "expected": e.expected,
                "params": dict(e.params or {}),
                "page": e.page,
                "quote": e.quote,
                "note": e.note,
            }
            for e in _entries(db, list_id)
        ],
    }


def import_list(
    db: Session,
    data: dict[str, Any],
    replace: bool,
    actor_id: str,
    actor_name: str | None,
) -> ReferenceListDetailOut:
    """Liste aus einer Datei anlegen; eine vorhandene desselben Dokuments und Sektors nur mit `replace`."""
    try:
        parsed = reference.parse_list(data)
    except ReferenceProblem as problem:
        raise Problem(422, "reference_invalid", detail=str(problem)) from None
    row = db.execute(
        select(ListRow).where(ListRow.document_sha256 == parsed.sha256, ListRow.sector == parsed.sector)
    ).scalar_one_or_none()
    if row is not None and not replace:
        raise Problem(409, "reference_list_exists")
    if row is None:
        row = ListRow(
            document_sha256=parsed.sha256,
            document_title=parsed.title or parsed.sha256[:12],
            sector=parsed.sector,
            created_by=actor_id,
        )
        db.add(row)
        db.flush()
    row.note = parsed.note
    row.status = parsed.status if parsed.status in ("draft", "checked") else "draft"
    _replace_entries(db, row, list(data.get("entries") or []), actor_id)
    _touch(row, actor_id, actor_name)
    audit.record(
        db,
        actor_type=_actor_type(actor_id),
        actor_id=actor_id,
        action="reference_list_imported",
        entity_type="reference_list",
        entity_id=str(row.id),
        after={"document": row.document_title, "sector": row.sector, "entries": len(parsed.entries)},
    )
    db.commit()
    return detail_out(db, row.id)
