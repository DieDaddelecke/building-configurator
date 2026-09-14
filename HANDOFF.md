# Hand-off für die nächste Session

> **Stand:** 14.09.2026 · **Letzte Session:** G1 abgeschlossen und nach GitHub gepusht, CI repariert, Umsetzungsplan für G2 auf Entscheidung D11 umgestellt, Modul G2 Regelwerk als automatische Simulation umgesetzt, committet und gepusht
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md) (drei Einträge vom 14.09.2026).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Commits: R0 (`1f4b646`, `c606387`), G1 (`cc48386`), CI und Images (`50c6bc7`, `dcef07a`, `e00f2a6`), danach Plan D11 und G2 (siehe `git log`). CI mit Backend, Frontend, E2E, Geheimnis- und Image-Scan; Ergebnis des Laufs für G2 in `gh run list` prüfen.
- **R0 Plattform (Plan 3.2):** anbieterunabhängiger Teil fertig; Überwachung, Offsite-Sicherung, Mail offen. Festlegungen [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **Betrieb bis zur Beta:** [deploy/unraid/README.md](deploy/unraid/README.md) (Emprise, Authentik, G1 Abschnitt 9, G2 Abschnitt 10), lokal geprüft, **noch nicht auf Unraid ausgeliefert**.
- **G1 Grundstück (Plan 3.3):** fertig, lokal intern freigeschaltet. ANNAHMEN G01–G21, [docs/BETRIEB.md](docs/BETRIEB.md) 8.
- **G2 Regelwerk (Plan 3.4 in der Fassung mit D11):** umgesetzt und getestet.
  - Backend `backend/app/rules` (Fachlogik in `domain/`), Adapter `backend/app/integrations/gpu.py` und `claude.py`, Migration `0003`, Jobs `plu_import` (wöchentlich) und `rules_extract`, CLI `plu-import` und `rules-extract`.
  - Frontend: Regeln als Simulation auf `/grundstueck` (Flag `rules_simulation`), Büro `/buero/regeln` (Abdeckung, Kosten, Regelwerk, Korrektur für die Zone) und Korrektur je Projekt in `/buero/grundstuecke/:id`.
  - Tests: Backend 168, Frontend 24, ruff/mypy/ESLint/tsc/Build grün; E2E `frontend/e2e/rules.spec.ts` mit `backend/tests/e2e_seed_rules.py`, Kundenpfad lokal grün.
  - **Noch keine echte Auswertung mit der Claude API** (kein Schlüssel). Referenzmenge, Kosten, Dauer und Anteil `unknown` ungemessen (ANNAHMEN RW18).
  - Festlegungen ANNAHMEN RW01–RW18, BETRIEB 9.
- **Lokaler Stack `emprise`** (Port 8080): G1 und G2 aktiv; Kataster und Planstand Treillières importiert; Kapitel ohne Schlüssel `failed: not_configured`, Zone Uh mit aufgezeichneter Auswertung eingespielt; Flags `site_selection` und `rules_simulation` für `architect`; Konto `ops@emprise.local` (`architect, ops`).
- **Umsetzungsplan:** als Ganzes Vorschlag; R0, G1, G2 beauftragt; D1–D4 und D11 entschieden, D9 entfällt, D12 neu (Plan 9); Überarbeitung und Prüfprotokoll in Plan 10.3.
- **Spezifikation:** unverändert; Korrekturen S1–S14 offen (4.4). **Mockup, Dokumentation.html:** unverändert.

## 2. Ergebnisse, die nur im Chat standen

- **Planwerk Treillières:** PLUi Erdre et Gesvres (`DU_244400503`, Stand 04.03.2026, 333 Seiten mit Textschicht). Live-Import 36 s, 12 Zonenkapitel über das Inhaltsverzeichnis, 26 Zonen- und Sektorcodes, 1.668 überlagernde Vorgaben. Am Gemeinderand liefert der GPU Zonen von Nantes Métropole mit (RW01).
- **Zone Uh (Testgrundstück AD 65):** Bauband 5–20 m zur Straße, seitlich auf der Grenze oder ≥ 3 m, Grundfläche 25 %, Traufe 7 m, First 10 m (S. 97–100); Dach, Fassade, unversiegelte Fläche ohne Zahl. Die aufgezeichnete Antwort ergibt am echten PDF dieselben Seiten.
- **Zitatprüfung:** Ähnlichkeit ≥ 0,9 allein ließ „recul de 6 mètres“ gegen den Text „3 mètres“ als belegt durch (0,968). Deshalb Zahlenprüfung (RW07).
- **Kostenschätzung** ohne Messung: 1–2 $ je Kapitel, 10–25 $ je Planstand Treillières (BETRIEB 9). Preise laut Skill `claude-api` (Opus 5: 5 $ Eingabe, 25 $ Ausgabe je Million Token).
- **Browserprüfung G2:** Kundenseite, Abdeckung, Regelwerk, Korrektur je Projekt geprüft; Anzeigefehler behoben. Keine CSP-Verstöße.
- **Lokaler Test-Stack der G1-Session:** Compose-Projekt `emprise-g1` (Datenbank läuft noch, Volume `emprise-g1_db-data`) und Image `emprise-backend:dev-g1`. Entfernen: `docker compose -p emprise-g1 down -v`.
- **Aus der R0-Session:** DNS `building-configurator.aslani.work` existierte am 14.09. nicht; `aslani.work` liegt bei Cloudflare; Serverstandort nicht bestätigt.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env` eintragen); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU, z. B. Brevo, Scaleway TEM) | Spez. 16, BETRIEB 5 |
| 2 (vor Beta) | – | Rechtliche Prüfung der ungeprüften Simulation: Wortlaut der Hinweise, Haftung | Plan 6.9, RW16 |
| 2 | – | Wer schreibt die Hinweistexte L7 (`notice.cadastre_accuracy`, `notice.risks_public_data`, `notice.rules_simulation`, `notice.rules_lotissement`)? Bis dahin Rückfalltext | G16, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN; Hinweis genügt oder eigener Kachel-Proxy? Empfehlung Hinweis | G15 |
| 2 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro | Plan 9 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 (vor H2) | D12 | Wie stark schränken simulierte Regeln den Konfigurator ein? Vorschlag: verifizierte Regeln wie Grenzen, `unknown` nur Hinweis, Anfrage immer möglich | Plan 9 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Außerhalb des Einzugsgebiets bis Modul A nur Hinweis – ausreichend? | G18 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta, öffentlich), D7, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 G2 abschließen (sobald ein Schlüssel eingetragen ist)

1. Lokal `docker compose up -d` mit `EMPRISE_ANTHROPIC_API_KEY`, dann `docker compose exec api python -m app.cli rules-extract --pending`. Kosten und Dauer je Kapitel in BETRIEB 9 eintragen.
2. Referenzmenge der Zonen von Treillières durch die Entwicklung (Sollwerte am Text, Spez. 11.4) und Abnahme Plan 3.4 messen: falsche Pflichtwerte ≤ 5 %, `unknown` ≤ 15 %. Bei Bedarf Prompt nachschärfen und `PROMPT_VERSION` in `backend/app/rules/domain/__init__.py` erhöhen.
3. Erst danach Beta für `rules_simulation` erwägen.
4. Später: Korrekturformular aus dem Schema statt JSON (RW15); OCR für Seiten ohne Textschicht (RW03).

### 4.2 Auslieferung und Betrieb

1. **Unraid in Betrieb nehmen** nach Unraid README 2–4 (durch den Nutzer: DNS, Reverse Proxy, Code auf den Server). Danach TLS, Authentik aus dem API-Container, `staff-add`, Login prüfen.
2. **G1 und G2 auf Unraid:** ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr` → `*.cloud.ovh.net`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`); `.env` mit `ANTHROPIC_API_KEY`; Flags `site_selection` und `rules_simulation` für `architect` (README 9, 10).
3. Überwachung: Uptime Kuma mit `/api/health/ready`, `/api/health/jobs` und Authentik; Alarm auf Logs `rules_extract_failed`, `rules_budget_exceeded`; Frische der Sicherung (README 7).
4. Offsite-Kopie von `BACKUP_DIR` und Appdata; erste Wiederherstellungsübung (BETRIEB 6).
5. SMTP nach E2 eintragen; Testmail über `POST /api/v1/admin/ops/test-mail`.
6. GitHub: Schutz des Hauptzweigs einrichten (infra/README); Caddy-Ersetzungen beim nächsten Caddy-Release prüfen (A27).
7. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6, 6.9): Staff-E-Mail, Mailadresse in Jobs (A12), IP-HMAC (A7), Adress-Cache als HMAC (G13), IP an IGN (G15); Claude API erhält nur Planunterlagen, Nutzungsbedingungen für gewerblichen Einsatz prüfen.
8. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.3 Hinweise für spätere Module

- **G3:** Wirkung überlagernder Vorgaben festlegen (Espace boisé classé, Baulinie `typepsc 15`, RW13); Standard-Geschosshöhen bei Geschossangaben (Plan 3.5); Abstände `unknown` im Lageplan markieren; Lotissement-Straßen als „voie“ nach PLU (G04).
- **A:** Frage „Lotissement?“ an den Kunden (RW16); Prüfung von Grenzen und Simulation im Anfrage-Detail mit den Büro-Endpunkten aus G1 und G2; Büro-Prüfliste auf Projekte mit Anfrage beschränken (G21); Anfrage ohne Baurahmen außerhalb des Einzugsgebiets (G18); `retention_cleanup` erweitern (A11); `DELETE /projects/{id}` gegen Aufbewahrung abwägen (S10).

### 4.4 Korrekturen an der Spezifikation (offen)

Prüfung vom 13.09.2026 (Lösung im Plan in Klammern): S1 Winkeltoleranz (Plan 3.7), S2 Firstrichtung Flachdach (3.8), S3 Neuprüfung beim Absenden (3.10), S4 Einzelabweichungen (teilweise), S5 Zustände (teilweise), S6 Preise an Typ-Identität (3.7), S7 keine Entwurfsregeln beim Kunden (durch D11 überholt), S8 Messpunkt Traufhöhe, S9 Queue `sandbox`, S10 Löschrecht vs. Aufbewahrung, S11 Paritätstest Lärche (teilweise), S12 Attikahöhe im Flachdach-Testmodell, S13 Spezifikation aufteilen, **S14 Leitplanken L2 und L6, 3.4, 4.2 (`rule_set`), 5.2.3 Schritt 5, 5.2.5, 5.9.1, 5.10.2 an D11 anpassen** (Plan 7, ANNAHMEN RW-Abschnitt).

### 4.5 Weitere Punkte

1. Einwilligung zur Datenweitergabe fehlt im Mockup (Spez. Anh. E.2 M10).

## 5. Empfohlener nächster Schritt

1. CI-Lauf des G2-Commits prüfen (`gh run list`); bei Fehlern zuerst beheben.
2. Nutzer trägt den Schlüssel der Claude API ein → 4.1 Punkt 1–2 (echte Auswertung, Referenzmenge, Kosten).
3. Priorität 1 aus Abschnitt 3 (Authentik-Hostname, E2) → Unraid nach 4.2 Punkt 1–2.
4. Danach nächstes Modul nach Plan 5: **G3 Baurahmen** (Plan 3.5; Spezifikation 5.3 und 5.9 vor Code vollständig lesen).

## 6. Hinweise und Stolperstellen

- **Befehle:** Backend-Prüfungen `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"`. Frontend `corepack pnpm …` im Ordner `frontend` (aus dem Wurzelordner zieht Corepack pnpm 12 und bricht ab). `python` im Host ist ein Store-Platzhalter; den Container nutzen. Git Bash: bei `docker -v` mit Linux-Pfaden `MSYS_NO_PATHCONV=1`.
- **Skripte mit Anführungszeichen:** Heredocs mit `'` oder `$$` im Bash-Werkzeug brechen ab oder verändern Text (ein `$$` in einer Migration wurde zu `$`). Längere Änderungen als Datei im Scratchpad schreiben und mit `node` ausführen.
- **E2E lokal unter Windows:** Chromium von Playwright löst `oidc.localhost` nicht auf; Tests mit Büro-Anmeldung laufen nur in der CI. Lokal Flags per `flag-set … --all` setzen, `corepack pnpm exec playwright test -g Kunde`, danach Flags zurücksetzen. G2-Seed: `docker compose cp backend/tests api:/tmp/tests` und `python -m tests.e2e_seed_rules` (README).
- **Planunterlage im Test:** Das Original-PDF (6,8 MB) liegt nicht im Repository; `backend/tests/rules_support.py` setzt aus der Textschicht ein PDF. Positionen im Kapitel-PDF sind im Ausschnitt und im Original gleich.
- **Jobarten registrieren:** `enqueue` braucht die Jobart; `app/rules` importiert `app.rules.jobs` deshalb lokal in den Funktionen (sonst Importzyklus).
- **Kosten der Claude API:** Jeder `rules-extract` mit Schlüssel kostet; `--force` wertet auch unveränderte Kapitel neu aus. Budget in der Abdeckung sichtbar.
- **Parallele Sessions im selben Ordner:** Dateien vor jeder Änderung neu einlesen; `docker compose up --build` baut den Arbeitsstand mit.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025. **Lokaler Login:** `ops@emprise.local`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen.
- **Rate-Limits beim Testen:** viele Projekte oder Grundstücke von derselben IP → 429; für Messskripte `EMPRISE_PROJECT_CREATE_LIMIT_PER_HOUR`, `EMPRISE_SITE_WRITE_LIMIT_PER_HOUR` hochsetzen.
- **Periodische Importe** (Kataster, Planstand) starten beim ersten Worker-Start und belasten externe Dienste; von Hand importierte Testdaten mit `--force` (Kataster) bzw. über `tests.e2e_seed_rules`.
- **FastAPI 0.141:** jede neue öffentliche Route in `test_access_policies.py` eintragen; `openapi.json` nach API-Änderungen neu erzeugen, dann `pnpm api:types`.
- **Browser-Bereich:** Screenshots von `localhost` funktionieren, von `file://` nicht.
- **Authentik:** nach der ersten TOTP-Einrichtung neu anmelden (A24).

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und die Einträge vom 14.09.2026 in AENDERUNGEN.md. Prüfe mit git status und gh run list, ob alles committet ist und die CI grün ist. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1, die du von mir brauchst.
```
