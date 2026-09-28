"""Parzelle aus einer Datei und Projekte am Architektenkonto (AN1, docs/PLAN_AN1_PARZELLE.md).

Die Dateien entstehen im Test: ein DXF mit zwei geschlossenen Polylinien, GeoJSON in Lambert-93 und in
WGS84. Damit ist geprüft, was der Architekt mitbringt, ohne Beispieldateien im Repository.
"""

import io
import json
import uuid
from collections.abc import Callable
from typing import Any

import ezdxf
import pytest
from sqlalchemy import select, text

from app.platform.jobs import enqueue
from app.platform.jobs.worker import run_one
from app.platform.models import FeatureFlag, Project
from tests.site_pdf_support import extract_pdf, plan_pdf

# Rechteck 20 × 30 m, lokal gezeichnet (ohne geografischen Bezug)
LOCAL_RING = [(0.0, 0.0), (20.0, 0.0), (20.0, 30.0), (0.0, 30.0)]
# Dasselbe Rechteck in Lambert-93 bei Treillières
L93_RING = [
    (355_000.0, 6_705_000.0),
    (355_020.0, 6_705_000.0),
    (355_020.0, 6_705_030.0),
    (355_000.0, 6_705_030.0),
]
# Ein Viereck in WGS84 (rund 25 × 35 m nahe Treillières)
WGS84_RING = [(-1.597000, 47.281800), (-1.596670, 47.281800), (-1.596670, 47.282115), (-1.597000, 47.282115)]


def dxf_bytes(*rings: tuple[list[tuple[float, float]], str], units: int = 6) -> bytes:
    document = ezdxf.new("R2010")
    document.header["$INSUNITS"] = units
    space = document.modelspace()
    for points, layer in rings:
        if not document.layers.has_entry(layer):
            document.layers.add(layer)
        space.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    stream = io.StringIO()
    document.write(stream)
    return stream.getvalue().encode("utf-8")


def geojson_bytes(ring: list[tuple[float, float]], name: str = "AD 65") -> bytes:
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name},
                "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in [*ring, ring[0]]]]},
            }
        ],
    }
    return json.dumps(document).encode("utf-8")


@pytest.fixture
def enabled(db_session: Any) -> None:
    db_session.add(FeatureFlag(key="site_selection", enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def project(client: Any, enabled: None) -> str:
    """Kundenprojekt über das Cookie; der Upload braucht kein Kataster."""
    return str(client.post("/api/v1/projects").json()["id"])


def upload(client: Any, project: str, name: str, data: bytes, **form: Any) -> Any:
    return client.post(
        f"/api/v1/projects/{project}/site/upload",
        files={"file": (name, data, "application/octet-stream")},
        data={"address_label": "Parzelle aus Datei", **form},
    )


# ---------------------------------------------------------------------------
# Datei lesen
# ---------------------------------------------------------------------------


def test_geojson_in_lambert93_forms_a_georeferenced_site(client: Any, project: str) -> None:
    response = upload(client, project, "parzelle.geojson", geojson_bytes(L93_RING))
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["candidates"] == []
    site = body["site"]
    assert site["origin"] == "upload" and site["georeferenced"] is True
    assert site["area_m2"] == pytest.approx(600.0)
    assert site["source_info"]["crs"] == "EPSG:2154"
    assert site["source_info"]["file_name"] == "parzelle.geojson"
    assert len(site["source_info"]["sha256"]) == 64
    assert site["source_info"]["name"] == "AD 65"
    assert site["outline_geojson"]["type"] == "Polygon"
    assert [e["kind"] for e in site["edges"]] == ["other"] * 4
    assert site["notices"] == ["notice.upload"]


def test_geojson_in_wgs84_is_converted_to_metres(client: Any, project: str) -> None:
    site = upload(client, project, "parzelle.json", geojson_bytes(WGS84_RING)).json()["site"]
    assert site["georeferenced"] is True and site["source_info"]["crs"] == "EPSG:4326"
    # rund 25 × 35 m; die genaue Fläche hängt an der Projektion
    assert 700 < site["area_m2"] < 1000
    assert len(site["edges"]) == 4


def test_local_dxf_forms_a_site_without_georeference(client: Any, project: str) -> None:
    site = upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE"))).json()["site"]
    assert site["origin"] == "upload" and site["georeferenced"] is False
    assert site["area_m2"] == pytest.approx(600.0)
    assert site["outline_geojson"] == {"type": "Polygon", "coordinates": []}
    assert site["source_info"]["layer"] == "PARCELLE" and site["source_info"]["crs"] == "local"


def test_dxf_in_millimetres_is_scaled(client: Any, project: str) -> None:
    ring = [(x * 1000, y * 1000) for x, y in LOCAL_RING]
    site = upload(client, project, "plan.dxf", dxf_bytes((ring, "0"), units=4)).json()["site"]
    assert site["area_m2"] == pytest.approx(600.0)


def test_several_outlines_offer_a_choice_before_anything_is_stored(
    client: Any, project: str, db_session: Any
) -> None:
    small = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    data = dxf_bytes((LOCAL_RING, "PARCELLE"), (small, "VOISIN"))
    body = upload(client, project, "plan.dxf", data).json()
    assert body["site"] is None
    assert [c["layer"] for c in body["candidates"]] == ["PARCELLE", "VOISIN"]  # größte zuerst
    assert [c["area_m2"] for c in body["candidates"]] == [600.0, 100.0]
    assert body["candidates"][0]["outline_local"][0][0] == [0.0, 0.0]
    assert db_session.execute(text("SELECT count(*) FROM site")).scalar_one() == 0

    chosen = upload(client, project, "plan.dxf", data, index=body["candidates"][1]["index"]).json()
    assert chosen["site"]["area_m2"] == pytest.approx(100.0)
    assert chosen["site"]["source_info"]["layer"] == "VOISIN"


def test_unknown_index_is_rejected(client: Any, project: str) -> None:
    response = upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")), index=7)
    assert response.status_code == 422 and response.json()["code"] == "upload_outline_not_found"


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("plan.dwg", b"egal"),
        ("plan.geojson", b"kein json"),
        ("leer.geojson", b'{"type": "FeatureCollection", "features": []}'),
    ],
)
def test_unreadable_files_are_rejected(client: Any, project: str, name: str, data: bytes) -> None:
    response = upload(client, project, name, data)
    assert response.status_code == 422 and response.json()["code"] == "upload_invalid"


