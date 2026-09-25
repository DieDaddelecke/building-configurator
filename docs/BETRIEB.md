# Betriebsanleitung

Einrichten der Module, typische Störungen und Handgriffe (Plan 6.8). Befehle mit `docker compose exec api …` gelten lokal; beim Anbieter läuft derselbe Befehl als einmaliger Container-Job mit dem Image der laufenden Version.

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

Alarme (Uptime-Dienst, minütlich): `/api/health/ready` ≠ 200 → „API oder Datenbank gestört“; `/api/health/jobs` ≠ 200 → „Worker steht oder ist überlastet“. Dazu Alarme auf Log-Einträge (Fehler-Tracking): `rules_extract_failed` (Kapitel gescheitert, Abschnitt 9), `rules_budget_exceeded` (Monatsbudget der Claude API erreicht), `road_import_implausible` (Straßenachsen, Abschnitt 8), `dossier_failed` (Dossier einer Fassung endgültig gescheitert, Abschnitt 14). Das in Plan G3 6.2 genannte `envelope_derive_failed` ist im Code nicht angelegt.

**Module im Betrieb.** Migrationen laufen beim Ausliefern mit (Job `migrate`). Freischalten über Feature-Flags (Plan 4.2): intern `python -m app.cli flag-set <flag> --role architect`, Beta für eingeladene Projekte über die Admin-API (für `inquiry` und `configurator` war `--all` für die Beta genannt), öffentlich `--all`, abschalten `--off`; jede Änderung steht im `audit_log`. `envelope_simulation` setzt `site_selection` und `rules_simulation` voraus (Plan G3 4.2).

| Modul | Migration | Flag | Jobs (Rhythmus) | Ausgehender Zugang von API und Worker | Vor dem Freischalten |
|---|---|---|---|---|---|
| P | 0001 | – | `mail_send`, `retention_cleanup` (täglich), `housekeeping` (stündlich) | SMTP-Anbieter (E2) | `staff-add` (3), SMTP (5) |
| G1 | 0002, 0006, 0012 | `site_selection` | `cadastre_import` (wöchentlich, auch beim ersten Start), `site_enrich`, `site_housekeeping` (alle 6 h) | `data.geopf.fr`, `cadastre.data.gouv.fr` (leitet auf `*.cloud.ovh.net` weiter), `georisques.gouv.fr`; Browser der Besucher: Kartenkacheln von `data.geopf.fr` | Einzugsgebiet, Erstimport (8) |
| G2 | 0003, 0004, 0013 | `rules_simulation` | `plu_import` (wöchentlich, auch beim ersten Start), `rules_extract`, `rules_housekeeping` (stündlich), `rules_document_read` (nur Analyse-Produkt, 15) | zusätzlich `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com` | Schlüssel und Budget (9) |
| G3 | 0005 | `envelope_simulation` | `envelope_sheet` | – | WeasyPrint im Image (10) |
| H1 | 0007 | – (nur Rollen: bearbeiten `architect`, `catalog_admin`; lesen `ops`) | – (Import synchron) | – | `openpyxl`, `ezdxf`, `python-multipart` im Image; Konto mit `catalog_admin` oder `architect` per `staff-add` |
| A | 0008 | `inquiry` | `mail_send` | – | Büro-Postfach, `legal-seed` (11) |
| H2 | 0009 | `configurator` | – | – | ein veröffentlichter Typ (12) |
| H3 | 0010 | `configurator` (dasselbe Flag) | – | – | veröffentlichter Preiskatalog mit Linien, Optionen und Preisen netto (13) |
| V | 0011 | `submission` (Übergabe); „Mein Vorgang“ mit `inquiry` oder `submission` | `dossier_generate`, `mail_send` | – | `legal-seed` für die zwei neuen Texte, Büro-Postfach (14) |

Die Tabelle gilt für den Hauskonfigurator. Aus demselben Code läuft mit `EMPRISE_PRODUCT=analyse` ein zweites Produkt („Emprise Analyse“) mit eigenem Stack und ohne die Module H1–H3, A und V: Abschnitt 15.

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
3. Flag und ausgehender Zugang: Tabelle in Abschnitt 1.

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

## 9. Regelwerk (Modul G2)

**Einrichten und Freischalten**

