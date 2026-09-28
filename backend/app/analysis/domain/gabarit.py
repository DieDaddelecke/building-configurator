"""Gabarit: Konturen je Höhenstufe in beiden Auslegungen (docs/PLAN_AN3_GABARIT.md 3.1, 3.2).

Eine Stufe `(von, bis]` hat die Kontur bei `bis`: Baukörperteile, die bis dorthin reichen, müssen darin liegen
(sichere Seite, sobald der Abstand mit der Höhe wächst). Die Ableitung ist die des Baurahmens
(`derive.contour_at_height`); hier kommen Stufen, Höhen je Teilfläche und ein Zwischenspeicher dazu.
"""

import math
from dataclasses import dataclass, field, replace

from shapely.geometry.base import BaseGeometry

from app.envelope.domain import tolerances as tol
from app.envelope.domain.derive import READINGS, Contour, Envelope, contour_at_height, reaches
from app.envelope.domain.heights import Heights, from_storeys
from app.envelope.domain.inputs import EnvelopeInput
from app.envelope.domain.setbacks import at_height, distances

STEP_M = 3.00
"""Stufenhöhe ohne kennzeichnende Höhe dazwischen (E-AN3G-2): etwa ein Geschoss."""
HEIGHT_DECIMALS = 2

Signature = tuple[object, ...]


@dataclass(frozen=True)
class LevelContour:
    geometry: BaseGeometry
    area_m2: float
    complete: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Level:
    from_m: float
    to_m: float
    contours: dict[str, LevelContour]
    """Je Auslegung (`lenient`, `strict`)."""
    roof: bool
    """Über der Traufe jeder Teilfläche, die bis hierher reicht: Dachzone (E-AN3G-7)."""


@dataclass(frozen=True)
class Gabarit:
    status: str
    """`ok`, `partial` (eine Teilfläche ohne Höchsthöhe) oder `unavailable`."""
    reason: str | None
    top_m: float | None
    storey_height_m: float | None
    """Geschosshöhe, mit der eine reine Geschossangabe umgerechnet ist; sonst `None`."""
    levels: list[Level]
    heights: dict[str, Heights]
    reasons: list[str] = field(default_factory=list)
    contours: "Contours | None" = None


def zone_heights(envelope: Envelope, storey_height_m: float) -> dict[str, Heights]:
    """Höhen je Teilfläche: Meter aus dem Plan unverändert; eine reine Geschossangabe mit der Geschosshöhe der
    Annahmen statt der 3,00 m aus G3 umgerechnet (docs/PLAN_AN3_GABARIT.md 7.1 Nr. 3)."""
    result: dict[str, Heights] = {}
    for part in envelope.parts:
        heights = part.heights
        if heights.assumptions and heights.storeys:
            derived = from_storeys(heights.storeys, storey_height_m)
            if derived is not None:
                heights = replace(
                    heights,
                    eave_m=derived[0],
                    ridge_m=derived[1],
                    assumptions=[f"storey_height_{storey_height_m:.2f}"],
                )
        result[part.zone_code] = heights
    return result


class Contours:
    """Konturen je Höhe und Auslegung. Stufen mit gleichen Abständen und gleichen Teilflächen ergeben dieselbe
    Kontur und werden nur einmal gerechnet (7.1 Nr. 9)."""

    def __init__(self, data: EnvelopeInput, envelope: Envelope, heights: dict[str, Heights]) -> None:
        self._data = data
        self._envelope = envelope
        self._heights = heights
        self._active = [p.zone_code for p in envelope.parts if p.excluded is None]
        self._contours: dict[Signature, Contour] = {}
        self._areas: dict[tuple[Signature, str], float] = {}

    def signature(self, height_m: float, reading: str) -> Signature:
        """Was die Kontur bestimmt: Teilflächen, die bis `height_m` reichen, und der Abstand je Kante."""
        reaching = tuple(z for z in self._active if reaches(self._heights[z], height_m))
        values: list[tuple[int, str, float | None]] = []
        for edge in self._envelope.edges:
            for zone in reaching:
                setbacks = [
                    at_height(s, self._heights[zone], height_m) for s in edge.setbacks if s.zone_code == zone
                ]
                if not setbacks:
                    continue
                lenient, strict, _ = distances(setbacks)
                value = lenient if reading == "lenient" else strict
                values.append((edge.seq, zone, None if value is None else round(value, 4)))
        return (reading, reaching, tuple(values))

    def at(self, height_m: float, reading: str) -> Contour:
        key = self.signature(height_m, reading)
        if key not in self._contours:
            self._contours[key] = contour_at_height(
                self._data, self._envelope, height_m, reading, self._heights
            )
        return self._contours[key]

    def area_in(self, height_m: float, reading: str, zone_code: str) -> float:
        """Fläche der Kontur innerhalb einer Teilfläche (für die Nutzfläche je Geschoss, 3.4)."""
        key = (self.signature(height_m, reading), zone_code)
        if key not in self._areas:
            part = next(p for p in self._envelope.parts if p.zone_code == zone_code)
            contour = self.at(height_m, reading).geometry
            self._areas[key] = 0.0 if contour.is_empty else float(contour.intersection(part.geometry).area)
        return self._areas[key]


