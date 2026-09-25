# Hand-off für die nächste Session

> **Stand:** 25.09.2026 · **Letzte Session:** „Emprise Analyse“ beauftragt und begonnen – AN0 (Produktschnitt) und AN1 (Parzelle einbringen, auch aus PDF) umgesetzt; committet und gepusht (Eintrag „Emprise Analyse: AN0 … und AN1 …“ oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat) ist gepusht; alles aus dieser und den zwei Vorsessions ist committet (`8c9707f` Plandokument, `d97da2c` AN0 und AN1, dazu der Wechsel des Objektspeichers). Arbeitsbaum sauber.
- **Hauskonfigurator:** R0 (ohne Auslieferung auf Unraid), G1–G3, A, H1–H3 und V fertig; R2 fachlich vollständig. Verhalten unverändert, berührt wurden nur Weg E (legt jetzt Kanten an, ANNAHMEN UP02) und die Löschung eines Projekts (liegt im Kern, Sperre aus Modul A bleibt, UP07).
- **Emprise Analyse (zweites Produkt, D18):** **AN0** (Produktschnitt: `EMPRISE_PRODUCT`, `app/products.py`, Grenz-Test, zweiter Vite-Einstieg, zweiter Stack) und **AN1** (Parzelle als DXF, GeoJSON, vektorielles PDF oder Zeichnung; Kanten von Hand einordnen; Projekte am Architektenkonto) umgesetzt. Festlegungen: ANNAHMEN PS01–PS09 und UP01–UP16; Pläne: [PLAN_ANALYSE](docs/PLAN_ANALYSE.md), [PLAN_AN1](docs/PLAN_AN1_PARZELLE.md); Betrieb: [BETRIEB 15](docs/BETRIEB.md).
- **Tests:** Backend 526 (vorher 474), Frontend 150 (143), dazu ruff, Format, mypy, Typprüfung, Lint und Build grün. Playwright lief wie bisher lokal nicht; für Konfigurator, V und das Analyse-Produkt gibt es kein Szenario.
- **Neue Abhängigkeit:** `pdfminer.six` (MIT) zum Lesen der Zeichenpfade in Plan-PDFs; PyMuPDF bleibt wegen AGPL ausgeschlossen (wie `app/rules/pdf.py`).
- **Lokale Stacks laufen:** Hauskonfigurator http://localhost:8080 (API 8000), „Emprise Analyse“ http://localhost:8180 (API 8100, Dienste `api-analyse` usw., eigene Datenbank `emprise_analyse`). Beide mit `ops@emprise.local`, Flags je Datenbank gesetzt. Migration 0011 → **0012** in beiden.
- **G2 ohne Schlüssel** der Claude API weiterhin ohne echte Auswertung; H1 fehlen fünf echte Typdateien und die XLSX-Vorlage.
- **Entscheidungen:** D1–D4, D8, D10, D11–D18 entschieden; G17 entschieden. **Spezifikation:** Korrekturen S1–S17 in Anhang E.4 (S3 und S5 gelöst).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

Alles Wesentliche steht in den Plänen und in ANNAHMEN. Kurz:

- **Gegenprobe mit echten Daten:** Aus dem Kataster von Treillières wurde ein Auszug wie von cadastre.gouv.fr gesetzt (22 Parzellen, 23 Gebäude, 458 Schraffurlinien, Rahmen). In 0,33 s gelesen, Maßstab 1:500 aus „Échelle d'édition“ erkannt, AD 65 mit **926,1 m² – gleich der Katasterfläche**. Die Datei lag nur im Scratchpad; ein echter Auszug aus dem Büro ist die nächste Probe (PLAN_AN1 8.3).
- **Zwei Fehler, die nur im Browser auffielen** (PLAN_AN1 7.1a): gleich benannte Dienste beider Stacks im selben lokalen Netz (die Analyse-Oberfläche landete abwechselnd beim Hauskonfigurator) und `safe_next`, das nach der Anmeldung nur `/buero` zuließ.
- **Ungeprüft geblieben:** echte Katasterauszug-PDFs, DXF aus echter CAD-Ausgabe (nur selbst erzeugte Dateien), Playwright.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); dringend, weil A und V Mails brauchen | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | – | **Gescannte PDFs lesen?** Ginge nur mit Bilderkennung über die Claude API – Kosten je Aufruf, braucht den Schlüssel. Empfehlung: erst nach den Priorität-1-Punkten | PLAN_AN1 8.3, UP16 |
| 2 | – | Hostname und Authentik-Anwendung für den Analyse-Stack (Vorschlag `analyse.aslani.work`) | BETRIEB 15, PS08 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E), die **vier** vorläufigen Rechtstexte (A und V) und die ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen des Analyse-Produkts: Der Hinweis im Fuß genügt, solange nur das eigene Büro arbeitet; **vor AN6 juristisch prüfen** | PLAN_ANALYSE 6 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt (Empfehlung) oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19 |
| 3 | E-A1, E-A6 | Endgültiger Produktname statt des Arbeitstitels „Emprise Analyse“ und Kostendeckel der Claude API je Organisation – beides erst vor AN6 (Abo für fremde Büros) | PLAN_ANALYSE 6 |
| 3 | – | Géorisques-Token vor öffentlichem Start | G12 |
| 3 | – | Umsetzungsplan als Ganzes freigeben (dann Plan 7 und Spez. E.4 einarbeiten); D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Emprise Analyse weiterbauen

