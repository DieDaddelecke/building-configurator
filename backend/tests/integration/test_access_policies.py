"""Jede Route trägt genau eine Zugriffsregel (Plan 3.2).

Öffentliche Routen sind hier ausdrücklich aufgezählt; eine neue öffentliche Route fällt so im Review auf.
"""

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
