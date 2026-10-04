# Betrieb

Betrieb für interne Einführung und Beta (Entscheidung D3 vom 14.09.2026): **Teil A** (Abschnitte 1–9) richtet Emprise auf Unraid ein, **Teil B** (10–23) beschreibt die Module im Betrieb, typische Störungen und Handgriffe. Befehle mit `docker compose exec api …` gelten lokal und auf Unraid (dort im Ordner `deploy/unraid`). Aufbau: [ARCHITECTURE.md](../../ARCHITECTURE.md).

# Teil A – Einrichtung auf Unraid

Zwei getrennte Stacks:

| Stack | Ordner | Adresse | Port auf Unraid |
|---|---|---|---|
| Emprise | `deploy/unraid` | `https://building-configurator.aslani.work` (vorläufig) | 8480 → `web` |
| Authentik | `deploy/unraid/authentik` | `https://auth.aslani.work` (entschieden 25.09.2026) | 9000 → `server` |

Nur diese beiden Ports bekommt der Reverse Proxy. Datenbank, Speicher und API haben keine Ports nach außen.

Lokal geprüft am 14.09.2026: Stack startet, Migration mit getrennten Rollen, Sicherung und Wiederherstellung, Anmeldung über Authentik 2026.8.2 mit TOTP. Nicht geprüft: TLS am Reverse Proxy und die Erreichbarkeit von Authentik aus dem Container (Abschnitt 2).

## 1. Voraussetzungen

- Unraid mit `docker compose` (Plugin „Docker Compose Manager“) und Terminal-Zugang
- Code auf Unraid, z. B. `/mnt/user/appdata/emprise-src` (Git-Klon oder Kopie über die Freigabe)
- `openssl` für Zufallswerte (auf Unraid vorhanden)

## 2. DNS und Reverse Proxy

Einträge im Reverse Proxy, alle mit TLS-Zertifikat:

| Hostname | Ziel | Hinweise |
|---|---|---|
| `building-configurator.aslani.work` | `http://<Unraid-IP>:8480` | `X-Forwarded-For` und `X-Forwarded-Proto` setzen |
| `auth.aslani.work` | `http://<Unraid-IP>:9000` | Websockets erlauben |
| `emprise-analyse.aslani.work` | Weiterleitung (301) auf `https://building-configurator.aslani.work/analyse` | nur falls der Name schon verteilt ist; die Analyse läuft in derselben Anwendung (Abschnitt 22) |

**Cloudflare:** `aslani.work` liegt bei Cloudflare. Seit dem 03.10.2026 laufen beide Einträge „proxied“ (orange Wolke, CNAME auf `aslani.work`) zum Nginx Proxy Manager (DECISIONS ADR-11; hebt „DNS only“ vom 25.09.2026 auf). Cloudflare sieht damit den Verkehr im Klartext. Einstellungen: SSL-Modus „Full (strict)“; Bot- und Angriffsschutz dürfen den Token-Abruf der API bei Authentik nicht blockieren (scheitert die Anmeldung nach der Rückkehr von Authentik, zuerst Cloudflare → Security → Events prüfen); Anfragen höchstens 100 MB. Vor dem öffentlichen Start die echte Client-IP aus `CF-Connecting-IP` übernehmen, sonst teilen sich alle Nutzer ein Rate-Limit.

**Port von Authentik:** Ist 9000 auf Unraid belegt (z. B. von MinIO), in `authentik/.env` `AUTHENTIK_PORT` ändern (auf `tower` am 03.10.2026: 9010) und im Reverse Proxy dasselbe Ziel eintragen.

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
5. Bei der ersten Anmeldung richtet jede Person den zweiten Faktor ein (Authenticator-App oder Sicherheitsschlüssel). **Danach einmal neu anmelden:** Authentik meldet den zweiten Faktor erst bei einer Anmeldung mit bereits eingerichtetem Gerät, Emprise zeigt beim ersten Mal „Kein Zugang“ mit diesem Hinweis. „Retour à la connexion“ allein hilft nicht, weil Authentik die laufende Anmeldung weiterverwendet: erst bei Authentik abmelden (`https://auth.aslani.work/flows/-/default/invalidation/`) oder ein privates Fenster nehmen. Ein Passkey im Passwort-Manager des Browsers steht im privaten Fenster nicht zur Verfügung. Neben einem Passkey eine Authenticator-App (TOTP) und Notfallcodes (Static tokens) einrichten, sonst sperrt ein verlorenes Gerät aus.

Nicht verwenden: reine Passkey-Anmeldung ohne Passwort. Authentik meldet sie als `user`, nicht als zweiten Faktor; Emprise lehnt sie ab.

## 4. Emprise einrichten

```bash
cd /mnt/user/appdata/emprise-src/deploy/unraid
cp .env.example .env
for v in SECRET_KEY POSTGRES_PASSWORD MIGRATOR_DB_PASSWORD APP_DB_PASSWORD READONLY_DB_PASSWORD; do
  sed -i "s/^$v=$/$v=$(openssl rand -hex 32)/" .env
done
```

In `.env` von Hand: `OIDC_ISSUER` (`https://auth.aslani.work/application/o/emprise/`), `OIDC_CLIENT_SECRET` (Wert aus Abschnitt 3), Pfade `APPDATA_DIR` und `BACKUP_DIR`. `chmod 600 .env`.

Dateiverzeichnis für Reglements, Steckbriefe, Berichte und Übergaben (`APPDATA_DIR/files`, im Container `/data/files`); es muss dem Container-Nutzer 10001 gehören, sonst bricht der Migrate-Job bei `storage-init` ab:

```bash
mkdir -p /mnt/user/appdata/emprise/files && chown 10001:10001 /mnt/user/appdata/emprise/files
```

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

Migrationen werden dabei **nicht** zurückgedreht: Sie sind abwärtskompatibel (erst erweitern, später aufräumen). `/api/health/ready` meldet dann `"migration_state": "ahead"` und bleibt bereit (200). Nur `"pending"` (Image neuer als Datenbank, Migrationsjob fehlt) ergibt 503. Eine getrennte Staging-Umgebung gibt es nicht; neue Funktionen laufen hinter Feature-Flags (Abschnitt 10). Alte Images gelegentlich aufräumen: `docker image ls emprise-backend`.

**Emprise Analyse** läuft seit dem 29.09.2026 in derselben Anwendung unter `/analyse` (Abschnitt 22); es gibt keinen zweiten Stack und keine zweite Authentik-Anwendung mehr.

## 6. Sicherung und Wiederherstellung

| Was | Wie | Wohin |
|---|---|---|
| Datenbank Emprise | Container `backup`, täglich um `BACKUP_HOUR`, 14 Tage | `BACKUP_DIR` |
| Dateien (`APPDATA_DIR/files`), Datenbank Authentik | Unraid-Plugin „Appdata Backup“ über `APPDATA_DIR` beider Stacks | Backup-Freigabe |
| Außer Haus | `BACKUP_DIR` und Appdata-Sicherung zusätzlich auf ein zweites Ziel in der EU | z. B. zweites Gerät oder EU-Speicher |

Sofortige Sicherung: `docker compose run --rm backup now`. Die Datei `BACKUP_DIR/last-success` enthält den Zeitpunkt der letzten erfolgreichen Sicherung.

**Wiederherstellung** (zuerst als Übung in eine Testdatenbank, Ergebnis in die Tabelle unten eintragen):

```bash
docker compose exec -T db psql -U postgres -c "CREATE DATABASE restore_test OWNER migrator"
docker compose exec -T db psql -U postgres -d restore_test -c "CREATE EXTENSION postgis"
docker compose exec -T backup sh -c 'pg_restore --no-owner --no-comments --role=migrator -d restore_test "$(ls /backups/emprise-*.dump | tail -1)"'
```

Für den Ernstfall statt `restore_test` die Datenbank `emprise` neu anlegen (vorher `api`, `worker`, `worker-long` stoppen), danach `./deploy.sh`.

Übungen mit Datum, Dauer und Datenstand:

| Datum | Umgebung | Verfahren | Dauer | Ergebnis |
|---|---|---|---|---|
| 14.09.2026 | lokal, Unraid-Stack | `backup now` → `pg_restore --no-owner --no-comments` in `restore_test` | < 1 min (leere Datenbank) | vollständig, 13 Tabellen, Schutztrigger vorhanden |
| – | Unraid | Übung mit echtem Datenstand | – | ausstehend |

## 7. Überwachung

Vorschlag ohne externe Dienste: Uptime Kuma als Container auf Unraid mit drei Prüfungen und Benachrichtigung (Mail oder Messenger):

| Prüfung | Alarm, wenn |
|---|---|
| `https://building-configurator.aslani.work/api/health/ready` | nicht 200 |
| `https://building-configurator.aslani.work/api/health/jobs` | nicht 200 (`worker` oder `worker-long` steht; die Antwort nennt die Warteschlange) |
| `https://auth.aslani.work/-/health/ready/` | nicht 200 |

Die Frische der Sicherung prüft ein User Script: Alarm, wenn `last-success` älter als 26 Stunden ist.

## 8. Grenzen bis zur Beta

- Verfügbarkeit hängt an Strom und Internetanschluss; kein zweiter Standort.
- Keine Wiederherstellung auf beliebige Zeitpunkte, nur auf die letzte nächtliche Sicherung (Datenverlust bis 24 h).
- Mailversand braucht einen Anbieter (E2); bis dahin scheitern Mailjobs und werden wiederholt.
- Vor dem öffentlichen Start von R1 wird über das Hosting neu entschieden (Plan 6.4).

## 9. Module auf Unraid

Migrationen, Flags, Jobs und ausgehender Zugang je Modul stehen in Abschnitt 10; hier nur, was auf Unraid dazukommt.

