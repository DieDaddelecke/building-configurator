# Refactoring-Plan

> **Stand:** 29.09.2026, zweite Fassung nach dem Auftrag „Complexity Reduction Refactoring“ und den Entscheidungen des Nutzers vom selben Tag. Grundlage: [REFACTORING_ANALYSIS.md](REFACTORING_ANALYSIS.md) (Befunde `B-…`), Zielbild in [REFACTORING_ARCHITECTURE.md](REFACTORING_ARCHITECTURE.md), Risiken `R-…` in [REFACTORING_RISKS.md](REFACTORING_RISKS.md).
> Jeder Schritt ist ein eigener Commit auf `main` (ohne Push), einzeln prüfbar und revertierbar. Keine neuen Funktionen.

## 0. Entscheidungen und Festlegungen

**Entscheidungen des Nutzers (29.09.2026)**

| Frage | Entscheidung | hebt auf |
|---|---|---|
| Produkte | eine Anwendung: ein API, eine Datenbank, ein Frontend, ein Worker-Image | PLAN_ANALYSE 3 (getrennte Datenbanken), ANNAHMEN PS08, E-A4; gemeinsamer Stack vom 28.09.2026 |
| Adresse | ein Hostname; Konfigurator `/`, Büro `/buero`, Analyse `/analyse`; eine Authentik-Anwendung | eigener Hostname `emprise-analyse.aslani.work` (PS08) |
| AN6-Zusätze | entfernen: API-Schlüssel, Budget und Scan-Kontingent je Organisation, Erscheinungsbild. Bleiben: Organisation, Mitglieder, globales Monatsbudget | Teile von AN6 (PLAN_AN6_MANDANTEN, ANNAHMEN MA01–MA09) |
| Dokumentation | sechs Zieldateien (README, ARCHITECTURE, DOMAIN, ROADMAP, DECISIONS, AI_CONTEXT) + Archiv; AENDERUNGEN endet, HANDOFF geht in ROADMAP auf | Dokumententabelle in AGENTS.md, Ablauf `/handoff` |
| Lokale Analyse-Daten | nicht übernehmen; `emprise_analyse`, Bucket und Volumes bleiben als Rückweg liegen | – |

**Festlegungen dieses Plans**

| Thema | Festlegung | Grund |
|---|---|---|
| Worker | zwei Dienste aus einem Image: `worker` (Queue `default`), `worker-long` (Queue `long`); lokal ein Worker für beide | B-10: eine Auswertung (bis 60 min) blockiert sonst den Mailcode (10 min gültig); nach dem Merge laufen die langen Jobs beider Bereiche in einer Queue. Abweichung vom Zielbild „ein Worker“ |
| Backend-Ordner | bleiben (`platform`, `integrations`, `<modul>/domain`) | entsprechen schon `infrastructure` und `calculations`; Umzug brächte nur Importänderungen |
| Frontend-Ordner | Fachordner bleiben; nur `src/products/analyse` → `src/analyse` | „Produkte“ gibt es danach nicht mehr |
| Feature-Flags | die sechs Modul-Flags bleiben bis zum öffentlichen Go-live; Zweig für API-Schlüssel entfällt | sie sind der Freischaltweg (intern → Beta → öffentlich), siehe Abschnitt 3 |
| Redis, Celery | nichts zu entfernen | existieren nicht (ANALYSIS 1, 9, 10); nur Doku |
| Dateispeicher | Schlüssel unverändert unter `/data/files/<key>`; keine neue Tabelle `files` | Fachtabellen tragen Schlüssel und sha256 schon |

## 1. Arbeitsweise je Schritt

1. Referenzen suchen, Runtime-, Test-, Docker- und Doku-Bezüge prüfen.
2. Ändern.
3. Prüfen – Backend: `docker compose --profile dev run --rm backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"` (bis Schritt 7 mit `-e TEST_S3=1`); Frontend: `corepack pnpm run typecheck && lint && test && build`; bei API-Änderung OpenAPI → TS; bei Infrastruktur `docker compose config`, Start, Smoke-Test.
4. Commit ohne Push.

Lokale Stacks laufen nur mit leerem `EMPRISE_OPENROUTER_API_KEY` (keine bezahlten Läufe). Schlägt ein Test fehl und ist die Ursache nicht sicher zu beheben, oder würde eine Vereinfachung Fachverhalten ändern, wird angehalten und berichtet.

## 2. Current → Target

