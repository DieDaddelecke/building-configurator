"""Prüfstempel für die Übergabe des Vorentwurfs (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.3, 3.4).

Der Stempel fasst in sechs benannten Teilen zusammen, worauf eine Auswertung beruht und was sie ergibt. Die
Oberfläche schickt den Stempel, den sie angezeigt hat, mit der Übergabe zurück; weicht der neu gerechnete ab,
nennt der Vergleich die Teile, die sich geändert haben. Gehasht wird der Inhalt, nicht Versionsnummern oder
Zeitstempel (wie die Prüfsumme des Baurahmens, Plan G3 4.2). Ohne Datenbank.
"""

import hashlib
import json
from typing import Any

from app.catalog.domain.offer import TypeOffer
from app.configuration.domain.options import Selection
from app.configuration.schemas import CheckOut, ConfigurationOut

STAMP_VERSION = "v1"
PARTS = ("site", "rules", "catalog", "configuration", "result", "engine")
_RESULT_EXCLUDED = {"project_id", "revision", "engine_version", "updated_at", "review_stamp"}


def canonical(value: Any) -> Any:
    """Schlüssel sortiert, Listen als Mengen: Eine andere Reihenfolge (Mengen in Python ordnen je Prozess
    anders) soll keinen Wechsel vortäuschen (Plan V 9.1 Nr. 5)."""
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        items = [canonical(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def digest(value: Any) -> str:
    raw = json.dumps(canonical(value), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def catalog_part(type_version_id: str, type_status: str, offer: TypeOffer, selection: Selection) -> str:
    """Versionen und Status von Typ, Linie und gewählten Optionen, dazu Stand und Satz des Preiskatalogs."""
    package = offer.package(selection.package_slug)
    options = [offer.option(slug) for slug in selection.option_slugs]
    return digest(
        {
            "type": [type_version_id, type_status],
            "package": [package.version_id, package.status] if package else None,
            "options": [[o.version_id, o.status] for o in options if o is not None],
            "price": [offer.catalog_version_id, offer.vat_rate],
        }
    )


def result_part(out: ConfigurationOut) -> str:
    """Inhalt der Auswertung. `selection.dropped` steht nur in der Antwort auf `PATCH` (Plan V 9.1 Nr. 4)."""
    data = out.model_dump(mode="json", exclude=_RESULT_EXCLUDED)
    if isinstance(data.get("selection"), dict):
        data["selection"].pop("dropped", None)
    return digest(data)


def make_stamp(parts: dict[str, str]) -> str:
    return f"{STAMP_VERSION}:" + ".".join(f"{name}={parts[name]}" for name in PARTS)


def parse_stamp(stamp: str | None) -> dict[str, str]:
    """Teile eines Stempels; unlesbar oder aus einer anderen Fassung: leer (dann gilt alles als geändert)."""
    if not stamp or not stamp.startswith(f"{STAMP_VERSION}:"):
        return {}
    parts: dict[str, str] = {}
    for item in stamp.removeprefix(f"{STAMP_VERSION}:").split("."):
        name, _, value = item.partition("=")
        if name in PARTS and value:
            parts[name] = value
    return parts


def changes(seen: str | None, current: str) -> list[str]:
    """Teile, in denen sich der angezeigte vom neu gerechneten Stempel unterscheidet."""
    old, new = parse_stamp(seen), parse_stamp(current)
    return [name for name in PARTS if old.get(name) != new.get(name)]


def _key(check: CheckOut) -> tuple[str, str | None, int | None, str | None]:
    subject = check.params.get("subject")
    return check.code, check.zone_code, check.edge_seq, str(subject) if subject is not None else None


def _all_checks(out: ConfigurationOut) -> list[CheckOut]:
    """Prüfungen aus Zulässigkeit (H2), Lage (H2) und Auswahl (H3), jede einmal."""
    found: dict[tuple[str, str | None, int | None, str | None], CheckOut] = {}
    sources = [
        out.fit.reasons if out.fit else [],
        out.evaluation.checks if out.evaluation else [],
        out.compliance.checks if out.compliance else [],
    ]
    for checks in sources:
        for check in checks:
            found.setdefault(_key(check), check)
    return list(found.values())


def deviations(out: ConfigurationOut) -> list[CheckOut]:
    """Bindende Verstöße (Plan V 3.4): nur mit ausdrücklicher Bestätigung übergebbar."""
    return [c for c in _all_checks(out) if c.binding and c.status == "fail"]


def open_points(out: ConfigurationOut) -> int:
    """Nicht ermittelte Prüfungen (`unknown`): offene Prüfpunkte im Dossier, sie hindern nie."""
    return sum(1 for c in _all_checks(out) if c.status == "unknown")
