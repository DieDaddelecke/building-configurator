"""Grundfläche, versiegelte und unversiegelte Fläche (Plan H3 3.5; Spez. 5.9.2, 5.9.3).

```
versiegelt = Haus + Carport + Zufahrt + Terrasse × Versiegelungsfaktor + Wege
unversiegelt = Fläche − versiegelt
```

Überlappungen (Zufahrt am Carport, Terrasse am Haus) zählen einmal. Die Grundfläche (Emprise) rechnet Haus,
Carport und eine Terrasse über der Grenzhöhe; die Regeln gelten je Zonen-Teilfläche (Spez. 5.9.2), deshalb
wird je Teilfläche verschnitten.
"""

from dataclasses import dataclass

import shapely
from shapely.geometry.base import BaseGeometry

from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.geometry import union
from app.envelope.domain.setbacks import rule_for


@dataclass(frozen=True)
class Buildings:
    """Was auf dem Grundstück steht, in lokalen Metern."""

    house_facade: BaseGeometry
    house_projection: BaseGeometry
    carport: BaseGeometry | None = None
    terrace: BaseGeometry | None = None
    terrace_height_m: float = 0.0
    terrace_sealing_factor: float = 1.0
    driveways: tuple[BaseGeometry, ...] = ()


@dataclass(frozen=True)
class PartAreas:
    zone_code: str
    area_m2: float
    emprise_m2: float
    sealed_m2: float
    unsealed_m2: float


@dataclass(frozen=True)
class Areas:
    site_m2: float
    house_m2: float
    carport_m2: float
    terrace_m2: float
    driveway_m2: float
    paths_m2: float
    emprise_m2: float
    sealed_m2: float
    unsealed_m2: float
    parts: tuple[PartAreas, ...]


def _area(geometry: BaseGeometry | None) -> float:
    return float(geometry.area) if geometry is not None and not geometry.is_empty else 0.0


def _round(value: float) -> float:
    return round(value, tol.AREA_DECIMALS)


def _counts_overhangs(part: PartContext | None) -> bool:
    rule = rule_for(part.rules, "max_footprint_ratio") if part else None
    return bool(rule and rule.status == "effective" and rule.params.get("counts_overhangs") == "yes")


def terrace_counts_above_m(part: PartContext | None) -> float:
    """Höhe, ab der eine Terrasse zur Grundfläche zählt: die Regel oder der Standard (Spez. 5.5.5)."""
    rule = rule_for(part.rules, "max_footprint_ratio") if part else None
    if rule and rule.status == "effective":
        value = rule.params.get("terrace_counts_above_m")
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    return tol.TERRACE_COUNTS_ABOVE_M


def _sealed(buildings: Buildings, within: BaseGeometry) -> float:
    """Versiegelte Fläche innerhalb von `within`, ohne Wege."""
    solid = [buildings.house_facade, buildings.carport, *buildings.driveways]
    base = union([g for g in solid if g is not None]).intersection(within)
    total = _area(base)
    if buildings.terrace is not None and not buildings.terrace.is_empty:
        extra = buildings.terrace.intersection(within).difference(base)
        total += _area(extra) * buildings.terrace_sealing_factor
    return total


def _emprise(buildings: Buildings, within: BaseGeometry, part: PartContext | None) -> float:
    """Grundfläche in `within` nach den Regeln der Teilfläche `part` (Überstände, Terrassenhöhe)."""
    house = buildings.house_projection if _counts_overhangs(part) else buildings.house_facade
    pieces: list[BaseGeometry | None] = [house, buildings.carport]
    if buildings.terrace_height_m > terrace_counts_above_m(part):
        pieces.append(buildings.terrace)
    return _area(union([p for p in pieces if p is not None]).intersection(within))


def compute_areas(ctx: SiteContext, buildings: Buildings, house_part: PartContext | None) -> Areas:
    """Flächen des Grundstücks und je Teilfläche. Die Wegepauschale liegt in der Teilfläche des Hauses."""
    site = ctx.polygon
    paths = tol.PATHS_LUMP_M2
    sealed_site = _sealed(buildings, site) + paths
    parts: list[PartAreas] = []
    for part in ctx.parts:
        within = shapely.make_valid(part.polygon)
        sealed = _sealed(buildings, within) + (paths if part is house_part else 0.0)
        parts.append(
            PartAreas(
                zone_code=part.zone_code,
                area_m2=_round(part.area_m2),
                emprise_m2=_round(_emprise(buildings, within, part)),
                sealed_m2=_round(sealed),
                unsealed_m2=_round(max(part.area_m2 - sealed, 0.0)),
            )
        )
    site_area = float(site.area)
    return Areas(
        site_m2=_round(site_area),
        house_m2=_round(_area(buildings.house_facade)),
        carport_m2=_round(_area(buildings.carport)),
        terrace_m2=_round(_area(buildings.terrace)),
        driveway_m2=_round(_area(union(list(buildings.driveways))) if buildings.driveways else 0.0),
        paths_m2=_round(paths),
        emprise_m2=_round(_emprise(buildings, site, house_part)),
        sealed_m2=_round(sealed_site),
        unsealed_m2=_round(max(site_area - sealed_site, 0.0)),
        parts=tuple(parts),
    )


def outside_site(ctx: SiteContext, geometry: BaseGeometry | None) -> bool:
    """Liegt `geometry` (zum Teil) außerhalb des Grundstücks? Toleranz wie bei der Lage."""
    if geometry is None or geometry.is_empty:
        return False
    return not ctx.polygon.buffer(tol.DISTANCE_TOLERANCE_M).covers(geometry)