```text
Current                                              Target
2 Produkt-Instanzen (EMPRISE_PRODUCT)                1 Anwendung, Bereiche / · /buero · /analyse
3 Datenbanken (emprise, emprise_analyse, _shared)    1 Datenbank (PostgreSQL + PostGIS)
2 Alembic-Stränge                                    1 Strang
2 Vite-Einstiege, SPA_INDEX                          1 Einstieg, zwei Router (basename /analyse)
SeaweedFS (S3), boto3                                Verzeichnis /data/files
1 Queue, 1 Worker-Prozess                            Queues default + long, worker + worker-long
3 Auth-Wege (Sitzung, Projekt-Cookie, API-Schlüssel) 2 Auth-Wege (Sitzung, Projekt-Cookie)
Unraid 19 Container, 4 PostgreSQL-Server             10 Container, 2 PostgreSQL-Server (inkl. Authentik)
lokal 14 Dienste, 3 Compose-Dateien                  7 Dienste, 2 Compose-Dateien (inkl. E2E-Aufsatz)
29 Dokumente                                         6 Dokumente + Archiv
```

## 3. Feature-Flags

| Flag | gated | dauerhaft? | Entscheidung |
|---|---|---|---|
| `site_selection` | G1-Routen (`site/api.py:70`) | nein, Freischaltung | bleibt bis Go-live; danach Prüfung entfernen, wenn `--all` stabil |
| `rules_simulation` | G2-Kundenrouten (`rules/api.py:61`) | nein | wie oben |
| `envelope_simulation` | G3 (`envelope/api.py:32`) | nein | wie oben |
| `inquiry` | Anfrage (`inquiry/api.py:55`) | nein | wie oben |
| `configurator` | H2/H3 (`configuration/api.py:42`) | nein | wie oben |
| `submission` | V (`submission/api.py:38`, `inquiry/api.py:60`) | nein | wie oben |
| `EMPRISE_EXTERNAL_ORGANISATIONS` | Anlage fremder Büros | Sicherheitssperre bis E-A5 | bleibt (Konfiguration, kein Flag) |

Nach dem Merge gilt jedes Flag für beide Bereiche; für Architekten sind lokal alle per `--role architect` gesetzt (README).

## 4. Schritte

### Phase 0 – Ausgangslage

| # | Change | Reason | Affected files | Risk | Migration strategy | Validation | Rollback |
|---|---|---|---|---|---|---|---|
| 0a | CI-Behebung committen | lag uncommittet vor | `0020_organisations.py`, `organisation.test.tsx`, `.gitleaksignore`, README | – | – | Diff gesichtet | Revert |
| 0b | Hand-off 29.09. committen | lag uncommittet vor | `AENDERUNGEN.md`, `HANDOFF.md` | – | – | – | Revert |
| 0c | Refactoring-Dokumente auf die Entscheidungen bringen | Phase 0/1 des Auftrags | `REFACTORING_*.md` | – | – | Links, Zeilenangaben per Grep | Revert |

### Phase 2 – Infrastruktur

#### S1 – Eine Backend-Anwendung

- **Change:** Produktprofil entfällt. `products.py` hält `ROUTERS`, `JOB_MODULES`, `PERIODIC` (Vereinigung; Router in der Reihenfolge von `ALL_ROUTERS`). `create_app` hängt alle Router ein, `create_full_app` entfällt. `registry.py` lädt alle Job-Module, der Worker plant alle periodischen Aufgaben ein. Nach der Anmeldung `/buero`; abgelehnte Anmeldung nach `/analyse?grund=…`, wenn `next` im Analyse-Bereich liegt, sonst `/buero/kein-zugang?grund=…`. Die Produktprüfung bei `POST /projects` entfällt. Einstellung `product` entfällt.
- **Reason:** Entscheidung „eine Anwendung“; B-73.
- **Affected files:** `backend/app/products.py`, `main.py`, `registry.py`, `config.py`, `cli.py` (openapi), `platform/jobs/worker.py`, `platform/auth/staff.py`, `platform/projects.py`, `platform/shared.py` (Übergang); Tests `test_module_boundaries.py`, `test_analysis.py`, `test_rule_correction.py`.
- **Risk:** R-60 (Routen oder Jobs fehlen), R-61 (abgelehnte Anmeldung am falschen Ort), R-62 (anonyme Kunden erreichen Analyse – ausgeschlossen durch `require_owned_project`).
- **Migration strategy:** Code-only; der alte Analyse-Stack ignoriert `EMPRISE_PRODUCT` bis zu S3.
- **Validation:** voller Backend-Lauf; `openapi.json` unverändert (`test_openapi_contract`); `test_access_policies.py` über alle Routen.
- **Rollback:** Revert.

