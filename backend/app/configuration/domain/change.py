"""Eine Änderung der Konfiguration prüfen, ohne Datenbank (Plan H3 3.1, 3.9; D12, L5; REFACTORING_PLAN S14).

Gespeichert wird nie ein Typ, der gesperrt ist, nie eine Lage mit bindendem Verstoß und keine Auswahl mit
neuem bindendem Verstoß. Nur **neue** bindende Verstöße zählen: Der Stand ohne Optionen (was H2 angenommen
hat) und der gespeicherte Stand sind erlaubt, damit niemand in einem Zustand festhängt, den erst ein Katalog-
oder Regelwechsel ungültig gemacht hat. Eine Ablehnung wird erst im Dienst zum Fehler der API.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.catalog.domain.offer import OptionOffer, TypeOffer
from app.configuration.domain import presets
from app.configuration.domain.checks import Check
from app.configuration.domain.context import SiteContext
from app.configuration.domain.design import Design, evaluate_design
from app.configuration.domain.fit import eligible_parts, evaluate_type
from app.configuration.domain.house import HouseType
from app.configuration.domain.options import Reason, Selection, resolve
from app.configuration.domain.outbuildings import carport_spec, terrace_spec
from app.configuration.domain.placement import Placement, PlacementResult, check_placement
from app.configuration.domain.rotations import is_allowed_rotation, site_rotations
from app.configuration.domain.surface import BoundaryOptions, requirements

BlockerKey = tuple[str, str | None, int | None, str | None]
UNOFFERED = frozenset({"not_offered", "unknown_option", "unknown_package", "catalog_unavailable"})
"""Gründe, aus denen eine Wahl beim Typwechsel entfällt (Plan H3 3.1)."""


class ChangeRejected(Exception):
    """Abgelehnte Änderung. `code` wird zum Fehlercode der API; dazu je nach Grund die Prüfungen, Gründe,
    das Ergebnis der Lage, Kanten oder erlaubten Drehungen."""

    def __init__(
        self,
        code: str,
        *,
        checks: Sequence[Check] = (),
        reasons: Sequence[Reason] = (),
        result: PlacementResult | None = None,
        edges: Sequence[int] = (),
        allowed: Sequence[float] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.checks = list(checks)
        self.reasons = list(reasons)
        self.result = result
        self.edges = list(edges)
        self.allowed = list(allowed)


@dataclass(frozen=True)
class Stored:
    """Gespeicherter Stand der Konfiguration."""

    placement: Placement | None
    boundary: BoundaryOptions
    selection: Selection


@dataclass(frozen=True)
class Change:
    """Verlangter Stand, auf den Typ schon angewandt. Ohne verlangte Lage gilt die gespeicherte, nach einem
    Typwechsel keine; fehlt sie, wird die straßennahe Stellung vorgeschlagen."""

    boundary: BoundaryOptions
    selection: Selection
    placement: Placement | None
    place: bool = False
    """Die Lage ist Teil der Änderung (auch „keine Lage“); ihre Drehung muss erlaubt sein."""
    new_type: bool = False
    type_or_boundary: bool = False
    """Typ oder Grenzschalter wurden angefragt: Dann muss der Typ auf das Grundstück passen."""
    selection_changed: bool = False


@dataclass(frozen=True)
class Decision:
    placement: Placement | None
    boundary: BoundaryOptions
    selection: Selection
    dropped: list[str]
    """Wahl, die beim Typwechsel entfiel, sortiert."""


def evaluate(
    house: HouseType,
    placement: Placement | None,
    boundary: BoundaryOptions,
    ctx: SiteContext,
    offer: TypeOffer,
    selection: Selection,
) -> tuple[PlacementResult | None, Design]:
    result = check_placement(house, placement, ctx, boundary) if placement else None
    return result, evaluate_design(house, placement, ctx, result, offer, selection)


def blocker_key(check: Check) -> BlockerKey:
    subject = check.params.get("subject")
    return check.code, check.zone_code, check.edge_seq, str(subject) if subject is not None else None


def new_blockers(design: Design, allowed: set[BlockerKey]) -> list[Check]:
    return [c for c in design.blocking if blocker_key(c) not in allowed]


def allowed_blockers(
    house: HouseType,
    placement: Placement | None,
    boundary: BoundaryOptions,
    ctx: SiteContext,
    offer: TypeOffer,
    stored: Stored | None,
) -> set[BlockerKey]:
    """Verstöße, die schon ohne die neue Wahl bestanden: der Stand ohne Optionen und der gespeicherte."""
    _, base = evaluate(house, placement, boundary, ctx, offer, Selection())
    allowed = {blocker_key(c) for c in base.blocking}
    if stored is not None:
        _, old = evaluate(house, stored.placement, stored.boundary, ctx, offer, stored.selection)
        allowed |= {blocker_key(c) for c in old.blocking}
    return allowed


def drop_unoffered(offer: TypeOffer, selection: Selection) -> tuple[Selection, list[str]]:
    """Beim Typwechsel entfällt, was der neue Typ nicht anbietet (Plan H3 3.1)."""
    bad = {r.slug for r in resolve(offer, selection).invalid if r.code in UNOFFERED and r.slug}
    kept = Selection(
        None if selection.package_slug in bad else selection.package_slug,
        tuple(s for s in selection.option_slugs if s not in bad),
    )
    return kept, sorted(s for s in bad if s)


def check_boundary_options(house: HouseType, ctx: SiteContext, options: BoundaryOptions) -> None:
    """Der Schalter gilt nur an Kanten, deren Regel Bauen auf der Grenze erlaubt (Plan H2 3.4)."""
    if not options:
        return
    permitted: set[int] = set()
    for part in ctx.parts:
        for seq, req in requirements(house, part, ctx, {}).items():
            if req.on_boundary_allowed:
                permitted.add(seq)
    invalid = sorted(seq for seq in options if seq not in permitted)
    if invalid:
        raise ChangeRejected("boundary_not_allowed", edges=invalid)


def allowed_placement(house: HouseType, ctx: SiteContext, requested: Placement | None) -> Placement | None:
    """Verlangte Lage mit der erlaubten Drehung, die der übermittelten entspricht."""
    if requested is None:
        return None
    allowed = site_rotations(house, ctx)
    matched = is_allowed_rotation(requested.rotation_deg, allowed)
    if matched is None:
        raise ChangeRejected("rotation_not_allowed", allowed=allowed)
    return replace(requested, rotation_deg=matched)


def decide_change(
    house: HouseType, ctx: SiteContext, offer: TypeOffer, change: Change, stored: Stored
) -> Decision:
    """Stand, der gespeichert wird, oder `ChangeRejected`. Die Reihenfolge der Prüfungen bestimmt, welcher
    Fehler bei mehreren zurückkommt: Grenzschalter, Typ, Auswahl, Drehung, Lage, neue Verstöße."""
    boundary, selection, placement = change.boundary, change.selection, change.placement
    dropped: list[str] = []
    check_boundary_options(house, ctx, boundary)
    fit = evaluate_type(house, ctx, boundary)
    if not fit.allowed and (change.new_type or change.type_or_boundary):
        raise ChangeRejected("type_blocked", checks=fit.reasons)
    if change.new_type:
        selection, dropped = drop_unoffered(offer, selection)
    elif change.selection_changed:
        known = set(resolve(offer, stored.selection).invalid)
        fresh = [r for r in resolve(offer, selection).invalid if r not in known]
        if fresh:
            raise ChangeRejected("invalid_selection", reasons=fresh)
    if change.place:
        placement = allowed_placement(house, ctx, placement)
    elif placement is None:
        placement = presets.compute(house, ctx, "street_near", boundary, eligible_parts(house, ctx))
    result, design = evaluate(house, placement, boundary, ctx, offer, selection)
    if result is not None and result.blocking:
        raise ChangeRejected("placement_violation", result=result)
    if design.blocking:
        allowed = allowed_blockers(
            house, placement, boundary, ctx, offer, None if change.new_type else stored
        )
        fresh_blockers = new_blockers(design, allowed)
        if fresh_blockers and change.new_type:
            # Optionen, die auf dem neuen Typ nicht aufgehen (Terrasse ohne Garten), fallen weg
            subjects = {str(c.params["subject"]) for c in fresh_blockers if "subject" in c.params}
            gone = subjects & set(selection.option_slugs)
            if gone:
                dropped = sorted({*dropped, *gone})
                selection = replace(
                    selection, option_slugs=tuple(s for s in selection.option_slugs if s not in gone)
                )
                _, design = evaluate(house, placement, boundary, ctx, offer, selection)
                fresh_blockers = new_blockers(design, allowed)
        if fresh_blockers:
            raise ChangeRejected("selection_blocked", checks=fresh_blockers)
    return Decision(placement, boundary, selection, dropped)


OptionStateName = Literal["included", "selected", "blocked", "available"]


@dataclass(frozen=True)
class OptionState:
    option: OptionOffer
    state: OptionStateName
    area_m2: float | None
    reasons: list[Reason]
    blockers: list[Check]


def option_area(option: OptionOffer, house: HouseType) -> float | None:
    if option.kind == "terrace":
        return terrace_spec(option, house).area_m2
    if option.kind == "carport":
        return carport_spec(option).area_m2
    return None


def option_states(
    house: HouseType,
    placement: Placement | None,
    boundary: BoundaryOptions,
    ctx: SiteContext,
    offer: TypeOffer,
    selection: Selection,
) -> list[OptionState]:
    """Zustand jeder angebotenen oder enthaltenen Option (Plan H3 3.9, 4.3). Eine noch nicht gewählte Option
    wird zur Auswahl hinzugenommen und gerechnet: neue bindende Verstöße oder ein Ausschluss machen sie
    `blocked`, mit Gründen. So sieht der Kunde, was nicht geht, ohne den Fehler auszulösen."""
    resolved = resolve(offer, selection)
    known = set(resolved.invalid)
    allowed = allowed_blockers(house, placement, boundary, ctx, offer, Stored(placement, boundary, selection))
    states: list[OptionState] = []
    for option in offer.options:
        included = option.slug in resolved.included_slugs
        if not (option.offered or included):
            continue
        area = option_area(option, house)
        if included:
            states.append(OptionState(option, "included", area, [], []))
            continue
        if option.slug in selection.option_slugs:
            states.append(OptionState(option, "selected", area, [], []))
            continue
        trial = replace(selection, option_slugs=(*selection.option_slugs, option.slug))
        reasons = [r for r in resolve(offer, trial).invalid if r not in known]
        blockers: list[Check] = []
        if not reasons:
            _, design = evaluate(house, placement, boundary, ctx, offer, trial)
            blockers = new_blockers(design, allowed)
        states.append(
            OptionState(option, "blocked" if reasons or blockers else "available", area, reasons, blockers)
        )
    return states
