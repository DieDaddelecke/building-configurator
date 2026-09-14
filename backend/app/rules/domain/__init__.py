"""Reine Fachlogik des Regelwerks: ohne Datenbank, Netz und FastAPI (Plan 3.2, 3.4; Spez. 12).

Die Regeln sind eine unverbindliche Simulation (Entscheidung D11). Die Schranken in `assess` ersetzen die
Freigabe durch das Büro: Nur belegte und plausible Werte wirken, alles andere wird `unknown`.
"""

ENGINE_VERSION = "g2-1.0.0"
PROMPT_VERSION = "g2-prompt-1"
"""Ändert sich der Prompt oder das Ausgabeschema, steigt die Version; Ergebnisse werden dann neu erzeugt."""
