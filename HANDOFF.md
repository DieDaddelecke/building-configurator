# Hand-off für die nächste Session

> **Stand:** 28.09.2026 · **Letzte Session:** AN4, Parzellen-Upload (UP17–UP19), KI-Modell (PU11, PU12) und vollständige Regelauswertung mit gemeinsamer Verwaltung – committet und gepusht (Eintrag vom 28.09.2026 oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` gepusht bis `adf7ac4`; die acht Commits der Session sind nach Themen getrennt, für sich prüfbar erst `adf7ac4`. Die CI zu `adf7ac4` lief beim Hand-off noch (zu `ec5a6e1` grün). Die Hand-off-Dokumente dieser Session sind noch nicht committet.
- **Hauskonfigurator:** R0 (ohne Unraid), G1–G3, A, H1–H3 und V fachlich vollständig. Neu: Regelformular statt JSON in beiden Büro-Formularen (AN4, RW15), Abdeckung im Büro-Regelwerk, Link zur Verwaltung; die Nachsuche gilt auch hier.
- **Emprise Analyse (D18):** AN0–AN4 umgesetzt, dazu UP17–UP19 (Konturen zusammenstellen, kurze Stücke, Beschriftungen). Offen: AN5, AN7 (gescannte PDFs, entschieden, ohne Modulplan), AN6. Pläne: [PLAN_ANALYSE](docs/PLAN_ANALYSE.md), [PLAN_AN4](docs/PLAN_AN4_KORREKTUR.md).
- **G2:**
  - Schlüssel von OpenRouter lokal aktiv (`.env`, gitignored).
  - Modell wählt der Betrieb in `/verwaltung` für beide Produkte; lokal Opus 5.5 gewählt, Vorgabe der Umgebung weiter `anthropic/claude-opus-5`.
  - `g2-prompt-5` mit Nachsuche, Abdeckung und Referenzlisten ([PLAN_G2_VOLLSTAENDIGKEIT](docs/PLAN_G2_VOLLSTAENDIGKEIT.md), VA01–VA10, BETRIEB 9, 15, 16); etwa 1,46 $ je Kapitel.
- **Gemeinsame Datenbank** `emprise_shared`: lokal im Datenbankserver des Hauptstacks; auf Unraid noch nicht eingerichtet ([deploy/unraid/README.md](deploy/unraid/README.md) 10).
- **Lokal:** beide Stacks am 28.09.2026 abends neu gebaut; Referenzliste Beyenes UC als Entwurf eingespielt; die Datenbank `emprise_probe` der Vergleichsläufe besteht noch.
- **Tests:** Backend 697 (mit `TEST_S3=1`), Frontend 210, ruff, Format, mypy, Typprüfung, Lint grün. Playwright lief nicht.
- **Entscheidungen:**
  - D1–D4, D8, D10, D11–D18, G17, E-AN3G-1 bis -8.
  - Am 28.09.2026: E-AN4-1 bis -9, E-A7 (Scans → AN7), Hostname `emprise-analyse.aslani.work`, Hinweistexte schreibt der Nutzer, PU11, PU12, G2-Vollständigkeit mit E-VA-1 bis -4 (AENDERUNGEN).
  - Spezifikation: S1–S17 in Anhang E.4.

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- Guthaben bei OpenRouter: 3,84 $ von 10 $ verbraucht (Anzeige beim Hand-off; sie hinkt nach). Kosten je Lauf: PLAN_AN2_PLU 9, PLAN_G2 7.5.
- Die Live-Auswertung Beyenes in der Analyse ist noch Version 1 (Opus 5, vor der Nachsuche). An der Referenzliste gemessen: 13 von 25 richtig, 1 falsch (pauschale Grundfläche 0,9), 8 fehlen still (PLAN_G2 7.6).
- Befund 7 (Art. UC 11.1) ist im Code behoben; der Nachweis kommt erst mit dem nächsten bezahlten Lauf (PLAN_G2 7.5).
- Der Schlüssel stand im Chat → erneuern (4.3).

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | **Referenzliste Beyenes UC prüfen**, dann auf „geprüft“ setzen. Dabei klären: Abstände kleiner Nebengebäude (unter 12 m², unter 2,5 m) als feste Werte wie in der Liste oder als „nicht abbildbar“ wie im Probelauf? | `/verwaltung` → Referenzlisten, PLAN_G2 7.5 |
| 1 | – | **Beyenes UC neu auswerten** (etwa 1,46 $)? Empfehlung: nach der Prüfung der Liste – behebt 0,9 und belegt Befund 7. Sonst die Grundfläche per AN4 korrigieren | PLAN_G2 7.5–7.6 |
| 1 | E2 | Mailanbieter (Empfehlung Scaleway TEM, sonst Brevo); am 25.09. „später“ | Spez. 16, BETRIEB 5 |
| 1 | – | Sammeladresse (`EMPRISE_OFFICE_EMAIL`) und Name des Büros für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | – | **Opus 5.5 als Vorgabe** (`EMPRISE_RULES_MODEL`, Unraid `RULES_MODEL`)? Empfehlung ja: fand am meisten, je Token günstiger (4/20 $ statt 5/25 $). Sonst nach der Auslieferung in `/verwaltung` wählen | PLAN_AN2_PLU 9, PLAN_G2 7.5 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation, die vier vorläufigen Rechtstexte, ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen des Analyse-Produkts; vor AN6 juristisch prüfen | PLAN_ANALYSE 6 |
| 2 | – | H10–H14 bestätigen; AF11 (Anfrage außerhalb des Gebiets), AF12 (Antwortvorlage mit CU-Hinweis); G15 (Kartenkacheln) | ANNAHMEN |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro; Ablauf der Anfragebearbeitung; Standort des Unraid-Servers (L8) | Plan 8, 9 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Messbar jetzt mit Referenzlisten (VA03) | RW19 |
| 3 | E-A1, E-A6 | Produktname; Kostendeckel je Organisation mit eigenem Limit für Scans (E-A7) – vor AN6 | PLAN_ANALYSE 6 |
| 3 | – | Géorisques-Token; Umsetzungsplan freigeben (Plan 7, Spez. E.4 einarbeiten); D2, D7, E1–E12 | G12, Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Emprise Analyse abschließen (RA2)

1. **AN5** (PLAN_ANALYSE 4): Bericht-PDF mit Gabarit und Schnitt, DXF in 3D (E-AN3G-5), GeoJSON, Projektliste, Georeferenzierung mit Gelände (E-AN3G-4).
2. **Modulplan AN7** mit Selbstprüfung (PLAN_ANALYSE 4, E-A7); der Schlüssel ist da.
3. **Echte Unterlagen:** PLUi Erdre et Gesvres (333 Seiten – bei etwa 1,46 $ je Kapitel vorher das Budget prüfen), ein PLU einer anderen Gemeinde, ein règlement de lotissement mit Tabelle je Lot. Dauer und Kosten gehören nach BETRIEB 15.
4. Nutzfläche gegen Handrechnung an drei realen Grundstücken (PLAN_ANALYSE 7 Punkt 6); Zitat-PDFs in Chrome und Firefox (PU06).
5. Vor Daten in Produktion: Export fehlt (UP07); vor AN6 die Betroffenenrechte neu bewerten. Echte CAD-DXF aus dem Büro (PLAN_AN1 8.3).
6. Ende-zu-Ende-Szenario Analyse (Parzelle bis Zusatzdokument, mit Korrektur); Komponententest `KonturWahl` mit vielen Flächen. Später: ungenutzte Dokumente aufräumen (E-AN2-4), Vergleichstabelle in Telefonbreite gestapelt, frei gezogene Schnittlinie (E-AN3G-3).

### 4.2 G2-Vollständigkeit nacharbeiten (PLAN_G2_VOLLSTAENDIGKEIT)

1. Nach der Entscheidung in 3: Beyenes neu auswerten, messen und in 7.5 nachtragen; weitere Referenzlisten anlegen (Zonen von Treillières als Referenzmenge nach Spez. 11.4, andere Gemeinden).
2. **Staffel der Grundflächenzahl** im Schema und in der Berechnung (E-VA-4, eigener Plan).
3. **Sperre oder Bestätigung** vor bezahlten Neuauswertungen durch `rules_housekeeping` bei neuer `ENGINE_VERSION` (BETRIEB 15, „Neu auswerten kostet“).
4. Denkaufwand `xhigh`/`max` an OpenRouter durchreichen. Später E-VA-1 (Nachsuche für Zusatzdokumente) und E-VA-2 (Begriffe in der Verwaltung pflegen).
5. `emprise_probe` löschen, wenn keine Modelltests mehr anstehen (`DROP DATABASE emprise_probe`).

### 4.3 G2 und G3 mit Schlüssel

1. **Schlüssel erneuern** (openrouter.ai/keys) und lokal in `.env` eintragen, auf Unraid in `.env` und `.env.analyse`.
2. Kapitel von Treillières neu auswerten (`rules-extract --pending` bzw. „Neu auswerten“; Monatsbudget beachten). Danach `setback_street.band`, `max_area` und die Abdeckung in `/buero/regeln` prüfen.
3. `envelope-check --commune 44209` über alle Zonen (BETRIEB 10), Anteile für H2 und H3; dann Beta der Flags erwägen. Später mehrbändige Reglements (RW23).

### 4.4 Ende-zu-Ende und Nachprüfung (H2, H3, V, A, H1)

1. Playwright: Kunde bis Vorentwurf (H2, H3, V), Weg E, „Kunde stellt Anfrage“ (A).
2. Im Browser ansehen: gesperrter Typ, Mehrzonen, Gelände, H3 mit `annex`/`unsealed_min`, V mit Abweichungen. DXF im ArchiCAD des Büros prüfen (BETRIEB 14).
3. Aufräumen:
   - `configuration/domain/placement.py` (`facade`, `footprint_polygons`, `all_segments`)
   - im Frontend `vatRate`, `configurator.options.kind`/`.perM2`, `configurator.plan_layers`, `submission.disabled`
   - Tests: `garage_driveway` (HK07) fehlt; `test_moving_the_house_rechecks_the_outbuildings` ist schwach
4. A: Test zu AF10 und Docstring in `platform/tasks.py`; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`; Löschung im Browser prüfen; Endlöschung nach D6.
5. H1: fünf echte Typen mit Fassadenrollen (Plan H1 12), XLSX-Vorlage mit „netto (HT)“ und „Terrasse je m²“, Docstring der Rollen in `catalog/api.py` (H01, H14); optional Entwurf direkt bearbeiten, Tests für Preise und Typstand, Playwright Katalogpflege, Fehlertexte der Konsistenzprüfung über `code`.
6. Nach Bedarf (Plan H3 10.3, EA06, H05, Plan V 9.3): Carport in Schnellstellungen, ungeprüfte Regelarten, Preis-Editor, V-Ausbau.

### 4.5 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4, Authentik `auth.aslani.work`).
2. **Zuerst den gemeinsamen Stack** (README 10: `./deploy.sh shared`, `SHARED_*` in beiden `.env`).
3. Dann G1–V nach README 9 und BETRIEB 1: `openrouter.ai`, Migrate-Job bis 0017 mit `shared-migrate`, `legal-seed`, Flags. **`EMPRISE_OFFICE_EMAIL` ist auf Unraid noch nicht verdrahtet.** Keine `demo_*`-Typen; vor `configurator` und `submission` einen Preiskatalog veröffentlichen (BETRIEB 13, 14).
4. Analyse unter `emprise-analyse.aslani.work` (README 2), mit eigener Authentik-Anwendung und `./deploy.sh analyse`.
5. Überwachung (README 7), Offsite-Sicherung mit `emprise-shared`, erste Wiederherstellungsübung; SMTP nach E2; Hauptzweig schützen.
6. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6), mit Analyse-Projekten; die gemeinsame Datenbank enthält nur Namen und Kennungen von Betriebskonten.
7. Band `minio-data` und den Test-Stack `emprise-g1` entfernen.