#### S2 – Ein Frontend-Einstieg, Analyse unter `/analyse`

- **Change:** `main.tsx` lädt für `/analyse…` die Analyse-App per `lazy()` mit `basename: "/analyse"`, sonst den Konfigurator. `analyse.html`, zweiter Rollup-Einstieg und `SPA_INDEX` entfallen. Login-Links im Analyse-Layout tragen `next=/analyse…`. `src/products/analyse` → `src/analyse`.
- **Reason:** „eine React-Anwendung“; ein Hostname.
- **Affected files:** `frontend/src/main.tsx`, `src/products/analyse/*` (verschoben), `analyse.html`, `vite.config.ts`, `Caddyfile`, `Dockerfile` (falls `SPA_INDEX` dort steht), Tests im Analyse-Ordner.
- **Risk:** R-63 (absolute Links im Analyse-Bereich), R-64 (CSS-Tokens mischen sich – ausgeschlossen, Wechsel per Neuladen).
- **Migration strategy:** Code-only.
- **Validation:** Typprüfung, Lint, Vitest, Build (Analyse als eigener Chunk), Smoke `/`, `/grundstueck`, `/buero`, `/analyse`.
- **Rollback:** Revert.

#### S3 – Compose ohne zweiten Produkt-Stack

- **Change:** lokal `compose.analyse.yaml` und `infra/local/postgres-init-analyse.sql` löschen; Unraid `compose.analyse.yaml`, `.env.analyse.example`, Zweig `analyse` in `deploy.sh` löschen; `EMPRISE_PRODUCT` überall entfernen; Befehle und Adressen in README, `deploy/unraid/README.md`, `docs/BETRIEB.md` 15 anpassen.
- **Reason:** eine Instanz.
- **Affected files:** siehe Change; `.github/workflows/ci.yml` prüfen.
- **Risk:** R-65 (alte Befehle in der Doku), R-11 (lokale Daten – bleiben liegen).
- **Migration strategy:** alten Stack mit `docker compose -p emprise-analyse down` (ohne `-v`) beenden. Reverse-Proxy-Weiterleitung und Authentik-Anwendung auf Unraid: ROADMAP.
- **Validation:** `docker compose config`, Start, Smoke.
- **Rollback:** Revert; alter Stack startet mit den liegengebliebenen Volumes.

#### S4 – Gemeinsame Tabellen in die Hauptdatenbank (vorher REF-003, REF-003b)

- **Change:** `SharedSetting`, `ReferenceList`, `ReferenceEntry` auf `Base`; `SharedAudit` geht in `audit_log` auf, sofern die Spalten passen. Migration 0021 legt fehlende Tabellen an und entfernt `alembic_version_shared`. `get_shared_db` → `get_db`, `shared_session()` → `get_sessionmaker()()`. Entfallen: `migrations_shared/`, `alembic_shared.ini`, `shared-migrate`, `_move_model_setting`, `app_setting` (falls leer), `EMPRISE_SHARED_*`, `db-init-shared`, Unraid-Stack `emprise-shared`.
- **Reason:** eine Datenbank; ein Alembic-Strang (B-30).
- **Affected files:** `platform/shared.py`, `rules/reference_models.py`, `reference_store.py`, `reference_api.py`, `model_choice.py`, `rules/service.py`, `cli.py`, `backend/Dockerfile`, `migrations_shared/*`, `alembic_shared.ini`, `migrations/versions/0021_*.py`, `tests/conftest.py`, Compose-Dateien, `infra/local/postgres-init-shared.sql`, `deploy/unraid/compose.shared.yaml`, `.env.shared.example`, `postgres/20-shared.sh`, i18n „für beide Produkte“.
- **Risk:** R-20 (Referenzlisten gehen verloren), R-22 (vorhandene Tabellen mit abweichendem Schema).
- **Migration strategy:** vorher `pg_dump --data-only` der vier Tabellen aus `emprise_shared`, nach 0021 in `emprise` einspielen, Zeilen zählen; `emprise_shared` bleibt liegen.
- **Validation:** Migration auf leerer DB und auf lokaler Kopie; `alembic check`; Integrationstests Referenzlisten und Modellwahl.
- **Rollback:** `downgrade` von 0021; Revert.

