"""Lädt alle Module, die Jobs oder periodische Aufgaben anmelden. API und Worker importieren diese Datei."""

import app.platform.mail
import app.platform.tasks  # noqa: F401
