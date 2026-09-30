# Roadmap

> **Stand:** 30.09.2026, nach dem Refactoring „Komplexität reduzieren“ (29./30.09.2026). Diese Datei ersetzt HANDOFF.md: Stand, offene Entscheidungen, offene Arbeitspunkte, nächster Schritt. `/handoff` schreibt sie am Ende jeder Session fort. Dauerhaftes steht nicht hier, sondern in [DECISIONS.md](DECISIONS.md) (Entscheidungen), [README.md](README.md) (Stolperstellen) und [deploy/unraid/README.md](deploy/unraid/README.md) (Betrieb).

## 1. Stand

- **Git:** `main` lokal, nicht gepusht; alle Commits seit `6eb1cd2` (CI-Behebung, Refactoring S1–S23, Dokumentation). Push nur auf Anweisung.
- **Hauskonfigurator:** R0 (ohne Unraid), G1–G3, A, H1–H3 und V fachlich vollständig.
- **Emprise Analyse:** AN0–AN7 umgesetzt, seit dem 29.09.2026 in derselben Anwendung unter `/analyse` (ADR-02). AN6 auf Organisationen und Mitglieder zurückgebaut (ADR-07); fremde Büros gesperrt bis E-A5.
- **Refactoring:** eine Anwendung, eine Datenbank, Dateiverzeichnis statt SeaweedFS, zwei Warteschlangen, AN6-Zusätze entfernt, reine Funktionen aus den großen Diensten gelöst, große Dienstmodule geteilt, Dokumentation auf sechs Dateien plus Archiv (ADR-01 bis ADR-10). Lokal 7 Dienste statt 14, auf Unraid 10 Container statt 19.
- **G2:** Modell Opus 5.5 (RW28, PU11), `g2-prompt-5` mit Nachsuche, etwa 1,46 $ je Kapitel. Im Modellvergleich (PLAN_G2_VOLLSTAENDIGKEIT 7.7) bleibt Opus 5.5 vorn; GPT-6 Sol mit Flex ist die günstige Alternative. „Offen“ in der Messung heißt `named_gap` (`rules/domain/reference.py`): eine Regel „nicht ermittelt“ mit Grund, ein Hinweis statt eines Werts oder eine offene Stelle.
- **Lokal:** Stack `emprise` auf Migration 0023, ohne OpenRouter-Schlüssel gestartet. Die lokalen Analyse-Daten wurden nicht übernommen; die Referenzliste „PLU Beyenes UC“ (25 Einträge, Entwurf) liegt in `emprise`, das Dokument dazu nicht (4.1).
- **Tests:** Backend 833, Frontend 241; ruff, Format, mypy, Typprüfung, Lint und Build grün. Die Schlussprüfung des Refactorings (Browser, Playwright) steht in 2.
- **OpenRouter:** Anzeige zuletzt 4,38 $ von 10 $ (29.09.2026, hinkt nach). Der Schlüssel stand am 28.09. im Chat und ist zu erneuern (4.3).

## 2. Nächster Schritt

