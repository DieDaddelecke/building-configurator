"""Organisationen (AN6, docs/PLAN_AN6_MANDANTEN.md): anlegen, Mitglieder, Grenzen und Scan-Kontingent,
Erscheinungsbild und API-Schlüssel.

Kern, weil `rules`, `analysis` und `plan` es brauchen. Die Kosten der Auswertung stehen in `rules`; das Modul
meldet sie über `register_cost_provider` an, damit die Plattform `rules` nicht kennt (wie die Projektliste).
"""

import io
import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from PIL import Image, UnidentifiedImageError
from sqlalchemy import String, func, literal_column, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit, storage
from app.platform.auth.context import Role
from app.platform.auth.tokens import hash_token
from app.platform.db import utcnow
from app.platform.logging import get_logger
from app.platform.models import ApiKey, Organisation, OrganisationMember, StaffUser, UsageRecord
from app.platform.problems import Problem

log = get_logger("organisations")

OPERATOR_NAME = "eigenes-buero"
OPERATOR_DISPLAY_NAME = "Eigenes Büro"
OPERATOR_ONLY_ROLES = frozenset({Role.ops, Role.rules_admin, Role.catalog_admin})
API_KEY_MAX_ACTIVE = 10
API_KEY_DEFAULT_DAYS = 365
API_KEY_MAX_DAYS = 730
LOGO_MAX_BYTES = 1_000_000
LOGO_MAX_PIXELS = 2000
LOGO_TARGET_PIXELS = 800
MIN_CONTRAST = 4.5
"""Akzentfarbe gegen Weiß (WCAG AA für Text), weil Überschriften und Linien des Berichts sie tragen."""
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")
HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$")
MONTH_FORMAT = literal_column("'YYYY-MM'", String())
"""Als Literal, nicht als Parameter: Sonst stehen in SELECT und GROUP BY zwei Parameter, und PostgreSQL hält
die Ausdrücke für verschieden."""

CostProvider = Callable[[Session, uuid.UUID, datetime], dict[str, float]]
"""Kosten der Auswertung einer Organisation je Monat (`YYYY-MM`) ab einem Zeitpunkt."""
_cost_providers: list[CostProvider] = []


def register_cost_provider(provider: CostProvider) -> None:
    if provider not in _cost_providers:
        _cost_providers.append(provider)


