"""Kanten korrigieren und bestätigen, Anreicherung wiederholen, Prüfliste des Büros (Modul G1,
Plan 3.3; aus `service.py` gelöst, REFACTORING_PLAN S20)."""

import uuid
from dataclasses import dataclass
from typing import Any, cast

from geoalchemy2.shape import to_shape
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.jobs import enqueue
from app.platform.problems import Problem
from app.site.domain import ENGINE_VERSION
from app.site.domain.edges import (
    Classification,
    EdgeFacts,
    EdgeGeometry,
    NeighbourCoverage,
    Override,
    OverrideKind,
    classify,
)
from app.site.models import Site, SiteEdge
from app.site.schemas import (
    SiteOut,
    SiteReviewItem,
)
from app.site.service import (
    load_site,
)
from app.site.store import (
    apply_classification,
    db_now,
    locked_site,
)

REVIEW_WARNINGS = [
    "customer_corrections_unconfirmed",
    "edges_need_review",
    "corner_lot",
    "flag_lot",
    "no_street_edge",
    "no_neighbour_data",
    "neighbour_data_incomplete",
]


@dataclass(frozen=True)
class Actor:
    type: str  # "customer" | "staff"
    id: str
    role: str  # "customer" | "architect"


def _reclassify(
    db: Session, site: Site, edges: list[SiteEdge], overrides: dict[int, Override]
) -> Classification:
    geometries = [
        EdgeGeometry(
            seq=e.seq,
            ring=e.ring,
            coords=tuple((float(x), float(y)) for x, y, *_ in to_shape(e.geometry).coords),
        )
        for e in edges
    ]
    facts = [
        EdgeFacts(
            neighbour_share=e.neighbour_share,
            adjacent=tuple(e.adjacent),
            street_candidate=cast(Any, e.street_candidate),
            probe_in_parcel=e.probe_in_parcel,
            road_share=e.road_share,
            street_name=e.street_name,
        )
        for e in edges
    ]
    return classify(
        geometries,
        facts,
        overrides,
        site_area_m2=site.area_m2,
        neighbour_coverage=cast(NeighbourCoverage, site.neighbour_coverage),
    )


def _current_overrides(edges: list[SiteEdge]) -> dict[int, Override]:
    return {
        e.seq: Override(cast(OverrideKind, e.override_kind), cast(Any, e.classification_source))
        for e in edges
        if e.override_kind is not None
    }


def _store(
    db: Session, site: Site, edges: list[SiteEdge], classification: Classification, actor: Actor
) -> None:
    by_seq = {e.geometry.seq: e for e in classification.edges}
    for row in edges:
        result = by_seq[row.seq]
        changed = (row.kind, row.classification_source, row.override_kind, row.confidence) != (
            result.kind,
            result.source,
            result.override,
            result.confidence,
        )
        row.kind = result.kind
        row.kind_auto = result.kind_auto
        row.classification_source = result.source
        row.override_kind = result.override
        row.confidence = result.confidence
        if changed:
            row.updated_at = db_now(db)
            row.updated_by = actor.id
    warnings = [*classification.warnings]
    if "area_mismatch" in site.warnings:
        warnings.append("area_mismatch")
    apply_classification(site, classification, warnings)
    site.engine_version = ENGINE_VERSION  # vollständig neu eingeordnet
    site.revision += 1
    site.updated_at = db_now(db)
    site.updated_by = actor.id


def correct_edge(
    db: Session,
    project_id: uuid.UUID,
    seq: int,
    kind: OverrideKind | None,
    actor: Actor,
    expected_revision: int | None = None,
) -> SiteOut:
    """Kantenart überschreiben oder mit `None` auf automatisch zurücksetzen (Spez. 5.1.4.6, Plan 3.3)."""
    site = locked_site(db, project_id, expected_revision)
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    target = next((e for e in edges if e.seq == seq), None)
    if target is None:
        raise Problem(404, "edge_not_found")
    if actor.role == "customer":
        if target.ring > 0:
            raise Problem(422, "edge_not_correctable")
        if target.classification_source == "architect":
            raise Problem(409, "edge_confirmed_by_architect")
    overrides = _current_overrides(edges)
    before = {"seq": seq, "kind": target.kind, "source": target.classification_source}
    if kind is None:
        overrides.pop(seq, None)
    else:
        overrides[seq] = Override(kind, "customer" if actor.role == "customer" else "architect")
    classification = _reclassify(db, site, edges, overrides)
    _store(db, site, edges, classification, actor)
    audit.record(
        db,
        actor_type="customer" if actor.role == "customer" else "staff",
        actor_id=actor.id,
        action="site_edge.correct",
        entity_type="site",
        entity_id=str(site.id),
        before=before,
        after={
            "seq": seq,
            "kind": target.kind,
            "source": target.classification_source,
            "revision": site.revision,
        },
    )
    db.commit()
    return load_site(db, project_id)