1. Schlussprüfung des Refactorings: voller Backend- und Frontend-Lauf, Browser-Rundgang (`/`, `/grundstueck`, `/buero`, `/analyse` mit Upload, Bericht und DXF, Mailcode bei wartendem langem Job), `corepack pnpm e2e`.
2. Auf Anweisung pushen und prüfen, dass die CI grün ist.
3. Danach nach Wahl des Nutzers: Referenzliste Beyenes UC prüfen und neu auswerten (4.1), G2-Befunde aus PLAN_G2 7.7 (4.1) oder Auslieferung auf Unraid (4.5).

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | **Push** der lokalen Commits | 1 |
| 1 | – | **Alte Datenbanken und Volumes löschen?** `emprise_analyse`, `emprise_shared`, `emprise_probe`, Volumes `emprise_storage-data` (SeaweedFS) und `emprise_minio-data`; Empfehlung: nach der Schlussprüfung, `pg_dump` vorher | 4.7 |
| 1 | – | **Referenzliste Beyenes UC prüfen**, dann auf „geprüft“ setzen; die Frage zu kleinen Nebengebäuden gehört zu E-VA-5 | `/analyse/verwaltung` → Referenzlisten, PLAN_G2 6, 7.5, 7.7 |
| 1 | – | **Beyenes UC neu auswerten** (etwa 1,46 $)? Empfehlung: nach der Prüfung der Liste; sonst die Grundfläche per Korrektur setzen | 4.1 |
| 1 | E2 | Mailanbieter (Empfehlung Scaleway TEM, sonst Brevo) | DECISIONS 3 |
| 1 | – | Sammeladresse (`EMPRISE_OFFICE_EMAIL`) und Name des Büros für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | – | AN7 Abnahme Nr. 4: bezahlte Auswertung des Scan-Kapitels UC (etwa 1,5 $) freigeben? | PLAN_AN7 6 |
| 2 | – | Befund „Zitat verschluckt eine Vorschrift“: Zitat in der Anweisung begrenzen oder überschießende Sätze in der Abdeckung wieder als offen führen? Empfehlung: Abdeckung (wirkt unabhängig vom Modell) | PLAN_G2 7.7 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation, die vier vorläufigen Rechtstexte, ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen der Analyse; vor fremden Büros juristisch prüfen. Mit E-A6 (Deckel je Organisation, wieder offen nach ADR-07) | DECISIONS 4.1 |
| 2 | – | H10–H14 bestätigen; AF11 (Anfrage außerhalb des Gebiets), AF12 (Antwortvorlage mit CU-Hinweis), G15 (Kartenkacheln) | ANNAHMEN |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro; Ablauf der Anfragebearbeitung; Standort des Unraid-Servers (L8) | DECISIONS 2 |
| 3 | – | Bruttopreise: Positionen und Summe werden getrennt gerundet und können um 1 Cent abweichen (B-65, per Test festgehalten). Vereinheitlichen? | 5 |
| 3 | – | `sentry-sdk` (nur aktiv mit `SENTRY_DSN`, nirgends gesetzt; ein Fremdanbieter widerspräche D3/D4) und `renovate.json` (nie ein Renovate-PR): entfernen oder behalten? | 5 |
| 3 | – | GPT-6 Sol mit Flex als günstigeres Modell? Empfehlung: bei Opus 5.5 bleiben | PLAN_G2 7.7 |
| 3 | E-A1 | Produktname der Analyse | DECISIONS 4.1 |
| 3 | – | Géorisques-Token; D2 (Beta, öffentlich), E1–E12 soweit offen | DECISIONS 2, 3 |
| später | E-VA-5 | Auslegung von Regeln gemeinsam mit dem Nutzer; bis dahin bleiben offene Punkte offen | PLAN_G2 6 |

## 4. Offene Arbeitspunkte

### 4.1 G2-Vollständigkeit (PLAN_G2_VOLLSTAENDIGKEIT)

1. **Befunde aus 7.7:** Ein Zitat verschluckt eine Vorschrift (S. 14 und S. 17 fehlen still); der Weg folgt aus der Entscheidung in 3. Den Widerspruch im Dach (`flat_roof` zugelassen, `flat` fehlt in `allowed_forms`) in `Roof._consistent` als ungültig werten.
2. **Beyenes UC:** Das PLU liegt nicht mehr in der lokalen Datenbank (Analyse-Daten nicht übernommen). Zum Neuauswerten unter `/analyse` ein Projekt anlegen und das PDF erneut hochladen; die Referenzliste findet es über die Prüfsumme. Danach messen und in PLAN_G2 7.5 nachtragen. Weitere Referenzlisten: Zonen von Treillières (Spez. 11.4), andere Gemeinden.
3. **Staffel der Grundflächenzahl** in Schema und Berechnung (E-VA-4, eigener Plan).
4. **Sperre oder Bestätigung** vor bezahlten Neuauswertungen durch `rules_housekeeping` bei neuer `ENGINE_VERSION`.
5. Denkaufwand `xhigh`/`max` an OpenRouter durchreichen; bei Flex `service_tier` und Wiederholung. Später E-VA-1 und E-VA-2.

### 4.2 Emprise Analyse

