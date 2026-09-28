"""Welche Module ein Produkt lädt (docs/PLAN_ANALYSE.md 3 und AN0).

Ein Repository, zwei Produkte aus demselben Kern (D16): `configurator` – der Hauskonfigurator und
Standard – und `analyse` – „Emprise Analyse“ für Architekten. Der Kern ist `platform`, `integrations`,
`site` (G1), `rules` (G2), `envelope` (G3) und `plan` (Lageplan und DXF); die Produktmodule kommen je
Produkt dazu. Welches Produkt eine Instanz ist, sagt `EMPRISE_PRODUCT`; die Wahl wirkt nur zur Laufzeit.

`openapi.json` entsteht weiter aus dem vollen Profil des Konfigurators (`app.main.create_full_app`),
damit es eine Datei bleibt und `frontend/src/api/schema.d.ts` nicht doppelt gepflegt werden muss.

Neue Router, Job-Module und periodische Aufgaben gehören hier eingetragen; `test_module_boundaries.py`
prüft, dass nichts vergessen wurde und dass der Kern kein Produktmodul importiert.
"""

from dataclasses import dataclass
from typing import Literal, get_args

Product = Literal["configurator", "analyse"]
PRODUCT_NAMES: tuple[Product, ...] = get_args(Product)

CORE_ROUTERS: tuple[str, ...] = (
    "app.platform.auth.staff",
    "app.platform.projects",
    "app.platform.flags",
    "app.platform.legal",
    "app.platform.ops",
    "app.platform.jobs.api",
    "app.site.api",
    "app.rules.api",
    "app.envelope.api",
    "app.rules.reference_api",
)
"""Reihenfolge bestimmt die Reihenfolge in `openapi.json`; nur hinten anfügen."""

CORE_JOB_MODULES: tuple[str, ...] = (
    "app.envelope.jobs",
    "app.platform.mail",
    "app.platform.tasks",
    "app.rules.jobs",
    "app.site.jobs",
)

CORE_PERIODIC: frozenset[str] = frozenset(
    {"retention_cleanup", "housekeeping", "rules_housekeeping", "site_housekeeping"}
)
"""Periodische Aufgaben beider Produkte. `cadastre_import` und `plu_import` beschaffen Daten für ein
festes Einzugsgebiet (D1) und laufen deshalb nur im Konfigurator; im Analyse-Produkt liefern die Nutzer
das Material selbst (D17). Die Jobarten bleiben trotzdem registriert, damit die CLI sie starten kann."""


@dataclass(frozen=True)
class ProductSpec:
    name: Product
    routers: tuple[str, ...]
    """Module mit einem `router`, in dieser Reihenfolge unter `/api/v1` eingehängt."""
    job_modules: tuple[str, ...]
    """Module, die Jobarten mit `@job(...)` anmelden; `app.registry` importiert sie."""
    periodic: frozenset[str]
    """Namen der periodischen Aufgaben, die der Worker dieses Produkts einplant."""
    staff_home: str
    """Seite nach der Anmeldung einer Mitarbeiterin, wenn kein Ziel mitkommt (AN1)."""
    staff_denied: str
    """Seite, wenn die Anmeldung abgelehnt wird; bekommt den Grund als Abfrageparameter."""


PRODUCTS: dict[Product, ProductSpec] = {
    "configurator": ProductSpec(
        name="configurator",
        routers=(
            *CORE_ROUTERS,
            "app.catalog.api",
            "app.configuration.api",
            "app.inquiry.api",
            "app.submission.api",
        ),
        job_modules=(*CORE_JOB_MODULES, "app.submission.jobs"),
        periodic=CORE_PERIODIC | {"cadastre_import", "plu_import"},
        staff_home="/buero",
        staff_denied="/buero/kein-zugang",
    ),
    # Eigenes Modul `analysis` seit AN3 (docs/PLAN_AN3_ANALYSE.md); Parzelle und PLU liegen im Kern (AN1, AN2)
    "analyse": ProductSpec(
        name="analyse",
        routers=(*CORE_ROUTERS, "app.analysis.api"),
        job_modules=CORE_JOB_MODULES,
        periodic=CORE_PERIODIC,
        staff_home="/",
        staff_denied="/",
    ),
}


def spec_for(product: Product) -> ProductSpec:
    return PRODUCTS[product]


ALL_ROUTERS: tuple[str, ...] = tuple(dict.fromkeys(r for spec in PRODUCTS.values() for r in spec.routers))
"""Vereinigung aller Profile für `openapi.json` (PLAN_ANALYSE 8.1 Nr. 5): Routen, die nur das Analyse-
Produkt hat, stehen hinten – die Reihenfolge des Konfigurators bleibt unverändert."""
