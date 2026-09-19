---
name: handoff
description: Bereitet die Übergabe an eine neue Session vor – zieht betroffene Projektdokumente nach, schreibt AENDERUNGEN.md und HANDOFF.md fort und aktualisiert das Memory. Nur auf ausdrücklichen Aufruf mit /handoff.
disable-model-invocation: true
---

# Hand-off vorbereiten

**Ziel:** Eine neue Session kann ohne diesen Gesprächsverlauf weiterarbeiten. Alles, was nur im Chat steht – Ergebnisse, Entscheidungen, offene Fragen, verworfene Wege – steht danach in Dateien oder im Memory.

**Eine Quelle je Inhalt** (AGENTS.md unter der Dokumententabelle): HANDOFF.md ist nur Momentaufnahme und wird jedes Mal neu geschrieben. Dauerhaftes gehört an seinen festen Ort und steht in HANDOFF höchstens als Verweis: Stolperstellen → README.md, Betrieb je Modul → docs/BETRIEB.md, Festlegungen → docs/ANNAHMEN.md, offene Spezifikationskorrekturen → Spezifikation Anhang E.4, Entscheidungen → Plan 9 bzw. Spez. 16.

Sprache: Deutsch. Datum: heutiges Datum absolut (TT.MM.JJJJ). Nichts erfinden; Unklares als offene Frage in HANDOFF.md aufnehmen.

## 1. Bestandsaufnahme

1. Gesprächsverlauf durchgehen und notieren:
   - geänderte, neue, gelöschte Dateien
   - Entscheidungen des Nutzers (mit Nummer aus Spezifikation 16 oder Umsetzungsplan 9, falls vorhanden)
   - Ergebnisse, die nur im Chat stehen (Prüfungen, Erklärungen, Messungen)
   - offene Fragen an den Nutzer, abgebrochene oder verschobene Arbeiten
   - Rückmeldungen des Nutzers zur Arbeitsweise
2. `HANDOFF.md`, neuesten Eintrag in `AENDERUNGEN.md` und `AGENTS.md` lesen.
3. Dateistand prüfen: Dateien mit Änderungsdatum auflisten (ohne `node_modules`). Ist der Ordner ein Git-Repository: `git status` und `git diff --stat`.

## 2. Projektdokumente nachziehen

Nur handeln, wenn der Fall eingetreten ist:

| Wenn … | dann … |
|---|---|
| `Hauskonfigurator.jsx` geändert | `node tools/build-mockup.cjs` ausführen; prüfen, ob `Dokumentation.html` geänderte Zahlen oder Abläufe nennt, und nachziehen; die Artefakte laut `AGENTS.md` erst nach Zustimmung des Nutzers aktualisieren |
| Entscheidung getroffen | In der Entscheidungstabelle (Spezifikation 16 bzw. Umsetzungsplan 9) als entschieden markieren: Datum, Ergebnis; betroffene Kapitel anpassen |
| Umsetzungsplan freigegeben oder Abweichungen übernommen | Status im Kopf von `UMSETZUNGSPLAN.md`, Rangfolge und Stand in `AGENTS.md` anpassen |
| Datei neu, umbenannt oder gelöscht | Dokumententabelle in `AGENTS.md` |
| Code-Stand geändert | Stand in `HANDOFF.md`; `AGENTS.md` nur, wenn ein Modul fertig wird; neue Annahmen in `docs/ANNAHMEN.md` (Spezifikation 0, Ort nach Plan 4.1) |
| Neue Stolperstelle, neuer Betriebsschritt, neue Spezifikationskorrektur | README „Stolperstellen“, BETRIEB (Modultabelle in Abschnitt 1), Spez. Anhang E.4 |
| Arbeitsweise geändert | `CLAUDE.md` (Claude-spezifisch) bzw. `AGENTS.md` (für alle Agenten) |
| Punkt aus `HANDOFF.md` 4 erledigt | Dort streichen, im Protokolleintrag nennen |

