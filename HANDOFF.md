# Hand-off für die nächste Session

> **Stand:** 14.09.2026 · **Letzte Session:** Prüfung der Umsetzung von G1 und G2 (23 Befunde) und Behebung aller Befunde samt Tests und Dokumentation; committet und gepusht
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md) (vier Einträge vom 14.09.2026).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Letzte Commits: G2 (`91e84f6`), Nacharbeiten G1/G2 (`13092f9`), Hand-off (`b2545db`). CI für die Nacharbeiten am 15.09.2026 vollständig grün (Backend, Frontend, E2E, Security).
- **R0 Plattform (Plan 3.2):** anbieterunabhängiger Teil fertig; Überwachung, Offsite-Sicherung, Mail offen. [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **Betrieb bis zur Beta:** [deploy/unraid/README.md](deploy/unraid/README.md) (G1 Abschnitt 9, G2 Abschnitt 10), lokal geprüft, **noch nicht auf Unraid ausgeliefert**.
- **G1 Grundstück (Plan 3.3):** fertig, lokal intern freigeschaltet. ANNAHMEN G01–G25, [docs/BETRIEB.md](docs/BETRIEB.md) 8. Neu: Hauptstraße nach Sicherheit (G23), keine hängenden Gelände-/Risikoabfragen (G24), Straßenachsen-Plausibilität (G25), Adress-Cache nur im Arbeitsspeicher (G22).
- **G2 Regelwerk (Plan 3.4 mit D11):** umgesetzt, geprüft, Befunde behoben. ANNAHMEN RW01–RW27, BETRIEB 9.
  - Auswertung + **Gegenprüfung** ohne Werte statt zweitem gleichem Lauf (RW19, Abweichung vom Plan 3.4).
  - Zitatprüfung: Auslassungen, Verneinungen, „nicht geregelt“ nur mit Formel, Sektor-Zuordnung (RW24, RW25).
  - Planstand am Ort aktualisieren, Rückfall auf vorigen Planstand als „veraltet“ (RW20, RW21); mehrbändige Reglements → `multiple_regulations` (RW23).
  - Job `rules_housekeeping` stündlich: Wiederaufnahme ohne Büro (RW22); Neubewertung ohne API-Aufruf bei neuer `ENGINE_VERSION`, Aufteilung bei `max_tokens` (RW26).
  - Migration `0004` (nur neue Spalten). Tests: Backend 196, Frontend 26; ruff, mypy, ESLint, tsc, Build grün.
  - **Noch keine echte Auswertung mit der Claude API** (kein Schlüssel). Referenzmenge, Kosten, Dauer, Anteil `unknown` und Wirkung der Gegenprüfung ungemessen.
- **Lokaler Stack `emprise`** (Port 8080): mit Arbeitsstand dieser Session neu gebaut, Migration 0004 angewendet; Kataster und Planstand Treillières; Zone Uh mit aufgezeichneter Auswertung, übrige Kapitel `failed: not_configured`; Flags `site_selection`, `rules_simulation` für `architect`; Konto `ops@emprise.local`.
- **Umsetzungsplan:** als Ganzes Vorschlag; R0, G1, G2 beauftragt; D1–D4, D11 entschieden, D12 offen (Plan 9). **Spezifikation:** unverändert, Korrekturen S1–S14 offen (4.4). **Mockup, Dokumentation.html:** unverändert.

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **Prüfung G1/G2:** 23 Befunde; jeder steht jetzt als Annahme (G22–G25, RW19–RW27) mit Test. Nachgestellte Fehlerfälle im Protokolleintrag von [AENDERUNGEN.md](AENDERUNGEN.md).
- **Verworfen:** Verdacht, schmale oder schräge Grundstücke erhielten zu wenige Geländestichproben – nachgestellt (4 × 60 m bis 6 × 90 m, gedreht), immer 9 Stichproben.
- **Grenzen der Umsetzung (bewusst):** Sektor-Zuordnung über Satzteile ist eine Heuristik (im Zweifel `unknown`); unsichere lange Straßenkante bleibt Straße (vorsichtig) mit `edges_need_review`; Kosten eines vom Zeitlimit abgebrochenen Aufrufs sind unbekannt (Lauf `interrupted:*` ohne Kosten); mehrbändige Reglements werden nicht ausgewertet.
- Frühere Chat-Ergebnisse (Planwerk Treillières, Zone Uh, Kostenschätzung 1–2 $ je Kapitel) stehen in ANNAHMEN RW01–RW18 und BETRIEB 9.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU, z. B. Brevo, Scaleway TEM) | Spez. 16, BETRIEB 5 |
| 2 (vor Beta) | – | Rechtliche Prüfung der ungeprüften Simulation: Wortlaut der Hinweise, Haftung | Plan 6.9, RW16 |
| 2 | – | Wer schreibt die Hinweistexte L7 (`notice.cadastre_accuracy`, `notice.risks_public_data`, `notice.rules_simulation`, `notice.rules_lotissement`)? Bis dahin Rückfalltext | G16, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN; Hinweis genügt oder eigener Kachel-Proxy? Empfehlung Hinweis | G15 |
| 2 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro | Plan 9 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 (vor H2) | D12 | Wie stark schränken simulierte Regeln den Konfigurator ein? Vorschlag: verifizierte Regeln wie Grenzen, `unknown` nur Hinweis, Anfrage immer möglich | Plan 9 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in den Umsetzungsplan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19, Plan 3.4 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Außerhalb des Einzugsgebiets bis Modul A nur Hinweis – ausreichend? | G18 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta, öffentlich), D7, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 G2 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`. `rules_housekeeping` plant die Kapitel innerhalb einer Stunde ein; sofort: `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer und Anteil der Gegenprüfung je Kapitel in BETRIEB 9 eintragen.
2. Referenzmenge der Zonen von Treillières durch die Entwicklung (Sollwerte am Text, Spez. 11.4) und Abnahme Plan 3.4 messen: falsche Pflichtwerte ≤ 5 %, `unknown` ≤ 15 %. Dabei prüfen: Wie oft ergeben RW24/RW25 (`sector_mismatch`, `no_marker`, Verneinungswörter) falsches `unknown`? Wirkung der Gegenprüfung (RW19). Bei Bedarf Prompt nachschärfen (Prüfsumme erkennt Änderungen) bzw. `ENGINE_VERSION` erhöhen (Neubewertung ohne Kosten).
3. Erst danach Beta für `rules_simulation` erwägen.
4. Später: Korrekturformular aus dem Schema statt JSON (RW15); OCR für Seiten ohne Textschicht (RW03); mehrbändige Reglements, wenn das Einzugsgebiet solche Pläne enthält (RW23).

