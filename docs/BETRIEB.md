# Betriebsanleitung

Typische Störungen und Handgriffe (Plan 6.8). Stand R0. Befehle mit `docker compose exec api …` gelten lokal; beim Anbieter läuft derselbe Befehl als einmaliger Container-Job mit dem Image der laufenden Version.

## 1. Überblick

| Baustein | Aufgabe | Prüfpunkt |
|---|---|---|
| `web` | Frontend, Sicherheitsköpfe, Weiterleitung `/api` | `GET /` |
| `api` | REST-API | `GET /api/health/live`, `/api/health/ready` |
| `worker` | Hintergrundjobs, Zeitplan | `GET /api/health/jobs` |
| `migrate` | Einmaliger Job vor jeder Auslieferung: `alembic upgrade head` | Exit-Code |
| Datenbank | PostgreSQL 16 + PostGIS 3, Rollen `migrator`, `app`, `readonly` | `/api/health/ready` |
| Objektspeicher | Dateien, privat, versioniert | `GET /api/v1/admin/ops/status` → `storage_ok` |
| Mail | Transaktionsmails über SMTP | `POST /api/v1/admin/ops/test-mail` |

Alarme (Uptime-Dienst, minütlich): `/api/health/ready` ≠ 200 → „API oder Datenbank gestört“; `/api/health/jobs` ≠ 200 → „Worker steht oder ist überlastet“.

## 2. Ausliefern und Rückrollen

1. Merge in `main` → CI grün → Images `emprise-backend:<commit>` und `emprise-web:<commit>`.
2. Staging: Migrationsjob mit dem neuen Image, danach `api`, `worker`, `web` auf das neue Image, dann Rauchtest: `/api/health/ready` meldet `"migration"` = Stand des Images.
3. Produktion: dieselben Images nach Freigabe, gleiche Reihenfolge.
4. **Rückrollen:** `api`, `worker`, `web` auf das vorige Image setzen. Migrationen **nicht** zurückdrehen: Sie sind abwärtskompatibel (erst erweitern, später aufräumen). `/api/health/ready` meldet dann `"migration_state": "ahead"` und bleibt bereit (200). Nur `"pending"` (Image neuer als Datenbank, Migrationsjob fehlt) ergibt 503.

> **Unraid (bis zur Beta):** Schritte 2–4 übernimmt `deploy/unraid/deploy.sh`, Rückrollen mit `deploy.sh rollback <release>`. Eine getrennte Staging-Umgebung gibt es dort nicht; neue Funktionen laufen hinter Feature-Flags. Anleitung: `deploy/unraid/README.md`.

## 3. Zugang für Mitarbeitende

- Freischalten oder Rollen setzen: `python -m app.cli staff-add person@buero.fr architect rules_admin`
- Sperren (beendet alle Sitzungen): `python -m app.cli staff-deactivate person@buero.fr`
- Die Person meldet sich unter `/buero` an. „Kein Zugang“ mit Grund `unknown`: Adresse nicht freigeschaltet oder beim Identitätsdienst anders geschrieben. Grund `mfa`: zweiter Faktor fehlt. Grund `email_unverified`: Adresse beim Identitätsdienst nicht bestätigt.
- Jede Freischaltung, Sperre, An- und Abmeldung steht im `audit_log`.

## 4. Jobs

- Zustand: `GET /api/v1/admin/ops/status` (Rolle `ops`): Anzahl je Status, fehlgeschlagen in 24 h, ältester wartender Job.
- Ein Job wird bis `max_attempts` mit wachsendem Abstand wiederholt (30 s, 60 s, 120 s … höchstens 1 h). Danach `failed` und Meldung an das Fehler-Tracking.
- Stürzt ein Worker ab, stellt ein anderer den Job nach Zeitlimit + 60 s zurück.
- Fehlgeschlagene Jobs erneut einreihen (bis `POST /admin/jobs/{id}/retry` existiert):
  ```sql
  UPDATE job SET status = 'queued', attempts = 0, run_after = now(), finished_at = NULL WHERE id = '<id>';
  ```
  Nur mit Rolle `migrator` und nur, wenn die Ursache behoben ist; Handler sind idempotent.

## 5. Mailzustellung gestört

1. `POST /api/v1/admin/ops/test-mail` auslösen; Status des Jobs über `GET /api/v1/jobs/{id}`.
2. `last_error` des Jobs lesen (`SELECT kind, attempts, last_error FROM job WHERE kind = 'mail_send' ORDER BY created_at DESC LIMIT 20`).
3. Häufige Ursachen: SMTP-Zugangsdaten abgelaufen, SPF/DKIM/DMARC der Absenderdomain, Sperre beim Anbieter.
4. Nach Behebung wartende Jobs laufen von selbst weiter; endgültig fehlgeschlagene nach Abschnitt 4 erneut einreihen.