- **Ausgehender Zugang:** Die Compose-Netze sperren ausgehenden Verkehr nicht; eine Firewall auf Unraid oder im Router muss die Hosts aus Abschnitt 10 erlauben.
- **`.env`** (Namen ohne Präfix `EMPRISE_`, `compose.yaml` setzt ihn): `CADASTRE_COMMUNES=["44209","44…"]` (INSEE-Codes, D1), `OPENROUTER_API_KEY`, `RULES_BUDGET_MONTH_USD`. `EMPRISE_OFFICE_EMAIL` (Modul A) ist in `compose.yaml` und `.env.example` noch nicht verdrahtet (ROADMAP 4.5). Weitere Einstellungen (Zeitlimits, Rate-Limits, Basis-URLs) haben Standardwerte in `backend/app/config.py`, Festlegungen in [DECISIONS.md](../../DECISIONS.md) und im Archiv (`docs/archiv/ANNAHMEN.md`).
- **Géorisques-Token** nur, falls die Schnittstelle v1 abgeschaltet wird: in `compose.override.yaml` bei `api`, `worker` und `worker-long` `EMPRISE_GEORISQUES_TOKEN` setzen, nicht leer übergeben.
- **Nach dem ersten Ausliefern:** `docker compose exec api python -m app.cli cadastre-import` (danach wöchentlich durch den Worker); Planstände sofort mit `plu-import` statt nach einer Woche. Ohne Schlüssel stehen die Kapitel auf „gescheitert: not_configured“ und werden nach dem Eintragen innerhalb einer Stunde ausgewertet (`rules_housekeeping`), sofort mit `rules-extract --pending` (kostet Token, Größenordnung in Abschnitt 16). Vor `inquiry`: `legal-seed` (Abschnitt 18). `staff-add` auch für die Katalogpflege (`catalog_admin` oder `architect`). Die Demo-Typen `demo_*` (`tests.e2e_seed_types`) **nie in Produktion**.
- **Image:** Der Steckbrief braucht WeasyPrint mit `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b`, `libfribidi0` und `fonts-dejavu-core` im Backend-Image (rund 80 MB mehr). Nach dem Aktualisieren: `docker compose exec api python -c "import weasyprint"`. Caddy-Ersetzungen beim nächsten Caddy-Release prüfen (ANNAHMEN A27).
- **Gegenprobe nach dem Ausliefern:** `docker compose exec api python -m app.cli envelope-check --commune 44209 --sample 50` (0 Fehler erwartet).
- **Speicher:** Kataster grob 10–20 MB in PostGIS je Gemeinde in der Größe von Treillières (≈ 8.800 Parzellen); das règlement écrit im Dateiverzeichnis (PLUi Erdre et Gesvres 6,8 MB), Seitentexte und Vorgaben wenige MB je Planstand in PostGIS; Steckbriefe unter `envelope-sheets/`, mit dem Projekt gelöscht und in der Sicherung des Dateiverzeichnisses enthalten.

# Teil B – Module im Betrieb

## 10. Überblick

| Baustein | Aufgabe | Prüfpunkt |
|---|---|---|
| `web` | Frontend, Sicherheitsköpfe, Weiterleitung `/api` | `GET /` |
| `api` | REST-API | `GET /api/health/live`, `/api/health/ready` |
| `worker` | Hintergrundjobs der Warteschlange `default`, Zeitplan | `GET /api/health/jobs` |
| `worker-long` (Unraid) | Warteschlange `long`: Auswertung, Lesen, Texterkennung, Importe | `GET /api/health/jobs` |
| `migrate` | Einmaliger Job vor jeder Auslieferung: `alembic upgrade head` | Exit-Code |
| Datenbank | PostgreSQL 16 + PostGIS 3, Rollen `migrator`, `app`, `readonly` | `/api/health/ready` |
| Dateiverzeichnis | Dateien, privat, unter `EMPRISE_FILES_DIR` (`/data/files`, seit 29.09.2026 statt SeaweedFS) | `GET /api/v1/admin/ops/status` → `storage_ok` |
| Mail | Transaktionsmails über SMTP | `POST /api/v1/admin/ops/test-mail` |

Alarme (Uptime-Dienst, minütlich): `/api/health/ready` ≠ 200 → „API oder Datenbank gestört“; `/api/health/jobs` ≠ 200 → „Worker steht oder ist überlastet“. Dazu Alarme auf Log-Einträge (Fehler-Tracking): `rules_extract_failed` (Kapitel gescheitert, Abschnitt 16), `rules_budget_exceeded` (Monatsbudget der Auswertung erreicht), `road_import_implausible` (Straßenachsen, Abschnitt 15), `dossier_failed` (Dossier einer Fassung endgültig gescheitert, Abschnitt 21). Das in Plan G3 6.2 genannte `envelope_derive_failed` ist im Code nicht angelegt.

**Module im Betrieb.** Migrationen laufen beim Ausliefern mit (Job `migrate`). Freischalten über Feature-Flags (Plan 4.2): intern `python -m app.cli flag-set <flag> --role architect`, Beta für eingeladene Projekte über die Admin-API (für `inquiry` und `configurator` war `--all` für die Beta genannt), öffentlich `--all`, abschalten `--off`; jede Änderung steht im `audit_log`. `envelope_simulation` setzt `site_selection` und `rules_simulation` voraus (Plan G3 4.2).

