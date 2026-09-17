"""Benannte Toleranzen und Schwellen der Grundstücksgeometrie (Spez. 13). Einheiten im Namen."""

# Grundstück bilden (Spez. 5.1.3)
SLIVER_CLOSE_M = 0.02
"""Spalten zwischen gewählten Parzellen bis zur doppelten Breite werden beim Vereinigen geschlossen."""
AREA_MISMATCH_RATIO = 0.03
MAX_PARCELS = 10

# Kanten bilden (Spez. 5.1.4 Schritt 1)
SIMPLIFY_TOLERANCE_M = 0.05
MERGE_ANGLE_DEG = 5.0
MIN_SEGMENT_M = 1e-6

# Kanten einordnen (Spez. 5.1.4 Schritte 2–5)
NEIGHBOUR_DISTANCE_M = 0.5
NEIGHBOUR_SHARE_STREET_MAX = 0.5
"""Liegt weniger als dieser Anteil einer Kante nahe einer Nachbarparzelle, ist sie Straßenkante."""
ADJACENT_SHARE_MIN = 0.1
ADJACENT_LENGTH_MIN_M = 1.0
PROBE_OFFSET_M = 2.0
PRIVATE_ROAD_MAX_WIDTH_M = 8.0
PRIVATE_ROAD_STREET_CONFIDENCE = 0.4
REAR_ANGLE_DEG = 45.0
CORNER_ANGLE_DEG = 45.0
CORNER_MIN_EDGE_M = 8.0
"""Mindestlänge je Straßenfront, damit zwei Fronten ein Eckgrundstück bilden."""
CORNER_CUT_MAX_M = 10.0
"""Längster kurzer Eckabschnitt (abgeschrägte Ecke) zwischen zwei Fronten."""
FLAG_LOT_MAX_FRONTAGE_M = 6.0
FLAG_LOT_MIN_AREA_M2 = 300.0
ROAD_DISTANCE_M = 15.0
"""Straßenachse bis zu diesem Abstand außerhalb der Kante bestätigt die Straßenkante (Spez. 5.1.4)."""
ROAD_SHARE_MIN = 0.5
ROAD_SAMPLE_SPACING_M = 1.0
ROAD_SAMPLES_MAX = 25
SITE_CROSSING_MAX_M = 0.1
BUILT_CROSSING_MAX_M = 1.0
"""Führt der Weg zur Achse über ein bebautes Nachbargrundstück, liegt die Straße hinter dem Nachbarn."""
UNCONFIRMED_STREET_CONFIDENCE = 0.55
"""Kante ohne Nachbarn, aber ohne Straßenachse in Reichweite: Grünfläche, Gewässer oder Bahn möglich."""
PARTIAL_COVERAGE_STREET_CONFIDENCE = 0.5
"""Am Rand des Einzugsgebiets fehlen Nachbarn; eine Kante ohne Nachbarn ist dort nur vermutlich Straße."""
REVIEW_CONFIDENCE_BELOW = 0.65
"""Automatisch eingeordnete Kanten darunter erzeugen die Warnung `edges_need_review`."""

# Umgebung laden (Spez. 5.1.1, Plan 3.3)
NEIGHBOUR_SEARCH_M = 50.0
LOOKUP_RADIUS_M = 20.0
CONTEXT_RADIUS_M = 25.0

# Gelände (Spez. 5.9.4)
TERRAIN_SAMPLES = 9
FLAT_SLOPE_MAX_PERCENT = 5.0

# Freies Zeichnen ohne Kataster, Weg E (Plan 3.3)
MANUAL_MIN_EDGES = 3
MANUAL_MAX_EDGES = 40
MANUAL_MIN_EDGE_M = 1.0
MANUAL_MAX_EDGE_M = 500.0
MANUAL_MIN_AREA_M2 = 20.0
MANUAL_MAX_AREA_M2 = 50_000.0

# Speicherung (Spez. 13)
STORAGE_DECIMALS = 3
