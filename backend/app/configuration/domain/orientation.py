"""Himmelsrichtung der Fassaden mit Meridiankonvergenz (Plan H3 3.10, HP05).

Die Lage rechnet in Lambert-93; „Norden“ ist dort Gitternorden. Der wahre Azimut einer Richtung ist ihr
Gitterazimut plus die Konvergenz `γ = atan2(X − X_s, Y_s − Y)` (Lambert-93 als Kegelprojektion mit dem
Scheitel in `(X_s, Y_s)`, Konstanten der IGN, ALG0002). Westlich des Mittelmeridians (3° O) ist `γ`
negativ: Der wahre Norden liegt im Gitter östlich des Gitternordens, eine Richtung mit dem Gitterazimut 0°
zeigt also wahr etwas westlich von Norden. In Treillières ist `γ ≈ −3,3°`.
"""

import math
from dataclasses import dataclass

from app.configuration.domain.geometry import normalize_deg
from app.configuration.domain.house import HouseType, role_normal_model_deg

LAMBERT93_X_S = 700000.0
LAMBERT93_Y_S = 12655612.049876
ROLES = ("street", "garden", "side_left", "side_right")


def convergence_deg(easting: float, northing: float) -> float:
    return math.degrees(math.atan2(easting - LAMBERT93_X_S, LAMBERT93_Y_S - northing))


@dataclass(frozen=True)
class Orientation:
    convergence_deg: float
    facades: dict[str, float]
    """Rolle → wahrer Azimut der Außennormalen (0° = Norden, im Uhrzeigersinn); nur zugewiesene Rollen."""


def orientation(house: HouseType, rotation_deg: float, site_centre: tuple[float, float]) -> Orientation:
    """Wahre Azimute der Fassadenrollen für ein Haus mit dieser Drehung; `site_centre` in Lambert-93."""
    gamma = convergence_deg(*site_centre)
    facades: dict[str, float] = {}
    for role in ROLES:
        model = role_normal_model_deg(house, role)
        if model is not None:
            facades[role] = normalize_deg(model + rotation_deg + gamma)
    return Orientation(round(gamma, 2), facades)
