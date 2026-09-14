"""Anmeldung der Mitarbeitenden über OIDC mit MFA (Plan 3.2, 6.7).

Der Identitätsdienst bestätigt Person und zweiten Faktor. Rollen und Freischaltung stehen in
`staff_user`; unbekannte Konten erhalten keinen Zugang (keine automatische Anlage).
"""

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.platform import audit
from app.platform.auth.context import RequestAuth, get_auth, public
from app.platform.auth.tokens import STAFF_COOKIE, hash_token, new_token
from app.platform.db import get_db, utcnow
from app.platform.logging import get_logger
from app.platform.models import StaffSession, StaffUser
from app.platform.problems import Problem

log = get_logger(__name__)
router = APIRouter(tags=["auth"])

RefusalReason = Literal["unknown", "inactive", "email_unverified", "mfa"]


@dataclass(frozen=True)
class LoginRefused:
    reason: RefusalReason


@lru_cache
def _oauth() -> OAuth:
    settings = get_settings()
    if not (settings.oidc_issuer and settings.oidc_client_id):
        raise Problem(503, "oidc_not_configured")
    oauth = OAuth()
    oauth.register(
        name="staff",
        server_metadata_url=settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value() if settings.oidc_client_secret else None,
        client_kwargs={"scope": settings.oidc_scopes, "code_challenge_method": "S256"},
    )
    return oauth


def safe_next(value: str | None) -> str:
    """Nur relative Ziele im Büro-Bereich, keine offene Weiterleitung."""
    if value and value.startswith("/buero") and not value.startswith("//") and "\\" not in value:
        return value
    return "/buero"


def resolve_staff_login(db: Session, claims: dict[str, Any], settings: Settings) -> StaffUser | LoginRefused:
    """Ordnet die bestätigten Angaben des Identitätsdienstes einem freigeschalteten Konto zu."""
    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip().lower()
    if settings.oidc_require_mfa:
        amr = {str(v) for v in claims.get("amr") or []}
        if not amr & set(settings.oidc_mfa_amr_values):
            return LoginRefused("mfa")

    user = db.execute(select(StaffUser).where(StaffUser.oidc_subject == subject)).scalar_one_or_none()
    if user is None:
        if not email or claims.get("email_verified") is not True:
            return LoginRefused("email_unverified")
        # Erste Anmeldung: Konto über die bestätigte E-Mail-Adresse finden und an das Subjekt binden
        user = db.execute(
            select(StaffUser).where(func.lower(StaffUser.email) == email, StaffUser.oidc_subject.is_(None))
        ).scalar_one_or_none()
        if user is None:
            return LoginRefused("unknown")
        user.oidc_subject = subject
    if not user.active:
        return LoginRefused("inactive")
    if claims.get("name") and not user.display_name:
        user.display_name = str(claims["name"])[:200]
    return user


def start_session(db: Session, user: StaffUser, amr: list[str], settings: Settings) -> str:
    token = new_token()
    now = utcnow()
    session = StaffSession(
        staff_user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(hours=settings.staff_session_hours),
        last_seen_at=now,
        amr=amr,
        created_by=str(user.id),
    )
    db.add(session)
    user.last_login_at = now
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=str(user.id),
        action="staff.login",
        entity_type="staff_session",
        entity_id=str(session.id),
    )
    return token


@router.get("/auth/staff/login", dependencies=[Depends(public)], include_in_schema=True)
async def staff_login(request: Request, next: str | None = None) -> Response:
    settings = get_settings()
    client = _oauth().create_client("staff")
    request.session["next"] = safe_next(next)
    redirect_uri = settings.public_base_url.rstrip("/") + "/api/v1/auth/staff/callback"
    response: Response = await client.authorize_redirect(request, redirect_uri)
    return response


@router.get("/auth/staff/callback", dependencies=[Depends(public)], include_in_schema=False)
async def staff_callback(request: Request, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    client = _oauth().create_client("staff")
    target = safe_next(request.session.pop("next", None))
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("oidc_callback_failed", error=exc.error)
        return RedirectResponse("/buero/kein-zugang?" + urlencode({"grund": "fehler"}), status_code=303)

    claims: dict[str, Any] = dict(token.get("userinfo") or {})
    result = resolve_staff_login(db, claims, settings)
    if isinstance(result, LoginRefused):
        db.commit()
        log.info("staff_login_refused", reason=result.reason)
        return RedirectResponse("/buero/kein-zugang?" + urlencode({"grund": result.reason}), status_code=303)

    session_token = start_session(db, result, [str(v) for v in claims.get("amr") or []], settings)
    db.commit()
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        STAFF_COOKIE,
        session_token,
        max_age=settings.staff_session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/auth/staff/logout", status_code=204, dependencies=[Depends(public)])
def staff_logout(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    if auth.staff is not None:
        db.execute(
            update(StaffSession).where(StaffSession.id == auth.staff.session_id).values(revoked_at=utcnow())
        )
        audit.record(
            db,
            actor_type="staff",
            actor_id=auth.staff.actor_id,
            action="staff.logout",
            entity_type="staff_session",
            entity_id=str(auth.staff.session_id),
        )
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        STAFF_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
    return response


class StaffInfo(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]


class SessionInfo(BaseModel):
    staff: StaffInfo | None
    project_id: str | None


@router.get("/session", response_model=SessionInfo, dependencies=[Depends(public)])
def current_session(auth: RequestAuth = Depends(get_auth)) -> SessionInfo:
    """Wer bin ich. Setzt beim ersten Aufruf das CSRF-Cookie (Middleware)."""
    staff = auth.staff
    return SessionInfo(
        staff=StaffInfo(
            id=str(staff.user_id),
            email=staff.email,
            display_name=staff.display_name,
            roles=sorted(staff.roles),
        )
        if staff
        else None,
        project_id=str(auth.project_id) if auth.project_id else None,
    )
