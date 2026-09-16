"""Lädt alle Module, die Jobs oder periodische Aufgaben anmelden. API und Worker importieren diese Datei."""

import app.envelope.jobs
import app.platform.mail
import app.platform.tasks
import app.rules.jobs
import app.site.jobs  # noqa: F401