## 6. Wiederherstellung

- **Punktgenau (Datenverlust höchstens 1 h):** Point-in-Time-Recovery des Anbieters auf eine neue Instanz, Anwendung auf die neue Verbindung umstellen, `/api/health/ready` prüfen.
- **Verlust der Region (höchstens 24 h):** täglichen Dump aus dem Objektspeicher der zweiten Region in eine neue Instanz einspielen (`pg_restore --no-owner --role=migrator`), danach Rollen und Rechte nach `infra/local/postgres-init.sql` prüfen.
- Übung vierteljährlich in Staging, Ergebnis mit Datum, Dauer und Datenstand in diesem Abschnitt protokollieren.

> **Unraid (bis zur Beta):** Kein PITR; Wiederherstellung aus dem nächtlichen Dump (Datenverlust bis 24 h), Befehle in `deploy/unraid/README.md` Abschnitt 6.

| Datum | Umgebung | Verfahren | Dauer | Ergebnis |
|---|---|---|---|---|
| 14.09.2026 | lokal, Unraid-Stack | `backup now` → `pg_restore --no-owner --no-comments` in `restore_test` | < 1 min (leere Datenbank) | vollständig, 13 Tabellen, Schutztrigger vorhanden |
| – | Unraid | Übung mit echtem Datenstand | – | ausstehend |

## 7. Sicherheitsvorfall

1. Betriebsverantwortung (D5) informieren; Zeitpunkt festhalten.
2. Eindämmen: betroffene Konten sperren (`staff-deactivate`), Geheimnisse im Secret Manager erneuern, bei Verdacht auf Sitzungsdiebstahl alle Sitzungen beenden: `UPDATE staff_session SET revoked_at = now() WHERE revoked_at IS NULL;`
3. Umfang klären: `audit_log`, Logs (ohne personenbezogene Daten), Fehler-Tracking.
4. Sind personenbezogene Daten betroffen: **Meldung an die CNIL binnen 72 Stunden** (Art. 33 DSGVO), bei hohem Risiko Benachrichtigung der Betroffenen (Art. 34).
5. Nachbereitung mit Ursache und Maßnahmen; Annahmen in `docs/ANNAHMEN.md` anpassen.

## 8. Kataster und Grundstück (Modul G1)

**Einrichten und Freischalten**

1. Einzugsgebiet setzen: `EMPRISE_CADASTRE_COMMUNES='["44209"]'` (INSEE-Codes; Entscheidung D1).
2. Erstimport: `python -m app.cli cadastre-import` (ohne Internet: `--from-dir <ordner> --release <stand>`). Danach prüft der Worker wöchentlich auf neue Stände.
3. Freischalten über das Flag `site_selection`: intern `python -m app.cli flag-set site_selection --role architect`, später Beta für Projekte (Admin-API) und öffentlich `flag-set site_selection --all`; abschalten mit `--off` (Plan 4.2). Jede Änderung steht im `audit_log`.
4. Ausgehender Zugang für API und Worker: `data.geopf.fr`, `cadastre.data.gouv.fr` (leitet auf `*.cloud.ovh.net` weiter), `georisques.gouv.fr`. Browser der Besucher laden Kartenkacheln von `data.geopf.fr`.

**Stand prüfen:** `GET /api/v1/admin/cadastre/imports` (Rolle `ops`): letzter Import je Gemeinde mit Stand, Anzahl Parzellen, Gebäude, Straßenachsen (`roads = -1`: Achsen fehlen, siehe unten) und Fehler.

**Katasterimport gescheitert** (Job `cadastre_import` endgültig `failed`, Meldung im Fehler-Tracking)

1. `error` des letzten Imports lesen. Der bisherige Stand bleibt in jedem Fall erhalten.
2. `parcel_count_change:<alt>-><neu>`: Parzellenzahl weicht mehr als max(2 %, 50) ab. Stichprobe im Kartenausschnitt der Gemeinde ansehen; ist der neue Stand plausibel (z. B. Flurneuordnung), `python -m app.cli cadastre-import --commune <insee> --force`.
3. `too_many_unusable_parcels`: Quelldaten fehlerhaft. Nächsten Stand abwarten; nicht erzwingen.
4. `transport:*`, `http_5xx`: Etalab nicht erreichbar. Der Job wiederholt sich; sonst am nächsten Tag von Hand starten (`POST /api/v1/admin/cadastre/imports`).
5. `roads = -1` bei erfolgreichem Import: der WFS der Géoplateforme war nicht erreichbar. Die Kanten werden ohne Straßenachsen unsicherer eingeordnet (mehr Prüffälle im Büro). Der nächste wöchentliche Lauf holt die Achsen nach; eilig: `cadastre-import --commune <insee>`.

