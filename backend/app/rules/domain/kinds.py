"""Regelarten mit Parametern, Pflichtarten und Plausibilitätsgrenzen (Spez. 5.2.4, Plan 3.4).

Längen in Metern, Höhen in Metern über dem Bezug der Regel, Winkel in Grad, Anteile als Zahl 0–1.
Jede Regel gilt für eine Art von Baukörper (`building_kind`); `any` heißt ohne Einschränkung (Spez. 5.2.4).
"""

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

RuleKind = Literal[
    "setback_street",
    "setback_side",
    "setback_rear",
    "setback_between_buildings",
    "max_footprint_ratio",
    "max_height",
    "roof",
    "facade",
    "unsealed_min",
    "parking",
    "annex",
    "planting",
    "fence",
    "text_only",
]
RULE_KINDS: tuple[str, ...] = get_args(RuleKind)
BuildingKind = Literal["main", "annex", "pool", "any"]
BUILDING_KINDS: tuple[str, ...] = get_args(BuildingKind)

MANDATORY_KINDS: tuple[str, ...] = (
    "setback_street",
    "setback_side",
    "setback_rear",
    "max_footprint_ratio",
    "max_height",
    "roof",
    "facade",
    "unsealed_min",
)
"""Pflichtarten für das Hauptgebäude (Spez. 5.2.4 Spalte „Pflicht“). Fehlt eine, wird sie `unknown`."""

RoofForm = Literal["gable", "hip", "mono_pitch", "flat", "mansard", "other"]
ROOF_FORMS: tuple[str, ...] = get_args(RoofForm)
MATERIALS: tuple[str, ...] = (
    "render",
    "wood",
    "brick",
    "stone",
    "concrete",
    "metal",
    "glass",
    "slate",
    "clay_tile",
    "zinc",
    "composite",
    "vegetation",
    "other",
)
"""Kontrolliertes Vokabular für Materialklassen (Spez. 4.1), gleich für Regeln und Ausführungen."""
COLOR_FAMILIES: tuple[str, ...] = ("light", "neutral", "natural", "dark", "bright", "other")

ParamType = Literal["number", "flag", "text", "items"]
PARAM_TYPES: dict[str, ParamType] = {
    "min_m": "number",
    "max_m": "number",
    "mode": "text",
    "measured_from": "text",
    "height_factor": "number",
    "height_basis": "text",
    "allow_on_boundary": "flag",
    "on_boundary_max_height_m": "number",
    "ratio": "number",
    "counts_overhangs": "text",
    "terrace_counts_above_m": "number",
    "ridge_m": "number",
    "eave_m": "number",
    "parapet_m": "number",
    "storeys": "text",
    "reference": "text",
    "measured_at": "text",
    "includes_roof_installations": "flag",
    "allowed_forms": "items",
    "pitch_min_deg": "number",
    "pitch_max_deg": "number",
    "flat_roof": "text",
    "ridge_orientation": "text",
    "materials_allowed": "items",
    "materials_forbidden": "items",
    "color_families_allowed": "items",
    "full_soil_ratio": "number",
    "counting": "text",
    "spaces_per_dwelling": "number",
    "spaces_per_m2_sdp": "number",
    "min_dimensions": "text",
    "max_footprint_m2": "number",
    "max_height_m": "number",
    "trees_per_m2": "number",
    "min_green_ratio": "number",
    "materials": "items",
    "summary": "text",
}
"""Alle Parameternamen mit Typ. Das Sprachmodell liefert Parameter als Liste aus Name und Wert."""

BOUNDS: dict[str, tuple[float, float]] = {
    "min_m": (0.0, 50.0),
    "max_m": (0.0, 50.0),
    "height_factor": (0.0, 2.0),
    "on_boundary_max_height_m": (0.0, 15.0),
    "ratio": (0.0, 1.0),
    "terrace_counts_above_m": (0.0, 3.0),
    "ridge_m": (2.0, 30.0),
    "eave_m": (2.0, 30.0),
    "parapet_m": (2.0, 30.0),
    "pitch_min_deg": (0.0, 75.0),
    "pitch_max_deg": (0.0, 75.0),
    "full_soil_ratio": (0.0, 1.0),
    "spaces_per_dwelling": (0.0, 6.0),
    "spaces_per_m2_sdp": (0.0, 0.2),
    "max_footprint_m2": (0.0, 1000.0),
    "max_height_m": (0.0, 15.0),
    "trees_per_m2": (0.0, 0.1),
    "min_green_ratio": (0.0, 1.0),
}
"""Plausibilitätsgrenzen (Plan 3.4). Werte außerhalb sind eher Lesefehler als echte Festsetzungen."""