def _tops(
    envelope: Envelope, heights: dict[str, Heights], zones: list[str]
) -> tuple[list[float], set[float]]:
    """Obergrenzen der Stufen (alle 3 m und die kennzeichnenden Höhen) und die Traufen darunter."""
    top = max(h for z in zones if (h := heights[z].highest_m) is not None)
    tops = {round(STEP_M * k, HEIGHT_DECIMALS) for k in range(1, math.floor(top / STEP_M + 1e-9) + 1)}
    eaves: set[float] = set()
    for zone in zones:
        zone_top = heights[zone].highest_m
        if zone_top is None:
            continue
        tops.add(round(zone_top, HEIGHT_DECIMALS))
        eave = heights[zone].eave_m
        if eave is not None and eave < zone_top - tol.DISTANCE_EPSILON_M:
            eaves.add(round(eave, HEIGHT_DECIMALS))
    tops |= eaves
    for edge in envelope.edges:
        for setback in edge.setbacks:
            limit = setback.params.get("on_boundary_max_height_m")
            if setback.params.get("allow_on_boundary") and isinstance(limit, int | float) and limit > 0:
                tops.add(round(float(limit), HEIGHT_DECIMALS))
    return sorted(t for t in tops if 0 < t <= top + tol.DISTANCE_EPSILON_M), eaves


def _roof(heights: dict[str, Heights], zones: list[str], from_m: float, to_m: float) -> bool:
    reaching = [z for z in zones if reaches(heights[z], to_m)]
    return bool(reaching) and all(
        (eave := heights[z].eave_m) is not None and from_m >= eave - tol.DISTANCE_EPSILON_M for z in reaching
    )


def _level_contour(contour: Contour) -> LevelContour:
    return LevelContour(
        geometry=contour.geometry,
        area_m2=contour.area_m2,
        complete=contour.complete,
        reasons=contour.incomplete_reasons,
    )


def gabarit(data: EnvelopeInput, envelope: Envelope, storey_height_m: float) -> Gabarit:
    """Stufen des Hüllkörpers. `storey_height_m` rechnet eine reine Geschossangabe um (obere Geschosshöhe der
    Annahmen, 3.2)."""
    heights = zone_heights(envelope, storey_height_m)
    converted = any(heights[p.zone_code].assumptions for p in envelope.parts if p.excluded is None)
    active = [p.zone_code for p in envelope.parts if p.excluded is None]
    if not active:
        return Gabarit("unavailable", "no_buildable_zone", None, None, [], heights)
    known = [z for z in active if heights[z].highest_m is not None]
    reasons = [f"height_unknown:{z}" for z in active if z not in known]
    if not known:
        return Gabarit("unavailable", "height_unknown", None, None, [], heights, reasons)

    contours = Contours(data, envelope, heights)
    tops, eaves = _tops(envelope, heights, known)
    levels: list[Level] = []
    previous = 0.0
    last: tuple[Signature, ...] | None = None
    for top in tops:
        current = tuple(contours.signature(top, reading) for reading in READINGS)
        if levels and current == last and previous not in eaves:
            # Gleiche Abstände wie darunter: die Stufe wächst (7.1 Nr. 5: nie über eine Traufe hinweg)
            levels[-1] = replace(levels[-1], to_m=top)
        else:
            levels.append(
                Level(
                    from_m=previous,
                    to_m=top,
                    contours={reading: _level_contour(contours.at(top, reading)) for reading in READINGS},
                    roof=_roof(heights, known, previous, top),
                )
            )
        previous, last = top, current
    return Gabarit(
        status="partial" if reasons else "ok",
        reason=None,
        top_m=tops[-1] if tops else None,
        storey_height_m=storey_height_m if converted else None,
        levels=levels,
        heights=heights,
        reasons=reasons,
        contours=contours,
    )
