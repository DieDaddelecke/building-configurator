"""Werte einer Regel als kurzer Text (Spez. 5.2.4) für Steckbrief und Bericht.

Gegenstück zu `frontend/src/rules/format.ts`; beide zeigen dieselben Sätze. Die Texte kommen aus den
Übersetzungen des Frontends (`tools/sync-check-texts.cjs`, Präfixe `rule_*`). Einheiten: Meter, Anteile 0–1,
Grad. Jeder Parameter einer wirksamen Regel erscheint; eine wirksame Regel ergibt nie einen leeren Text.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.platform.i18n import Locale, translate

_GROUP: dict[Locale, str] = {"de": ".", "fr": " "}
"""Tausendertrennung wie `Intl.NumberFormat` (de-DE, fr-FR)."""


def number(value: Any, locale: Locale, digits: int = 2) -> str:
    """Zahl mit höchstens `digits` Stellen nach dem Komma, ohne Nullen am Ende (`maximumFractionDigits`)."""
    if value is None:
        return "?"
    rounded = Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    whole, _, fraction = f"{abs(rounded):f}".partition(".")
    fraction = fraction.rstrip("0")
    groups = f"{int(whole):,}".replace(",", _GROUP[locale])
    sign = "-" if rounded < 0 else ""
    return f"{sign}{groups},{fraction}" if fraction else f"{sign}{groups}"


def _metres(value: Any, locale: Locale) -> str:
    return f"{number(value, locale)} m"


def _percent(value: Any, locale: Locale) -> str:
    return f"{number(None if value is None else float(value) * 100, locale, 1)} %"


def _term(prefix: str, value: object, locale: Locale) -> str:
    """Begriff aus dem Vokabular; unbekannte Werte erscheinen, wie sie sind."""
    key = f"{prefix}{value}"
    text = translate(key, locale)
    return str(value) if text == key else text


def _list(values: object, prefix: str, locale: Locale) -> str:
    return ", ".join(_term(prefix, v, locale) for v in values) if isinstance(values, list | tuple) else ""


def _join(parts: list[str | None]) -> str:
    return " · ".join(p for p in parts if p)


def _t(key: str, locale: Locale, **params: object) -> str:
    return translate(f"rule_value.{key}", locale, **params)


def _measured_from(p: Mapping[str, Any], locale: Locale) -> str | None:
    if p.get("measured_from") == "roof_edge":
        return _t("fromRoofEdge", locale)
    if p.get("measured_from") == "any_projection":
        return _t("fromProjection", locale)
    return None


def _boundary(p: Mapping[str, Any], locale: Locale) -> str:
    parts: list[str] = []
    if p.get("min_m") is not None:
        parts.append(f"≥ {_metres(p['min_m'], locale)}")
    if p.get("height_factor") is not None:
        basis = p.get("height_basis")
        parts.append(
            _t(
                "heightFactor",
                locale,
                factor=number(p["height_factor"], locale),
                basis=_term("rule_basis.", "undefined" if basis is None else basis, locale),
            )
        )
    text = " · ".join(parts)
    if p.get("allow_on_boundary"):
        text = _t("orOnBoundary", locale, value=text)
    height = p.get("on_boundary_max_height_m")
    return _join(
        [
            text,
            _t("onBoundaryHeight", locale, value=_metres(height, locale)) if height is not None else None,
            _measured_from(p, locale),
        ]
    )


def _street(p: Mapping[str, Any], locale: Locale) -> str:
    mode = p.get("mode")
    if mode == "alignment":
        text = _t("alignment", locale)
    elif mode == "range":
        text = _t("range", locale, min=number(p.get("min_m"), locale), max=_metres(p.get("max_m"), locale))
    elif mode == "fixed":
        text = _t("fixed", locale, value=_metres(p.get("min_m"), locale))
    else:
        text = f"≥ {_metres(p.get('min_m'), locale)}"
    return _join([text, _measured_from(p, locale)])


def _pitch(p: Mapping[str, Any], locale: Locale) -> str | None:
    low, high = p.get("pitch_min_deg"), p.get("pitch_max_deg")
    if low is None and high is None:
        return None
    shown = [number(v, locale) if v is not None else "…" for v in (low, high)]
    return f"{shown[0]}–{shown[1]}°"


def rule_values(kind: str, params: Mapping[str, Any], locale: Locale) -> str:
    """Die Werte einer wirksamen Regel; leer, wenn die Regel keine trägt."""
    p = params
    if kind == "setback_street":
        return _street(p, locale)
    if kind in ("setback_side", "setback_rear", "setback_between_buildings"):
        return _boundary(p, locale)
    if kind == "max_footprint_ratio":
        return f"≤ {_percent(p.get('ratio'), locale)}"
    if kind == "max_height":
        return _join(
            [
                f"{_t('eave', locale)} ≤ {_metres(p['eave_m'], locale)}"
                if p.get("eave_m") is not None
                else None,
                f"{_t('ridge', locale)} ≤ {_metres(p['ridge_m'], locale)}"
                if p.get("ridge_m") is not None
                else None,
                f"{_t('parapet', locale)} ≤ {_metres(p['parapet_m'], locale)}"
                if p.get("parapet_m") is not None
                else None,
                str(p["storeys"]) if p.get("storeys") else None,
                _t("streetLevel", locale) if p.get("reference") == "street_level" else None,
                _t("mean", locale) if p.get("measured_at") == "mean" else None,
                _t("roofInstallations", locale) if p.get("includes_roof_installations") is True else None,
            ]
        )
    if kind == "roof":
        materials = p.get("materials_allowed")
        return _join(
            [
                _list(p.get("allowed_forms"), "rule_roof_form.", locale),
                _pitch(p, locale),
                _term("rule_flat_roof.", p["flat_roof"], locale) if p.get("flat_roof") else None,
                _t("ridgeParallel", locale) if p.get("ridge_orientation") == "parallel_to_street" else None,
                _t("ridgePerpendicular", locale)
                if p.get("ridge_orientation") == "perpendicular_to_street"
                else None,
                _t("roofMaterials", locale, value=_list(materials, "rule_material.", locale))
                if isinstance(materials, list) and materials
                else None,
            ]
        )
    if kind == "facade":
        forbidden = p.get("materials_forbidden")
        return _join(
            [
                _list(p.get("materials_allowed"), "rule_material.", locale),
                _t("notMaterials", locale, value=_list(forbidden, "rule_material.", locale))
                if isinstance(forbidden, list) and forbidden
                else None,
                _list(p.get("color_families_allowed"), "rule_color.", locale),
            ]
        )
    if kind == "unsealed_min":
        full = p.get("full_soil_ratio")
        counting = p.get("counting")
        return _join(
            [
                f"≥ {_percent(p['ratio'], locale)}" if p.get("ratio") is not None else None,
                _t("fullSoil", locale, value=_percent(full, locale)) if full is not None else None,
                counting if isinstance(counting, str) else None,
            ]
        )
    if kind == "parking":
        per_dwelling, per_area = p.get("spaces_per_dwelling"), p.get("spaces_per_m2_sdp")
        dimensions = p.get("min_dimensions")
        return _join(
            [
                _t("spacesPerDwelling", locale, value=number(per_dwelling, locale))
                if per_dwelling is not None
                else None,
                _t("spacesPerArea", locale, area=number(1 / float(per_area), locale, 0))
                if per_area
                else None,
                _t("minDimensions", locale, value=dimensions) if isinstance(dimensions, str) else None,
            ]
        )
    if kind == "annex":
        return _join(
            [
                f"≤ {number(p['max_footprint_m2'], locale)} m²"
                if p.get("max_footprint_m2") is not None
                else None,
                f"{_t('height', locale)} ≤ {_metres(p['max_height_m'], locale)}"
                if p.get("max_height_m") is not None
                else None,
            ]
        )
    if kind == "planting":
        trees = p.get("trees_per_m2")
        return _join(
            [
                f"≥ {_percent(p['min_green_ratio'], locale)}"
                if p.get("min_green_ratio") is not None
                else None,
                _t("trees", locale, value=number(float(trees) * 100, locale)) if trees is not None else None,
            ]
        )
    if kind == "fence":
        return _join(
            [
                f"≤ {_metres(p['max_height_m'], locale)}" if p.get("max_height_m") is not None else None,
                _list(p.get("materials"), "rule_material.", locale),
            ]
        )
    if kind == "max_area":
        return _join(
            [
                _t("sdpMax", locale, value=number(p["sdp_m2"], locale, 0))
                if p.get("sdp_m2") is not None
                else None,
                _t("footprintMax", locale, value=number(p["footprint_m2"], locale, 0))
                if p.get("footprint_m2") is not None
                else None,
            ]
        )
    summary = p.get("summary")
    return "" if summary is None else str(summary)


def rule_value(kind: str, status: str, reason: str | None, params: Mapping[str, Any], locale: Locale) -> str:
    """Wert einer wirksamen Regel; für andere Status der Grund (`unknown`) oder „nicht geregelt“."""
    if status == "not_regulated":
        return translate("rule_status.not_regulated", locale)
    if status == "unknown":
        return reason_text(reason, locale)
    return rule_values(kind, params, locale) or translate("rule_status.effective", locale)


def reason_text(reason: str | None, locale: Locale) -> str:
    """Warum ein Wert nicht ermittelt ist; ohne bekannten Grund „nicht ermittelt“."""
    key = f"rule_reason.{reason or 'missing'}"
    text = translate(key, locale)
    return translate("rule_status.unknown", locale) if text == key else text
