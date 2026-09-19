@AGENTS.md

# Arbeitsweise für Claude

## Zu Beginn jeder Session

Bevor du auf eine Aufgabe eingehst:

1. **[HANDOFF.md](HANDOFF.md) vollständig lesen** – aktueller Stand, offene Entscheidungen, offene Arbeitspunkte, nächster Schritt.
2. **[AENDERUNGEN.md](AENDERUNGEN.md): den neuesten Eintrag lesen** (oberster `##`-Abschnitt; den davor, wenn der Startprompt ihn nennt).
3. **Memory lesen:** Der Index `MEMORY.md` wird automatisch geladen. Die Memory-Dateien, die für die Aufgabe relevant sind, vollständig lesen.
4. **Aktuelle Dokumentation:** `AGENTS.md` ist oben eingebunden; ihre Dokumententabelle sagt, welches Dokument wofür gilt. Große Dokumente (`BACKEND_SPEZIFIKATION.md`, `UMSETZUNGSPLAN.md`, `docs/ANNAHMEN.md`, `Dokumentation.html`, `Hauskonfigurator.jsx`) nur in den Kapiteln lesen, die die Aufgabe betrifft; Überschriften per Grep (`^#{2,4} `) finden. Spezifikation: Kapitel 0–2 und die im Modulabschnitt des Umsetzungsplans genannten Kapitel (Spez. 0 Punkt 1, Entscheidung 19.09.2026). Vollständig nur, wenn die Aufgabe das ganze Dokument betrifft (Überarbeitung, Prüfung).
5. **Abgleich:** Angaben aus HANDOFF.md und Memory, die Dateien, Kapitel oder Entscheidungen nennen, gegen den aktuellen Dateistand prüfen. Widersprüche dem Nutzer melden, bevor darauf aufgebaut wird.

## Am Ende einer Session: `/handoff`

Der Befehl `/handoff` ([.claude/skills/handoff/SKILL.md](.claude/skills/handoff/SKILL.md)) aktualisiert alle betroffenen Dokumente, schreibt AENDERUNGEN.md und HANDOFF.md fort und pflegt das Memory, damit eine neue Session ohne den Gesprächsverlauf weiterarbeiten kann. Der Nutzer ruft ihn auf. Hatte eine Session umfangreiche Änderungen oder Ergebnisse, die nur im Chat stehen, schlage ihn am Ende vor.
