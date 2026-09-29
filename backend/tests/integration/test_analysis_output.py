"""Ausgabe der Analyse (AN5, docs/PLAN_AN5_AUSGABE.md) gegen PostGIS.

Grundlage wie in AN3: Parzelle 20 × 30 m aus einer DXF-Datei ohne Lage, Test-Reglement mit Zone Uh und
aufgezeichneter Modellantwort. Höhendienst und Géorisques antworten aus Aufzeichnungen (`test_site.py`).
Die App läuft als Produkt „Emprise Analyse“.
"""

import io
import itertools
import math
import uuid
from html import escape
from typing import Any

import ezdxf
import pytest
from sqlalchemy import func, select, text

from app.analysis import report, service
from app.analysis.jobs import analysis_report
from app.envelope.models import EnvelopeSheet
from app.platform import storage
from app.platform.db import utcnow
from app.platform.i18n import translate
from app.platform.jobs.registry import JobContext
from app.platform.models import Job
from app.rules.models import ProjectRegulation, SourceFile, SourcePage
from app.site.jobs import site_enrich
from app.site.models import Site
from tests.integration import test_analysis as an3
from tests.integration import test_site as g1
from tests.integration.test_rules_upload import customer_project

memory_storage = an3.memory_storage
settings = an3.settings
flags = an3.flags
architect = an3.architect
upload_project = an3.upload_project
app = an3.app
external = g1.external
with_plu = an3.with_plu

# Treillières, nahe der Lage der Testparzellen
LON, LAT = -1.6186, 47.3322
# Gitterkonvergenz dort: westlich des Mittelmeridians 3° O zeigt geografisch Nord im Gitter nach Nordost,
# etwa n · (λ − 3°) mit n = 0,7256 für Lambert-93, also 0,7256 × 4,62° ≈ 3,35°
GAMMA = 3.35
# Erste Exzentrizität² des Ellipsoids GRS80: Verhältnis der Krümmungsradien für Richtungen aus Länge/Breite
E2 = 0.00669438