Den Abschnitt „Stand“ in `AGENTS.md` auf höchstens drei Sätze halten; Details gehören in `HANDOFF.md`.

## 3. `AENDERUNGEN.md` fortschreiben

Neuen Eintrag **oben** unter der Einleitung einfügen, frühere Einträge nicht ändern:

```
## TT.MM.JJJJ – <Thema der Session>

**Commits** – Kennungen (sobald vorhanden); die Dateiliste liefert `git show --stat`
**Neu / Geändert / Gelöscht** – knapp, was und warum; Dateien nur nennen, wo es nicht aus dem Commit hervorgeht (Dokumente, Nicht-Committetes)
**Entschieden** – Nr. – Ergebnis
**Ohne Dateiänderung** – Ergebnisse nur aus dem Chat, mit Verweis, wo sie jetzt stehen
**Unverändert** – nur, wenn es eine Aussage trägt (z. B. bewusst nicht angefasst)
**Memory** – angelegt, geändert, gelöscht
```

Leere Rubriken weglassen.

## 4. `HANDOFF.md` neu schreiben

Vollständig ersetzen – Momentaufnahme, keine Historie. Feste Gliederung:

1. Kopf: Stand-Datum, Thema der letzten Session, Hinweis auf `AENDERUNGEN.md`
2. Aktueller Stand (5–10 Punkte, je Dokument oder Bereich)
3. Ergebnisse der letzten Session, die nur im Chat standen
4. Offene Entscheidungen des Nutzers, priorisiert, mit Verweis auf die Tabelle
5. Offene Arbeitspunkte, priorisiert, mit Datei und Kapitel; noch offene Punkte aus der vorigen Fassung übernehmen
6. Empfohlener nächster Schritt
7. Hinweise nur zu dieser Session; dauerhafte Stolperstellen in README.md eintragen
8. Startprompt für die neue Session als Codeblock

Höchstens etwa 120 Zeilen. Auf Dokumente und Kapitel verweisen statt Inhalte zu kopieren.

## 5. Memory aktualisieren

Memory-Verzeichnis und Dateiformat stehen im Systemprompt der Session (Abschnitt „Memory“); Index ist `MEMORY.md`.

- **Ablegen**, was nicht aus den Projektdateien hervorgeht: Vorlieben und Rückmeldungen des Nutzers zur Arbeitsweise (mit **Why** und **How to apply**), Hintergründe von Entscheidungen, externe Verweise.
- **Nicht ablegen:** Projektstand, Dateiinhalte, erledigte Aufgaben – das steht in `HANDOFF.md` und `AENDERUNGEN.md`.
- Vorhandene Einträge prüfen: aktualisieren statt doppeln, überholte oder falsche löschen.
- `MEMORY.md`: eine Zeile je Datei, keine Inhalte.

## 6. Prüfen

1. Alle in `HANDOFF.md`, `AGENTS.md`, `CLAUDE.md` und im neuen Protokolleintrag genannten Dateien existieren.
2. Kapitelverweise stimmen (Überschrift per Grep).
3. Datum überall gleich; Stand in `AGENTS.md` widerspricht `HANDOFF.md` nicht.
4. Keine offenen Punkte verloren: die Abschnitte 3 (Entscheidungen), 4 (Arbeitspunkte) und 6 (Hinweise) gegen `git show HEAD:HANDOFF.md` abgleichen. Jeder Punkt ist erledigt (im Protokoll), weiter offen oder an seinen dauerhaften Ort verschoben.
5. Jeder Verweis auf eine Liste oder einen Inhalt in einer anderen Datei („siehe …“) zeigt auf eine Stelle, an der er wirklich steht.

## 7. Abschluss

Dem Nutzer kurz melden: aktualisierte Dateien, Memory-Änderungen, was bewusst offen blieb, Startprompt. Keine Commits, keine Veröffentlichungen und keine Löschungen außerhalb des Memory ohne Zustimmung.