| Modul | Migration | Flag | Jobs (Rhythmus) | Ausgehender Zugang von API und Worker | Vor dem Freischalten |
|---|---|---|---|---|---|
| P | 0001 | – | `mail_send`, `retention_cleanup` (täglich), `housekeeping` (stündlich) | SMTP-Anbieter (E2) | `staff-add` (11), SMTP (13) |
| G1 | 0002, 0006, 0012 | `site_selection` | `cadastre_import` (wöchentlich, auch beim ersten Start), `site_enrich`, `site_housekeeping` (alle 6 h) | `data.geopf.fr`, `cadastre.data.gouv.fr` (leitet auf `*.cloud.ovh.net` weiter), `georisques.gouv.fr`; Browser der Besucher: Kartenkacheln von `data.geopf.fr` | Einzugsgebiet, Erstimport (15) |
| G2 | 0003, 0004, 0013, 0014, 0015, 0016, 0017 | `rules_simulation` | `plu_import` (wöchentlich, auch beim ersten Start), `rules_extract`, `rules_housekeeping` (stündlich), `rules_document_read` (Analyse, 22) | zusätzlich `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `openrouter.ai` (Worker; die API für die Liste der Modelle, PU11) | Schlüssel, Budget und Modell (16) |
| G3 | 0005 | `envelope_simulation` | `envelope_sheet` | – | WeasyPrint im Image (17) |
| H1 | 0007 | – (nur Rollen: bearbeiten `architect`, `catalog_admin`; lesen `ops`) | – (Import synchron) | – | `openpyxl`, `ezdxf`, `python-multipart` im Image; Konto mit `catalog_admin` oder `architect` per `staff-add` |
| A | 0008 | `inquiry` | `mail_send` | – | Büro-Postfach, `legal-seed` (18) |
| H2 | 0009 | `configurator` | – | – | ein veröffentlichter Typ (19) |
| H3 | 0010 | `configurator` (dasselbe Flag) | – | – | veröffentlichter Preiskatalog mit Linien, Optionen und Preisen netto (20) |
| V | 0011 | `submission` (Übergabe); „Mein Vorgang“ mit `inquiry` oder `submission` | `dossier_generate`, `mail_send` | – | `legal-seed` für die zwei neuen Texte, Büro-Postfach (21) |

„Emprise Analyse“ läuft in derselben Anwendung unter `/analyse`: Abschnitt 22.

## 11. Zugang für Mitarbeitende

- Freischalten oder Rollen setzen: `python -m app.cli staff-add person@buero.fr architect rules_admin`
- Sperren (beendet alle Sitzungen): `python -m app.cli staff-deactivate person@buero.fr`
- Die Person meldet sich unter `/buero` an. „Kein Zugang“ mit Grund `unknown`: Adresse nicht freigeschaltet oder beim Identitätsdienst anders geschrieben. Grund `mfa`: zweiter Faktor fehlt. Grund `email_unverified`: Adresse beim Identitätsdienst nicht bestätigt.
- Jede Freischaltung, Sperre, An- und Abmeldung steht im `audit_log`.

## 12. Jobs

- Zustand: `GET /api/v1/admin/ops/status` (Rolle `ops`): Anzahl je Status, fehlgeschlagen in 24 h, ältester wartender Job.
- Ein Job wird bis `max_attempts` mit wachsendem Abstand wiederholt (30 s, 60 s, 120 s … höchstens 1 h). Danach `failed` und Meldung an das Fehler-Tracking.
- Stürzt ein Worker ab, stellt ein anderer den Job nach Zeitlimit + 60 s zurück.
- **Zwei Warteschlangen** (seit 29.09.2026, Migration 0022, REFACTORING_PLAN S5): `long` für `rules_extract`, `rules_document_read`, `rules_document_ocr`, `plu_import` und `cadastre_import`, alles andere in `default`. Auf Unraid bedient `worker` nur `default` und `worker-long` nur `long` (`EMPRISE_WORKER_QUEUES`); lokal bedient ein Worker beide (Vorgabe). `/api/health/jobs` meldet je Warteschlange (`queues.default`, `queues.long`); die Schwelle von `long` ist `EMPRISE_JOB_WAITING_ALARM_MINUTES_LONG` (120 min), weil ein Job dort hinter einer Auswertung von bis zu 60 min wartet. Alarm nur in `long`: `worker-long` läuft nicht.
- Fehlgeschlagene Jobs erneut einreihen (bis `POST /admin/jobs/{id}/retry` existiert):
  ```sql
  UPDATE job SET status = 'queued', attempts = 0, run_after = now(), finished_at = NULL WHERE id = '<id>';
  ```
  Nur mit Rolle `migrator` und nur, wenn die Ursache behoben ist; Handler sind idempotent.

## 13. Mailzustellung gestört

1. `POST /api/v1/admin/ops/test-mail` auslösen; Status des Jobs über `GET /api/v1/jobs/{id}`.
2. `last_error` des Jobs lesen (`SELECT kind, attempts, last_error FROM job WHERE kind = 'mail_send' ORDER BY created_at DESC LIMIT 20`).
3. Häufige Ursachen: SMTP-Zugangsdaten abgelaufen, SPF/DKIM/DMARC der Absenderdomain, Sperre beim Anbieter.
4. Nach Behebung wartende Jobs laufen von selbst weiter; endgültig fehlgeschlagene nach Abschnitt 12 erneut einreihen.

## 14. Sicherheitsvorfall

1. Betriebsverantwortung (D5) informieren; Zeitpunkt festhalten.
2. Eindämmen: betroffene Konten sperren (`staff-deactivate`), Geheimnisse in `.env` erneuern und neu ausliefern, bei Verdacht auf Sitzungsdiebstahl alle Sitzungen beenden: `UPDATE staff_session SET revoked_at = now() WHERE revoked_at IS NULL;`
3. Umfang klären: `audit_log`, Logs (ohne personenbezogene Daten), Fehler-Tracking.
4. Sind personenbezogene Daten betroffen: **Meldung an die CNIL binnen 72 Stunden** (Art. 33 DSGVO), bei hohem Risiko Benachrichtigung der Betroffenen (Art. 34).
5. Nachbereitung mit Ursache und Maßnahmen; Festlegungen in `DECISIONS.md` anpassen.

## 15. Kataster und Grundstück (Modul G1)

**Einrichten und Freischalten**

1. Einzugsgebiet setzen: `EMPRISE_CADASTRE_COMMUNES='["44209"]'` (INSEE-Codes; Entscheidung D1).
2. Erstimport: `python -m app.cli cadastre-import` (ohne Internet: `--from-dir <ordner> --release <stand>`). Danach prüft der Worker wöchentlich auf neue Stände.
3. Flag und ausgehender Zugang: Tabelle in Abschnitt 10.

**Kataster ohne Regeln (D1, Île-de-France):** Gemeinden außerhalb von `CADASTRE_COMMUNES` werden nur von Hand importiert und nicht wöchentlich aktualisiert; Parzellenwahl ja, Regeln und Baurahmen nein (Konfigurator im freien Modus). Paris nur als Arrondissements 75101–75120. Für viele Gemeinden im Ordner `deploy/unraid` im Hintergrund, in Paketen von 50, mit zweitem Durchlauf für Gescheitertes (`cadastre-import` bricht bei einer Ausnahme ab, fertige Stände überspringt er):

```bash
docker compose exec -T api python -c "import json,urllib.request as u; [print(c['code']) for d in ('77','78','91','92','93','94','95') for c in json.load(u.urlopen(f'https://geo.api.gouv.fr/departements/{d}/communes?fields=code'))]" > /mnt/user/appdata/emprise/idf_communes.txt
nohup sh -c 'cd /mnt/user/appdata/emprise-src/deploy/unraid; for pass in 1 2; do sed "s/^/--commune /" /mnt/user/appdata/emprise/idf_communes.txt | xargs -n 100 docker compose exec -T api python -m app.cli cadastre-import; done; echo IDF FERTIG' > /mnt/user/appdata/emprise/idf_import.log 2>&1 &
```

Lokal gemessen (03.10.2026): 1 265 Gemeinden in 51 Minuten; mit Treillières und Paris 3,7 Mio. Parzellen, Datenbank 3,2 GB, eine Sicherung (`pg_dump --format=custom`) 945 MB, bei 14 Tagen Aufbewahrung rund 13 GB im Sicherungsordner. Gescheitert: `grep ": failed" idf_import.log`.

**Stand prüfen:** `GET /api/v1/admin/cadastre/imports` (Rolle `ops`): letzter Import je Gemeinde mit Stand, Anzahl Parzellen, Gebäude, Straßenachsen (`roads = -1`: Achsen fehlen, siehe unten) und Fehler.

**Katasterimport gescheitert** (Job `cadastre_import` endgültig `failed`, Meldung im Fehler-Tracking)

1. `error` des letzten Imports lesen. Der bisherige Stand bleibt in jedem Fall erhalten.
2. `parcel_count_change:<alt>-><neu>`: Parzellenzahl weicht mehr als max(2 %, 50) ab. Stichprobe im Kartenausschnitt der Gemeinde ansehen; ist der neue Stand plausibel (z. B. Flurneuordnung), `python -m app.cli cadastre-import --commune <insee> --force`.
3. `too_many_unusable_parcels`: Quelldaten fehlerhaft. Nächsten Stand abwarten; nicht erzwingen.
4. `transport:*`, `http_5xx`: Etalab nicht erreichbar. Der Job wiederholt sich; sonst am nächsten Tag von Hand starten (`POST /api/v1/admin/cadastre/imports`).
5. `roads = -1` bei erfolgreichem Import: der WFS der Géoplateforme war nicht erreichbar oder lieferte weniger als die Hälfte der bisherigen Straßenachsen (Log `road_import_implausible`). Die bisherigen Achsen bleiben; ohne jede Achse werden Kanten unsicherer eingeordnet. Der nächste wöchentliche Lauf holt die Achsen nach; eilig: `cadastre-import --commune <insee>` (mit `--force` auch bei weniger Achsen).

**Géoplateforme oder Géorisques ausgefallen**

- Adresssuche meldet `geocoding_unavailable`: Kunden wählen die Parzelle über Karte oder Parzellennummer; Parzellen kommen aus der eigenen Datenbank.
- Kartenkacheln fehlen: Parzellen sind trotzdem sichtbar und wählbar; Parzellennummer funktioniert immer.
- Gelände oder Risiken `unavailable`: Hinweis „nicht abgefragt“ beim Grundstück. Sobald der Dienst wieder antwortet: `POST /api/v1/admin/sites/enrich-retry` (Rolle `ops`) stößt alle betroffenen Grundstücke erneut an. Auch unerwartete Antworten und ein Zeitlimit enden nach dem letzten Versuch als `unavailable`; bleibt eine Abfrage ohne wartenden Job auf „wird abgefragt“ stehen (Worker verloren), setzt `site_housekeeping` (alle 6 h) sie nach 30 Minuten auf `unavailable`.
- Adressvorschläge liegen 24 h im Arbeitsspeicher des API-Prozesses, nicht in der Datenbank (Annahme G22); nach einem Neustart fragt die API die Géoplateforme erneut.

**Prüfliste im Büro:** `/buero/grundstuecke` zeigt nur Projekte mit Anfrage (AF04), Grundstücke mit unbestätigten Kundenkorrekturen zuerst. Solange eine Kundenkorrektur unbestätigt ist, ist der Baurahmen nicht bindend.

## 16. Regelwerk (Modul G2)

**Einrichten und Freischalten**

1. Schlüssel von OpenRouter und Monatsbudget setzen: `EMPRISE_OPENROUTER_API_KEY`, `EMPRISE_RULES_BUDGET_MONTH_USD` (Unraid: `OPENROUTER_API_KEY`, `RULES_BUDGET_MONTH_USD` in `.env`). Budget entschieden am 25.09.2026: **150 $ je Monat** auf Unraid, lokal 20 $ (Vorgaben in `.env.example` und den Compose-Dateien). Den Schlüssel trägt der Nutzer selbst ein. **Modell wählen:** in `/analyse/verwaltung` → „KI-Modell“ (Rollen `ops` und `rules_admin`) für alle künftigen Auswertungen beider Produkte, ohne Neustart; Preise aus der Liste von OpenRouter (PU11, Abschnitt 23). **Vorgabe des Modells**, solange niemand wählt: `EMPRISE_RULES_MODEL` (Unraid `RULES_MODEL`), Name wie auf openrouter.ai/models, Vorgabe `anthropic/claude-opus-5.5` mit 4 $/20 $ je Million Token (seit 28.09.2026, vorher Opus 5; die Umgebung leitet den Preis fürs Lesen aus dem Cache mit 10 % ab und zählt ihn damit doppelt so hoch wie die Liste, 0,40 $ statt 0,20 $ – genau zählt ein in `/analyse/verwaltung` gewähltes Modell); beim Wechsel die Preise je Million Token mit anpassen (`EMPRISE_RULES_PRICE_INPUT_PER_MTOK`, `EMPRISE_RULES_PRICE_OUTPUT_PER_MTOK`; Unraid ohne `EMPRISE_`), sonst stimmen Kostenzählung und Budget nicht. Wirksam nach `docker compose up -d api worker` (auf Unraid auch `worker-long`); ausgewertete Kapitel bleiben, bis sie neu ausgewertet werden. **Eingabeform:** Modelle ohne PDF-Eingabe bekommen die Textschicht der Seiten statt der PDF-Auszüge (PU12); für die Vorgabe `EMPRISE_RULES_INPUT` (`pdf` oder `text`, Unraid `RULES_INPUT`). **Nachsuche** (VA03–VA08): Nach Auswertung und Gegenprüfung fragt ein dritter Aufruf gezielt nach fehlenden Angaben und offenen Textstellen; an `EMPRISE_RULES_GAP_SEARCH` (Vorgabe `true`), Zusatzseiten aus anderen Teilen des Dokuments höchstens `EMPRISE_RULES_GAP_EXTRA_PAGES_MAX` (15). Kosten je Kapitel mit Opus 5.5 und PDF gemessen 1,46 $ statt 0,59 $, etwa 3,5 Minuten länger (PLAN_G2_VOLLSTAENDIGKEIT 7.5). **Messen** gegen eine Referenzliste ohne Aufruf: `python -m app.cli reference-check beyenes_uc.json --version all` (Listen in `app/rules/reference_seed`). An die Schnittstelle gehen nur öffentliche Planunterlagen (L8); seit E-D19 läuft der Aufruf über OpenRouter als zusätzlichen Drittanbieter statt direkt über die Claude API.
2. Planstände importiert der Worker beim ersten Start und danach wöchentlich (`plu_import`); sofort: `python -m app.cli plu-import` (ohne Internet: `--from-dir`). Jedes Zonenkapitel wird danach als Job `rules_extract` ausgewertet.
3. Flag und ausgehender Zugang: Tabelle in Abschnitt 10.

**Stand prüfen:** `/buero/regeln` bzw. `GET /api/v1/admin/rules/coverage`: je Gemeinde Planstand und Status, je Kapitel Sektoren, Status mit Grund, Läufe, Kosten, offene Pflichtwerte je Sektor; oben Monatskosten und Budget.

**Kosten (Schätzung, nach der ersten echten Auswertung ersetzen):** je Kapitel eine Auswertung mit rund 50–60 PDF-Seiten und eine Gegenprüfung der gefundenen Regeln (Dokumente aus dem Cache, kurze Antwort); Größenordnung 1–2 $ je Kapitel, für Treillières (12 Kapitel) 10–25 $ je Planstand. Neue Planstände erscheinen etwa ein- bis zweimal im Jahr. Das Budget wird vor jedem Aufruf geprüft.

**Automatische Wiederaufnahme:** Der Job `rules_housekeeping` (stündlich) nimmt Kapitel ohne Eingriff wieder auf (Annahme RW22): `pending` ohne wartenden Job nach 30 Minuten; `not_configured`, sobald ein Schlüssel eingetragen ist; `budget_exceeded`, sobald das Budget wieder reicht (Monatswechsel, höheres Budget); vorübergehende Fehler (`rate_limited`, `http_5xx`, `transport:*`, `interrupted:*`) nach 24 h, höchstens bei 6 gescheiterten Aufrufen je Woche; ausgewertete Kapitel nach einer neuen Version der Schranken (Neubewertung aus gespeicherten Antworten, ohne Kosten). `extracting` länger als 70 Minuten wird `interrupted:stale`.

**Kapitel gescheitert** (Status `failed`, Grund in der Abdeckung, Log `rules_extract_failed`)

- `not_configured`, `budget_exceeded`, `rate_limited`, `http_5xx`, `transport:*`, `interrupted:*`: siehe Wiederaufnahme; eilig im Büro „Erneut versuchen“ oder `python -m app.cli rules-extract --pending`. Beides nutzt gespeicherte Teile und kostet nur für fehlende.
- `auth`, `model_not_found`, `bad_request:…`: Konfiguration prüfen (Schlüssel, `EMPRISE_RULES_MODEL`); danach „Erneut versuchen“.
- `refusal`: Das Modell hat abgelehnt, auch der Rückfall. Einmal „Erneut versuchen“; bleibt es dabei, sehen Kunden „nicht verfügbar“, das Büro prüft bei Anfrage.
- `max_tokens`: Sektoren werden automatisch auf mehrere Aufrufe verteilt; der Grund bleibt nur, wenn schon ein einzelner Sektor zu lang ist. Der Entwicklung melden.
- `chapter_too_long`: Kapitel und allgemeine Seiten über 150 Seiten, meist falsch erkannte Kapitelgrenzen. Kein Aufruf; der Entwicklung melden.
- `chapter_not_detected`: Das Kapitel kommt im aktuellen Planstand nicht mehr vor.

**„Neu auswerten“** (nur bei ausgewerteten Kapiteln, mit Rückfrage) wertet vollständig neu aus und kostet erneut. Ein zweiter Klick legt keinen zweiten Job an, solange einer wartet oder läuft.

**Import gescheitert** (Job `plu_import` endgültig `failed`): meist GPU nicht erreichbar oder Antwort abgeschnitten (`truncated`). Ein vorhandener Planstand bleibt aktiv, die Gemeinde behält ihn (Fehler `check_failed:…` in der Abdeckung). Später `python -m app.cli plu-import --commune <insee>`.

**Planstand erneuern:** `plu-import --force` aktualisiert den Planstand an Ort und Stelle (Annahme RW20): Korrekturen des Büros, gespeicherte Aufrufe und Kosten bleiben, unveränderte Kapitel werden nicht neu ausgewertet. Ein geändertes Datum im GPU löst dasselbe beim wöchentlichen Lauf aus.

**Neuer Planstand:** Bis alle Kapitel ausgewertet sind, sehen Kunden die Regeln des vorigen Planstands als „veraltet“; die Abdeckung nennt ihn (Annahme RW21). Ist der neue Stand nicht lesbar (`no_regulation`, `multiple_regulations`, `no_chapters`), bleibt der vorige als „veraltet“ sichtbar. `multiple_regulations`: Das règlement écrit besteht aus mehreren Dateien (Bände); das wird noch nicht ausgewertet (RW23), das Büro prüft bei Anfrage.

**Viele `unknown`-Werte in einem Kapitel:** Regelwerk im Büro öffnen (Zitat, Grund, Alternativen aus Auswertung und Gegenprüfung). Liegt es an der Auswertung, nach Prompt- oder Modelländerung neu auswerten; liegt es am Planwerk (Werte im Zonenplan), bleibt es bei `unknown`. Korrekturen des Büros sind freiwillig (D11).

## 17. Baurahmen (Modul G3)

Der Baurahmen wird bei jedem Abruf aus Grundstück und Regeln gerechnet und nicht gespeichert. Es gibt daher nichts nachzuführen: Sobald Gelände, Kanten oder Regeln stimmen, stimmt auch der Baurahmen.

**Kunde sieht „kein auswertbarer Bebauungsplan“**

1. Regeln prüfen: `GET /api/v1/admin/projects/<id>/rules` oder `/buero/regeln`. Steht die Zone auf `in_progress` oder `unavailable`, liegt es an G2 (Abschnitt 16), nicht an G3.
2. Liegt das Grundstück in keiner Zone des Planwerks (`no_zone`), prüfen, ob der Planstand die Gemeinde abdeckt (`plu-import --commune`).

**Fläche wirkt zu groß oder zu klein**

- `strict.complete = false` mit `incomplete_reasons` nennt die Kante, deren Abstand fehlt. Ursache ist eine Regel mit Status `unknown` in G2; Abhilfe: Kapitel erneut auswerten oder Korrektur für die Zone (Abschnitt 16).
- `band_unclear`: Das Modell hat nicht gesagt, ob das Bauband für den ganzen Baukörper gilt. Nach einer erneuten Auswertung ab `PROMPT_VERSION g2-prompt-3` (heute `g2-prompt-4`, ANNAHMEN EA06) ist der Parameter gesetzt.
- `zones_without_rules`: Eine Teilfläche ohne ausgewertete Regeln bleibt bewusst leer (BR04).

**Steckbrief scheitert**

- Job `envelope_sheet` in `/api/v1/admin/ops/status` oder `GET /api/v1/jobs/<id>`. Der Job ist idempotent; ein Fehlschlag wird einmal wiederholt.
- `skipped: input_changed` ist kein Fehler: Die Eingaben haben sich seit dem Auftrag geändert, der nächste Klick fordert den neuen Stand an.
- Fehlt WeasyPrint (`cannot load library`), fehlen die Systembibliotheken im Image (`libpango-1.0-0`, `libpangoft2-1.0-0`, `fonts-dejavu-core`); Image neu bauen.

**Regelmäßig prüfen**

```bash
docker compose exec api python -m app.cli envelope-check --commune 44209 --sample 200
```

Der Lauf legt nichts an (Transaktion wird zurückgerollt) und meldet Ausnahmen, Dauer und die Verteilung der Hinweise. Nach einer neuen `ENGINE_VERSION` von G2 oder G3 und nach einem neuen Planstand ist er die schnellste Gegenprobe (Werte des letzten Laufs: BR12).

## 18. Anfrage (Modul A)

Keine neuen externen Dienste; Mail läuft über den bestehenden Weg (Abschnitt 13).

**Vor der Freischaltung (`flag-set inquiry`)**

1. `EMPRISE_OFFICE_EMAIL` auf die echte Sammeladresse des Architekturbüros setzen (Vorschlag `buero@emprise.local` ist ein Platzhalter).
2. Vorläufige Einwilligungstexte einmalig veröffentlichen, falls noch keine Version besteht:

   ```bash
   docker compose exec api python -m app.cli legal-seed
   ```

   Ohne diese Texte scheitert `POST .../inquiry/confirm` mit `503 legal_text_missing`. Endgültiger Wortlaut nach Rechtsberatung: neue Version über `POST /admin/legal-texts` veröffentlichen, keine Codeänderung nötig.
3. Flag `inquiry` setzen (Abschnitt 10).

**Anfrage kommt nicht beim Büro an**

- Job `mail_send` in `/api/v1/admin/ops/status` prüfen (wie Abschnitt 13); die Anfrage selbst ist bereits gespeichert, auch wenn der Mailversand scheitert (`inquiry` committet vor den Mail-Jobs).
- `office_mail`/`customer_mail` sind zwei getrennte Jobs; ein Fehlschlag der einen betrifft die andere nicht.

**Löschung eines Projekts mit Anfrage**

`DELETE /api/v1/projects/<id>` liefert `409 deletion_requires_office`, sobald eine Anfrage besteht (Plan A 3.9, D6 noch offen). Es gibt noch keine Büro-Funktion für die Endlöschung danach; bis dahin händisch in der Datenbank, mit Audit-Eintrag.

## 19. Konfigurator: Typen und Lage (Modul H2)

Keine neuen externen Dienste und keine neuen Jobs. Zulässigkeit und Prüfung der Lage werden bei jedem Abruf aus Grundstück, Regeln und veröffentlichtem Katalog gerechnet; gespeichert werden nur der gewählte Typ (als Typversion), die Lage und die Grenzschalter (Tabelle `configuration`, Migration 0009, keine neue Sequenz).

**Vor der Freischaltung (`flag-set configurator`)**

1. Mindestens ein Typ muss veröffentlicht sein (Büro, `/buero/katalog`). Ohne Typen zeigt die Seite „Es ist noch kein Haustyp veröffentlicht“.
2. Lokal zum Ansehen: `docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types` legt drei erfundene Typen `demo_*` an. **Nie in Produktion.**
3. Flag `configurator` setzen (Abschnitt 10).

**Typ wird zu Unrecht gesperrt oder zugelassen**

- Die Karte nennt jeden Grund mit dem Code der Prüfung (`GET /api/v1/projects/<id>/catalog/types`, Feld `reasons` mit Regelart, Seite und Zitat). Bindend ist nur eine wirksame Regel; was `unknown` ist, steht unter `hints`. Ursache eines falschen Sperrgrunds ist fast immer die Regel in G2: Zitat prüfen, Kapitel neu auswerten oder Korrektur für die Zone/das Projekt setzen (Abschnitt 16).
- `no_valid_position`: Der Typ passt in keiner erlaubten Drehung auf die bebaubare Fläche. Der Baurahmen (Abschnitt 17) zeigt die Fläche; ein Haus von 12 × 8 m braucht mindestens diese Maße plus die Abstände.
- Fehlen die Fassadenrollen am Typ (`facade_roles_missing`), richtet sich die Ausrichtung nach Modellnorden; im Büro unter `/buero/katalog` je Typ zuweisen (das geht nur an einem Entwurf, danach neue Version).
- Höhenprüfungen sind `unknown`, solange das Gelände fehlt oder steiler als 5 % ist (`height_unverifiable`); das Gelände kommt über den Job `site_enrich` (Abschnitt 15).

**Lage wird abgelehnt (`422 placement_violation`)**

Die Antwort enthält alle Prüfungen mit Kante, Soll und Ist. `rotation_not_allowed` nennt die erlaubten Drehungen. `revision_conflict` heißt: Die Konfiguration wurde in einem anderen Tab geändert; die Oberfläche lädt neu.

**Regelmäßig prüfen**

Nach einem neuen Planstand, neuen Regeln (G2) oder einer neuen Katalogversion können gespeicherte Konfigurationen ungültig werden. Das ist beabsichtigt: `GET /projects/<id>/configuration` prüft neu und zeigt die Verstöße; gelöscht wird nichts.

## 20. Konfigurator: Linie, Optionen und Kosten (Modul H3)

Keine neuen externen Dienste und keine neuen Jobs, dasselbe Flag `configurator` wie H2. Auswahl, Nebenbauten, Flächen, Prüfungen, Energie und Kosten werden bei jedem Abruf gerechnet; gespeichert werden nur die Versionen von Linie und Optionen (`configuration.package_version_id`, `configuration.modules`). Migration `0010` ergänzt Spalten mit Standardwert, das Rückrollen auf das vorige Image bleibt möglich.

**Vor dem Freischalten von Linie, Optionen und Kosten**

1. **Preiskatalog veröffentlichen** (`/buero/katalog/preise`, „Preiskatalog veröffentlichen“). Ohne veröffentlichten Katalog gibt es weder wählbare Linien noch Optionen noch Kosten; der Konfigurator sagt das ausdrücklich („Es ist noch kein Preiskatalog veröffentlicht“). Ein Import (XLSX) schreibt in den **Entwurf**; nach der Veröffentlichung entsteht beim nächsten Import ein neuer Entwurf, der die Zeilen der veröffentlichten Version übernimmt.
2. **Preise netto (HT) eintragen.** Angezeigt wird brutto mit dem Satz des Katalogs (20 %, `vat_rate_default`). Wer brutto einträgt, bekommt 20 % zu viel im Korridor. Terrasse: der Wert je Typ gilt **je m²**; alle anderen Optionen sind ein fester Aufschlag.
3. **Linien und Optionen veröffentlichen** (`/buero/katalog/linien-optionen`) und im Blatt „Preise“ des Typdatenblatts (XLSX) je Linie und Option eine Zeile führen. Eine Option ohne Zeile für den Typ erscheint für diesen Typ nicht (Anwendbarkeit).
4. **Art und Maße** einer Option: `terrace` (Tiefe, Höhe über Gelände, Versiegelungsfaktor) und `carport` (Stellplätze, Breite, Tiefe, Höhe). Zwei Carports (einstellig, zweistellig) sind zwei Optionen; sie schließen sich von selbst aus. **Material** von Fassade und Dach an Option und Linie nur, wenn die Regelprüfung es nutzen soll.
5. **RE2020-Befund** je Typ und Linie (Formular auf der Seite des Typs unter `/buero/katalog`; `PUT /api/v1/admin/catalog/types/<typ>/energy-assessment/<linie>`): ohne Befund steht „Wärmeschutznachweis erforderlich“ und es gibt keinen Aufpreis.
6. Fassadenrollen der Typen zuweisen (H2): ohne Rolle `garden` ist keine Terrasse möglich (`no_garden_facade`).
7. Lokal zum Ansehen: `docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types` legt zusätzlich Linien, Optionen, Preise (erfunden) und einen veröffentlichten Preiskatalog an. **Nie in Produktion.**

**Keine Kosten oder kein Korridor**

`GET /api/v1/projects/<id>/configuration`, Feld `costs`: `available = false` mit `reason`. `catalog_unavailable` heißt: kein veröffentlichter Preiskatalog (Schritt 1). `base_price_missing`: für den Typ gibt es weder eine Zeile im Katalog noch einen Basispreis an der Typversion.

**Option nicht wählbar (`blocked`) oder abgelehnt**

`GET /api/v1/projects/<id>/catalog/options` nennt je Option den Zustand und die Gründe: `excluded_by` (Ausschluss), ein bindender Verstoß mit Code (`annex_footprint`, `footprint_total`, `unsealed_min`, `no_garden_facade`, `terrace_outside_site`, `no_valid_position`, `facade_material`, `roof_material`). Bindend ist nur eine wirksame Regel oder eine geometrische Gewissheit; `unknown` und `carport_setback_*` sind Hinweise. `PATCH` lehnt mit `invalid_selection` (Auswahl passt nicht zum Katalog) oder `selection_blocked` (neuer bindender Verstoß) ab. `no_valid_position` beim Carport: neben dem Haus ist kein erreichbarer Platz; das Haus zur Seite ziehen oder den kleineren Carport wählen.

**Katalogpflege: Veröffentlichung**

Linie und Option lassen sich nur aus `draft`/`review` veröffentlichen (`409 version_not_publishable`); eine später veröffentlichte ältere Version verdrängt die neuere nicht.

## 21. Vorentwurf-Übergabe (Modul V)

Keine neuen externen Dienste. Neu sind die Tabellen `submission` (Fassungen mit Snapshot und Dossier) und `inquiry_message`, die Spalten `consent.submission_id` und `customer.locale`, die Zustände `rueckfrage` und `zurueckgezogen` (Migration `0011`) und der Job `dossier_generate` (PDF fr/de und DXF, 2–4 s lokal). Dateien liegen im Dateiverzeichnis unter `dossiers/<Projekt>/<Fassung>/`. Plan und Festlegungen: [PLAN_V_VORENTWURF_UEBERGABE.md](../../docs/archiv/PLAN_V_VORENTWURF_UEBERGABE.md), ANNAHMEN VU01–VU16.

**Vor dem Freischalten (`flag-set submission`)**

1. H3 muss laufen (veröffentlichter Preiskatalog, Abschnitt 20) und A eingerichtet sein (Büro-Postfach `EMPRISE_OFFICE_EMAIL`, Abschnitt 18).
2. `docker compose exec api python -m app.cli legal-seed` veröffentlicht zusätzlich `notice.design_confirmation` und `consent.transmission_design` (vorläufig, wie A). Ohne sie scheitert die Übergabe mit `503 legal_text_missing`.
3. Flag `submission` setzen; „Mein Vorgang“ (`/vorgang`) und der Zugangslink funktionieren auch mit `inquiry` allein.

**Rückrollen:** Die Migration erweitert nur. Ein zurückgerolltes Image kennt die Zustände `rueckfrage` und `zurueckgezogen` nicht; die Anfragenliste des Büros scheitert dann an solchen Vorgängen, bis das neue Image wieder läuft.

**Dossier fehlt oder ist gescheitert**

- `dossier_status = pending`: Job `dossier_generate` in `/api/v1/admin/ops/status` prüfen; der Worker muss laufen (WeasyPrint und `ezdxf` im Image).
- `failed` nach drei Versuchen (Log `dossier_failed`, Fehler in `submission.dossier_error`): Ursache beheben, dann im Anfrage-Detail „Dossier neu erzeugen“ (`POST /api/v1/admin/projects/<id>/submissions/<n>/dossier`). Das Dossier entsteht allein aus dem Snapshot; es zeigt immer die übergebene Fassung.
- Der Kunde merkt vom Fehler nichts; seine Fassung und die Mails sind schon unterwegs.

**Übergabe abgelehnt**

- `409 review_changed`: Seit dem Anzeigen hat sich etwas geändert (`changes`: `site`, `rules`, `catalog`, `configuration`, `result`, `engine`). Beabsichtigt; die Oberfläche lädt neu und der Kunde übergibt erneut.
- `409 deviations_not_acknowledged`: bindende Verstöße (meist nach einem Regel- oder Katalogwechsel); der Kunde muss „mit Abweichungen übergeben“ bestätigen.
- `409 submission_incomplete`: Typ, Lage oder (wenn der Katalog Linien anbietet) Linie fehlen.

**Nachrichten und Zustände:** Eine Nachricht des Büros setzt `neu`/`in_bearbeitung` auf `rueckfrage` und schickt dem Kunden Text und Zugangslink; eine Antwort des Kunden setzt `rueckfrage` auf `in_bearbeitung`. `zurueckgezogen` setzt nur der Kunde; eine neue Fassung öffnet den Vorgang wieder (`neu`). Gelöscht wird nichts (D6).

**Zugangslink:** 30 Tage gültig (`EMPRISE_ACCESS_LINK_DAYS`), signiert mit `EMPRISE_SECRET_KEY` (ein neuer Schlüssel macht alle Links ungültig). Das Einlösen gibt ein neues Projekt-Cookie aus; andere Geräte des Kunden brauchen dann ebenfalls den Link. Wer keinen gültigen Link hat, fordert auf `/vorgang` einen neuen an (Mail `access_link`, nur an bestätigte Adressen mit Vorgang).

**DXF in ArchiCAD übernehmen** (vom Büro noch nicht erprobt, Plan V 6)

- `…_local.dxf`: Einheit Meter; der Ursprung (0, 0) ist der Punkt auf der Ebene `ORIGINE`, seine Lambert-93-Koordinaten stehen im Text auf der Ebene `TEXTE`. In ArchiCAD „Ablage > Interoperabilität > Zusammenführen“ (DXF), Einheit Meter, Einfügepunkt = Projektnullpunkt; der Plan liegt dann im lokalen System des Projekts.
- `…_L93.dxf`: Koordinaten in Lambert-93 (EPSG:2154). Nur verwenden, wenn das ArchiCAD-Projekt georeferenziert ist (Vermessungspunkt auf Lambert-93); sonst liegt der Plan Kilometer vom Nullpunkt entfernt.
- Ebenen: `PARCELLE`, `LIMITE_VOIE`/`_SEPARATIVE`/`_FOND`/`_AUTRE`, `VOISINS_PARCELLES`, `VOISINS_BATI`, `ZONE_CONSTRUCTIBLE_LARGE`/`_STRICTE`, `MAISON_FACADE`, `MAISON_DEBORD`, `TERRASSE`, `CARPORT`, `ACCES`, `ORIGINE`, `TEXTE`. Bei frei gezeichneten Grundstücken (Weg E) gibt es nur die lokale Datei.

## 22. Emprise Analyse (AN0–AN7)

Aus demselben Repository entsteht ein Bereich für Architekturbüros ([PLAN_ANALYSE.md](../../docs/archiv/PLAN_ANALYSE.md), ANNAHMEN PS01–PS09, UP01–UP19, PU01–PU12, EA01–EA17, KR01–KR09, AU01–AU12, SC01–SC10 und MA01–MA09). Umgesetzt sind **AN0** (Produktschnitt), **AN1** (Parzelle als DXF, GeoJSON, vektorielles PDF oder Zeichnung, Kanten von Hand einordnen, Projekte am Architektenkonto), **AN2** (règlement écrit als PDF hochladen, Zone wählen, Regeln und Baurahmen) **AN3** (bindende Grundfläche, Vollgeschosse, Nutzfläche als Spanne mit Annahmen je Projekt; Zusatzdokumente mit Lotwahl und Vergleich; Gabarit in Höhenstufen und zwei Schnitte), **AN4** (Regeln korrigieren und ergänzen mit Begründung und Fundstelle, Werte aus Zusatzdokumenten übernehmen, zwei Stände vergleichen) und **AN5** (Projekte mit Name, Notiz und Archiv; Lage auf der Katasterebene einpassen, danach Gelände und Risiken; Geländeprofil im Schnitt; Bericht-PDF, DXF lokal und in Lambert-93, GeoJSON), **AN7** (gescannte PDFs) und **AN6** (Organisationen mit Mitgliedern; fremde Büros gesperrt bis E-A5; API-Schlüssel, Budget und Scan-Kontingent je Organisation und Erscheinungsbild seit 29.09.2026 zurückgebaut).

**Eine Anwendung (seit 29.09.2026, DECISIONS ADR-02).** Konfigurator, Büro und Analyse laufen in einer Instanz mit einer Datenbank; die Analyse liegt unter `/analyse` (lokal http://localhost:8080/analyse, auf Unraid `https://building-configurator.aslani.work/analyse`). `EMPRISE_PRODUCT`, `SPA_INDEX`, `compose.analyse.yaml` und der Stack `emprise-analyse` entfallen; alle Router, Jobarten und periodischen Aufgaben laufen in der einen Instanz. Die frühere Datenbank `emprise_analyse` bleibt lokal unangetastet liegen (nicht übernommen, Entscheidung 29.09.2026).

