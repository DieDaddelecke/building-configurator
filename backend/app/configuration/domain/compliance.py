"""Prüfungen der Auswahl: Nebenbauten, Flächen, Stellplätze, Material (Plan H3 3.6; Spez. 5.9.2).

Wie in H2 trägt jede Prüfung einen stabilen Code, Messwert, Grenze und die Herkunft der Regel. Bindend ist sie
nur bei wirksamer Regel oder geometrischer Gewissheit (D12); sonst ist sie ein Hinweis mit Grund. Nicht
prüfbare Regeln stehen als `unknown`, nie als bestanden (Spez. 5.9.1).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from app.configuration.domain.areas import Areas, outside_site, terrace_counts_above_m
from app.configuration.domain.checks import FAIL, HINT, PASS, UNKNOWN, Check
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.options import Resolved
from app.configuration.domain.outbuildings import CarportPlacement, CarportSpec, TerraceSpec
from app.envelope.domain.inputs import RuleInput
from app.envelope.domain.setbacks import rule_for

EPS = 1e-6


@dataclass(frozen=True)
class MaterialSubject:
    """Träger von Materialklassen für die Prüfung von Fassade und Dach: Linie oder Option (H3) oder das Haus
    aus der Hausbeschreibung (`house`, HM4)."""

    kind: str
    slug: str
    regulatory: Mapping[str, str]
    """`facade_material`, `roof_material` (Vokabular `rules.domain.kinds.MATERIALS`)."""


def material_subjects(resolved: Resolved) -> list[MaterialSubject]:
    """Linie und wirksame Optionen der Auswahl (H3)."""
    subjects: list[MaterialSubject] = []
    if resolved.package is not None:
        subjects.append(MaterialSubject("package", resolved.package.slug, resolved.package.regulatory))
    subjects.extend(MaterialSubject("option", o.slug, o.regulatory) for o in resolved.effective)
    return subjects


@dataclass(frozen=True)
class SiteFacts:
    """Was die Geometrie ergeben hat."""

    terrace_spec: TerraceSpec | None = None
    terrace: BaseGeometry | None = None
    carport_spec: CarportSpec | None = None
    carport: CarportPlacement | None = None
    has_garage_door: bool = False
    placed: bool = True
    """Ob das Haus eine Lage hat; ohne sie gibt es keine Geometrie zu prüfen."""


def _usable(rule: RuleInput | None) -> bool:
    return rule is not None and rule.status == "effective"


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def geometry_checks(ctx: SiteContext, facts: SiteFacts) -> list[Check]:
    """Terrasse und Carport gehen nicht auf: geometrisch sicher, deshalb bindend (Plan H3 3.6)."""
    checks: list[Check] = []
    spec = facts.terrace_spec
    if spec is not None:
        subject = {"subject": spec.slug}
        if spec.width_m is None:
            checks.append(Check(code="no_garden_facade", kind="terrace", status=FAIL, params=subject))
        elif facts.placed and outside_site(ctx, facts.terrace):
            checks.append(Check(code="terrace_outside_site", kind="terrace", status=FAIL, params=subject))
    carport = facts.carport_spec
    if carport is not None and facts.placed:
        subject = {"subject": carport.slug}
        if facts.carport is None:
            checks.append(Check(code="no_valid_position", kind="carport", status=FAIL, params=subject))
        elif facts.carport.setback == "assumed":
            checks.append(
                Check(
                    code="carport_setback_assumed", kind="annex", status=HINT, binding=False, params=subject
                )
            )
        elif facts.carport.setback == "relaxed":
            checks.append(
                Check(
                    code="carport_setback_relaxed", kind="annex", status=HINT, binding=False, params=subject
                )
            )
    return checks


def rule_checks(
    ctx: SiteContext,
    house_part: PartContext | None,
    areas: Areas | None,
    facts: SiteFacts,
    materials: Sequence[MaterialSubject],
) -> list[Check]:
    """Grundfläche der Summe, unversiegelter Anteil, Nebengebäude, Stellplätze und Material."""
    checks = [*_parking_checks(ctx, house_part, facts)]
    if ctx.is_free or house_part is None:
        return checks
    if areas is not None:
        checks.extend(_area_checks(ctx, areas, facts))
        checks.extend(_annex_checks(ctx, house_part, facts))
    checks.extend(_material_checks(house_part, materials))
    return checks


def _area_checks(ctx: SiteContext, areas: Areas, facts: SiteFacts) -> list[Check]:
    checks: list[Check] = []
    extra_footprint = facts.carport is not None or (
        facts.terrace is not None and areas.terrace_m2 > 0 and _terrace_counts(ctx, facts)
    )
    for part, measured in zip(ctx.parts, areas.parts, strict=True):
        if measured.sealed_m2 <= 0:
            continue
        ratio_rule = rule_for(part.rules, "max_footprint_ratio")
        ratio = _number(ratio_rule.params.get("ratio")) if _usable(ratio_rule) and ratio_rule else None
        if extra_footprint and ratio is not None and ratio_rule is not None:
            limit = ratio * part.area_m2
            checks.append(
                Check(
                    code="footprint_total",
                    kind="max_footprint_ratio",
                    status=PASS if measured.emprise_m2 <= limit + EPS else FAIL,
                    measured=measured.emprise_m2,
                    limit=round(limit, 2),
                    unit="m2",
                    zone_code=part.zone_code,
                    citation=ratio_rule.citation,
                    params={"ratio": ratio},
                )
            )
        rule = rule_for(part.rules, "unsealed_min")
        if rule is not None and rule.status == "not_regulated":
            continue
        minimum = None
        if _usable(rule) and rule is not None:
            minimum = _number(rule.params.get("ratio"))
            if minimum is None:
                minimum = _number(rule.params.get("full_soil_ratio"))
        if rule is None or minimum is None or not _usable(rule):
            checks.append(
                Check(
                    code="unsealed_min_unknown",
                    kind="unsealed_min",
                    status=UNKNOWN,
                    binding=False,
                    reason=(rule.reason if rule else None) or "missing",
                    zone_code=part.zone_code,
                    measured=measured.unsealed_m2,
                    unit="m2",
                )
            )
            continue
        limit = minimum * part.area_m2
        checks.append(
            Check(
                code="unsealed_min",
                kind="unsealed_min",
                status=PASS if measured.unsealed_m2 >= limit - EPS else FAIL,
                measured=measured.unsealed_m2,
                limit=round(limit, 2),
                unit="m2",
                zone_code=part.zone_code,
                citation=rule.citation,
                params={"ratio": minimum},
            )
        )
    return checks


def _terrace_counts(ctx: SiteContext, facts: SiteFacts) -> bool:
    spec = facts.terrace_spec
    return spec is not None and any(
        spec.height_above_terrain_m > terrace_counts_above_m(p) for p in ctx.parts
    )


def _annex_checks(ctx: SiteContext, house_part: PartContext, facts: SiteFacts) -> list[Check]:
    spec = facts.carport_spec
    if spec is None or not facts.placed:
        return []
    part = house_part
    if facts.carport is not None:
        centre = facts.carport.polygon.centroid
        part = next((p for p in ctx.parts if p.polygon.buffer(0.01).contains(centre)), house_part)
    rule = rule_for(part.rules, "annex", "annex")
    if rule is None or rule.status == "not_regulated":
        return []
    subject = {"subject": spec.slug}
    if not _usable(rule):
        return [
            Check(
                code="annex_unknown",
                kind="annex",
                status=UNKNOWN,
                binding=False,
                reason=rule.reason or "missing",
                zone_code=part.zone_code,
                params=subject,
            )
        ]
    checks: list[Check] = []
    limit_area = _number(rule.params.get("max_footprint_m2"))
    if limit_area is not None:
        checks.append(
            Check(
                code="annex_footprint",
                kind="annex",
                status=PASS if spec.area_m2 <= limit_area + EPS else FAIL,
                measured=spec.area_m2,
                limit=limit_area,
                unit="m2",
                zone_code=part.zone_code,
                citation=rule.citation,
                params=subject,
            )
        )
    limit_height = _number(rule.params.get("max_height_m"))
    if limit_height is not None:
        checks.append(
            Check(
                code="annex_height",
                kind="annex",
                status=PASS if spec.height_m <= limit_height + EPS else FAIL,
                measured=spec.height_m,
                limit=limit_height,
                unit="m",
                zone_code=part.zone_code,
                citation=rule.citation,
                params=subject,
            )
        )
    return checks


def _parking_checks(ctx: SiteContext, house_part: PartContext | None, facts: SiteFacts) -> list[Check]:
    offered = (facts.carport_spec.spaces if facts.carport_spec else 0) + (1 if facts.has_garage_door else 0)
    if offered == 0:
        return [Check(code="parking_not_shown", kind="parking", status=HINT, binding=False)]
    rule = rule_for(house_part.rules, "parking") if house_part and not ctx.is_free else None
    if not _usable(rule) or rule is None:
        return []
    required = _number(rule.params.get("spaces_per_dwelling"))
    if required is None:
        return [
            Check(code="parking_not_checked", kind="parking", status=HINT, binding=False, reason="per_area")
        ]
    return [
        Check(
            code="parking",
            kind="parking",
            status=PASS if offered >= required - EPS else HINT,
            binding=False,
            measured=float(offered),
            limit=required,
            citation=rule.citation,
        )
    ]


def _material_checks(part: PartContext, subjects: Sequence[MaterialSubject]) -> list[Check]:
    facade = rule_for(part.rules, "facade")
    roof = rule_for(part.rules, "roof")
    checks: list[Check] = []
    for subject in subjects:
        kind, slug, regulatory = subject.kind, subject.slug, subject.regulatory
        for key, rule, code in (
            ("facade_material", facade, "facade_material"),
            ("roof_material", roof, "roof_material"),
        ):
            if not _usable(rule) or rule is None:
                continue
            allowed = [str(m) for m in rule.params.get("materials_allowed", [])]
            forbidden = (
                [str(m) for m in rule.params.get("materials_forbidden", [])]
                if code == "facade_material"
                else []
            )
            if not allowed and not forbidden:
                continue
            material = regulatory.get(key)
            params = {"subject": slug, "subject_kind": kind}
            if material is None:
                # Eine Option ohne Angabe ändert das Material nicht; offen ist es nur bei Linie oder Haus
                if kind != "option":
                    checks.append(
                        Check(
                            code="material_unknown",
                            kind="facade" if code == "facade_material" else "roof",
                            status=UNKNOWN,
                            binding=False,
                            reason="missing",
                            zone_code=part.zone_code,
                            params={**params, "field": key},
                        )
                    )
                continue
            bad = material in forbidden or (bool(allowed) and material not in allowed)
            checks.append(
                Check(
                    code=code,
                    kind="facade" if code == "facade_material" else "roof",
                    status=FAIL if bad else PASS,
                    measured=material,
                    limit=",".join(forbidden if material in forbidden else allowed),
                    zone_code=part.zone_code,
                    citation=rule.citation,
                    params={**params, "rule": "forbidden" if material in forbidden else "allowed"},
                )
            )
    return checks
