# Emprise – Hauskonfigurator

Webplattform für Bauinteressenten in Frankreich: Parzelle wählen, die Vorgaben des Bebauungsplans (PLU) werden zu harten Grenzen, darin wird ein Haus konfiguriert (Typ, Ausstattungslinie, Optionen, Lage). Ergebnis ist kein Kauf, sondern ein unverbindlicher Vorentwurf, den ein Architekturbüro prüft und in ein Angebot überführt. „Emprise“ ist eine eigene Marke, getrennt vom Büro.

## Stand (18.09.2026)

Details, offene Punkte und nächster Schritt: [HANDOFF.md](HANDOFF.md).

- Mockup und Fachdokumentation des Mockups: fertig.
- Umsetzungsplan: als Ganzes nicht freigegeben; R0 (Modul P), G1, G2, G3 und H1 (Backend) wurden daraus beauftragt. D1 (bis zur Beta), D2 (G1 intern), D3, D4, D11 (G2 automatisch als Simulation, Büro prüft erst bei Anfrage) und D14 (Modul A bleibt Notausgang neben H2–V) sind entschieden (Plan Kapitel 9).
- R0 Plattform: anbieterunabhängiger Teil umgesetzt und getestet; Betrieb bis zur Beta auf Unraid mit Authentik vorbereitet (`deploy/unraid/`), auf dem Server noch nicht ausgeliefert. Repository privat auf GitHub mit CI.
- G1–G3 (Grundstück, Regelwerk, Baurahmen): umgesetzt, getestet, lokal intern freigeschaltet, gepusht. G1 zusätzlich um Weg E ergänzt (freies Zeichnen ohne Kataster, ANNAHMEN G26–G30); G2 ohne Schlüssel der Claude API noch keine echte Auswertung (ANNAHMEN RW01–RW27); G3 über 200 echte Parzellen ohne Fehler geprüft (ANNAHMEN BR01–BR15, [docs/PLAN_G3_BAURAHMEN.md](docs/PLAN_G3_BAURAHMEN.md)).
- H1 Hauskatalog: Backend umgesetzt und getestet (`backend/app/catalog`, Datenmodell, XLSX/DXF-Import, Katalogpflege-API unter `/admin/catalog`, kein Kundenschritt), gepusht, CI grün (ANNAHMEN H01–H09, [docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md)). Katalogpflege-Oberfläche im Frontend und die fünf Platzhalter-Typen als echte XLSX/DXF-Dateien noch offen.
- Spezifikation: Korrekturen aus der Prüfung vom 13.09.2026 und Anpassung an D11 noch nicht eingearbeitet.

## Dokumente

| Datei | Inhalt | Lesen, wenn … |
|---|---|---|
| [HANDOFF.md](HANDOFF.md) | Momentaufnahme: Stand, offene Entscheidungen und Arbeitspunkte, nächster Schritt, Stolperstellen | zu Beginn jeder Session |
| [AENDERUNGEN.md](AENDERUNGEN.md) | Änderungsprotokoll je Session, neueste zuerst | zu Beginn jeder Session (neuester Eintrag) |
| [BACKEND_SPEZIFIKATION.md](BACKEND_SPEZIFIKATION.md) | Maßgebliche Vorgabe für das Backend: Leitplanken, Datenmodell, Abläufe, API, Tests, Meilensteine, offene Entscheidungen, Prüfprotokoll | vor jeder Backend-Arbeit; Kapitel 0 regelt die Arbeitsweise |
| [UMSETZUNGSPLAN.md](UMSETZUNGSPLAN.md) | Zuschnitt in Module, Releases, technische Umsetzung je Modul, IT-Infrastruktur, Abweichungen von der Spezifikation (Kapitel 7), offene Entscheidungen D1–D10, Prüfprotokoll | vor Planung oder Beginn eines Moduls; welche Spezifikationskapitel ein Modul braucht, steht im Modulabschnitt |
| [README.md](README.md) | Aufbau des Repositorys, lokal starten, Prüfbefehle, Regeln für API-Änderungen | vor Code-Arbeit |
| [docs/PLAN_G3_BAURAHMEN.md](docs/PLAN_G3_BAURAHMEN.md) | Plan des Moduls G3: fachliche Festlegungen, Architektur, Arbeitsschritte, Prüfprotokoll | Arbeit am Baurahmen |
| [docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md) | Plan des Moduls H1: fachliche Festlegungen, Architektur, Arbeitsschritte, Prüfprotokoll | Arbeit am Hauskatalog |
| [docs/ANNAHMEN.md](docs/ANNAHMEN.md) | Festlegungen und Abweichungen in der Umsetzung (Spez. 0 Punkt 7), je Modul ein Abschnitt | vor Code-Arbeit; neue Annahmen hier eintragen |
| [docs/BETRIEB.md](docs/BETRIEB.md) | Betriebsanleitung: Ausliefern, Rückrollen, Zugang, Jobs, Mail, Wiederherstellung, Sicherheitsvorfall | Betrieb, Störungen |
| [deploy/unraid/README.md](deploy/unraid/README.md) | Betrieb bis zur Beta auf Unraid: Reverse Proxy, Authentik, Einrichtung, Aktualisieren, Sicherung, Überwachung | Auslieferung, Arbeit an `deploy/unraid` |
| [infra/README.md](infra/README.md) | Anforderungen an einen späteren verwalteten Anbieter, Umgebungsvariablen, Proof-of-Concept-Liste | Wechsel des Hostings |
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

Für Zuschnitt, Reihenfolge und Infrastruktur beauftragter Module (bisher R0, G1, G2, G3, H1) gilt `UMSETZUNGSPLAN.md` vor Kapitel 14 der Spezifikation. Abweichungen stehen in `docs/ANNAHMEN.md`.

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