#### S5 – Lange Jobs in eigene Warteschlange (vorher REF-001)

- **Change:** `queue="long"` für `rules_extract`, `rules_document_read`, `rules_document_ocr`, `plu_import`, `cadastre_import`; Migration 0022 stellt wartende Jobs um; `/health/jobs` je Queue (`job_waiting_alarm_minutes_long`); Unraid-Dienst `worker-long`; lokal ein Worker für `["default","long"]`.
- **Reason:** B-10.
- **Affected files:** `rules/jobs.py`, `site/jobs.py`, `platform/health.py`, `config.py`, `migrations/versions/0022_*.py`, Compose, `deploy.sh`, `tests/integration/test_jobs.py`.
- **Risk:** R-01 (Jobs ohne Abnehmer), R-02 (doppelte Wartung – unkritisch).
- **Migration strategy:** Migration stellt wartende Jobs um.
- **Validation:** Test „`claim` mit `default` nimmt keinen `long`-Job“; Health-Test; Mailpit bei wartender Auswertung.
- **Rollback:** Revert; `UPDATE job SET queue='default' WHERE status='queued'`.

#### S6/S7 – Dateien im Verzeichnis statt SeaweedFS (vorher REF-002)

- **Change:** `platform/storage.py` auf `EMPRISE_FILES_DIR` (gleiche vier Funktionen, atomar, Traversal abgewiesen), `storage-init` legt an und prüft; Übergangsbefehl `storage-copy-from-s3` (S6). S7 entfernt Übergangsbefehl, `boto3`, `boto3-stubs`, `presigned_get_url`, `s3_*`, Dienst `storage`, SeaweedFS in CI, `TEST_S3`.
- **Reason:** B-20, B-21: ein Host, vier Funktionen.
- **Affected files:** `platform/storage.py`, `config.py`, `cli.py`, `pyproject.toml`, `uv.lock`, `backend/Dockerfile`, Compose, Unraid-Compose, `.env.example`, CI, `tests/integration/test_storage_ops.py`, neue Unit-Tests, README-Stolperstellen.
- **Risk:** R-10 (Dateirechte), R-11 (Daten beim Umzug), R-13 (kein Schutz gegen Überschreiben).
- **Migration strategy:** lokal Bucket `emprise-local` kopieren, sha256 der Reglements prüfen; Unraid hat keine Daten.
- **Validation:** Unit-Tests `tmp_path`; Integrationstests; von Hand Bericht-PDF, DXF, Reglement-Zitat.
- **Rollback:** bis S7 Einstellung zurück (Daten liegen noch in SeaweedFS); danach Revert.

### Phase 3 – Backend