### 4.2 Auslieferung und Betrieb

1. **Unraid in Betrieb nehmen** nach Unraid README 2–4 (durch den Nutzer: DNS, Reverse Proxy, Code auf den Server). Danach TLS, Authentik aus dem API-Container, `staff-add`, Login prüfen.
2. **G1 und G2 auf Unraid:** ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr` → `*.cloud.ovh.net`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`); `.env` mit `ANTHROPIC_API_KEY`; Flags `site_selection` und `rules_simulation` für `architect` (README 9, 10). Migration 0004 läuft beim Ausliefern mit.
3. Überwachung: Uptime Kuma mit `/api/health/ready`, `/api/health/jobs` und Authentik; Alarm auf Logs `rules_extract_failed`, `rules_budget_exceeded`, `road_import_implausible`; Frische der Sicherung (README 7).
4. Offsite-Kopie von `BACKUP_DIR` und Appdata; erste Wiederherstellungsübung (BETRIEB 6).
5. SMTP nach E2 eintragen; Testmail über `POST /api/v1/admin/ops/test-mail`.
6. GitHub: Schutz des Hauptzweigs einrichten (infra/README); Caddy-Ersetzungen beim nächsten Caddy-Release prüfen (A27).
7. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6, 6.9): Staff-E-Mail, Mailadresse in Jobs (A12), IP-HMAC (A7), Adressvorschläge im Arbeitsspeicher (G22), IP an IGN (G15); Claude API erhält nur Planunterlagen, Nutzungsbedingungen für gewerblichen Einsatz prüfen.
8. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.3 Hinweise für spätere Module

