# Hand-off für die nächste Session

> **Stand:** 19.09.2026 · **Letzte Sessions:** H2 (Zulässigkeit und Implantation) geplant, umgesetzt, gepusht; danach die Dokumentation verdichtet (beide Einträge vom 19.09. in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Code-Stand `98fce8f` (H2), CI-Lauf 35427795221 grün. `7cecdb5` (Hand-off-Dokumente der H2-Session) ist lokal committet, nicht gepusht. **Nicht committet:** die Verdichtung der Dokumentation.
- **R0 Plattform:** anbieterunabhängiger Teil fertig; Unraid vorbereitet, nicht ausgeliefert (ANNAHMEN A1–A27).
- **G1–G3:** fertig, lokal intern freigeschaltet (G01–G30, RW01–RW27, BR01–BR15). G2 ohne Schlüssel der Claude API noch keine echte Auswertung.
- **H1 Hauskatalog:** Backend und Büro-Oberfläche `/buero/katalog` fertig (H01–H14). Bearbeiten `architect` und `catalog_admin`, `ops` liest. Offen: fünf echte Typdateien, XLSX-Vorlage (4.5).
- **A Anfrage:** fertig (AF01–AF12, BETRIEB 11), lokal intern für `architect` freigeschaltet (Flag `inquiry`); die Anfrage kennt noch **keine Konfiguration** (kommt mit V).
- **H2:** fertig (HP01–HP20, BETRIEB 12): `backend/app/configuration`, Migration 0009, Flag `configurator`, Route `/konfigurator` mit Typkarten (Gründe, Vorschläge), Lage ziehen und drehen, Schnellstellungen, Grenzschalter. Weg E und Grundstücke ohne Regeln laufen im freien Modus.
- **Hauskonfigurator (R2):** H1 und H2 da; **H3 (Linie, Optionen, Kosten) und V (Übergabe) fehlen**.
- **Tests:** Backend 362, Frontend 91, ruff, mypy, Typprüfung, Lint grün. Playwright lief lokal nicht.
- **Lokaler Stack `emprise`:** Migration 0009, Flag `configurator` für `architect`. Testdaten: erfundene Typen `demo_ligne`, `demo_plateau`, `demo_plateau_adapte` (`backend/tests/e2e_seed_types.py`), H1-Typen `ligne` v1 (veröffentlicht) und `plateau` v1 (Entwurf), Linie `confort`, Option `pv`, RE2020-Befund ligne/confort, Anfrage `EMP-2026-000001`.
- **Entscheidungen:** R0, G1, G2, G3, H1, A, H2 aus dem Umsetzungsplan beauftragt; D1–D4, D11, D14 entschieden; D12/D13 nach Empfehlung genommen, **nicht bestätigt**. **Spezifikation:** Korrekturen S1–S17 offen (Anhang E.4); seit 19.09. wird sie kapitelweise gelesen.

## 2. Ergebnisse der letzten Sessions, die nur im Chat standen

- **Auslegung des Auftrags (H2-Session):** „erstelle den hauskonfigurator“ heißt R2 (H1–V). Begonnen mit H2 (Plan, dann Umsetzung), H3 und V als fehlend benannt; der Nutzer widersprach nicht und wies Commit und Push an.
- **Nach Empfehlung genommen, nicht bestätigt:** D12, D13, Terrasse/Carport/Zufahrt erst in H3, kein `/buildable` (ANNAHMEN HP01–HP04). Browserprüfung und nicht Gesehenes: Plan H2 10.1 und 10.3.
- **Weiter gültig aus H1** (H10–H14, nicht bestätigt; **H2 liest diese Formate**): Eingang/Garagentor als `{edge, position}`, links/rechts der Fassadenrollen von der Straße aus, Linien und Optionen nur als neue Version änderbar.
- **Korrektur:** Der Abschlusstext der H2-Session nannte das H1-Frontend als offen; das stand nur in einer älteren HANDOFF-Fassung, die Dateien waren richtig.
- **Verdichtung der Dokumentation:** Befunde, Entscheidungen und Selbstprüfung im Eintrag „Dokumentation verdichtet“ in AENDERUNGEN.md; neue Arbeitspunkte daraus in 4.5, 4.7 und 4.9.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); dringend, weil Modul A Mails braucht | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für den Einwilligungstext | AF02, AF05 |
| 2 | D12, D13 | Nach Empfehlung genommen (HP01, HP02): bestätigen oder ändern | Plan 9, ANNAHMEN HP |
| 2 | – | Terrasse/Carport/Zufahrt erst mit H3 (Abweichung von Plan 3.8): einverstanden? Maße (Vorschlag: Terrasse 24 m² als 8 × 3 m wie im Mockup, Carport zweistellig 6 × 5 m)? | HP03, Plan 3.8/3.9 |
| 2 (vor H3) | D8, D10 | Honorar oder Bauleistung (bestimmt die Bedeutung der Preisspannen); Mehrwertsteuer in der Anzeige (Vorschlag brutto) | Plan 9 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E) und die zwei vorläufigen Einwilligungstexte | Plan 6.9, RW16, AF05 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Zugangslink in der Kundenmail (signiert) und Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt (Empfehlung) oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Umsetzungsplan als Ganzes freigeben (dann Plan 7 und Spez. E.4 einarbeiten); D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Nachprüfung von H2 und fehlende Ende-zu-Ende-Tests