| # | Change | Reason | Affected files | Risk | Migration strategy | Validation | Rollback |
|---|---|---|---|---|---|---|---|
| S8 | AN6-Zusätze entfernen: `ApiKey`, Bearer-Weg, `API_KEY_PATHS`, `document_api_keys`, Flag-Zweig `auth.api`, `UsageRecord` und Scan-Kontingent, Budget je Organisation, Logo/Farben in Bericht und DXF, CLI `org-set-budget`, Routen `/organisation/logo`, `/usage`, `/api-keys`, Frontend-Abschnitte | Entscheidung; ein Auth-Weg weniger | `platform/auth/context.py`, `middleware.py`, `flags.py`, `organisations.py`, `org_api.py`, `models.py`, `rules/ocr.py`, `analysis/report.py`, `analysis/export.py`, `config.py`, `cli.py`, `main.py`, Migration 0023, Frontend `analyse/OrganisationSeite.tsx`, Tests, `docs/API_ANALYSE.md` | R-66 (Report-Layout ohne Branding), R-67 (Zugriffsregeln) | Migration 0023 entfernt Tabellen/Spalten, `downgrade` legt sie leer an | Backend, `test_access_policies.py`, `test_organisations.py`, Frontend, OpenAPI → TS | Revert + `downgrade` |
| S9 | toten Code entfernen | B-24 u. a. | `configuration/domain/placement.py:303,308`, weitere nur bestätigte Funde | R-32 | – | voller Lauf | Revert |
| S10 | `rules/sources.py` (`store_source`, `ensure_chapter`, `ChapterValues`) aus `plan_import` | B-07, B-68 | `rules/plan_import.py`, `rules/documents.py`, Tests | minimal | – | voller Lauf | Revert |
| S11 | Schnittstelle der Extraktion nach `rules/domain/extraction.py`; `input_hash`/`ocr_stamp` in leichtes Modul; Test „reine Lesepfade laden kein `openai`“; Zugriffsregel B-23 | B-68, B-69, B-23 | `integrations/openrouter.py`, `rules/extract.py`, `rules/service.py`, `plan_import.py`, `auth/context.py`, `tests/unit/test_module_boundaries.py`, `test_access_policies.py` | minimal | – | neuer Test schlägt bei absichtlichem Import an | Revert |
| S12 | reine Zonenauflösung `rules/domain/resolve.py` (`resolve_zones`, `overall_status`, `split_slivers`, `choose_result`); Rückkanal `warnings` wird Rückgabewert; Korrekturen auf Domain-Dataclass | B-60, B-61 | `rules/service.py`, neu `rules/domain/resolve.py`, Unit-Tests | R-68 (Verhalten ändert sich beim Herauslösen) | – | Unit-Tests; `envelope-check --commune 44209` vorher = nachher | Revert |
| S13 | reine Geometrie aus `site/service.py` (`relocate`, `choose_candidate`, `upload_provenance`, `classify_outline`); eine `_rings`; ein `SiteEdge`-Helfer | B-62, B-63 | `site/service.py`, `site/domain/*`, `envelope/domain/local.py`, `configuration/service.py` | R-68 | – | Unit- und Integrationstests, E2E `site.spec.ts` | Revert |
| S14 | `configuration/domain/change.py: decide_change`, `options.py: option_states`; Bruttoformel nur vereinheitlichen, wenn Werte gleich | B-64, B-65 | `configuration/service.py`, `domain/*`, `outputs.py`, Tests | R-69 (Preisänderung) | – | Test hält heutige Werte fest | Revert |
| S15 | `catalog/domain/offer.py: build_offer`, `consistency.py: type_findings` | B-66 | `catalog/service.py`, `catalog/domain/*` | R-68 | – | voller Lauf | Revert |
| S16 | eine `_rule_input`; `fingerprint` nach `envelope/domain/fingerprint.py` | B-67 | `analysis/service.py`, `envelope/service.py` | minimal | – | voller Lauf | Revert |
| S17 | eine Leseroutine `read_pages(pdf) -> NormalizedDocument(pages, is_scan)` für GPU und Upload; Verhalten unverändert | B-70 | `rules/pdf.py`, `plan_import.py`, `documents.py` | R-70 (Kapitelerkennung) | – | `test_rules_upload.py`, `test_rules.py` | Revert |
| S18 | **fix:** OCR-Stand im `input_hash` auch beim Text-Rückfall | B-71 | `rules/extract.py`, Test | ältere Hashes werden neu (erwünscht) | – | Test | Revert |
| S19/S20 | `rules/service.py` und `site/service.py` nach Anwendungsfall teilen (reine Verschiebung, Schnitte wie ANALYSIS 5.1) | B-06 | `rules/*`, `site/*`, Aufrufer, Tests | R-40 | – | voller Lauf, `git diff --color-moved` | Revert |

### Phase 4 – Frontend

| # | Change | Reason | Affected files | Risk | Validation | Rollback |
|---|---|---|---|---|---|---|
| S21 | eine Verwaltungsseite für Modellwahl und Referenzlisten | nach dem Merge doppelt (`/verwaltung` und `/analyse/verwaltung`) | `src/verwaltung/*`, `src/analyse/VerwaltungSeite.tsx`, Router | gering | Vitest, Smoke | Revert |
| S22 | tote Props (`vatRate`) und ungenutzte Übersetzungsschlüssel | B-24 | `configuration/Linien.tsx`, `i18n/*.json` | R-32 | `check-texte.test.ts`, Vitest | Revert |
| S23 | handgeschriebene API-Typen durch `components["schemas"]` ersetzen, wo gleich | „keine doppelten Typen“ | Fundstellen per Grep | gering | Typprüfung | Revert |

Doppelte Komponenten werden nur zusammengeführt, wo sie gleich sind; sonst Befund im Abschlussbericht.

### Phase 5 – Dokumentation (nach Phase 2–4)

