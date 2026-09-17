# Hand-off für die nächste Session

> **Stand:** 17.09.2026 · **Letzte Session:** G1 um Weg E ergänzt (Grundstück frei zeichnen und bemaßen, ohne Kataster und ohne Bebaubarkeitscheck), committet, CI-Stand noch ungeprüft (nicht gepusht)
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Letzter Commit `11a6e64` (Weg E) liegt **einen Commit vor `origin/main`** – noch nicht gepusht, CI dafür also noch nicht gelaufen. Davor `b8cae60` (G3 Nacharbeiten), gepusht, CI grün.
- **R0 Plattform (Plan 3.2):** anbieterunabhängiger Teil fertig; Überwachung, Offsite-Sicherung, Mail offen. [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **Betrieb bis zur Beta:** [deploy/unraid/README.md](deploy/unraid/README.md) (G1 Abschnitt 9, G2 Abschnitt 10, G3 Abschnitt 11), lokal geprüft, **noch nicht auf Unraid ausgeliefert**.
- **G1 Grundstück (Plan 3.3):** fertig, lokal intern freigeschaltet. ANNAHMEN G01–G25, [docs/BETRIEB.md](docs/BETRIEB.md) 8. **Neu: Weg E** – Grundstück ohne Kataster frei zeichnen und bemaßen (`site.origin = manual_sketch`), G2/G3 werden dafür nicht aufgerufen, kein Baurahmen, kein Steckbrief; eigener Hinweistext `notice.manual_sketch`. ANNAHMEN G26–G30, Plan 3.3 (Zusatz), Kapitel 7, 9 (D13), 10.4.
- **G2 Regelwerk (Plan 3.4):** fertig, ANNAHMEN RW01–RW27, BETRIEB 9. **Noch keine echte Auswertung mit der Claude API** (kein Schlüssel); die aufgezeichnete Auswertung im lokalen Stack kennt `setback_street.band` noch nicht.
- **G3 Baurahmen (Plan 3.5):** umgesetzt, getestet, lokal intern freigeschaltet. Plan und Prüfprotokoll: [docs/PLAN_G3_BAURAHMEN.md](docs/PLAN_G3_BAURAHMEN.md), Festlegungen ANNAHMEN BR01–BR15, Betrieb BETRIEB 10. Zwei Konturen statt `B(0)`/`B(H_max)`; Bauband wirkt auf die Fläche bei ganzem Baukörper; kein Zwischenspeicher, Prüfsumme über den Inhalt der Eingaben.
- **Lokaler Stack `emprise`** (Port 8080): mit dem Stand dieser Session neu gebaut, Migration 0006 angewendet; Flags `site_selection`, `rules_simulation`, `envelope_simulation` für `architect`; Konto `ops@emprise.local`.
- **Umsetzungsplan:** R0, G1, G2, G3 beauftragt; D1–D4, D11 entschieden, D12 und **D13 (neu)** offen (Plan 9); Abweichungen in Plan 7. **Spezifikation:** unverändert, Korrekturen S1–S14 offen (4.4). **Mockup, Dokumentation.html:** unverändert.

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **„So viel wie möglich lokal, keine Drittanbieter“** auf Nachfrage präzisiert: Mailversand (E2) darf ein EU-Drittanbieter sein (Brevo/Scaleway TEM, wegen Zustellbarkeit), kein Eigenbetrieb eines SMTP-Servers; die Claude API bleibt als Kernfunktion ausdrücklich ausgenommen. Memory `project-hosting-unraid` entsprechend präzisiert.
- **Idee „Grundstück selbst zeichnen“** vom Nutzer eingebracht, gemeinsam zu einem Konzept ausgearbeitet (Entscheidungen per Rückfrage: Zusatz zu G1 statt eigenem Modul, freies Koordinatenraster ohne Kartenbezug, Adresse Pflicht), in UMSETZUNGSPLAN.md 3.3 ausformuliert und mit Selbstprüfung versehen (Prüfprotokoll 10.4: vier Logikfehler gefunden und behoben, u. a. dass ein vollständig bemaßtes Polygon mathematisch überbestimmt ist – die letzte Kante muss sich aus dem Schlusspunkt ergeben).
- **Browserprüfung von Weg E** am lokalen Stack: Zeichnen, Bemaßen mit Live-Vorschau, Absenden, Ergebnisansicht, Selbstüberschneidung vom Server abgelehnt, Deutsch/Französisch. Dabei zwei Anzeigefehler gefunden und noch in derselben Session behoben: Label „Surface (cadastre)“ bei einem Grundstück ganz ohne Kataster; ungerundete Klickkoordinaten (`34,391423349434085`) in den Bemaßungsfeldern.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter: EU-Drittanbieter akzeptiert (Nutzer, 17.09.2026), welcher konkret (z. B. Brevo, Scaleway TEM) noch offen | Spez. 16, BETRIEB 5 |
| 2 (vor Beta) | – | Rechtliche Prüfung der ungeprüften Simulation: Wortlaut der Hinweise, Haftung, Bezeichnungen der beiden Konturen **und der Hinweis für Weg E** (`notice.manual_sketch` darf nicht wie ein Bebaubarkeitscheck wirken) | Plan 6.9, RW16, Plan G3 10, Plan 3.3 |
| 2 | – | Wer schreibt die Hinweistexte L7 (`notice.cadastre_accuracy`, `notice.risks_public_data`, `notice.rules_simulation`, `notice.rules_lotissement`, `notice.envelope_simulation`, **`notice.manual_sketch`**)? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN; Hinweis genügt oder eigener Kachel-Proxy? Empfehlung Hinweis | G15 |
| 2 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro | Plan 9 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 (vor H2/R2) | D12 | Wie stark schränken simulierte Regeln den Konfigurator ein? Engste Kontur als Grenze, weiteste als Suchraum (Vorschlag) | Plan 9, BR01 |
| 3 (vor R2) | **D13** | **Neu:** Wie geht H2 mit einem Grundstück ohne Baurahmen um (Weg E)? Vorschlag: Platzierung ohne Abstandsprüfung, gezeichneter Umriss gilt direkt als Fläche | Plan 9, 3.3 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in den Umsetzungsplan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19, Plan 3.4 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Außerhalb des Einzugsgebiets bis Modul A nur Hinweis – ausreichend? | G18 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta, öffentlich), D7, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`. `rules_housekeeping` plant die Kapitel innerhalb einer Stunde ein; sofort: `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer und Anteil der Gegenprüfung je Kapitel in BETRIEB 9 eintragen.
2. **Wegen `g2-prompt-3` werten alle Kapitel neu aus** (gespeicherte Antworten passen nicht mehr zur Prüfsumme). Danach prüfen, ob `setback_street.band` gefüllt ist und der Hinweis `band_unclear` verschwindet.
3. Referenzmenge der Zonen von Treillières messen (Sollwerte am Text, Spez. 11.4): falsche Pflichtwerte ≤ 5 %, `unknown` ≤ 15 %; Wirkung der Gegenprüfung (RW19) und der Schranken RW24/RW25.
4. Danach `envelope-check --commune 44209` über **alle** Zonen wiederholen und den Anteil unvollständiger engster Konturen in BETRIEB 10 festhalten (BR12).
5. Erst danach Beta für `rules_simulation` und `envelope_simulation` erwägen.
6. Später: Korrekturformular aus dem Schema statt JSON (RW15); OCR für Seiten ohne Textschicht (RW03); mehrbändige Reglements (RW23).

