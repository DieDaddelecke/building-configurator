"""Benannte Toleranzen und Schwellen des Hauskatalogs (Spez. 13; Plan H1 3.5). Einheiten im Namen."""

# Neigungsprüfung (Plan H1 3.5, Spez. 5.4.5): nur für Dachformen mit definiertem First
ANGLE_TOLERANCE_DEG = 0.1
"""Ohne Toleranz fiele ein mit 34,99° berechneter First unter eine Mindestneigung von 35°."""
PITCHED_ROOF_FORMS = ("gable", "hip")
"""Dachformen mit einer Neigungsprüfung. `flat` und `complex` haben keinen geometrisch definierten First."""

# Raumflächen vs. Geschossfläche (Plan H1 3.5, Spez. 5.4.5)
ROOM_AREA_SHARE_MIN = 0.75
ROOM_AREA_SHARE_MAX = 0.95

# Umriss aus DXF (Plan H1 3.3)
FOOTPRINT_MIN_AREA_M2 = 20.0
FOOTPRINT_MAX_AREA_M2 = 2_000.0
FOOTPRINT_LAYER_FACADE = "EMPRISE_FOOTPRINT_FACADE"
FOOTPRINT_LAYER_PROJECTION = "EMPRISE_FOOTPRINT_PROJECTION"

# Speicherung (Spez. 13)
STORAGE_DECIMALS = 3
