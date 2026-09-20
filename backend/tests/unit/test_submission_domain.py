"""Modul V ohne Datenbank: Prüfstempel, Texte, Lageplan, DXF, PDF und Zugangslink
(docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.3, 3.7, 3.9)."""

import io
import uuid
from typing import Any

import pytest

from app.configuration import review
from app.submission import dossier
from app.submission.dossier import dxf, pdf
from app.submission.dossier import format as fmt
from app.submission.dossier.plan import choose_scale, from_snapshot

ORIGIN = {"e": 355000.0, "n": 6700000.0, "crs": "EPSG:2154"}


def rect(x: float, y: float, w: float, h: float) -> list[list[float]]:
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]


def snapshot(origin: str = "parcel", **overrides: Any) -> dict[str, Any]:
    """Kleinster Snapshot einer Fassung: Grundstück 20 × 31 m, Haus 12 × 8 m, Terrasse, Carport."""
    data: dict[str, Any] = {
        "schema_version": 2,
        "number": "EMP-2026-000042",
        "sequence": 1,
        "submitted_at": "2026-09-19T12:00:00+00:00",
        "locale": "de",
        "customer": {"name": "Camille Martin", "email": "c@example.fr", "lotissement": "no"},
        "consents": [
            {
                "kind": "design_confirmation",
                "legal_text_key": "notice.design_confirmation",
                "legal_text_version": 1,
                "confirmed_at": "2026-09-19T12:00:00+00:00",
            }
        ],
        "site": {
            "origin": origin,
            "address_label": "12 rue imaginaire" if origin != "parcel" else None,
            "area_m2": 620.0,
            "local_origin": ORIGIN,
            "outline_local": [rect(0, 0, 20, 31)],
            "parcels": [
                {
                    "idu": "44209000AD0065",
                    "section": "AD",
                    "number": "0065",
                    "area_official_m2": 620,
                    "area_geometric_m2": 619.4,
                    "accuracy_class": "api_vector",
                }
            ]
            if origin == "parcel"
            else [],
            "edges": [
                {
                    "seq": 1,
                    "kind": "street",
                    "coords_local": [[0, 31], [20, 31]],
                    "length_m": 20.0,
                    "classification_source": "auto",
                },
                {
                    "seq": 2,
                    "kind": "side",
                    "coords_local": [[20, 31], [20, 0]],
                    "length_m": 31.0,
                    "classification_source": "customer",
                },
            ],
            "context": {"parcels": [rect(-20, 0, 20, 31)], "buildings": [rect(-15, 5, 8, 8)]},
            "terrain": {"status": "ok", "slope_percent": 1.2, "reference_altitude_ngf": 42.0},
            "risks": {
                "status": "ok",
                "items": [
                    {
                        "kind": "clay_shrink_swell",
                        "label": "Exposition moyenne",
                        "level": "moderate",
                        "scope": "address",
                    },
                    {"kind": "flood", "label": "Risque Existant", "level": "present", "scope": "commune"},
                ],
            },
        },
        "rules": {"plan": {"title": "PLU Treillières"}},
        "envelope": {
            "status": "ok",
            "contours": {
                "lenient": {"rings_local": [rect(3, 3, 14, 23)]},
                "strict": {"rings_local": [rect(4, 5, 12, 20)]},
            },
        },
        "configuration": {
            "placement": {"origin": {"e": 4.0, "n": 15.0}, "rotation_deg": 0.0},
            "evaluation": {
                "facade_local": rect(4, 15, 12, 8),
                "projection_local": rect(3.5, 14.5, 13, 9),
                "checks": [
                    {
                        "code": "setback_street",
                        "kind": "setback",
                        "status": "pass",
                        "binding": True,
                        "measured": 8.0,
                        "limit": 5.0,
                        "params": {},
                        "citation": {
                            "page": 12,
                            "quote": "Les constructions s'implantent à 5 m.",
                            "quote_verified": True,
                        },
                    },
                ],
                "edges": [
                    {"seq": 1, "kind": "street", "measured_m": 8.0, "required_m": 5.0, "status": "pass"},
                    {"seq": 2, "kind": "side", "measured_m": 4.0, "required_m": None, "status": "unknown"},
                ],
            },
            "fit": {
                "reasons": [],
                "facts": {
                    "living_area_m2": 158,
                    "footprint_m2": 96,
                    "ridge_height_m": 8.4,
                    "eave_height_m": 5.6,
                    "storeys": "R+1",
                },
            },
            "compliance": {
                "checks": [
                    {
                        "code": "unsealed_min_unknown",
                        "kind": "unsealed_min",
                        "status": "unknown",
                        "binding": False,
                        "params": {},
                    },
                    {
                        "code": "annex_footprint",
                        "kind": "annex",
                        "status": "fail",
                        "binding": True,
                        "measured": 30.0,
                        "limit": 20.0,
                        "params": {"subject": "carport_2"},
                    },
                ]
            },
            "outbuildings": {
                "terrace": {"polygon_local": rect(4, 12, 12, 3)},
                "carport": {"polygon_local": rect(16.5, 24, 3, 5)},
                "driveways": [{"polygon_local": rect(16.5, 29, 3, 2)}],
            },
            "areas": {
                "site_m2": 620,
                "house_m2": 96,
                "terrace_m2": 36,
                "carport_m2": 15,
                "driveway_m2": 6,
                "paths_m2": 10,
                "emprise_m2": 111,
                "sealed_m2": 163,
                "unsealed_m2": 457,
            },
            "costs": {
                "available": True,
                "vat_rate": 0.2,
                "catalog_version": 3,
                "display": {"min_cents": 38_400_000, "max_cents": 41_800_000},
                "items": [
                    {
                        "code": "TYPE_BASE",
                        "kind": "base",
                        "slug": None,
                        "label_de": "Klein",
                        "label_fr": "Klein",
                        "min_cents": 39_360_000,
                        "max_cents": 43_440_000,
                        "included": False,
                    },
                    {
                        "code": "OPT_TERRASSE",
                        "kind": "option",
                        "slug": "terrasse",
                        "label_de": "Terrasse",
                        "label_fr": "Terrasse",
                        "min_cents": 1_728_000,
                        "max_cents": 1_728_000,
                        "included": False,
                        "quantity": 36.0,
                        "unit": "m²",
                        "unit_price_cents": 48_000,
                    },
                ],
            },
            "energy": {"status": "not_assessed", "climate_zone": "H2b", "verdict": None, "measures": None},
            "orientation": {"convergence_deg": -3.3, "facades": {"garden": 176.7, "street": 356.7}},
        },
        "catalog": {
            "type": {"slug": "klein", "version": 1, "status": "published", "name": "Klein"},
            "package": {
                "slug": "base",
                "version": 1,
                "status": "retired",
                "label_de": "Basis",
                "label_fr": "Base",
            },
            "options": [
                {
                    "slug": "terrasse",
                    "version": 1,
                    "status": "published",
                    "label_de": "Terrasse",
                    "label_fr": "Terrasse",
                    "included": False,
                }
            ],
        },
        "review_stamp": "v1:site=a.rules=b.catalog=c.configuration=1.result=d.engine=e",
        "deviations": [],
        "deviations_acknowledged": False,
        "open_points": 1,
        "engine": {"configuration": "h3-1.0.0", "dossier": dossier.DOSSIER_VERSION},
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Prüfstempel
# ---------------------------------------------------------------------------


def test_canonical_hash_ignores_order_of_lists_and_keys() -> None:
    assert review.digest({"a": [3, 1, 2], "b": {"y": 1, "x": 2}}) == review.digest(
        {"b": {"x": 2, "y": 1}, "a": [2, 3, 1]}
    )
    assert review.digest({"a": [1, 2]}) != review.digest({"a": [1, 3]})


def test_changes_name_the_differing_parts() -> None:
    parts = dict.fromkeys(review.PARTS, "0" * 12)
    old = review.make_stamp(parts)
    new = review.make_stamp({**parts, "rules": "1" * 12, "result": "2" * 12})
    assert review.changes(old, new) == ["rules", "result"]
    assert review.changes(old, old) == []
    assert review.changes("unlesbar", new) == list(review.PARTS)
    assert review.parse_stamp(new)["configuration"] == "0" * 12


def test_deviations_and_open_points_come_from_all_check_lists() -> None:
    from app.configuration.schemas import CheckOut

    fail = CheckOut(code="footprint", kind="footprint", status="fail", binding=True)
    hint = CheckOut(code="footprint", kind="footprint", status="fail", binding=False, zone_code="Uh")
    unknown = CheckOut(code="max_height_unknown", kind="max_height", status="unknown", binding=False)

    class Out:
        fit = type("Fit", (), {"reasons": [fail]})()
        evaluation = type("Evaluation", (), {"checks": [fail, unknown]})()
        compliance = type("Compliance", (), {"checks": [hint]})()

    assert [c.code for c in review.deviations(Out())] == ["footprint"]  # type: ignore[arg-type]
    assert review.open_points(Out()) == 1  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Texte
# ---------------------------------------------------------------------------


def test_numbers_and_money_follow_the_language() -> None:
    assert fmt.number(1234.5, "de", 1) == "1.234,5"
    assert fmt.number(1234.5, "fr", 1) == "1 234,5"
    assert fmt.money(38_400_000, "de") == "384.000 €"
    costs = {"available": True, "display": {"min_cents": 38_400_000, "max_cents": 41_800_000}}
    assert fmt.costs_text(costs, "de") == "ca. 384.000 € – 418.000 €"
    assert fmt.costs_text(costs, "fr").startswith("env. 384 000 €")
    assert fmt.costs_text({"available": False}, "de").startswith("noch kein")


def test_check_texts_use_the_synchronised_translations() -> None:
    setback = {"code": "setback_street", "measured": 8.0, "limit": 5.0, "params": {}}
    assert fmt.check_text(setback, "de") == "Abstand zur Straße: 8,00 m (mindestens 5,00 m)"
    annex = {"code": "annex_footprint", "measured": 30.0, "limit": 20.0, "params": {"subject": "carport_2"}}
    assert "„Carport 6 × 5“" in fmt.check_text(annex, "de", {"carport_2": "Carport 6 × 5"})
    roof = {"code": "roof_form", "measured": "flat", "limit": "gable,hip", "params": {}}
    assert fmt.check_text(roof, "de") == "Dachform: Flachdach (zulässig: Satteldach, Walmdach)"
    assert fmt.check_text({"code": "gibt_es_nicht", "params": {}}, "fr") == "gibt_es_nicht"
    assert fmt.edge_name("street", 3, "de") == "Straße (3)"


# ---------------------------------------------------------------------------
# Lageplan, DXF, PDF
# ---------------------------------------------------------------------------


def test_plan_reads_the_snapshot_and_picks_a_scale() -> None:
    plan = from_snapshot(snapshot())
    assert plan.georeferenced and plan.origin == (355000.0, 6700000.0)
    assert plan.facade and plan.terrace and plan.carport and len(plan.driveways) == 1
    assert [e.kind for e in plan.edges] == ["street", "side"]
    assert choose_scale(plan) == 250  # 26 × 37 m passen auf 170 × 150 mm erst ab 1:250
    assert not from_snapshot(snapshot("manual_sketch")).georeferenced


def test_file_names_leave_out_lambert_for_a_drawn_site() -> None:
    names = [name for name, *_ in dossier.file_names(snapshot())]
    assert names == [
        "EMP-2026-000042_F1_fr.pdf",
        "EMP-2026-000042_F1_de.pdf",
        "EMP-2026-000042_F1_L93.dxf",
        "EMP-2026-000042_F1_local.dxf",
    ]
    manual = [name for name, *_ in dossier.file_names(snapshot("manual_sketch"))]
    assert "EMP-2026-000042_F1_L93.dxf" not in manual and len(manual) == 3


def test_dxf_in_lambert_is_the_local_plan_shifted_by_the_origin() -> None:
    import ezdxf

    plan = from_snapshot(snapshot())
    l93 = ezdxf.read(io.StringIO(dxf.render(plan, "L93", ["EMP"]).decode()))
    local = ezdxf.read(io.StringIO(dxf.render(plan, "local", ["EMP"]).decode()))
    assert l93.header["$INSUNITS"] == 6
    for layer in (
        "PARCELLE",
        "LIMITE_VOIE",
        "LIMITE_SEPARATIVE",
        "MAISON_FACADE",
        "TERRASSE",
        "CARPORT",
        "ACCES",
    ):
        assert l93.modelspace().query(f'*[layer=="{layer}"]'), layer
    house_l93 = next(iter(l93.modelspace().query('LWPOLYLINE[layer=="MAISON_FACADE"]')))
    house_local = next(iter(local.modelspace().query('LWPOLYLINE[layer=="MAISON_FACADE"]')))
    assert house_l93.closed and len(house_l93) == 4
    assert house_local.get_points("xy")[0] == pytest.approx((4.0, 15.0))
    assert house_l93.get_points("xy")[0] == pytest.approx((355004.0, 6700015.0))
    with pytest.raises(ValueError):
        dxf.render(from_snapshot(snapshot("manual_sketch")), "L93", [])


def test_pdf_html_shows_ranges_checks_and_notices_but_no_total() -> None:
    html = pdf.render_html(snapshot(), from_snapshot(snapshot()), "de", ["a.dxf"])
    assert "EMP-2026-000042" in html and "Fassung 1" in html
    assert "ca. 384.000 € – 418.000 €" in html
    assert "Abstand zur Straße: 8,00 m (mindestens 5,00 m)" in html and "S. 12" in html
    assert "Cadastre DGFiP / Etalab (ODbL 1.0)" in html
    assert "Basis" in html and "Inzwischen zurückgezogene Katalogstände" in html
    assert "Maßstab 1:250" in html and "<svg" in html
    assert (
        "Schrumpfen und Quellen toniger Böden: mittel" in html and "Hochwasser: vorhanden · Gemeinde" in html
    )
    assert "36,0 m²" in html
    assert "Gesamt" not in html and "total" not in html.lower()
    # Abweichungen zuerst: der Verstoß des Carports steht vor dem bestandenen Abstand
    assert html.index("Nebengebäude") < html.index("Abstand zur Straße")
    french = pdf.render_html(snapshot(), from_snapshot(snapshot()), "fr", [])
    assert "Pré-projet" in french and "env. 384 000 €" in french


def test_pdf_of_a_drawn_site_has_no_north_and_no_cadastre_source() -> None:
    manual = snapshot("manual_sketch")
    html = pdf.render_html(manual, from_snapshot(manual), "de", [])
    assert "ohne geografischen Bezug" in html and "Etalab" not in html and "Lambert-93)" not in html


def test_dossier_builds_real_pdfs() -> None:
    files = dossier.build(snapshot())
    assert [f.kind for f in files] == ["pdf", "pdf", "dxf", "dxf"]
    assert all(f.data.startswith(b"%PDF") for f in files if f.kind == "pdf")


# ---------------------------------------------------------------------------
# Zugangslink
# ---------------------------------------------------------------------------


def test_access_token_round_trip_and_tampering() -> None:
    from app.inquiry import access
    from app.platform.problems import Problem

    project = uuid.uuid4()
    token = access.make_token(project)
    assert access.read_token(token) == project
    payload, signature = token.split(".")
    other = access.make_token(uuid.uuid4()).split(".")[0]
    for broken in (f"{other}.{signature}", f"{payload}.{signature[:-2]}xx", "kaputt", f"{payload}."):
        with pytest.raises(Problem):
            access.read_token(broken)