**Einrichten (AN1)**

1. Konto freischalten: `python -m app.cli staff-add person@buero.fr architect` (lokal `docker compose exec api …`). Ohne `--organisation` kommt das Konto in die Organisation des Betreibers („Eigenes Büro“, AN6).
2. Flag setzen: `python -m app.cli flag-set site_selection --role architect`. Ohne das Flag antworten alle Grundstücksendpunkte mit `403 feature_disabled` (UP10); das Flag gilt für Konfigurator und Analyse.
3. Für die Parzelle im Analyse-Bereich ist kein Katasterimport nötig: Sie kommt als DXF, GeoJSON oder PDF oder wird gezeichnet (D17). Mit Kataster (Einzugsgebiet `CADASTRE_COMMUNES`) funktioniert zusätzlich der Katasterklick.
4. Für die Auswertung hochgeladener Reglements (AN2): `OPENROUTER_API_KEY` und `RULES_BUDGET_MONTH_USD` in `.env` (lokal `EMPRISE_OPENROUTER_API_KEY`, Budget-Vorgabe 20 $). Das Budget gilt für die ganze Anwendung. Ohne Schlüssel steht das gewählte Kapitel auf „nicht eingerichtet“ und startet von selbst, sobald er eingetragen ist (RW22). Regeln und Baurahmen liest die Analyse über die Büro-Endpunkte (PU08). Ausgehender Zugang zusätzlich `openrouter.ai`.

