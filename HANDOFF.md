# Hand-off für die nächste Session

> **Stand:** 19.09.2026 · **Letzte Session:** H2 (Zulässigkeit und Implantation) geplant und vollständig umgesetzt (Backend, Frontend), im Browser geprüft, gepusht. Davor: H1-Oberfläche, Modul A.
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Letzter Code-Commit `98fce8f` (H2), davor `4423903` (Hand-off-Dokumente). CI-Lauf 35427795221 war bei Abschluss **noch in Arbeit** (`gh run list`). **Nicht committet:** die Dokumentänderungen dieses Handoffs (HANDOFF, AENDERUNGEN, AGENTS).
- **R0 Plattform:** anbieterunabhängiger Teil fertig; noch nicht auf Unraid ausgeliefert. [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **G1–G3:** fertig, lokal intern freigeschaltet (G01–G30, RW01–RW27, BR01–BR15). G2 ohne Schlüssel der Claude API noch keine echte Auswertung.
- **H1 Hauskatalog:** Backend und Büro-Oberfläche `/buero/katalog` fertig (H01–H14; [docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md)). Rechte: `architect`, `catalog_admin` bearbeiten, `ops` liest. Offen: fünf echte Typdateien, XLSX-Vorlage, Betriebsabschnitt (4.5).
- **A Anfrage:** fertig (AF01–AF12, [docs/BETRIEB.md](docs/BETRIEB.md) 11). Die Anfrage kennt noch **keine Konfiguration** (kommt mit V).
- **H2:** fertig und getestet ([docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md](docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md), ANNAHMEN HP01–HP20, BETRIEB 12). `backend/app/configuration`, Migration 0009, Flag `configurator`, Route `/konfigurator`: Typkarten mit Gründen und Vorschlägen, Lage ziehen/drehen, Schnellstellungen, Grenzschalter. Weg E und Grundstücke ohne Regeln laufen im freien Modus.
- **Hauskonfigurator (R2) insgesamt:** H1, H2 da; **H3 (Linie, Optionen, Kosten) und V (Übergabe) fehlen**.
- **Tests:** Backend 362, Frontend 91, ruff, mypy, Typprüfung, Lint grün. Playwright lief lokal nicht.
- **Lokaler Stack `emprise`:** neu gebaut, Migration 0009, Flag `configurator` für `architect`. Testdaten: erfundene Typen `demo_ligne`, `demo_plateau`, `demo_plateau_adapte` (Skript `backend/tests/e2e_seed_types.py`), H1-Typen `ligne` v1 (veröffentlicht) und `plateau` v1 (Entwurf), Linie `confort`, Option `pv`, RE2020-Befund ligne/confort, Anfrage `EMP-2026-000001`.
- **Umsetzungsplan:** R0, G1, G2, G3, H1, A, H2 beauftragt; D1–D4, D11, D14 entschieden; D12/D13 nach Empfehlung genommen, **nicht bestätigt**. **Spezifikation:** unverändert, Korrekturen S1–S14 offen (4.8).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **Auslegung des Auftrags:** „erstelle den hauskonfigurator“ heißt R2 (H1–V). Ich begann mit H2 (Plan, dann Umsetzung) und sagte dem Nutzer, dass H3 und V fehlen; er widersprach nicht und wies dann Commit und Push an.
- **Als entschieden genommen, nicht bestätigt** (ANNAHMEN HP01–HP04): D12 (nur `effective` sperrt, Unbekanntes ist Hinweis), D13 (Weg E nur Umriss; erweitert auf Grundstücke ohne verfügbare Regeln), Terrasse/Carport/Zufahrt erst in H3, kein `/buildable`.
- **Browserprüfung (AD 65, fr/de):** Ablauf funktioniert. Behoben: „2,99 m von 3,00 m“ (HP11), Schwenken um die Ecke beim Drehen (HP19), wiederholte Hinweise. Befunde: Plan H2 Kapitel 10.
- **Nicht gesehen:** gesperrter Typ mit echten Regeln (auf AD 65 nur Zone Uh ohne Dachregel ausgewertet, alle Demo-Typen zulässig), Ziehen per Berührung, Mehrzonen-Grundstück am echten Beispiel. Höhenprüfung lokal überall `unknown`, weil das Gelände fehlt.
- **Aus der H1-Session weiter gültig** (ANNAHMEN H10–H14, nicht bestätigt; **H2 liest diese Formate**): Eingang/Garagentor als `{edge, position}`; links/rechts der Fassadenrollen von der Straße aus gesehen; Linien und Optionen nur als neue Version änderbar.
- **Beobachtet, nicht behoben (H1):** `publish_package_version`/`publish_module_version` prüfen weder Status noch Reihenfolge (ältere Version nach einer neueren veröffentlichen, erneut veröffentlichen). Beim Typ abgesichert. Prüfhinweise und Fehlertexte des Backends (`detail`) sind deutsch, auch in der französischen Oberfläche.
- **Korrektur:** Im Abschlusstext dieser Session stand, HANDOFF.md nenne das H1-Frontend als offen. Das traf nur auf eine ältere Fassung zu; die im Repository liegende sagte es richtig.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); dringend, weil Modul A Mails braucht | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für den Einwilligungstext | AF02, AF05 |
| 2 | D12, D13 | Nach Empfehlung genommen (HP01, HP02): bestätigen oder ändern | Plan 9, ANNAHMEN HP |
| 2 | – | Terrasse/Carport/Zufahrt erst mit H3 (Abweichung von Plan 3.8): einverstanden? Maße (Vorschlag: Terrasse 24 m² als 8 × 3 m wie im Mockup, Carport zweistellig 6 × 5 m)? | HP03, Plan 3.8/3.9 |
| 2 (vor H3) | D8, D10 | Honorar oder Bauleistung (bestimmt Bedeutung der Preisspannen); Mehrwertsteuer in der Anzeige (Vorschlag brutto) | Plan 9 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E) und die zwei vorläufigen Einwilligungstexte | Plan 6.9, RW16, AF05 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Zugangslink in der Kundenmail (signiert) und Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? | RW19 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 CI und Nachprüfung von H2

