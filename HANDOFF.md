# Hand-off für die nächste Session

> **Stand:** 14.09.2026 · **Letzte Sessions (parallel):** R0 Plattform und Betrieb auf Unraid mit Authentik; G1 Grundstück umgesetzt und intern freigeschaltet
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md) (zwei Einträge vom 14.09.2026).

---

## 1. Aktueller Stand

- **Git:** `main`: `1f4b646` (R0 und Dokumente), `c606387` (R0-Nacharbeiten: Unraid, Authentik, `storage-init`), `cc48386` (G1), danach CI- und Image-Korrekturen. Remote `origin`: privates Repo https://github.com/DieDaddelecke/building-configurator, `main` gepusht.
- **R0 Plattform (Plan 3.2):** anbieterunabhängiger Teil fertig; anbietergebundene Teile (Überwachung, Offsite-Sicherung, Mail) offen. Festlegungen [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **Betrieb bis zur Beta:** [deploy/unraid/README.md](deploy/unraid/README.md) mit Emprise- und Authentik-Stack, lokal geprüft, **noch nicht auf Unraid ausgeliefert**.
- **G1 Grundstück (Plan 3.3):** umgesetzt, getestet und committet.
  - Backend `backend/app/site` + Adapter `backend/app/integrations`, Migration `0002`; Frontend Karte (MapLibre), `/grundstueck`, Büro-Prüfliste `/buero/grundstuecke`; E2E `frontend/e2e/site.spec.ts`.
  - Tests: Backend 109, Frontend 20, Build, ruff/mypy/ESLint/tsc grün. Der E2E-Kundenablauf lief lokal gegen den Produktions-Build; der Freischaltschritt per OIDC-Login im E2E läuft seit 14.09.2026 in der CI auf GitHub.
  - Festlegungen [docs/ANNAHMEN.md](docs/ANNAHMEN.md) G01–G21, Betrieb [docs/BETRIEB.md](docs/BETRIEB.md) Abschnitt 8.
- **Lokaler Stack `emprise`** (Port 8080) läuft mit G1: Treillières importiert (8.753 Parzellen, 5.134 Straßenachsen), Flag `site_selection` für `architect`, Konto `ops@emprise.local` mit Rollen `architect, ops`.
- **Umsetzungsplan:** als Ganzes Vorschlag; R0 und G1 beauftragt; D1, D2 (intern), D3, D4 entschieden (Plan 9); 3.3, 3.6 und 8 an G1-Entscheidungen angepasst.
- **Spezifikation:** unverändert; Korrekturen aus 4.3 offen. **Mockup, Dokumentation.html:** unverändert.

## 2. Ergebnisse, die nur im Chat standen

- **Echte Daten statt Annahmen:** In Treillières liegen Lotissement-Straßen und Grünstreifen auf einer gemeinsamen Parzelle (AD 71). Ohne BD-TOPO-Achsen erkannte G1 dort keine Straße. Die Einordnung wurde an Zeichnungen von 7 Grundstücken und zwei Rastern mit je 12 Grundstücken geprüft (G04–G06, G21).
- **Stichprobe 300 Parzellen:** Eckgrundstücke 38 % → 17 % nach neuer Regel; übrige Prüffälle sind überwiegend echte Hinterlieger- und Pfeifenstielgrundstücke.
- **Lokaler Test-Stack der G1-Session:** Compose-Projekt `emprise-g1` (gestoppt, Volume `emprise-g1_db-data` mit ganz Treillières) und Image `emprise-backend:dev-g1`. Entfernen: `docker compose -p emprise-g1 down -v`.
- **Aus der R0-Session:** DNS `building-configurator.aslani.work` existierte am 14.09. nicht; `aslani.work` liegt bei Cloudflare; Serverstandort Frankreich nicht bestätigt.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | deploy/unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU, z. B. Brevo, Scaleway TEM) | Spez. 16, BETRIEB 5 |
| 2 | – | Wer schreibt die Hinweistexte L7 für G1 (`notice.cadastre_accuracy`, `notice.risks_public_data`)? Bis dahin Rückfalltext | ANNAHMEN G16, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln kommen direkt vom IGN (IP der Besucher); Hinweis genügt oder eigener Kachel-Proxy? Empfehlung Hinweis | ANNAHMEN G15 |
| 2 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (vor Beta mit Kundendaten) | Plan 9 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 | – | G3: Plan verlangt „10 Steckbriefe fachlich prüfen“ – ebenfalls an den Anfrageeingang verlegen? (vgl. Entscheidung zu G1) | Plan 3.5, 8 |
| 3 | – | ODbL des Katasters vor Modul V rechtlich klären; Géorisques-Token vor öffentlichem Start beantragen | ANNAHMEN G12, G17 |
| 3 | – | Außerhalb des Einzugsgebiets bis Modul A nur Hinweis – ausreichend? | ANNAHMEN G18 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta, öffentlich), D7, D9, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 Auslieferung und Betrieb