| # | Change | Reason | Affected files | Risk | Validation | Rollback |
|---|---|---|---|---|---|---|
| S24 | README, ARCHITECTURE, DOMAIN, ROADMAP, DECISIONS (Original-IDs + neue ADRs), AI_CONTEXT aus dem Code | Entscheidung Dokumentation | sechs Dateien | R-31 (Information geht verloren) | Links lösen auf; Stichprobe IDs | Revert |
| S25 | Altbestand unverändert nach `docs/archiv/` (Spezifikation, Umsetzungsplan, Modulpläne, ANNAHMEN, API_ANALYSE, AENDERUNGEN, HANDOFF, infra/README, Mockup, REFACTORING_*); Betriebsteil von BETRIEB in `deploy/unraid/README.md` | Verweise im Code bleiben auffindbar | `git mv` | R-31 | Grep der Verweise | Revert |
| S26 | `CLAUDE.md`, `AGENTS.md` als Einstiege auf `AI_CONTEXT.md`; `/handoff` pflegt ROADMAP und DECISIONS; Memory angepasst | neue Arbeitsweise | `.claude/skills/handoff/SKILL.md`, Memory | R-34 (Session-Start findet Stand nicht) | Probelesen | Revert |

## 5. Nicht vereinfachen

| Bereich | Warum nicht |
|---|---|
| Drei Läufe der Regelauswertung und die Schranken | Vollständigkeit und Richtigkeit (RW19, PLAN_G2_VOLLSTAENDIGKEIT); gemessen |
| Reine `domain/`-Pakete, Hypothesis-Tests | Testbarkeit, Determinismus |
| Auth: OIDC mit MFA, Zugriffsregel je Route, CSRF, Token als Hash, Rate-Limits | Sicherheit |
| Rollen `migrator`/`app` | Anwendung ohne DDL-Rechte |
| Unveränderliche Versionen mit Fundstelle | Nachvollziehbarkeit (L3) |
| PostGIS, Shapely | Kataster, Zonen, Geometrie |
| Organisationen mit Mitgliedern, `EMPRISE_EXTERNAL_ORGANISATIONS` | Projektzugriff im Büro; Sperre bis E-A5 |
| OpenAPI → TypeScript | keine doppelten Typen |
| Textabgleich Frontend → Backend | gleiche Sätze in Oberfläche und PDF |
| IDs der Entscheidungen und Festlegungen | ≈ 770 Verweise aus dem Code; bleiben im Archiv und in DECISIONS |

## 6. Prüfprotokoll (Selbstprüfung)

### 6.1 Erste Fassung (Analyse ohne Merge)

Fehler der ersten Fassung (Zählungen, Aufruferlisten, fehlender `worker-long` im Zielbild, Dateirechte, B-21 als Tatsache, Rückwärts-Reexporte) sind dort behoben und bleiben für die übernommenen Schritte gültig.

### 6.2 Zweite Fassung

| Prüfpunkt | Ergebnis |
|---|---|
| Läuft der alte Analyse-Stack nach S1 weiter? | ja; unbekannte Variable wird ignoriert, Stack entfällt in S3 |
| Wird die Analyse für anonyme Kunden offen? | nein; `require_owned_project` (`platform/auth/context.py:350`) für Analyse und PLU-Upload |
| Analyse-Projekte in der Prüfliste des Büros? | nein; `review_queue` verlangt eine Anfrage (`site/service.py:1055`) |
| Projektlisten | Architektenliste zeigt alle Projekte der Organisation, auch im Konfigurator angelegte – gewollt („eine Anwendung“); Filter erst bei Bedarf (ROADMAP) |
| `openapi.json` gleich? | ja, wenn `ROUTERS` die Reihenfolge von `ALL_ROUTERS` übernimmt |
| Migrationsnummern | Kopf `0020_organisations`; 0021–0023 linear |
| Bezahlte Läufe | keine; Stacks ohne Schlüssel |
| Fachverlust | nur entschiedene AN6-Zusätze; Extraktionen durch Tests und `envelope-check` gesichert |
| Alternative Konfigurator unter `/configurateur` | verworfen: Kunden-URLs, E2E, Mails ändern sich ohne Gewinn |
| Alternative ein Router für beide Bereiche | verworfen: ≈ 20 absolute Links und Tests; zwei Router in einem Build sind eine Anwendung |
| Alternative ein Worker ohne zweite Queue | verworfen: B-10 wird durch den Merge größer |
| Alternative Backend nach `domains/`/`calculations/`/`infrastructure/` | verworfen: gleiche Struktur unter anderen Namen, ≈ 300 Importänderungen |