1. CI-Lauf 35427795221 abwarten; bei Netzfehlern zu `sum.golang.org` `gh run rerun <id> --failed`.
2. Playwright-Szenario „Kunde wählt Typ und verschiebt das Haus“.
3. Gesperrten Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung und Höhenprüfung mit Gelände im Browser ansehen (`site_enrich` lokal prüfen).
4. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.

### 4.2 H3 – Konfiguration und Kosten (nächstes Modul)

Umsetzungsplan 3.9, Spez. 5.5.4–5.5.6, 5.6.5, 5.9.3, 5.9.6. Zuerst `docs/PLAN_H3_….md` schreiben und selbst prüfen (Memory `feedback-selbstpruefung-dokumente`). Aus H2: Tabelle `configuration` um Linie und Optionen erweitern (Migration 0010); Optionen um Art und Maße (H1 kennt `geometry_mode = none`); Terrasse an der Gartenfassade und Carport an der Straßenkante automatisch setzen (Nebengebäuderegeln `annex`); Freifläche mit Zufahrt; Kostenkorridor aus `type_base_price`/`package_type_price`/`module_type_price` (nur Spannen, L1); RE2020 aus `energy_assessment`; Himmelsrichtung mit Meridiankonvergenz (HP05); `evaluate()` in Typteil (gecacht) und Lageteil. Frontend: Schritte Linie, Optionen, Vorentwurf in `/konfigurator`; die Typkarte zeigt bewusst keinen Preis (HP17).

### 4.3 V – Vorentwurf-Übergabe

Umsetzungsplan 3.10: Anfrage um Konfiguration und Auswertung im Snapshot erweitern, vollständige Neuprüfung beim Absenden, Dossier-PDF, Lageplan als DXF (Lambert-93 und lokale Meter), Zustände, Nachrichten. D14: A bleibt daneben Notausgang.