- **G3:** Zonenstatus `outdated` und Warnungen `rules_outdated`, `plan_update_failed`, `zone_coverage_incomplete` (`uncovered_share`) im Baurahmen berücksichtigen (RW21, RW27); Vorrang spezifischer vor `any`-Regeln wie `service.apply_override` (RW27); Wirkung überlagernder Vorgaben festlegen (Espace boisé classé, Baulinie `typepsc 15`, RW13); Standard-Geschosshöhen bei Geschossangaben (Plan 3.5); Abstände `unknown` im Lageplan markieren; Lotissement-Straßen als „voie“ nach PLU (G04); unsichere Straßenkanten (`edges_need_review`, G23).
- **A:** Frage „Lotissement?“ an den Kunden (RW16); Prüfung von Grenzen und Simulation im Anfrage-Detail mit den Büro-Endpunkten aus G1 und G2; Büro-Prüfliste auf Projekte mit Anfrage beschränken (G21); Anfrage ohne Baurahmen außerhalb des Einzugsgebiets (G18); `retention_cleanup` erweitern (A11); `DELETE /projects/{id}` gegen Aufbewahrung abwägen (S10).

### 4.4 Korrekturen an der Spezifikation (offen)

Prüfung vom 13.09.2026 (Lösung im Plan in Klammern): S1 Winkeltoleranz (Plan 3.7), S2 Firstrichtung Flachdach (3.8), S3 Neuprüfung beim Absenden (3.10), S4 Einzelabweichungen (teilweise), S5 Zustände (teilweise), S6 Preise an Typ-Identität (3.7), S7 keine Entwurfsregeln beim Kunden (durch D11 überholt), S8 Messpunkt Traufhöhe, S9 Queue `sandbox`, S10 Löschrecht vs. Aufbewahrung, S11 Paritätstest Lärche (teilweise), S12 Attikahöhe im Flachdach-Testmodell, S13 Spezifikation aufteilen, **S14 Leitplanken L2 und L6, 3.4, 4.2 (`rule_set`), 5.2.3 Schritt 5, 5.2.5, 5.9.1, 5.10.2 an D11 anpassen** (Plan 7, ANNAHMEN RW-Abschnitt).

### 4.5 Weitere Punkte

1. Einwilligung zur Datenweitergabe fehlt im Mockup (Spez. Anh. E.2 M10).
2. Oberflächenänderungen dieser Session (Status „veraltet“, Warnungen, Büro-Knöpfe „Erneut versuchen“/„Neu auswerten“) im Browser ansehen; bisher nur Komponententests.

## 5. Empfohlener nächster Schritt

1. Nutzer trägt den Schlüssel der Claude API ein → 4.1 Punkt 1–2 (echte Auswertung, Referenzmenge, Wirkung der neuen Schranken).
2. Priorität 1 aus Abschnitt 3 (Authentik-Hostname, E2) → Unraid nach 4.2 Punkt 1–2.
3. Danach nächstes Modul nach Plan 5: **G3 Baurahmen** (Plan 3.5; Spezifikation 5.3 und 5.9 vor Code vollständig lesen).

## 6. Hinweise und Stolperstellen

