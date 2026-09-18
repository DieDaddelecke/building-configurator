# Hand-off für die nächste Session

> **Stand:** 18.09.2026 · **Letzte Session:** Modul A (Anfrage) geplant und vollständig umgesetzt (Backend, Frontend), im Browser geprüft, gepusht, CI grün. Davor: H1-Backend, G1 Weg E.
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat). Letzter Code-Commit `d66ee11` (Modul A), CI-Lauf 35389397303 grün. **Nicht committet:** die Dokumentänderungen dieses Handoffs (HANDOFF, AENDERUNGEN, AGENTS, UMSETZUNGSPLAN, ANNAHMEN, PLAN_A).
- **R0 Plattform:** anbieterunabhängiger Teil fertig; noch nicht auf Unraid ausgeliefert. [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **G1–G3:** fertig, lokal intern freigeschaltet (G01–G30, RW01–RW27, BR01–BR15). G2 ohne Schlüssel der Claude API noch keine echte Auswertung.
- **H1 Hauskatalog:** Backend fertig (`backend/app/catalog`, H01–H09), Frontend und die fünf echten Typdateien offen.
- **A Anfrage:** fertig und getestet ([docs/PLAN_A_ANFRAGE.md](docs/PLAN_A_ANFRAGE.md), ANNAHMEN AF01–AF12, [docs/BETRIEB.md](docs/BETRIEB.md) 11). Kunde: Kontaktformular auf der Grundstücksseite → Code per Mail → zwei Bestätigungen → `EMP-<Jahr>-<Sequenz>`; Export, Löschung (nach einer Anfrage `409`). Büro: `/buero/anfragen` (Liste, Detail mit Kontakt, Status, Baurahmen, Kanten, Regeln). Flag `inquiry` lokal für `architect`. 302 Backend-, 43 Frontend-Tests.
- **Lokaler Stack `emprise`:** mit Modul A neu gebaut, Migrationen 0007 und 0008 angewendet (`/api/health/ready` meldet 0008). Testdaten: Anfrage `EMP-2026-000001` (Projekt `f53faa49…`, Weg E, Status „in Bearbeitung“), drei Mails in Mailpit; `legal-seed` ist gelaufen.
- **Umsetzungsplan:** R0, G1, G2, G3, H1 (Backend), A beauftragt; D1–D4, D11, D14 entschieden, D12 und D13 offen. **Spezifikation:** unverändert, Korrekturen S1–S14 offen (4.6).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **Plan-Empfehlungen als entschieden genommen** („setze modul A um“): Steckbrief nur als Link im Büro (kein Mailanhang), Löschung nach einer Anfrage gesperrt (D6 offen), vorläufige Rechtstexte selbst entworfen, Sammelpostfach `EMPRISE_OFFICE_EMAIL`. Nichts davon hat der Nutzer ausdrücklich bestätigt; alles in ANNAHMEN AF01–AF05 und umkehrbar.
- **Beim Bau gefundene Fehler:** fehlender `GRANT` auf die neue Sequenz (Migration 0008 ergänzt, AF07); G1-Tests setzten Projekte ohne Anfrage voraus (G21 wirkt jetzt, Tests angepasst).
- **Beim Handoff gegen Plan 3.6 abgeglichen, nicht umgesetzt:** Zugangslink in der Kundenmail, Antwortvorlage mit Certificat-d'urbanisme-Hinweis, Idempotenz-Schlüssel (AF12); Anfrage außerhalb des Einzugsgebiets (AF11): G1 bildet dort kein Grundstück, der Hinweis `site.outside` verspricht die Anfrage aber („folgt in Kürze“).
- **Browserprüfung:** ganze Kundenstrecke und Büro-Detail funktionieren; die Löschung mit `window.confirm` ließ sich im Browserwerkzeug nicht auslösen (nur Backend-Test). E2E (Playwright) lief lokal nicht, die CI war grün.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); jetzt dringender, weil Modul A Mails braucht | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für den Einwilligungstext | AF02, AF05 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E) **und** die zwei vorläufigen Einwilligungstexte des Moduls A | Plan 6.9, RW16, AF05 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg bauen oder Hinweis `site.outside` streichen/ändern? | AF11 |
| 2 | – | Zugangslink zum Projekt in der Kundenmail (signiert) und Antwortvorlage des Büros mit CU-Hinweis: jetzt nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt oder Kachel-Proxy? | G15 |
| 2 | D5, D6, D8 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage); Honorar oder Bauleistung | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen) | Plan 8 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 (vor H2) | D12, D13 | Wie stark schränken simulierte Regeln ein? Wie geht H2 mit Weg E um? | Plan 9, BR01 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? | RW19 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta), D7, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11/AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“ in Playwright; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx` (bisher nur `AnfrageFormular`).
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`, danach Weiterleitung auf `/`, veraltetes Cookie).
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6), Nachrichten an den Kunden (kommt mit V).