1. **AN2 – PLU hochladen** (8–10 T, PLAN_ANALYSE 4): règlement als PDF in den Objektspeicher, Zonenkapitel von Hand wählen, **zweiter Einstieg in `rules/service.py::resolve_rules`** (größter verdeckter Aufwand). Erst danach lohnt AN3.
2. **Vor AN1-Daten in Produktion:** `GET /projects/{id}/export` fehlt dem Analyse-Produkt (UP07); vor AN6 auch die Betroffenenrechte neu bewerten.
3. Echten Katasterauszug und eine echte CAD-DXF aus dem Büro durch den Upload schicken (PLAN_AN1 8.3); bei Abweichungen Maßstabserkennung und Kandidatenfilter nachziehen.
4. Ende-zu-Ende-Szenario für das Analyse-Produkt (Playwright fehlt ganz), Komponententest für `KonturWahl` mit vielen Flächen.

### 4.2 Ende-zu-Ende-Tests und Nachprüfung von H2, H3 und V

1. Playwright-Szenarien: „Kunde wählt Typ, verschiebt das Haus, wählt Linie und Optionen, übergibt den Vorentwurf“ (H2, H3, V) und Weg E (fehlt seit 17.09.); für A siehe 4.4. Für V braucht die CI zusätzlich `tests.e2e_seed_types`, `legal-seed` und den Code aus Mailpit.
2. Im Browser ansehen: gesperrter Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung, Höhenprüfung mit Gelände; für H3 ein Grundstück mit wirksamer `annex`- und `unsealed_min`-Regel; für V eine Übergabe **mit** Abweichungen und ein Dossier für Weg E.
3. **DXF im ArchiCAD des Büros prüfen** (Vorgehen in BETRIEB 14); bisher nur mit `ezdxf` zurückgelesen.
4. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.
5. Ungenutztes im Frontend: `vatRate` in `configuration/Linien.tsx`, Schlüssel `configurator.options.kind`, `configurator.options.perM2`, `configurator.plan_layers`, `submission.disabled` in `i18n/{de,fr}.json`.
6. Tests ergänzen: Zufahrt zum Garagentor (`garage_driveway`, HK07) hat keinen Test; `test_moving_the_house_rechecks_the_outbuildings` akzeptiert 200 oder 422 und ist damit schwach.

### 4.3 H3 und V weiterentwickeln (nach Bedarf)

- Schnellstellungen des Hauses (H2) kennen den Carport nicht (Plan H3 10.3).
- Nicht geprüft: `spaces_per_m2_sdp`, `setback_between_buildings`, `color_families_allowed`; kein Keller, keine Photovoltaik-Belegung, keine Ausführungen und Mengen (Plan 7, X3).
- Ein Preis-Editor fehlt: Preise kommen nur aus dem XLSX (H05, H14); die Importbeschreibung sollte „netto (HT)“ und „Terrasse je m²“ nennen (siehe 4.5).
- V: Anhänge an Nachrichten, Kopie einer Fassung als neue Konfiguration (Spez. 5.10.8), Webhooks (X5), erweitertes Dossier (X4) – bewusst offen (Plan V 1, 9.3).

