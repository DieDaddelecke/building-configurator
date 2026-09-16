"""Kommandozeile: `python -m app.cli <befehl>`.

worker                         Hintergrundjobs ausführen
openapi [datei]                OpenAPI-Beschreibung schreiben (Grundlage des Frontend-Clients)
staff-add EMAIL ROLLE [ROLLE]  Mitarbeitende freischalten oder Rollen setzen
staff-deactivate EMAIL         Zugang sperren und Sitzungen beenden
storage-init                   Bucket mit Versionierung anlegen, falls er fehlt
cadastre-import [--commune X]  Kataster des Einzugsgebiets importieren (G1)
flag-set KEY [--role R] [--all] [--off]  Feature-Flag setzen (Plan 4.2)
plu-import [--commune X] [--force] [--from-dir D]  Planstand aus dem GPU importieren (G2)
rules-extract (--chapter ID | --pending) [--force]  Zonenkapitel sofort auswerten (G2, kostet Token)
envelope-check [--commune X] [--zone Z] [--sample N]  Baurahmen über echte Parzellen prüfen (G3)
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


def cmd_storage_init(args: argparse.Namespace) -> None:
    """Bucket mit Versionierung anlegen, falls er fehlt (idempotent).

    Für selbst betriebene S3-Dienste (MinIO lokal, SeaweedFS auf Unraid). Bei einem verwalteten
    Anbieter legt OpenTofu den Bucket an; der Befehl ändert dann nichts.
    """
    from app.platform import storage

    settings = get_settings()
    client = storage.client()
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        client.create_bucket(Bucket=settings.s3_bucket)
    client.put_bucket_versioning(Bucket=settings.s3_bucket, VersioningConfiguration={"Status": "Enabled"})
    print(f"bucket {settings.s3_bucket}: bereit")


def cmd_cadastre_import(args: argparse.Namespace) -> None:
    """Kataster des Einzugsgebiets sofort importieren (G1). Ohne Angabe: EMPRISE_CADASTRE_COMMUNES."""
    from app.integrations.etalab_cadastre import CadastreSource, DirectoryCadastre, EtalabCadastre
    from app.integrations.http import new_client
    from app.integrations.ign_bdtopo import DirectoryRoads, GeoplateformeRoads, RoadSource
    from app.site.cadastre_import import import_commune

    settings = get_settings()
    communes = args.commune or settings.cadastre_communes
    failed = False
    with new_client(settings) as client, get_sessionmaker()() as session:
        source: CadastreSource = (
            DirectoryCadastre(Path(args.from_dir), args.release)
            if args.from_dir
            else EtalabCadastre(client, settings)
        )
        roads: RoadSource = (
            DirectoryRoads(Path(args.from_dir)) if args.from_dir else GeoplateformeRoads(client, settings)
        )
        for commune in communes:
            result = import_commune(session, source, settings, commune, force=args.force, roads=roads)
            failed = failed or result.status == "failed"
            print(f"{commune}: {result.status} {result.release or ''} {result.counts or result.error or ''}")
    if failed:
        sys.exit(1)


def cmd_flag_set(args: argparse.Namespace) -> None:
    """Feature-Flag setzen (Einführung intern → Beta → öffentlich, Plan 4.2), mit Audit wie die Admin-API."""
    from app.platform.flags import FLAG_KEY
    from app.platform.models import FeatureFlag

    if not FLAG_KEY.match(args.key):
        sys.exit(f"{args.key}: ungültiger Schlüssel")
    with get_sessionmaker()() as session:
        flag = session.get(FeatureFlag, args.key)
        before = (
            {"enabled_for_all": flag.enabled_for_all, "enabled_roles": list(flag.enabled_roles)}
            if flag
            else None
        )
        if flag is None:
            flag = FeatureFlag(key=args.key, created_by="cli")
            session.add(flag)
        if args.description is not None:
            flag.description = args.description
        flag.enabled_for_all = bool(args.all) and not args.off
        flag.enabled_roles = [] if args.off else sorted({Role(r).value for r in args.role or []})
        if args.off:
            flag.enabled_project_ids = []
        flag.updated_at = utcnow()
        flag.updated_by = "cli"
        roles = list(flag.enabled_roles)
        after = {"enabled_for_all": flag.enabled_for_all, "enabled_roles": roles}
        audit.record(
            session,
            actor_type="system",
            actor_id="cli",
            action="feature_flag.put",
            entity_type="feature_flag",
            entity_id=args.key,
            before=before,
            after=after,
        )
        session.commit()
        print(f"{args.key}: alle={flag.enabled_for_all} rollen={', '.join(roles) or '–'}")


def cmd_plu_import(args: argparse.Namespace) -> None:
    """Planstand je Gemeinde importieren; die Auswertung der Kapitel übernimmt danach der Worker."""
    from app.integrations.http import new_client
    from app.rules.plan_import import ApiGpu, DirectoryGpu, GpuSource, import_commune

    settings = get_settings()
    communes = args.commune or settings.cadastre_communes
    with new_client(settings) as client, get_sessionmaker()() as session:
        source: GpuSource = DirectoryGpu(Path(args.from_dir)) if args.from_dir else ApiGpu(client, settings)
        for commune in communes:
            result = import_commune(session, source, settings, commune, force=args.force)
            notes = "; ".join(result.notes)
            print(f"{commune}: {result.status} Kapitel={result.chapters} Zonen={result.zones} {notes}")


def cmd_rules_extract(args: argparse.Namespace) -> None:
    """Kapitel synchron auswerten (Betrieb, Referenzmenge), ohne Worker. Die Ausgabe nennt die Kosten."""
    import uuid
    from contextlib import contextmanager

    from sqlalchemy import select

    from app.integrations.claude import ClaudeExtractor
    from app.rules.extract import extract_chapter
    from app.rules.models import RegulationChapter

    settings = get_settings()

    @contextmanager
    def sessions():  # type: ignore[no-untyped-def]
        session = get_sessionmaker()()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    with get_sessionmaker()() as session:
        if args.chapter:
            ids = [uuid.UUID(args.chapter)]
        else:
            ids = list(
                session.execute(
                    select(RegulationChapter.id).where(RegulationChapter.status.in_(["pending", "failed"]))
                ).scalars()
            )
    for chapter_id in ids:
        outcome = extract_chapter(
            sessions, settings, chapter_id, lambda: ClaudeExtractor(settings), force=args.force
        )
        detail = outcome.detail or ""
        print(f"{chapter_id}: {outcome.status} {detail} ${outcome.cost_usd:.2f} {outcome.counts or ''}")


def cmd_envelope_check(args: argparse.Namespace) -> None:
    """Baurahmen für echte Parzellen ableiten, ohne etwas zu speichern (Plan G3 6.2 Punkt 2).

    Prüft auf Ausnahmen, ungültige Geometrien und die Schachtelung der Konturen und misst die Dauer.
    Jede Parzelle läuft in einer eigenen Transaktion, die am Ende zurückgerollt wird; Projekte, Grundstücke
    und Jobs bleiben also nicht zurück.
    """
    import statistics
    import time
    import uuid
    from collections import Counter

    from sqlalchemy import text as sql_text

    import app.registry  # noqa: F401  Jobarten registrieren; `form_site` legt `site_enrich` an
    from app.envelope import service as envelope_service
    from app.platform.models import Project
    from app.site import service as site_service
    from app.site.models import RefParcel

    configure_logging("WARNING", json=False)
    factory = get_sessionmaker()
    with factory() as session:
        query = select(RefParcel.idu).order_by(RefParcel.idu)
        if args.commune:
            query = query.where(RefParcel.commune_insee == args.commune)
        idus = list(session.execute(query).scalars())
        if args.zone:
            in_zone = set(
                session.execute(
                    sql_text(
                        "SELECT p.idu FROM ref_parcel p JOIN zone z ON ST_Intersects(z.geometry, p.geometry) "
                        "WHERE z.code = :zone"
                    ),
                    {"zone": args.zone},
                ).scalars()
            )
            idus = [idu for idu in idus if idu in in_zone]
    if args.sample and args.sample < len(idus):
        step = len(idus) / args.sample
        idus = [idus[int(index * step)] for index in range(args.sample)]

    statuses: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    durations: list[float] = []
    problems: list[str] = []
    for idu in idus:
        session = factory()
        started = time.perf_counter()
        try:
            project = Project(access_token_hash=uuid.uuid4().bytes, created_by="envelope-check")
            session.add(project)
            session.flush()
            site_service.form_site(session, project.id, [idu], "envelope-check")
            envelope, _data = envelope_service.build_envelope(session, project.id)
            durations.append((time.perf_counter() - started) * 1000)
            statuses[envelope.status] += 1
            warnings.update(envelope.warnings)
            lenient = envelope.contours["lenient"]
            strict = envelope.contours["strict"]
            if strict.area_m2 > lenient.area_m2 + 0.01:
                problems.append(f"{idu}: engste Kontur größer als die weiteste")
            if lenient.area_m2 > envelope.area_m2 + 0.01:
                problems.append(f"{idu}: Kontur größer als das Grundstück")
            if not strict.complete:
                statuses["strict_incomplete"] += 1
        except Exception as exc:  # Ausnahmen sind hier das Ergebnis des Laufs
            problems.append(f"{idu}: {type(exc).__name__}: {exc}")
        finally:
            session.rollback()
            session.close()

    print(f"Parzellen: {len(idus)} (Gemeinde {args.commune or 'alle'}, Zone {args.zone or 'alle'})")
    for name, count in sorted(statuses.items()):
        print(f"  {name}: {count}")
    if durations:
        ordered = sorted(durations)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        print(f"  Dauer: Median {statistics.median(ordered):.0f} ms, p95 {p95:.0f} ms")
    for code, count in warnings.most_common():
        print(f"  Hinweis {code}: {count}")
    for problem in problems[:20]:
        print(f"  FEHLER {problem}")
    print(f"Fehler insgesamt: {len(problems)}")
    if problems:
        sys.exit(1)


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
    sub.add_parser("storage-init").set_defaults(func=cmd_storage_init)
    p_import = sub.add_parser("cadastre-import")
    p_import.add_argument("--commune", action="append", help="INSEE-Code, mehrfach möglich")
    p_import.add_argument("--force", action="store_true", help="Stand erneut importieren, Mengenprüfung aus")
    p_import.add_argument("--from-dir", help="Ordner mit cadastre-<insee>-<datensatz>.json.gz statt Download")
    p_import.add_argument("--release", default="local", help="Standbezeichnung bei --from-dir")
    p_import.set_defaults(func=cmd_cadastre_import)
    p_flag = sub.add_parser("flag-set")
    p_flag.add_argument("key")
    p_flag.add_argument("--role", action="append", choices=[r.value for r in Role], help="mehrfach möglich")
    p_flag.add_argument("--all", action="store_true", help="für alle freischalten")
    p_flag.add_argument("--off", action="store_true", help="ganz abschalten")
    p_flag.add_argument("--description")
    p_flag.set_defaults(func=cmd_flag_set)
    p_plu = sub.add_parser("plu-import")
    p_plu.add_argument("--commune", action="append", help="INSEE-Code, mehrfach möglich")
    p_plu.add_argument(
        "--force", action="store_true", help="neu laden, am Ort aktualisieren; Korrekturen bleiben"
    )
    p_plu.add_argument("--from-dir", help="Ordner mit aufgezeichneten GPU-Antworten und Planunterlagen")
    p_plu.set_defaults(func=cmd_plu_import)
    p_extract = sub.add_parser("rules-extract")
    target = p_extract.add_mutually_exclusive_group(required=True)
    target.add_argument("--chapter", help="ID des Zonenkapitels (Büro: Abdeckung)")
    target.add_argument("--pending", action="store_true", help="alle offenen oder gescheiterten Kapitel")
    p_extract.add_argument(
        "--force", action="store_true", help="auch bei unveränderter Eingabe neu auswerten"
    )
    p_extract.set_defaults(func=cmd_rules_extract)
    p_envelope = sub.add_parser("envelope-check")
    p_envelope.add_argument("--commune", help="INSEE-Kennung, sonst alle importierten Gemeinden")
    p_envelope.add_argument("--zone", help="nur Parzellen in dieser Zone (z. B. Uh)")
    p_envelope.add_argument("--sample", type=int, help="gleichmäßige Stichprobe dieser Größe")
    p_envelope.set_defaults(func=cmd_envelope_check)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
