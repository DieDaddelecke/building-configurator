"""Benannte Toleranzen und Annahmen des Baurahmens (Spez. 13). Einheiten im Namen."""

# Bebaubare Fläche (Spez. 5.3.2)
MIN_PART_AREA_M2 = 4.0
"""Teilflächen darunter entfallen: dort passt kein Baukörper."""
MIN_PART_WIDTH_M = 2.0
"""Breite geprüft über buffer(-w/2).buffer(w/2)."""
DISTANCE_EPSILON_M = 0.01
"""Rechentoleranz für Abstände (Spez. 5.3.4)."""

# Standard-Geschosshöhen (Plan 3.5): nur für die engste Kontur, nie als angezeigter Grenzwert
STOREY_HEIGHT_M = 3.00
"""Geschosshöhe, wenn der PLU nur Geschosse nennt (z. B. `R+1+C`). Übliche Umrechnung in französischen
Plänen (R+1 ≈ 6 m à l'égout); der Wert wirkt nur auf höhenabhängige Abstände der engsten Auslegung."""
ROOF_STOREY_RIDGE_M = 5.00
"""Zuschlag von der Traufe zum First bei einem ausgebauten Dachgeschoss (`C`)."""
ATTIC_STOREY_HEIGHT_M = 3.00
"""Höhe eines Attikageschosses (`A`)."""

# Speicherung (Spez. 13)
STORAGE_DECIMALS = 3
