"""Art und Maße einer Option (Plan H3 3.2). Rein: keine Datenbank, kein FastAPI.

Die Art legt Geometrie und Einheit des Preises fest: `terrace` wird je m² berechnet, alles andere fest.
Parameter werden beim Anlegen geprüft und mit Standardwerten gefüllt, damit die Auswertung nie mit fehlenden
Werten rechnen muss.
"""

from typing import Any, Literal, get_args

from app.rules.domain.kinds import MATERIALS

OptionKind = Literal["plain", "terrace", "carport"]
OPTION_KINDS: tuple[str, ...] = get_args(OptionKind)

GEOMETRY_MODE: dict[str, str] = {"plain": "none", "terrace": "parametric", "carport": "parametric"}
"""Aus der Art abgeleitet; ein zweiter Wert, den das Büro pflegen müsste, entfällt."""

REGULATORY_KEYS = ("facade_material", "roof_material")

TERRACE_DEFAULTS: dict[str, float] = {"depth_m": 3.0, "height_above_terrain_m": 0.3, "sealing_factor": 1.0}
TERRACE_BOUNDS: dict[str, tuple[float, float]] = {
    "depth_m": (0.5, 6.0),
    "height_above_terrain_m": (0.0, 3.0),
    "sealing_factor": (0.0, 1.0),
}
CARPORT_DEFAULTS: dict[str, float] = {"depth_m": 5.0, "height_m": 2.7}
CARPORT_BOUNDS: dict[str, tuple[float, float]] = {
    "width_m": (2.0, 12.0),
    "depth_m": (2.0, 10.0),
    "height_m": (2.0, 4.0),
}


class OptionParamsInvalid(ValueError):
    """Maße oder Material einer Option sind ungültig; der Text nennt das Feld."""


def _number(name: str, raw: dict[str, Any], default: float | None, bounds: tuple[float, float]) -> float:
    value = raw.get(name, default)
    if value is None:
        raise OptionParamsInvalid(f"{name} fehlt")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OptionParamsInvalid(f"{name} muss eine Zahl sein")
    low, high = bounds
    if not (low <= float(value) <= high):
        raise OptionParamsInvalid(f"{name} muss zwischen {low:g} und {high:g} liegen")
    return float(value)


def normalize_params(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Maße der Art geprüft und mit Standardwerten gefüllt; unbekannte Felder sind ein Fehler."""
    if kind not in OPTION_KINDS:
        raise OptionParamsInvalid(f"Art „{kind}“ unbekannt")
    if kind == "plain":
        if raw:
            raise OptionParamsInvalid("eine Option ohne Geometrie hat keine Maße")
        return {}
    allowed = set(TERRACE_DEFAULTS) if kind == "terrace" else {"spaces", "width_m", "depth_m", "height_m"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise OptionParamsInvalid(f"unbekannte Felder: {', '.join(unknown)}")
    if kind == "terrace":
        return {n: _number(n, raw, TERRACE_DEFAULTS[n], TERRACE_BOUNDS[n]) for n in TERRACE_DEFAULTS}
    spaces = raw.get("spaces")
    if spaces not in (1, 2) or isinstance(spaces, bool):
        raise OptionParamsInvalid("spaces muss 1 oder 2 sein")
    return {
        "spaces": int(spaces),
        "width_m": _number("width_m", raw, 3.0 * int(spaces), CARPORT_BOUNDS["width_m"]),
        "depth_m": _number("depth_m", raw, CARPORT_DEFAULTS["depth_m"], CARPORT_BOUNDS["depth_m"]),
        "height_m": _number("height_m", raw, CARPORT_DEFAULTS["height_m"], CARPORT_BOUNDS["height_m"]),
    }


def normalize_regulatory(raw: dict[str, str]) -> dict[str, str]:
    """Materialklassen aus dem Vokabular der Regeln (Spez. 4.1); leere Angaben entfallen."""
    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        if key not in REGULATORY_KEYS:
            raise OptionParamsInvalid(f"unbekanntes Feld {key}")
        if value in (None, ""):
            continue
        if value not in MATERIALS:
            raise OptionParamsInvalid(f"{key}: „{value}“ ist keine Materialklasse")
        cleaned[key] = value
    return cleaned
