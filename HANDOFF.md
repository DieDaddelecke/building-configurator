# Hand-off für die nächste Session

> **Stand:** 29.09.2026 · **Letzte Session:** Emprise Analyse AN5, AN7, AN6 (technische Basis), Opus 5.5 als Vorgabe, Modellvergleich G2 (Kimi K3, GPT-6 Sol, GLM-5.3) und E-VA-5 – gepusht bis `6eb1cd2`, CI rot, die Behebung liegt lokal (Eintrag vom 29.09.2026 oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` gepusht bis `6eb1cd2`. **CI rot seit `24d3627`:** ruff S608 in `0020_organisations.py` (Backend); gitleaks meldete in `24d3627` einen Testwert (bei `6eb1cd2` grün). **Lokal behoben, nicht committet:** `# noqa: S608`, Testwert `emp_beispiel` in `organisation.test.tsx`, `.gitleaksignore` mit dem Fund; ruff und Test grün. Ebenfalls offen: README-Stolperstelle und die Hand-off-Dokumente.
- **Hauskonfigurator:** R0 (ohne Unraid), G1–G3, A, H1–H3 und V fachlich vollständig; seit dem 28.09. unverändert.
- **Emprise Analyse (D18):** AN0–AN7 umgesetzt, AN6 als technische Basis. Fremde Büros gesperrt bis E-A5; offen sind Bezahlung, AGB und Auftragsverarbeitung. Pläne [PLAN_AN5](docs/PLAN_AN5_AUSGABE.md), [PLAN_AN7](docs/PLAN_AN7_SCAN.md), [PLAN_AN6](docs/PLAN_AN6_MANDANTEN.md), [API_ANALYSE](docs/API_ANALYSE.md).
- **G2:** Vorgabe der Umgebung Opus 5.5 (RW28), in `/verwaltung` lokal ebenso; `g2-prompt-5` mit Nachsuche, etwa 1,46 $ je Kapitel. Im Modellvergleich ([PLAN_G2_VOLLSTAENDIGKEIT](docs/PLAN_G2_VOLLSTAENDIGKEIT.md) 7.7) bleibt Opus 5.5 vorn; GPT-6 Sol mit Flex ist die günstige Alternative.
- **Datenbanken:** `emprise_shared` lokal im Datenbankserver des Hauptstacks, auf Unraid noch nicht eingerichtet ([deploy/unraid/README.md](deploy/unraid/README.md) 10). `emprise_probe` auf 0020, mit den Vergleichsversionen 9–16.
- **Lokal:** Beide Stacks laufen mit 0020. Im Analyse-Stack liegen AN6-Testdaten: „Atelier Sud“ mit zwei Mitgliedern, ein Projekt aus der API, zwei API-Schlüssel (einer widerrufen). Die Sperre für fremde Büros ist wieder aktiv.
- **Tests:** Backend 776 (mit `TEST_S3=1`), Frontend 243; ruff, Format, mypy, Typprüfung, Lint und Build grün. Playwright lief nicht.
- **Entscheidungen:** D1–D4, D8, D10, D11–D18, G17, E-AN3G-1 bis -8, E-AN4-1 bis -9, PU11, PU12, E-VA-1 bis -4. Am 29.09.2026: RW28, E-AN5-1 bis -10, E-AN7-1 bis -7, E-AN6-1 bis -10, E-VA-5 (AENDERUNGEN). Spezifikation: S1–S17 in Anhang E.4.

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **„Offen“** in der Messung ist das Ergebnis `named_gap` ([reference.py](backend/app/rules/domain/reference.py)): eine Regel „nicht ermittelt“ mit Grund, ein Hinweis statt eines Werts oder eine offene Stelle. Aus den offenen Punkten je Modell und den PLU-Stellen dazu entstanden die ersten Auslegungsfragen in E-VA-5 (PLAN_G2 6).
- **OpenRouter:** Die Anzeige stand zuletzt bei 4,38 $ von 10 $ und hinkt nach. Die Vergleiche des Tages kosteten nach eigener Rechnung 1,71 $.
- Die Hilfsskripte der Probeläufe lagen nur im Scratchpad der Session und sind nicht im Repository. Das Vorgehen steht in PLAN_G2 7.5 und 7.7; Einzelheiten unter 6.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | **Behebung der CI committen und pushen** (0020, Testwert, `.gitleaksignore`, README) | 1 |
| 1 | – | **Referenzliste Beyenes UC prüfen**, dann auf „geprüft“ setzen. Die Frage zu den kleinen Nebengebäuden gehört zu E-VA-5 | `/verwaltung` → Referenzlisten, PLAN_G2 6, 7.5, 7.7 |
| 1 | – | **Beyenes UC neu auswerten** (etwa 1,46 $)? Empfehlung: nach der Prüfung der Liste. Das behebt die 0,9 und belegt Befund 7 im Produkt. Sonst die Grundfläche per AN4 korrigieren | PLAN_G2 7.5–7.7 |
| 1 | E2 | Mailanbieter (Empfehlung Scaleway TEM, sonst Brevo); am 25.09. „später“ | Spez. 16, BETRIEB 5 |
| 1 | – | Sammeladresse (`EMPRISE_OFFICE_EMAIL`) und Name des Büros für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | – | AN7 Abnahme Nr. 4: **bezahlte Auswertung des Scan-Kapitels UC** (etwa 1,5 $ mit Opus 5.5) freigeben? | PLAN_AN7 6 |
| 2 | – | Wie mit dem Befund „Zitat verschluckt eine Vorschrift“ umgehen? Zwei Wege: das Zitat in der Anweisung begrenzen, oder überschießende Sätze in der Abdeckung wieder als offen führen. Empfehlung: in der Abdeckung, denn das wirkt unabhängig vom Modell | PLAN_G2 7.7 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation, die vier vorläufigen Rechtstexte, ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen des Analyse-Produkts; vor der Freigabe fremder Büros juristisch prüfen | PLAN_ANALYSE 6, E-AN6-8 |
| 2 | – | H10–H14 bestätigen; AF11 (Anfrage außerhalb des Gebiets), AF12 (Antwortvorlage mit CU-Hinweis); G15 (Kartenkacheln) | ANNAHMEN |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro; Ablauf der Anfragebearbeitung; Standort des Unraid-Servers (L8) | Plan 8, 9 |
| 3 | – | GPT-6 Sol mit Flex als günstigeres Modell? Empfehlung: bei Opus 5.5 bleiben. Flex nur mit Wiederholung bei fehlender Kapazität und mit `service_tier` im Code | PLAN_G2 7.7 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Mit den Referenzlisten (VA03) jetzt messbar | RW19 |
| 3 | E-A1 | Produktname; E-A6 (Deckel je Organisation) ist mit AN6 technisch umgesetzt (E-AN6-4) | PLAN_ANALYSE 6 |
| 3 | – | Géorisques-Token; Umsetzungsplan freigeben (Plan 7, Spez. E.4 einarbeiten); D2, D7, E1–E12 | G12, Plan 9, Spez. 16 |
| später | E-VA-5 | **Auslegung von Regeln gemeinsam mit dem Nutzer**: Er erklärt, wie offene Punkte zu lesen sind. Bis dahin bleiben sie offen | PLAN_G2 6 |

## 4. Offene Arbeitspunkte

### 4.1 G2-Vollständigkeit nacharbeiten (PLAN_G2_VOLLSTAENDIGKEIT)

1. **Befunde aus 7.7:** Ein Zitat verschluckt eine Vorschrift (S. 14 und S. 17 fehlen still); der Weg folgt aus der Entscheidung in 3. Den Widerspruch im Dach (`flat_roof` zugelassen, `flat` fehlt in `allowed_forms`) in `Roof._consistent` als ungültig werten.
2. Nach der Entscheidung in 3: Beyenes neu auswerten, messen, in 7.5 nachtragen. Weitere Referenzlisten anlegen: Zonen von Treillières als Referenzmenge nach Spez. 11.4, andere Gemeinden.
3. **Staffel der Grundflächenzahl** im Schema und in der Berechnung (E-VA-4, eigener Plan).
4. **Sperre oder Bestätigung** vor bezahlten Neuauswertungen durch `rules_housekeeping` bei neuer `ENGINE_VERSION` (BETRIEB 15, „Neu auswerten kostet“).
5. Denkaufwand `xhigh`/`max` an OpenRouter durchreichen. Falls Flex gewählt wird: `service_tier` und Wiederholung. Später E-VA-1 (Nachsuche für Zusatzdokumente) und E-VA-2 (Begriffe in der Verwaltung pflegen).
6. `emprise_probe` löschen, wenn keine Modelltests mehr anstehen (`DROP DATABASE emprise_probe`).

### 4.2 Emprise Analyse nacharbeiten

1. **Echte Unterlagen:** PLUi Erdre et Gesvres (333 Seiten; bei etwa 1,46 $ je Kapitel vorher das Budget prüfen), ein PLU einer anderen Gemeinde, ein règlement de lotissement mit Tabelle je Lot, ein echter Scan (daran die Schwelle „unsicher“ nachstellen, E-AN7-5). Dauer und Kosten gehören nach BETRIEB 15.
2. DXF (lokal, Lambert-93, 3D-Gabarit) im ArchiCAD des Büros prüfen (BETRIEB 14, E-AN5-3). Echte CAD-DXF aus dem Büro (PLAN_AN1 8.3).
3. Nutzfläche gegen Handrechnung an drei realen Grundstücken (PLAN_ANALYSE 7 Punkt 6); Zitat-PDFs in Chrome und Firefox (PU06).
4. Vor Daten in Produktion: Export fehlt (UP07); Betroffenenrechte mit Organisationen neu bewerten. Verwaiste Dateien bei `retention_cleanup` (PLAN_AN5 7.4 Nr. 9).
5. Für fremde Büros (nach E-A5): Bezahlung, AGB, Auftragsverarbeitung, Einladung der Mitglieder (E-AN6-9).
6. Ende-zu-Ende-Szenario Analyse, von der Parzelle bis zum Zusatzdokument, mit Korrektur und Bericht. Komponententest `KonturWahl` mit vielen Flächen. Scan-Parzelle als PDF im Browser bis zum Ende (bisher nur bis zur Kalibrierung, PLAN_AN7 6 Nr. 5).
7. Später: ungenutzte Dokumente aufräumen (E-AN2-4), Vergleichstabelle in Telefonbreite gestapelt, frei gezogene Schnittlinie (E-AN3G-3), Zonengrenze einzeichnen (E-AN5-8).

### 4.3 G2 und G3 mit Schlüssel

1. **Schlüssel erneuern** (openrouter.ai/keys), weil er am 28.09. im Chat stand. Lokal in `.env` eintragen, auf Unraid in `.env` und `.env.analyse`.
2. Kapitel von Treillières neu auswerten (`rules-extract --pending` bzw. „Neu auswerten“; Monatsbudget beachten). Danach `setback_street.band`, `max_area` und die Abdeckung in `/buero/regeln` prüfen.
3. `envelope-check --commune 44209` über alle Zonen (BETRIEB 10), Anteile für H2 und H3; dann Beta der Flags erwägen. Später mehrbändige Reglements (RW23).

### 4.4 Ende-zu-Ende und Nachprüfung (H2, H3, V, A, H1)

1. Playwright: Kunde bis Vorentwurf (H2, H3, V), Weg E, „Kunde stellt Anfrage“ (A).
2. Im Browser ansehen: gesperrter Typ, Mehrzonen, Gelände, H3 mit `annex`/`unsealed_min`, V mit Abweichungen. DXF von V im ArchiCAD des Büros prüfen (BETRIEB 14), zusammen mit der DXF der Analyse (4.2 Punkt 2).
3. Aufräumen: `configuration/domain/placement.py` (`facade`, `footprint_polygons`, `all_segments`); im Frontend `vatRate`, `configurator.options.kind`/`.perM2`, `configurator.plan_layers`, `submission.disabled`. Tests: `garage_driveway` (HK07) fehlt, `test_moving_the_house_rechecks_the_outbuildings` ist schwach.
4. A: Test zu AF10 und Docstring in `platform/tasks.py`; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`; Löschung im Browser prüfen; Endlöschung nach D6.
5. H1: fünf echte Typen mit Fassadenrollen (Plan H1 12); XLSX-Vorlage mit „netto (HT)“ und „Terrasse je m²“; Docstring der Rollen in `catalog/api.py` (H01, H14). Optional: Entwurf direkt bearbeiten, Tests für Preise und Typstand, Playwright für die Katalogpflege, Fehlertexte der Konsistenzprüfung über `code`.
6. Nach Bedarf (Plan H3 10.3, EA06, H05, Plan V 9.3): Carport in Schnellstellungen, ungeprüfte Regelarten, Preis-Editor, V-Ausbau.

### 4.5 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4, Authentik `auth.aslani.work`).
2. **Zuerst den gemeinsamen Stack** (README 10: `./deploy.sh shared`, `SHARED_*` in beiden `.env`).
3. Dann G1–V nach README 9 und BETRIEB 1: `openrouter.ai` erreichbar machen; Migrate-Job **bis 0020** mit `shared-migrate`, dann `legal-seed` und Flags (das Image enthält Tesseract). **`EMPRISE_OFFICE_EMAIL` ist auf Unraid noch nicht verdrahtet.** Keine `demo_*`-Typen; vor `configurator` und `submission` einen Preiskatalog veröffentlichen (BETRIEB 13, 14).
4. Analyse unter `emprise-analyse.aslani.work` (README 2), mit eigener Authentik-Anwendung und `./deploy.sh analyse`. `EXTERNAL_ORGANISATIONS=false` lassen.
5. Überwachung (README 7), Offsite-Sicherung mit `emprise-shared`, erste Wiederherstellungsübung; SMTP nach E2; Hauptzweig schützen.
6. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6), mit Analyse-Projekten und Organisationen.
7. Band `minio-data` und den Test-Stack `emprise-g1` entfernen.

### 4.6 Weitere Punkte

- Spez. S1–S17 mit Plan 7 einarbeiten, sobald der Plan freigegeben ist.
- „Regelwerke“ im Büro mit echten Daten ansehen.
- Einwilligung im Mockup (Spez. E.2 M10).
- CNIG-Typliste (BR05).
- Log `envelope_derive_failed` (Plan G3 6.2).

## 5. Empfohlener nächster Schritt

1. Auf Anweisung die Behebung der CI und den Hand-off committen und pushen, dann prüfen, dass die CI grün ist.
2. Referenzliste Beyenes UC prüfen (3), dann mit Freigabe neu auswerten und messen (4.1 Punkt 2); den Schlüssel erneuern (4.3).
3. Danach die G2-Befunde aus 7.7 (4.1 Punkt 1) oder die Auslieferung auf Unraid samt gemeinsamem Stack (4.5).

## 6. Hinweise

- Stolperstellen stehen dauerhaft in [README.md](README.md), unter anderem gitleaks bei Testwerten, ruff vor dem Commit, `run_one` mit PLU, Prüfsumme des Berichts und `/admin`-Routen mit Organisation.
- Die Commits `24d3627` bis `6eb1cd2` sind in der CI rot, bis die Behebung committet ist. Die Zwischencommits `219a285` bis `1c4ba2b` bauen einzeln nicht; bei `git bisect` überspringen.
- **Probeläufe in `emprise_probe`:** Die gemeinsamen Tabellen liegen leer in derselben Datenbank, damit das Modell aus der Umgebung gilt (`EMPRISE_RULES_*`). Der PDF-Modus braucht `EMPRISE_S3_BUCKET=emprise-analyse-local`. Vor dem zweiten Durchlauf `input_hash` des Kapitels leeren. Das Startskript nahm die Nachsuche aus der Prüfsumme, damit Lauf 1 und 2 wiederverwendet werden. Budgetgrenze je Lauf über `EMPRISE_RULES_BUDGET_MONTH_USD`.
- Der volle Backend-Lauf dauert etwa 8,5 Minuten; im Hintergrund mit `docker compose run -T`.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den obersten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen.
Frage mich danach in höchstens drei Fragen (Empfehlung an erster Stelle): Commit der CI-Behebung,
falls noch offen (HANDOFF 1), Ergebnis meiner Prüfung der Referenzliste Beyenes UC samt Freigabe der
Neuauswertung (HANDOFF 3), und was als Nächstes kommt (G2-Befunde aus PLAN_G2 7.7, Auslieferung auf
Unraid oder echte Unterlagen, HANDOFF 4). Arbeite das Gewählte ab (Modulplan mit Selbstprüfung, dann
Umsetzung). Bezahlte Läufe nur nach meiner Freigabe. Committe und pushe nur auf meine Anweisung.
```
