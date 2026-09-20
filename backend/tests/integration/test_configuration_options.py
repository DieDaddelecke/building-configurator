"""Modul H3 gegen PostGIS: Linie, Optionen, Terrasse und Carport, Flächen, Kosten, Energie (Plan H3 6).

Preise ohne Mehrwertsteuerumrechnung sind Sache der Einheitstests; hier gilt der Standardsatz des Katalogs
(20 %, Anzeige brutto, D10). Grundstück AD 65 (Zone Uh) und die Typen des H2-Tests: `klein` 12 × 8 m.
"""

from typing import Any

import pytest

from app.catalog import service as catalog_service
from app.catalog.schemas import ModuleIn, PackageIn
from tests.integration import test_configuration as _config
from tests.integration.test_catalog import LIGNE_KENNWERTE, ROOMS, _dxf, _xlsx
from tests.integration.test_configuration import ROLES, patch, rect, url

# Fixtures des H2-Tests (Grundstück AD 65 mit ausgewerteter Zone Uh, Typen `klein` und `gross`)
catalog = _config.catalog
configurator = _config.configurator
memory_storage = _config.memory_storage
project = _config.project
sessions = _config.sessions
settings = _config.settings

VAT = 0.2


def publish_module(db: Any, slug: str, **body: Any) -> None:
    body.setdefault("label_de", slug)
    body.setdefault("label_fr", slug)
    catalog_service.create_module_version(db, slug, ModuleIn(**body), "test")
    catalog_service.publish_module_version(db, slug, 1, "test")


def publish_package(db: Any, slug: str, **body: Any) -> None:
    body.setdefault("label_de", slug)
    body.setdefault("label_fr", slug)
    catalog_service.create_package_version(db, slug, PackageIn(**body), "test")
    catalog_service.publish_package_version(db, slug, 1, "test")


def import_priced(
    db: Any,
    slug: str,
    *,
    facade: list[tuple[float, float]],
    kennwerte: dict[str, str],
    prices: list[tuple[Any, ...]],
    roles: dict[str, str] | None = ROLES,
) -> None:
    from app.catalog.schemas import FacadeRolesIn

    catalog_service.import_type_version(
        db, slug, _xlsx(kennwerte, ROOMS, prices), _dxf(facade, rect(*_size(facade), 0.5)), "test"
    )
    if roles:
        catalog_service.set_facade_roles(db, slug, 1, FacadeRolesIn(roles=roles), "test")  # type: ignore[arg-type]
    catalog_service.publish_type_version(db, slug, 1, "test")


