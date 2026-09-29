"""Grenze zwischen Kern und Fachmodulen (AN0, PLAN_ANALYSE 3); Vollständigkeit von `app/products.py`.

Der Kern (G1–G3, Plattform) trägt Konfigurator und Analyse und darf deshalb nichts aus deren Fachmodulen
importieren. Die Prüfung läuft über den Syntaxbaum, damit auch Importe innerhalb von Funktionen auffallen.
"""

import ast
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path

from fastapi.routing import iter_route_contexts

from app.main import create_app
from app.products import JOB_MODULES, ROUTERS

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
                    f"{path.relative_to(APP.parent)} importiert {module}: Der Kern trägt Konfigurator und "
                    "Analyse und darf nichts aus deren Fachmodulen kennen (PLAN_ANALYSE 3)."
                )


def test_every_listed_module_is_importable() -> None:
    for module in ROUTERS:
        assert hasattr(import_module(module), "router"), f"{module} hat keinen router"
    for module in JOB_MODULES:
        import_module(module)


def test_every_module_with_a_router_or_jobs_is_listed() -> None:
    """Ein Modul mit `router` oder `@job` außerhalb der Listen liefe nirgends."""
    for path in sorted(APP.rglob("*.py")):
        module = ".".join(path.relative_to(APP.parent).with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        has_router = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "router" for t in node.targets)
            for node in tree.body
        )
        has_jobs = any(
            isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "job"
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for dec in node.decorator_list
        )
        if has_router and module != "app.platform.health":
            assert module in ROUTERS, f"{module} hat einen router, steht aber nicht in app/products.py"
        if has_jobs:
            assert module in JOB_MODULES, f"{module} meldet Jobs an, steht aber nicht in app/products.py"


def _routes_of(module: str) -> set[tuple[str, str]]:
    return {
        (method, f"/api/v1{route.path}")
        for route in import_module(module).router.routes
        for method in getattr(route, "methods", None) or ()
    }


def test_app_serves_configurator_and_analysis() -> None:
    served = {
        (method, str(ctx.path))
        for ctx in iter_route_contexts(create_app().routes)
        for method in getattr(ctx, "methods", None) or ()
    }
    for module in ROUTERS:
        assert _routes_of(module) <= served, f"{module} fehlt in der Anwendung"
