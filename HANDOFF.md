# Hand-off für die nächste Session

> **Stand:** 13.09.2026 · **Letzte Session:** Prüfung der Backend-Spezifikation, Umsetzungsplan in Modulen, Einrichtung der Session-Übergabe, erster Hand-off
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md).

---

## 1. Aktueller Stand

- **Mockup** ([Hauskonfigurator.jsx](Hauskonfigurator.jsx), [emprise.html](emprise.html)): fertig und am 13.09.2026 durchgeklickt. Korridor, Abstände, Begrenzung und Formularprüfung stimmen mit Spezifikation 11.2 überein. `emprise.html` ist auf dem Stand der JSX.
- **Spezifikation** ([BACKEND_SPEZIFIKATION.md](BACKEND_SPEZIFIKATION.md)): unverändert. Die Prüfung ergab Korrekturbedarf (Abschnitt 4), noch nicht eingearbeitet.
- **Umsetzungsplan** ([UMSETZUNGSPLAN.md](UMSETZUNGSPLAN.md)): neu, selbst geprüft (Kapitel 10). **Status: Vorschlag, vom Nutzer noch nicht freigegeben.** Bis zur Freigabe gilt Kapitel 14 der Spezifikation.
- **Code:** noch keiner für Backend oder produktives Frontend.
- **Git:** noch kein Repository.
- **Session-Übergabe:** Anweisungen in [CLAUDE.md](CLAUDE.md), Befehl `/handoff` in [.claude/skills/handoff/SKILL.md](.claude/skills/handoff/SKILL.md).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

**Rückmeldung zur Spezifikation (Kernaussagen):**
- Fachlich sorgfältig; das Hauptproblem ist der Umfang von Version 1 (sechs Teilprodukte) und die Reihenfolge: Die erste Übergabe an das Büro kam erst in M9.
- Engpass ist die Datenpflege (Regelwerke je Gemeinde, Typmodelle, Preise, RE2020-Gutachten), nicht der Code.
- Geschäftsfrage offen: Bietet das Büro Honorar oder Bauleistung an? → Entscheidung D8.

**Erklärung der Kette Kataster/PLU → Webseite:** Inhaltlich jetzt in UMSETZUNGSPLAN.md 3.1–3.5 festgehalten.

**Auftrag des Nutzers für den Plan:** Funktionen nacheinander so umsetzen, dass jede allein produktiv nutzbar ist; Schwerpunkt IT-Infrastruktur; danach Selbstprüfung auf Logikfehler und Alternativen.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Umsetzungsplan freigeben (ganz, teilweise, mit Änderungen)? | UMSETZUNGSPLAN.md |
| 1 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 1 | D1 | Einzugsgebiet und Pilotgemeinden | Plan 9 |
| 2 | D3 / E1 | Hosting-Anbieter (nach Proof of Concept) | Plan 6.4, Spez. 16 |
| 2 | D4, D5, D6 | Anmeldung Mitarbeitende, Betriebsverantwortung, Datenschutzrolle Emprise ↔ Büro | Plan 9 |
| 3 | D2, D7, D9, D10 und E2–E12 | Übrige | Plan 9, Spez. 16 |
| 3 | – | Sessionbeginn: große Dokumente wie jetzt nur kapitelweise lesen oder immer vollständig (grob 130.000 Tokens je Session)? Vom Nutzer noch nicht beantwortet | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 Korrekturen an der Spezifikation (aus der Prüfung vom 13.09.2026)

