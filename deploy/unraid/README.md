# Emprise auf Unraid

Betrieb für interne Einführung und Beta (Entscheidung D3 vom 14.09.2026). Zwei getrennte Stacks:

| Stack | Ordner | Adresse | Port auf Unraid |
|---|---|---|---|
| Emprise | `deploy/unraid` | `https://building-configurator.aslani.work` (vorläufig) | 8480 → `web` |
| Authentik | `deploy/unraid/authentik` | z. B. `https://auth.aslani.work` | 9000 → `server` |

Nur diese beiden Ports bekommt der Reverse Proxy. Datenbank, Speicher und API haben keine Ports nach außen.

Lokal geprüft am 14.09.2026: Stack startet, Migration mit getrennten Rollen, SeaweedFS mit Versionierung, Sicherung und Wiederherstellung, Anmeldung über Authentik 2026.8.2 mit TOTP. Nicht geprüft: TLS am Reverse Proxy und die Erreichbarkeit von Authentik aus dem Container (Abschnitt 2).

## 1. Voraussetzungen

- Unraid mit `docker compose` (Plugin „Docker Compose Manager“) und Terminal-Zugang
- Code auf Unraid, z. B. `/mnt/user/appdata/emprise-src` (Git-Klon oder Kopie über die Freigabe)
- `openssl` für Zufallswerte (auf Unraid vorhanden)

## 2. DNS und Reverse Proxy

Zwei Einträge im Reverse Proxy, beide mit TLS-Zertifikat:

| Hostname | Ziel | Hinweise |
|---|---|---|
| `building-configurator.aslani.work` | `http://<Unraid-IP>:8480` | `X-Forwarded-For` und `X-Forwarded-Proto` setzen |
| `auth.aslani.work` | `http://<Unraid-IP>:9000` | Websockets erlauben |

**Cloudflare:** `aslani.work` liegt bei Cloudflare. Ist ein Eintrag „proxied“ (orange Wolke) oder läuft ein Tunnel, sieht Cloudflare den gesamten Verkehr im Klartext, auch Anmeldedaten und später Kundendaten. Das widerspricht Leitplanke L8 und Plan 6.9 (keine US-Anbieter im Datenweg). Für die Beta: Einträge nur als DNS („DNS only“, graue Wolke) und TLS am eigenen Reverse Proxy. Bleibt der Cloudflare-Proxy, muss der Reverse Proxy die echte Client-IP aus `CF-Connecting-IP` übernehmen, sonst teilen sich alle Nutzer ein Rate-Limit.

**Erreichbarkeit aus dem Container:** Die API ruft Authentik über die öffentliche Adresse auf (`OIDC_ISSUER`). Unterstützt der Router keinen Zugriff von innen auf die eigene öffentliche Adresse, Datei `compose.override.yaml` neben `compose.yaml` anlegen:

```yaml
services:
  api:
    extra_hosts:
      - "auth.aslani.work:<IP des Reverse Proxy im LAN>"
```

## 3. Authentik einrichten

```bash
cd /mnt/user/appdata/emprise-src/deploy/unraid/authentik
cp .env.example .env
```

In `.env` setzen: `AUTHENTIK_SECRET_KEY` und `PG_PASS` (je `openssl rand -hex 32`), `AUTHENTIK_BASE_URL`, `EMPRISE_PUBLIC_BASE_URL`, `EMPRISE_OIDC_CLIENT_SECRET` (`openssl rand -hex 32`, derselbe Wert kommt in Abschnitt 4 in `OIDC_CLIENT_SECRET`).

```bash
docker compose up -d
```

1. `https://auth.aslani.work/if/flow/initial-setup/` öffnen und das Passwort für `akadmin` setzen.
2. Admin-Oberfläche → Anwendungen: „Emprise“ muss vorhanden sein (Blueprint `blueprints/emprise.yaml`). Unter System → Blueprints steht „Emprise – Anmeldung Büro“ auf `successful`.
3. System → Einstellungen: **„Benutzer dürfen E-Mail ändern“ ausschalten** (Bezeichnung in der Oberfläche prüfen). Emprise ordnet Konten bei der ersten Anmeldung über die E-Mail-Adresse zu.
4. Keine Selbstregistrierung einrichten. Konten legt nur die Administration an (Verzeichnis → Benutzer) mit der dienstlichen E-Mail-Adresse.
5. Bei der ersten Anmeldung richtet jede Person den zweiten Faktor ein (Authenticator-App oder Sicherheitsschlüssel). **Danach einmal neu anmelden:** Authentik meldet den zweiten Faktor erst bei einer Anmeldung mit bereits eingerichtetem Gerät, Emprise zeigt beim ersten Mal „Kein Zugang“ mit diesem Hinweis.