PERCENT_PARAMS = frozenset({"ratio", "full_soil_ratio", "min_green_ratio", "height_factor"})
"""Anteile: Im Text darf der Wert auch in Prozent stehen (0,4 ↔ 40 %)."""
RECIPROCAL_PARAMS = frozenset({"height_factor", "spaces_per_m2_sdp", "trees_per_m2"})
"""Faktoren und Dichten: Im Text darf der Kehrwert stehen (H/2, 1 place pour 50 m², 1 arbre pour 100 m²).
Für Längen gilt das nicht, sonst belegte „H/2“ einen Mindestabstand von 0,5 m."""
BUILDING_SPECIFIC_KINDS = frozenset(
    {"setback_street", "setback_side", "setback_rear", "max_height", "roof", "facade"}
)
"""Regelarten, die je Baukörper verschieden sein können. Die übrigen gelten für das Grundstück als Ganzes."""


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SetbackStreet(_Params):
    min_m: float | None = None
    max_m: float | None = None
    mode: Literal["min", "fixed", "range", "alignment"] = "min"
    measured_from: Literal["facade", "roof_edge", "any_projection"] = "facade"

    @model_validator(mode="before")
    @classmethod
    def _band_is_range(cls, data: Any) -> Any:
        """Mindestabstand mit Obergrenze ist ein Bauband (`range`); sonst ginge die Obergrenze verloren."""
        if isinstance(data, dict) and data.get("mode", "min") == "min" and data.get("max_m") is not None:
            return {**data, "mode": "range"}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> "SetbackStreet":
        if self.mode in ("min", "fixed") and self.min_m is None:
            raise ValueError("min_m_required")
        if self.mode in ("fixed", "alignment") and self.max_m is not None:
            raise ValueError("max_m_requires_range")
        if self.mode == "range" and (self.min_m is None or self.max_m is None or self.min_m > self.max_m):
            raise ValueError("range_invalid")
        return self


class SetbackBoundary(_Params):
    """Seitliche oder hintere Grenze: `max(min_m, height_factor × H)`; Bauen auf der Grenze optional."""

    min_m: float | None = None
    height_factor: float | None = None
    height_basis: Literal["eave", "ridge", "facade_point"] | None = None
    allow_on_boundary: bool = False
    on_boundary_max_height_m: float | None = None
    measured_from: Literal["facade", "roof_edge", "any_projection"] = "facade"

    @model_validator(mode="after")
    def _consistent(self) -> "SetbackBoundary":
        if self.min_m is None and self.height_factor is None:
            raise ValueError("min_m_or_height_factor_required")
        if self.height_factor is not None and self.height_basis is None:
            raise ValueError("height_basis_required")
        return self


class SetbackBetween(_Params):
    min_m: float | None = None
    height_factor: float | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "SetbackBetween":
        if self.min_m is None and self.height_factor is None:
            raise ValueError("min_m_or_height_factor_required")
        return self


class MaxFootprintRatio(_Params):
    ratio: float
    counts_overhangs: Literal["yes", "no", "per_code"] | None = None
    terrace_counts_above_m: float | None = None


class MaxHeight(_Params):
    ridge_m: float | None = None
    eave_m: float | None = None
    parapet_m: float | None = None
    storeys: str | None = None
    reference: Literal["natural_terrain", "street_level"] = "natural_terrain"
    measured_at: Literal["highest_point", "mean"] = "highest_point"
    includes_roof_installations: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> "MaxHeight":
        if self.ridge_m is None and self.eave_m is None and self.parapet_m is None and self.storeys is None:
            raise ValueError("height_required")
        if self.storeys is not None and not _storeys_valid(self.storeys):
            raise ValueError("storeys_invalid")
        if self.eave_m is not None and self.ridge_m is not None and self.eave_m > self.ridge_m:
            raise ValueError("eave_above_ridge")
        return self


class Roof(_Params):
    allowed_forms: tuple[RoofForm, ...] = ()
    pitch_min_deg: float | None = None
    pitch_max_deg: float | None = None
    flat_roof: Literal["allowed", "annex_only", "green_only", "forbidden"] | None = None
    ridge_orientation: Literal["any", "parallel_to_street", "perpendicular_to_street"] = "any"
    materials_allowed: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "Roof":
        has_form = self.allowed_forms or self.pitch_min_deg is not None or self.pitch_max_deg is not None
        has_other = self.flat_roof is not None or self.ridge_orientation != "any" or self.materials_allowed
        if not (has_form or has_other):
            raise ValueError("roof_empty")
        if (
            self.pitch_min_deg is not None
            and self.pitch_max_deg is not None
            and self.pitch_min_deg > self.pitch_max_deg
        ):
            raise ValueError("pitch_range_invalid")
        _check_vocabulary(self.materials_allowed, MATERIALS)
        return self


