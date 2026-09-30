"""Zulässigkeit eines Typs für ein Grundstück und Vorschläge (Plan H2 3.5, 3.6; Spez. 5.4.6).

Ein Typ ist gesperrt, wenn es keine Teilfläche gibt, in der alle bindenden Typprüfungen bestehen und in der
für mindestens eine erlaubte Drehung eine zulässige Lage existiert. Dann stehen alle Gründe im Ergebnis. Nicht
bindende Prüfungen (unbekannte Regeln) bleiben als Hinweise.
"""

from dataclasses import dataclass, field

from app.configuration.domain.checks import FAIL, Check, type_checks
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.house import HouseType
from app.configuration.domain.rotations import (
    allowed_rotations,
    ridge_orientation_rule,
)
from app.configuration.domain.surface import BoundaryOptions, part_surface


@dataclass(frozen=True)
class TypeFit:
    house: HouseType
    allowed: bool
    reasons: list[Check]
    """Alle bindenden Verstöße; leer, wenn der Typ zulässig ist."""
    hints: list[Check]
    rotations: list[float]
    """Erlaubte Drehungen, für die es eine zulässige Lage gibt."""
    suggestions: list[str] = field(default_factory=list)


def evaluate_type(
    house: HouseType, ctx: SiteContext, boundary_options: BoundaryOptions | None = None
) -> TypeFit:
    options = boundary_options or {}
    per_part = [(part, type_checks(house, part, ctx)) for part in ctx.parts]
    if not per_part:
        return TypeFit(house, False, [Check(code="no_zone", kind="site", status=FAIL)], [], [])

    eligible = [pc for pc in per_part if not any(c.blocks for c in pc[1])]
    reference = (
        eligible[0]
        if eligible
        else min(per_part, key=lambda pc: (sum(c.blocks for c in pc[1]), -pc[0].area_m2))
    )
    reasons = [c for c in reference[1] if c.blocks]

    # Lage: auch für Teilflächen, in denen der Typ schon aus anderem Grund scheitert, damit „passt nicht“
    # neben den übrigen Gründen steht (Spez. 11.2)
    feasible: dict[str, list[float]] = {}
    ridge_fail: list[Check] = []
    for part, _ in per_part:
        permitted = allowed_rotations(house, part, ctx)
        if not permitted:
            ridge_fail.append(_ridge_reason(part))
        feasible[part.zone_code] = [
            r for r in permitted if not part_surface(house, part, r, ctx, options).is_empty
        ]
    usable = sorted({r for part, _ in eligible for r in feasible[part.zone_code]})
    anywhere = any(feasible.values())
    if not anywhere or (eligible and not usable):
        reasons.extend(ridge_fail or [Check(code="no_valid_position", kind="site", status=FAIL)])
    return TypeFit(house, not reasons, reasons, _hints(reference[1]), usable if not reasons else [])


def _ridge_reason(part: PartContext) -> Check:
    return Check(
        code="ridge_orientation",
        kind="roof",
        status=FAIL,
        zone_code=part.zone_code,
        params={"orientation": ridge_orientation_rule(part)},
    )


def _hints(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.status in ("hint", "unknown")]


def with_suggestions(fits: list[TypeFit]) -> list[TypeFit]:
    """Vorschläge für gesperrte Typen: erst `alternatives`, dann dieselbe Familie, jeweils zulässig und nach
    Nähe der Wohnfläche geordnet (Spez. 5.4.6)."""
    allowed = {f.house.slug: f for f in fits if f.allowed}
    result: list[TypeFit] = []
    for fit in fits:
        if fit.allowed:
            result.append(fit)
            continue
        house = fit.house
        chosen = [slug for slug in house.alternatives if slug in allowed]
        family = sorted(
            (
                f.house
                for f in allowed.values()
                if house.family and f.house.family == house.family and f.house.slug not in chosen
            ),
            key=lambda h: abs(h.living_area_m2 - house.living_area_m2),
        )
        chosen.extend(h.slug for h in family)
        result.append(TypeFit(house, fit.allowed, fit.reasons, fit.hints, fit.rotations, suggestions=chosen))
    return result


def eligible_parts(house: HouseType, ctx: SiteContext) -> list[PartContext]:
    """Teilflächen, in denen der Typ nicht schon aus anderem Grund als der Lage scheitert."""
    return [p for p in ctx.parts if not any(c.blocks for c in type_checks(house, p, ctx))]
