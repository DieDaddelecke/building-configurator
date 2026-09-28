"""Formularbeschreibung der Regelarten (AN4, docs/PLAN_AN4_KORREKTUR.md 3.1).

Abgeleitet aus den Pydantic-Modellen in `kinds.py`: dieselbe Quelle wie Prüfung (`validate_params`) und
Modellausgabe (`PARAM_TYPES`). Die Oberfläche erzeugt daraus das Korrekturformular statt eines JSON-Felds
(RW15). Zusammenhänge zwischen Parametern („`min_m` oder `height_factor`“) prüft weiter nur der Server.
"""

import types
from dataclasses import dataclass
from typing import Any, Literal, Union, get_args, get_origin

from app.rules.domain.kinds import (
    BOUNDS,
    BUILDING_SPECIFIC_KINDS,
    COLOR_FAMILIES,
    MANDATORY_KINDS,
    MATERIALS,
    PARAM_MODELS,
)

FieldType = Literal["number", "flag", "choice", "items", "text"]
Unit = Literal["m", "m2", "deg", "share", "factor", "per_area", "count"]

UNITS: dict[str, Unit] = {
    "min_m": "m",
    "max_m": "m",
    "on_boundary_max_height_m": "m",
    "terrace_counts_above_m": "m",
    "ridge_m": "m",
    "eave_m": "m",
    "parapet_m": "m",
    "max_height_m": "m",
    "max_footprint_m2": "m2",
    "sdp_m2": "m2",
    "footprint_m2": "m2",
    "pitch_min_deg": "deg",
    "pitch_max_deg": "deg",
    "ratio": "share",
    "full_soil_ratio": "share",
    "min_green_ratio": "share",
    "height_factor": "factor",
    "spaces_per_m2_sdp": "per_area",
    "trees_per_m2": "per_area",
    "spaces_per_dwelling": "count",
}
"""Einheit je Zahl, fest statt aus `PERCENT_PARAMS` abgeleitet: `height_factor` darf im Text als Prozent
stehen, ist aber ein Faktor (H/2 = 0,5); Dichten gibt man als Kehrwert ein (1 je 50 m², 7.1 Nr. 6, 7)."""

VOCABULARIES: dict[str, tuple[str, ...]] = {
    "materials_allowed": MATERIALS,
    "materials_forbidden": MATERIALS,
    "materials": MATERIALS,
    "color_families_allowed": COLOR_FAMILIES,
}
"""Listen aus freiem Text (`tuple[str, ...]`), die das Modell gegen ein Vokabular prüft."""


@dataclass(frozen=True)
class ParamField:
    name: str
    type: FieldType
    required: bool
    default: Any
    options: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    unit: Unit | None = None


@dataclass(frozen=True)
class KindForm:
    kind: str
    building_specific: bool
    mandatory: bool
    params: tuple[ParamField, ...]


def _strip_none(annotation: Any) -> Any:
    if get_origin(annotation) in (Union, types.UnionType):
        rest = [arg for arg in get_args(annotation) if arg is not type(None)]
        return rest[0] if len(rest) == 1 else annotation
    return annotation


def _field(name: str, annotation: Any, required: bool, default: Any) -> ParamField:
    inner = _strip_none(annotation)
    bounds = BOUNDS.get(name)
    extra: dict[str, Any] = {
        "min": bounds[0] if bounds else None,
        "max": bounds[1] if bounds else None,
        "unit": UNITS.get(name),
    }
    if default == ():
        default = []
    if get_origin(inner) is Literal:
        return ParamField(name, "choice", required, default, tuple(str(v) for v in get_args(inner)))
    if get_origin(inner) is tuple:
        item = get_args(inner)[0]
        options = tuple(get_args(item)) if get_origin(item) is Literal else VOCABULARIES.get(name, ())
        return ParamField(name, "items", required, default, tuple(str(v) for v in options))
    if inner is bool:
        return ParamField(name, "flag", required, default)
    if inner in (float, int):
        return ParamField(name, "number", required, default, **extra)
    return ParamField(name, "text", required, default)


def kind_forms() -> list[KindForm]:
    """Alle Regelarten in der Reihenfolge von `PARAM_MODELS` mit ihren Parametern in Feldreihenfolge."""
    result: list[KindForm] = []
    for kind, model in PARAM_MODELS.items():
        params = tuple(
            _field(
                name,
                info.annotation,
                info.is_required(),
                None if info.is_required() else info.default,
            )
            for name, info in model.model_fields.items()
        )
        result.append(
            KindForm(
                kind=kind,
                building_specific=kind in BUILDING_SPECIFIC_KINDS,
                mandatory=kind in MANDATORY_KINDS,
                params=params,
            )
        )
    return result