def test_tiny_outline_is_not_plausible(client: Any, project: str) -> None:
    tiny = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    response = upload(client, project, "plan.dxf", dxf_bytes((tiny, "PARCELLE")))
    assert response.status_code == 422 and response.json()["code"] == "upload_invalid"


def test_upload_cannot_replace_a_cadastre_site(client: Any, project: str, db_session: Any) -> None:
    db_session.execute(
        text(
            "INSERT INTO site (id, project_id, origin, geometry, area_m2, local_origin_e, local_origin_n,"
            " parcel_idus, outline_hash, neighbour_coverage, road_data, engine_version, created_by)"
            " VALUES (gen_random_uuid(), :p, 'parcel',"
            " ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 2154), 100, 0, 0,"
            " ARRAY['x']::varchar[], 'h', 'complete', false, 'g1-1.1.0', 'test')"
        ),
        {"p": uuid.UUID(project)},
    )
    db_session.commit()
    response = upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")))
    assert response.status_code == 409 and response.json()["code"] == "site_origin_mismatch"


def test_cadastre_site_cannot_replace_an_upload(client: Any, project: str, db_session: Any) -> None:
    """Umgekehrt wie oben: Auch aus einem Upload wird kein Katastergrundstück (G28, symmetrisch).

    Die Parzelle wird von Hand eingesetzt, weil dieser Test ohne Katasterimport läuft; ohne sie
    scheiterte der Aufruf schon an `parcel_not_found`, bevor die Herkunft geprüft wird.
    """
    db_session.execute(
        text(
            "INSERT INTO ref_parcel (idu, commune_insee, prefix, section, number, area_official_m2,"
            " geometry, release) VALUES ('44209000AD0065', '44209', '000', 'AD', '0065', 600,"
            " ST_Multi(ST_GeomFromText('POLYGON((0 0, 20 0, 20 30, 0 30, 0 0))', 2154)), 'test')"
        )
    )
    db_session.commit()
    upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")))
    switched = client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": ["44209000AD0065"]})
    assert switched.status_code == 409 and switched.json()["code"] == "site_origin_mismatch"


def test_same_file_twice_keeps_the_revision(client: Any, project: str) -> None:
    data = dxf_bytes((LOCAL_RING, "PARCELLE"))
    first = upload(client, project, "plan.dxf", data).json()["site"]
    again = upload(client, project, "plan.dxf", data).json()["site"]
    assert again["revision"] == first["revision"] == 1


def test_a_drawn_site_can_be_replaced_by_an_upload(client: Any, project: str) -> None:
    drawn = client.put(
        f"/api/v1/projects/{project}/site",
        json={
            "edges": [
                {"length_m": 10, "angle_deg": 90},
                {"length_m": 20, "angle_deg": 180},
                {"length_m": 10, "angle_deg": 270},
            ],
            "address_label": "gezeichnet",
        },
    ).json()
    assert drawn["origin"] == "manual_sketch"
    site = upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE"))).json()["site"]
    assert site["origin"] == "upload" and site["revision"] == 2