1. **Echte Unterlagen:** PLUi Erdre et Gesvres (333 Seiten; Budget vorher prüfen), ein PLU einer anderen Gemeinde, ein règlement de lotissement mit Tabelle je Lot, ein echter Scan (Schwelle „unsicher“, E-AN7-5). Dauer und Kosten in `deploy/unraid/README.md` nachtragen.
2. DXF (lokal, Lambert-93, 3D-Gabarit) im ArchiCAD des Büros prüfen (E-AN5-3); echte CAD-DXF aus dem Büro.
3. Nutzfläche gegen Handrechnung an drei realen Grundstücken; Zitat-PDFs in Chrome und Firefox.
4. Vor Daten in Produktion: Export (UP07); Betroffenenrechte mit Organisationen neu bewerten; verwaiste Dateien bei `retention_cleanup` (B-22, PLAN_AN5 7.4 Nr. 9).
5. Für fremde Büros (nach E-A5): Deckel je Organisation (E-A6), Bezahlung, AGB, Auftragsverarbeitung, Einladung der Mitglieder; Rückweg für API-Schlüssel und Erscheinungsbild in Git `24d3627`.
6. Ende-zu-Ende-Szenario Analyse von der Parzelle bis zum Zusatzdokument mit Korrektur und Bericht; Komponententest `KonturWahl` mit vielen Flächen; Scan-Parzelle als PDF im Browser bis zum Ende.
7. Später: ungenutzte Dokumente aufräumen (E-AN2-4), Vergleichstabelle in Telefonbreite gestapelt, frei gezogene Schnittlinie (E-AN3G-3), Zonengrenze einzeichnen (E-AN5-8), Filter der Projektliste nach Bereich, falls die gemischte Liste stört (ADR-02).

### 4.3 G2 und G3 mit Schlüssel

1. **Schlüssel erneuern** (openrouter.ai/keys); lokal in `.env`, auf Unraid in `.env`.
2. Kapitel von Treillières neu auswerten (`rules-extract --pending` bzw. „Neu auswerten“; Monatsbudget beachten). Danach `setback_street.band`, `max_area` und die Abdeckung in `/buero/regeln` prüfen.
3. `envelope-check --commune 44209` über alle Zonen, Anteile für H2 und H3; dann Beta der Flags erwägen. Später mehrbändige Reglements (RW23).

### 4.4 Ende-zu-Ende und Nachprüfung (H1–H3, A, V)