### 4.2 H1 abschließen

1. Katalogpflege-Oberfläche im Frontend (Büro-Route): Typ-Import mit Vorschau, Fassadenrollen, Preise/RE2020, veröffentlichen.
2. Fünf Platzhalter-Typen als echte XLSX/DXF erfassen ([docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md) Kapitel 12; DXF-Umriss dort nur als Rechteck angenommen) und hochladen.
3. Linien und Optionen vor den Typen anlegen und veröffentlichen, sonst `catalog_reference_unknown`.
4. `docs/BETRIEB.md`-Abschnitt für H1 (Migration 0007, neue Abhängigkeiten openpyxl/ezdxf/python-multipart).

### 4.3 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; danach prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry` erwägen.
6. Später: Korrekturformular statt JSON (RW15); OCR (RW03); mehrbändige Reglements (RW23).

### 4.4 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add`, Login prüfen.
2. G1–A auf Unraid: ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`), `.env` mit `ANTHROPIC_API_KEY` und `EMPRISE_OFFICE_EMAIL`; Migrationen 0007/0008 laufen beim Ausliefern mit; danach `legal-seed` und `flag-set inquiry` (BETRIEB 11); Caddy-Ersetzungen prüfen (A27).
3. Überwachung (Uptime Kuma), Offsite-Sicherung, erste Wiederherstellungsübung.
4. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
5. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe im Objektspeicher (BR10), **Kundenkontakt, Einwilligungen und Snapshot (Modul A)**; die Claude API erhält nur Planunterlagen.
6. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.5 Nächstes Modul

- **H2** (Zulässigkeit und Implantation): braucht H1 (Backend fertig), G3 (fertig), Entscheidungen D12 und D13. Spezifikation 5.3.3–5.3.6 vor Code lesen; H2 nutzt `envelope/domain` mit den Höhen der Konfiguration und legt `/buildable?height_m=` an (Plan 7). Alternativ zuerst das H1-Frontend (4.2).
- Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).

### 4.6 Korrekturen an der Spezifikation (offen)

Unverändert seit 13.09.2026: S1–S14 (siehe AENDERUNGEN.md 14.09.). Die Abweichungen von H1 und A (ANNAHMEN H01–H09, AF01–AF12) sind Plan-Ebene. S10 (Löschung gegen Aufbewahrung) ist mit Modul A vorläufig entschärft (`409` nach einer Anfrage), die Spezifikation 10.2 sagt weiter nur „Löschung“.

### 4.7 Weitere Punkte

1. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten im Browser ansehen; die Grundstücks-Detailansicht ist jetzt in `AnfrageDetail` einmal gesehen (Weg E, ohne Regeln).
2. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): mit Modul A serverseitig da, das Mockup zeigt sie weiter nicht.

## 5. Empfohlener nächster Schritt

1. Dokumentänderungen dieses Handoffs committen (und pushen, auf Anweisung).
2. Priorität 1 aus Abschnitt 3 klären (Claude-API-Schlüssel, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name), dann 4.3/4.4.
3. Entscheiden, ob AF11/AF12 vor der Beta nachgeholt werden; dann 4.1.
4. Danach H1-Frontend (4.2) oder H2 (D12/D13 vorher).

## 6. Hinweise und Stolperstellen

- **Neue Sequenzen brauchen einen eigenen `GRANT`** in der Migration (AF07); die einmalige Vergabe aus 0001 erfasst nur damalige Sequenzen. `TRUNCATE … RESTART IDENTITY` setzt `inquiry_number_seq` nicht zurück: Tests dürfen keine feste Nummer erwarten.
- **Lokalen Stack aktualisieren:** `docker compose build migrate web`, dann `docker compose up -d migrate api worker web` (`api` und `worker` nutzen das Image `emprise-backend:local`, das der Dienst `migrate` baut; `backend-dev` ist ein eigenes Image `:dev`). Nach neuen Abhängigkeiten zusätzlich `uv lock` und `docker compose --profile dev build backend-dev` (diese Session: `email-validator`).
- **Backend-Prüfung:** `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"`. `backend-dev` sieht nur `backend/`, kein `frontend/`; lokal ist kein Python installiert (immer im Container). `openapi.json`: `python -m app.cli openapi openapi.json`, dann `corepack pnpm run api:types` im Ordner `frontend` (ohne `MSYS_NO_PATHCONV=1`).
- **Frontend:** `corepack pnpm run typecheck && corepack pnpm run lint && corepack pnpm run test`. `unwrap` scheitert an `204` ohne Rumpf (`useDeleteProject` umgeht das). i18n ist verschachtelt (`inquiry.contact.name`), die Backend-Übersetzungen sind flach (`problem.…`) mit `{param}` statt `{{param}}`.
- **Browserprüfung:** Büro-Login am lokalen Stack geht ohne Eingabe (Mock-OIDC). Wer im selben Browser als `architect` angemeldet ist, sieht auch auf `/grundstueck` die Flags dieser Rolle. Codes und Mails: Mailpit `http://localhost:8025`. `window.confirm` wird im Browserwerkzeug abgebrochen.
- **Heredocs im Bash-Werkzeug** zerbrechen an Apostrophen, Backticks und `$$`; und Git-Bash-`/tmp` ist nicht das `C:\tmp` von Node. Längere Dateien mit dem Write-Werkzeug schreiben (Scratchpad für Zwischendateien).
- **H1-Trigger `forbid_published_modification`** ist bedingt (nur bei `status = 'published'`), `forbid_modification` unbedingt (`audit_log`, `legal_text`, `consent`); `inquiry` hat bewusst keinen.
- **Jobarten registrieren:** Wer `enqueue` aufruft, muss `app.registry` importieren. Modul A nutzt nur den bestehenden Job `mail_send`.
- **FastAPI:** neue **öffentliche** Route in `test_access_policies.py` eintragen; Routen mit `require_project_access` oder Rolle brauchen keinen Eintrag.
- **Weg E:** Geometrie ohne geografischen Bezug, nie ohne Prüfung von `site.origin` behandeln.
- **WeasyPrint** braucht Pango und DejaVu im Image. **Unsichtbare Zeichen:** `backend/app/rules/domain/text.py` beim Neuschreiben mit `git diff` prüfen.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025. **Lokaler Login:** `ops@emprise.local`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen. Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`.
- **Rate-Limits beim Testen:** viele Projekte/Codes von derselben IP oder Adresse → 429; Limits in `.env` hochsetzen (`inquiry_*` in `config.py`).
- **Kosten der Claude API:** Aufrufe mit Schlüssel kosten; Änderungen an Prompt/Ausgabeschema vor dem Eintragen des Schlüssels bündeln.
- **CI:** Security-Job baut Caddy mit `xcaddy`; Netzfehler zu `sum.golang.org` sind kein Codefehler, mit `gh run rerun <id> --failed` wiederholen.
- **Commit und Push nur auf Aufforderung** (siehe Memory `feedback-plan-dann-umsetzen`).

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den Eintrag vom 18.09.2026 (Modul A) in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen, nenne die Entscheidungen mit Priorität 1 und frag mich, ob AF11 (Anfrage außerhalb des Einzugsgebiets) und AF12 (Zugangslink, Antwortvorlage) vor der Beta nachgeholt werden sollen, bevor wir mit dem H1-Frontend oder H2 weitermachen. Die Dokumentänderungen des letzten Handoffs sind noch nicht committet.
```
