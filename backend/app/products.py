"""Welche Module die Anwendung lädt: Router und Job-Module.

Konfigurator und „Emprise Analyse“ sind eine Anwendung mit einer Datenbank (Entscheidung des Nutzers vom
29.09.2026, REFACTORING_PLAN S1); die Bereiche trennt das Frontend (`/`, `/buero`, `/analyse`). Der Kern ist
`platform`, `integrations`, `site` (G1), `rules` (G2), `envelope` (G3) und `plan` (Lageplan und DXF); die
Fachmodule des Konfigurators und der Analyse kommen dazu.

Neue Router und Job-Module gehören hier eingetragen, sonst laufen sie nicht; `test_module_boundaries.py`
prüft, dass jedes genannte Modul existiert und dass der Kern kein Konfigurator-Modul importiert. Periodische
Aufgaben plant der Worker alle ein, die ein geladenes Job-Modul mit `periodic(...)` anmeldet.
"""

ROUTERS: tuple[str, ...] = (
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
    "app.platform.org_api",
    "app.catalog.api",
    "app.configuration.api",
    "app.inquiry.api",
    "app.submission.api",
    "app.analysis.api",
    "app.house.api",
)
"""Reihenfolge bestimmt die Reihenfolge in `openapi.json`; nur hinten anfügen."""

JOB_MODULES: tuple[str, ...] = (
    "app.envelope.jobs",
    "app.platform.mail",
    "app.platform.tasks",
    "app.rules.jobs",
    "app.site.jobs",
    "app.submission.jobs",
    "app.analysis.jobs",
    "app.house.jobs",
)