1. Schlüssel der Claude API und Monatsbudget setzen: `EMPRISE_ANTHROPIC_API_KEY`, `EMPRISE_RULES_BUDGET_MONTH_USD` (Unraid: `ANTHROPIC_API_KEY`, `RULES_BUDGET_MONTH_USD` in `.env`). An die API gehen nur öffentliche Planunterlagen (L8).
2. Planstände importiert der Worker beim ersten Start und danach wöchentlich (`plu_import`); sofort: `python -m app.cli plu-import` (ohne Internet: `--from-dir`). Jedes Zonenkapitel wird danach als Job `rules_extract` ausgewertet.
3. Flag und ausgehender Zugang: Tabelle in Abschnitt 1.

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

## 10. Baurahmen (Modul G3)

Der Baurahmen wird bei jedem Abruf aus Grundstück und Regeln gerechnet und nicht gespeichert. Es gibt daher nichts nachzuführen: Sobald Gelände, Kanten oder Regeln stimmen, stimmt auch der Baurahmen.

**Kunde sieht „kein auswertbarer Bebauungsplan“**

1. Regeln prüfen: `GET /api/v1/admin/projects/<id>/rules` oder `/buero/regeln`. Steht die Zone auf `in_progress` oder `unavailable`, liegt es an G2 (Abschnitt 9), nicht an G3.
2. Liegt das Grundstück in keiner Zone des Planwerks (`no_zone`), prüfen, ob der Planstand die Gemeinde abdeckt (`plu-import --commune`).

**Fläche wirkt zu groß oder zu klein**

- `strict.complete = false` mit `incomplete_reasons` nennt die Kante, deren Abstand fehlt. Ursache ist eine Regel mit Status `unknown` in G2; Abhilfe: Kapitel erneut auswerten oder Korrektur für die Zone (Abschnitt 9).
- `band_unclear`: Das Modell hat nicht gesagt, ob das Bauband für den ganzen Baukörper gilt. Nach einer erneuten Auswertung mit `PROMPT_VERSION g2-prompt-3` ist der Parameter gesetzt.
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

## 11. Anfrage (Modul A)

Keine neuen externen Dienste; Mail läuft über den bestehenden Weg (Abschnitt 5).

**Vor der Freischaltung (`flag-set inquiry`)**

1. `EMPRISE_OFFICE_EMAIL` auf die echte Sammeladresse des Architekturbüros setzen (Vorschlag `buero@emprise.local` ist ein Platzhalter).
2. Vorläufige Einwilligungstexte einmalig veröffentlichen, falls noch keine Version besteht:

   ```bash
   docker compose exec api python -m app.cli legal-seed
   ```

   Ohne diese Texte scheitert `POST .../inquiry/confirm` mit `503 legal_text_missing`. Endgültiger Wortlaut nach Rechtsberatung: neue Version über `POST /admin/legal-texts` veröffentlichen, keine Codeänderung nötig.
3. Flag `inquiry` setzen (Abschnitt 1).

**Anfrage kommt nicht beim Büro an**

- Job `mail_send` in `/api/v1/admin/ops/status` prüfen (wie Abschnitt 5); die Anfrage selbst ist bereits gespeichert, auch wenn der Mailversand scheitert (`inquiry` committet vor den Mail-Jobs).
- `office_mail`/`customer_mail` sind zwei getrennte Jobs; ein Fehlschlag der einen betrifft die andere nicht.

**Löschung eines Projekts mit Anfrage**

`DELETE /api/v1/projects/<id>` liefert `409 deletion_requires_office`, sobald eine Anfrage besteht (Plan A 3.9, D6 noch offen). Es gibt noch keine Büro-Funktion für die Endlöschung danach; bis dahin händisch in der Datenbank, mit Audit-Eintrag.

## 12. Konfigurator: Typen und Lage (Modul H2)

Keine neuen externen Dienste und keine neuen Jobs. Zulässigkeit und Prüfung der Lage werden bei jedem Abruf aus Grundstück, Regeln und veröffentlichtem Katalog gerechnet; gespeichert werden nur der gewählte Typ (als Typversion), die Lage und die Grenzschalter (Tabelle `configuration`, Migration 0009, keine neue Sequenz).

**Vor der Freischaltung (`flag-set configurator`)**

1. Mindestens ein Typ muss veröffentlicht sein (Büro, `/buero/katalog`). Ohne Typen zeigt die Seite „Es ist noch kein Haustyp veröffentlicht“.
2. Lokal zum Ansehen: `docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types` legt drei erfundene Typen `demo_*` an. **Nie in Produktion.**
3. Flag `configurator` setzen (Abschnitt 1).

