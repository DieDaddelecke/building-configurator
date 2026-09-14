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

> Offen bis D3: Die Pipeline-Schritte 2–4 als `deploy.yml` mit dem OpenTofu-Stand des Anbieters.

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

> Offen bis D3: konkrete Befehle des Anbieters; erste Übung im Proof of Concept.

| Datum | Umgebung | Verfahren | Dauer | Ergebnis |
|---|---|---|---|---|
| – | – | – | – | noch nicht geübt |

## 7. Sicherheitsvorfall

1. Betriebsverantwortung (D5) informieren; Zeitpunkt festhalten.
2. Eindämmen: betroffene Konten sperren (`staff-deactivate`), Geheimnisse im Secret Manager erneuern, bei Verdacht auf Sitzungsdiebstahl alle Sitzungen beenden: `UPDATE staff_session SET revoked_at = now() WHERE revoked_at IS NULL;`
3. Umfang klären: `audit_log`, Logs (ohne personenbezogene Daten), Fehler-Tracking.
4. Sind personenbezogene Daten betroffen: **Meldung an die CNIL binnen 72 Stunden** (Art. 33 DSGVO), bei hohem Risiko Benachrichtigung der Betroffenen (Art. 34).
5. Nachbereitung mit Ursache und Maßnahmen; Annahmen in `docs/ANNAHMEN.md` anpassen.
