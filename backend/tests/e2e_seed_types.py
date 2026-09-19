"""Drei veröffentlichte Testtypen für den Konfigurator (H2) im lokalen Stack, nach dem Muster der Typen des
Mockups: Ligne (passt), Plateau (Flachdach, gesperrt in Zone UB/Uh) und Plateau — angepasst (Ersatz).

    docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types

Die Typen heißen `demo_*` und sind erfundene Werte, keine echten Typdaten (Plan H1 Kapitel 12).
Ein zweiter Lauf legt neue Versionen an und veröffentlicht sie.
"""

from typing import Any

from sqlalchemy import select

from app.catalog import service
from app.catalog.models import BuildingType
from app.catalog.schemas import FacadeRolesIn
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


def main() -> None:
    with get_sessionmaker()() as db:
        for slug, kennwerte, width, alternatives in TYPES:
            xlsx = _xlsx(kennwerte, ROOMS, [])
            dxf = _dxf(rect(width, 8.0), rect(width, 8.0, 0.5))
            created: Any = service.import_type_version(db, slug, xlsx, dxf, "seed")
            service.set_facade_roles(db, slug, created.version, FacadeRolesIn(roles=ROLES), "seed")  # type: ignore[arg-type]
            service.publish_type_version(db, slug, created.version, "seed")
            if alternatives:
                building_type = db.execute(select(BuildingType).where(BuildingType.slug == slug)).scalar_one()
                building_type.alternatives = alternatives
                db.commit()
            print(f"{slug} v{created.version} veröffentlicht")


if __name__ == "__main__":
    main()