**Typ wird zu Unrecht gesperrt oder zugelassen**

- Die Karte nennt jeden Grund mit dem Code der Prüfung (`GET /api/v1/projects/<id>/catalog/types`, Feld `reasons` mit Regelart, Seite und Zitat). Bindend ist nur eine wirksame Regel; was `unknown` ist, steht unter `hints`. Ursache eines falschen Sperrgrunds ist fast immer die Regel in G2: Zitat prüfen, Kapitel neu auswerten oder Korrektur für die Zone/das Projekt setzen (Abschnitt 9).
- `no_valid_position`: Der Typ passt in keiner erlaubten Drehung auf die bebaubare Fläche. Der Baurahmen (Abschnitt 10) zeigt die Fläche; ein Haus von 12 × 8 m braucht mindestens diese Maße plus die Abstände.
- Fehlen die Fassadenrollen am Typ (`facade_roles_missing`), richtet sich die Ausrichtung nach Modellnorden; im Büro unter `/buero/katalog` je Typ zuweisen (das geht nur an einem Entwurf, danach neue Version).
- Höhenprüfungen sind `unknown`, solange das Gelände fehlt oder steiler als 5 % ist (`height_unverifiable`); das Gelände kommt über den Job `site_enrich` (Abschnitt 8).

**Lage wird abgelehnt (`422 placement_violation`)**

Die Antwort enthält alle Prüfungen mit Kante, Soll und Ist. `rotation_not_allowed` nennt die erlaubten Drehungen. `revision_conflict` heißt: Die Konfiguration wurde in einem anderen Tab geändert; die Oberfläche lädt neu.

**Regelmäßig prüfen**

Nach einem neuen Planstand, neuen Regeln (G2) oder einer neuen Katalogversion können gespeicherte Konfigurationen ungültig werden. Das ist beabsichtigt: `GET /projects/<id>/configuration` prüft neu und zeigt die Verstöße; gelöscht wird nichts.

## 13. Konfigurator: Linie, Optionen und Kosten (Modul H3)

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

## 14. Vorentwurf-Übergabe (Modul V)

Keine neuen externen Dienste. Neu sind die Tabellen `submission` (Fassungen mit Snapshot und Dossier) und `inquiry_message`, die Spalten `consent.submission_id` und `customer.locale`, die Zustände `rueckfrage` und `zurueckgezogen` (Migration `0011`) und der Job `dossier_generate` (PDF fr/de und DXF, 2–4 s lokal). Dateien liegen im Objektspeicher unter `dossiers/<Projekt>/<Fassung>/`. Plan und Festlegungen: [PLAN_V_VORENTWURF_UEBERGABE.md](PLAN_V_VORENTWURF_UEBERGABE.md), ANNAHMEN VU01–VU16.

**Vor dem Freischalten (`flag-set submission`)**

1. H3 muss laufen (veröffentlichter Preiskatalog, Abschnitt 13) und A eingerichtet sein (Büro-Postfach `EMPRISE_OFFICE_EMAIL`, Abschnitt 11).
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

## 15. Zweites Produkt: Emprise Analyse (AN0–AN2)

Aus demselben Repository entsteht ein zweites Produkt für Architekturbüros ([PLAN_ANALYSE.md](PLAN_ANALYSE.md), ANNAHMEN PS01–PS09, UP01–UP16 und PU01–PU10). Umgesetzt sind **AN0** (Produktschnitt), **AN1** (Parzelle als DXF, GeoJSON, vektorielles PDF oder Zeichnung, Kanten von Hand einordnen, Projekte am Architektenkonto) und **AN2** (règlement écrit als PDF hochladen, Zone wählen, Regeln und Baurahmen). Analyse und Nutzfläche (AN3), Regelformular und Zusatzdokumente (AN4), Bericht und CAD-Ausgabe (AN5) fehlen noch; Gelände und Risiken bleiben aus, auch bei georeferenzierten Dateien.

| | Hauskonfigurator | Emprise Analyse |
|---|---|---|
| `EMPRISE_PRODUCT` | `configurator` (Standard) | `analyse` |
| Module unter `/api/v1` | Kern + Katalog, Konfiguration, Anfrage, Übergabe (91 Operationen im OpenAPI-Dokument, Stand AN2) | nur Kern: Plattform, G1, G2, G3 (51 Operationen) |
| Periodische Aufgaben | alle sechs | ohne `cadastre_import` und `plu_import` (D17: der Nutzer lädt hoch) |
| Oberfläche | `index.html` | `analyse.html` über `SPA_INDEX` im Web-Container |
| Datenbank, Speicher, Sicherung, Hostname, Authentik | eigene | eigene (E-A4) |
| Images | dieselben, Kennzeichen `current` | dieselben, Kennzeichen `current-analyse` |

