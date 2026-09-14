# Infrastruktur

**Stand 14.09.2026:** Bis zur Beta läuft Emprise selbst betrieben auf Unraid, Anleitung und Stacks in [`deploy/unraid`](../deploy/unraid/README.md) (D3, D4 entschieden). Die Abschnitte unten beschreiben den späteren Wechsel zu einem verwalteten Anbieter vor dem öffentlichen Start von R1; dafür gibt es noch **keinen OpenTofu-Code**.

| Ordner | Inhalt |
|---|---|
| `local/postgres-init.sql` | Rollen `migrator`, `app`, `readonly` und Rechte; Vorlage für die verwaltete Datenbank |
| `local/oidc.json` | Lokaler OIDC-Testdienst mit MFA-Claim |

## 1. Was der Anbieter bereitstellen muss

| Baustein | Konfiguration der Anwendung |
|---|---|
| Container `web` (öffentlich, hinter TLS-Lastverteiler) | Image `emprise-web:<commit>`, Port 8080, `API_UPSTREAM=<privater Name der API>:8000` |
| Container `api` (nur privat erreichbar) | Image `emprise-backend:<commit>`, Port 8000, `FORWARDED_ALLOW_IPS` = Netz des Web-Containers |
| Container `worker` (dauerhaft, ohne eingehende Anfragen, mindestens 1 Instanz) | gleiches Image, Befehl `python -m app.cli worker` |
| Job `migrate` vor jeder Auslieferung | gleiches Image, Befehl `alembic upgrade head`, Datenbankrolle `migrator` |
| PostgreSQL 16 + PostGIS 3 mit PITR, private Verbindung | Rollen nach `local/postgres-init.sql`; Erweiterung `postgis` durch den Admin anlegen |
| S3-Bucket, privat, Versionierung an; zweiter Bucket in anderer EU-Region für Sicherungen | |
| Secret Manager | alle `EMPRISE_*`-Geheimnisse (siehe Tabelle 2) |
| Logs | JSON von stdout; Aufbewahrung 30 Tage |

## 2. Umgebungsvariablen

Vollständige Liste mit Standardwerten: `backend/app/config.py`. Pflicht in `staging` und `production`:

| Variable | Beispiel | Geheim |
|---|---|---|
| `EMPRISE_ENV` | `production` | |
| `EMPRISE_RELEASE` | Commit-Kennung (wird beim Image-Bau gesetzt) | |
| `EMPRISE_PUBLIC_BASE_URL` | `https://app.emprise.fr` (https Pflicht) | |
| `EMPRISE_SECRET_KEY` | 64 zufällige Zeichen | ja |
| `EMPRISE_DATABASE_URL` | `postgresql+psycopg://app:…@db-privat:5432/emprise` | ja |
| `EMPRISE_MIGRATION_DATABASE_URL` | `postgresql+psycopg://migrator:…@db-privat:5432/emprise` (nur Job `migrate`) | ja |
| `EMPRISE_OIDC_ISSUER`, `EMPRISE_OIDC_CLIENT_ID`, `EMPRISE_OIDC_CLIENT_SECRET` | nach D4; Rücksprungadresse `https://…/api/v1/auth/staff/callback` | Secret ja |
| `EMPRISE_S3_ENDPOINT_URL`, `EMPRISE_S3_REGION`, `EMPRISE_S3_BUCKET`, `EMPRISE_S3_ACCESS_KEY`, `EMPRISE_S3_SECRET_KEY` | | Schlüssel ja |
| `EMPRISE_SMTP_HOST`, `EMPRISE_SMTP_PORT`, `EMPRISE_SMTP_USERNAME`, `EMPRISE_SMTP_PASSWORD`, `EMPRISE_SMTP_STARTTLS`, `EMPRISE_MAIL_FROM` | nach E2 | Passwort ja |
| `EMPRISE_SENTRY_DSN` | EU-Datenhaltung | ja |

## 3. Proof of Concept (ein Tag, Plan 6.4)

Ergebnis je Punkt in diese Tabelle eintragen; Grundlage für D3.

| # | Prüfung | Vorgehen | Ergebnis |
|---|---|---|---|
| 1 | Rechenzentrum Frankreich, AVV | Vertragsunterlagen | |
| 2 | PostgreSQL 16 mit PostGIS und PITR | Instanz anlegen, `CREATE EXTENSION postgis`, Rollen aus `local/postgres-init.sql`, Job `migrate`, `/api/health/ready` = 200 mit `postgis` | |
| 3 | Worker dauerhaft ohne Kaltstart | `worker` starten; `POST /api/v1/admin/ops/test-mail` → Job `succeeded` innerhalb von Sekunden; `/api/health/jobs` = 200 nach 30 min Leerlauf | |
| 4 | S3 mit Versionierung | `GET /api/v1/admin/ops/status` → `storage_ok: true` | |
| 5 | Private Verbindung API ↔ Datenbank, API nicht öffentlich | Zugriff auf Port 8000 von außen scheitert | |
| 6 | Secret Manager, Registry, Logs | Geheimnisse nur dort; JSON-Logs sichtbar, ohne IP-Adressen und Mailadressen | |
| 7 | OpenTofu-Provider | Umgebung `staging` vollständig per `tofu apply` erzeugen und wieder löschen | |
| 8 | Zweite EU-Region | täglicher `pg_dump` in den Sicherungsbucket; **Wiederherstellung** in eine neue Instanz, Zeit messen (BETRIEB.md Abschnitt 6) | |
| 9 | Rückrollen | Image `n` ausliefern, dann `n-1`: `/api/health/ready` bleibt 200 (`migration_state: ahead`) | |
| 10 | Kosten | Monatspreis Staging + Produktion nach Plan 6.10 | |

## 4. Offen

- OpenTofu-Stand und `deploy.yml` (Staging automatisch, Produktion nach Freigabe) – nach D3.
- Täglicher Dump in die zweite Region als geplanter Container-Job – nach D3.
- Uptime-Dienst mit Alarmen auf `/api/health/ready` und `/api/health/jobs`, Fehler-Tracking-Konto – nach D5.
- Domain, Maildomain mit SPF/DKIM/DMARC – Kapitel 8 des Plans (R0, Emprise).
- Schutz des Hauptzweigs und Pflicht-Pull-Requests im Repository-Dienst – nach Anlage des Remote-Repositorys.
- Die OpenAPI-Oberfläche `/api/v1/docs` lädt Skripte von einem CDN und wird durch die CSP des Web-Containers blockiert; in Staging über die API direkt oder gar nicht nutzen.
