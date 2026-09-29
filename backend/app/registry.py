"""Lädt die Module, die Jobs oder periodische Aufgaben anmelden. API, Worker und CLI importieren diese Datei.

Welche Module das sind, sagt `app.products`.
"""

from importlib import import_module

from app.products import JOB_MODULES

for _name in JOB_MODULES:
    import_module(_name)