# ---------------------------------------------------------------------------
# PDF: Katasterauszug oder Plan des Geometers (UP13–UP16)
# ---------------------------------------------------------------------------


def test_pdf_extract_offers_the_parcels_and_forms_the_chosen_one(client: Any, project: str) -> None:
    data = extract_pdf()
    body = upload(client, project, "extrait.pdf", data).json()
    assert body["site"] is None and body["format"] == "pdf"
    assert (body["scale"], body["scale_source"]) == (500, "file")
    names = [c["name"] for c in body["candidates"]]
    assert names[:2] == ["65", "66"]
    # Gemeinsamer Ursprung: In der Übersicht liegt 66 um die Breite von 65 (20 m) daneben
    first, second = body["candidates"][0], body["candidates"][1]

    def min_x(rings: list[list[list[float]]]) -> float:
        return min(point[0] for ring in rings for point in ring)

    offset = min_x(second["outline_overview"]) - min_x(first["outline_overview"])
    assert offset == pytest.approx(20.0, abs=0.05)

    chosen = upload(client, project, "extrait.pdf", data, index=first["index"]).json()["site"]
    assert chosen["origin"] == "upload" and chosen["georeferenced"] is False
    assert chosen["area_m2"] == pytest.approx(600.0, rel=0.002)
    info = chosen["source_info"]
    assert (info["format"], info["scale"], info["scale_source"], info["page"], info["name"]) == (
        "pdf",
        500,
        "file",
        1,
        "65",
    )
    assert [e["kind"] for e in chosen["edges"]] == ["other"] * 4


def test_parcel_cut_by_a_foreign_line_is_joined_from_its_pieces(client: Any, project: str) -> None:
    """Eine fremde Linie (auf echten Auszügen etwa ein Kreis) teilt Parzelle 65 und ihr Haus: Keine Fläche ist
    die ganze Parzelle, die zwei Teile zusammen schon – das Haus auf der Linie bleibt kein Loch (UP17)."""
    data = extract_pdf(extra=[line(35, 10, 35, 90)])
    candidates = upload(client, project, "extrait.pdf", data).json()["candidates"]

    def near(area: float) -> int:
        return next(c["index"] for c in candidates if c["area_m2"] == pytest.approx(area, rel=0.01))

    assert not any(c["area_m2"] == pytest.approx(600.0, rel=0.01) for c in candidates)
    # links 7,5 × 30 m ohne den Hausteil (15 m²), rechts 12,5 × 30 m ohne den Hausteil (33 m²)
    pieces = [near(210.0), near(342.0)]
    site = upload(client, project, "extrait.pdf", data, index=pieces).json()["site"]
    assert site["area_m2"] == pytest.approx(600.0, rel=0.002)
    assert [e["kind"] for e in site["edges"]] == ["other"] * 4
    info = site["source_info"]
    assert (info["indices"], info["index"], info["name"], info["scale"]) == (pieces, None, "65", 500)
    assert info["short_piece_m"] == 2.0

    apart = upload(client, project, "extrait.pdf", data, index=[pieces[0], near(360.0)])
    assert apart.status_code == 422 and apart.json()["code"] == "site_not_contiguous"
    unknown = upload(client, project, "extrait.pdf", data, index=[pieces[0], 999])
    assert unknown.status_code == 422 and unknown.json()["code"] == "upload_outline_not_found"
    too_many = upload(client, project, "extrait.pdf", data, index=list(range(21)))
    assert too_many.status_code == 422


def test_lettering_across_a_boundary_leaves_no_notch(client: Any, project: str) -> None:
    """Ein Buchstabe als gefüllter Umriss auf der Südgrenze von 65 kerbt das Grundstück nicht ein (UP19)."""
    data = extract_pdf(extra=[filled(38, 78, 4, 4, "black")])
    candidates = upload(client, project, "extrait.pdf", data).json()["candidates"]
    first = next(c for c in candidates if c["name"] == "65")
    assert first["area_m2"] == pytest.approx(600.0, rel=0.002)
    site = upload(client, project, "extrait.pdf", data, index=first["index"]).json()["site"]
    assert len(site["edges"]) == 4


def test_pdf_without_scale_asks_for_it(client: Any, project: str) -> None:
    data = extract_pdf(header="Plan de situation")
    missing = upload(client, project, "plan.pdf", data)
    assert missing.status_code == 422 and missing.json()["code"] == "upload_scale_missing"
    given = upload(client, project, "plan.pdf", data, scale=500).json()
    assert (given["scale"], given["scale_source"]) == (500, "input")