### 4.2 Auslieferung und Betrieb

1. **Unraid in Betrieb nehmen** nach Unraid README 2–4 (durch den Nutzer: DNS, Reverse Proxy, Code auf den Server). Danach TLS, Authentik aus dem API-Container, `staff-add`, Login prüfen.
2. **G1, G2 und G3 auf Unraid:** ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr` → `*.cloud.ovh.net`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`); `.env` mit `ANTHROPIC_API_KEY`; Flags für `architect` (README 9–11). G3 und Weg E brauchen keinen neuen Zugang, G3 aber WeasyPrint im Image. Migration 0006 läuft beim Ausliefern mit.
3. Überwachung: Uptime Kuma mit `/api/health/ready`, `/api/health/jobs` und Authentik; Alarm auf Logs `rules_extract_failed`, `rules_budget_exceeded`, `road_import_implausible`; Frische der Sicherung (README 7).
4. Offsite-Kopie von `BACKUP_DIR` und Appdata; erste Wiederherstellungsübung (BETRIEB 6).
5. SMTP nach E2 eintragen (EU-Anbieter, siehe Abschnitt 3); Testmail über `POST /api/v1/admin/ops/test-mail`.
6. GitHub: Schutz des Hauptzweigs einrichten (infra/README); Caddy-Ersetzungen beim nächsten Caddy-Release prüfen (A27).
7. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6, 6.9): Staff-E-Mail, Mailadresse in Jobs (A12), IP-HMAC (A7), Adressvorschläge im Arbeitsspeicher (G22), IP an IGN (G15); Steckbriefe im Objektspeicher (BR10); Claude API erhält nur Planunterlagen.
8. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.3 Nächstes Modul und spätere Module

