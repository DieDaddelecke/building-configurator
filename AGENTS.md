# Emprise – Hauskonfigurator

Webplattform für Bauinteressenten in Frankreich: Parzelle wählen, die Vorgaben des Bebauungsplans (PLU) werden zu harten Grenzen, darin wird ein Haus konfiguriert (Typ, Ausstattungslinie, Optionen, Lage). Ergebnis ist kein Kauf, sondern ein unverbindlicher Vorentwurf, den ein Architekturbüro prüft und in ein Angebot überführt. „Emprise“ ist eine eigene Marke, getrennt vom Büro.

## Stand (13.09.2026)

Details, offene Punkte und nächster Schritt: [HANDOFF.md](HANDOFF.md).

- Klickbares Frontend-Mockup mit festen Beispieldaten: fertig.
- Fachdokumentation des Mockups: fertig.
- Backend: spezifiziert, noch kein Code.
- Umsetzungsplan in Modulen und Releases (R0–R2, Ausbau X1–X5) mit IT-Infrastruktur: Vorschlag, noch nicht freigegeben. Bis zur Freigabe gilt Kapitel 14 der Spezifikation; nächster Schritt nach Freigabe ist R0 mit Proof of Concept beim Hosting-Anbieter.
- Der Ordner ist noch kein Git-Repository.

## Dokumente

| Datei | Inhalt | Lesen, wenn … |
|---|---|---|
| [HANDOFF.md](HANDOFF.md) | Momentaufnahme: Stand, offene Entscheidungen und Arbeitspunkte, nächster Schritt, Stolperstellen | zu Beginn jeder Session |
| [AENDERUNGEN.md](AENDERUNGEN.md) | Änderungsprotokoll je Session, neueste zuerst | zu Beginn jeder Session (neuester Eintrag) |
| [BACKEND_SPEZIFIKATION.md](BACKEND_SPEZIFIKATION.md) | Maßgebliche Vorgabe für das Backend: Leitplanken, Datenmodell, Abläufe, API, Tests, Meilensteine, offene Entscheidungen, Prüfprotokoll | vor jeder Backend-Arbeit; Kapitel 0 regelt die Arbeitsweise |
| [UMSETZUNGSPLAN.md](UMSETZUNGSPLAN.md) | Zuschnitt in Module, Releases, technische Umsetzung je Modul, IT-Infrastruktur, Abweichungen von der Spezifikation (Kapitel 7), offene Entscheidungen D1–D10, Prüfprotokoll | vor Planung oder Beginn eines Moduls; welche Spezifikationskapitel ein Modul braucht, steht im Modulabschnitt |
| [Hauskonfigurator.jsx](Hauskonfigurator.jsx) | Mockup als einzelne React-Datei; Daten als Konstanten am Dateianfang | Frontend-Arbeit; Zuordnung zum Backend in Spezifikation 8.1 |
| [emprise.html](emprise.html) | Aus der JSX erzeugte, eigenständige Seite | nie von Hand ändern, nur neu erzeugen |
| [Dokumentation.html](Dokumentation.html) | Beschreibung des Mockups: Seitenaufbau, Ableitung der Regeln, Volumetrie, Material und Preise, Beispiel-Mail, Gestaltung (Farben, Schriften) | fachliche Logik oder Gestaltung des Mockups |
| [tools/build-mockup.cjs](tools/build-mockup.cjs) | Erzeugt `emprise.html` aus der JSX | nach Änderungen am Mockup |
| `C:\Users\sarah\Downloads\mockup-prompt.md` (außerhalb des Projekts) | Ursprünglicher Auftrag für das Mockup mit Beispieldaten und Regeln | nur zur Herkunft, falls noch vorhanden |

## Rangfolge bei Widersprüchen

1. Anweisung des Nutzers
2. `BACKEND_SPEZIFIKATION.md` – auch dort, wo sie Fehler des Mockups korrigiert (Anhang E.2)
3. `Hauskonfigurator.jsx` für Verhalten und Aussehen der Oberfläche
4. `Dokumentation.html` – beschreibt den Stand des Mockups und wird nicht automatisch nachgezogen

Die Leitplanken L1–L8 (Spezifikation 1.2) gelten auch für Änderungen am Frontend.

## Mockup ändern

1. `Hauskonfigurator.jsx` bearbeiten.
2. Einmalig `npm install --no-save esbuild`, danach `node tools/build-mockup.cjs`.
3. Veröffentlichte Artefakte aktualisieren. Aus einer neuen Session die URL mitgeben, sonst entsteht ein neues Artefakt:
   - Mockup: https://claude.ai/code/artifact/32deba67-7935-49f5-90af-181e05a23aee (Datei `emprise.html`)
   - Dokumentation: https://claude.ai/code/artifact/73ba0a48-1197-4d7c-8c8a-8ad1e6fe1576 (Datei `Dokumentation.html`)
4. Prüfen, ob `Dokumentation.html` betroffen ist; sie ist statisches HTML ohne Build und nennt konkrete Zahlen und Abläufe des Mockups.

## Sprache

Kommunikation und Dokumente auf Deutsch. Das Mockup verwendet deutsche Bezeichner; für das Backend gilt die Sprachregelung in Spezifikation Kapitel 0 und das Glossar in Kapitel 2.