1. Playwright-Szenarien „Kunde wählt Typ und verschiebt das Haus“ (H2) und Weg E (fehlt seit 17.09.); für A siehe 4.4.
2. Gesperrten Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung und Höhenprüfung mit Gelände im Browser ansehen (`site_enrich` lokal prüfen).
3. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.

### 4.2 H3 – Konfiguration und Kosten (nächstes Modul)

Umsetzungsplan 3.9, Spez. 5.5.4–5.5.6, 5.6.5, 5.9.3, 5.9.6. Zuerst `docs/PLAN_H3_….md` schreiben und selbst prüfen (Memory `feedback-selbstpruefung-dokumente`). Aus H2 (Plan H2 9): Tabelle `configuration` um Linie und Optionen erweitern (Migration 0010); Optionen um Art und Maße (H1 kennt `geometry_mode = none`); Terrasse an der Gartenfassade und Carport an der Straßenkante automatisch setzen (Nebengebäuderegeln `annex`); Freifläche mit Zufahrt; Kostenkorridor aus `type_base_price`/`package_type_price`/`module_type_price` (nur Spannen, L1); RE2020 aus `energy_assessment`; Himmelsrichtung mit Meridiankonvergenz (HP05); `evaluate()` in Typteil (gecacht) und Lageteil. Frontend: Schritte Linie, Optionen, Vorentwurf in `/konfigurator`; die Typkarte zeigt bewusst keinen Preis (HP17).

### 4.3 V – Vorentwurf-Übergabe

Umsetzungsplan 3.10: Anfrage um Konfiguration und Auswertung im Snapshot erweitern, vollständige Neuprüfung beim Absenden, Dossier-PDF, Lageplan als DXF (Lambert-93 und lokale Meter), Zustände, Nachrichten. D14: A bleibt daneben Notausgang.

