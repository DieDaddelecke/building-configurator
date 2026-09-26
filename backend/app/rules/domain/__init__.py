"""Reine Fachlogik des Regelwerks: ohne Datenbank, Netz und FastAPI (Plan 3.2, 3.4; Spez. 12).

Die Regeln sind eine unverbindliche Simulation (Entscheidung D11). Die Schranken in `assess` ersetzen die
Freigabe durch das Büro: Nur belegte und plausible Werte wirken, alles andere wird `unknown`.
"""

ENGINE_VERSION = "g2-1.2.0"
"""Stand der Schranken. Eine neue Version bewertet gespeicherte Antworten des Modells neu, ohne Aufruf."""
PROMPT_VERSION = "g2-prompt-4"
"""Bezeichnung des Prompts für Berichte. Ob neu ausgewertet wird, entscheidet die Prüfsumme über Prompts
und Schemata (`extraction.prompt_fingerprint`): Eine vergessene Erhöhung nutzt keine alten Antworten.
"""