1. **Unraid in Betrieb nehmen** nach deploy/unraid README 2–4 (durch den Nutzer: DNS, Reverse Proxy, Code auf den Server). Danach TLS, Erreichbarkeit von Authentik aus dem API-Container, `staff-add`, Login prüfen.
2. **G1 auf Unraid:** ausgehenden Zugang zu `data.geopf.fr`, `cadastre.data.gouv.fr` (→ `*.cloud.ovh.net`), `georisques.gouv.fr` sicherstellen; Import läuft beim ersten Worker-Start; `flag-set site_selection --role architect` (README 9, BETRIEB 8).
3. Überwachung: Uptime Kuma mit `/api/health/ready`, `/api/health/jobs` und Authentik; Frische der Sicherung (README 7).
4. Offsite-Kopie von `BACKUP_DIR` und Appdata; erste Wiederherstellungsübung (BETRIEB 6).
5. SMTP nach E2 eintragen; Testmail über `POST /api/v1/admin/ops/test-mail`.
6. CI auf GitHub vollständig grün seit 14.09.2026 (Backend, Frontend, E2E, Geheimnis- und Image-Scan). Offen: Schutz des Hauptzweigs einrichten (infra/README); Caddy-Ersetzungen beim nächsten Release prüfen (A27).
7. Verarbeitungsverzeichnis anlegen (Plan 4.1 Kriterium 6, 6.9): Staff-E-Mail, Job-Nutzlast mit Mailadresse (A12), IP-HMAC (A7), Geokodierungs-Cache als HMAC (G13), IP an IGN beim Kartenaufruf (G15).
8. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.2 Hinweise für spätere Module

- **A:** `retention_cleanup` um „ohne Kontakt und ohne Anfrage“ erweitern (A11).
- **A:** Grenzen des Grundstücks im Anfrage-Detail zur Prüfung zeigen; Büro-Prüfliste `/buero/grundstuecke` auf Projekte mit Anfrage beschränken; unbestätigte Kundenkorrekturen hindern das Absenden nicht (G21, Plan 3.6).
- **A:** Anfrage ohne Baurahmen für Grundstücke außerhalb des Einzugsgebiets (G18, Plan 2.1).
- **A:** `DELETE /projects/{id}` gegen die Aufbewahrung beim Büro abwägen (S10).
- **G2/G3:** Ob Lotissement-Straßen auf Privatparzellen als „voie“ zählen, regelt der PLU; bei der Regelerfassung beachten (G04).

### 4.3 Korrekturen an der Spezifikation (Prüfung 13.09.2026, unverändert offen)

