# Hand-off für die nächste Session

> **Stand:** 26.09.2026 · **Letzte Session:** G2-Schnittstelle auf OpenRouter umgestellt (statt der Claude API unmittelbar), committet und gepusht (Eintrag vom 26.09.2026 oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` gepusht bis `16ac599` (`86869ed` Hand-off der AN3-Session, `16ac599` OpenRouter-Umstellung). Nichts uncommittet. CI zu `16ac599` nicht abgewartet.
- **Hauskonfigurator:** R0 (ohne Auslieferung auf Unraid), G1–G3, A, H1–H3 und V fachlich unverändert seit AN3 (neue Regelart `max_area`, PLU-Prompt `g2-prompt-4`).
- **Emprise Analyse (D18):** AN0–AN2 und AN3 (RA1-Teil und Zusatzdokumente) umgesetzt, fachlich unverändert seit der Vorsession. Pläne [PLAN_ANALYSE](docs/PLAN_ANALYSE.md), [PLAN_AN3](docs/PLAN_AN3_ANALYSE.md); Festlegungen EA01–EA12; Betrieb [BETRIEB 15](docs/BETRIEB.md).
- **G2 – Schnittstelle umgestellt:** Regelauswertung läuft jetzt über **OpenRouter** (`backend/app/integrations/openrouter.py`, OpenAI-kompatible Chat-Completions-API) statt unmittelbar über die Claude API; Modell weiter frei wählbar (Vorgabe `anthropic/claude-opus-5`). Schlüssel heißt jetzt `EMPRISE_OPENROUTER_API_KEY` (Unraid: `OPENROUTER_API_KEY`), nicht mehr `EMPRISE_ANTHROPIC_API_KEY`/`ANTHROPIC_API_KEY`. Festlegung **RW28** in `docs/ANNAHMEN.md`; damit ein weiterer Drittanbieter im Datenweg neben der bisherigen Ausnahme der Claude API (D3/D4) – akzeptiert für öffentliche Planunterlagen (L8). Entfällt: zugesichertes 1-Stunden-Zwischenspeichern, serverseitiger Fallback-Header (beides Anthropic-spezifisch).
- **G2 weiterhin ohne Schlüssel** ohne echte Auswertung (beide Produkte); H1 fehlen fünf echte Typdateien und die XLSX-Vorlage.
- **Tests:** Backend 585, Frontend 172, dazu ruff, `ruff format --check`, mypy, Frontend-Typecheck und Lint grün (im `backend-dev`-Image geprüft). Playwright lief nicht; für Konfigurator, V und das Analyse-Produkt gibt es kein Szenario.
- **Laufende Container `api`/`worker` veraltet:** Sie nutzen noch das alte Image `emprise-backend:local` ohne `openai`-Paket. Vor dem nächsten echten Auswertungslauf: `docker compose build migrate web`, dann `docker compose up -d migrate api worker web` (beide Stacks, siehe Abschnitt 4 unten).
- **Entscheidungen:** D1–D4, D8, D10, D11–D18 entschieden; G17 entschieden; am 25.09.2026 Budget, Authentik-Hostname und E-AN2-5; am 26.09.2026 OpenRouter statt Claude API (RW28). **Spezifikation:** Korrekturen S1–S17 in Anhang E.4 (S3 und S5 gelöst).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

Keine offenen: Die Abwägung zum zusätzlichen Drittanbieter steht in RW28 (`docs/ANNAHMEN.md`), die technischen Einzelheiten im AENDERUNGEN-Eintrag vom 26.09.2026.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | E2 | Mailanbieter (EU-Drittanbieter, Empfehlung Scaleway TEM, sonst Brevo); am 25.09.2026 „später“ – A und V können ohne ihn nicht produktiv gehen | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für die Einwilligungstexte (am 25.09.2026 nicht genannt) | AF02, AF05, VU08 |
| 2 | – | Gescannte PDFs (Parzelle, Reglement, Zusatzdokumente) lesen? Nur mit Bilderkennung über die Schnittstelle – Kosten je Aufruf. Empfehlung: nach dem Schlüssel | UP16, PU03, RW03 |
| 2 | – | Hostname und Authentik-Anwendung für den Analyse-Stack (Vorschlag `analyse.aslani.work`) | BETRIEB 15, PS08 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E), die **vier** vorläufigen Rechtstexte (A und V) und die ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen des Analyse-Produkts: Hinweis im Fuß genügt, solange nur das eigene Büro arbeitet; **vor AN6 juristisch prüfen** | PLAN_ANALYSE 6 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7 (auch `notice.rules_upload`, `notice.site_without_cadastre`)? Bis dahin Rückfalltext | G16, G30, BR11, PU05, EA12, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt (Empfehlung) oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19 |
| 3 | E-A1, E-A6 | Endgültiger Produktname statt „Emprise Analyse“ und Kostendeckel je Organisation – beides erst vor AN6 | PLAN_ANALYSE 6 |
| 3 | – | Géorisques-Token vor öffentlichem Start | G12 |
| 3 | – | Umsetzungsplan als Ganzes freigeben (dann Plan 7 und Spez. E.4 einarbeiten); D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Emprise Analyse weiterbauen (RA2)

1. **Nächstes Modul** – eines von: **AN4** (Regelformular statt JSON, RW15; Wert je Projekt übersteuern; **Werte aus Zusatzdokumenten mit Zitat übernehmen**, dazu Quelle an `project_rule_override`) oder **AN3 vollständig** (Gabarit als Höhenstufen, Schnitt) oder **AN5** (Bericht-PDF, DXF, Georeferenzierung). Reihenfolge nach PLAN_ANALYSE 5: AN3-Rest, AN4, AN5.
2. **Echte Unterlagen durch den Upload:** das vollständige PLUi Erdre et Gesvres (333 Seiten), ein PLU einer anderen Gemeinde, ein echtes règlement de lotissement mit Tabelle je Lot – Kapitelerkennung, Lesedauer, Vorschläge, Zuordnung der Lots. Mit Schlüssel Dauer und Kosten in BETRIEB 15 eintragen (PLAN_ANALYSE 7 Punkt 7).
3. **Nutzfläche gegen Handrechnung:** drei reale Grundstücke des Büros (PLAN_ANALYSE 7 Punkt 6); Abweichungen als Annahmen (EA03–EA05).
4. Zitat-PDFs in Chrome und Firefox öffnen (PU06; springt `#page=` auf die Seite?).
5. **Vor Daten in Produktion:** `GET /projects/{id}/export` fehlt dem Analyse-Produkt (UP07); vor AN6 auch die Betroffenenrechte neu bewerten.
6. Echten Katasterauszug und eine echte CAD-DXF aus dem Büro durch den Upload schicken (PLAN_AN1 8.3).
7. Ende-zu-Ende-Szenario für das Analyse-Produkt (Parzelle, Reglement, Zone, Analyse, Zusatzdokument); Komponententest für `KonturWahl` mit vielen Flächen.
8. Später: ungenutzte hochgeladene Dokumente aufräumen (E-AN2-4, BETRIEB 15 – bisher nur per SQL); Vergleichstabelle der Zusatzdokumente in Telefonbreite gestapelt statt verschiebbar.

### 4.2 Ende-zu-Ende-Tests und Nachprüfung von H2, H3 und V

1. Playwright-Szenarien: „Kunde wählt Typ, verschiebt das Haus, wählt Linie und Optionen, übergibt den Vorentwurf“ (H2, H3, V) und Weg E; für A siehe 4.4. Für V braucht die CI zusätzlich `tests.e2e_seed_types`, `legal-seed` und den Code aus Mailpit.
2. Im Browser ansehen: gesperrter Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung, Höhenprüfung mit Gelände; für H3 ein Grundstück mit wirksamer `annex`- und `unsealed_min`-Regel; für V eine Übergabe **mit** Abweichungen und ein Dossier für Weg E.
3. **DXF im ArchiCAD des Büros prüfen** (BETRIEB 14); bisher nur mit `ezdxf` zurückgelesen.
4. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.
5. Ungenutztes im Frontend: `vatRate` in `configuration/Linien.tsx`, Schlüssel `configurator.options.kind`, `configurator.options.perM2`, `configurator.plan_layers`, `submission.disabled` in `i18n/{de,fr}.json`.
6. Tests ergänzen: Zufahrt zum Garagentor (`garage_driveway`, HK07) hat keinen Test; `test_moving_the_house_rechecks_the_outbuildings` akzeptiert 200 oder 422 und ist damit schwach.

### 4.3 H3 und V weiterentwickeln (nach Bedarf)

- Schnellstellungen des Hauses (H2) kennen den Carport nicht (Plan H3 10.3).
- Nicht geprüft: `spaces_per_m2_sdp`, `setback_between_buildings`, `color_families_allowed`, `max_area` (EA06); kein Keller, keine Photovoltaik-Belegung, keine Ausführungen und Mengen (Plan 7, X3).
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

1. **Schlüssel von OpenRouter** (Nutzer, [openrouter.ai/keys](https://openrouter.ai/keys)): in `.env` und `.env.analyse` bzw. lokal `EMPRISE_OPENROUTER_API_KEY`. Da die laufenden Container das alte Image nutzen: zuerst `docker compose build migrate web` (beide Stacks: zusätzlich `-f compose.analyse.yaml`), dann `docker compose up -d migrate api worker web`; danach sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-4` (Parameter `band`, Regelart `max_area`) alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist und ob `max_area` nur echte Obergrenzen trifft.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten; für H2 den Anteil gesperrter Typen je Zone prüfen; für H3, wie oft `annex`, `unsealed_min` und `facade` wirksam werden.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator`/`submission` erwägen.
6. Später: OCR (RW03); mehrbändige Reglements (RW23). Das Korrekturformular (RW15) gehört zu AN4 (4.1).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4; Authentik unter `auth.aslani.work`, DNS only), danach TLS, Authentik, `staff-add`, Login prüfen.
2. G1–V auf Unraid nach Unraid README 9 und BETRIEB 1 (ausgehender Zugang **jetzt zusätzlich `openrouter.ai` statt `api.anthropic.com`**, `.env` mit `OPENROUTER_API_KEY`, Migrationen 0007–0014, `legal-seed`, Flags). **`EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `deploy/unraid/.env.example` noch nicht verdrahtet** – ergänzen. `demo_*`-Typen und Demo-Preise nie in Produktion; vor `configurator` und `submission` einen Preiskatalog veröffentlichen (BETRIEB 13, 14).
3. Zweiten Stack ausliefern, sobald gewünscht: `.env.analyse` aus der Vorlage (mit `OPENROUTER_API_KEY`), eigene Authentik-Anwendung, `./deploy.sh analyse` (BETRIEB 15).
4. Überwachung (Uptime Kuma, Unraid README 7) mit den Log-Alarmen aus BETRIEB 1, auch `dossier_failed`; Offsite-Sicherung; erste Wiederherstellungsübung.
5. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
6. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshots, Konfiguration, Dossierdateien; die Projekte des Analyse-Produkts (Eigentümer, hochgeladene Umrisse, Annahmen); hochgeladene Reglements und Zusatzdokumente enthalten in der Regel keine personenbezogenen Daten (PU01; ein cahier des charges kann Namen von Verkäufern nennen – prüfen). Die Schnittstelle (OpenRouter) erhält nur Planunterlagen.
7. Den ungenutzten Band `minio-data` entfernen (`docker volume rm emprise_minio-data`, README).

### 4.8 Weitere Punkte

1. **Spezifikation:** S1–S17 mit Stand in Spez. Anhang E.4; zusammen mit Plan Kapitel 7 einarbeiten, sobald der Plan freigegeben ist (Abschnitt 3).
2. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen; hochgeladene Reglements erscheinen dort nicht (nur je Projekt im Analyse-Produkt).
3. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
4. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).
5. Log `envelope_derive_failed` (Plan G3 6.2) anlegen oder im Plan streichen.
6. Alten Test-Stack der G1-Session entfernen: `docker compose -p emprise-g1 down -v`.

## 5. Empfohlener nächster Schritt

1. Priorität 1 aus Abschnitt 3: Mailanbieter (E2) und Büro-Angaben, sobald bekannt; den Schlüssel von OpenRouter eintragen (4.6 Punkt 1) – dabei zuerst die Container-Images neu bauen (alte `api`/`worker` haben `openai` noch nicht installiert).
2. Mit Schlüssel zuerst 4.1 Punkt 2 (echte Unterlagen) – misst beide Produkte; sonst das nächste RA2-Modul (4.1 Punkt 1) oder die Auslieferung auf Unraid (4.7).
3. Bald 4.2 und 4.1 Punkt 7: Playwright-Szenarien.

## 6. Hinweise

- Stolperstellen (lokaler Stack, Docker-Start, SeaweedFS, Tests, Fixtures aus anderen Testmodulen, Browserprüfung mit PDFs und Scheinauswertung – auch für Zusatzdokumente) stehen dauerhaft in [README.md](README.md).
- Der Volllauf des Backends dauert rund 7 Minuten; `docker compose run -T` benutzen.
- `uv lock` in einem Container ohne die bestehende `uv.lock` als Ausgangspunkt löst **alle** Pakete frisch auf und zieht ungewollt viele Fremdupgrades mit (in dieser Session so passiert und verworfen). Immer die vorhandene `uv.lock` zuerst in den Container kopieren, dann `uv lock` – so ändert sich nur, was die geänderten Abhängigkeiten wirklich erzwingen.
- Beim Öffnen eines PDF im Browserwerkzeug geht beim Nutzer ein Speichern-Dialog auf; PDFs dort nicht aufrufen.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den obersten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen.
Frage mich danach in höchstens drei Fragen (Empfehlung an erster Stelle), welches Modul als Nächstes kommt
(HANDOFF 4.1 Punkt 1: AN4, Rest von AN3 oder AN5 – oder die Auslieferung auf Unraid, 4.7) und was aus
Priorität 1 in HANDOFF 3 inzwischen feststeht.
Arbeite das gewählte Modul ab (Modulplan mit Selbstprüfung, dann Umsetzung). Committe und pushe nur auf
meine Anweisung.
```