### 4.6 Weitere Punkte

- Spez. S1–S17 mit Plan 7 einarbeiten, sobald der Plan freigegeben ist.
- „Regelwerke“ im Büro mit echten Daten ansehen.
- Einwilligung im Mockup (Spez. E.2 M10).
- CNIG-Typliste (BR05).
- Log `envelope_derive_failed` (Plan G3 6.2).

## 5. Empfohlener nächster Schritt

1. Hand-off-Dokumente committen, CI zu `adf7ac4` ansehen.
2. Referenzliste Beyenes UC prüfen (3), dann mit Freigabe neu auswerten und messen (4.2 Punkt 1); Schlüssel erneuern.
3. Danach AN5 oder Modulplan AN7 – oder Auslieferung auf Unraid samt gemeinsamem Stack (4.5).

## 6. Hinweise

- Stolperstellen stehen dauerhaft in [README.md](README.md): gemeinsame Alembic-Umgebung, Laufzeit-Image, weiterlaufendes `docker compose run`, geteilte Cookies beider Apps.
- Zwischencommits `219a285` bis `1c4ba2b` bauen einzeln nicht (gemischte Abschnitte im späteren Commit); bei `git bisect` überspringen.
- Der volle Backend-Lauf dauerte 8,5 Minuten; im Hintergrund mit `docker compose run -T`.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den obersten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen.
Frage mich danach in höchstens drei Fragen (Empfehlung an erster Stelle): Ergebnis meiner Prüfung
der Referenzliste Beyenes UC und Freigabe der Neuauswertung (HANDOFF 3, Priorität 1), Opus 5.5 als
Vorgabe, und was als Nächstes kommt (AN5, Modulplan AN7 oder Auslieferung auf Unraid, HANDOFF 4).
Arbeite das Gewählte ab (Modulplan mit Selbstprüfung, dann Umsetzung). Bezahlte Läufe nur nach
meiner Freigabe. Committe und pushe nur auf meine Anweisung.
```
