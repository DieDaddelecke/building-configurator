"""Konsistenzprüfungen ohne IFC-Modell (Plan H1 3.5).

Von den fünf IFC-Prüfungen aus Spez. 5.4.5 lässt sich ohne Modell nur die Neigung aus First, Traufe und
Tiefe sinnvoll gegenrechnen; die übrigen setzen Bauteile voraus, die es beim manuellen Erfassungsweg nicht
gibt. Eine Warnung zu den Raumflächen bleibt möglich, aber bewusst großzügig (keine Innenwandfläche
bekannt).
"""

import math
from dataclasses import dataclass

from app.catalog.domain import tolerances as tol


@dataclass(frozen=True)
class ConsistencyFinding:
    code: str
    level: str
    """`error` oder `warning`."""
    detail: str


def check_roof_pitch(
    *,
    roof_form: str,
    declared_pitch_deg: float | None,
    ridge_height_m: float,
    eave_height_m: float,
    depth_m: float,
) -> ConsistencyFinding | None:
    """Neigung aus Firsthöhe, Traufhöhe und Tiefe gegen die angegebene Neigung (Spez. 5.4.5).

    Nur für Dachformen mit geometrisch definiertem First (`gable`, `hip`, Plan H1 3.5). Der First liegt in
    der Mitte der Tiefe; der Lauf ist deshalb die halbe Tiefe (Beispiel Ligne in Spez. 5.4.5:
    `atan(2,8 / 4,0) = 35,0°` bei 8,0 m Tiefe).
    """
    if roof_form not in tol.PITCHED_ROOF_FORMS:
        return None
    if declared_pitch_deg is None:
        return ConsistencyFinding("pitch_missing", "error", "Neigung fehlt für eine geneigte Dachform")
    run_m = depth_m / 2
    if run_m <= 0:
        return ConsistencyFinding("depth_invalid", "error", "Tiefe muss positiv sein")
    computed_deg = math.degrees(math.atan((ridge_height_m - eave_height_m) / run_m))
    if abs(computed_deg - declared_pitch_deg) > tol.ANGLE_TOLERANCE_DEG:
        return ConsistencyFinding(
            "pitch_mismatch",
            "error",
            f"angegeben {declared_pitch_deg:.1f}°, aus Höhen und Tiefe berechnet {computed_deg:.1f}°",
        )
    return None


def check_room_area_share(
    *, room_area_sum_m2: float, storey_footprint_m2: float
) -> ConsistencyFinding | None:
    """Summe der Raumflächen gegen die Geschossfläche (Spez. 5.4.5), hier als weite Warnschwelle."""
    if storey_footprint_m2 <= 0:
        return None
    share = room_area_sum_m2 / storey_footprint_m2
    if not tol.ROOM_AREA_SHARE_MIN <= share <= tol.ROOM_AREA_SHARE_MAX:
        return ConsistencyFinding(
            "room_area_share_unusual",
            "warning",
            f"Raumflächen sind {share:.0%} der Geschossfläche (erwartet "
            f"{tol.ROOM_AREA_SHARE_MIN:.0%}–{tol.ROOM_AREA_SHARE_MAX:.0%})",
        )
    return None