Nicht verwenden: reine Passkey-Anmeldung ohne Passwort. Authentik meldet sie als `user`, nicht als zweiten Faktor; Emprise lehnt sie ab.

## 4. Emprise einrichten

```bash
cd /mnt/user/appdata/emprise-src/deploy/unraid
cp .env.example .env
for v in SECRET_KEY POSTGRES_PASSWORD MIGRATOR_DB_PASSWORD APP_DB_PASSWORD READONLY_DB_PASSWORD S3_SECRET_KEY; do
  sed -i "s/^$v=$/$v=$(openssl rand -hex 32)/" .env
done
```

In `.env` von Hand: `OIDC_ISSUER` (`https://auth.aslani.work/application/o/emprise/`), `OIDC_CLIENT_SECRET` (Wert aus Abschnitt 3), Pfade `APPDATA_DIR` und `BACKUP_DIR`. `chmod 600 .env`.

```bash
chmod +x deploy.sh
./deploy.sh
docker compose exec api python -m app.cli staff-add vorname.name@buero.fr ops architect
```

Prüfen:

- `https://building-configurator.aslani.work/api/health/ready` → `"status": "ok"`, `"postgis"`, `"migration_state": "current"`
- `https://building-configurator.aslani.work/buero` → Anmeldung über Authentik → Startseite mit Rollen

## 5. Aktualisieren und Rückrollen

```bash
cd /mnt/user/appdata/emprise-src && git pull
deploy/unraid/deploy.sh
```

`deploy.sh` baut die Images mit der Commit-Kennung, führt die Migration aus, startet neu und prüft `/api/health/ready`. Frühere Releases stehen in `releases.log`; die Images bleiben erhalten.

```bash
deploy/unraid/deploy.sh rollback <release>
```

Migrationen werden dabei nicht zurückgedreht (abwärtskompatibel, docs/BETRIEB.md Abschnitt 2). Alte Images gelegentlich aufräumen: `docker image ls emprise-backend`.

## 6. Sicherung und Wiederherstellung

| Was | Wie | Wohin |
|---|---|---|
| Datenbank Emprise | Container `backup`, täglich um `BACKUP_HOUR`, 14 Tage | `BACKUP_DIR` |
| Dateien (SeaweedFS), Datenbank Authentik | Unraid-Plugin „Appdata Backup“ über `APPDATA_DIR` beider Stacks | Backup-Freigabe |
| Außer Haus | `BACKUP_DIR` und Appdata-Sicherung zusätzlich auf ein zweites Ziel in der EU | z. B. zweites Gerät oder EU-Speicher |

Sofortige Sicherung: `docker compose run --rm backup now`. Die Datei `BACKUP_DIR/last-success` enthält den Zeitpunkt der letzten erfolgreichen Sicherung.

**Wiederherstellung** (zuerst als Übung in eine Testdatenbank, Ergebnis in docs/BETRIEB.md Abschnitt 6 eintragen):

```bash
docker compose exec -T db psql -U postgres -c "CREATE DATABASE restore_test OWNER migrator"
docker compose exec -T db psql -U postgres -d restore_test -c "CREATE EXTENSION postgis"
docker compose exec -T backup sh -c 'pg_restore --no-owner --no-comments --role=migrator -d restore_test "$(ls /backups/emprise-*.dump | tail -1)"'
```

Für den Ernstfall statt `restore_test` die Datenbank `emprise` neu anlegen (vorher `api`, `worker` stoppen), danach `./deploy.sh`.

## 7. Überwachung

Vorschlag ohne externe Dienste: Uptime Kuma als Container auf Unraid mit drei Prüfungen und Benachrichtigung (Mail oder Messenger):

| Prüfung | Alarm, wenn |
|---|---|
| `https://building-configurator.aslani.work/api/health/ready` | nicht 200 |
| `https://building-configurator.aslani.work/api/health/jobs` | nicht 200 (Worker steht) |
| `https://auth.aslani.work/-/health/ready/` | nicht 200 |