def _size(points: list[tuple[float, float]]) -> tuple[float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


ALL_PRICES: list[tuple[Any, ...]] = [
    ("linie", "base", 0),
    ("linie", "confort", 34_000),
    ("option", "terrasse", 400),
    ("option", "carport_1", 9_000),
    ("option", "carport_2", 14_500),
    ("option", "pv", 11_200),
    ("option", "holz_sued", 12_400),
    ("option", "holz_voll", 28_900),
]


@pytest.fixture
def offers(db_session: Any, catalog: None) -> None:
    """Optionen, Linien und einen veröffentlichten Preiskatalog zum Typ `klein` (aus `catalog`)."""
    publish_module(db_session, "terrasse", kind="terrace")
    publish_module(db_session, "carport_1", kind="carport", params={"spaces": 1})
    publish_module(db_session, "carport_2", kind="carport", params={"spaces": 2})
    publish_module(db_session, "pv")
    publish_module(db_session, "holz_sued", excludes_slugs=["holz_voll"])
    publish_module(db_session, "holz_voll", excludes_slugs=["holz_sued"])
    publish_package(db_session, "base")
    publish_package(db_session, "confort", included_option_slugs=["pv"])
    # Typ mit Preisen: neu importiert (Version 2), damit die Preiszeilen im Entwurf des Katalogs stehen
    klein = {**LIGNE_KENNWERTE, "name": "Klein", "neigung_deg": "35.0", "familie": "klein"}
    import_priced(db_session, "preisig", facade=rect(12, 8), kennwerte=klein, prices=ALL_PRICES)
    catalog_service.set_energy_assessment(
        db_session,
        "preisig",
        "base",
        climate_zone="H2b",
        verdict="Base verfehlt den Schwellenwert knapp",
        compliant=False,
        compliance_surcharge_cents=950_000,
        measures="verstärkte Dämmung",
        actor_id="test",
    )
    catalog_service.publish_price_catalog(db_session, "test")


def select(client: Any, project: str, **body: Any) -> Any:
    return patch(client, project, {"type_slug": "preisig", **body})


def gross(eur: int) -> int:
    return round(eur * 100 * (1 + VAT))


# ---------------------------------------------------------------------------
# Angebot
# ---------------------------------------------------------------------------


def test_options_need_a_chosen_type(client: Any, project: str, offers: None, configurator: None) -> None:
    response = client.get(url(project, "catalog/options"))
    assert response.status_code == 409 and response.json()["code"] == "no_type_selected"


def test_options_list_shows_offered_lines_and_options_with_gross_prices(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    assert select(client, project).status_code == 200
    body = client.get(url(project, "catalog/options")).json()
    assert body["catalog_available"] is True and body["vat_rate"] == VAT and body["display_basis"] == "gross"
    lines = {p["slug"]: p for p in body["packages"]}
    assert set(lines) == {"base", "confort"}
    assert lines["confort"]["price"]["min_cents"] == gross(34_000)
    assert lines["base"]["energy"]["status"] == "action"
    assert lines["confort"]["energy"]["status"] == "not_assessed"
    options = {o["slug"]: o for o in body["options"]}
    assert set(options) == {"terrasse", "carport_1", "carport_2", "pv", "holz_sued", "holz_voll"}
    terrace = options["terrasse"]
    assert terrace["kind"] == "terrace" and terrace["area_m2"] == pytest.approx(36.0)
    assert terrace["price"]["basis"] == "per_m2" and terrace["price"]["unit_price_cents"] == gross(400)
    assert terrace["price"]["min_cents"] == round(gross(400) * 36.0)
    assert options["carport_2"]["area_m2"] == pytest.approx(30.0)
    # Das Haus steht mittig an der Straße: daneben passt der einstellige Carport, der andere nicht
    assert {slug: o["state"] for slug, o in options.items()} == {
        "terrasse": "available",
        "carport_1": "available",
        "carport_2": "blocked",
        "pv": "available",
        "holz_sued": "available",
        "holz_voll": "available",
    }
    assert [c["code"] for c in options["carport_2"]["checks"]] == ["no_valid_position"]


def test_options_are_empty_without_a_published_price_catalog(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    assert patch(client, project, {"type_slug": "klein"}).status_code == 200
    body = client.get(url(project, "catalog/options")).json()
    assert body["catalog_available"] is False and body["packages"] == [] and body["options"] == []
    config = client.get(url(project, "configuration")).json()
    assert config["costs"]["available"] is False and config["costs"]["reason"] == "catalog_unavailable"
    rejected = patch(client, project, {"package_slug": "confort"})
    assert rejected.status_code == 422 and rejected.json()["code"] == "invalid_selection"


# ---------------------------------------------------------------------------
# Auswahl und Kosten
# ---------------------------------------------------------------------------


def test_line_selection_prices_the_corridor_gross_and_rounded(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project).json()
    assert saved["costs"]["available"] is True and saved["selection"]["package_slug"] is None
    base_only = saved["costs"]["gross"]
    assert base_only["min_cents"] == gross(328_000) and base_only["max_cents"] == gross(362_000)

    body = patch(client, project, {"package_slug": "confort"}, revision=saved["revision"]).json()
    costs = body["costs"]
    assert costs["gross"]["min_cents"] == gross(328_000 + 34_000)
    assert costs["gross"]["max_cents"] == gross(362_000 + 34_000)
    assert costs["display"]["min_cents"] % 100_000 == 0 and costs["display"]["max_cents"] % 100_000 == 0
    assert costs["catalog_version"] == 1 and costs["display_basis"] == "gross"
    assert {i["kind"] for i in costs["items"]} == {"base", "package", "option"}
    assert [i["slug"] for i in costs["items"] if i["included"]] == [
        "pv"
    ]  # in Confort enthalten, kostet nichts
    assert body["selection"]["package_slug"] == "confort" and body["selection"]["package_version"] == 1


def test_re2020_surcharge_of_the_base_line_goes_into_the_corridor(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project, package_slug="base").json()
    assert saved["energy"]["status"] == "action" and saved["energy"]["surcharge_cents"] == gross(9_500)
    items = {i["code"]: i for i in saved["costs"]["items"]}
    assert "RE2020_CONFORMITY" in items
    assert saved["costs"]["net"]["min_cents"] == (328_000 + 9_500) * 100


def test_option_included_in_the_line_is_free_and_charged_again_without_it(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project, package_slug="confort").json()
    with_pv = patch(client, project, {"option_slugs": ["pv"]}, revision=saved["revision"]).json()
    assert with_pv["costs"]["gross"] == saved["costs"]["gross"]  # pv ist in confort enthalten
    assert with_pv["selection"]["included_slugs"] == ["pv"]
    pv_item = next(i for i in with_pv["costs"]["items"] if i["slug"] == "pv")
    assert pv_item["included"] is True and pv_item["min_cents"] == 0
    back = patch(client, project, {"package_slug": "base"}, revision=with_pv["revision"]).json()
    pv_item = next(i for i in back["costs"]["items"] if i["slug"] == "pv")
    assert pv_item["included"] is False and pv_item["min_cents"] == gross(11_200)
    listed = {o["slug"]: o["state"] for o in client.get(url(project, "catalog/options")).json()["options"]}
    assert listed["pv"] == "selected"


def test_unknown_or_unoffered_option_is_rejected_with_reasons(
    client: Any, project: str, offers: None, configurator: None, db_session: Any
) -> None:
    saved = select(client, project).json()
    publish_module(db_session, "keller")  # ohne Preiszeile für den Typ: wird nicht angeboten
    for slug, code in (("keller", "unknown_option"), ("nix", "unknown_option")):
        response = patch(client, project, {"option_slugs": [slug]}, revision=saved["revision"])
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "invalid_selection"
        assert [(r["code"], r["slug"]) for r in body["reasons"]] == [(code, slug)]
    unknown_line = patch(client, project, {"package_slug": "gold"})
    assert unknown_line.status_code == 422 and unknown_line.json()["reasons"][0]["code"] == "unknown_package"
    assert client.get(url(project, "configuration")).json()["revision"] == saved["revision"]


def test_exclusion_is_rejected_and_shown_as_blocked_in_the_list(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project, option_slugs=["holz_sued"]).json()
    response = patch(
        client, project, {"option_slugs": ["holz_sued", "holz_voll"]}, revision=saved["revision"]
    )
    assert response.status_code == 422
    assert [(r["code"], r["slug"], r["other"]) for r in response.json()["reasons"]] == [
        ("excluded_by", "holz_voll", "holz_sued")
    ]
    listed = {o["slug"]: o for o in client.get(url(project, "catalog/options")).json()["options"]}
    assert listed["holz_voll"]["state"] == "blocked"
    assert listed["holz_voll"]["reasons"][0]["code"] == "excluded_by"


def test_both_carports_exclude_each_other(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project, option_slugs=["carport_1"]).json()
    assert saved["outbuildings"]["carport"]["spaces"] == 1
    response = patch(client, project, {"option_slugs": ["carport_1", "carport_2"]})
    assert response.status_code == 422 and response.json()["reasons"][0]["code"] == "excluded_by"
    # Der zweistellige Carport findet neben dem mittigen Haus keine Stelle (die Zufahrt darf es nicht kreuzen)
    swapped = patch(client, project, {"option_slugs": ["carport_2"]})
    assert swapped.status_code == 422 and swapped.json()["code"] == "selection_blocked"
    assert [c["code"] for c in swapped.json()["checks"]] == ["no_valid_position"]


# ---------------------------------------------------------------------------
# Terrasse, Carport, Flächen
# ---------------------------------------------------------------------------


def test_terrace_is_placed_at_the_garden_facade_and_priced_per_square_metre(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    body = select(client, project, option_slugs=["terrasse"]).json()
    terrace = body["outbuildings"]["terrace"]
    assert terrace["placed"] is True and terrace["polygon_local"]
    assert terrace["area_m2"] == pytest.approx(36.0) and terrace["width_m"] == pytest.approx(12.0)
    assert terrace["depth_m"] == pytest.approx(3.0)
    item = next(i for i in body["costs"]["items"] if i["slug"] == "terrasse")
    assert item["quantity"] == pytest.approx(36.0) and item["unit"] == "m2"
    assert item["min_cents"] == pytest.approx(gross(400) * 36.0, abs=40)
    assert body["areas"]["terrace_m2"] == pytest.approx(36.0, abs=0.1)
    assert body["areas"]["sealed_m2"] > body["areas"]["house_m2"]
    assert body["areas"]["sealed_m2"] + body["areas"]["unsealed_m2"] == pytest.approx(
        body["areas"]["site_m2"], abs=0.05
    )


def test_carport_gets_a_driveway_and_its_own_area(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    body = select(client, project, option_slugs=["carport_1"]).json()
    carport = body["outbuildings"]["carport"]
    assert carport["placed"] is True and carport["area_m2"] == pytest.approx(15.0)
    assert carport["setback"] in ("known", "assumed", "relaxed")
    assert body["areas"]["carport_m2"] == pytest.approx(15.0, abs=0.1)
    assert body["outbuildings"]["driveways"] and body["outbuildings"]["driveways"][0]["source"] == "carport"
    codes = {c["code"] for c in body["compliance"]["checks"]}
    assert "parking_not_shown" not in codes


def test_no_carport_or_garage_only_hints_at_parking(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    body = select(client, project).json()
    assert "parking_not_shown" in {c["code"] for c in body["compliance"]["checks"]}
    assert body["outbuildings"]["carport"] is None and body["outbuildings"]["driveways"] == []
    assert body["compliance"]["hint"] >= 1


def test_orientation_reports_true_azimuth_with_the_meridian_convergence(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    body = select(client, project).json()
    orientation = body["orientation"]
    assert -3.6 < orientation["convergence_deg"] < -3.0  # Treillières
    assert {"street", "garden"} <= set(orientation["facades"])
    diff = (orientation["facades"]["garden"] - orientation["facades"]["street"]) % 360
    assert diff == pytest.approx(180.0, abs=0.2)


def test_type_change_keeps_what_is_offered_and_reports_what_was_dropped(
    client: Any, project: str, offers: None, configurator: None, db_session: Any
) -> None:
    other = {**LIGNE_KENNWERTE, "name": "Andere", "neigung_deg": "35.0", "familie": "andere"}
    import_priced(
        db_session,
        "andere",
        facade=rect(11, 8),
        kennwerte=other,
        prices=[("linie", "confort", 30_000), ("option", "pv", 10_000)],
    )
    catalog_service.publish_price_catalog(db_session, "test")
    saved = select(client, project, package_slug="confort", option_slugs=["terrasse", "pv"]).json()
    assert saved["selection"]["option_slugs"] == ["terrasse", "pv"]
    switched = patch(client, project, {"type_slug": "andere"}, revision=saved["revision"])
    assert switched.status_code == 200, switched.text
    selection = switched.json()["selection"]
    assert selection["package_slug"] == "confort" and selection["option_slugs"] == ["pv"]
    assert selection["dropped"] == ["terrasse"]
    assert client.get(url(project, "configuration")).json()["selection"]["dropped"] == []


def test_terrace_without_garden_facade_is_blocked_and_dropped_on_type_change(
    client: Any, project: str, offers: None, configurator: None, db_session: Any
) -> None:
    kennwerte = {**LIGNE_KENNWERTE, "name": "Ohne", "neigung_deg": "35.0", "familie": "ohne"}
    import_priced(
        db_session, "ohne_rollen", facade=rect(11, 8), kennwerte=kennwerte, prices=ALL_PRICES, roles=None
    )
    catalog_service.publish_price_catalog(db_session, "test")
    on = patch(client, project, {"type_slug": "ohne_rollen"})
    assert on.status_code == 200, on.text
    blocked = patch(client, project, {"option_slugs": ["terrasse"]})
    assert blocked.status_code == 422
    body = blocked.json()
    assert body["code"] == "selection_blocked"
    assert [c["code"] for c in body["checks"]] == ["no_garden_facade"]
    listed = {o["slug"]: o for o in client.get(url(project, "catalog/options")).json()["options"]}
    assert listed["terrasse"]["state"] == "blocked"
    assert [c["code"] for c in listed["terrasse"]["checks"]] == ["no_garden_facade"]

    saved = select(client, project, option_slugs=["terrasse"])
    assert saved.status_code == 200
    moved = patch(client, project, {"type_slug": "ohne_rollen"})
    assert moved.status_code == 200
    assert moved.json()["selection"]["dropped"] == ["terrasse"]


# ---------------------------------------------------------------------------
# Verträge
# ---------------------------------------------------------------------------


def test_moving_the_house_rechecks_the_outbuildings(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    saved = select(client, project, package_slug="confort", option_slugs=["terrasse", "carport_1"]).json()
    presets = client.post(url(project, "configuration/placement-presets") + "?type=preisig").json()["presets"]
    moved = patch(client, project, {"placement": presets["set_back"]}, revision=saved["revision"])
    assert moved.status_code in (200, 422), moved.text
    if moved.status_code == 200:
        body = moved.json()
        assert body["outbuildings"]["terrace"]["placed"] is True
        assert body["selection"]["option_slugs"] == ["terrasse", "carport_1"]
    else:
        assert moved.json()["code"] == "selection_blocked"


def test_no_response_field_reads_as_a_total_price(app: Any) -> None:
    """L1: kein Feld `total`, `price_total` oder `sum` in einer Antwort des Konfigurators."""
    schema = app.openapi()["components"]["schemas"]
    forbidden = {"total", "total_cents", "sum", "sum_cents", "price_total", "exact_cents"}
    for name in ("CostsOut", "CostItemOut", "RangeOut", "PriceOut", "OptionChoiceOut", "PackageChoiceOut"):
        assert not forbidden & set(schema[name]["properties"]), name


def test_response_is_a_simulation_everywhere(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    body = select(client, project, package_slug="confort").json()
    assert body["simulation"] is True
    assert client.get(url(project, "catalog/options")).json()["simulation"] is True


def test_office_reads_the_full_evaluation(
    client: Any, project: str, offers: None, configurator: None, login_as: Any
) -> None:
    select(client, project, package_slug="confort", option_slugs=["terrasse"])
    login_as("architect")
    body = client.get(f"/api/v1/admin/projects/{project}/configuration").json()
    assert body["costs"]["available"] is True and body["selection"]["package_slug"] == "confort"


def test_evaluation_time_stays_within_the_budget(
    client: Any, project: str, offers: None, configurator: None
) -> None:
    import time

    select(client, project, package_slug="confort", option_slugs=["terrasse", "carport_2", "pv"])
    start = time.perf_counter()
    assert client.get(url(project, "configuration")).status_code == 200
    evaluation = time.perf_counter() - start
    start = time.perf_counter()
    assert client.get(url(project, "catalog/options")).status_code == 200
    listing = time.perf_counter() - start
    assert evaluation < 2.0 and listing < 4.0, (evaluation, listing)  # Spez. 11.5: p95 < 800 ms für PATCH


# ---------------------------------------------------------------------------
# Katalogpflege
# ---------------------------------------------------------------------------


def test_module_kind_and_dimensions_are_validated_and_filled(db_session: Any) -> None:
    from app.platform.problems import Problem

    created = catalog_service.create_module_version(
        db_session, "terrasse_b", ModuleIn(label_de="T", label_fr="T", kind="terrace"), "test"
    )
    assert created.params == {"depth_m": 3.0, "height_above_terrain_m": 0.3, "sealing_factor": 1.0}
    carport = catalog_service.create_module_version(
        db_session, "cp", ModuleIn(label_de="C", label_fr="C", kind="carport", params={"spaces": 2}), "test"
    )
    assert carport.params["width_m"] == 6.0 and carport.params["depth_m"] == 5.0
    for body in (
        ModuleIn(label_de="C", label_fr="C", kind="carport", params={"spaces": 5}),
        ModuleIn(label_de="C", label_fr="C", kind="terrace", params={"depth_m": 99}),
        ModuleIn(label_de="C", label_fr="C", regulatory={"facade_material": "gold"}),
    ):
        with pytest.raises(Problem) as error:
            catalog_service.create_module_version(db_session, "bad", body, "test")
        assert error.value.status == 422


def test_older_version_published_later_does_not_replace_the_newer_one(db_session: Any) -> None:
    for _ in range(2):
        catalog_service.create_package_version(
            db_session, "alt", PackageIn(label_de="Alt", label_fr="Alt"), "test"
        )
    catalog_service.publish_package_version(db_session, "alt", 2, "test")
    catalog_service.publish_package_version(db_session, "alt", 1, "test")
    current = [
        p for p in catalog_service.list_packages(db_session) if p.slug == "alt" and p.status == "published"
    ]
    assert {p.version for p in current} == {1, 2}
    from sqlalchemy import select

    from app.catalog.models import Package, PackageVersion

    package = db_session.execute(select(Package).where(Package.slug == "alt")).scalar_one()
    newest = db_session.get(PackageVersion, package.current_version_id)
    assert newest.version == 2
    again = catalog_service.publish_package_version(db_session, "alt", 2, "test")
    assert again.status == "published"


def test_regulatory_material_of_a_line_is_stored(db_session: Any) -> None:
    created = catalog_service.create_package_version(
        db_session,
        "holz",
        PackageIn(label_de="H", label_fr="H", regulatory={"facade_material": "wood", "roof_material": ""}),
        "test",
    )
    assert created.regulatory == {"facade_material": "wood"}


def test_new_price_draft_starts_from_the_published_prices(offers: None, db_session: Any) -> None:
    """Befund beim Bau: Ein neuer Entwurf begann leer, die nächste Veröffentlichung hätte alle Preise der
    nicht neu importierten Typen verloren (Plan H3 10.1a Nr. 12)."""
    kennwerte = {**LIGNE_KENNWERTE, "name": "Zweiter", "neigung_deg": "35.0", "familie": "zweiter"}
    import_priced(
        db_session, "zweiter", facade=rect(11, 8), kennwerte=kennwerte, prices=[("linie", "confort", 30_000)]
    )
    draft = catalog_service.get_draft_price_catalog(db_session, "test")
    assert draft.status == "draft" and draft.version == 2
    assert {b.building_type_slug for b in draft.base_prices} >= {"preisig", "zweiter"}
    assert ("confort", "preisig", 3_400_000) in {
        (p.package_slug, p.building_type_slug, p.surcharge_cents) for p in draft.package_prices
    }
    assert ("terrasse", "preisig") in {(m.module_slug, m.building_type_slug) for m in draft.module_prices}
    assert draft.vat_rate_default == pytest.approx(VAT)