**Prüfpunkte**

- Richtige Oberfläche: `GET /analyse` liefert die Anwendung; der Titel wechselt nach dem Laden auf „Emprise Analyse“.
- Anmeldung aus der Analyse führt nach `/analyse…` zurück; eine abgelehnte Anmeldung zeigt den Grund auf `/analyse`.

**Hochgeladene Reglements (AN2)**

- Ablage: `rules/uploads/<sha256>.pdf` im Dateiverzeichnis, Seitentexte in `source_page`. Dasselbe PDF ist dasselbe Dokument für alle Projekte (PU01); es bleibt, wenn ein Projekt gelöscht wird (E-AN2-4) – ein Reglement enthält keine personenbezogenen Daten. Ungenutzte Dokumente räumt noch nichts auf; bei Bedarf von Hand (`DELETE FROM land_use_plan WHERE origin = 'upload' AND id NOT IN (SELECT land_use_plan_id FROM project_regulation)` – löscht auch Läufe und senkt damit die Monatskosten, nur zum Monatsbeginn).
- Kosten je Kapitel stehen im Abschnitt „Bebauungsplan“ der Projektseite (Aufrufe, Dollar) und in `rule_extraction_run`; Größenordnung wie beim GPU-Weg (16): 1–2 $ je Kapitel. Ein **weiterer Sektor** desselben Kapitels wertet es neu aus (E-AN2-2).
- **„Wird gelesen“ bleibt stehen:** Job `rules_document_read` prüfen (Abschnitt 12; `SELECT status, last_error FROM job WHERE kind = 'rules_document_read' ORDER BY created_at DESC`). Scheitert er dreimal, steht das Dokument auf `failed: interrupted:<Art>`; erneutes Hochladen derselben Datei liest neu.
- **Scan:** mehr als die Hälfte der Seiten ohne Textschicht. Seit AN7 kein Fehler mehr, sondern Status `scan` mit Hinweis und Texterkennung (unten „Gescannte PDFs“). Ein PDF mit Textschicht (Géoportail de l'Urbanisme, Gemeinde) bleibt genauer.
- **Kein Kapitel erkannt:** Der Architekt gibt den Seitenbereich von Hand an (Kapitel, optional allgemeine Bestimmungen). Mehrbändige Reglements (allgemeine Bestimmungen in eigener Datei) vorher zu einem PDF verbinden.
- **Kapitel gescheitert:** Gründe und Wiederaufnahme wie in 16 (`not_configured`, `budget_exceeded` … nimmt `rules_housekeeping` von selbst wieder auf).

**Analyse und Zusatzdokumente (AN3)**

- Migration **0014**: Rolle `supplement` in `project_regulation`, Tabelle `analysis_parameters` (Annahmen je Projekt, gelöscht mit dem Projekt). Keine neuen Jobs, Flags oder Dienste; Zusatzdokumente laufen durch `rules_document_read` und `rules_extract` wie ein PLU.
- **Kosten:** Das Lot eines Zusatzdokuments zu wählen kostet wie eine Zonenwahl (ein Kapitel `DOC`, Größenordnung 1 $ bei wenigen Seiten); ein weiteres Lot desselben Dokuments wertet es neu aus (E-AN3-4). Monatsbudget und Zählung gemeinsam mit den PLU-Kapiteln. Ohne Schlüssel steht das Lot auf „nicht eingerichtet“ wie ein Kapitel.
- **Prompt:** Seit AN3 kennt der PLU-Prompt die Regelart `max_area` (`g2-prompt-4`); mit dem Schlüssel werden alle Kapitel ohnehin neu ausgewertet (16). Zusatzdokumente haben einen eigenen Prompt mit eigener Prüfsumme.
- **Über 150 Seiten:** Die Lotwahl antwortet `422 chapter_too_long`; einen Seitenbereich angeben.
- **Grenzen:** höchstens drei Zusatzdokumente je Projekt; dasselbe PDF nicht zugleich als PLU und als Zusatzdokument (`409 document_type_conflict`). Die Analyse rechnet Zusatzdokumente nicht ein (E-AN3-2).
- **Annahmen zurücksetzen** ohne Oberfläche: `DELETE FROM analysis_parameters WHERE project_id = …`.
- **Gabarit und Schnitt** (28.09.2026, EA13–EA17): keine Migration, keine Jobs; gerechnet mit jedem Abruf von `GET /projects/{id}/analysis` (`gabarit`, `sections`). Laufzeit lokal für das Testprojekt (20 × 30 m, Zone Uh): Median 59 ms, höchstens 61 ms bei zehn Abrufen, Antwort 9 KB. Aufwand wächst mit Kantenzahl und Stufen (bis zu zwei Auslegungen × Stufen + Geschosse, gleiche Abstandssätze nur einmal); an einem echten Katasterstück mit Regeln nachmessen.
- **Gabarit „nicht verfügbar“:** Die Höhenregel der Zone fehlt oder ist nicht ermittelt (`height_unknown`); Regeln im Abschnitt „Bebauungsplan“ prüfen. Die übrigen Kennzahlen bleiben, die Nutzfläche fehlt dann ohnehin.

**Korrekturen und Stände (AN4)**

- Migration **0015**: Fundstelle an `project_rule_override` (`source_file_id`, `page`, `quote`, `quote_verified`; nur neue, leere Spalten). Keine neuen Jobs, Flags oder Dienste. Korrekturen kosten nichts; sie wirken sofort in Regeln, Baurahmen und Analyse und stehen im Audit-Log (`project_rule_override.put`/`.delete` mit Fundstelle).
- **Korrekturen eines Projekts ansehen** ohne Oberfläche: `SELECT zone_code, kind, building_kind, status, params, note, page, quote_verified, updated_by FROM project_rule_override WHERE project_id = …`. Eine Korrektur einer Zone, die das Projekt nicht mehr hat (Zone oder PLU gewechselt), wirkt nicht und steht in der Oberfläche unter „Nicht wirksame Korrekturen“; mit gleichem Zonencode wirkt sie auch in einem neuen PLU weiter (KR04).
- **`422 zone_unknown`:** Die Zone gehört nicht zu den aktuellen Regeln – meist ein Zonenwechsel in einem anderen Tab; Seite neu laden. **`422 source_document_unknown`:** Die Fundstelle liegt in einem Dokument, das nicht (mehr) am Projekt hängt. **Zitat mit `*`:** nicht auf der Seite gefunden (zu kurz, anders geschrieben, falsche Seite); die Korrektur gilt trotzdem.
- **Stände vergleichen** (`GET /projects/{id}/analysis/comparison`) rechnet Baurahmen und Analyse zweimal: lokal für das Testprojekt Median 82 ms, höchstens 92 ms bei zehn Abrufen; `GET /analysis` Median 53 ms. Der Vergleich rechnet erst, wenn der Architekt ihn aufklappt.
- **Frühere Auswertungen** erscheinen im Vergleich, sobald ein Regelwerk eine zweite Version hat – etwa nach der Neuauswertung aller Kapitel mit dem Schlüssel (16, `g2-prompt-4`). Dann zeigt „Stände vergleichen“, was sich geändert hat, und ob eigene Korrekturen überflüssig geworden sind.

**KI-Modell der Auswertung (PLAN_AN2_PLU 8, PU11)**

- Migration **0016**: Tabelle `app_setting` (leer). Keine neuen Jobs oder Flags. Die API holt die Liste der Modelle bei `openrouter.ai` ohne Schlüssel und hält sie eine Stunde vor; ist OpenRouter nicht erreichbar, meldet der Dialog das (`503 models_unavailable`) und das Modell bleibt.
- **Für Konfigurator und Analyse** (Abschnitt 23): Von VA09 bis zum 29.09.2026 lag die Wahl in `shared_setting` der gemeinsamen Datenbank; seit Migration 0021 wieder in `app_setting` (mit `updated_by_name`).
- **Ansehen ohne Oberfläche:** `SELECT value, updated_at, updated_by FROM app_setting WHERE key = 'rules_model'`; keine Zeile = Vorgabe aus der Umgebung. **Zurück zur Vorgabe** ohne Oberfläche: `DELETE FROM app_setting WHERE key = 'rules_model'`. Jede Wahl steht im Audit-Log (`rules_model_changed`, altes und neues Modell).
- Ein Wechsel gilt für die nächste Auswertung eines Kapitels; eine laufende bleibt beim alten Modell. Ausgewertete Kapitel werden nicht von selbst neu ausgewertet; der Lauf nennt das Modell (`rule_extraction_run.model`).

**Nachsuche und Abdeckung (PLAN_G2_VOLLSTAENDIGKEIT, VA03–VA08)**

- Migration **0017**: Spalten `open_passages` und `out_of_scope_passages` an `rule_set_version` (leere Liste). Keine neuen Jobs oder Flags. Ältere Versionen zeigen keine Abdeckung, bis das Kapitel neu ausgewertet wird.
- **Neu auswerten kostet:** Die Anweisung `g2-prompt-5` und die Nachsuche ändern die Prüfsumme der Eingabe; gespeicherte Antworten passen nicht mehr. Kapitel werden deshalb nicht von selbst neu ausgewertet (die Version der Schranken bleibt `g2-1.2.0`), sondern erst bei „Neu auswerten“, neuem Sektor oder neuem Dokument – jeweils ein bezahlter Lauf. **Vorsicht bei einer neuen `ENGINE_VERSION` von G2:** `rules_housekeeping` bewertet dann alle Kapitel neu (`engine_changed`); ohne Aufruf nur, solange die gespeicherten Antworten zur Prüfsumme passen – für alle vor `g2-prompt-5` ausgewerteten Kapitel also je ein bezahlter Lauf. Vor einer solchen Änderung das Budget prüfen oder die Wiederaufnahme sperren (ROADMAP 4.1).
- **Ansehen ohne Oberfläche:** `SELECT version, coverage, jsonb_array_length(open_passages) FROM rule_set_version ORDER BY created_at DESC`; die Nachsuche steht als Lauf `run_no = 3`, Teil `gaps:…` in `rule_extraction_run`.

**Ausgabe, Lage und Gelände (AN5)**

- Migration **0018**: Spalten `name`, `note`, `archived_at` an `project` (leer), Tabelle `analysis_report`. Neuer Job **`analysis_report`** (Worker, 180 s, 2 Versuche); keine neuen Flags oder periodischen Aufgaben. Die Lage setzen braucht wie alle Grundstücksendpunkte `site_selection` (UP10).
- **Ausgehender Zugang** (keine Kosten, keine Schlüssel): Nach „Lage übernehmen“ und nach dem Upload einer Datei mit Koordinaten fragt der Worker (`site_enrich`) Höhen bei `data.geopf.fr` (Pakete zu 100 Punkten, höchstens 200 je Grundstück) und Risiken bei `georisques.gouv.fr` ab – wie G1 im Konfigurator. Der Browser lädt zum Einpassen Kacheln von `data.geopf.fr` (Plan IGN, Luftbild, Katasterebene `CADASTRALPARCELS.PARCELLAIRE_EXPRESS`); die Adresssuche läuft über die API (`/geocode`, Géoplateforme). Name und Notiz eines Projekts gehen an keinen Dienst.
- **Ablage:** Berichte unter `analysis/<Projekt>/<Prüfsumme>_<Sprache>.pdf` (rund 50 KB). Derselbe Stand wird nur einmal erzeugt; frühere Stände bleiben bis zum Löschen des Projekts, das sie mitnimmt (AU11). DXF und GeoJSON entstehen im Request und werden nicht abgelegt. Aufrufe des Berichts sind begrenzt wie der Steckbrief (`EMPRISE_ENVELOPE_SHEET_LIMIT_PER_HOUR`, eigener Zähler).
- **Laufzeiten** lokal (Testparzelle Zone Uh, 600 m², 29.09.2026): `site_enrich` 5,3 s mit 148 Höhenpunkten; Bericht-Job 1,0–2,5 s (7–8 Seiten); DXF beim ersten Abruf nach dem Start 0,5 s, danach unter 0,1 s; GeoJSON unter 0,1 s.
- **„Gelände wird abgefragt“ bleibt stehen:** Job `site_enrich` prüfen (Abschnitt 12 und 15). Scheitert ein Dienst, stehen Gelände oder Risiken auf „nicht verfügbar“; erneut „Lage übernehmen“ (auch ohne Änderung) fragt neu ab.
- **„Bericht wird erstellt“ bleibt stehen:** Job `analysis_report` prüfen (`SELECT status, last_error FROM job WHERE kind = 'analysis_report' ORDER BY created_at DESC`); die Seite fragt 90 s lang nach, danach „Bericht erstellen“ erneut. `409 report_not_ready` beim Herunterladen: der Stand hat sich seit dem Auftrag geändert (Korrektur, Notiz, Lage) – neu erstellen.
- **Fehlercodes:** `409 export_not_georeferenced` (DXF Lambert-93 oder GeoJSON ohne Lage), `409 site_position_parcel` (Grundstück aus dem Kataster, liegt schon richtig), `409 revision_conflict` (Grundstück in einem anderen Tab geändert; Seite neu laden).
- **Lage prüfen ohne Oberfläche:** `SELECT georeferenced, source_info->'position' FROM site WHERE project_id = …` (`method` `map` = von Hand eingepasst, `file` = aus der Datei; `rotation_deg` ist die Summe aller Drehungen). Jede Änderung steht im Audit-Log (`site.position`).

**Gescannte PDFs (AN7, SC01–SC10)**

- Migration **0019**: Status `scan` an `land_use_plan`, Spalten `ocr_state`, `ocr_error`, `ocr_started_at`, `ocr_finished_at` an `source_file`, `ocr_confidence` an `source_page` (alle leer bzw. `none`). Neuer Job **`rules_document_ocr`** (20 Seiten je Lauf, 3 Versuche, 900 s); keine neuen Flags, periodischen Aufgaben oder Dienste. Im Image `tesseract-ocr` und `tesseract-ocr-fra` (etwa 22 MB), dazu `pypdfium2`.
- **Kosten und Zugang:** Die Erkennung läuft im Worker, kostet nichts und schickt nichts nach außen. Sie belegt den Worker in Teilen von etwa einer Minute; andere Jobs warten höchstens einen Teil.
- **Laufzeit** lokal (12 Kerne, 29.09.2026): 3,0 s je Seite, Beyenes als Scan mit 74 Seiten in 223 s. Die Schätzung im Hinweis rechnet mit `EMPRISE_OCR_SECONDS_PER_PAGE` (Vorgabe 3); auf Unraid nachmessen (`SELECT ocr_finished_at - ocr_started_at, page_count FROM source_file WHERE ocr_state = 'done'`) und die Variable anpassen.
- **Fortschritt ohne Oberfläche:** `SELECT ocr_state, ocr_error, (SELECT count(*) FROM source_page p WHERE p.source_file_id = f.id AND p.ocr_confidence IS NOT NULL) AS erkannt, cardinality(empty_pages) AS gesamt FROM source_file f WHERE ocr_state <> 'none'`.
- **„Texterkennung gescheitert“:** `ocr_error` zeigt den Grund. `ocr_unavailable` – Tesseract fehlt im Image (eigener Build ohne Stufe `base`?); `tesseract --version` im Worker prüfen. `interrupted:<Art>` – Job dreimal abgebrochen (Speicher, Zeitlimit); erkannte Seiten bleiben, „Erneut versuchen“ in der Oberfläche setzt bei der ersten offenen Seite fort.
- **Kapitel fehlen nach der Erkennung:** Verzeichnisse liest die Erkennung schlecht; die Kapitelsuche nimmt dann die Seitenüberschriften (SC07). Findet sie nichts, den Seitenbereich von Hand angeben. Zonenkürzel können verlesen sein („Uig“ statt „UIg“); das Kapitel ist trotzdem wählbar.
- **Werte „im Scan nicht sicher lesbar“** (`scan_unconfirmed`): Das Zitat des Modells ließ sich im erkannten Text nicht bestätigen, meist eine anders gelesene Zahl. Im PDF nachsehen und bei Bedarf korrigieren (AN4).
- **Stolperstelle OpenRouter:** Ein Modell ohne PDF-Eingabe im PDF-Modus lässt OpenRouter die Seiten mit Mistral OCR lesen (2 $ je 1 000 Seiten, ohne Hinweis). Für solche Modelle den Textmodus (PU12) wählen; dann geht der erkannte Text.
- **Parzelle nachzeichnen:** `POST /site/scan` rendert und erkennt im Aufruf (2–5 s), speichert nichts. Scheitert Tesseract dabei, kommt die Vorschau ohne Maßstab (Log `site_scan_ocr_failed`) und der Architekt kalibriert. Die Herkunft steht in `site.source_info->'trace'`.
- **Kapitelsuche geändert (SC07):** gilt nur beim Lesen. Bereits gelesene Dokumente behalten ihre Kapitel; bei Beyenes (Textschicht) fehlte dadurch Zone UE (ROADMAP 4.1).

**Organisationen (AN6, MA01–MA09)**

- Migration **0020**: Tabellen `organisation`, `organisation_member`, `api_key`, `usage_record`; Spalten `project.organisation_id` (mit Fremdschlüssel), `regulation_chapter.billing_organisation_id`, `rule_extraction_run.organisation_id`. Gibt es Konten oder Projekte mit Eigentümer, legt sie „Eigenes Büro“ (`eigenes-buero`, Art `operator`) an und ordnet ihm Konten, Projekte mit Eigentümer sowie alle bisherigen Läufe und Kapitel zu (MA01) – das eigene Büro merkt nichts, sein Verbrauch im laufenden Monat bleibt vollständig. Rückrollen: `alembic downgrade 0019` entfernt die neuen Tabellen und Spalten und leert `project.organisation_id` (Organisationen, Schlüssel und Verbrauch gehen verloren). Ein älteres Image kennt nur Projekte mit Eigentümer: Projekte, die ein API-Schlüssel angelegt hat, zeigt es nicht und löscht sie nach 90 Tagen ohne Aktivität.
- Migration **0023** (29.09.2026, REFACTORING_PLAN S8) baut API-Schlüssel, Budget und Scan-Kontingent je Organisation und das Erscheinungsbild zurück: Tabellen `api_key` und `usage_record`, Grenzen und Schriftfeld an `organisation`, `regulation_chapter.billing_organisation_id` und `rule_extraction_run.organisation_id` entfallen. Kapitel mit `organisation_budget_exceeded` werden zu `budget_exceeded` und laufen weiter, sobald das Budget der Instanz (`RULES_BUDGET_MONTH_USD`) reicht. Alte Audit-Einträge mit `actor_type = 'api_key'` bleiben. Logos bleiben als Dateien unter `organisations/` liegen und können gelöscht werden. Rückrollen: `alembic downgrade 0022` legt Tabellen und Spalten leer wieder an.
- **Fremde Büros sind gesperrt**, bis E-A5 juristisch geklärt ist (Nutzungsbedingungen, AVV, Datenauskunft): `org-create --kind customer` verlangt `EXTERNAL_ORGANISATIONS=true` (lokal `EMPRISE_EXTERNAL_ORGANISATIONS`). Tests schalten es ein.
- **Anlegen:** `python -m app.cli org-create atelier-sud "Atelier Sud" --kind customer`, dann `org-member-add atelier-sud chef@atelier-sud.fr --role admin` (legt das Konto mit Rolle `architect` an). Das Konto beim Identitätsdienst richtet der Betreiber ein; die erste Anmeldung bindet es über die bestätigte Adresse. Weitere Mitglieder trägt der `admin` auf der Seite „Organisation“ ein. `org-list` zeigt Organisationen und Mitgliederzahl.
- **Trennung:** Projekte, Reglements, Regeln und Dateien sieht nur die eigene Organisation; auch Betriebsrollen reichen nicht in fremde Organisationen (E-AN6-7). Unterstützung für ein fremdes Büro nur mit dessen Zustimmung und über die Datenbank. Rollen des Betriebs (`ops`, `rules_admin`, `catalog_admin`) wirken nur in „Eigenes Büro“; `staff-add` und die Mitgliederverwaltung lehnen sie anderswo ab.

**Störungen beim Hochladen einer Parzelle**

- `422 upload_invalid`: kein lesbares DXF oder GeoJSON, keine geschlossene Polylinie, oder keine Kontur mit plausibler Fläche (20–50 000 m², UP08). Im DXF muss die Parzelle eine **geschlossene** Polylinie sein; einzelne Linien werden nicht verbunden.
- Mehrere Konturen: Die Antwort enthält `candidates` statt `site`; die Oberfläche zeigt sie zur Auswahl. Erst der zweite Aufruf mit `index` legt das Grundstück an.
- `409 site_origin_mismatch`: Das Projekt hat schon ein Grundstück aus dem Kataster. Für eine andere Herkunft ein neues Projekt anlegen.
- Fläche unplausibel groß oder klein: meist die Einheit im DXF (`$INSUNITS`). Millimeter und Zentimeter werden umgerechnet, fehlt die Angabe, gelten Meter.
- **PDF** (UP13–UP16): `422 upload_pdf_no_vector` – das PDF enthält keine Linien, meist ein Scan; die Oberfläche bietet das Nachzeichnen an (SC08), genauer ist das PDF aus dem CAD oder von cadastre.gouv.fr. `422 upload_scale_missing` – kein Maßstab im Text, von Hand angeben. `422 upload_scale_ambiguous` – mehrere Maßstäbe, die Antwort nennt sie in `scales`. Stimmt die Fläche nicht mit der Katasterfläche, war das PDF nicht maßstäblich gedruckt oder der Maßstab falsch; `source_info.scale` und `scale_source` zeigen, womit gerechnet wurde. Große Pläne: höchstens 3 Seiten, 60 000 Linienstücke, 20 MB (`EMPRISE_SITE_UPLOAD_MAX_BYTES`); der realistische Auszug mit 458 Schraffurlinien brauchte 0,3 s.
- „ohne geografischen Bezug“ trotz Lambert-93-Datei: Die Koordinaten liegen außerhalb des erkannten Bereichs (UP04). Abstände und Flächen stimmen trotzdem; Gelände, Risiken, DXF in Lambert-93 und GeoJSON gibt es nach „Lage festlegen“ (AN5).

**Grenzen**

- Das Analyse-Produkt kennt **keine Datenauskunft** (`GET /projects/{id}/export` liegt in Modul A, UP07) und kein Löschen einer ganzen Organisation; die Löschung eines Projekts gibt es. Beides vor dem Freischalten fremder Büros mit E-A5 klären (PLAN_AN6 3.8).
- Gespeicherte Antworten gelten je Kapitel: Dasselbe Dokument als Upload eines Analyse-Projekts und aus dem GPU-Import wird je einmal ausgewertet und bezahlt (PLAN_ANALYSE 3, letzter Punkt).

## 23. Verwaltung: KI-Modell und Referenzlisten (PLAN_G2_VOLLSTAENDIGKEIT 3.9–3.10)

KI-Modell der Auswertung (`app_setting`) und Referenzlisten (`reference_list`, `reference_entry`) gelten für Konfigurator und Analyse; jede Änderung steht im Audit-Log. Oberfläche: `/analyse/verwaltung` (das Büro verlinkt dorthin, `/verwaltung` leitet weiter), Rollen `ops` und `rules_admin`; nicht an ein Büro gebunden (VA09, VA10).

- **Eine Datenbank seit 29.09.2026** (Migration 0021, REFACTORING_PLAN S4): Die frühere gemeinsame Datenbank `emprise_shared` mit eigener Migrationskette, `shared-migrate`, `db-init-shared` und dem Unraid-Stack `emprise-shared` entfallen. 0021 legt die Tabellen an, übernimmt `shared_setting` und `shared_audit`, wenn sie in derselben Datenbank liegen, und löscht `alembic_version_shared`.
- **Daten aus einer eigenen `emprise_shared` übernehmen** (lokal am 29.09.2026 so gemacht), solange `emprise` noch auf 0020 steht: die Tabellen in `emprise` einspielen, dann `docker compose up -d --build`; der Migrate-Job führt sie zusammen. Zeilenzahlen vorher und nachher vergleichen; `emprise_shared` bleibt liegen, bis der Betrieb sie löscht.

  ```bash
  docker compose exec -T db pg_dump -U postgres -t shared_setting -t shared_audit -t reference_list -t reference_entry -t alembic_version_shared emprise_shared | docker compose exec -T db psql -U postgres -d emprise -v ON_ERROR_STOP=1
  ```

- **Referenzliste einspielen:** `python -m app.cli reference-import beyenes_uc.json` (mitgelieferte Listen in `app/rules/reference_seed`; `--replace` ersetzt). Messen ohne Oberfläche: `python -m app.cli reference-check <datei> --version all`.
- **Sicherung:** mit der Datenbank `emprise` (Abschnitt 6).

**Störungen**

- `/analyse/verwaltung` meldet „dem Betrieb vorbehalten“: Konto ohne Rolle `ops` oder `rules_admin` (`staff-add`).
- `404 reference_not_evaluated`: Das Dokument der Liste ist hier nicht ausgewertet (Prüfsumme der Planunterlage und Sektor). Die Liste gilt trotzdem; gemessen wird, sobald das Dokument ausgewertet ist.
- `409 reference_list_exists`: Für Dokument und Sektor gibt es schon eine Liste; beim Import „vorhandene Liste ersetzen“ wählen.

**Prüfen:** `/analyse/verwaltung` zeigt KI-Modell und Referenzlisten; `/verwaltung` leitet dorthin weiter.
