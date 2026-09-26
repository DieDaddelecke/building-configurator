"""Tabellen des Moduls G2 (Plan 3.4, Spez. 4.2).

Abweichend von Spez. 4.2 (Entscheidung D11): `rule_set_version.status` ist `simulated`, `office_reviewed`
oder `retired` statt `draft`/`validated`; Regeln tragen `status` und `origin` statt einer Entscheidung.
Regeln und Regelwerksversionen sind unveränderlich (L4): Eine Korrektur erzeugt eine neue Version.
"""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk

L93 = 2154


def _geom(kind: str) -> Geometry:
    return Geometry(kind, srid=L93, spatial_index=False)


class RulesCommune(Base):
    """Stand je Gemeinde des Einzugsgebiets: welches Planwerk gilt, warum es keine Simulation gibt."""

    __tablename__ = "rules_commune"

    commune_insee: Mapped[str] = mapped_column(String(5), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    land_use_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="SET NULL")
    )
    fallback_land_use_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="SET NULL")
    )
    """Zuletzt vollständig ausgewerteter Planstand. Kunden sehen ihn als „veraltet“, solange der neue Stand
    nicht vollständig ausgewertet ist oder nicht importiert werden konnte (Plan 3.4)."""
    error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('ok','rnu','no_document','no_regulation','multiple_regulations','no_chapters',"
            "'failed')",
            name="status_known",
        ),
    )


class LandUsePlan(UuidPk, Created, Base):
    """Planstand eines Planwerks im GPU (PLU, PLUi). Ein neuer Stand ist ein neuer Datensatz (Spez. 5.2.5).

    Seit AN2 auch ein **hochgeladenes** règlement écrit (`origin = 'upload'`, docs/PLAN_AN2_PLU.md 3.1):
    ohne GPU-Kennung, ohne Gemeinden und Zonen, erkannt an der Prüfsumme der Datei. Dasselbe PDF ist
    dasselbe Dokument; Kapitel, Läufe und Regelwerke hängen daran wie an einem Planstand des GPU.
    """

    __tablename__ = "land_use_plan"

    origin: Mapped[str] = mapped_column(String(10), server_default=text("'gpu'"))
    gpu_doc_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    document_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    partition: Mapped[str] = mapped_column(String(60))
    du_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    gpu_timestamp: Mapped[str | None] = mapped_column(String(40))
    gpu_update_date: Mapped[str | None] = mapped_column(String(40))
    communes: Mapped[list[str]] = mapped_column(ARRAY(String(5)), server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'importing'"))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    error: Mapped[str | None] = mapped_column(Text)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('importing','active','superseded','failed')", name="status_known"),
        CheckConstraint(
            "(origin = 'gpu' AND gpu_doc_id IS NOT NULL) "
            "OR (origin = 'upload' AND document_sha256 IS NOT NULL)",
            name="origin_known",
        ),
    )


class SourceFile(UuidPk, Created, Base):
    """Planunterlage im Objektspeicher; Duplikate über `sha256` erkennbar (Spez. 4.2)."""

    __tablename__ = "source_file"

    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int] = mapped_column(Integer)
    empty_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default=text("'{}'"))

    __table_args__ = (CheckConstraint("kind IN ('regulation_pdf')", name="kind_known"),)


class SourcePage(Base):
    """Textschicht je Seite: Grundlage der Kapitelsuche und der Zitatprüfung."""

    __tablename__ = "source_page"

    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_file.id", ondelete="CASCADE"), primary_key=True
    )
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)


class Zone(UuidPk, Created, Base):
    __tablename__ = "zone"

    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="CASCADE"), index=True
    )
    gpu_gid: Mapped[int] = mapped_column(BigInteger)
    code: Mapped[str] = mapped_column(String(20))
    label: Mapped[str | None] = mapped_column(String(300))
    zone_type: Mapped[str | None] = mapped_column(String(10))
    commune_insee: Mapped[str] = mapped_column(String(5))
    chapter_code: Mapped[str | None] = mapped_column(String(20))
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))

    __table_args__ = (
        UniqueConstraint("land_use_plan_id", "gpu_gid", name="uq_zone_plan_gid"),
        Index("ix_zone_geometry", "geometry", postgresql_using="gist"),
    )


class OverlayConstraint(UuidPk, Created, Base):
    """Überlagernde Vorgaben aus dem GPU als Hinweis (Plan 3.4): Vorschriften, Informationen, Servituden."""

    __tablename__ = "overlay_constraint"

    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="CASCADE"), index=True
    )
    commune_insee: Mapped[str] = mapped_column(String(5))
    endpoint: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(20))
    type_code: Mapped[str | None] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(500))
    partition: Mapped[str | None] = mapped_column(String(80))
    gpu_gid: Mapped[int] = mapped_column(BigInteger)
    effect: Mapped[str] = mapped_column(String(10), server_default=text("'info'"))
    geometry: Mapped[Any] = mapped_column(_geom("GEOMETRY"))

    __table_args__ = (
        UniqueConstraint("land_use_plan_id", "endpoint", "gpu_gid", name="uq_overlay_plan_endpoint_gid"),
        CheckConstraint("category IN ('prescription','information','servitude')", name="category_known"),
        CheckConstraint("effect IN ('no_build','rules','info')", name="effect_known"),
        Index("ix_overlay_constraint_geometry", "geometry", postgresql_using="gist"),
    )