**Ausliefern auf Unraid.** `deploy/unraid/.env.analyse.example` nach `.env.analyse` kopieren und ausfüllen (eigene Geheimnisse, eigener Hostname, eigenes `APPDATA_DIR` und `BACKUP_DIR`), in Authentik eine zweite Anwendung anlegen (wie Unraid README 3), im Reverse Proxy den zweiten Hostnamen auf `WEB_PORT` zeigen lassen, dann:

```
./deploy.sh analyse                # bauen und ausliefern
./deploy.sh analyse rollback REL   # nur diesen Stack zurückrollen
```

`releases.log` führt beide Stacks mit Namen. Ein Rückrollen des einen lässt den anderen unberührt, weil die Kennzeichen getrennt sind.

**Lokal.** Der Analyse-Stack setzt auf den laufenden Hauptstack auf (gemeinsamer Datenbankserver, Objektspeicher, Mailpit, OIDC-Testdienst; eigene Datenbank `emprise_analyse`, eigener Bucket):

```
docker compose -f compose.analyse.yaml up -d
```

Anwendung http://localhost:8180, API http://localhost:8100/api/v1/docs. Die Dienste heißen dort `api-analyse`, `worker-analyse`, `web-analyse` (PS08). Beenden mit `docker compose -f compose.analyse.yaml down`; die Datenbank `emprise_analyse` bleibt bestehen.

**Einrichten nach dem ersten Start (AN1)**

1. Konto freischalten: `python -m app.cli staff-add person@buero.fr architect` – **im Analyse-Stack**, er hat eigene Tabellen (lokal: `docker compose -f compose.analyse.yaml exec api-analyse …`).
2. Flag setzen: `python -m app.cli flag-set site_selection --role architect`. Ohne das Flag antworten alle Grundstücksendpunkte mit `403 feature_disabled` (UP10).
3. Kein Katasterimport nötig: Die Parzelle kommt als DXF oder GeoJSON oder wird gezeichnet (D17). `CADASTRE_COMMUNES=[]` ist der Normalfall; mit einer Gemeinde darin läuft der Import von Hand (`cadastre-import`), dann funktioniert auch der Katasterklick.
4. Für die Auswertung hochgeladener Reglements (AN2): `ANTHROPIC_API_KEY` und `RULES_BUDGET_MONTH_USD` in `.env.analyse` (lokal `EMPRISE_ANTHROPIC_API_KEY`, Budget-Vorgabe 20 $). Das Budget gilt je Datenbank, also getrennt vom Hauskonfigurator. Ohne Schlüssel steht das gewählte Kapitel auf „nicht eingerichtet“ und startet von selbst, sobald er eingetragen ist (RW22). Die Flags `rules_simulation` und `envelope_simulation` braucht das Analyse-Produkt nicht: Regeln und Baurahmen liest die Oberfläche über die Büro-Endpunkte (PU08). Ausgehender Zugang zusätzlich `api.anthropic.com`.

**Prüfpunkte**

- Richtiges Profil: `GET /api/v1/openapi.json` des Analyse-Stacks enthält keine Route mit `catalog`, `inquiry`, `submission` oder `configuration`.
- Richtige Oberfläche: `GET /` liefert `<title>Emprise Analyse</title>`. Kommt „Emprise“, fehlt `SPA_INDEX=analyse.html`.
- Richtige Zeitpläne: `SELECT name FROM periodic_schedule` zeigt vier Einträge (`housekeeping`, `retention_cleanup`, `rules_housekeeping`, `site_housekeeping`), im Konfigurator sechs.

**Hochgeladene Reglements (AN2)**

