"""Kommandozeile: `python -m app.cli <befehl>`.

worker                         Hintergrundjobs ausführen
openapi [datei]                OpenAPI-Beschreibung schreiben (Grundlage des Frontend-Clients)
staff-add EMAIL ROLLE [ROLLE]  Mitarbeitende freischalten oder Rollen setzen
staff-deactivate EMAIL         Zugang sperren und Sitzungen beenden
local-storage-init             Nur lokal: Bucket anlegen
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.platform import audit
from app.platform.auth.context import Role
from app.platform.db import get_sessionmaker, utcnow
from app.platform.logging import configure_logging
from app.platform.models import StaffSession, StaffUser


def cmd_worker(args: argparse.Namespace) -> None:
    import app.registry  # noqa: F401
    from app.main import init_sentry
    from app.platform.jobs.worker import run_worker

    settings = get_settings()
    configure_logging(settings.log_level, json=settings.env != "local")
    init_sentry(settings)
    run_worker(settings)


def cmd_openapi(args: argparse.Namespace) -> None:
    from app.main import create_app

    spec = create_app().openapi()
    output = json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.file:
        Path(args.file).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)


def cmd_staff_add(args: argparse.Namespace) -> None:
    roles = sorted({Role(r).value for r in args.roles})
    email = args.email.strip().lower()
    with get_sessionmaker()() as session:
        user = session.execute(select(StaffUser).where(StaffUser.email == email)).scalar_one_or_none()
        before = {"roles": user.roles, "active": user.active} if user else None
        if user is None:
            user = StaffUser(email=email, roles=roles, created_by="cli")
            session.add(user)
        else:
            user.roles = roles
            user.active = True
        session.flush()
        audit.record(
            session,
            actor_type="system",
            actor_id="cli",
            action="staff_user.put",
            entity_type="staff_user",
            entity_id=str(user.id),
            before=before,
            after={"roles": roles, "active": True},
        )
        session.commit()
        print(f"{email}: {', '.join(roles)}")


def cmd_staff_deactivate(args: argparse.Namespace) -> None:
    email = args.email.strip().lower()
    with get_sessionmaker()() as session:
        user = session.execute(select(StaffUser).where(StaffUser.email == email)).scalar_one_or_none()
        if user is None:
            sys.exit(f"{email}: nicht gefunden")
        user.active = False
        session.execute(
            update(StaffSession)
            .where(StaffSession.staff_user_id == user.id, StaffSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        audit.record(
            session,
            actor_type="system",
            actor_id="cli",
            action="staff_user.deactivate",
            entity_type="staff_user",
            entity_id=str(user.id),
            after={"active": False},
        )
        session.commit()
        print(f"{email}: gesperrt")


def cmd_local_storage_init(args: argparse.Namespace) -> None:
    """Nur lokal: Bucket mit Versionierung anlegen. In staging/production entsteht er per OpenTofu."""
    from app.platform import storage

    settings = get_settings()
    if settings.env not in ("local", "test"):
        sys.exit("local-storage-init ist nur für local und test gedacht")
    client = storage.client()
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        client.create_bucket(Bucket=settings.s3_bucket)
    client.put_bucket_versioning(Bucket=settings.s3_bucket, VersioningConfiguration={"Status": "Enabled"})
    print(f"bucket {settings.s3_bucket}: bereit")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("worker").set_defaults(func=cmd_worker)
    p_openapi = sub.add_parser("openapi")
    p_openapi.add_argument("file", nargs="?")
    p_openapi.set_defaults(func=cmd_openapi)
    p_add = sub.add_parser("staff-add")
    p_add.add_argument("email")
    p_add.add_argument("roles", nargs="+", choices=[r.value for r in Role])
    p_add.set_defaults(func=cmd_staff_add)
    p_deactivate = sub.add_parser("staff-deactivate")
    p_deactivate.add_argument("email")
    p_deactivate.set_defaults(func=cmd_staff_deactivate)
    sub.add_parser("local-storage-init").set_defaults(func=cmd_local_storage_init)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
