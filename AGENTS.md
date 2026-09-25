# Emprise – Hauskonfigurator

Webplattform für Bauinteressenten in Frankreich: Parzelle wählen, die Vorgaben des Bebauungsplans (PLU) werden zu harten Grenzen, darin wird ein Haus konfiguriert (Typ, Ausstattungslinie, Optionen, Lage). Ergebnis ist kein Kauf, sondern ein unverbindlicher Vorentwurf, den ein Architekturbüro prüft und in ein Angebot überführt. „Emprise“ ist eine eigene Marke, getrennt vom Büro.

## Stand (25.09.2026)

Mockup, Fachdokumentation, Spezifikation und Umsetzungsplan liegen vor. Umgesetzt: R0 (ohne Auslieferung auf Unraid), G1–G3, A, H1, H2, H3 und V; damit ist der Hauskonfigurator (R2) fachlich vollständig. Daneben ist ein zweites Produkt beauftragt: „Emprise Analyse“ – G1–G3 als eigenständige Web-App für Architekten ([docs/PLAN_ANALYSE.md](docs/PLAN_ANALYSE.md)); davon sind AN0 (Produktschnitt) und AN1 (Parzelle als Datei – auch PDF – oder Zeichnung einbringen, Kanten einordnen, Projekte am Konto) umgesetzt, AN2–AN6 stehen aus. Einzelheiten, offene Entscheidungen und nächster Schritt: [HANDOFF.md](HANDOFF.md).

## Dokumente

| Datei | Inhalt | Lesen, wenn … |
|---|---|---|
| [HANDOFF.md](HANDOFF.md) | Momentaufnahme: Stand, offene Entscheidungen und Arbeitspunkte, nächster Schritt | zu Beginn jeder Session |
| [AENDERUNGEN.md](AENDERUNGEN.md) | Änderungsprotokoll je Session, neueste zuerst | zu Beginn jeder Session (nur neuester Eintrag) |
| [BACKEND_SPEZIFIKATION.md](BACKEND_SPEZIFIKATION.md) | Maßgebliche Vorgabe für das Backend: Leitplanken, Datenmodell, Abläufe, API, Tests, Meilensteine, offene Entscheidungen E1–E12, Prüfprotokoll mit offenen Korrekturen (Anhang E.4) | vor Backend-Arbeit kapitelweise nach Kapitel 0 Punkt 1 |
| [UMSETZUNGSPLAN.md](UMSETZUNGSPLAN.md) | Zuschnitt in Module, Releases, Technik je Modul, IT-Infrastruktur, Abweichungen von der Spezifikation (Kapitel 7), Entscheidungen D1–D18, Prüfprotokoll | vor Planung oder Beginn eines Moduls; der Modulabschnitt nennt die nötigen Spezifikationskapitel |
| `docs/PLAN_<Modul>.md` | Pläne der Module [G3](docs/PLAN_G3_BAURAHMEN.md), [H1](docs/PLAN_H1_HAUSKATALOG.md), [A](docs/PLAN_A_ANFRAGE.md), [H2](docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md), [H3](docs/PLAN_H3_KONFIGURATION_KOSTEN.md), [V](docs/PLAN_V_VORENTWURF_UEBERGABE.md): fachliche Festlegungen, Architektur, Arbeitsschritte, Prüfprotokoll | Arbeit am jeweiligen Modul |
| [docs/PLAN_ANALYSE.md](docs/PLAN_ANALYSE.md) | Zweites Produkt „Emprise Analyse“: eigenständige Web-App für Architekten aus G1–G3 (Parzelle und PLU hochladen, Baurahmen, Nutzfläche, CAD-Ausgabe); AN0 und AN1 umgesetzt, Modulplan [AN1](docs/PLAN_AN1_PARZELLE.md) | Arbeit am Analyse-Produkt oder am Produktschnitt |
| [docs/ANNAHMEN.md](docs/ANNAHMEN.md) | Festlegungen und Abweichungen der Umsetzung, je Modul ein Abschnitt mit IDs (A, G, RW, BR, H, AF, HP, HK, VU, PS, UP) | vor Code-Arbeit den Abschnitt des Moduls; neue Annahmen hier eintragen |
| [README.md](README.md) | Aufbau, lokal starten, Prüfbefehle, Regeln für API-Änderungen, Stolperstellen | vor Code-Arbeit |
| [docs/BETRIEB.md](docs/BETRIEB.md) | Module im Betrieb (Flags, Migrationen, Jobs, ausgehender Zugang), Ausliefern, Rückrollen, Zugang, Mail, Wiederherstellung, Sicherheitsvorfall, Störungen je Modul | Betrieb, Störungen, Freischalten |
| [deploy/unraid/README.md](deploy/unraid/README.md) | Betrieb bis zur Beta auf Unraid: Reverse Proxy, Authentik, Einrichtung, Aktualisieren, Sicherung, Überwachung, Module | Auslieferung, Arbeit an `deploy/unraid` |
| [infra/README.md](infra/README.md) | Anforderungen an einen späteren verwalteten Anbieter, Umgebungsvariablen, Proof-of-Concept-Liste | Wechsel des Hostings |
| [Hauskonfigurator.jsx](Hauskonfigurator.jsx) | Mockup als einzelne React-Datei; Daten als Konstanten am Dateianfang | Frontend-Arbeit; Zuordnung zum Backend in Spezifikation 8.1 |
| [emprise.html](emprise.html) | Aus der JSX erzeugte, eigenständige Seite | nie von Hand ändern, nur neu erzeugen |
| [Dokumentation.html](Dokumentation.html) | Beschreibung des Mockups (Stand 13.09.2026): Seitenaufbau, Ableitung der Regeln, Volumetrie, Material und Preise, Beispiel-Mail, Gestaltung | fachliche Logik oder Gestaltung des Mockups |
| [tools/build-mockup.cjs](tools/build-mockup.cjs) | Erzeugt `emprise.html` aus der JSX | nach Änderungen am Mockup |
| [tools/sync-check-texts.cjs](tools/sync-check-texts.cjs) | Übernimmt die Texte der Prüfungen aus dem Frontend in die Übersetzungen des Backends (Dossier-PDF) | nach Änderungen an diesen Texten (README „Änderungen an der API“) |
| `C:\Users\sarah\Downloads\mockup-prompt.md` (außerhalb des Projekts) | Ursprünglicher Auftrag für das Mockup mit Beispieldaten und Regeln | nur zur Herkunft, falls noch vorhanden |

Jeder Inhalt steht an einer Stelle; andere Dokumente verweisen darauf: Stand nur in HANDOFF, Entscheidungen in Plan 9 und Spez. 16, Festlegungen in ANNAHMEN, Betrieb in BETRIEB, Stolperstellen in README, offene Spezifikationskorrekturen in Spez. Anhang E.4.

## Rangfolge bei Widersprüchen

1. Anweisung des Nutzers
2. `BACKEND_SPEZIFIKATION.md` – auch dort, wo sie Fehler des Mockups korrigiert (Anhang E.2)
3. `Hauskonfigurator.jsx` für Verhalten und Aussehen der Oberfläche
4. `Dokumentation.html` – beschreibt den Stand des Mockups und wird nicht automatisch nachgezogen

Für Zuschnitt, Reihenfolge und Infrastruktur beauftragter Module (HANDOFF 1) gilt `UMSETZUNGSPLAN.md` vor Kapitel 14 der Spezifikation. Abweichungen stehen in Plan Kapitel 7 und `docs/ANNAHMEN.md`.

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