1. Playwright: Kunde bis Vorentwurf (H2, H3, V), Weg E, „Kunde stellt Anfrage“ (A).
2. Im Browser ansehen: gesperrter Typ, Mehrzonen, Gelände, H3 mit `annex`/`unsealed_min`, V mit Abweichungen. DXF von V im ArchiCAD des Büros prüfen, zusammen mit der DXF der Analyse.
3. Tests: `garage_driveway` (HK07) fehlt, `test_moving_the_house_rechecks_the_outbuildings` ist schwach; `configuration/domain/placement.py::facade` prüfen.
4. A: Test zu AF10 und Docstring in `platform/tasks.py`; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`; Löschung im Browser; Endlöschung nach D6.
5. H1: fünf echte Typen mit Fassadenrollen; XLSX-Vorlage mit „netto (HT)“ und „Terrasse je m²“; Docstring der Rollen in `catalog/api.py` (H01, H14). Optional: Entwurf direkt bearbeiten, Tests für Preise und Typstand, Playwright für die Katalogpflege, Fehlertexte der Konsistenzprüfung über `code`.
6. Nach Bedarf: Carport in Schnellstellungen, ungeprüfte Regelarten, Preis-Editor, V-Ausbau (Plan H3 10.3, EA06, H05, Plan V 9.3).

### 4.5 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen nach [deploy/unraid/README.md](deploy/unraid/README.md) (Authentik `auth.aslani.work`, eine Anwendung).
2. `openrouter.ai` erreichbar machen; Migrate-Job bis 0023, dann `legal-seed` und Flags. **`EMPRISE_OFFICE_EMAIL` ist auf Unraid noch nicht verdrahtet.** Keine `demo_*`-Typen; vor `configurator` und `submission` einen Preiskatalog veröffentlichen.
3. Reverse Proxy: `emprise-analyse.aslani.work` als Weiterleitung auf `/analyse`, falls der Name schon verteilt ist.
4. Überwachung (Uptime Kuma), Offsite-Sicherung, erste Wiederherstellungsübung mit Datenbank und Dateiverzeichnis; SMTP nach E2; Hauptzweig schützen.
5. Verarbeitungsverzeichnis mit Analyse-Projekten und Organisationen.
6. Nach dem öffentlichen Start mit `--all`: Flag-Prüfungen im Code entfernen (ADR-10).

### 4.6 Weitere Punkte

- „Regelwerke“ im Büro mit echten Daten ansehen.
- CNIG-Typliste für überlagernde Vorgaben (BR05, E-G3-2) vor einer Erweiterung des Einzugsgebiets.
- Log `envelope_derive_failed` (Plan G3 6.2).

### 4.7 Aufräumen (nach Freigabe, siehe 3)

- Datenbanken `emprise_analyse`, `emprise_shared`, `emprise_probe` (`DROP DATABASE`, vorher `pg_dump`).
- Volumes `emprise_storage-data` (SeaweedFS, darin auch der Bucket der Analyse mit dem Beyenes-PDF) und `emprise_minio-data` (MinIO; 29 Dateien, auf die die Datenbank noch verweist, fehlen seit der MinIO-Zeit; Dossiers lassen sich im Büro neu erzeugen).
- 240 Projekte mit `created_by = 'envelope-check'` vom 16.09.2026 in der lokalen Datenbank.
- Test-Stack `emprise-g1`.

## 5. Befunde des Refactorings, nicht umgesetzt

| Befund | Bewertung |
|---|---|
| Brutto doppelt gerundet (B-65): `configuration/domain/costs.py` und `configuration/outputs.py` runden Positionen und Summe getrennt, Abweichung bis 1 Cent | Fachverhalten, per Test festgehalten; Entscheidung in 3 |
| Gescanntes Reglement im GPU-Weg endet mit `no_chapters` (keine Texterkennung ohne Bestätigung, E-AN7-6) | Funktionserweiterung; `platform/scan.py` ist wiederverwendbar |
| Eingabe-Hash beim Text-Rückfall (S18): Kapitel, die vor dem 30.09.2026 über den Rückfall ausgewertet wurden, tragen den alten Hash; eine spätere Texterkennung löst dort keine Neuauswertung aus | nur lokale Altdaten; mit `--force` neu auswerten, falls nötig |
| `site/service.py`: `relocate` und `classify_outline` nicht als reine Funktionen gelöst | kein Fehler; bei nächster Arbeit an G1 |
| Schwelle `UNCOVERED_WARNING_SHARE` doppelt (`envelope/domain/derive.py`, `rules/domain/resolve.py`) | gleicher Wert 0,01; bei Änderung beide anpassen oder zusammenlegen |
| Zyklen `inquiry` ⇄ `submission` (B-01) und `rules.jobs` ⇄ `rules.*` (B-72) | funktionieren; beobachten |
| Drei PDF-Renderer mit eigenem HTML/CSS (Steckbrief, Bericht, Dossier; B-05) | Zusammenlegen erst bei der nächsten Arbeit an einem Renderer |
| `catalog/service.py` mit rund 1.150 Zeilen | ein Thema; teilen bei der nächsten Arbeit an H1 |
| Frontend-Build warnt vor Chunks über 500 kB | Analyse ist schon eigener Chunk; weiter teilen bei Bedarf |
| Layouts von Büro und Analyse getrennt | unterschiedlich gestaltet, nicht doppelt |
| Handgeschriebene Frontend-Typen `Problem`, `ParcelCollection`, `ReviewPart` | ohne Entsprechung in `components["schemas"]` |
| `sentry-sdk` und `renovate.json` vermutlich ungenutzt | Entscheidung in 3 |
| Tabellenliste in `backend/tests/conftest.py` von Hand gepflegt (REF-014) | aus den Metadaten erzeugen, wenn sie stört |

## 6. Hinweise

- Bezahlte Läufe nur nach Freigabe je Lauf; Tests und lokale Stacks ohne `EMPRISE_OPENROUTER_API_KEY` (README).
- Probeläufe in `emprise_probe`: gemeinsame Tabellen leer in derselben Datenbank, damit das Modell aus der Umgebung gilt (`EMPRISE_RULES_*`); vor dem zweiten Durchlauf `input_hash` des Kapitels leeren; Budgetgrenze über `EMPRISE_RULES_BUDGET_MONTH_USD`. Dateien liegen seit ADR-06 im Dateiverzeichnis; ein Probelauf im PDF-Modus braucht das Reglement dort.
- Die Zwischencommits `219a285` bis `1c4ba2b` bauen einzeln nicht; bei `git bisect` überspringen.

## 7. Startprompt für die neue Session

```
Lies ROADMAP.md und AI_CONTEXT.md. Fasse den Stand in fünf Sätzen zusammen.
Frage mich danach in höchstens drei Fragen (Empfehlung an erster Stelle), was aus ROADMAP 2 und 3 als
Nächstes kommt. Arbeite das Gewählte ab (Plan mit Selbstprüfung, dann Umsetzung). Bezahlte Läufe nur
nach meiner Freigabe. Committe und pushe nur auf meine Anweisung.
```