- **Befehle:** Backend-Prüfungen `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"`. Nach neuen Abhängigkeiten zuerst `docker compose --profile dev build backend-dev` (sonst z. B. `No module named 'pypdf'`). Frontend `corepack pnpm …` im Ordner `frontend` (aus dem Wurzelordner zieht Corepack pnpm 12). `python` im Host ist ein Store-Platzhalter; den Container nutzen. Git Bash: bei `docker -v` oder `docker exec -w` mit Linux-Pfaden `MSYS_NO_PATHCONV=1`.
- **Skripte mit Sonderzeichen:** `node -e "…"` und Heredocs im Bash-Werkzeug zerbrechen an Backticks, `$$` und `'`. Längere Änderungen als Datei im Scratchpad schreiben und mit `node` ausführen; kurze mit dem Edit-Werkzeug.
- **Unsichtbare Zeichen:** `backend/app/rules/domain/text.py` enthält in `_TRANSLATE` geschützte Leerzeichen (U+00A0, U+202F) und einen weichen Trennstrich. Beim vollständigen Neuschreiben der Datei gingen sie verloren; mit `git diff` prüfen.
- **Formatierer:** `ruff format` ändert Dateien; danach vor dem Edit-Werkzeug neu lesen. Das `# type: ignore[arg-type]` an `messages=` in `claude.py` ist nötig, auch wenn mypy es einmal als unbenutzt meldet.
- **E2E lokal unter Windows:** Chromium von Playwright löst `oidc.localhost` nicht auf; Tests mit Büro-Anmeldung laufen nur in der CI. Lokal Flags per `flag-set … --all`, `corepack pnpm exec playwright test -g Kunde`, danach zurücksetzen. G2-Seed: `docker compose cp backend/tests api:/tmp/tests` und `python -m tests.e2e_seed_rules` (README).
- **Tests G2:** `FakeExtractor` bildet aus einer Auswertungsantwort die Gegenprüfung; `[uh_output(), uh_output(footprint=0.3)]` heißt „Gegenprüfung liest bei der Grundfläche anders“. Das Original-PDF (6,8 MB) liegt nicht im Repository; `rules_support.py` setzt es aus der Textschicht.
- **CI:** Der Security-Job baut Caddy mit `xcaddy`; ein Netzfehler zu `sum.golang.org` ließ den Lauf des Hand-off-Commits `8cf8a27` scheitern (kein Codefehler). Bei gleichem Fehler den Lauf wiederholen: `gh run rerun <id> --failed`.
- **Jobarten registrieren:** `enqueue` braucht die Jobart; `app/rules` importiert `app.rules.jobs` lokal in den Funktionen (sonst Importzyklus).
- **Kosten der Claude API:** Aufrufe mit Schlüssel kosten; `--force` und „Neu auswerten“ werten vollständig neu aus. Ohne `force` werden gespeicherte Teile genutzt. Budget in der Abdeckung.
- **Parallele Sessions im selben Ordner:** Dateien vor jeder Änderung neu einlesen; `docker compose up --build` baut den Arbeitsstand mit.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten. Lokaler G1-Test-Stack `emprise-g1` (Datenbank läuft noch): `docker compose -p emprise-g1 down -v`.
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025. **Lokaler Login:** `ops@emprise.local`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen. Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`.
- **Rate-Limits beim Testen:** viele Projekte oder Grundstücke von derselben IP → 429; `EMPRISE_PROJECT_CREATE_LIMIT_PER_HOUR`, `EMPRISE_SITE_WRITE_LIMIT_PER_HOUR` hochsetzen.
- **Periodische Importe** (Kataster, Planstand) starten beim ersten Worker-Start und belasten externe Dienste; von Hand importierte Testdaten mit `--force` (Kataster) bzw. über `tests.e2e_seed_rules`.
- **FastAPI 0.141:** jede neue öffentliche Route in `test_access_policies.py` eintragen; `openapi.json` nach API-Änderungen neu erzeugen, dann `pnpm api:types`.
- **Browser-Bereich:** Screenshots von `localhost` funktionieren, von `file://` nicht. **Authentik:** nach der ersten TOTP-Einrichtung neu anmelden (A24).

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und die Einträge vom 14.09.2026 in AENDERUNGEN.md. Prüfe mit git status und gh run list, ob alles committet ist und die CI grün ist. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1, die du von mir brauchst.
```