class Facade(_Params):
    materials_allowed: tuple[str, ...] = ()
    materials_forbidden: tuple[str, ...] = ()
    color_families_allowed: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "Facade":
        if not (self.materials_allowed or self.materials_forbidden or self.color_families_allowed):
            raise ValueError("facade_empty")
        _check_vocabulary(self.materials_allowed + self.materials_forbidden, MATERIALS)
        _check_vocabulary(self.color_families_allowed, COLOR_FAMILIES)
        return self


class UnsealedMin(_Params):
    ratio: float | None = None
    full_soil_ratio: float | None = None
    counting: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "UnsealedMin":
        if self.ratio is None and self.full_soil_ratio is None:
            raise ValueError("ratio_required")
        return self


class Parking(_Params):
    spaces_per_dwelling: float | None = None
    spaces_per_m2_sdp: float | None = None
    min_dimensions: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Parking":
        if self.spaces_per_dwelling is None and self.spaces_per_m2_sdp is None:
            raise ValueError("parking_empty")
        return self


class Annex(_Params):
    max_footprint_m2: float | None = None
    max_height_m: float | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Annex":
        if self.max_footprint_m2 is None and self.max_height_m is None:
            raise ValueError("annex_empty")
        return self


class Planting(_Params):
    trees_per_m2: float | None = None
    min_green_ratio: float | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Planting":
        if self.trees_per_m2 is None and self.min_green_ratio is None:
            raise ValueError("planting_empty")
        return self


class Fence(_Params):
    max_height_m: float | None = None
    materials: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "Fence":
        if self.max_height_m is None and not self.materials:
            raise ValueError("fence_empty")
        _check_vocabulary(self.materials, MATERIALS)
        return self


class TextOnly(_Params):
    summary: str


PARAM_MODELS: dict[str, type[_Params]] = {
    "setback_street": SetbackStreet,
    "setback_side": SetbackBoundary,
    "setback_rear": SetbackBoundary,
    "setback_between_buildings": SetbackBetween,
    "max_footprint_ratio": MaxFootprintRatio,
    "max_height": MaxHeight,
    "roof": Roof,
    "facade": Facade,
    "unsealed_min": UnsealedMin,
    "parking": Parking,
    "annex": Annex,
    "planting": Planting,
    "fence": Fence,
    "text_only": TextOnly,
}


def _storeys_valid(value: str) -> bool:
    """`R`, `R+1`, `R+1+C`, `R+2+A` (Erdgeschoss, Obergeschosse, Dach- oder Attikageschoss)."""
    parts = value.replace(" ", "").upper().split("+")
    if not parts or parts[0] != "R":
        return False
    rest = parts[1:]
    if rest and rest[-1] in ("C", "A", "CA", "COMBLES"):
        rest = rest[:-1]
    return len(rest) <= 1 and all(p.isdigit() and 0 < int(p) <= 5 for p in rest)


def _check_vocabulary(values: tuple[str, ...], vocabulary: tuple[str, ...]) -> None:
    unknown = [v for v in values if v not in vocabulary]
    if unknown:
        raise ValueError("vocabulary:" + ",".join(sorted(unknown)))


class ParamProblem(ValueError):
    """Parameter ungültig (`invalid_params`) oder außerhalb der Plausibilitätsgrenzen (`implausible`)."""

    def __init__(self, reason: Literal["invalid_params", "implausible"], detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def validate_params(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Parameter einer Regelart prüfen und normalisiert zurückgeben (Standardwerte ausgefüllt, ohne leere
    Angaben, Listen sortiert).

    Erst Plausibilitätsgrenzen, dann Typen und Zusammenhänge. Wirft `ParamProblem`.
    """
    model = PARAM_MODELS.get(kind)
    if model is None:
        raise ParamProblem("invalid_params", f"unknown_kind:{kind}")
    for name, value in raw.items():
        bounds = BOUNDS.get(name)
        if bounds is not None and isinstance(value, int | float) and not isinstance(value, bool):
            low, high = bounds
            if not (low <= float(value) <= high):
                raise ParamProblem("implausible", f"{name}={value}")
    try:
        parsed = model.model_validate(raw)
    except ValidationError as exc:
        messages = sorted({str(e.get("msg", "")).removeprefix("Value error, ") for e in exc.errors()})
        raise ParamProblem("invalid_params", "; ".join(messages)) from None
    dumped = parsed.model_dump(exclude_none=True)
    return {k: sorted(v) if isinstance(v, tuple | list) else v for k, v in dumped.items() if v != ()}


def params_equal(a: dict[str, Any], b: dict[str, Any], tolerance: float = 0.01) -> bool:
    """Gleichheit zweier normalisierter Parameter; Zahlen mit Toleranz (Meter, Anteile, Grad)."""
    if a.keys() != b.keys():
        return False
    for key, left in a.items():
        right = b[key]
        if isinstance(left, float | int) and isinstance(right, float | int) and not isinstance(left, bool):
            if abs(float(left) - float(right)) > tolerance:
                return False
        elif left != right:
            return False
    return True