### 4.4 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11/AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx` (bisher nur `AnfrageFormular`).
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`, danach Weiterleitung auf `/`, veraltetes Cookie).
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6), Nachrichten an den Kunden (mit V).

### 4.5 H1 abschließen

1. **Fünf Platzhalter-Typen** als echte XLSX/DXF erfassen (Plan H1 Kapitel 12; DXF-Umriss dort nur als Rechteck angenommen) und hochladen; Linien und Optionen zuerst (sonst `catalog_reference_unknown`); **Fassadenrollen zuweisen** (sonst richtet sich H2 nach Modellnorden, `facade_roles_missing`). Ein Generator fehlt; `backend/tests/e2e_seed_types.py` zeigt ein Muster.
2. XLSX-Vorlage zum Herunterladen (Endpunkt oder Datei); bisher nur die Beschreibung im Importformular.
3. `publish_package_version`/`publish_module_version` prüfen weder Status noch Reihenfolge: eine ältere Version lässt sich nach einer neueren veröffentlichen, eine veröffentlichte oder zurückgezogene erneut (beim Typ abgesichert). Absichern, Test dazu.
4. Docstring von `backend/app/catalog/api.py` nennt die Rollen falsch (`architect` liest nur); laut Code bearbeiten `architect` und `catalog_admin` (H01, H14).
5. Optional: Entwurf direkt bearbeiten statt neue Version; Komponententests für Linien/Optionen und Preise (bisher nur Typenliste und Typstand); Playwright Katalogpflege; Fehlertexte der Konsistenzprüfung über `code` übersetzen statt des deutschen `detail`.

### 4.6 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten; für H2 den Anteil gesperrter Typen je Zone stichprobenartig prüfen.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator` erwägen.
6. Später: Korrekturformular statt JSON (RW15); OCR (RW03); mehrbändige Reglements (RW23).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add` (auch für die Katalogpflege), Login prüfen.
2. G1–H2 auf Unraid nach Unraid README 9 und BETRIEB 1 (ausgehender Zugang, `.env` mit `ANTHROPIC_API_KEY`, Migrationen 0007–0009, `legal-seed`, Flags). **`EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `.env.example` noch nicht verdrahtet** – ergänzen, sonst gehen Büro-Mails an den Platzhalter. `demo_*`-Typen nie in Produktion.
3. Überwachung (Uptime Kuma, Unraid README 7) mit den Log-Alarmen aus BETRIEB 1; Offsite-Sicherung; erste Wiederherstellungsübung.
4. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
5. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshot (A), Konfiguration am Projekt (H2); die Claude API erhält nur Planunterlagen.
6. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.8 Korrekturen an der Spezifikation

S1–S17 mit Stand in Spez. Anhang E.4; zusammen mit Plan Kapitel 7 einarbeiten, sobald der Plan freigegeben ist (Abschnitt 3).

### 4.9 Weitere Punkte

1. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen.
2. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
3. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).
4. Log `envelope_derive_failed` (Plan G3 6.2) anlegen oder im Plan streichen; bisher gibt es keinen Alarm für G3.
5. Alten Test-Stack der G1-Session entfernen: `docker compose -p emprise-g1 down -v` (Container `emprise-g1-db-1`, Volume `emprise-g1_db-data`).

## 5. Empfohlener nächster Schritt

1. Verdichtete Dokumentation prüfen lassen und committen (auf Anweisung), `7cecdb5` mit pushen.
2. Priorität 1 aus Abschnitt 3 klären (Schlüssel der Claude API, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name), dann 4.6/4.7.
3. **H3 planen und umsetzen** (4.2); vorher Terrasse/Carport, D8/D10 klären. Danach V (4.3). Erst dann ist der Hauskonfigurator vollständig. Parallel H1 abschließen (4.5), sonst gibt es keine echten Typen für die Beta.

## 6. Hinweise

- Stolperstellen (Werkzeuge, lokaler Stack, Tests, Browserprüfung) stehen jetzt dauerhaft in [README.md](README.md); neue dort eintragen.
- Modulübersicht für Betrieb und Freischalten: [docs/BETRIEB.md](docs/BETRIEB.md) Abschnitt 1.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und die beiden Einträge vom 19.09.2026 in AENDERUNGEN.md (Dokumentation verdichtet, H2). Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1. Frag mich, ob die Abweichung „Terrasse und Carport erst in H3“ (ANNAHMEN HP03) und die nach Empfehlung genommenen D12/D13 so bleiben sollen und welche Maße Terrasse und Carport haben sollen. Danach plane H3 (Konfiguration und Kosten) nach Umsetzungsplan 3.9 mit Selbstprüfung und setze es um. Die Verdichtung der Dokumentation ist noch nicht committet, 7cecdb5 noch nicht gepusht.
```
