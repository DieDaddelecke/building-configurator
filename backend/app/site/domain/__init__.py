"""Reine Fachlogik des Grundstücks: ohne Datenbank, Netz und FastAPI (Plan 3.2, Spez. 12).

Koordinaten sind Lambert-93 (EPSG:2154) in Metern, Winkel in Grad, Azimut 0° = Norden im Uhrzeigersinn.
"""

ENGINE_VERSION = "g1-1.1.0"
"""1.1.0: Hauptstraße nach Sicherheit, dann Länge. Gespeicherte Grundstücke behalten ihre Einordnung, bis sie
neu gebildet oder korrigiert werden."""
