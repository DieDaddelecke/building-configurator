"""Zahlen, Beträge und Texte für Dossier und Mails (V 3.7, 3.10). Französisch führt (D7).

Die Texte der Prüfungen stehen unter `check.*` in den Übersetzungen des Backends und kommen aus dem
Frontend (`tools/sync-check-texts.cjs`); `check_text` bildet `checkText` aus `configuration/format.ts` nach.
"""

from datetime import datetime
from typing import Any

from app.platform.i18n import Locale, translate

AREA_CHECKS = {"footprint", "footprint_total", "unsealed_min", "annex_footprint"}
MATERIAL_CHECKS = {"facade_material", "roof_material"}
_THOUSANDS = {"de": ".", "fr": " "}


class _Blank(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return ""


def tr(key: str, locale: Locale, **params: object) -> str:
    """Übersetzung mit Platzhaltern; fehlt ein Platzhalter, bleibt er leer (wie i18next ohne Wert)."""
    return translate(key, locale).format_map(_Blank(params))


def known(key: str, locale: Locale) -> bool:
    return translate(key, locale) != key


def number(value: float | int | None, locale: Locale, digits: int = 0) -> str:
    if value is None:
        return "–"
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", _THOUSANDS[locale])


def money(cents: int, locale: Locale) -> str:
    return f"{number(round(cents / 100), locale, 0)} €"


def date(value: str | datetime, locale: Locale) -> str:
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return moment.strftime("%d.%m.%Y" if locale == "de" else "%d/%m/%Y")


def label(item: dict[str, Any] | None, locale: Locale) -> str | None:
    if not item:
        return None
    first, second = ("label_de", "label_fr") if locale == "de" else ("label_fr", "label_de")
    value = item.get(first) or item.get(second) or item.get("slug")
    return str(value) if value else None


def costs_text(costs: dict[str, Any] | None, locale: Locale) -> str:
    """„ca. 384.000 – 418.000 €“; nur die gerundete Spanne (L1)."""
    if not costs or not costs.get("available") or not costs.get("display"):
        return tr("dossier.costs.unavailable", locale)
    display = costs["display"]
    return tr(
        "dossier.costs.range",
        locale,
        min=money(display["min_cents"], locale),
        max=money(display["max_cents"], locale),
    )


def parcels(site: dict[str, Any]) -> str:
    items = site.get("parcels") or []
    if items:
        return " + ".join(f"{p['section']} {int(p['number'])}" for p in items)
    return str(site.get("address_label") or "–")


def _words(value: object, prefix: str, locale: Locale) -> str:
    parts = [part for part in str(value or "").split(",") if part]
    return ", ".join(tr(f"{prefix}.{p}", locale) if known(f"{prefix}.{p}", locale) else p for p in parts)


def check_text(check: dict[str, Any], locale: Locale, names: dict[str, str] | None = None) -> str:
    """Text einer Prüfung mit Messwert und Grenze; unbekannte Codes erscheinen als Code, nie leer."""
    names = names or {}
    code = str(check["code"])
    params = check.get("params") or {}
    slug = params.get("subject") if isinstance(params.get("subject"), str) else ""
    key = "no_valid_position_option" if code == "no_valid_position" and slug else code
    if not known(f"check.{key}", locale):
        return code

    def value(raw: object) -> str:
        if code in ("roof_form", "roof_form_open", "roof_flat"):
            return _words(raw, "check_roof", locale)
        if code in MATERIAL_CHECKS:
            return _words(raw, "check_material", locale)
        if isinstance(raw, int | float) and not isinstance(raw, bool):
            return number(raw, locale, 1 if code in AREA_CHECKS else 2)
        return str(raw or "")

    orientation = params.get("orientation")
    reason = check.get("reason")
    # Mehrere Neigungen einer Mansarde oder eines Krüppelwalms (E-HM-61)
    pitches = " / ".join(
        f"{number(float(p), locale, 1)}°" for p in str(params.get("pitches") or "").split(",") if p
    )
    return tr(
        f"check.{key}",
        locale,
        measured=value(check.get("measured")),
        limit=value(check.get("limit")),
        orientation=_words(orientation, "check_orientation", locale) if orientation else "",
        reason=_words(reason, "check_reason", locale) if reason else "",
        subject=names.get(str(slug), str(slug)),
        readings=_words(params.get("readings"), "check_roof", locale),
        pitches=pitches,
    )


def edge_name(kind: str, seq: int, locale: Locale) -> str:
    return tr(f"check_edge.{kind if kind in ('street', 'side', 'rear') else 'other'}", locale, seq=seq)


def compass(azimuth_deg: float, locale: Locale) -> str:
    keys = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
    return tr(f"compass.{keys[round((azimuth_deg % 360) / 45) % 8]}", locale)
