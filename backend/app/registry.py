"""Lädt die Module, die Jobs oder periodische Aufgaben anmelden. API, Worker und CLI importieren diese Datei.

Welche Module das sind, sagt `app.products` für das Produkt dieser Instanz (`EMPRISE_PRODUCT`).
"""

from importlib import import_module

from app.config import get_settings
from app.products import spec_for

for _name in spec_for(get_settings().product).job_modules:
    import_module(_name)
