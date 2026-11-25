"""Jede Route trägt genau eine Zugriffsregel (Plan 3.2).

Öffentliche Routen sind hier ausdrücklich aufgezählt; eine neue öffentliche Route fällt so im Review auf.
Ebenso die `/admin`-Routen, die allen Organisationen offenstehen, ohne ein Projekt im Pfad zu nennen (B-23).
"""

import re
from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import create_app

PUBLIC_ROUTES = {
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/health/jobs"),
    ("GET", "/api/v1/session"),
    ("GET", "/api/v1/flags"),
    ("GET", "/api/v1/legal/notices"),
    ("POST", "/api/v1/projects"),
    ("GET", "/api/v1/auth/staff/login"),
    ("GET", "/api/v1/auth/staff/callback"),
    ("POST", "/api/v1/auth/staff/logout"),
    # G1 hinter Feature-Flag `site_selection`, mit Rate-Limit
    ("GET", "/api/v1/geocode"),
    ("GET", "/api/v1/cadastre/service-area"),
    ("GET", "/api/v1/cadastre/parcels"),
    # V: Zugangslink aus der Kundenmail, mit Rate-Limit (Plan V 3.9)
    ("POST", "/api/v1/access/redeem"),
    ("POST", "/api/v1/access/request"),
}


def _policies(dependant: Dependant) -> list[str]:
    found: list[str] = []
    for dep in dependant.dependencies:
        policy: Any = getattr(dep.call, "__access_policy__", None)
        if policy:
            found.append(policy)
        else:
            found.extend(_policies(dep))
    return found


def test_every_route_declares_exactly_one_access_policy() -> None:
    app = create_app()
    problems: list[str] = []
    public_seen: set[tuple[str, str]] = set()
    routes = [ctx for ctx in iter_route_contexts(app.routes) if isinstance(ctx.original_route, APIRoute)]
    assert len(routes) >= len(PUBLIC_ROUTES)
    for route in routes:
        # Der Routenkontext enthält auch Abhängigkeiten, die am Router hängen
        policies = _policies(route.dependant)
        for method in route.methods or ():
            key = (method, str(route.path))
            if len(policies) != 1:
                problems.append(f"{method} {route.path}: {policies or 'keine Zugriffsregel'}")
            elif policies[0] == "public":
                public_seen.add(key)
    assert not problems, problems
    assert public_seen == PUBLIC_ROUTES


OPEN_WITHOUT_PROJECT = {
    # Nur die Beschreibung der Regelarten für das Formular, keine Daten
    ("GET", "/api/v1/admin/rule-kinds"),
    # Prüft im Handler, ob die Datei zu einem Projekt der Organisation gehört (rules/api.py)
    ("GET", "/api/v1/regulation-files/{file_id}"),
}


def _role_policies(dependant: Dependant) -> list[Any]:
    found: list[Any] = []
    for dep in dependant.dependencies:
        if str(getattr(dep.call, "__access_policy__", "")).startswith("roles:"):
            found.append(dep.call)
        else:
            found.extend(_role_policies(dep))
    return found


def test_organisation_check_cannot_be_bypassed_by_a_path_name() -> None:
    """`require_roles` prüft die Organisation nur über den Pfadparameter `project_id` (B-23, REFACTORING_PLAN
    S11). Deshalb: Ein Projekt im Pfad heißt genau so, und eine Route, die allen Organisationen offensteht und
    kein Projekt nennt, ist oben begründet."""
    app = create_app()
    problems: list[str] = []
    open_seen: set[tuple[str, str]] = set()
    for route in iter_route_contexts(app.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        path = str(route.path)
        for policy in _role_policies(route.dependant):
            for name in re.findall(r"/projects/\{([^}:]+)", path):
                if name != "project_id":
                    problems.append(f"{path}: Projekt als {{{name}}} statt {{project_id}}")
            if getattr(policy, "__open_to_organisations__", False) and "{project_id}" not in path:
                open_seen |= {(method, path) for method in route.methods or ()}
    assert not problems, problems
    assert open_seen == OPEN_WITHOUT_PROJECT


SERVICE_ROUTES = {
    # Regeldienst für die Massenstudie, nur lesend (ADR-12, docs/PLAN_REGELDIENST.md 4)
    ("GET", "/api/v1/service/rules/communes/{insee}", "service:rules:read"),
    ("GET", "/api/v1/service/rules/communes/{insee}/zones/{zone_code}", "service:rules:read"),
}


def test_service_tokens_reach_only_listed_read_routes() -> None:
    """Ein Service-Token öffnet nur die hier aufgezählten Routen unter `/api/v1/service/`, und dort gilt keine
    andere Zugriffsregel; eine neue Route für andere Dienste fällt so im Review auf."""
    app = create_app()
    seen: set[tuple[str, str, str]] = set()
    for route in iter_route_contexts(app.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        path = str(route.path)
        policies = _policies(route.dependant)
        for method in route.methods or ():
            if path.startswith("/api/v1/service/") or any(p.startswith("service:") for p in policies):
                seen |= {(method, path, policy) for policy in policies}
    assert seen == SERVICE_ROUTES