### 4.4 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11 und AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`.
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`, Weiterleitung auf `/`, veraltetes Cookie) – die Löschung liegt seit AN1 im Kern.
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6).

### 4.5 H1 abschließen

1. **Fünf Platzhalter-Typen** als echte XLSX/DXF erfassen (Plan H1 Kapitel 12) und hochladen; Linien und Optionen zuerst, **Fassadenrollen zuweisen**. `backend/tests/e2e_seed_types.py` zeigt ein Muster mit Preisen.
2. XLSX-Vorlage zum Herunterladen; darin „Preise netto (HT)“ und „Terrasse je m²“ ergänzen.
3. Docstring von `backend/app/catalog/api.py` nennt die Rollen falsch (`architect` liest nur); laut Code bearbeiten `architect` und `catalog_admin` (H01, H14).
4. Optional: Entwurf direkt bearbeiten statt neue Version; Komponententests für Preise und Typstand; Playwright Katalogpflege; Fehlertexte der Konsistenzprüfung über `code` übersetzen.

### 4.6 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten; für H2 den Anteil gesperrter Typen je Zone prüfen; für H3, wie oft `annex`, `unsealed_min` und `facade` wirksam werden.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator`/`submission` erwägen.
6. Später: Korrekturformular statt JSON (RW15) – **gehört auch zu AN4**; OCR (RW03); mehrbändige Reglements (RW23).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add`, Login prüfen.
2. G1–V auf Unraid nach Unraid README 9 und BETRIEB 1 (ausgehender Zugang, `.env` mit `ANTHROPIC_API_KEY`, Migrationen 0007–**0012**, `legal-seed`, Flags). **`EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `deploy/unraid/.env.example` noch nicht verdrahtet** – ergänzen. `demo_*`-Typen und Demo-Preise nie in Produktion; vor `configurator` und `submission` einen Preiskatalog veröffentlichen (BETRIEB 13, 14).
3. Zweiten Stack ausliefern, sobald gewünscht: `.env.analyse` aus der Vorlage, eigene Authentik-Anwendung, `./deploy.sh analyse` (BETRIEB 15).
4. Überwachung (Uptime Kuma, Unraid README 7) mit den Log-Alarmen aus BETRIEB 1, auch `dossier_failed`; Offsite-Sicherung; erste Wiederherstellungsübung.
5. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
6. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshots, Konfiguration, Dossierdateien; neu die Projekte des Analyse-Produkts (Eigentümer, hochgeladene Umrisse). Die Claude API erhält nur Planunterlagen.
7. Erledigt am 25.09.2026: lokal und in CI SeaweedFS statt MinIO (A16) – MinIO war nicht mehr abrufbar. Offen bleibt, den ungenutzten Band `minio-data` zu entfernen.

### 4.8 Weitere Punkte

1. **Spezifikation:** S1–S17 mit Stand in Spez. Anhang E.4; zusammen mit Plan Kapitel 7 einarbeiten, sobald der Plan freigegeben ist (Abschnitt 3).
2. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen.
3. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
4. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).
5. Log `envelope_derive_failed` (Plan G3 6.2) anlegen oder im Plan streichen.
6. Alten Test-Stack der G1-Session entfernen: `docker compose -p emprise-g1 down -v`.

## 5. Empfohlener nächster Schritt

1. **CI im Auge behalten:** Der Lauf nach dem Wechsel des Objektspeichers muss grün sein, besonders der Job `e2e` – er startet den ganzen Stack und lief mit SeaweedFS noch nie.
2. Priorität 1 aus Abschnitt 3 klären (Schlüssel der Claude API, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name).
3. Danach entweder **AN2** (PLU hochladen, 4.1) oder die Auslieferung auf Unraid und G2/G3 mit echtem Schlüssel (4.6, 4.7). Beides ist unabhängig voneinander.
4. In beiden Fällen bald 4.2: Playwright-Szenarien und die Browserprüfungen, die noch fehlen.

## 6. Hinweise

- Stolperstellen (Werkzeuge, lokaler Stack, Tests, Browserprüfung, Prüftexte) stehen dauerhaft in [README.md](README.md); neu dort: der Analyse-Stack hängt am Netz und an den Images des Hauptstacks, seine Dienste heißen `…-analyse`, Konto und Flag gelten je Datenbank, und beide Produkte teilen lokal den Cookie-Vorrat.
- Der Volllauf des Backends dauert jetzt 5–17 Minuten (die PDF-Tests setzen PDFs mit WeasyPrint); `docker compose run -T` benutzen.
- Screenshots im Browserwerkzeug scheiterten zeitweise („page did not finish rendering“), wenn das Fenster im Hintergrund lag; `get_page_text` und `javascript_tool` gingen weiter.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den obersten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen.
Committe zuerst wie in HANDOFF 5 Punkt 1 beschrieben (Dokumente der Vorsessions getrennt, dann AN0+AN1),
zeig mir die Commit-Nachrichten vor dem Push. Danach entscheide mit mir die Priorität-1-Punkte aus
HANDOFF 3 – höchstens drei Fragen, jede mit Empfehlung an erster Stelle.
Arbeite anschließend AN2 aus HANDOFF 4.1 ab (Plan mit Selbstprüfung, dann Umsetzung) oder, wenn ich
das vorziehe, die Auslieferung auf Unraid (4.7). Pushe nur auf meine Anweisung.
```
