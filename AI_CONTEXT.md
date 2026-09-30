# KI-Kontext: Emprise

Einstieg für KI-Agenten (Claude, Codex und andere). `CLAUDE.md` und `AGENTS.md` verweisen hierher.

## Projekt

Webplattform für Bauinteressenten in Frankreich: Parzelle wählen, die Vorgaben des Bebauungsplans (PLU) werden zu Grenzen, darin wird ein Haus konfiguriert (Typ, Ausstattungslinie, Optionen, Lage). Ergebnis ist kein Kauf, sondern ein unverbindlicher Vorentwurf, den ein Architekturbüro prüft. In derselben Anwendung: „Emprise Analyse“, mit der Architekten des Büros Parzelle und PLU hochladen und Baurahmen, Nutzfläche, Bericht und DXF erhalten. „Emprise“ ist eine eigene Marke, getrennt vom Büro.

Stand und nächster Schritt: [ROADMAP.md](ROADMAP.md).

## Zu Beginn jeder Session

1. [ROADMAP.md](ROADMAP.md) vollständig lesen.
2. Memory lesen: Der Index `MEMORY.md` wird automatisch geladen; die für die Aufgabe relevanten Dateien vollständig lesen.
3. Die Abschnitte lesen, die die Aufgabe betreffen: [ARCHITECTURE.md](ARCHITECTURE.md), [DOMAIN.md](DOMAIN.md), [DECISIONS.md](DECISIONS.md); vor Code-Arbeit [README.md](README.md) (Prüfbefehle, Regeln für API-Änderungen, Stolperstellen).
4. Das Archiv (`docs/archiv/`) nur zum Nachschlagen einer ID oder eines Kapitels, auf die Code oder DECISIONS verweisen; Überschriften per Grep (`^#{2,4} `) finden.
5. Abgleich: Angaben aus ROADMAP und Memory, die Dateien, Kapitel oder Entscheidungen nennen, gegen den aktuellen Dateistand prüfen. Widersprüche dem Nutzer melden, bevor darauf aufgebaut wird.

## Dokumente

| Datei | Inhalt | Pflegen, wenn … |
|---|---|---|
| [README.md](README.md) | Aufbau, Start, Prüfen, Regeln für API-Änderungen, Stolperstellen | eine dauerhafte Stolperstelle auftaucht, Befehle sich ändern |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Dienste, Module, Schichten, Abläufe, Anmeldung, Auslöser für spätere Bausteine | sich Aufbau oder Abläufe ändern |
| [DOMAIN.md](DOMAIN.md) | Zweck, Leitplanken L1–L8, Glossar, Fachregeln | sich Fachregeln ändern |
| [DECISIONS.md](DECISIONS.md) | Entscheidungen mit ursprünglichen IDs (D, E, E-…, ANNAHMEN-Auswahl), ADRs; Karte der Archiv-IDs | eine Entscheidung fällt oder eine Festlegung entsteht |
| [ROADMAP.md](ROADMAP.md) | Stand, offene Entscheidungen, Arbeitspunkte, Befunde, Startprompt | am Ende jeder Session (`/handoff`) |
| [deploy/unraid/README.md](deploy/unraid/README.md) | Betrieb: Einrichtung, Module, Jobs, Störungen, Sicherung, Rückrollen | sich der Betrieb ändert |
| `docs/archiv/` | Spezifikation, Umsetzungsplan, Modulpläne, ANNAHMEN, Hand-off, Änderungsprotokoll, Mockup, Refactoring-Analyse – unverändert, historisch | nie; nur lesen |

Jeder Inhalt steht an genau einer Stelle; andere Dokumente verweisen darauf. Das Änderungsprotokoll ist das Git-Log.

## Rangfolge bei Widersprüchen

1. Anweisung des Nutzers.
2. [DECISIONS.md](DECISIONS.md) und [DOMAIN.md](DOMAIN.md).
3. Der Code als Ist-Zustand. Weicht er von 2 ab, ist das ein Befund: melden, nicht still angleichen.
4. Das Archiv. Es gilt nur, soweit DECISIONS darauf verweist; die Spezifikation beschreibt teils Veraltetes (Celery, Redis, MinIO, Claude API).

Für Oberfläche und Verhalten gilt das Frontend in `frontend/`; das Mockup im Archiv wird nicht mehr gepflegt.

## Arbeitsregeln

- **Leitplanken L1–L8** ([DOMAIN.md](DOMAIN.md) 2) gelten für Backend und Frontend.
- **Das Sprachmodell liest, Python rechnet, der Mensch prüft** (ADR-01): keine Berechnung und keine Fachentscheidung im Prompt; neue Regeln als Parameter mit Schranken in `rules/domain`.
- **Schichten:** `api.py` → `service.py` → `domain/` (rein). Genau eine Zugriffsregel je Route. Typen im Frontend aus OpenAPI (`pnpm run api:types`), keine handgeschriebenen DTOs. Datenbank nur über Alembic. Einzelheiten: README „Änderungen an der API“.
- **Kosten:** Bezahlte Auswertungen über OpenRouter nur nach Freigabe des Nutzers je Lauf. Tests und lokale Stacks ohne `EMPRISE_OPENROUTER_API_KEY`.
- **Git:** Commit und Push nur auf Anweisung, dann auf `main`, nach Thema getrennt.
- **Dokumentation:** Neue Entscheidungen und Festlegungen in DECISIONS, Stolperstellen in README, Betrieb in `deploy/unraid/README.md`, Stand nur in ROADMAP. Ein Plan für ein neues Modul oder einen größeren Umbau entsteht als `docs/PLAN_<Name>.md` mit Selbstprüfung; bei der Umsetzung gehen seine Entscheidungen nach DECISIONS, danach kommt er ins Archiv. Verweise im Code auf archivierte IDs („Spez. 5.3.1“, „PLAN_AN5 7.4“, „ANNAHMEN PU12“) bleiben gültig; neue Verweise zeigen auf DECISIONS oder DOMAIN.

## Sprache

Kommunikation und Dokumente auf Deutsch. Bezeichner im Backend englisch (Glossar in [DOMAIN.md](DOMAIN.md) 3), im Frontend deutsch für Komponenten; Oberfläche Französisch führend, Deutsch zusätzlich (D7).

## Am Ende einer Session

Der Befehl `/handoff` ([.claude/skills/handoff/SKILL.md](.claude/skills/handoff/SKILL.md)) schreibt ROADMAP fort, trägt neue Entscheidungen in DECISIONS ein und pflegt das Memory. Der Nutzer ruft ihn auf; nach umfangreichen Änderungen oder Ergebnissen, die nur im Chat stehen, ihn vorschlagen.