### 4.4 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11/AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`.
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`).
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6), Nachrichten an den Kunden (mit V).

### 4.5 H1 abschließen

1. **Fünf Platzhalter-Typen** als echte XLSX/DXF erfassen ([docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md) Kapitel 12) und hochladen; Linien und Optionen zuerst (sonst `catalog_reference_unknown`); **Fassadenrollen zuweisen** (sonst richtet sich H2 nach Modellnorden, `facade_roles_missing`). Ein Generator fehlt; `backend/tests/e2e_seed_types.py` zeigt ein Muster.
2. XLSX-Vorlage zum Herunterladen (Endpunkt oder Datei).
3. `publish_package_version`/`publish_module_version` absichern (Abschnitt 2), Test dazu.
4. `docs/BETRIEB.md`-Abschnitt für H1 (Migration 0007, Abhängigkeiten openpyxl/ezdxf/python-multipart, Rolle `catalog_admin`).
5. Optional: Entwurf direkt bearbeiten statt neue Version; Komponententests für Linien/Optionen und Preise; Playwright Katalogpflege; Konsistenzprüfung über `code` übersetzen.

### 4.6 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen (BETRIEB 10); für H2 den Anteil gesperrter Typen je Zone stichprobenartig prüfen.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator` erwägen.
6. Später: Korrekturformular statt JSON (RW15); OCR (RW03); mehrbändige Reglements (RW23).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add` (auch für `catalog_admin`), Login prüfen.
2. G1–H2 auf Unraid: ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`), `.env` mit `ANTHROPIC_API_KEY` und `EMPRISE_OFFICE_EMAIL`; Migrationen 0007–0009 laufen mit; danach `legal-seed`, `flag-set inquiry`/`configurator` (BETRIEB 11, 12); Caddy-Ersetzungen prüfen (A27). **Die `demo_*`-Typen nie in Produktion.**
3. Überwachung (Uptime Kuma), Offsite-Sicherung, erste Wiederherstellungsübung.
4. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
5. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshot (A), Konfiguration am Projekt (H2); die Claude API erhält nur Planunterlagen.
6. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.8 Korrekturen an der Spezifikation (offen)

S1–S14 unverändert seit 13.09.2026 (AENDERUNGEN.md 14.09.). Aus H2: Spez. 6.3 nennt `/buildable` (entfällt, HP04), 5.3.6 die Rastersuche (ersetzt durch die Fläche zulässiger Ursprünge), 6.1 `placement` in Lambert-93 (API lokal, HP12). S10 (Löschung gegen Aufbewahrung) ist mit Modul A vorläufig entschärft.

### 4.9 Weitere Punkte

1. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen.
2. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
3. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).

## 5. Empfohlener nächster Schritt

1. CI-Ergebnis von `98fce8f` prüfen; Dokumentänderungen dieses Handoffs committen (auf Anweisung).
2. Priorität 1 aus Abschnitt 3 klären (Schlüssel der Claude API, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name), dann 4.6/4.7.
3. **H3 planen und umsetzen** (4.2); vorher Terrasse/Carport, D8/D10 klären. Danach V (4.3). Erst dann ist der Hauskonfigurator vollständig. Parallel H1 abschließen (4.5), sonst gibt es keine echten Typen für die Beta.

## 6. Hinweise und Stolperstellen

