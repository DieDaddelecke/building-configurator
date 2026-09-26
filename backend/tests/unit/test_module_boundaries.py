"""Grenze zwischen Kern und Produktmodulen (AN0, docs/PLAN_ANALYSE.md 3).

Der Kern trägt beide Produkte und darf deshalb nichts aus dem Hauskonfigurator importieren. Die Prüfung
läuft über den Syntaxbaum, damit auch Importe innerhalb von Funktionen auffallen. Dazu wird geprüft, dass
die Listen in `app/products.py` vollständig und die Profile geschnitten sind.
"""

import ast
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path

from fastapi.routing import iter_route_contexts

import app.registry  # noqa: F401  meldet die Jobarten des laufenden Produkts an
from app.config import Settings
from app.main import create_app
from app.platform.jobs.registry import periodic_specs
from app.products import PRODUCT_NAMES, PRODUCTS, Product, spec_for

APP = Path(__file__).resolve().parents[2] / "app"
CORE_PACKAGES = ("platform", "integrations", "site", "rules", "envelope", "plan")
PRODUCT_PACKAGES = ("catalog", "configuration", "inquiry", "submission", "analysis")


def _package_of(path: Path) -> str:
    """Paket, in dem die Datei liegt: `app/site/jobs.py` und `app/site/__init__.py` → `app.site`."""
    return ".".join(path.relative_to(APP.parent).parts[:-1])


def _imports(path: Path) -> Iterator[str]:
    package = _package_of(path)
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if not node.level:
                if node.module:
                    yield node.module
                continue
            parts = package.split(".")
            base = ".".join(parts[: len(parts) - (node.level - 1)])
            yield f"{base}.{node.module}" if node.module else base


def test_core_does_not_import_product_modules() -> None:
    forbidden = tuple(f"app.{name}" for name in PRODUCT_PACKAGES)
    for package in CORE_PACKAGES:
        for path in sorted((APP / package).rglob("*.py")):
            for module in _imports(path):
                assert not module.startswith(forbidden), (
                    f"{path.relative_to(APP.parent)} importiert {module}: Der Kern trägt beide Produkte "
                    "und darf nichts aus dem Hauskonfigurator kennen (PLAN_ANALYSE 3)."
                )


def test_every_product_module_is_importable() -> None:
    for name in PRODUCT_NAMES:
        spec = spec_for(name)
        for module in spec.routers:
            assert hasattr(import_module(module), "router"), f"{module} hat keinen router"
        for module in spec.job_modules:
            import_module(module)


def test_periodic_tasks_are_assigned_to_a_product() -> None:
    """Jede angemeldete periodische Aufgabe steht in mindestens einem Profil – und umgekehrt."""
    registered = {spec.name for spec in periodic_specs()}
    assigned = set[str]().union(*(spec.periodic for spec in PRODUCTS.values()))
    assert registered == assigned, (
        "app/products.py und die `periodic(...)`-Aufrufe passen nicht zusammen: "
        f"nur angemeldet {sorted(registered - assigned)}, nur eingetragen {sorted(assigned - registered)}"
    )


def _served(product: Product) -> set[tuple[str, str]]:
    """Methode und Pfad jeder Route, die eine Instanz dieses Produkts bedient."""
    app = create_app(Settings(product=product))
    return {
        (method, str(ctx.path))
        for ctx in iter_route_contexts(app.routes)
        for method in getattr(ctx, "methods", None) or ()
    }


def _routes_of(module: str) -> set[tuple[str, str]]:
    return {
        (method, f"/api/v1{route.path}")
        for route in import_module(module).router.routes
        for method in getattr(route, "methods", None) or ()
    }


def test_analyse_profile_serves_no_configurator_routes() -> None:
    served = _served("analyse")
    only_configurator = set(spec_for("configurator").routers) - set(spec_for("analyse").routers)
    assert only_configurator, "Ohne Unterschied prüft dieser Test nichts"
    for module in only_configurator:
        extra = sorted(_routes_of(module) & served)
        assert not extra, f"{module} läuft im Analyse-Produkt mit: {extra}"


def test_analyse_profile_serves_site_rules_and_envelope() -> None:
    """Der Kern G1–G3 ist der Zweck des zweiten Produkts und muss vorhanden sein."""
    served = _served("analyse")
    assert ("GET", "/api/v1/projects/{project_id}/site") in served
    assert ("GET", "/api/v1/projects/{project_id}/rules") in served
    assert ("GET", "/api/v1/projects/{project_id}/envelope") in served


def test_configurator_serves_no_analysis_routes_but_openapi_has_both() -> None:
    """AN3: `analysis` läuft nur im Analyse-Produkt; `openapi.json` beschreibt trotzdem alle Routen."""
    from app.main import create_full_app

    served = _served("configurator")
    analysis = _routes_of("app.analysis.api")
    assert analysis and not analysis & served
    full = {
        (method, str(ctx.path))
        for ctx in iter_route_contexts(create_full_app().routes)
        for method in getattr(ctx, "methods", None) or ()
    }
    assert analysis <= full and served <= full