- **A Anfrage (Plan 3.6)** ist der nächste Schnitt: Kontakt mit E-Mail-Code, Einwilligung, Snapshot aus Grundstück und Baurahmen (`input_hash` aus G3 übernehmen, BR07), Mail mit Steckbrief (BR10), Anfragenliste, **Prüfung der Simulation durch das Büro** mit den Endpunkten `GET /admin/projects/{id}/site|rules|envelope`. Für Weg E entsteht keine Simulation zur Prüfung – die Anfrage müsste den gezeichneten Umriss trotzdem transportieren (noch nicht entworfen). Weiter offen: Frage „Lotissement?“ (RW16), Anfrage ohne Baurahmen außerhalb des Einzugsgebiets (G18), Büro-Prüfliste auf Projekte mit Anfrage beschränken (G21), `retention_cleanup` erweitern (A11, auch `envelope_sheet`), `DELETE /projects/{id}` gegen Aufbewahrung abwägen (S10).
- **H2** nutzt `envelope/domain` mit den Höhen der Konfiguration (Setback-Funktionen, Bauband-Bedingung `facade`, Flucht `fixed`) und legt `/buildable?height_m=` an (Plan 7); für Weg E siehe D13.
- **Vor Erweiterung des Einzugsgebiets:** CNIG-Typliste der überlagernden Vorgaben gegen den Standard prüfen (BR05).

### 4.4 Korrekturen an der Spezifikation (offen)

Prüfung vom 13.09.2026 (Lösung im Plan in Klammern): S1 Winkeltoleranz (Plan 3.7), S2 Firstrichtung Flachdach (3.8), S3 Neuprüfung beim Absenden (3.10), S4 Einzelabweichungen (teilweise), S5 Zustände (teilweise), S6 Preise an Typ-Identität (3.7), S7 keine Entwurfsregeln beim Kunden (durch D11 überholt), S8 Messpunkt Traufhöhe, S9 Queue `sandbox`, S10 Löschrecht vs. Aufbewahrung, S11 Paritätstest Lärche (teilweise), S12 Attikahöhe im Flachdach-Testmodell, S13 Spezifikation aufteilen, S14 Leitplanken L2 und L6 an D11 anpassen. Aus Plan 7 zusätzlich: Bauband als Flächenbedingung (5.2.4), zwei Auslegungen statt `B(0)`/`B(H_max)` (5.3.1), `/buildable` erst mit H2 (6.3), kein Höhenbezug in m NGF (5.9.4). **Neu:** ein fünfter Eingangsweg zum Grundstück (Weg E, 5.1.1) ohne Katasterbezug ist der Spezifikation noch nicht bekannt.

### 4.5 Weitere Punkte

1. Einwilligung zur Datenweitergabe fehlt im Mockup (Spez. Anh. E.2 M10).
2. Büro-Oberfläche aus G2 (Knöpfe „Erneut versuchen“, „Neu auswerten“, Status „veraltet“) im Browser ansehen; bisher nur Komponententests. Der Kundenpfad ist mit G3 und Weg E im Browser geprüft.

## 5. Empfohlener nächster Schritt

1. **Push entscheiden:** `11a6e64` (Weg E) ist committet, aber noch nicht gepusht – push freigeben, damit CI läuft, oder vorher noch etwas ändern.
2. Nutzer trägt den Schlüssel der Claude API ein → 4.1 Punkt 1–4 (echte Auswertung mit `band`, Referenzmenge, Wiederholung der G3-Messung).
3. Priorität 1 aus Abschnitt 3 (Authentik-Hostname, konkreter E2-Anbieter) → Unraid nach 4.2 Punkt 1–2.
4. Danach **Modul A** (Plan 3.6) als letztes Modul von R1; Spezifikation 5.10 und 10.2 vor Code lesen. Vorher klären, wie eine Anfrage ohne Simulation (Weg E) aussieht (4.3).

## 6. Hinweise und Stolperstellen