Befunde der Prüfung vom 13.09.2026 (Lösung im Plan in Klammern): S1 Winkeltoleranz (Plan 3.7), S2 Firstrichtung Flachdach (3.8), S3 Neuprüfung beim Absenden (3.10), S4 Einzelabweichungen (teilweise), S5 Zustände (teilweise), S6 Preise an Typ-Identität (3.7), S7 keine Entwurfsregeln beim Kunden (3.4), S8 Messpunkt Traufhöhe (offen), S9 Queue `sandbox` „ohne Internetzugang“ (offen), S10 Löschrecht vs. Aufbewahrung (offen), S11 Paritätstest Lärche (teilweise), S12 Attikahöhe im Flachdach-Testmodell (offen), S13 Spezifikation aufteilen (offen). Dazu Plan Kapitel 7 und die Abweichungen in `docs/ANNAHMEN.md`.

### 4.4 Weitere Punkte

1. Einwilligung zur Datenweitergabe fehlt im Mockup (Spez. Anh. E.2 M10).

## 5. Empfohlener nächster Schritt

1. Nutzer entscheidet Priorität 1 aus Abschnitt 3 (Authentik-Hostname/Cloudflare, E2).
2. Unraid nach 4.1 Punkt 1–2 in Betrieb nehmen und G1 dort intern freischalten.
3. Danach nächstes Modul nach Plan 5: **G2 Regelwerk** (Plan 3.4; Spezifikation 5.2 vor Code vollständig lesen).

## 6. Hinweise und Stolperstellen

- **Parallele Sessions im selben Ordner:** Abstimmung per `ListAgents`/`SendMessage`, Dateien vor jeder Änderung neu einlesen. `docker compose up --build` baut den Arbeitsstand samt fremder halbfertiger Dateien; für isolierte Tests eigenes Compose-Projekt (`-p <name>` mit Override `ports: !reset []`) oder `git worktree`.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- **Befehle:** Backend-Prüfungen `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && mypy app && pytest"`. Frontend `corepack pnpm …` im Ordner `frontend` (aus dem Wurzelordner zieht Corepack pnpm 12 und bricht ab). `python` im Host ist ein Store-Platzhalter; `py` oder den Container nutzen. Git Bash: bei `docker -v` mit Linux-Pfaden `MSYS_NO_PATHCONV=1`; Skripte im Scratchpad nicht `inspect.py` nennen (verdeckt die Standardbibliothek).
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025.
- **Lokaler Login:** `ops@emprise.local` per `staff-add`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen.
- **Rate-Limits beim Testen:** Viele Projekte oder Grundstücke von derselben IP laufen in 429; für Messskripte `EMPRISE_PROJECT_CREATE_LIMIT_PER_HOUR` und `EMPRISE_SITE_WRITE_LIMIT_PER_HOUR` hochsetzen.
- **Massentests belasten externe Dienste:** Jedes gebildete Grundstück erzeugt einen `site_enrich`-Job mit Aufrufen an Géorisques (3–6 s je Aufruf). Nach Messläufen wartende Jobs löschen.
- **Periodischer Katasterimport** startet beim ersten Worker-Start; ein von Hand gestarteter Import mit anderem Stand wird wegen der Mengenprüfung abgelehnt (`--force` für Testdaten).
- **FastAPI 0.141:** Routen mit `fastapi.routing.iter_route_contexts` durchlaufen; jede neue öffentliche Route in `test_access_policies.py` eintragen.
- **`openapi.json`** nach API-Änderungen neu erzeugen, dann `pnpm api:types`; ein Test prüft das.
- **Browser-Bereich:** Screenshots von `localhost`-Seiten funktionieren, von lokalen Dateien (`file://`) nicht. Lagepläne zur Prüfung mit matplotlib im Container als PNG erzeugen und mit Read ansehen.
- **Authentik:** nach der ersten TOTP-Einrichtung neu anmelden (A24); Blueprint-Änderungen nach Neustart von `worker`.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und die beiden Einträge vom 14.09.2026 in AENDERUNGEN.md. Prüfe mit git status, welche Änderungen offen sind. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1, die du von mir brauchst.
```