- Ablage: `rules/uploads/<sha256>.pdf` im Objektspeicher des Stacks, Seitentexte in `source_page`. Dasselbe PDF ist dasselbe Dokument für alle Projekte (PU01); es bleibt, wenn ein Projekt gelöscht wird (E-AN2-4) – ein Reglement enthält keine personenbezogenen Daten. Ungenutzte Dokumente räumt noch nichts auf; bei Bedarf von Hand (`DELETE FROM land_use_plan WHERE origin = 'upload' AND id NOT IN (SELECT land_use_plan_id FROM project_regulation)` – löscht auch Läufe und senkt damit die Monatskosten, nur zum Monatsbeginn).
- Kosten je Kapitel stehen im Abschnitt „Bebauungsplan“ der Projektseite (Aufrufe, Dollar) und in `rule_extraction_run`; Größenordnung wie beim GPU-Weg (9): 1–2 $ je Kapitel. Ein **weiterer Sektor** desselben Kapitels wertet es neu aus (E-AN2-2).
- **„Wird gelesen“ bleibt stehen:** Job `rules_document_read` prüfen (Abschnitt 4; `SELECT status, last_error FROM job WHERE kind = 'rules_document_read' ORDER BY created_at DESC`). Scheitert er dreimal, steht das Dokument auf `failed: interrupted:<Art>`; erneutes Hochladen derselben Datei liest neu.
- **`document_no_text`:** mehr als die Hälfte der Seiten ohne Textschicht, meist ein Scan. Ein PDF mit Textschicht besorgen (Géoportail de l'Urbanisme, Gemeinde); OCR gibt es nicht (RW03).
- **Kein Kapitel erkannt:** Der Architekt gibt den Seitenbereich von Hand an (Kapitel, optional allgemeine Bestimmungen). Mehrbändige Reglements (allgemeine Bestimmungen in eigener Datei) vorher zu einem PDF verbinden.
- **Kapitel gescheitert:** Gründe und Wiederaufnahme wie in 9 (`not_configured`, `budget_exceeded` … nimmt `rules_housekeeping` von selbst wieder auf).

**Störungen beim Hochladen einer Parzelle**

- `422 upload_invalid`: kein lesbares DXF oder GeoJSON, keine geschlossene Polylinie, oder keine Kontur mit plausibler Fläche (20–50 000 m², UP08). Im DXF muss die Parzelle eine **geschlossene** Polylinie sein; einzelne Linien werden nicht verbunden.
- Mehrere Konturen: Die Antwort enthält `candidates` statt `site`; die Oberfläche zeigt sie zur Auswahl. Erst der zweite Aufruf mit `index` legt das Grundstück an.
- `409 site_origin_mismatch`: Das Projekt hat schon ein Grundstück aus dem Kataster. Für eine andere Herkunft ein neues Projekt anlegen.
- Fläche unplausibel groß oder klein: meist die Einheit im DXF (`$INSUNITS`). Millimeter und Zentimeter werden umgerechnet, fehlt die Angabe, gelten Meter.
- **PDF** (UP13–UP16): `422 upload_pdf_no_vector` – das PDF enthält keine Linien, meist ein Scan; das PDF aus dem CAD oder von cadastre.gouv.fr nehmen. `422 upload_scale_missing` – kein Maßstab im Text, von Hand angeben. `422 upload_scale_ambiguous` – mehrere Maßstäbe, die Antwort nennt sie in `scales`. Stimmt die Fläche nicht mit der Katasterfläche, war das PDF nicht maßstäblich gedruckt oder der Maßstab falsch; `source_info.scale` und `scale_source` zeigen, womit gerechnet wurde. Große Pläne: höchstens 3 Seiten, 60 000 Linienstücke, 20 MB (`EMPRISE_SITE_UPLOAD_MAX_BYTES`); der realistische Auszug mit 458 Schraffurlinien brauchte 0,3 s.
- „ohne geografischen Bezug“ trotz Lambert-93-Datei: Die Koordinaten liegen außerhalb des erkannten Bereichs (UP04). Folge ist nur, dass keine Karte und später keine Lambert-93-Ausgabe möglich ist; Abstände und Flächen stimmen trotzdem.

**Grenzen**

- Das Analyse-Produkt kennt **keine Datenauskunft** (`GET /projects/{id}/export` liegt in Modul A, UP07); die Löschung eines Projekts gibt es. Vor AN6 (fremde Büros) neu bewerten.
- Im Image liegen beide Oberflächen. Unter `/index.html` zeigt der Analyse-Stack die Seite des Konfigurators; deren Aufrufe laufen dort ins Leere (PS06).
- Regelwerke werden nicht geteilt: Eine Auswertung, die beide Produkte brauchen, kostet zweimal (PLAN_ANALYSE 3, letzter Punkt).
