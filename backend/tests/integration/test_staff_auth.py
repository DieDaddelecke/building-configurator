from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.platform.auth.staff import LoginRefused, resolve_staff_login
from app.platform.models import AuditLog, StaffSession, StaffUser

MFA_CLAIMS = {"sub": "idp-123", "email": "Archi@Buero.test", "email_verified": True, "amr": ["pwd", "mfa"]}


def test_first_login_binds_subject_via_verified_email(db_session: Any) -> None:
    db_session.add(StaffUser(email="archi@buero.test", roles=["architect"]))
    db_session.commit()

    user = resolve_staff_login(db_session, dict(MFA_CLAIMS), get_settings())
    assert isinstance(user, StaffUser)
    assert user.oidc_subject == "idp-123"

    # Danach zählt das Subjekt, nicht mehr die Adresse
    again = resolve_staff_login(db_session, {**MFA_CLAIMS, "email": "neu@buero.test"}, get_settings())
    assert isinstance(again, StaffUser) and again.id == user.id


def test_login_refusals(db_session: Any) -> None:
    settings = get_settings()
    db_session.add(StaffUser(email="archi@buero.test", roles=["architect"]))
    db_session.add(StaffUser(email="weg@buero.test", roles=["ops"], active=False))
    db_session.commit()

    assert resolve_staff_login(db_session, {**MFA_CLAIMS, "amr": ["pwd"]}, settings) == LoginRefused("mfa")
    assert resolve_staff_login(db_session, {**MFA_CLAIMS, "email_verified": False}, settings) == LoginRefused(
        "email_unverified"
    )
    assert resolve_staff_login(
        db_session, {**MFA_CLAIMS, "email": "fremd@buero.test"}, settings
    ) == LoginRefused("unknown")
    assert resolve_staff_login(
        db_session, {**MFA_CLAIMS, "sub": "idp-9", "email": "weg@buero.test"}, settings
    ) == LoginRefused("inactive")


def test_roles_are_enforced(client: Any, login_as: Any) -> None:
    assert client.get("/api/v1/admin/flags").status_code == 401
    login_as("architect")
    assert client.get("/api/v1/admin/flags").json()["code"] == "forbidden"
    login_as("ops")
    assert client.get("/api/v1/admin/flags").status_code == 200


def test_session_and_logout(client: Any, login_as: Any, db_session: Any) -> None:
    user = login_as("ops", email="ops@buero.test")
    info = client.get("/api/v1/session").json()
    assert info["staff"]["email"] == "ops@buero.test"
    assert info["staff"]["roles"] == ["ops"]

    assert client.post("/api/v1/auth/staff/logout").status_code == 204
    assert client.get("/api/v1/session").json()["staff"] is None
    revoked = db_session.execute(
        select(StaffSession).where(StaffSession.staff_user_id == user.id)
    ).scalar_one()
    assert revoked.revoked_at is not None
    actions = set(db_session.execute(select(AuditLog.action)).scalars())
    assert {"staff.login", "staff.logout"} <= actions