- **Modellnamen der API müssen über alle Module eindeutig sein:** gleiche Pydantic-Namen (`PlacementIn` in Katalog und H2) werden im OpenAPI umbenannt und brechen die generierten Frontend-Typen. Nach Änderungen `python -m app.cli openapi openapi.json` (Container), dann `corepack pnpm run api:types`; `test_committed_openapi_matches_code` prüft es.
- **`backend-dev` nutzt die Umgebungsvariablen des lokalen Stacks:** Skripte wie `python -m tests.e2e_seed_types` laufen gegen die lokale Datenbank `emprise`; pytest legt eine eigene Testdatenbank an.
- **Tabelle `rule` ist unveränderlich:** Tests ändern Regeln nur über `rules_service.set_override`. Fixtures des Baurahmen-Tests (`project`: Grundstück AD 65, Zone Uh) übernimmt `test_configuration.py` per Zuweisung (`project = _envelope.project`), nicht per Import (ruff F811).
- **H2 domain ist rein:** `backend/app/configuration/domain`, Eingabe `EnvelopeInput`/`Envelope` aus G3 (`envelope.service.derived`). Koordinaten dort lokal, in der Datenbank Lambert-93. Testgrundstück 20 × 31 m (Straße Norden) über `tests/configuration_support.py`.
- **React-Hooks-Lint (Version 7):** keine Ref-Zugriffe beim Rendern, keine `setState`-Effekte; `Implantation` baut deshalb mit `key={revision}` neu auf.
- **Neue Sequenzen brauchen einen eigenen `GRANT`** (AF07); `inquiry_number_seq` wird von `TRUNCATE … RESTART IDENTITY` nicht zurückgesetzt.
- **Lokalen Stack aktualisieren:** `docker compose build migrate web`, dann `docker compose up -d migrate api worker web` (`api`/`worker` nutzen `emprise-backend:local`, das `migrate` baut; `backend-dev` ist `:dev`). Nach neuen Abhängigkeiten `uv lock` und `docker compose --profile dev build backend-dev`.
- **Backend-Prüfung:** `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"` (Git-Bash: `MSYS_NO_PATHCONV=1` davor); etwa 3,5 Minuten. Lokal ist kein Python installiert.
- **Frontend:** `corepack pnpm run typecheck && corepack pnpm run lint && corepack pnpm run test` im Ordner `frontend`. Eine frühere Session sah in Git-Bash einen Pfadfehler und nahm PowerShell; in dieser lief es aus Bash. `unwrap` scheitert an `204` ohne Rumpf. i18n verschachtelt, Backend-Übersetzungen flach (`problem.…`, `{param}`).
- **Datei-Uploads:** `openapi-fetch` mit `bodySerializer: () => formData` und Platzhalter-Rumpf (`frontend/src/api/catalog.ts`); Content-Type nicht setzen.
- **Browserprüfung:** Login `http://localhost:8080/api/v1/auth/staff/login` (Mock-OIDC, ohne Eingabe, `ops@emprise.local`, landet unter `/buero`), danach `/grundstueck`: „Saisir la référence cadastrale“ (Section `AD`, Nummer `65`), „Valider le terrain“, „Choisir ma maison“. `left_click_drag` löst das Ziehen aus. Dateien in Formulare per `javascript_tool` (`DataTransfer`), Daten über die Web-Ebene bereitstellen (`docker cp` nach `emprise-web-1:/srv/`; fremde Ursprünge blockt die CSP). `window.confirm` wird abgebrochen: vorher `window.confirm = () => true`.
- **Heredocs im Bash-Werkzeug** zerbrechen an Apostrophen, Backticks und `$$`; Git-Bash-`/tmp` ist nicht das `C:\tmp` von Node. Längere Dateien mit dem Write-Werkzeug schreiben, kleine Textersetzungen mit Node-Skripten.
- **H1-Trigger `forbid_published_modification`** ist bedingt (nur `published`), `forbid_modification` unbedingt (`audit_log`, `legal_text`, `consent`). Der Preiskatalog legt bei `GET .../price-catalog/draft` bei Bedarf einen Entwurf an.
- **Jobarten registrieren:** Wer `enqueue` aufruft, muss `app.registry` importieren. **FastAPI:** neue öffentliche Route in `test_access_policies.py` eintragen; Projekt- und Rollenrouten brauchen keinen Eintrag.
- **Weg E:** Geometrie ohne geografischen Bezug, nie ohne Prüfung von `site.origin`. **WeasyPrint** braucht Pango und DejaVu im Image. **Unsichtbare Zeichen:** `backend/app/rules/domain/text.py` beim Neuschreiben mit `git diff` prüfen.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten. **Ports lokal:** Web 8080, API 8000, OIDC 8081, MinIO 9000, Mailpit 8025. Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`. Beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen.
- **Rate-Limits beim Testen:** 429 bei vielen Projekten/Codes derselben IP; Limits in `.env` hochsetzen (`inquiry_*`, `configuration_limit_per_minute`). **Kosten der Claude API:** Änderungen an Prompt/Ausgabeschema vor dem Eintragen des Schlüssels bündeln.
- **CI:** Security-Job baut Caddy mit `xcaddy`; Netzfehler zu `sum.golang.org` sind kein Codefehler.
- **Commit und Push nur auf Aufforderung**, direkt auf `main` (Memory `feedback-plan-dann-umsetzen`); offene Dokumente einer vorigen Session getrennt vom Code committen.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den Eintrag vom 19.09.2026 (H2) in AENDERUNGEN.md. Prüfe das Ergebnis des CI-Laufs 35427795221 zum Commit 98fce8f. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1. Frag mich, ob die Abweichung „Terrasse und Carport erst in H3“ (ANNAHMEN HP03) und die nach Empfehlung genommenen D12/D13 so bleiben sollen und welche Maße Terrasse und Carport haben sollen. Danach plane H3 (Konfiguration und Kosten) nach Umsetzungsplan 3.9 mit Selbstprüfung und setze es um. Die Dokumentänderungen dieses Handoffs sind noch nicht committet.
```