def test_pdf_with_two_scales_names_them(client: Any, project: str) -> None:
    response = upload(client, project, "plan.pdf", extract_pdf(header="1/500 et 1/2000"))
    assert response.status_code == 422
    assert response.json()["code"] == "upload_scale_ambiguous"
    assert response.json()["scales"] == [500, 2000]


def test_scanned_pdf_is_rejected_clearly(client: Any, project: str) -> None:
    response = upload(client, project, "scan.pdf", plan_pdf([], "Échelle 1/500"))
    assert response.status_code == 422 and response.json()["code"] == "upload_pdf_no_vector"


# ---------------------------------------------------------------------------
# Kanten von Hand einordnen
# ---------------------------------------------------------------------------


def test_architect_classifies_edges_of_an_uploaded_parcel(
    client: Any, project: str, login_as: Callable[..., Any]
) -> None:
    site = upload(client, project, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE"))).json()["site"]
    assert site["main_street_seq"] is None
    login_as("architect")
    seq = site["edges"][0]["seq"]
    updated = client.patch(
        f"/api/v1/admin/projects/{project}/site/edges/{seq}",
        json={"kind": "street"},
        headers={"If-Match": f'"{site["revision"]}"'},
    )
    assert updated.status_code == 200, updated.json()
    body = updated.json()
    assert body["main_street_seq"] == seq
    assert body["street_azimuth_deg"] is not None and body["garden_azimuth_deg"] is not None
    kinds = {e["seq"]: e["kind"] for e in body["edges"]}
    assert kinds[seq] == "street"
    # Die übrigen Kanten leitet `classify` aus der Hauptstraße ab (Seite und Hinten)
    assert set(kinds.values()) <= {"street", "side", "rear"}
    assert "no_street_edge" not in body["warnings"]


# ---------------------------------------------------------------------------
# Projekte am Architektenkonto
# ---------------------------------------------------------------------------


def test_architect_project_has_an_owner_and_no_cookie(
    client: Any, enabled: None, login_as: Callable[..., Any], db_session: Any
) -> None:
    login_as("architect")
    created = client.post("/api/v1/projects")
    assert created.status_code == 201
    project_id = uuid.UUID(created.json()["id"])
    assert "emprise_project" not in created.cookies
    project = db_session.get(Project, project_id)
    assert project.owner_staff_user_id is not None and project.organisation_id is None

    # Zugriff über die Mitarbeitersitzung, nicht über das Cookie
    site = upload(client, str(project_id), "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE"))).json()["site"]
    assert site["origin"] == "upload"
    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    entry = next(p for p in listed.json() if p["id"] == str(project_id))
    assert entry["site_origin"] == "upload" and entry["area_m2"] == pytest.approx(600.0)
    assert entry["address_label"] == "Parzelle aus Datei"


def test_customer_projects_stay_invisible_to_architects(
    client: Any, app: Any, enabled: None, login_as: Callable[..., Any]
) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as customer:
        customer.get("/api/v1/session")
        customer.headers["X-CSRF-Token"] = customer.cookies["emprise_csrf"]
        foreign = customer.post("/api/v1/projects").json()["id"]
    login_as("architect")
    assert client.get(f"/api/v1/projects/{foreign}").status_code == 404
    assert [p["id"] for p in client.get("/api/v1/projects").json()] == []


def test_projects_without_the_role_are_not_listed(client: Any, login_as: Callable[..., Any]) -> None:
    assert client.get("/api/v1/projects").status_code == 401
    login_as("ops")
    assert client.get("/api/v1/projects").status_code == 403


def test_retention_keeps_projects_with_an_owner(
    client: Any, login_as: Callable[..., Any], db_session: Any
) -> None:
    user = login_as("architect")
    owned = Project(access_token_hash=b"owned", owner_staff_user_id=user.id)
    anonymous = Project(access_token_hash=b"anonymous")
    db_session.add_all([owned, anonymous])
    db_session.commit()
    db_session.execute(text("UPDATE project SET last_activity_at = now() - make_interval(days => 91)"))
    enqueue(db_session, "retention_cleanup")
    db_session.commit()
    run_one("w1", ["default"])
    db_session.expire_all()
    assert set(db_session.execute(select(Project.id)).scalars()) == {owned.id}


def test_architect_deletes_an_own_project(client: Any, enabled: None, login_as: Callable[..., Any]) -> None:
    login_as("architect")
    project_id = client.post("/api/v1/projects").json()["id"]
    upload(client, project_id, "plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")))
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
