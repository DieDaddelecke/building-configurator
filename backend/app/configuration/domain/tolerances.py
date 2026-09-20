"""Benannte Toleranzen und Grenzen von H2 (Spez. 13). Einheiten im Namen."""

DISTANCE_TOLERANCE_M = 0.01
"""Rechentoleranz für Abstände und Zugehörigkeit (Spez. 5.3.4: „− 0,01“)."""
ROTATION_TOLERANCE_DEG = 0.05
"""Eine übermittelte Drehung gilt als erlaubt, wenn sie so nah an einer erlaubten liegt."""
RIDGE_TOLERANCE_DEG = 10.0
"""Firstrichtung nach der Implantation gegen die Vorgabe (Spez. 5.3.4)."""
PITCH_TOLERANCE_DEG = 0.1
"""Wie bei H1: Ligne hat aus der Geometrie 34,99° und darf die Mindestneigung von 35° nicht verfehlen."""
HEIGHT_TOLERANCE_M = 0.005
MIN_SURFACE_AREA_M2 = 1e-4
"""Kleinere Flächen zulässiger Ursprünge sind Rechenstaub, keine Lage (1 cm²)."""
FLAT_SLOPE_MAX_PERCENT = 5.0
"""Über dieser Neigung sind Höhenprüfungen `unknown` (Spez. 5.9.4, wie G3)."""

# Schnellstellungen (Spez. 5.3.5)
PRESET_GRID_M = 0.5
"""Raster der zusätzlichen Kandidaten im Inneren der Fläche; Ecken und Kantenmitten kommen immer dazu."""
PRESET_CANDIDATES_MAX = 4000
GARDEN_CANDIDATES_MAX = 150
"""Für `garden_max` wird je Kandidat eine Differenzfläche gebildet; mehr als das lohnt nicht."""
PRESET_TIE_M = 0.05
"""Gleichstand bei der Zielfunktion: dann gewinnt die erste (straßenzugewandte) Drehung."""

STORAGE_DECIMALS = 3
"""Stellen beim Ausgeben von Koordinaten in Metern."""

# Terrasse, Carport, Zufahrt und Flächen (Plan H3 3.3–3.5, Spez. 5.9.3)
DRIVEWAY_WIDTH_M = 3.0
"""Breite der Zufahrt zum Carport oder Garagentor."""
PATHS_LUMP_M2 = 10.0
"""Wege: Pauschale (Spez. 5.9.3, Standard); der Preiskatalog trägt das Feld nicht (Plan H3 3.5)."""
TERRACE_COUNTS_ABOVE_M = 0.6
"""Eine Terrasse zählt zur Grundfläche, wenn sie höher liegt (Spez. 5.5.5); die Regel kann es ändern."""
AREA_DECIMALS = 2
"""Stellen bei Flächen in m² in den Antworten."""
OUTBUILDING_CLEARANCE_M = 0.5
"""Abstand zwischen Carport und Haus: der Carport berührt das Haus nicht (Plan H3 3.4)."""
