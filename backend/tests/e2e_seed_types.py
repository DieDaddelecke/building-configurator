"""Drei veröffentlichte Testtypen für den Konfigurator (H2, H3) im lokalen Stack, nach dem Muster der Typen
des Mockups: Ligne (passt), Plateau (Flachdach, gesperrt in Zone UB/Uh) und Plateau — angepasst (Ersatz).
Dazu Linien, Optionen und ein veröffentlichter Preiskatalog (erfundene Preise).

    docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types

Die Typen heißen `demo_*` und sind erfundene Werte, keine echten Typdaten (Plan H1 Kapitel 12).
Ein zweiter Lauf legt neue Typversionen an und veröffentlicht sie; Linien und Optionen bleiben bestehen.
"""

from typing import Any

from sqlalchemy import select

from app.catalog import service
from app.catalog.models import BuildingType
from app.catalog.schemas import FacadeRolesIn, ModuleIn, PackageIn
from app.platform.db import get_sessionmaker
from tests.integration.test_catalog import LIGNE_KENNWERTE, ROOMS, _dxf, _xlsx

ROLES = {"0": "garden", "1": "side_right", "2": "street", "3": "side_left"}


def rect(width: float, depth: float, margin: float = 0.0) -> list[tuple[float, float]]:
    return [
        (-margin, -margin),
        (width + margin, -margin),
        (width + margin, depth + margin),
        (-margin, depth + margin),
    ]


TYPES: list[tuple[str, dict[str, str], float, list[str]]] = [
    (
        "demo_ligne",
        {**LIGNE_KENNWERTE, "name": "Ligne (Demo)", "neigung_deg": "35.0", "familie": "ligne"},
        12.0,
        [],
    ),
    (
        "demo_plateau",
        {
            **{k: v for k, v in LIGNE_KENNWERTE.items() if k not in ("neigung_deg", "firstrichtung")},
            "name": "Plateau (Demo)",
            "dachform": "flat",
            "firsthoehe_m": "6.8",
            "traufhoehe_m": "6.8",
            "wohnflaeche_m2": "141",
            "familie": "plateau",
        },
        16.5,
        ["demo_plateau_adapte"],
    ),
    (
        "demo_plateau_adapte",
        {
            **LIGNE_KENNWERTE,
            "name": "Plateau — angepasst (Demo)",
            "neigung_deg": "37.8",
            "firsthoehe_m": "8.1",
            "traufhoehe_m": "5.0",
            "wohnflaeche_m2": "132",
            "familie": "plateau",
        },
        13.5,
        [],
    ),
]


# Linien und Optionen der Demo (Aufschläge in Euro netto, Terrasse je m²): erfundene Werte wie die Typen
LINES = [
    ("base", "Base", "Base", [], []),
    ("confort", "Confort", "Confort", ["Fassade Putz durchgefärbt", "Fenster Holz-Alu"], ["pv"]),
]
OPTIONS: list[tuple[str, str, str, str, dict[str, Any]]] = [
    ("terrasse", "Terrasse Holz", "Terrasse bois", "terrace", {}),
    ("carport_1", "Carport einstellig", "Carport simple", "carport", {"spaces": 1}),
    ("carport_2", "Carport zweistellig", "Carport double", "carport", {"spaces": 2}),
    ("pv", "Photovoltaik 6 kWp", "Photovoltaïque 6 kWc", "plain", {}),
    (
        "holz_sued",
        "Holzverschalung Lärche (Süd)",
        "Bardage mélèze (sud)",
        "plain",
        {"facade_material": "wood"},
    ),
]
PRICES: list[tuple[str, str, int]] = [
    ("linie", "base", 0),
    ("linie", "confort", 34_000),
    ("option", "terrasse", 400),
    ("option", "carport_1", 9_000),
    ("option", "carport_2", 14_500),
    ("option", "pv", 11_200),
    ("option", "holz_sued", 12_400),
]


def seed_offers(db: Any) -> None:
    """Optionen und Linien einmal anlegen und veröffentlichen (ein zweiter Lauf lässt sie in Ruhe)."""
    have = {m.slug for m in service.list_modules(db)} | {p.slug for p in service.list_packages(db)}
    for slug, label_de, label_fr, kind, extra in OPTIONS:
        if slug in have:
            continue
        regulatory = {k: v for k, v in extra.items() if k.endswith("_material")}
        params = {k: v for k, v in extra.items() if not k.endswith("_material")}
        service.create_module_version(
            db,
            slug,
            ModuleIn(label_de=label_de, label_fr=label_fr, kind=kind, params=params, regulatory=regulatory),
            "seed",  # type: ignore[arg-type]
        )
        service.publish_module_version(db, slug, 1, "seed")
    for slug, label_de, label_fr, scope, included in LINES:
        if slug in have:
            continue
        service.create_package_version(
            db,
            slug,
            PackageIn(label_de=label_de, label_fr=label_fr, scope=scope, included_option_slugs=included),
            "seed",
        )
        service.publish_package_version(db, slug, 1, "seed")


def main() -> None:
    with get_sessionmaker()() as db:
        seed_offers(db)
        for slug, kennwerte, width, alternatives in TYPES:
            xlsx = _xlsx(kennwerte, ROOMS, PRICES)
            dxf = _dxf(rect(width, 8.0), rect(width, 8.0, 0.5))
            created: Any = service.import_type_version(db, slug, xlsx, dxf, "seed")
            service.set_facade_roles(db, slug, created.version, FacadeRolesIn(roles=ROLES), "seed")  # type: ignore[arg-type]
            service.publish_type_version(db, slug, created.version, "seed")
            if alternatives:
                building_type = db.execute(select(BuildingType).where(BuildingType.slug == slug)).scalar_one()
                building_type.alternatives = alternatives
                db.commit()
            print(f"{slug} v{created.version} veröffentlicht")
        service.set_energy_assessment(
            db,
            "demo_ligne",
            "base",
            climate_zone="H2b",
            verdict="Linie Base verfehlt den Bbio-Schwellenwert knapp",
            compliant=False,
            compliance_surcharge_cents=950_000,
            measures="verstärkte Dämmung und kontrollierte Lüftung",
            actor_id="seed",
        )
        published = service.publish_price_catalog(db, "seed")
        print(f"Preiskatalog Version {published.version} veröffentlicht")


if __name__ == "__main__":
    main()