def site_of(client: Any, project: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects/{project}/site")
    assert response.status_code == 200, response.json()
    body: dict[str, Any] = response.json()
    return body


def place(client: Any, project: str, **body: Any) -> Any:
    revision = body.pop("expected_revision", None) or site_of(client, project)["revision"]
    return client.put(
        f"/api/v1/projects/{project}/site/position",
        json={"lon": LON, "lat": LAT, "expected_revision": revision, **body},
    )


def enrich(db_session: Any) -> None:
    """Den jüngsten Auftrag für Gelände und Risiken ausführen; ältere Aufträge (Auswertung) bleiben liegen."""
    db_session.expire_all()
    queued = (
        db_session.execute(
            select(Job)
            .where(Job.kind == "site_enrich", Job.status == "queued")
            .order_by(Job.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert queued is not None
    site_enrich(JobContext(job_id=queued.id, attempt=1, project_id=queued.project_id), queued.payload)
    db_session.expire_all()


def jobs_of(db_session: Any, kind: str) -> int:
    db_session.expire_all()
    return int(db_session.execute(select(func.count()).select_from(Job).where(Job.kind == kind)).scalar_one())


def bearings(outline: dict[str, Any]) -> list[float]:
    """Richtung jeder Kante in Grad im Uhrzeigersinn von geografisch Nord, auf dem Ellipsoid gerechnet."""
    ring = outline["coordinates"][0]
    out = []
    for (lon1, lat1), (lon2, lat2) in itertools.pairwise(ring):
        phi = math.radians((lat1 + lat2) / 2)
        east = (lon2 - lon1) * math.cos(phi)
        north = (lat2 - lat1) * (1 - E2) / (1 - E2 * math.sin(phi) ** 2)
        out.append(math.degrees(math.atan2(east, north)) % 360)
    return out


def read_dxf(content: bytes) -> Any:
    return ezdxf.read(io.StringIO(content.decode()))


def run_report(project: str, input_hash: str, locale: str = "fr") -> dict[str, Any]:
    result = analysis_report(
        JobContext(job_id=uuid.uuid4(), attempt=1, project_id=uuid.UUID(project)),
        {"project_id": project, "input_hash": input_hash, "locale": locale},
    )
    assert result is not None
    return result


def correct(client: Any, project: str, body: dict[str, Any]) -> None:
    response = client.put(f"/api/v1/projects/{project}/rule-overrides", json=body)
    assert response.status_code == 200, response.json()


def html_of(db_session: Any, project: str, locale: Any) -> str:
    db_session.expire_all()
    data = service.report_data(db_session, uuid.UUID(project))
    return report.render_html(data, locale=locale, generated_at=utcnow(), report=report.report_hash(data))


def request_report(client: Any, project: str, locale: str = "fr") -> Any:
    return client.post(f"/api/v1/projects/{project}/analysis/report", json={"locale": locale})


# ---------------------------------------------------------------------------
# Projekte (3.1)
# ---------------------------------------------------------------------------


def test_projects_have_a_name_a_note_and_an_archive(client: Any, upload_project: str) -> None:
    listed = client.get("/api/v1/projects").json()
    assert [(p["id"], p["name"], p["archived_at"]) for p in listed] == [(upload_project, None, None)]

    changed = client.patch(
        f"/api/v1/projects/{upload_project}",
        json={"name": "  Maison Dupont ", "note": "Rendez-vous en mairie le 3 octobre"},
    )
    assert changed.status_code == 200, changed.json()
    assert (changed.json()["name"], changed.json()["note"]) == (
        "Maison Dupont",
        "Rendez-vous en mairie le 3 octobre",
    )
    details = client.get(f"/api/v1/projects/{upload_project}/details").json()
    assert details["note"] == "Rendez-vous en mairie le 3 octobre"
    assert client.get("/api/v1/projects").json()[0]["name"] == "Maison Dupont"

    # Archivieren blendet nur aus (E-AN5-7); nur genannte Felder ändern sich
    archived = client.patch(f"/api/v1/projects/{upload_project}", json={"archived": True}).json()
    assert archived["archived_at"] is not None and archived["name"] == "Maison Dupont"
    assert client.get("/api/v1/projects").json() == []
    assert [p["id"] for p in client.get("/api/v1/projects?archived=true").json()] == [upload_project]
    assert client.get(f"/api/v1/projects/{upload_project}/analysis").status_code == 200

    restored = client.patch(f"/api/v1/projects/{upload_project}", json={"archived": False, "name": ""})
    assert (restored.json()["archived_at"], restored.json()["name"]) == (None, None)
    assert [p["id"] for p in client.get("/api/v1/projects").json()] == [upload_project]

    too_long = client.patch(f"/api/v1/projects/{upload_project}", json={"name": "x" * 121})
    assert too_long.status_code == 422


# ---------------------------------------------------------------------------
# Lage einpassen (3.2) und Gelände (3.3)
# ---------------------------------------------------------------------------


def test_position_places_the_upload_rigidly_and_queries_terrain(
    client: Any, upload_project: str, db_session: Any, external: Any
) -> None:
    before = site_of(client, upload_project)
    assert before["georeferenced"] is False and before["placement"]["pivot_wgs84"] is None
    assert before["placement"]["map_rotation_deg"] == 0.0
    assert before["placement"]["pivot_local"] == [10.0, 15.0]

    placed = place(client, upload_project)
    assert placed.status_code == 200, placed.json()
    site = placed.json()
    assert site["georeferenced"] is True and site["revision"] == before["revision"] + 1
    lon, lat = site["placement"]["pivot_wgs84"]
    assert abs(lon - LON) < 1e-6 and abs(lat - LAT) < 1e-6
    # Achsen folgen Gitternord und erscheinen auf der Karte um −γ gedreht; das Blatt bleibt nach Norden
    assert site["placement"]["map_rotation_deg"] == pytest.approx(-GAMMA, abs=0.02)
    assert all(min(b % 90, 90 - b % 90) < 0.02 for b in bearings(site["outline_geojson"])), bearings(
        site["outline_geojson"]
    )
    assert site["source_info"]["position"]["method"] == "map"
    assert site["source_info"]["file_name"] == before["source_info"]["file_name"]
    # Starr: Maße und Einordnung der Kanten bleiben
    assert [(e["kind"], round(e["length_m"], 2)) for e in site["edges"]] == [
        (e["kind"], round(e["length_m"], 2)) for e in before["edges"]
    ]
    assert site["terrain"]["status"] == "pending"
    assert jobs_of(db_session, "site_enrich") == 1

    enrich(db_session)
    terrain = site_of(client, upload_project)["terrain"]
    assert terrain["status"] == "ok" and terrain["samples"] >= 9

    # Nachdrehen um 90° am selben Ort: Drehpunkt bleibt, Kantenrichtungen drehen mit
    turned = place(client, upload_project, rotation_deg=90).json()
    assert turned["source_info"]["position"]["rotation_deg"] == 90.0
    lon, lat = turned["placement"]["pivot_wgs84"]
    assert abs(lon - LON) < 1e-6 and abs(lat - LAT) < 1e-6
    for old, new in zip(site["edges"], turned["edges"], strict=True):
        assert (new["normal_azimuth_deg"] - old["normal_azimuth_deg"]) % 360 == pytest.approx(90.0, abs=0.01)
    assert jobs_of(db_session, "site_enrich") == 2

    stale = place(client, upload_project, expected_revision=before["revision"])
    assert (stale.status_code, stale.json()["code"]) == (409, "revision_conflict")


def test_position_turns_clockwise_from_sheet_north(client: Any, upload_project: str) -> None:
    """Abnahme 1: Nach Δ = 30° zeigt die Kante, die auf dem Blatt nach Norden lief, geografisch nach 30°."""
    before = site_of(client, upload_project)
    site = place(client, upload_project, rotation_deg=30).json()
    assert all(abs(b % 90 - 30) < 0.02 for b in bearings(site["outline_geojson"]))
    # Die Kante (20,0)–(20,30) läuft auf dem Blatt nach Norden, ihre Normale zeigt nach Osten
    running_north = next(e for e in before["edges"] if abs(e["normal_azimuth_deg"] - 90) < 0.01)
    turned = next(e for e in site["edges"] if e["seq"] == running_north["seq"])
    assert turned["length_m"] == pytest.approx(running_north["length_m"], abs=0.001)
    # Normale im Gitter: 90° + 30° + γ
    assert turned["normal_azimuth_deg"] == pytest.approx(120 + GAMMA, abs=0.02)


def test_cadastral_sites_cannot_be_moved(client: Any, upload_project: str, db_session: Any) -> None:
    db_session.execute(text("UPDATE site SET origin = 'parcel'"))
    db_session.commit()
    refused = place(client, upload_project)
    assert (refused.status_code, refused.json()["code"]) == (409, "site_position_parcel")


# ---------------------------------------------------------------------------
# DXF und GeoJSON (3.4, 3.5)
# ---------------------------------------------------------------------------


def test_exports_follow_the_position(
    client: Any, upload_project: str, db_session: Any, settings: Any, external: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    client.patch(f"/api/v1/projects/{upload_project}", json={"name": "Maison Dupont-Lefèvre"})
    base = f"/api/v1/projects/{upload_project}/analysis/export"

    local = client.get(f"{base}/dxf?variant=local")
    assert local.status_code == 200 and local.headers["content-type"].startswith("application/dxf")
    disposition = local.headers["content-disposition"]
    assert "Maison-Dupont-Lefevre_" in disposition and disposition.endswith('_local.dxf"')
    document = read_dxf(local.content)
    layers = {layer.dxf.name for layer in document.layers}
    assert {"PARCELLE", "GABARIT_LARGE_COURBES", "GABARIT_LARGE_VOLUME", "COUPE"} <= layers
    notes = " ".join(entity.dxf.text for entity in document.modelspace().query("TEXT"))
    assert "sans position geographique" in notes and "altitude du terrain inconnue" in notes

    for suffix in ("dxf?variant=L93", "geojson"):
        refused = client.get(f"{base}/{suffix}")
        assert (refused.status_code, refused.json()["code"]) == (409, "export_not_georeferenced")

    assert place(client, upload_project).status_code == 200
    enrich(db_session)

    l93 = client.get(f"{base}/dxf?variant=L93")
    assert l93.status_code == 200 and l93.headers["content-disposition"].endswith('_L93.dxf"')
    document = read_dxf(l93.content)
    parcel = document.modelspace().query('LWPOLYLINE[layer=="PARCELLE"]').first
    x, y = parcel.get_points("xy")[0]
    assert 300_000 < x < 400_000 and 6_650_000 < y < 6_750_000
    notes = " ".join(entity.dxf.text for entity in document.modelspace().query("TEXT"))
    assert "m NGF" in notes and "ajustee a la main" in notes
    # Z in m NGF: Höhenlinien des Gabarits liegen über dem Gelände (Aufzeichnung um 52,8 m)
    elevations = {
        round(entity.dxf.elevation, 1)
        for entity in document.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer.startswith("GABARIT_")
    }
    assert elevations and min(elevations) > 50

    geojson = client.get(f"{base}/geojson")
    assert geojson.status_code == 200 and geojson.headers["content-type"] == "application/geo+json"
    collection = geojson.json()
    assert collection["type"] == "FeatureCollection"
    by_layer = {feature["properties"]["layer"]: feature for feature in collection["features"]}
    assert {"PARCELLE", "GABARIT_LARGE_COURBES", "COUPE"} <= set(by_layer)
    lon, lat = by_layer["PARCELLE"]["geometry"]["coordinates"][0][0]
    assert abs(lon - LON) < 0.001 and abs(lat - LAT) < 0.001
    assert by_layer["GABARIT_LARGE_COURBES"]["properties"]["z_ngf_top"] > 50

    # Der Bericht nennt Lage und Risiken mit den Begriffen der Oberfläche, nicht mit denen der Quelle
    html = html_of(db_session, upload_project, "de")
    assert escape(translate("report.site.position_map", "de")) in html
    assert escape(translate("risk.kind.clay_shrink_swell", "de")) in html
    assert escape(translate("risk.level.low", "de")) in html
    assert "Exposition" not in html


def test_customers_have_no_output(client: Any, flags: None, login_as: Any, db_session: Any) -> None:
    customer = customer_project(client, db_session)
    login_as("architect")
    for method, path in (
        ("get", "analysis/export/dxf"),
        ("get", "analysis/export/geojson"),
        ("get", "analysis/report"),
        ("get", "details"),
    ):
        assert getattr(client, method)(f"/api/v1/projects/{customer}/{path}").status_code == 404
    assert request_report(client, customer).status_code == 404
    assert client.patch(f"/api/v1/projects/{customer}", json={"name": "X"}).status_code == 404


# ---------------------------------------------------------------------------
# Bericht (3.6)
# ---------------------------------------------------------------------------


def test_report_is_created_once_per_state_and_language(
    client: Any, upload_project: str, db_session: Any, settings: Any, memory_storage: dict[str, bytes]
) -> None:
    with_plu(client, upload_project, db_session, settings)
    missing = client.get(f"/api/v1/projects/{upload_project}/analysis/report")
    assert (missing.status_code, missing.json()["code"]) == (409, "report_not_ready")

    first = request_report(client, upload_project)
    assert first.status_code == 202, first.json()
    pending = first.json()
    assert pending["status"] == "pending" and pending["input_hash"].startswith("sha256:")
    assert request_report(client, upload_project).json()["job_id"] == pending["job_id"]
    assert jobs_of(db_session, service.REPORT_JOB) == 1

    result = run_report(upload_project, pending["input_hash"])
    assert result["matched_request"] is True and result["size_bytes"] > 5000
    assert run_report(upload_project, pending["input_hash"])["skipped"] == "already_generated"

    ready = request_report(client, upload_project)
    assert ready.status_code == 200
    assert (ready.json()["status"], ready.json()["input_hash"]) == ("ready", pending["input_hash"])
    assert jobs_of(db_session, service.REPORT_JOB) == 1

    download = client.get(f"/api/v1/projects/{upload_project}/analysis/report?locale=fr")
    assert download.status_code == 200 and download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")
    assert download.headers["content-disposition"].endswith('_fr.pdf"')
    key = service.report_key(uuid.UUID(upload_project), pending["input_hash"], "fr")
    assert memory_storage[key] == download.content
    assert client.get(f"/api/v1/projects/{upload_project}/analysis/report?locale=de").status_code == 409

    # Was der Bericht zeigt, ändert die Prüfsumme: Notiz, Parameter, Korrekturen
    client.patch(f"/api/v1/projects/{upload_project}", json={"note": "Variante avec garage"})
    noted = request_report(client, upload_project).json()
    assert noted["status"] == "pending" and noted["input_hash"] != pending["input_hash"]
    client.put(
        f"/api/v1/projects/{upload_project}/rule-overrides",
        json={
            "zone_code": "Uh",
            "kind": "parking",
            "building_kind": "any",
            "status": "effective",
            "params": {"spaces_per_dwelling": 2},
            "note": "Article 12 – oublié par la lecture automatique",
        },
    )
    corrected = request_report(client, upload_project).json()
    assert corrected["input_hash"] not in (pending["input_hash"], noted["input_hash"])
    # Ein Auftrag zu einem überholten Stand setzt den aktuellen
    late = run_report(upload_project, noted["input_hash"])
    assert (late["matched_request"], late["input_hash"]) == (False, corrected["input_hash"])
    assert client.get(f"/api/v1/projects/{upload_project}/analysis/report?locale=fr").status_code == 200


@pytest.mark.parametrize("locale", ["de", "fr"])
def test_report_shows_rules_corrections_and_open_points(
    client: Any, upload_project: str, db_session: Any, settings: Any, locale: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    client.patch(
        f"/api/v1/projects/{upload_project}", json={"name": "Maison <Dupont>", "note": "Variante avec garage"}
    )
    correct(
        client,
        upload_project,
        {
            "zone_code": "Uh",
            "kind": "parking",
            "building_kind": "any",
            "status": "effective",
            "params": {"spaces_per_dwelling": 2},
            "note": "Article 12 – oublié par la lecture automatique",
        },
    )
    html = html_of(db_session, upload_project, locale)
    sections = ("figures", "plan", "gabarit", "cut_A", "cut_B", "rules", "assumptions", "site", "documents")
    for section in sections:
        assert escape(translate(f"report.section.{section}", locale)) in html, section
    assert "Maison &lt;Dupont&gt;" in html and "Variante avec garage" in html
    assert escape(translate("report.rules.corrections", locale)) in html
    assert "Article 12 – oublié par la lecture automatique" in html
    # Werte lesen sich wie in der Oberfläche (rules/format.ts), nicht als Parameterliste
    assert escape(translate("rule_value.spacesPerDwelling", locale, value="2")) in html
    assert "spaces_per_dwelling" not in html and "rule_value." not in html
    assert "PLUi Erdre et Gesvres" in html
    # Lageplan, Gabarit in Höhenstufen, zwei Schnitte
    assert html.count("<svg") >= 4

    # Ohne Höhe kein Gabarit; die Regel steht als offener Punkt mit der Begründung des Büros
    correct(
        client,
        upload_project,
        {
            "zone_code": "Uh",
            "kind": "max_height",
            "status": "unknown",
            "note": "Hauteur à vérifier en mairie",
        },
    )
    html = html_of(db_session, upload_project, locale)
    assert escape(translate("report.rules.open", locale)) in html
    assert "Hauteur à vérifier en mairie" in html
    assert escape(translate("report.section.cut_A", locale)) not in html


@pytest.mark.parametrize("locale", ["de", "fr"])
def test_report_marks_what_comes_from_a_scan(
    client: Any, upload_project: str, db_session: Any, settings: Any, locale: Any
) -> None:
    """AN7 (PLAN_AN7_SCAN 3.7): Regeln „S. n (Scan)“, Dokument „Scan, Text erkannt“, Parzelle
    nachgezeichnet."""
    with_plu(client, upload_project, db_session, settings)
    link = db_session.execute(
        select(ProjectRegulation).where(ProjectRegulation.project_id == uuid.UUID(upload_project))
    ).scalar_one()
    source = db_session.execute(
        select(SourceFile).where(SourceFile.land_use_plan_id == link.land_use_plan_id)
    ).scalar_one()
    pages = list(
        db_session.execute(select(SourcePage).where(SourcePage.source_file_id == source.id)).scalars()
    )
    # Als wäre jede Seite per Texterkennung gelesen
    source.empty_pages = [p.page for p in pages]
    source.ocr_state, source.ocr_finished_at = "done", utcnow()
    for page in pages:
        page.ocr_confidence = 91.0
    site = db_session.execute(select(Site).where(Site.project_id == uuid.UUID(upload_project))).scalar_one()
    trace = {"file_name": "extrait-cadastral.jpg", "page": 1, "scale_method": "calibrated", "reference_m": 20}
    site.source_info = {**site.source_info, "trace": trace}
    db_session.commit()

    html = html_of(db_session, upload_project, locale)
    scan = translate("report.scan", locale)
    assert f"({escape(scan)})" in html
    assert escape(translate("report.documents.ocr", locale, pages=len(pages))) in html
    assert escape(translate("report.origin_site.traced", locale)) in html
    assert "extrait-cadastral.jpg" in html
    assert escape(translate("report.site.scale_calibrated", locale, length="20,00 m")) in html


def test_deleting_the_project_removes_its_files(
    client: Any,
    upload_project: str,
    db_session: Any,
    settings: Any,
    memory_storage: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storage, "delete", lambda key: memory_storage.pop(key, None))
    with_plu(client, upload_project, db_session, settings)
    pending = request_report(client, upload_project).json()
    run_report(upload_project, pending["input_hash"])
    sheet_key = f"envelope/{upload_project}/sheet.pdf"
    memory_storage[sheet_key] = b"%PDF-1.7"
    db_session.add(
        EnvelopeSheet(
            project_id=uuid.UUID(upload_project),
            input_hash="sha256:" + "0" * 64,
            engine_version="test",
            storage_key=sheet_key,
            size_bytes=8,
        )
    )
    db_session.commit()
    report_key = service.report_key(uuid.UUID(upload_project), pending["input_hash"], "fr")
    assert report_key in memory_storage

    assert client.delete(f"/api/v1/projects/{upload_project}").status_code == 204
    assert report_key not in memory_storage and sheet_key not in memory_storage
