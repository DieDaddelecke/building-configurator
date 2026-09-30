---
name: handoff
description: Bereitet die Übergabe an eine neue Session vor – zieht betroffene Dokumente nach, trägt Entscheidungen in DECISIONS.md ein, schreibt ROADMAP.md fort und aktualisiert das Memory. Nur auf ausdrücklichen Aufruf mit /handoff.
disable-model-invocation: true
---

# Hand-off vorbereiten

**Ziel:** Eine neue Session kann ohne diesen Gesprächsverlauf weiterarbeiten. Alles, was nur im Chat steht – Ergebnisse, Entscheidungen, offene Fragen, verworfene Wege – steht danach in Dateien oder im Memory.

**Eine Quelle je Inhalt** (AI_CONTEXT.md, Dokumententabelle): ROADMAP.md trägt Stand, offene Entscheidungen, Arbeitspunkte und nächsten Schritt und wird fortgeschrieben. Dauerhaftes gehört an seinen festen Ort und steht in ROADMAP höchstens als Verweis: Entscheidungen und Festlegungen → DECISIONS.md, Fachregeln → DOMAIN.md, Aufbau → ARCHITECTURE.md, Stolperstellen und Befehle → README.md, Betrieb → deploy/unraid/README.md. Das Archiv (`docs/archiv/`) wird nicht geändert. Ein Änderungsprotokoll gibt es nicht mehr; das ist das Git-Log.

Sprache: Deutsch. Datum: heutiges Datum absolut (TT.MM.JJJJ). Nichts erfinden; Unklares als offene Frage in ROADMAP.md 3 aufnehmen.

## 1. Bestandsaufnahme

1. Gesprächsverlauf durchgehen und notieren:
   - geänderte, neue, gelöschte Dateien
   - Entscheidungen des Nutzers (mit vorhandener ID aus DECISIONS, sonst neue)
   - Ergebnisse, die nur im Chat stehen (Prüfungen, Erklärungen, Messungen)
   - offene Fragen an den Nutzer, abgebrochene oder verschobene Arbeiten
   - Rückmeldungen des Nutzers zur Arbeitsweise
2. `ROADMAP.md` und die betroffenen Abschnitte von `DECISIONS.md` lesen.
3. Dateistand prüfen: `git status`, `git diff --stat` und `git log --oneline` seit dem Stand in ROADMAP 1.

## 2. Dokumente nachziehen

Nur handeln, wenn der Fall eingetreten ist:

| Wenn … | dann … |
|---|---|
| Entscheidung getroffen | In `DECISIONS.md`: offene Zeile als entschieden markieren (Datum, Ergebnis) oder neu eintragen – Architektur, Betrieb und Arbeitsweise als ADR in Abschnitt 1, Fachfestlegungen mit neuer ID `F01` ff. in Abschnitt 4. Überholtes mit „aufgehoben durch …“ kennzeichnen, nicht löschen |
| Fachregel geändert | `DOMAIN.md` |
| Aufbau, Dienste, Module oder Abläufe geändert | `ARCHITECTURE.md` |
| Neue Stolperstelle, neuer Prüf- oder Startbefehl | `README.md` |
| Neuer Betriebsschritt, neue Migration, neues Flag, neuer Job, neue Störung | `deploy/unraid/README.md` (Modultabelle in Abschnitt 10, Abschnitt des Moduls) |
| Datei neu, umbenannt oder gelöscht | Dokumententabelle in `AI_CONTEXT.md`, Aufbau in `README.md` |
| Arbeitsweise geändert | `AI_CONTEXT.md` (für alle Agenten) bzw. `CLAUDE.md` (nur Claude) |
| Punkt aus ROADMAP 3 oder 4 erledigt | Dort streichen; Ergebnis an seinen dauerhaften Ort |

## 3. `ROADMAP.md` fortschreiben

Gliederung und Nummern beibehalten (andere Dokumente verweisen auf „ROADMAP 3“ usw.). Kopf ohne Nummer: Stand-Datum und Thema der letzten Session. Danach:

1. Stand (5–10 Punkte): Git-Stand, Bereiche, Tests, Kosten
2. Nächster Schritt
3. Offene Entscheidungen des Nutzers, priorisiert, mit Verweis
4. Offene Arbeitspunkte, priorisiert, mit Datei und Abschnitt; offene Punkte der vorigen Fassung übernehmen
5. Befunde, die nicht umgesetzt wurden
6. Hinweise, die nur für die nächsten Sessions gelten; dauerhafte Stolperstellen in README
7. Startprompt als Codeblock

Ergebnisse der Session, die nur im Chat standen, kommen an ihren Ort (Stand, Arbeitspunkt, DECISIONS, README). Auf Dokumente und Abschnitte verweisen statt Inhalte zu kopieren; höchstens etwa 150 Zeilen.

## 4. Memory aktualisieren

Memory-Verzeichnis und Dateiformat stehen im Systemprompt der Session (Abschnitt „Memory“); Index ist `MEMORY.md`.

- **Ablegen**, was nicht aus den Projektdateien hervorgeht: Vorlieben und Rückmeldungen des Nutzers zur Arbeitsweise (mit **Why** und **How to apply**), Hintergründe von Entscheidungen, externe Verweise.
- **Nicht ablegen:** Projektstand, Dateiinhalte, erledigte Aufgaben – das steht in ROADMAP und im Git-Log.
- Vorhandene Einträge prüfen: aktualisieren statt doppeln, überholte oder falsche löschen.
- `MEMORY.md`: eine Zeile je Datei, keine Inhalte.

## 5. Prüfen

1. Alle in ROADMAP, AI_CONTEXT und CLAUDE.md genannten Dateien existieren; relative Links lösen auf.
2. Abschnittsverweise stimmen (Überschrift per Grep).
3. Datum überall gleich; ROADMAP widerspricht DECISIONS nicht.
4. Keine offenen Punkte verloren: ROADMAP 3, 4 und 5 gegen `git show HEAD:ROADMAP.md` abgleichen. Jeder Punkt ist erledigt, weiter offen oder an seinen dauerhaften Ort verschoben.
5. Jeder Verweis („siehe …“) zeigt auf eine Stelle, an der der Inhalt wirklich steht.

## 6. Abschluss

Dem Nutzer kurz melden: aktualisierte Dateien, Memory-Änderungen, was bewusst offen blieb, Startprompt. Keine Commits, keine Veröffentlichungen und keine Löschungen außerhalb des Memory ohne Zustimmung.