def confirm_customer_edges(
    db: Session, project_id: uuid.UUID, actor: Actor, expected_revision: int | None = None
) -> SiteOut:
    """Architekt übernimmt alle Kundenkorrekturen; der Baurahmen wird damit bindend (Plan 3.3)."""
    site = locked_site(db, project_id, expected_revision)
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    confirmed = [e.seq for e in edges if e.classification_source == "customer"]
    if not confirmed:
        return load_site(db, project_id)
    overrides = {
        seq: Override(o.kind, "architect" if o.source == "customer" else o.source)
        for seq, o in _current_overrides(edges).items()
    }
    classification = _reclassify(db, site, edges, overrides)
    _store(db, site, edges, classification, actor)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor.id,
        action="site_edge.confirm_customer",
        entity_type="site",
        entity_id=str(site.id),
        after={"seqs": confirmed, "revision": site.revision},
    )
    db.commit()
    return load_site(db, project_id)


def retry_enrichment(db: Session, actor: str) -> int:
    """Gelände und Risiken erneut abfragen, wo sie nach einem Ausfall `unavailable` sind (BETRIEB.md 8)."""
    sites = list(
        db.execute(
            select(Site)
            .where((Site.terrain_status == "unavailable") | (Site.risks_status == "unavailable"))
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for site in sites:
        if site.terrain_status == "unavailable":
            site.terrain_status = "pending"
        if site.risks_status == "unavailable":
            site.risks_status = "pending"
        enqueue(
            db,
            "site_enrich",
            {"site_id": str(site.id), "outline_hash": site.outline_hash},
            idempotency_key=f"site_enrich_retry:{site.id}:{site.revision}:{db_now(db).isoformat()}",
            project_id=site.project_id,
            created_by=actor,
        )
    db.commit()
    return len(sites)


def review_queue(
    db: Session, *, only_corrections: bool = True, require_inquiry: bool = True, limit: int = 200
) -> list[SiteReviewItem]:
    """Prüfliste des Büros. Standard: nur unbestätigte Kundenkorrekturen, nur Projekte mit Anfrage (G21,
    Modul A). Mit `only_corrections=False` auch unsichere Einordnungen; `require_inquiry=False` zeigt wie
    vor Modul A auch Grundstücke anonymer Besucher (nur zum Testen, keine Büro-Route)."""
    warnings = ["customer_corrections_unconfirmed"] if only_corrections else REVIEW_WARNINGS
    base_query = """
        SELECT s.project_id, s.parcel_idus, s.revision, s.warnings, s.updated_at,
               (SELECT count(*) FROM site_edge e
                WHERE e.site_id = s.id AND e.classification_source = 'customer') AS customer_corrections
        FROM site s
        WHERE s.warnings && CAST(:warnings AS varchar[])
        ORDER BY (s.warnings && ARRAY['customer_corrections_unconfirmed']::varchar[]) DESC,
                 s.updated_at DESC
        LIMIT :limit
        """
    with_inquiry_query = """
        SELECT s.project_id, s.parcel_idus, s.revision, s.warnings, s.updated_at,
               (SELECT count(*) FROM site_edge e
                WHERE e.site_id = s.id AND e.classification_source = 'customer') AS customer_corrections
        FROM site s
        WHERE s.warnings && CAST(:warnings AS varchar[])
          AND EXISTS (SELECT 1 FROM inquiry i WHERE i.project_id = s.project_id)
        ORDER BY (s.warnings && ARRAY['customer_corrections_unconfirmed']::varchar[]) DESC,
                 s.updated_at DESC
        LIMIT :limit
        """
    rows = db.execute(
        text(with_inquiry_query if require_inquiry else base_query),
        {"warnings": warnings, "limit": limit},
    ).all()
    return [
        SiteReviewItem(
            project_id=r.project_id,
            parcel_idus=list(r.parcel_idus),
            revision=r.revision,
            warnings=list(r.warnings),
            customer_corrections=r.customer_corrections,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
