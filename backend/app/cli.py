"""Kommandozeile: `python -m app.cli <befehl>`.

worker                         Hintergrundjobs ausführen
openapi [datei]                OpenAPI-Beschreibung schreiben (Grundlage des Frontend-Clients)
staff-add EMAIL ROLLE [ROLLE] [--organisation NAME]  Mitarbeitende freischalten oder Rollen setzen
staff-deactivate EMAIL         Zugang sperren und Sitzungen beenden
org-create NAME ANZEIGENAME [--kind customer|operator]  Organisation anlegen (AN6; fremde erst nach E-A5)
org-member-add ORGANISATION EMAIL [--role admin|member]  Konto einer Organisation zuordnen
org-set-budget NAME [--budget USD|default] [--ocr-pages N|default]  Grenzen einer Organisation
org-list                       Organisationen mit Mitgliedern und Grenzen
storage-init                   Dateiverzeichnis anlegen und prüfen (im Migrate-Job)
cadastre-import [--commune X]  Kataster des Einzugsgebiets importieren (G1)
flag-set KEY [--role R] [--all] [--off]  Feature-Flag setzen (Plan 4.2)
plu-import [--commune X] [--force] [--from-dir D]  Planstand aus dem GPU importieren (G2)
legal-seed                     Vorläufige Einwilligungstexte (A, V) veröffentlichen (Plan A 3.10, V 3.5)
rules-extract (--chapter ID | --pending) [--force]  Zonenkapitel sofort auswerten (G2, kostet Token)
envelope-check [--commune X] [--zone Z] [--sample N]  Baurahmen über echte Parzellen prüfen (G3)
reference-check DATEI [--version N|all]  Auswertung an einer Referenzliste messen (G2, ohne Aufruf)
reference-import DATEI [--replace]  Referenzliste in die Verwaltung übernehmen
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from app.config import get_settings
from app.platform import audit, organisations
from app.platform.auth.context import Role
from app.platform.db import get_sessionmaker, utcnow
from app.platform.logging import configure_logging
from app.platform.models import Organisation, OrganisationMember, StaffSession, StaffUser


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


def _organisation_by_name(session: Any, name: str | None) -> Organisation:
    """Organisation nach Namen; ohne Namen die des Betreibers, angelegt beim ersten Konto (AN6)."""
    if name is None:
        org = organisations.operator_organisation(session, create=True)
        assert org is not None
        return org
    org = session.execute(select(Organisation).where(Organisation.name == name)).scalar_one_or_none()
    if org is None:
        sys.exit(f"{name}: Organisation nicht gefunden")
    return org


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
        # Jedes Konto gehört zu einer Organisation, sonst wirkt keine Rolle (AN6, PLAN_AN6_MANDANTEN 3.1)
        membership = session.get(OrganisationMember, user.id)
        org = (
            session.get(Organisation, membership.organisation_id)
            if membership is not None and args.organisation is None
            else _organisation_by_name(session, args.organisation)
        )
        assert org is not None
        role = args.org_role or (
            membership.role if membership else "admin" if org.kind == "operator" else "member"
        )
        try:
            organisations.set_membership(session, org, user, role, "cli")
        except organisations.OrganisationError as exc:
            sys.exit(f"{email}: {exc.code}")
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
        print(f"{email}: {', '.join(roles)} · {org.name} ({role})")


def cmd_org_create(args: argparse.Namespace) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        try:
            org = organisations.create_organisation(
                session, settings, name=args.name, display_name=args.display_name, kind=args.kind, actor="cli"
            )
        except organisations.OrganisationError as exc:
            hint = (
                " (EMPRISE_EXTERNAL_ORGANISATIONS, erst nach E-A5)" if exc.code.startswith("external") else ""
            )
            sys.exit(f"{args.name}: {exc.code}{hint}")
        session.commit()
        print(f"{org.name}: {org.id} ({org.kind})")


def cmd_org_member_add(args: argparse.Namespace) -> None:
    """Konto einer Organisation zuordnen; ein neues Konto bekommt die Rolle `architect`."""
    email = args.email.strip().lower()
    with get_sessionmaker()() as session:
        org = _organisation_by_name(session, args.organisation)
        user = session.execute(select(StaffUser).where(StaffUser.email == email)).scalar_one_or_none()
        if user is None:
            user = StaffUser(email=email, roles=["architect"], created_by="cli")
            session.add(user)
            session.flush()
        try:
            organisations.set_membership(session, org, user, args.role, "cli")
        except organisations.OrganisationError as exc:
            sys.exit(f"{email}: {exc.code}")
        session.commit()
        print(f"{email}: {org.name} ({args.role})")


def cmd_org_set_budget(args: argparse.Namespace) -> None:
    """Monatsbudget und Scan-Kontingent; `default` setzt die Vorgabe der Umgebung zurück (3.4)."""
    with get_sessionmaker()() as session:
        org = _organisation_by_name(session, args.name)
        before = {"budget_month_usd": org.budget_month_usd, "ocr_pages_month": org.ocr_pages_month}
        if args.budget is not None:
            org.budget_month_usd = None if args.budget == "default" else float(args.budget)
        if args.ocr_pages is not None:
            org.ocr_pages_month = None if args.ocr_pages == "default" else int(args.ocr_pages)
        audit.record(
            session,
            actor_type="system",
            actor_id="cli",
            action="organisation.budget",
            entity_type="organisation",
            entity_id=str(org.id),
            before=before,
            after={"budget_month_usd": org.budget_month_usd, "ocr_pages_month": org.ocr_pages_month},
        )
        session.commit()
        settings = get_settings()
        print(
            f"{org.name}: Budget {organisations.budget_limit(settings, org) or 'ohne eigene Grenze'} $ · "
            f"Scan {organisations.ocr_limit(settings, org) or 'ohne Grenze'} Seiten je Monat"
        )


def cmd_org_list(args: argparse.Namespace) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        for org in session.execute(select(Organisation).order_by(Organisation.name)).scalars():
            members = len(
                session.execute(
                    select(OrganisationMember.staff_user_id).where(
                        OrganisationMember.organisation_id == org.id
                    )
                ).all()
            )
            state = "aktiv" if org.active else "gesperrt"
            budget, pages = organisations.budget_limit(settings, org), organisations.ocr_limit(settings, org)
            print(
                f"{org.name:24} {org.kind:9} {state:8} {members:3} Mitglieder"
                f" · Budget {'ohne Grenze' if budget is None else f'{budget:g} $'}"
                f" · Scan {'ohne Grenze' if pages is None else f'{pages} Seiten'}"
            )


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
    """Dateiverzeichnis anlegen und mit einer Probe prüfen (im Migrate-Job, idempotent). Schlägt fehl, wenn
    der Nutzer des Containers (10001) nicht schreiben darf – dann das Verzeichnis auf dem Host freigeben."""
    import uuid

    from app.platform import storage

    root = storage.root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        ok = storage.roundtrip_check(f"ops-check/storage-init-{uuid.uuid4()}")
    except OSError as exc:
        sys.exit(f"Dateiverzeichnis {root} nicht beschreibbar: {exc}")
    if not ok:
        sys.exit(f"Dateiverzeichnis {root}: Probe gelesen, aber verändert")
    print(f"Dateiverzeichnis {root}: bereit")


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


def cmd_legal_seed(args: argparse.Namespace) -> None:
    """Vorläufige Einwilligungstexte der Module A und V veröffentlichen, falls noch keine Version besteht
    (docs/PLAN_A_ANFRAGE.md 3.10, PLAN_V 3.5). Endgültiger Wortlaut folgt über `POST /admin/legal-texts`."""
    from app.inquiry.texts import PROVISIONAL_TEXTS
    from app.platform import legal
    from app.platform.models import LegalText
    from app.submission.texts import PROVISIONAL_TEXTS as DESIGN_TEXTS

    with get_sessionmaker()() as session:
        for key, locale, title, body in [*PROVISIONAL_TEXTS, *DESIGN_TEXTS]:
            exists = session.execute(
                select(LegalText.id).where(LegalText.key == key, LegalText.locale == locale)
            ).first()
            if exists is not None:
                print(f"{key} ({locale}): bereits veröffentlicht, übersprungen")
                continue
            text = legal.publish(
                session, key=key, locale=locale, title=title, body=body, actor_type="system", actor_id="cli"
            )
            print(f"{key} ({locale}): Version {text.version} veröffentlicht")
        session.commit()


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

    from app.integrations.openrouter import OpenRouterExtractor
    from app.rules.extract import extract_chapter
    from app.rules.model_choice import effective_settings
    from app.rules.models import RegulationChapter

    with get_sessionmaker()() as session:
        # Dasselbe Modell wie der Worker: in der Verwaltung gewählt oder aus der Umgebung (VA09)
        settings = effective_settings(session, get_settings())

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
            sessions, settings, chapter_id, lambda: OpenRouterExtractor(settings), force=args.force
        )
        detail = outcome.detail or ""
        print(f"{chapter_id}: {outcome.status} {detail} ${outcome.cost_usd:.2f} {outcome.counts or ''}")


def cmd_reference_import(args: argparse.Namespace) -> None:
    """Referenzliste aus einer Datei in die Verwaltung übernehmen (VA10); vorhandene nur mit `--replace`.
    Ohne Anmeldung: als `system:reference-import`."""
    import json as json_module

    from app.rules import reference, reference_store

    path = Path(args.file)
    if not path.exists():
        path = reference.SEED_DIR / args.file
    data = json_module.loads(path.read_text(encoding="utf-8"))
    with get_sessionmaker()() as db:
        result = reference_store.import_list(db, data, args.replace, "system:reference-import", None)
    title = f"{result.document_title} {result.sector}"
    print(f"Referenzliste {title}: {result.entries_count} Einträge ({result.status})")


def cmd_reference_check(args: argparse.Namespace) -> None:
    """Auswertung an einer Referenzliste messen (PLAN_G2_VOLLSTAENDIGKEIT 3.10); ohne Aufruf des Modells."""
    from app.rules import reference
    from app.rules.domain.reference import measure

    path = Path(args.file)
    if not path.exists():
        path = reference.SEED_DIR / args.file
    ref = reference.load_file(path)
    print(f"Referenzliste: {ref.title}, Sektor {ref.sector}, {len(ref.entries)} Einträge ({ref.status})")
    with get_sessionmaker()() as session:
        versions = reference.versions_for(session, ref.sha256, ref.sector)
        if not versions:
            print("Dieses Dokument ist in dieser Instanz nicht ausgewertet.")
            return
        if args.version == "all":
            chosen = versions
        elif args.version:
            chosen = [v for v in versions if v.version == int(args.version)]
        else:
            chosen = versions[-1:]
        for version in chosen:
            open_passages, dismissed = reference.passages(version)
            measured = measure(ref.entries, reference.found_rules(session, version), open_passages, dismissed)
            print(reference.report(ref, version, measured))


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
    p_add.add_argument(
        "--organisation", help="Name der Organisation; ohne: die bisherige oder die des Betreibers"
    )
    p_add.add_argument("--org-role", choices=["admin", "member"])
    p_add.set_defaults(func=cmd_staff_add)
    p_org = sub.add_parser("org-create")
    p_org.add_argument("name", help="Kurzname aus Kleinbuchstaben, Ziffern und Bindestrich")
    p_org.add_argument("display_name")
    p_org.add_argument("--kind", choices=["customer", "operator"], default="customer")
    p_org.set_defaults(func=cmd_org_create)
    p_member = sub.add_parser("org-member-add")
    p_member.add_argument("organisation")
    p_member.add_argument("email")
    p_member.add_argument("--role", choices=["admin", "member"], default="admin")
    p_member.set_defaults(func=cmd_org_member_add)
    p_budget = sub.add_parser("org-set-budget")
    p_budget.add_argument("name")
    p_budget.add_argument("--budget", help="Dollar je Monat oder `default`")
    p_budget.add_argument("--ocr-pages", help="erkannte Seiten je Monat oder `default`")
    p_budget.set_defaults(func=cmd_org_set_budget)
    sub.add_parser("org-list").set_defaults(func=cmd_org_list)
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
    sub.add_parser("legal-seed").set_defaults(func=cmd_legal_seed)
    p_extract = sub.add_parser("rules-extract")
    target = p_extract.add_mutually_exclusive_group(required=True)
    target.add_argument("--chapter", help="ID des Zonenkapitels (Büro: Abdeckung)")
    target.add_argument("--pending", action="store_true", help="alle offenen oder gescheiterten Kapitel")
    p_extract.add_argument(
        "--force", action="store_true", help="auch bei unveränderter Eingabe neu auswerten"
    )
    p_extract.set_defaults(func=cmd_rules_extract)
    p_reference_import = sub.add_parser("reference-import")
    p_reference_import.add_argument("file", help="Pfad oder Name in app/rules/reference_seed")
    p_reference_import.add_argument("--replace", action="store_true")
    p_reference_import.set_defaults(func=cmd_reference_import)
    p_reference = sub.add_parser("reference-check")
    p_reference.add_argument("file", help="Pfad oder Name in app/rules/reference_seed")
    p_reference.add_argument("--version", help="Nummer der Regelwerksversion oder `all`; ohne: die neueste")
    p_reference.set_defaults(func=cmd_reference_check)
    p_envelope = sub.add_parser("envelope-check")
    p_envelope.add_argument("--commune", help="INSEE-Kennung, sonst alle importierten Gemeinden")
    p_envelope.add_argument("--zone", help="nur Parzellen in dieser Zone (z. B. Uh)")
    p_envelope.add_argument("--sample", type=int, help="gleichmäßige Stichprobe dieser Größe")
    p_envelope.set_defaults(func=cmd_envelope_check)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