- **Befehle:** Backend-Prüfungen `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"` (MinIO und Mailpit müssen laufen, sonst scheitern `test_storage_ops`). Nach neuen Abhängigkeiten zuerst `uv lock` im Container, dann `docker compose --profile dev build backend-dev`. Frontend `corepack pnpm …` im Ordner `frontend`. Git Bash: bei `docker -v` oder `docker exec -w` mit Linux-Pfaden `MSYS_NO_PATHCONV=1`.
- **Heredocs im Bash-Werkzeug** zerbrechen an einer **ungeraden Zahl von Apostrophen** im Text (französische Zitate!), an Backticks und `$$`. Längere Dateien mit dem Write-Werkzeug schreiben oder ein Skript im Scratchpad ablegen und mit `node` ausführen.
- **E2E vor dem Push lokal laufen lassen:** Flags per `flag-set … --all`, dann `corepack pnpm exec playwright test -g Kunde`, danach `--role architect` zurücksetzen. Nur der Kundenpfad läuft lokal; Tests mit Büro-Anmeldung brauchen die CI. Weg E hat noch kein E2E-Playwright-Szenario, nur Komponententests – beim nächsten E2E-Lauf ergänzen.
- **G3:** `envelope-check` legt nichts an (Transaktion wird zurückgerollt) und ist die schnellste Gegenprobe nach Änderungen an G1, G2 oder den Schranken. Der Baurahmen wird nie gespeichert; ändert sich etwas an den Eingaben, ändert sich `input_hash` und damit auch der Steckbrief.
- **Weg E:** Bemaßte Polygone sind mit `n` Kanten mathematisch überbestimmt, wenn alle `n` frei eingebbar wären (zwei Schließungsbedingungen); die letzte Kante ergibt sich immer aus dem Schlusspunkt und wird weder abgefragt noch angezeigt. Koordinaten der Wanderung vor `math.floor()` auf Mikrometer runden, sonst weicht der Ursprung bei glatten Winkeln (90°/180°/270°) durch Gleitkommarauschen gelegentlich um 1 m ab (`backend/app/site/domain/manual.py`). Die Geometrie liegt technisch im SRID 2154, hat aber keinen geografischen Bezug – nie ohne Prüfung von `site.origin` als echte Lage behandeln.
- **WeasyPrint** braucht Pango und DejaVu im Image (`Dockerfile`, Stufe `base`); die Warnung zu HarfBuzz-Subset ist unkritisch.
- **Unsichtbare Zeichen:** `backend/app/rules/domain/text.py` enthält in `_TRANSLATE` geschützte Leerzeichen (U+00A0, U+202F) und einen weichen Trennstrich; beim Neuschreiben mit `git diff` prüfen. `ruff format` ändert Dateien – danach vor dem Edit-Werkzeug neu lesen.
- **Jobarten registrieren:** Wer `enqueue` aufruft (auch die CLI), muss `app.registry` importieren, sonst „Unbekannte Jobart“.
- **FastAPI:** jede neue öffentliche Route in `test_access_policies.py` eintragen (Weg E brauchte keine neue Route, nur eine erweiterte `SiteIn`); `openapi.json` neu erzeugen, dann `pnpm api:types`. Listenfelder in Antwortmodellen **ohne** Standardwert lassen, sonst werden sie im Frontend-Typ optional.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025. **Lokaler Login:** `ops@emprise.local`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen. Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`.
- **Rate-Limits beim Testen:** viele Projekte oder Grundstücke von derselben IP → 429; `EMPRISE_PROJECT_CREATE_LIMIT_PER_HOUR`, `EMPRISE_SITE_WRITE_LIMIT_PER_HOUR` hochsetzen.
- **Kosten der Claude API:** Aufrufe mit Schlüssel kosten; `--force` und „Neu auswerten“ werten vollständig neu aus. Eine Änderung an Prompt oder Ausgabeschema erzwingt eine neue Auswertung aller Kapitel (RW26) – solche Änderungen vor dem Eintragen des Schlüssels bündeln.
- **CI:** Der Security-Job baut Caddy mit `xcaddy`; ein Netzfehler zu `sum.golang.org` ließ früher einen Lauf scheitern (kein Codefehler). Wiederholen mit `gh run rerun <id> --failed`. Für `11a6e64` noch kein CI-Lauf, da nicht gepusht.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den Eintrag vom 17.09.2026 in AENDERUNGEN.md. Prüfe mit git status, ob der Commit 11a6e64 (Weg E) gepusht ist; falls nicht, frag nach, ob du das tun sollst, und prüfe danach mit gh run list die CI. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1, die du von mir brauchst.
```