**Géoplateforme oder Géorisques ausgefallen**

- Adresssuche meldet `geocoding_unavailable`: Kunden wählen die Parzelle über Karte oder Parzellennummer; Parzellen kommen aus der eigenen Datenbank.
- Kartenkacheln fehlen: Parzellen sind trotzdem sichtbar und wählbar; Parzellennummer funktioniert immer.
- Gelände oder Risiken `unavailable`: Hinweis „nicht abgefragt“ beim Grundstück. Sobald der Dienst wieder antwortet: `POST /api/v1/admin/sites/enrich-retry` (Rolle `ops`) stößt alle betroffenen Grundstücke erneut an.

**Prüfliste im Büro:** `/buero/grundstuecke` zeigt Grundstücke mit unbestätigten Kundenkorrekturen zuerst. Solange eine Kundenkorrektur unbestätigt ist, ist der Baurahmen nicht bindend.

## 9. Regelwerk (Modul G2)

**Einrichten und Freischalten**

1. Schlüssel der Claude API und Monatsbudget setzen: `EMPRISE_ANTHROPIC_API_KEY`, `EMPRISE_RULES_BUDGET_MONTH_USD` (Unraid: `ANTHROPIC_API_KEY`, `RULES_BUDGET_MONTH_USD` in `.env`). An die API gehen nur öffentliche Planunterlagen (L8).
2. Planstände importiert der Worker beim ersten Start und danach wöchentlich (`plu_import`); sofort: `python -m app.cli plu-import` (ohne Internet: `--from-dir`). Jedes Zonenkapitel wird danach als Job `rules_extract` ausgewertet.
3. Freischalten über `rules_simulation`: intern `python -m app.cli flag-set rules_simulation --role architect`, später Beta und `--all` (Plan 4.2).
4. Ausgehender Zugang für API und Worker zusätzlich: `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `data.geopf.fr`, `api.anthropic.com`.

**Stand prüfen:** `/buero/regeln` bzw. `GET /api/v1/admin/rules/coverage`: je Gemeinde Planstand und Status, je Kapitel Sektoren, Status mit Grund, Läufe, Kosten, offene Pflichtwerte je Sektor; oben Monatskosten und Budget.

**Kosten (Schätzung, nach der ersten echten Auswertung ersetzen):** je Kapitel zwei Läufe mit rund 50–60 PDF-Seiten, allgemeine Seiten aus dem Cache; Größenordnung 1–2 $ je Kapitel, für Treillières (12 Kapitel) 10–25 $ je Planstand. Neue Planstände erscheinen etwa ein- bis zweimal im Jahr.

**Kapitel gescheitert** (Status `failed`, Grund in der Abdeckung, Log `rules_extract_failed`)

- `not_configured`: Schlüssel fehlt. Eintragen, Dienste neu starten, dann `python -m app.cli rules-extract --pending`.
- `budget_exceeded`: Monatsbudget erreicht. Budget prüfen und anheben oder den Monatswechsel abwarten; danach `rules-extract --pending`.
- `auth`, `model_not_found`, `bad_request:…`: Konfiguration prüfen (Schlüssel, `EMPRISE_RULES_MODEL`); `bad_request` mit Größenangabe: Kapitel zu lang, der Entwicklung melden.
- `refusal`: Das Modell hat abgelehnt, auch der Rückfall. Kapitel einmal neu auswerten („Neu auswerten“); bleibt es dabei, sehen Kunden „nicht verfügbar“, das Büro prüft bei Anfrage.
- `max_tokens`: Ausgabe zu lang (sehr viele Sektoren). Der Entwicklung melden; bis dahin „nicht verfügbar“.
- `rate_limited`, `http_5xx`, `transport:*`: wiederholt sich selbst (3 Versuche); danach „Neu auswerten“.

**Import gescheitert** (Job `plu_import` endgültig `failed`, Gemeinde `failed`): meist GPU nicht erreichbar oder Antwort abgeschnitten (`truncated`). Der vorige Planstand bleibt aktiv. Später `python -m app.cli plu-import --commune <insee>`. Status `no_regulation` oder `no_chapters`: Planunterlagen fehlen oder sind nicht lesbar; Kunden sehen den Grund, das Büro prüft bei Anfrage.

**Viele `unknown`-Werte in einem Kapitel:** Regelwerk im Büro öffnen (Zitat, Grund, Alternativen beider Läufe). Liegt es an der Auswertung, nach Prompt- oder Modelländerung neu auswerten; liegt es am Planwerk (Werte im Zonenplan), bleibt es bei `unknown`. Korrekturen des Büros sind freiwillig (D11).
