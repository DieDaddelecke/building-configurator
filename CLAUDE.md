@AGENTS.md

# Arbeitsweise für Claude

## Zu Beginn jeder Session

Bevor du auf eine Aufgabe eingehst:

1. **[HANDOFF.md](HANDOFF.md) vollständig lesen** – aktueller Stand, offene Entscheidungen, offene Arbeitspunkte, nächster Schritt.
2. **[AENDERUNGEN.md](AENDERUNGEN.md): mindestens den neuesten Eintrag lesen.**
3. **Memory lesen:** Der Index `MEMORY.md` wird automatisch geladen. Die Memory-Dateien, die für die Aufgabe relevant sind, vollständig lesen.
4. **Aktuelle Dokumentation:** `AGENTS.md` ist oben eingebunden; ihre Dokumententabelle sagt, welches Dokument wofür gilt. Die großen Dokumente (`BACKEND_SPEZIFIKATION.md`, `UMSETZUNGSPLAN.md`, `Dokumentation.html`, `Hauskonfigurator.jsx`) in den Kapiteln lesen, die die Aufgabe betrifft; Überschriften per Grep (`^#{2,3} `) finden. Vollständig lesen, wenn die Aufgabe das ganze Dokument betrifft (Überarbeitung, Prüfung) oder wenn Kapitel 0 der Spezifikation es vor Backend-Code verlangt.
5. **Abgleich:** Angaben aus HANDOFF.md und Memory, die Dateien, Kapitel oder Entscheidungen nennen, gegen den aktuellen Dateistand prüfen. Widersprüche dem Nutzer melden, bevor darauf aufgebaut wird.

## Am Ende einer Session: `/handoff`

Der Befehl `/handoff` ([.claude/skills/handoff/SKILL.md](.claude/skills/handoff/SKILL.md)) aktualisiert alle betroffenen Dokumente, schreibt AENDERUNGEN.md und HANDOFF.md fort und pflegt das Memory, damit eine neue Session ohne den Gesprächsverlauf weiterarbeiten kann. Der Nutzer ruft ihn auf. Hatte eine Session umfangreiche Änderungen oder Ergebnisse, die nur im Chat stehen, schlage ihn am Ende vor.