class OrganisationError(Exception):
    """Fehler beim Anlegen oder Zuordnen; die CLI zeigt `code`, die API antwortet mit einem Problem."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Monat, Grenzen und Verbrauch (3.4)
# ---------------------------------------------------------------------------


def month_start(now: datetime | None = None) -> datetime:
    """Beginn des Kalendermonats in UTC, wie die Monatskosten der Instanz."""
    current = now or utcnow()
    return datetime(current.year, current.month, 1, tzinfo=UTC)


def months_back(count: int, now: datetime | None = None) -> datetime:
    start = month_start(now)
    for _ in range(count - 1):
        start = month_start(start - timedelta(days=1))
    return start


def budget_limit(settings: Settings, org: Organisation) -> float | None:
    """Monatsbudget der Auswertung; None = keine eigene Grenze (nur die der Instanz)."""
    if org.budget_month_usd is not None:
        return org.budget_month_usd
    return None if org.kind == "operator" else settings.org_budget_month_usd


def ocr_limit(settings: Settings, org: Organisation) -> int | None:
    """Erkannte Seiten je Monat (E-AN7-7); None = keine Grenze."""
    if org.ocr_pages_month is not None:
        return org.ocr_pages_month
    return None if org.kind == "operator" else settings.org_ocr_pages_month


def ocr_pages_used(db: Session, organisation_id: uuid.UUID, now: datetime | None = None) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.organisation_id == organisation_id,
            UsageRecord.kind == "ocr_pages",
            UsageRecord.created_at >= month_start(now),
        )
    ).scalar_one()
    return int(total)


def reserve_ocr_pages(
    db: Session, settings: Settings, organisation_id: uuid.UUID, pages: int, reference: str, actor: str
) -> None:
    """Scan-Kontingent prüfen und die Seiten buchen, in der Transaktion der Bestätigung (3.4). Die Zeile der
    Organisation wird gesperrt, damit zwei gleichzeitige Bestätigungen die Grenze nicht gemeinsam
    überschreiten."""
    org = db.execute(
        select(Organisation).where(Organisation.id == organisation_id).with_for_update()
    ).scalar_one()
    limit = ocr_limit(settings, org)
    if limit is not None:
        remaining = max(0, limit - ocr_pages_used(db, organisation_id))
        if pages > remaining:
            raise Problem(409, "ocr_quota_exceeded", remaining=remaining, pages=pages, limit=limit)
    db.add(
        UsageRecord(
            organisation_id=organisation_id,
            kind="ocr_pages",
            quantity=pages,
            reference=reference[:100],
            created_by=actor,
        )
    )


@dataclass(frozen=True)
class MonthUsage:
    month: str
    cost_usd: float
    ocr_pages: int


def usage(db: Session, organisation_id: uuid.UUID, months: int = 6) -> list[MonthUsage]:
    """Verbrauch der letzten Monate, neuester zuerst (Seite Organisation, 3.7)."""
    since = months_back(months)
    costs: dict[str, float] = {}
    for provider in _cost_providers:
        for month, value in provider(db, organisation_id, since).items():
            costs[month] = costs.get(month, 0.0) + value
    pages: dict[str, int] = {}
    month_of = func.to_char(UsageRecord.created_at, MONTH_FORMAT)
    rows = db.execute(
        select(month_of, func.sum(UsageRecord.quantity))
        .where(
            UsageRecord.organisation_id == organisation_id,
            UsageRecord.kind == "ocr_pages",
            UsageRecord.created_at >= since,
        )
        .group_by(month_of)
    ).all()
    for month, quantity in rows:
        pages[str(month)] = int(quantity or 0)
    result: list[MonthUsage] = []
    start = month_start()
    for _ in range(months):
        key = f"{start:%Y-%m}"
        result.append(MonthUsage(key, round(costs.get(key, 0.0), 2), pages.get(key, 0)))
        start = month_start(start - timedelta(days=1))
    return result


# ---------------------------------------------------------------------------
# Anlegen und Mitglieder (3.1)
# ---------------------------------------------------------------------------


def operator_organisation(db: Session, *, create: bool = False, actor: str = "cli") -> Organisation | None:
    """Die Organisation des Betreibers; mit `create` wird sie beim ersten Konto angelegt."""
    org = db.execute(select(Organisation).where(Organisation.kind == "operator")).scalar_one_or_none()
    if org is None and create:
        org = Organisation(
            name=OPERATOR_NAME, display_name=OPERATOR_DISPLAY_NAME, kind="operator", created_by=actor
        )
        db.add(org)
        db.flush()
    return org


def create_organisation(
    db: Session, settings: Settings, *, name: str, display_name: str, kind: str, actor: str
) -> Organisation:
    if not NAME.match(name):
        raise OrganisationError("invalid_name")
    if kind not in ("operator", "customer"):
        raise OrganisationError("invalid_kind")
    if kind == "customer" and not settings.external_organisations:
        # Fremde Büros erst nach juristischer Prüfung (E-A5, E-AN6-8)
        raise OrganisationError("external_organisations_disabled")
    if kind == "operator" and operator_organisation(db) is not None:
        raise OrganisationError("operator_exists")
    if db.execute(select(Organisation.id).where(Organisation.name == name)).first() is not None:
        raise OrganisationError("name_taken")
    org = Organisation(name=name, display_name=display_name.strip()[:200], kind=kind, created_by=actor)
    db.add(org)
    db.flush()
    audit.record(
        db,
        actor_type="system" if actor == "cli" else "staff",
        actor_id=actor,
        action="organisation.create",
        entity_type="organisation",
        entity_id=str(org.id),
        after={"name": name, "kind": kind},
    )
    return org


def check_roles_allowed(org: Organisation, roles: list[str]) -> None:
    """Rollen des Betriebs nur in der Organisation `operator` (3.1, 7.1 Nr. 11)."""
    if org.kind != "operator" and set(roles) & OPERATOR_ONLY_ROLES:
        raise OrganisationError("operator_roles_outside_operator")


def set_membership(db: Session, org: Organisation, user: StaffUser, role: str, actor: str) -> None:
    """Konto einer Organisation zuordnen oder die Rolle ändern. Ein Konto gehört zu einer Organisation
    (E-AN6-1): Ein Wechsel muss vorher die alte Mitgliedschaft beenden."""
    if role not in ("admin", "member"):
        raise OrganisationError("invalid_role")
    check_roles_allowed(org, user.roles)
    membership = db.get(OrganisationMember, user.id)
    if membership is not None and membership.organisation_id != org.id:
        raise OrganisationError("member_of_other_organisation")
    before = {"role": membership.role} if membership else None
    if membership is None:
        db.add(OrganisationMember(staff_user_id=user.id, organisation_id=org.id, role=role, created_by=actor))
    else:
        membership.role = role
    audit.record(
        db,
        actor_type="system" if actor == "cli" else "staff",
        actor_id=actor,
        action="organisation_member.put",
        entity_type="organisation",
        entity_id=str(org.id),
        before=before,
        after={"staff_user": str(user.id), "role": role},
    )


def admin_count(db: Session, organisation_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(OrganisationMember)
            .join(StaffUser, StaffUser.id == OrganisationMember.staff_user_id)
            .where(
                OrganisationMember.organisation_id == organisation_id,
                OrganisationMember.role == "admin",
                StaffUser.active.is_(True),
            )
        ).scalar_one()
    )


# ---------------------------------------------------------------------------
# API-Schlüssel (3.6)
# ---------------------------------------------------------------------------


def create_api_key(
    db: Session, organisation_id: uuid.UUID, *, name: str, scopes: list[str], days: int, actor: str
) -> tuple[ApiKey, str]:
    """Neuer Schlüssel; der Klartext kommt nur hier zurück und wird nie gespeichert."""
    now = utcnow()
    active = db.execute(
        select(func.count())
        .select_from(ApiKey)
        .where(
            ApiKey.organisation_id == organisation_id, ApiKey.revoked_at.is_(None), ApiKey.expires_at > now
        )
    ).scalar_one()
    if active >= API_KEY_MAX_ACTIVE:
        raise Problem(409, "api_key_limit", limit=API_KEY_MAX_ACTIVE)
    prefix = secrets.token_hex(4)
    token = f"emp_{prefix}_{secrets.token_urlsafe(32)}"
    key = ApiKey(
        organisation_id=organisation_id,
        name=name.strip()[:80],
        prefix=prefix,
        token_hash=hash_token(token),
        scopes=sorted(set(scopes)),
        expires_at=now + timedelta(days=days),
        created_by=actor,
    )
    db.add(key)
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="api_key.create",
        entity_type="api_key",
        entity_id=str(key.id),
        after={
            "organisation": str(organisation_id),
            "scopes": key.scopes,
            "expires_at": key.expires_at.isoformat(),
        },
    )
    return key, token


def revoke_api_key(db: Session, organisation_id: uuid.UUID, key_id: uuid.UUID, actor: str) -> None:
    key = db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.organisation_id == organisation_id)
    ).scalar_one_or_none()
    if key is None:
        raise Problem(404, "not_found")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        audit.record(
            db,
            actor_type="staff",
            actor_id=actor,
            action="api_key.revoke",
            entity_type="api_key",
            entity_id=str(key.id),
        )


# ---------------------------------------------------------------------------
# Erscheinungsbild (3.5)
# ---------------------------------------------------------------------------


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_to_white(color: str) -> float:
    return 1.05 / (_luminance(color) + 0.05)


def check_accent_color(color: str) -> str:
    value = color.strip().lower()
    if not HEX_COLOR.match(value):
        raise Problem(422, "invalid_color")
    if contrast_to_white(value) < MIN_CONTRAST:
        raise Problem(422, "color_contrast_too_low", contrast=round(contrast_to_white(value), 2))
    return value


def normalise_logo(data: bytes) -> bytes:
    """PNG oder JPEG prüfen, verkleinern und als PNG neu schreiben: entfernt Metadaten und alles, was kein
    Bild ist (7.1 Nr. 8). Kein SVG (E-AN6-6)."""
    if len(data) > LOGO_MAX_BYTES:
        raise Problem(413, "upload_too_large", limit=LOGO_MAX_BYTES)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ("PNG", "JPEG"):
                raise Problem(422, "logo_format")
            if max(probe.size) > LOGO_MAX_PIXELS:
                raise Problem(422, "logo_too_large", limit=LOGO_MAX_PIXELS)
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            converted = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise Problem(422, "logo_format") from None
    converted.thumbnail((LOGO_TARGET_PIXELS, LOGO_TARGET_PIXELS))
    out = io.BytesIO()
    converted.save(out, format="PNG", optimize=True)
    return out.getvalue()


def store_logo(db: Session, org: Organisation, data: bytes, actor: str) -> str | None:
    """Neues Logo ablegen; gibt den alten Schlüssel zurück, den der Aufrufer nach dem Commit löscht."""
    png = normalise_logo(data)
    old = org.logo_key
    org.branding_revision += 1
    key = f"organisations/{org.id}/logo-{org.branding_revision}.png"
    storage.put_bytes(key, png, "image/png")
    org.logo_key, org.updated_at = key, utcnow()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="organisation.logo",
        entity_type="organisation",
        entity_id=str(org.id),
        after={"revision": org.branding_revision, "bytes": len(png)},
    )
    return old


def remove_logo(db: Session, org: Organisation, actor: str) -> str | None:
    old = org.logo_key
    if old is not None:
        org.logo_key, org.updated_at = None, utcnow()
        org.branding_revision += 1
        audit.record(
            db,
            actor_type="staff",
            actor_id=actor,
            action="organisation.logo_remove",
            entity_type="organisation",
            entity_id=str(org.id),
        )
    return old


def delete_file_quietly(key: str | None) -> None:
    if key is None:
        return
    try:
        storage.delete(key)
    except Exception:
        log.warning("organisation_file_delete_failed", key=key)


@dataclass(frozen=True)
class Branding:
    """Erscheinungsbild für Bericht und DXF (3.5); leer, wenn nichts gesetzt ist."""

    display_name: str
    address_lines: list[str]
    phone: str | None
    email: str | None
    website: str | None
    registration: str | None
    accent_color: str | None
    logo_png: bytes | None
    revision: int

    @property
    def contact_lines(self) -> list[str]:
        contact = " · ".join(v for v in (self.phone, self.email, self.website) if v)
        return [line for line in (*self.address_lines, contact, self.registration or "") if line]


def branding_for(
    db: Session, organisation_id: uuid.UUID | None, *, load_logo: bool = True
) -> Branding | None:
    """Erscheinungsbild der Organisation eines Projekts; None für Kundenprojekte und solange nichts gesetzt
    ist (Revision 0: der Bericht bleibt wie vor AN6). `load_logo=False` für die Prüfsumme: Sie braucht nur die
    Revision, nicht das Bild aus dem Objektspeicher."""
    if organisation_id is None:
        return None
    org = db.get(Organisation, organisation_id)
    if org is None or org.branding_revision == 0:
        return None
    logo: bytes | None = None
    if org.logo_key and load_logo:
        try:
            logo = storage.get_bytes(org.logo_key)
        except Exception:
            log.warning("organisation_logo_missing", organisation=str(org.id))
    return Branding(
        display_name=org.display_name,
        address_lines=list(org.address_lines or []),
        phone=org.phone,
        email=org.email,
        website=org.website,
        registration=org.registration,
        accent_color=org.accent_color,
        logo_png=logo,
        revision=org.branding_revision,
    )


def branding_revision(db: Session, organisation_id: uuid.UUID | None) -> int:
    if organisation_id is None:
        return 0
    revision = db.execute(
        select(Organisation.branding_revision).where(Organisation.id == organisation_id)
    ).scalar_one_or_none()
    return int(revision or 0)