| Nr. | Befund | Stelle | Im Plan gelöst? |
|---|---|---|---|
| S1 | Ligne-Neigung `atan(2,8/4,0)` = 34,99° < 35° → ohne Winkeltoleranz gesperrt | Spez. 11.3, Anhang C | ja, Plan 3.7 |
| S2 | Firstrichtungstest mit Plateau sinnlos (Flachdach hat keinen First) | Spez. 11.2, D7 | ja, Plan 3.8 |
| S3 | „Gespeicherte Konfigurationen sind immer auswahlgültig“ stimmt nicht → Neuprüfung beim Absenden | Spez. 5.10.2 Punkt 1 | ja, Plan 3.10 |
| S4 | Zulässigkeit mit Einzelabweichungen sperrt Typen fälschlich, wenn nur zwei Gruppen gemeinsam passen | Spez. 5.4.6 | teilweise, Plan 3.8; automatische Erkennung zusammenwirkender Gruppen fehlt noch |
| S5 | Zustände für E-Mail-Bestätigung und `dossier_failed` fehlen; Projekt- und Übergabestatus vermischt | Spez. 5.10.1, 5.10.2 | teilweise (Code vor Absenden, Plan 3.6); Zustandsautomat offen |
| S6 | Preise und RE2020-Bewertungen an Typversion gekoppelt | Spez. 4.3 | ja, Plan 3.7 |
| S7 | Rückfall auf Entwurfsregeln zeigt ungeprüfte Regeln beim Kunden | Spez. 4.4 | ja, Plan 3.4 |
| S8 | Traufhöhe an Wandaußenseite gemessen; viele PLU messen am Tiefpunkt der Traufe (bis ca. 0,35 m Unterschied) → Messpunkt als Regelparameter | Spez. 5.4.3 | nein |
| S9 | Queue `sandbox` „ohne Netzwerk“ braucht DB und Objektspeicher → „ohne Internetzugang“ | Spez. 7 | nein (Plan X2 formuliert richtig) |
| S10 | Löschrecht `DELETE /projects/{id}` kollidiert mit Aufbewahrung beim Büro | Spez. 6.3, 10.2 | nein |
| S11 | Paritätstest Lärche in M1 nur zufällig gleich gerundet (Pauschale vs. `finish_delta`) | Spez. 11.2 | teilweise, Plan 3.9 |
| S12 | Flachdach-Testmodell nennt „Firsthöhe“ statt Attikahöhe | Spez. 11.3 | nein |
| S13 | Spezifikation (~60.000 Tokens) aufteilen: Kerndokument plus Dokument je Modul; Anhang E auslagern | Spez. gesamt | nein |

Dazu die 20 Abweichungen aus Plan Kapitel 7, die nach Freigabe in die Spezifikation gehören.

### 4.2 Weitere Punkte

1. `git init` vor Beginn von R0 (Spez. 13 verlangt Commits je Meilenstein).
2. Einwilligung zur Datenweitergabe fehlt im Mockup (bekannt, Spez. Anhang E.2 M10).
3. Mit „prüfen“ markierte Angaben im Plan (Anbieter, Procrastinate, Etalab-Rhythmus, Kartendienste) sind nicht gegen aktuelle Unterlagen abgeglichen.
4. Befehl `/handoff` in der neuen Session testen: Erscheint er als Befehl, und startet er nicht von selbst (`disable-model-invocation`)? Bisher ungetestet.

## 5. Empfohlener nächster Schritt

1. Nutzer entscheidet über den Plan und D8, D1.
2. Danach: Spezifikation überarbeiten (Plan Kapitel 7 und Tabelle 4.1 einarbeiten, Kapitel 14 durch Releases ersetzen, AGENTS.md-Rangfolge anpassen).
3. Dann R0: `git init`, Proof of Concept Hosting (Plan 6.4), Gerüst P.

## 6. Hinweise und Stolperstellen

- Große Dokumente kapitelweise lesen: Überschriften mit Grep `^#{2,3} ` finden. Spezifikation ~1.600 Zeilen, Plan ~670 Zeilen.
- `emprise.html` nie von Hand ändern; Artefakt-URLs und Ablauf in AGENTS.md.
- Mockup im Browser prüfen: `file:///C:/Users/sarah/Documents/Codex_Projet/building-configurator/emprise.html` im Browser-Bereich öffnen. Screenshots liefen in eine Zeitüberschreitung; Bedienung und Auslesen per `find` und `javascript_tool` funktionierten. Typkarten sind keine `<button>`, sondern Elemente mit `role=button`; die Kontaktprüfung meldet Fehler erst beim Klick auf „Vorentwurf zur Prüfung übergeben“.
- Der erste Hand-off lief von Hand nach `SKILL.md`, weil der in derselben Session angelegte Befehl dort nicht als Befehl verfügbar war.
- Der Ordner heißt `Codex_Projet`; `AGENTS.md` ist die gemeinsame Anweisung für mehrere Agenten, `CLAUDE.md` bindet sie ein und ergänzt Claude-spezifische Abläufe.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den neuesten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen und nenne die offenen Entscheidungen, die du von mir brauchst, bevor wir weitermachen.
```
