"""Prüfergebnis und Prüfungen des Typs (Plan H2 3.1, 3.5; Spez. 5.9.1, 5.9.2).

Eine Prüfung trägt einen stabilen Code (`message_key` der Oberfläche), Messwert, Grenze, Herkunft der Regel
und ob sie bindend ist. `unknown` gilt nie als bestanden (Spez. 5.9.1). Bindend ist eine Prüfung nur,
wenn die Regel wirksam ist (D12); Hinweise erscheinen mit Grund, sperren aber nichts.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.house import HouseType
from app.envelope.domain.inputs import Citation, RuleInput
from app.envelope.domain.setbacks import rule_for

PASS, FAIL, HINT, UNKNOWN, NOT_APPLICABLE = "pass", "fail", "hint", "unknown", "not_applicable"


@dataclass(frozen=True)
class Check:
    code: str
    kind: str
    """Regelart (`roof`, `max_height`, `setback_street` …) oder `site`."""
    status: str
    binding: bool = True
    measured: float | str | None = None
    limit: float | str | None = None
    unit: str | None = None
    edge_seq: int | None = None
    zone_code: str | None = None
    reason: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    citation: Citation | None = None

    @property
    def blocks(self) -> bool:
        return self.status == FAIL and self.binding


_STOREYS = re.compile(r"^R(?:\+(\d))?(?:\+(C|A|CA|COMBLES))?$", re.IGNORECASE)
_FORM_ALIASES = {"complex": "other"}


def type_checks(house: HouseType, part: PartContext, ctx: SiteContext) -> list[Check]:
    """Prüfungen, die nur vom Typ und der Teilfläche abhängen. Im freien Modus gibt es keine Regeln."""
    if ctx.is_free:
        return []
    return [
        *_roof_checks(house, part),
        *_height_checks(house, part, ctx),
        *_footprint_checks(house, part),
    ]


def _unknown(kind: str, rule: RuleInput | None, part: PartContext) -> Check:
    return Check(
        code=f"{kind}_unknown",
        kind=kind,
        status=UNKNOWN,
        binding=False,
        reason=(rule.reason if rule else None) or "missing",
        zone_code=part.zone_code,
    )


def _usable(rule: RuleInput | None) -> bool:
    return rule is not None and rule.status == "effective"


def _roof_checks(house: HouseType, part: PartContext) -> list[Check]:
    rule = rule_for(part.rules, "roof")
    if rule is not None and rule.status == "not_regulated":
        return []
    if not _usable(rule):
        return [_unknown("roof", rule, part)]
    assert rule is not None
    params = rule.params
    zone = part.zone_code
    checks: list[Check] = []
    form = _FORM_ALIASES.get(house.roof_form, house.roof_form)
    allowed = [str(f) for f in params.get("allowed_forms", [])]
    form_failed = False
    if allowed:
        # Benennt der PLU die Form nicht eindeutig (Krüppelwalm), entscheidet die Prüfung nur, wenn alle
        # Lesarten gleich ausgehen; sonst bleibt sie offen, bis die Auslegung festgelegt ist (E-HM-61)
        readings = house.roof_form_readings or (form,)
        fitting = [f for f in readings if f in allowed]
        form_failed = not fitting
        undecided = 0 < len(fitting) < len(readings)
        checks.append(
            Check(
                code="roof_form_open" if undecided else "roof_form",
                kind="roof",
                status=UNKNOWN if undecided else FAIL if form_failed else PASS,
                binding=not undecided,
                measured=form,
                limit=",".join(allowed),
                params={"readings": ",".join(readings)} if house.roof_form_readings else {},
                zone_code=zone,
                citation=rule.citation,
            )
        )
    flat_rule = params.get("flat_roof")
    if house.is_flat and flat_rule and not form_failed:
        if flat_rule in ("forbidden", "annex_only"):
            status, binding = FAIL, True
        elif flat_rule == "green_only":
            status, binding = HINT, False
        else:
            status, binding = PASS, True
        checks.append(
            Check(
                code="roof_flat",
                kind="roof",
                status=status,
                binding=binding,
                measured=form,
                limit=str(flat_rule),
                zone_code=zone,
                citation=rule.citation,
            )
        )
    minimum, maximum = params.get("pitch_min_deg"), params.get("pitch_max_deg")
    if (minimum is not None or maximum is not None) and not house.is_flat:
        pitch = house.pitch_deg
        if pitch is None and house.roof_pitches_deg:
            checks.append(_pitches_check(house.roof_pitches_deg, minimum, maximum, zone, rule))
        elif pitch is None:
            checks.append(
                Check(
                    code="roof_pitch",
                    kind="roof",
                    status=UNKNOWN,
                    binding=False,
                    zone_code=zone,
                    reason="pitch_missing",
                )
            )
        else:
            too_flat = minimum is not None and pitch < float(minimum) - tol.PITCH_TOLERANCE_DEG
            too_steep = maximum is not None and pitch > float(maximum) + tol.PITCH_TOLERANCE_DEG
            checks.append(
                Check(
                    code="roof_pitch",
                    kind="roof",
                    status=FAIL if too_flat or too_steep else PASS,
                    measured=pitch,
                    limit=_number(minimum if too_flat or maximum is None else maximum),
                    unit="deg",
                    params={"min": minimum, "max": maximum},
                    zone_code=zone,
                    citation=rule.citation,
                )
            )
    return checks


def _pitches_check(
    pitches: tuple[float, ...], minimum: Any, maximum: Any, zone: str | None, rule: RuleInput
) -> Check:
    """Dachflächen verschieden geneigt (Mansarde, Krüppelwalm): entschieden, wenn alle Neigungen die Grenzen
    einhalten oder keine; sonst offen, weil die Auslegung festlegt, welche Neigung maßgeblich ist
    (E-HM-61)."""

    def violated(pitch: float) -> float | None:
        if minimum is not None and pitch < float(minimum) - tol.PITCH_TOLERANCE_DEG:
            return float(minimum)
        if maximum is not None and pitch > float(maximum) + tol.PITCH_TOLERANCE_DEG:
            return float(maximum)
        return None

    failing = [(p, limit) for p in pitches if (limit := violated(p)) is not None]
    undecided = 0 < len(failing) < len(pitches)
    if failing:
        measured, limit = failing[0]
    else:
        # Alle eingehalten: die Neigung am nächsten an einer Grenze
        measured = max(pitches) if maximum is not None else min(pitches)
        limit = float(maximum) if maximum is not None else float(minimum)
    return Check(
        code="roof_pitch_open" if undecided else "roof_pitch",
        kind="roof",
        status=UNKNOWN if undecided else FAIL if failing else PASS,
        binding=not undecided,
        measured=measured,
        limit=limit,
        unit="deg",
        params={"min": minimum, "max": maximum, "pitches": ",".join(f"{p:g}" for p in pitches)},
        zone_code=zone,
        citation=rule.citation,
    )


def _height_checks(house: HouseType, part: PartContext, ctx: SiteContext) -> list[Check]:
    rule = rule_for(part.rules, "max_height")
    if rule is not None and rule.status == "not_regulated":
        return []
    if not _usable(rule):
        return [_unknown("max_height", rule, part)]
    assert rule is not None
    params = rule.params
    zone = part.zone_code
    checks: list[Check] = []
    unverifiable = _height_unverifiable(ctx, params)
    if unverifiable is not None:
        checks.append(
            Check(
                code="height_unverifiable",
                kind="max_height",
                status=UNKNOWN,
                binding=False,
                reason=unverifiable,
                zone_code=zone,
                citation=rule.citation,
            )
        )
    else:
        ridge_limit = params.get("parapet_m") if house.is_flat else None
        if ridge_limit is None:
            ridge_limit = params.get("ridge_m")
        if ridge_limit is not None:
            checks.append(_height("height_ridge", house.ridge_height_m, float(ridge_limit), zone, rule))
        if params.get("eave_m") is not None and not house.is_flat:
            checks.append(_height("height_eave", house.eave_height_m, float(params["eave_m"]), zone, rule))
    storeys = params.get("storeys")
    if storeys:
        fit = storeys_fit(house.storeys, str(storeys))
        checks.append(
            Check(
                code="height_storeys",
                kind="max_height",
                status=PASS if fit else FAIL,
                measured=house.storeys,
                limit=str(storeys),
                zone_code=zone,
                citation=rule.citation,
            )
        )
    return checks


def _height_unverifiable(ctx: SiteContext, params: dict[str, Any]) -> str | None:
    """Höhen gelten über natürlichem Gelände; ohne belastbares Gelände nicht prüfbar (Spez. 5.9.4)."""
    if params.get("reference") == "street_level":
        return "street_level"
    terrain = ctx.terrain
    if terrain.status != "ok":
        return "terrain_unavailable"
    if terrain.slope_percent is not None and terrain.slope_percent > tol.FLAT_SLOPE_MAX_PERCENT:
        return "terrain_steep"
    return None


def _height(code: str, measured: float, limit: float, zone: str, rule: RuleInput) -> Check:
    return Check(
        code=code,
        kind="max_height",
        status=PASS if measured <= limit + tol.HEIGHT_TOLERANCE_M else FAIL,
        measured=measured,
        limit=limit,
        unit="m",
        zone_code=zone,
        citation=rule.citation,
    )


def _footprint_checks(house: HouseType, part: PartContext) -> list[Check]:
    rule = rule_for(part.rules, "max_footprint_ratio")
    if rule is not None and rule.status == "not_regulated":
        return []
    if not _usable(rule):
        return [_unknown("max_footprint_ratio", rule, part)]
    assert rule is not None
    ratio = rule.params.get("ratio")
    if ratio is None:
        return []
    counts_overhangs = rule.params.get("counts_overhangs") == "yes"
    measured = house.projection.area if counts_overhangs else house.facade.area
    limit = float(ratio) * part.area_m2
    return [
        Check(
            code="footprint",
            kind="max_footprint_ratio",
            status=PASS if measured <= limit + 1e-6 else FAIL,
            measured=round(measured, 2),
            limit=round(limit, 2),
            unit="m2",
            zone_code=part.zone_code,
            citation=rule.citation,
            params={"ratio": ratio},
        )
    ]


def parse_storeys(value: str) -> tuple[int, str] | None:
    """`R+1+C` → (1, `C`); `R` → (0, ``); `R+2+A` → (2, `A`)."""
    match = _STOREYS.match(value.replace(" ", ""))
    if match is None:
        return None
    top = (match.group(2) or "").upper()
    return int(match.group(1) or 0), "C" if top in ("C", "CA", "COMBLES") else top


def storeys_fit(house: str, limit: str) -> bool:
    """Passt die Geschossfolge des Typs in die zulässige? Unlesbare Angaben gelten als nicht passend."""
    have, allowed = parse_storeys(house), parse_storeys(limit)
    if have is None or allowed is None:
        return False
    if have[0] > allowed[0]:
        return False
    return have[1] == "" or have[1] == allowed[1]


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