Die Frische der Sicherung prüft ein User Script: Alarm, wenn `last-success` älter als 26 Stunden ist.

## 8. Grenzen bis zur Beta

- Verfügbarkeit hängt an Strom und Internetanschluss; kein zweiter Standort.
- Keine Wiederherstellung auf beliebige Zeitpunkte, nur auf die letzte nächtliche Sicherung (Datenverlust bis 24 h).
- Mailversand braucht einen Anbieter (E2); bis dahin scheitern Mailjobs und werden wiederholt.
- Vor dem öffentlichen Start von R1 wird über das Hosting neu entschieden (Plan 6.4).

## 9. Hinweise für R1 (Modul G1)

- `api` und `worker` brauchen ausgehenden Zugang zu `data.geopf.fr`, `cadastre.data.gouv.fr` (Weiterleitung auf `*.cloud.ovh.net`) und `georisques.gouv.fr`. Die Compose-Netze sperren ausgehenden Verkehr nicht; eine Firewall auf Unraid oder im Router muss ihn erlauben.
- Einzugsgebiet in `.env` setzen: `CADASTRE_COMMUNES=["44209","44…"]` (INSEE-Codes, D1). Erstimport nach der Auslieferung: `docker compose exec api python -m app.cli cadastre-import`; danach aktualisiert der Worker wöchentlich. Freischaltung über das Feature-Flag `site_selection`, zuerst intern: `docker compose exec api python -m app.cli flag-set site_selection --role architect` (Plan 4.2); öffentlich später mit `--all`.
- Speicher: grob 10–20 MB in PostGIS je Gemeinde in der Größe von Treillières (≈ 8.800 Parzellen).
- Géorisques-Token nur, falls die Schnittstelle v1 abgeschaltet wird: dann in `compose.override.yaml` bei `api` und `worker` `EMPRISE_GEORISQUES_TOKEN` setzen. Nicht leer übergeben.
- Weitere Einstellungen (Zeitlimits, Rate-Limits, Basis-URLs) haben Standardwerte in `backend/app/config.py`; Details in `docs/ANNAHMEN.md`, Abschnitt G1.

## 10. Hinweise für R1 (Modul G2)

- Ausgehender Zugang zusätzlich zu `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr` und `api.anthropic.com`.
- In `.env` `ANTHROPIC_API_KEY` und `RULES_BUDGET_MONTH_USD` setzen. Ohne Schlüssel importiert der Worker die Planstände trotzdem; die Kapitel stehen dann auf „gescheitert: not_configured“ und werden nach dem Eintragen innerhalb einer Stunde automatisch ausgewertet (Job `rules_housekeeping`); sofort mit `docker compose exec api python -m app.cli rules-extract --pending` (kostet Token, Größenordnung in BETRIEB 9).
- Planstände prüft der Worker wöchentlich; sofort: `docker compose exec api python -m app.cli plu-import`.
- Freischaltung über `rules_simulation`, zuerst intern: `docker compose exec api python -m app.cli flag-set rules_simulation --role architect`.
- Speicher: das règlement écrit liegt im Objektspeicher (PLUi Erdre et Gesvres 6,8 MB), Seitentexte und Vorgaben in PostGIS (wenige MB je Planstand).

## 11. Hinweise für R1 (Modul G3)

- **Migration 0005** legt die Tabelle `envelope_sheet` an und läuft beim Ausliefern mit.
- **Kein neuer ausgehender Zugang.** G3 rechnet nur mit Daten aus der eigenen Datenbank.
- **Image:** Der Steckbrief braucht WeasyPrint mit `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b`, `libfribidi0` und `fonts-dejavu-core`; sie stecken im Backend-Image (rund 80 MB mehr). Nach dem Aktualisieren prüfen: `docker compose exec api python -c "import weasyprint"`.
- **Freischalten** (intern für das Büro):

  ```bash
  docker compose exec api python -m app.cli flag-set envelope_simulation --role architect
  ```

- **Objektspeicher:** Steckbriefe liegen unter `envelope-sheets/`; sie werden mit dem Projekt gelöscht und sind in der Sicherung des Buckets enthalten.
- **Gegenprobe nach dem Ausliefern:** `docker compose exec api python -m app.cli envelope-check --commune 44209 --sample 50` (0 Fehler erwartet).