class RegulationChapter(UuidPk, Created, Base):
    """Zonenkapitel im règlement écrit mit den Sektoren des Einzugsgebiets; Einheit der Auswertung."""

    __tablename__ = "regulation_chapter"

    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_file.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    first_page: Mapped[int] = mapped_column(Integer)
    last_page: Mapped[int] = mapped_column(Integer)
    general_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    sectors: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    suggested_sectors: Mapped[list[str]] = mapped_column(ARRAY(String(20)), server_default=text("'{}'"))
    """Nur hochgeladene Dokumente: Zonencodes aus dem Kapiteltext als Vorschlag für die Zonenwahl (AN2)."""
    detection: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    engine_version: Mapped[str | None] = mapped_column(String(20))
    """Stand der Schranken bei der letzten Bewertung. Weicht er ab, wird aus gespeicherten Läufen neu
    bewertet."""
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("land_use_plan_id", "code", name="uq_regulation_chapter_plan_code"),
        CheckConstraint("status IN ('pending','extracting','succeeded','failed')", name="status_known"),
        CheckConstraint("first_page >= 1 AND last_page >= first_page", name="pages_valid"),
    )


class RuleExtractionRun(UuidPk, Created, Base):
    """Ein Aufruf des Sprachmodells: Modell, Prompt, Kosten, Rohantwort (Plan 3.4, 6.8). Wird nie gelöscht,
    solange das Kapitel besteht: Die Monatskosten werden daraus berechnet."""

    __tablename__ = "rule_extraction_run"

    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regulation_chapter.id", ondelete="CASCADE"))
    run_no: Mapped[int] = mapped_column(Integer)
    """1 = Auswertung, 2 = Gegenprüfung."""
    part: Mapped[str] = mapped_column(String(200), server_default=text("''"))
    """Teil des Laufs: `sectors:Ub,Uba` oder `verify:<Prüfsumme der Regeln>`; Wiederverwendung je Teil."""
    input_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(60))
    prompt_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(String(300))
    stop_reason: Mapped[str | None] = mapped_column(String(30))
    served_by_fallback: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    cost_usd: Mapped[float] = mapped_column(Float, server_default=text("0"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(100))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("status IN ('succeeded','failed')", name="status_known"),
        Index("ix_rule_extraction_run_chapter", "chapter_id", "created_at"),
        Index("ix_rule_extraction_run_created", "created_at"),
    )


class RuleSet(UuidPk, Created, Base):
    """Regelwerk je Zone oder Sektor eines Planstands; `current_version_id` ist die wirksame Version."""

    __tablename__ = "rule_set"

    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("land_use_plan.id", ondelete="CASCADE"))
    zone_code: Mapped[str] = mapped_column(String(20))
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("regulation_chapter.id", ondelete="SET NULL")
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("land_use_plan_id", "zone_code", name="uq_rule_set_plan_zone"),)


class RuleSetVersion(UuidPk, Created, Base):
    __tablename__ = "rule_set_version"

    rule_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rule_set.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(20))
    based_on_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    extraction_run_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=text("'{}'")
    )
    engine_version: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(60))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    coverage: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("rule_set_id", "version", name="uq_rule_set_version_set_version"),
        CheckConstraint("status IN ('simulated','office_reviewed','retired')", name="status_known"),
        CheckConstraint("origin IN ('extraction','office')", name="origin_known"),
    )


RULE_STATUSES = "('effective','unknown','not_regulated','text_only')"


class Rule(UuidPk, Created, Base):
    __tablename__ = "rule"

    rule_set_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_set_version.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    building_kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(40))
    detail: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # CASCADE statt SET NULL: Regeln sind gegen UPDATE geschützt; Unterlagen fallen nur mit dem Planstand weg
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id", ondelete="CASCADE"))
    page: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(Text)
    quote_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    similarity: Mapped[float] = mapped_column(Float, server_default=text("0"))
    confidence: Mapped[float] = mapped_column(Float, server_default=text("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    origin: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        CheckConstraint(f"status IN {RULE_STATUSES}", name="status_known"),
        CheckConstraint("building_kind IN ('main','annex','pool','any')", name="building_kind_known"),
        CheckConstraint("origin IN ('extraction','office')", name="origin_known"),
    )


class ProjectRegulation(UuidPk, Created, Base):
    """Hochgeladenes Dokument eines Projekts mit gewählter Zone (AN2, docs/PLAN_AN2_PLU.md 3.1).

    Ein Projekt hat höchstens ein PLU (`role = 'plu'`) und bis zu drei Zusatzdokumente (`supplement`,
    AN3, docs/PLAN_AN3_ANALYSE.md 3.7). Das Dokument bleibt, wenn das Projekt gelöscht wird (E-AN2-4)."""

    __tablename__ = "project_regulation"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    land_use_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("land_use_plan.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), server_default=text("'plu'"))
    zone_code: Mapped[str | None] = mapped_column(String(20))
    """Sektor, für den ausgewertet wird (`Uba`; bei Zusatzdokumenten das Lot, `Lot-12` oder `Ensemble`);
    leer, bis der Architekt Zone oder Lot wählt."""
    chapter_code: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("project_id", "land_use_plan_id", name="uq_project_regulation_project_document"),
        CheckConstraint("role IN ('plu','supplement')", name="role_known"),
        Index("uq_project_regulation_plu", "project_id", unique=True, postgresql_where=text("role = 'plu'")),
    )


class ProjectRuleOverride(UuidPk, Created, Base):
    """Korrektur des Büros nur für ein Projekt (z. B. Lotissement); ändert die Zone für andere nicht."""

    __tablename__ = "project_rule_override"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    zone_code: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(40))
    building_kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint(
            "project_id", "zone_code", "kind", "building_kind", name="uq_project_rule_override_key"
        ),
        CheckConstraint(f"status IN {RULE_STATUSES}", name="status_known"),
        CheckConstraint("building_kind IN ('main','annex','pool','any')", name="building_kind_known"),
    )
