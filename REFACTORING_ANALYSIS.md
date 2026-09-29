# Refactoring-Analyse: Ist-Zustand

> **Stand:** 29.09.2026, Code auf `main` bei `6eb1cd2` plus die lokale, nicht committete CI-Behebung. Nur Analyse, kein Code geändert.
> **Nachtrag 29.09.2026 (zweiter Auftrag):** Der Nutzer hat entschieden, beide Produkte zu einer Anwendung zusammenzuführen, die AN6-Zusätze zu entfernen und die Dokumentation auf sechs Dateien plus Archiv umzubauen. Abschnitt 4 ist dadurch überholt; neue Befunde stehen in Abschnitt 21. Der Plan ist entsprechend neu geschrieben.
> **Quelle der Wahrheit ist der Code.** Wo Dokumente abweichen, steht das in Abschnitt 17.
> Zugehörig: [REFACTORING_PLAN.md](REFACTORING_PLAN.md) (Schritte REF-001 ff.), [REFACTORING_ARCHITECTURE.md](REFACTORING_ARCHITECTURE.md) (Diagramme, Zielbild), [REFACTORING_RISKS.md](REFACTORING_RISKS.md) (Risiken R-01 ff.). Befunde tragen IDs `B-01` ff., auf die der Plan verweist.

## 0. Kernaussage

1. Die Anwendung ist bereits ein **modularer Monolith**: FastAPI, eine PostgreSQL-Datenbank mit PostGIS je Produkt, ein Worker über eine eigene Jobtabelle (`SELECT … FOR UPDATE SKIP LOCKED`), React mit Typen aus OpenAPI. **Kein Redis, kein Celery, keine Microservices.**
2. Die Fachlogik liegt in **reinen, deterministischen `domain/`-Paketen** ohne Datenbank und Netz; das Sprachmodell liefert nur Kandidaten, die durch deterministische Schranken laufen. Die geforderte LLM-Grenze wird eingehalten.
3. Die größte **vermeidbare** Komplexität liegt im **Betrieb**: zwei Produkt-Stacks plus ein dritter gemeinsamer Stack, vier PostgreSQL-Server und zwei S3-Server (SeaweedFS) auf einem einzigen Unraid-Rechner. Nichts davon ist schon in Betrieb, deshalb ist jetzt der günstigste Zeitpunkt zum Vereinfachen.
4. Ein **echter Fehler aus Architektur**: Der Worker arbeitet alle Jobs nacheinander aus einer Warteschlange ab. Eine Regelauswertung (bis 60 min) hält eine Bestätigungsmail auf, deren Code nach 10 min verfällt (B-10).
5. Die **Dokumentation** (≈ 1,16 MB in 29 Dateien) ist größer als nötig. Die Spezifikation steht in der Rangfolge an zweiter Stelle, beschreibt aber noch Celery, Redis, MinIO und die Claude API (B-40).

## 1. Korrektur der Ausgangsannahmen des Auftrags

| Annahme im Auftrag | Befund im Code | Beleg |
|---|---|---|
| Redis wird genutzt (Rate-Limit, Cache, Queue, Sessions, Locks) | **Kein Redis.** Rate-Limits in PostgreSQL, Cache in PostgreSQL oder im Prozess, Queue in PostgreSQL, Sitzungen in PostgreSQL, Sperren über `FOR UPDATE`/`SKIP LOCKED` | `backend/app/platform/rate_limit.py:1` („Kein Redis“), `backend/pyproject.toml` ohne `redis` |
| Celery als Queue | **Kein Celery.** Eigene Jobtabelle `job` mit Claim per `SKIP LOCKED`, Backoff, Zeitlimit, periodischen Aufgaben | `backend/app/platform/jobs/queue.py`, `worker.py` |
| S3-kompatibler Distributed Storage | SeaweedFS **als Einzelknoten**, nicht verteilt; signierte URLs werden in der Anwendung nicht genutzt | `backend/app/platform/storage.py:61` (nur ein Test ruft `presigned_get_url`) |
| mehrere parallele PDF-Pipelines | Zwei Einstiege (GPU-Import und Upload), die in **dieselben** Funktionen münden (`store_source`, `ensure_chapter`) | `backend/app/rules/documents.py:42` |
| LLM trifft fachliche Entscheidungen | Nein: Das LLM liefert `ExtractedRule`, Schranken in `rules/domain/assess.py` prüfen Zitat, Zahlen und Sektor; die Berechnung in `envelope/domain/derive.py` ist rein | Abschnitt 7 |
| doppelte Backend-/Worker-/Docker-Strukturen der zwei Bereiche | Im **Code** ein Paket, ein Image, ein Migrationsstrang, ein Frontend-Paket. Doppelt ist nur der **Betrieb** | Abschnitt 4 |

## 2. Repository-Inventar

```text
building-configurator/
├── backend/            FastAPI-Monolith (≈ 38 200 Zeilen Python in app/, 3 200 in Migrationen, 15 400 Testzeilen)
│   ├── app/platform/   Querschnitt: DB, Auth, Jobs, Flags, Audit, Rate-Limit, Speicher, Organisationen
│   ├── app/integrations/ Adapter: Kataster, IGN, Géorisques, GPU, OpenRouter, SMTP
│   ├── app/site/       G1 Grundstück (Kataster, Skizze, Upload, Scan, Lage, Kanten)
│   ├── app/rules/      G2 Regeln (GPU-Import, Upload, OCR, LLM-Auswertung, Schranken, Korrekturen, Referenzlisten)
│   ├── app/envelope/   G3 Baurahmen (rein) + Steckbrief-PDF
│   ├── app/plan/       Lageplan-Geometrie und DXF-Ausgabe
│   ├── app/analysis/   Produkt „Analyse“: Nutzfläche, Gabarit, Schnitt, Bericht, DXF/GeoJSON
│   ├── app/catalog/    H1 Hauskatalog (Produkt Konfigurator)
│   ├── app/configuration/ H2/H3 Konfiguration, Kosten (Produkt Konfigurator)
│   ├── app/inquiry/    A Anfrage, Einwilligung, Zugang (Produkt Konfigurator)
│   ├── app/submission/ V Vorentwurf-Übergabe, Dossier-PDF (Produkt Konfigurator)
│   ├── migrations/     Alembic, 20 Revisionen, ein Strang für beide Produkte
│   └── migrations_shared/ Alembic, 1 Revision, gemeinsame Datenbank
├── frontend/           React 19 + Vite, zwei Einstiege (index.html, analyse.html); ≈ 17 200 Zeilen von Hand, 5 200 Testzeilen,
│                       10 800 Zeilen erzeugte Typen (schema.d.ts), 2 × 2 250 Zeilen Übersetzungen
├── compose*.yaml       lokal: Hauptstack, Analyse-Aufsatz, E2E-Ergänzung
├── deploy/unraid/      Betrieb bis zur Beta: drei Compose-Projekte + Authentik, deploy.sh, Sicherung
├── infra/              lokale Init-Skripte; README für einen späteren verwalteten Anbieter
├── tools/              Mockup-Build, Textabgleich Frontend → Backend
├── docs/               17 Modulpläne, ANNAHMEN, BETRIEB, API_ANALYSE
└── *.md, *.jsx, *.html Spezifikation, Umsetzungsplan, Hand-off, Änderungsprotokoll, Mockup
```

| Bereich | Zweck | Technik | Wichtige Dateien | Abhängigkeiten | Komplexität | Bekannte Probleme | Vereinfachung |
|---|---|---|---|---|---|---|---|
| Frontend | Zwei SPAs aus einem Paket | React 19, React Router 8, TanStack Query, openapi-fetch, MapLibre, Tailwind 4, i18next | `src/App.tsx`, `src/products/analyse/App.tsx`, `src/api/*.ts`, `vite.config.ts` | API über OpenAPI-Typen | MEDIUM | Vorschaurechnung im Browser neben der des Servers (gewollt, L5); zwei Ordnerlogiken (`pages/` und Fachordner) | gering; keine Umstrukturierung nötig (Abschnitt 14) |
| Backend | API, Fachlogik, CLI | FastAPI, SQLAlchemy 2, Pydantic 2, Shapely, GeoAlchemy2 | `app/main.py`, `app/products.py`, `app/*/service.py`, `app/*/domain/` | PostgreSQL, Speicher, OpenRouter, Behördendienste | MEDIUM–HIGH | vier Dienstmodule über 1 000 Zeilen; zwei Importzyklen | Module nach Anwendungsfall teilen (REF-007 bis REF-009) |
| Datenbank | Fachdaten, Jobs, Sitzungen, Rate-Limits, Kataster | PostgreSQL 16 + PostGIS 3.5, Alembic | `migrations/versions/0001…0020`, `app/*/models.py` | – | MEDIUM | drei Datenbanken (zwei Produkte + gemeinsam), zwei Alembic-Stränge; Tabelle `app_setting` verwaist | gemeinsame Datenbank entfällt (REF-003), `app_setting` entfernen (REF-006) |
| Worker | Hintergrundjobs, periodische Aufgaben | eigener Worker, gleiches Image | `app/platform/jobs/*`, `app/*/jobs.py` | PostgreSQL | LOW | **eine** Warteschlange, **ein** Prozess: lange Jobs blockieren kurze (B-10) | zweite Warteschlange für lange Jobs (REF-001) |
| Infrastruktur | Container lokal, CI, Unraid | Docker Compose, Caddy (selbst gebaut), GitHub Actions, Authentik | `compose*.yaml`, `deploy/unraid/*`, `.github/workflows/ci.yml`, `frontend/Dockerfile` | – | HIGH | 19 Container auf einem Rechner; lokale Stacks über ein externes Netz gekoppelt | SeaweedFS und gemeinsamen Stack streichen, lokal ein Compose-Projekt (REF-002 bis REF-004) |
| Storage | PDFs, DXF, XLSX, Logos, Berichte | SeaweedFS über S3 (`boto3`), Bucket mit Versionierung | `app/platform/storage.py` | Container `storage` | MEDIUM | signierte URLs ungenutzt; Löschen im versionierten Bucket löscht nach S3-Semantik nicht endgültig (B-21) | Dateisystem-Volume (REF-002) |
| AI / LLM | Regeln aus Reglement lesen | OpenRouter über `openai`-SDK, erzwungener Funktionsaufruf | `app/integrations/openrouter.py`, `app/rules/extract.py`, `app/rules/domain/extraction.py`, `assess.py` | OpenRouter | HIGH (fachlich bedingt) | Kosten je Lauf; drei Durchgänge (Auswertung, Gegenprüfung, Nachsuche) | nicht vereinfachen (Abschnitt 7) |
| PDF | Text, Seitenauszüge, Vektorpfade, Rendern, OCR, PDF erzeugen | pypdf, pdfminer.six, pypdfium2 + Pillow, Tesseract, WeasyPrint | `app/rules/pdf.py`, `app/site/domain/pdfplan.py`, `app/platform/scan.py`, drei Renderer | – | MEDIUM | drei Lesebibliotheken; drei WeasyPrint-Renderer mit eigenem HTML/CSS | optional zusammenführen (REF-012, REF-013) |
| Auth | Büro-Anmeldung, Kundenzugang, API-Schlüssel | OIDC (Authentik, lokal Mock), Sitzungen in DB, Projekt-Cookie, Bearer-Schlüssel, CSRF | `app/platform/auth/*`, `app/platform/middleware.py` | Authentik | MEDIUM | Organisationsprüfung hängt am Pfadnamen `project_id` (README-Stolperstelle) | nicht vereinfachen; Regel per Test absichern (REF-010) |
| Tests | Unit, Integration, E2E | pytest (+ hypothesis), Vitest, Playwright | `backend/tests/*`, `frontend/src/**/*.test.tsx`, `frontend/e2e/*` | PostgreSQL, Tesseract | MEDIUM | Backend-Lauf 5–17 min; Tabellenliste in `conftest.py` von Hand gepflegt | Tabellenliste aus Metadaten (REF-014) |
| Dokumentation | Vorgaben, Pläne, Betrieb, Protokoll | Markdown, HTML | Tabelle in `AGENTS.md` | Code verweist ≈ 770-mal auf Kapitel und IDs | HIGH | Spezifikation veraltet, 17 Modulpläne nach Umsetzung historisch, Mockup noch in der Rangfolge | Stand markieren, nicht umbenennen (REF-005, REF-011) |

## 3. Infrastruktur-Komponenten

Einstufung: **A** Essential, **B** Useful (ersetzbar), **C** Optional (vereinfachbar/entfernbar), **D** Dead.

### 3.1 Lokal (`compose.yaml`, `compose.analyse.yaml`)

| Dienst | Zweck | Abhängig von | Genutzt von | Stufe | Begründung |
|---|---|---|---|---|---|
| `db` | PostgreSQL + PostGIS für `emprise`, `emprise_analyse`, `emprise_shared`, `emprise_probe` | – | alle Backends | A | PostGIS für Kataster, Zonen und Transformation (Abschnitt 15) |
| `storage` | SeaweedFS mit S3 | – | `migrate`, `api`, `worker` beider Stacks | C | Einzelknoten, 4 Funktionen genutzt; ein Volume reicht (B-20) |
| `mailpit` | Mails ansehen | – | `worker` | A (nur lokal) | Codes und Zugangslinks prüfen |
| `oidc` | Mock-OIDC | – | `api`, E2E | A (nur lokal/CI) | Anmeldung ohne Authentik |
| `db-init-shared` | legt `emprise_shared` an | `db` | `migrate` | C | entfällt mit REF-003 |
| `migrate` | Alembic, `shared-migrate`, `storage-init` | `db`, `storage`, `db-init-shared` | `api`, `worker` | A | Einmal-Job; wird schlanker |
| `api` | FastAPI | `migrate` | `web` | A | – |
| `worker` | Jobs | `migrate` | – | A | – |
| `web` | Caddy mit SPA und `/api`-Weiterleitung | `api` | Browser | A | – |
| `backend-dev` (Profil) | Tests und Werkzeuge | `db` | Entwickler | A | kein Python auf dem Rechner |
| `db-init-analyse`, `migrate-analyse`, `api-analyse`, `worker-analyse`, `web-analyse` | zweites Produkt | Netz `emprise_default` und Images des Hauptstacks (extern) | – | B | nötig, aber als zweite Compose-Datei mit externem Netz umständlich (B-32) |

### 3.2 Auslieferung Unraid (noch nicht in Betrieb)

| Compose-Projekt | Dienste | Stufe | Befund |
|---|---|---|---|
| `emprise` | `db`, `storage`, `migrate`, `api`, `worker`, `web`, `backup` | A außer `storage` (C) | – |
| `emprise-analyse` | dieselben sieben, eigene Werte | A außer `storage` (C) | zweiter SeaweedFS, zweiter Backup-Container |
| `emprise-shared` | `shared-db`, `backup` | C | eigener PostgreSQL-Server und Backup für eine Einstellungszeile und die Referenzlisten (B-30) |
| `authentik` | `postgresql`, `server`, `worker` | A | D4, MFA; eigener Stack ist richtig |
| Reverse Proxy (vorhanden, außerhalb) | TLS | A | – |
| Überwachung | Vorschlag Uptime Kuma, nicht eingerichtet | B | genügt; Sentry nur als leere Variable (C) |

Summe: **19 Container** (davon 2 Einmal-Jobs `migrate`), **4 PostgreSQL-Server**, **2 SeaweedFS**, **3 Backup-Container**.

### 3.3 CI (`.github/workflows/ci.yml`)

| Job | Inhalt | Stufe | Befund |
|---|---|---|---|
| `backend` | PostGIS-Dienst, **SeaweedFS-Container**, Tesseract, ruff, mypy, pytest | A | SeaweedFS nur für einen Test (`TEST_S3=1`) |
| `frontend` | Typen aus OpenAPI prüfen, Lint, Typen, Vitest, Build | A | – |
| `e2e` | ganzer Stack, Playwright | A | – |
| `security` | gitleaks, Trivy auf beide Images | A | Caddy mit `xcaddy` selbst gebaut, damit Trivy grün ist; Netzfehler zu `sum.golang.org` (README) |

### 3.4 Besonders geprüfte Dienste

| Dienst | Vorhanden? | Stufe | Kurz |
|---|---|---|---|
| Redis | nein | – | nichts zu entfernen |
| Celery | nein | – | nichts zu entfernen |
| SeaweedFS / S3 | ja | C | Abschnitt 11 |
| PostgreSQL | ja, 4 Server auf Unraid | A (1 je Produkt), C (gemeinsamer Server) | Abschnitte 4, 15 |
| PostGIS | ja | A | Abschnitt 15 |
| Worker | ja, einer je Produkt | A | Abschnitt 10 |
| Reverse Proxy | Caddy im Web-Container + vorhandener Proxy auf Unraid | A | – |
| OIDC | Authentik (lokal Mock) | A | Abschnitt 12 |
| Monitoring | Health-Endpunkte, strukturierte Logs, optional Sentry | A (Endpunkte), C (Sentry) | – |

## 4. Zwei Produkte: getrennt lassen oder zusammenführen?

**Befund.** „Emprise Analyse“ und der Hauskonfigurator sind **im Code bereits eine Anwendung**:

| Ebene | Stand | Beleg |
|---|---|---|
| Backend-Paket | eines; `EMPRISE_PRODUCT` wählt Router und Jobs zur Laufzeit | `backend/app/products.py` |
| Fachlogik | Analyse baut auf `envelope/domain` auf, ohne eigene Kopie | `app/analysis/domain/*` importiert `envelope.domain.derive`, `setbacks`, `heights` |
| Grenze Kern ↔ Produkt | per AST-Test gesichert | `backend/tests/unit/test_module_boundaries.py` |
| Migrationen | ein Strang; die Analyse-Datenbank trägt die Konfigurator-Tabellen ungenutzt mit | `migrations/versions` |
| OpenAPI / TS-Typen | eine Datei aus dem vollen Profil | `app/main.py::create_full_app` |
| Frontend | ein Paket, zwei Vite-Einstiege, gemeinsame Fachordner | `frontend/vite.config.ts`, `src/products/analyse` importiert `site`, `rules`, `envelope`, `api` |
| Image | je eines für Backend und Web, `SPA_INDEX` wählt die Seite | `frontend/Caddyfile` |
| **Betrieb** | **getrennt**: eigene Datenbank, eigener Objektspeicher, eigener Hostname, eigene Authentik-Anwendung, eigener Stack | `deploy/unraid/compose.analyse.yaml`, PLAN_ANALYSE 3 |

Gründe für die Trennung im Betrieb stehen in den Dokumenten und sind **Entscheidungen des Nutzers**: Berufsdaten der Büros und Kundendaten des Konfigurators getrennt halten (PLAN_ANALYSE 3), Datenbanken der Produkte untereinander unerreichbar (Entscheidung 28.09.2026, `deploy/unraid/compose.shared.yaml`), rechtlicher Rahmen für fremde Büros offen (E-A5), Datenschutzrollen offen (D6).

> **Überholt durch Entscheidung des Nutzers vom 29.09.2026** (zweiter Auftrag „Complexity Reduction“): Beide Produkte werden **eine** Anwendung mit **einer** Datenbank, einem Hostnamen (Analyse unter `/analyse`) und einem Worker-Image. Die folgende Empfehlung ist nur noch Herleitung; maßgeblich ist [REFACTORING_PLAN.md](REFACTORING_PLAN.md). Warum der Merge sicher ist: Analyse-Routen verlangen schon heute `require_owned_project` (Projekt der eigenen Organisation), das Kunden-Cookie reicht nicht; Kern-Routen liefen schon in beiden Produkten; `review_queue` des Büros zeigt nur Projekte mit Anfrage.

**Empfehlung (Stand vor dem 29.09.): KEEP SEPARATE im Betrieb, Code bleibt zusammengeführt.**
- Zusammenführen im Code ist schon geschehen und richtig; ein weiterer Schritt (eine Instanz für beide Produkte, eine Datenbank) würde die Datentrennung aufheben, die rechtlich noch ungeklärt ist (E-A5, D6), und ein Rückrollen des einen Produkts träfe das andere.
- Vereinfacht wird **um** die Trennung herum: kein dritter gemeinsamer Stack (REF-003), kein S3-Server je Produkt (REF-002), lokal ein Compose-Projekt mit Profil statt zweier gekoppelter Dateien (REF-004).
- Neu bewerten, wenn E-A5 und D6 entschieden sind: Geben sie getrennte Datenbanken in einem Server frei, kann ein PostgreSQL-Server beide Produktdatenbanken tragen (wie lokal schon heute).

## 5. Backend-Komplexität

### 5.1 Große Dateien

| Datei | Zeilen | Verantwortungen heute | Problem | Vereinfachung | Risiko |
|---|---:|---|---|---|---|
| `app/rules/service.py` | 1 450 | (1) Regeln für ein Grundstück auflösen inkl. Rückfall auf älteren Planstand und hochgeladenes PLU, (2) Zusatzdokumente, (3) Abdeckung und Modell für das Büro, (4) Bürofassung anlegen, (5) Projektkorrekturen (AN4), (6) Jobs einplanen und Housekeeping | sechs Anwendungsfälle in einer Datei; `_rules_for_zones` 166 Zeilen mit 13 Parametern (B-06) | teilen nach Anwendungsfall (REF-007) | LOW, reine Verschiebung |
| `app/site/service.py` | 1 438 | Suche/Karte, Grundstück aus Kataster bilden, Skizze/Upload/Scan, Lage einpassen (AN5), Kanten korrigieren, Lesemodelle für G3 und Anzeige | fünf Eingangswege und zwei Lesemodelle in einer Datei; `form_site` 145 Zeilen (B-06) | teilen (REF-008) | LOW |
| `app/catalog/service.py` | 1 170 | Typen, Versionen, Linien, Optionen, Preise, Energie, Plandokumente, Angebot je Typ | groß, aber ein Thema (Katalogpflege) | teilen nur bei nächster Arbeit an H1 (P3) | LOW |
| `app/rules/extract.py` | 1 007 | Ablauf der LLM-Auswertung: Aufrufe, Wiederverwendung, Gegenprüfung, Nachsuche, Kosten, Versionen schreiben | ein Ablauf, fachlich zusammenhängend; `_Calls` kapselt die Aufrufe | **nicht teilen**; der Ablauf liest sich am Stück | – |
| `app/analysis/report.py` | 884 | HTML des Berichts, CSS, Prüfsumme, WeasyPrint | viel HTML als f-Strings | gemeinsame PDF-Basis (REF-012, P3) | LOW |
| `app/rules/plan_import.py` | 814 | GPU-Import, Planstand, Quellen und Kapitel speichern | `store_source` und `ensure_chapter` werden auch vom Upload genutzt (B-07) | in neutrales Modul verschieben (REF-009) | LOW |
| `app/configuration/service.py` | 805 | Konfiguration lesen/ändern, Prüfungen, Kosten | `patch_configuration` 125 Zeilen | P3 | – |
| `app/rules/documents.py` | 743 | Upload des Reglements, Lesen, Zone/Lot wählen | hängt von `plan_import` ab | REF-009 | LOW |
| `app/cli.py` | 688 | 20 Befehle | enthält Einmal-Umzug `_move_model_setting` | Umzug entfernen (REF-006) | LOW |

Die übrigen Dateien liegen unter 700 Zeilen; die längsten Funktionen außerhalb der Tabelle: `site/cadastre_import.py::_run` (149), `submission/service.py::submit` (133), `site/domain/edges.py::_classify` (122), `catalog/service.py::import_type_version` (122). Sie sind lang, aber linear und durch Tests gedeckt; kein Handlungsbedarf außerhalb der Arbeit am jeweiligen Modul.

### 5.2 Schichten und Aufrufketten

- Muster je Modul: `api.py` (FastAPI, Zugriffsregel) → `service.py` (Anwendungsfall, Transaktion) → `domain/` (rein) und `models.py` (SQLAlchemy). **Keine** Repository-Schicht, keine generischen Basisklassen, keine Dependency-Injection-Container. Die Schichtung ist flach und passend.
- Aufrufe über Modulgrenzen gehen nur an `service`-Funktionen (Plan 3.2), zum Beispiel `envelope.service` → `site.service.envelope_site` und `rules.service.envelope_rules`.

### 5.3 Abhängigkeiten zwischen Modulen

```text
platform ⇄ integrations      (platform.mail → integrations.smtp; integrations → platform.logging)
integrations → rules.domain   (openrouter.py nutzt Prompt- und Schemaklassen aus rules/domain/extraction.py)
site → integrations, platform
rules → site, integrations, platform
envelope → site, rules, platform
analysis → envelope, rules, site, plan, platform
catalog → rules, platform
configuration → catalog, envelope, site, platform
inquiry ⇄ submission          (echter Zyklus: Detailansicht des Büros ↔ Übergabe)
```

- **B-01 Zyklus `inquiry` ⇄ `submission`**: `inquiry/service.py:48-49` importiert `submission.views` und `Submission`, `submission/service.py:22-24` importiert `inquiry`. Funktioniert, erschwert aber Verständnis und Tests. P3 (REF-015).
- **B-02** `integrations/openrouter.py` hängt an `rules.domain.extraction`: Der Adapter kennt das Fachschema. Hinnehmbar (ein Aufrufer), nicht umbauen.

### 5.4 Versteckte Seiteneffekte

| Stelle | Seiteneffekt | Bewertung |
|---|---|---|
| `platform/auth/context.py::_touch` | schreibt `last_seen_at`/`last_activity_at` in eigener Transaktion bei **lesenden** Anfragen (höchstens alle 10 min) | gewollt und dokumentiert |
| `platform/rate_limit.py::check_value` | eigene Transaktion, zählt auch bei Rollback der Anfrage | gewollt |
| `app/registry.py` | Import registriert Jobs je Produkt; `main.py` importiert `app.registry` nur wegen des Seiteneffekts | üblich, per `test_module_boundaries.py` abgesichert |
| `rules/model_choice.py` | lädt die Modellliste von OpenRouter mit Prozess-Cache (1 h) und Thread-Sperre | gewollt |
| `platform/tasks.py::retention_cleanup` | löscht Projekte per SQL, **ohne** zugehörige Dateien im Speicher (B-22) | Lücke, PLAN_AN5 7.4 Nr. 9 |

## 6. Wo die Fachlogik liegt

| Thema | Ort | Deterministisch | Testbar ohne DB | Framework-frei | LLM-abhängig | Doppelt |
|---|---|---|---|---|---|---|
| Abstände (Setbacks) | `envelope/domain/setbacks.py`, `bands.py` | ja | ja | ja | nein (nur Parameter) | Klartext im Frontend `products/analyse/abstand.ts` (Anzeige) |
| Baurahmen | `envelope/domain/derive.py` | ja („rein und deterministisch“) | ja | ja | nein | nein |
| Grundfläche | `analysis/domain/footprint.py`, `configuration/domain/surface.py` | ja | ja | ja | nein | verschiedene Fragen (Analyse vs. Konfiguration), keine Kopie |
| Höhe | `envelope/domain/heights.py` | ja | ja | ja | nein | `analysis/domain/storeys.py` bewusst getrennt (Quelle der Regel, EA-Festlegung) |
| Geschosse | `analysis/domain/storeys.py` | ja | ja | ja | nein | nein |
| Grundstücksgeometrie | `site/domain/*` (Kanten, Upload, PDF-Plan, Skizze) | ja | ja | ja | nein | Vorschau im Browser `site/manual.ts` (L5, Server maßgeblich) |
| Konfigurationsregeln | `configuration/domain/*` | ja | ja | ja | nein | Vorschau beim Ziehen `configuration/geometry.ts` (L5) |
| PLU-Regeln (Schranken) | `rules/domain/assess.py`, `kinds.py`, `text.py` | ja | ja | ja | prüft LLM-Ausgabe | nein |
| Validierung Parameter | `rules/domain/kinds.py::validate_params` | ja | ja | ja | nein | Frontend `rules/felder.ts` nur Einheiten; Zusammenhänge prüft der Server |
| Regelwerte als Text | `rules/format.py` (PDF) und `frontend/src/rules/format.ts` (Oberfläche) | ja | ja | ja | nein | **ja, bewusst** – Texte per `tools/sync-check-texts.cjs` und Tests abgeglichen (B-03) |

**Befund:** Die Fachlogik ist sauber getrennt. Die Vorschau-Rechnungen im Browser sind als nicht maßgeblich gekennzeichnet (Leitplanke L5). Die einzige echte Dopplung (Regelwerte als Text) ist durch Abgleich und Tests gesichert.

## 7. Regelkette (G2) und LLM-Grenze

```text
PDF (GPU-Download oder Upload)
 → pdf.check / pdf.read_text (pypdf)            Größe, Seitenzahl, Text je Seite
 → [Scan?] ocr.run_batch (pypdfium2 + Tesseract) nur nach Bestätigung, nur Seiten ohne Textschicht
 → source_page (Text je Seite) + chapters.detect_structure → regulation_chapter
 → extract_chapter: Lauf 1 Auswertung (LLM) → ExtractedRule
 → assess_rule: Sektor, Parameter, Zitat auf der Seite, Zahlen im Zitat, fremder Sektor   (deterministisch)
 → verify: Lauf 2 Gegenprüfung (LLM liest Wert ohne Vorgabe) → nur übereinstimmende Werte wirken
 → fill_gaps: Lauf 3 Nachsuche (LLM) für fehlende Pflichtarten und offene Stellen
 → complete: fehlende Pflichtarten = unknown („missing“), nie Standardwert
 → rule_set_version + rule (unveränderlich)
 → Korrekturen: Bürofassung (office_reviewed) oder Projektkorrektur (AN4) mit Begründung und Fundstelle
 → envelope_input → derive_envelope (rein) → Analyse / Konfiguration (rein)
```

| Frage | Befund |
|---|---|
| Trifft das LLM die fachliche Berechnung? | Nein. Es liefert Regelart, Parameter, Zitat. Gerechnet wird ausschließlich in `envelope/domain`, `analysis/domain`, `configuration/domain`. |
| Trifft es rechtliche Entscheidungen? | Nein. Ergebnis ist eine **Simulation** (D11); das Büro prüft nach Kontakt. Mehrdeutige Vorschriften bleiben offen (E-VA-5). |
| Wo wirkt das LLM am stärksten? | Beim Status `not_regulated` („belegt nicht geregelt“) und bei `text_only`. Beides braucht ein geprüftes Zitat; bei fehlendem Zitat wird die Regel `unknown`. |
| Unnötige Verzweigungen? | Keine gefunden. Die drei Läufe sind eine bewusste Qualitätsentscheidung (RW19, PLAN_G2_VOLLSTAENDIGKEIT) und gemessen (Referenzlisten). Zwei Eingabearten (`pdf`/`text`) je nach Modell (PU12) sind nötig. |
| Entspricht die Kette dem Zielbild `Document → NormalizedDocument → RuleCandidate → Validated RuleSet → Deterministic calculation`? | Ja, unter anderen Namen: `source_page` ≙ NormalizedDocument, `ExtractedRule` ≙ RuleCandidate, `AssessedRule`/`rule_set_version` ≙ Validated RuleSet, `derive_envelope` ≙ Deterministic calculation. **Keine Umbenennung empfohlen.** |

## 8. PDF- und Dokumentpfade

| Pfad | Zweck | Bibliothek | Datei |
|---|---|---|---|
| Reglement lesen | Text je Seite, Plausibilität | pypdf | `rules/pdf.py::read_text`, `check` |
| Seitenauszug für das LLM | PDF mit ausgewählten Seiten | pypdf | `rules/pdf.py::extract_pages` |
| Scan erkennen und OCR | Seiten rendern, Tesseract | pypdfium2, Pillow, `tesseract` | `platform/scan.py`, `rules/ocr.py` |
| Parzelle aus Vektor-PDF | Zeichenpfade, Maßstab | pdfminer.six | `site/domain/pdfplan.py` |
| Parzelle aus Scan | Seite als Bild zum Nachzeichnen | pypdfium2 | `platform/scan.py`, `site/service.py::scan_preview` |
| PDF erzeugen | Steckbrief, Bericht, Dossier | WeasyPrint | `envelope/sheet.py`, `analysis/report.py`, `submission/dossier/pdf.py` |

**Befund B-04:** Es gibt **keine** zwei fachlich gleichen Pipelines. GPU-Import und Upload münden in `plan_import.store_source` und `ensure_chapter`; OCR ergänzt nur fehlende Seitentexte derselben `source_page`. Nebenbefunde: drei Lesebibliotheken für drei verschiedene Fähigkeiten (Text, Vektorpfade, Rendern), alle wegen der AGPL von PyMuPDF gewählt; drei Renderer mit eigenem HTML/CSS (B-05).

## 9. Redis

Keine Redis-Nutzung. Die typischen Redis-Aufgaben liegen so:

| Aufgabe | Datei | Umsetzung | Nötig? | Ersetzbar? |
|---|---|---|---|---|
| Rate-Limiting | `platform/rate_limit.py` | Tabelle `rate_limit_counter`, feste Fenster, HMAC der IP | ja (Spez. 10.1) | ist schon die einfache Lösung |
| Caching | `site/models.py::geocode_cache`, `rules/model_choice.py` | Tabelle mit Ablauf; Prozess-Cache 1 h | ja | – |
| Queue | `platform/jobs/queue.py` | Tabelle `job`, `SKIP LOCKED` | ja | – |
| Sitzungen | `platform/models.py::StaffSession` | Tabelle, Token als Hash | ja | – |
| Locks | `FOR UPDATE` in `site/service.py::_locked_site`, `SKIP LOCKED` im Worker | PostgreSQL | ja | – |
| Job-Verarbeitung | Worker | Abschnitt 10 | ja | – |

## 10. Worker und Queue

| Aspekt | Befund |
|---|---|
| Aktuelle Architektur | `API → INSERT job (gleiche Transaktion) → Worker pollt (1 s) → claim SKIP LOCKED → Handler → complete/fail mit Backoff`; periodische Aufgaben über `periodic_schedule`; verwaiste Jobs per `requeue_stale`; Zeitlimit per `SIGALRM` |
| Tatsächliche Anforderungen | 14 Jobarten: kurz (Mail 60 s, Steckbrief 120 s, Bericht 180 s, Dossier 300 s, Anreicherung 60 s) und lang (Regelauswertung bis 3 600 s, Katasterimport 3 600 s, PLU-Import, Lesen und OCR je 900 s) |
| Komplexität | LOW – ≈ 480 Zeilen, verständlich, getestet (`tests/integration/test_jobs.py`) |
| **B-10 Fehlerbild** | **Eine** Warteschlange `default` (`config.py:160`), **ein** Prozess je Produkt, Reihenfolge `ORDER BY run_after, created_at` (`queue.py:83`). Eine Mail, die hinter einer Regelauswertung eingereiht wird, wartet bis zu deren Ende; stehen mehrere Kapitel an, entsprechend länger. Der Bestätigungscode der Anfrage gilt **10 Minuten** (`config.py:140`). Beobachtet in kleinem Maßstab im E2E-Lauf (ANNAHMEN A28: „schoben den Steckbrief-Job um 24 s nach hinten“). Zudem schlägt `/api/health/jobs` nach 15 min Wartezeit Alarm, auch wenn nur Auswertungen legitim warten. |
| Einfacher PostgreSQL-Worker ausreichend? | **Ja – er ist schon einer.** Nötig ist nur die Trennung kurz/lang, die Tabelle (`job.queue`) und die Einstellung (`EMPRISE_WORKER_QUEUES`) schon vorsehen (REF-001). |
| Migrationsaufwand | klein (Dekorator-Argument, zweiter Worker-Dienst, Health je Warteschlange) |
| Risiko | LOW |

## 11. Storage

| Frage | Befund |
|---|---|
| Was wird gespeichert? | Reglements (bis 100 MB, Schlüssel mit SHA-256), Katalog-XLSX/DXF/Plan-PDF, Steckbriefe, Berichte, Dossiers mit Anlagen, Logos. Wenige hundert Dateien je Jahr im Pilotbetrieb. |
| Wie wird zugegriffen? | Nur vier Funktionen: `put_bytes`, `get_bytes`, `delete`, `roundtrip_check`. Alle Downloads laufen **durch die API**; `presigned_get_url` und `public_client` werden nur in `tests/integration/test_storage_ops.py` benutzt (B-20). |
| Metadaten | in der Datenbank (`storage_key`, `content_type` je Zeile); der `ContentType` am Objekt wird nie gelesen |
| Server und Worker | ein Rechner; API und Worker laufen auf demselben Host |
| Sicherung | Datenbank per `pg_dump`; SeaweedFS-Verzeichnis per Unraid-Plugin „Appdata Backup“ als Dateikopie eines laufenden Dienstes (deploy/unraid/README 6) – Wiederherstellbarkeit ungeprüft |
| **B-21 Löschen** | `storage-init` schaltet die Versionierung ein (`cli.py:235`). Nach S3-Semantik legt `delete_object` ohne Versionskennung nur eine Löschmarke an; der Inhalt bleibt. Löschungen nach Betroffenenrechten (Projekt löschen, Dossiers) wären dann unvollständig. Auf SeaweedFS **nicht nachgeprüft** – erster Schritt von REF-002. |
| **B-22 Verwaiste Dateien** | `retention_cleanup` löscht Projekte per SQL, Dateien bleiben (PLAN_AN5 7.4 Nr. 9) |
| Stolperstellen | Start ~15 s, `-volume.max=0` nötig, keine Konsole, Dateien zum Ansehen nur über Python-Einzeiler (README) |
| Brauchen wir S3-kompatiblen verteilten Speicher? | **Nein, heute nicht.** Ein Rechner, API und Worker auf demselben Host, keine signierten URLs, geringe Datenmenge. Ein Verzeichnis auf einem gemeinsamen Volume erfüllt alle genutzten Fähigkeiten. S3 wird wieder nötig bei einem zweiten Rechner oder beim Wechsel zu einem verwalteten Anbieter (infra/README) – dank der vier Funktionen ist das dann eine lokale Änderung. |

## 12. Authentifizierung und Autorisierung

| Baustein | Umsetzung | Sicherheitskritisch | Architekturkomplexität |
|---|---|---|---|
| Büro-Anmeldung | OIDC (Authlib), PKCE, MFA-Pflicht über `amr`, keine automatische Kontoanlage, Sitzung als Token-Hash in DB | ja | LOW |
| Kundenzugang | anonymes Projekt-Cookie, Token-Hash, Zugangslink per Mail (V) | ja | LOW |
| API-Schlüssel (AN6) | `Bearer emp_…`, nur `/api/v1/projects`, nie mit Cookies, Scopes `read`/`write`, Rate-Limit je Schlüssel | ja | MEDIUM |
| Rollen | `architect`, `rules_admin`, `catalog_admin`, `ops`; wirksam nur in Organisation `operator`, in fremder nur `architect` | ja | MEDIUM |
| Zugriffsregeln | genau eine Regel je Route, per Test erzwungen (`test_access_policies.py`) | ja | LOW |
| CSRF | Double-Submit-Cookie in `middleware.py` | ja | LOW |
| Mandantentrennung | `require_project_access`, `require_owned_project`, `_check_staff_project` | ja | MEDIUM |

**Befund B-23:** Die Organisationsprüfung für `/admin`-Routen greift nur, wenn der Pfadparameter genau `project_id` heißt (`context.py::require_roles`, README-Stolperstelle). Eine künftige Route mit anderem Namen würde die Prüfung still umgehen. Keine Vereinfachung, sondern eine Absicherung per Test (REF-010).

**Empfehlung:** Nichts entfernen. Die Komplexität ist überwiegend sicherheitsbedingt und gut getestet.

## 13. Mandantenfähigkeit (AN6)

| Frage | Befund |
|---|---|
| Umfang | ≈ 2 100 Zeilen (`platform/organisations.py`, `org_api.py`, `rules/budget.py`, Migration 0020, `OrganisationSeite.tsx`, `api/organisation.ts`) plus Tests |
| Genutzt heute? | Nur im Analyse-Produkt: die Organisation „Eigenes Büro“ (`operator`) hält den Bestand. Fremde Büros sind per `EMPRISE_EXTERNAL_ORGANISATIONS=false` gesperrt bis E-A5. Lokal Testdaten „Atelier Sud“. |
| Echte Isolation | zeilenbasiert (`organisation_id` an Projekt, Dokument, Auswertungslauf), keine Datenbank je Mandant – die einfachste tragfähige Form |
| Nötig heute? | **Teilweise.** Das eigene Büro braucht Konten und Projekte; Budget je Organisation, Scan-Kontingent, Erscheinungsbild und API-Schlüssel sind Vorbereitung auf fremde Büros (vom Nutzer als „technische Basis“ beauftragt). |
| Empfehlung | **Einfrieren, nicht entfernen.** Entfernen kostet mehr als es spart (Migration, Tests, sicherheitskritischer Code) und hebt eine Nutzerentscheidung auf. Nicht weiter ausbauen (Bezahlung, Einladungen), bis E-A5 entschieden ist. Fällt E-A5 negativ aus: Rückbaupfad in REF-016 (P3). |

## 14. Frontend

| Aspekt | Befund |
|---|---|
| Struktur | Fachordner `site/`, `rules/`, `envelope/`, `configuration/`, `katalog/`, `verwaltung/`, `inquiry/`, dazu `pages/` für Seiten des Konfigurators und `products/analyse/` für das zweite Produkt |
| State | TanStack Query für Serverzustand, lokaler React-State; kein globaler Store |
| API-Schicht | `openapi-fetch` mit Typen aus `schema.d.ts`; `src/api/*.ts` definiert Hooks und leitet Typen aus `components["schemas"]` ab – **keine** von Hand gepflegten DTOs (Ausnahme `Problem` in `client.ts`, RFC 9457) |
| Doppelte Komponenten | keine gefunden; das Analyse-Produkt nutzt die gemeinsamen Bausteine (`site/KantenListe`, `rules/RegelFormular`, `envelope/Baurahmen`, `components/plan/*`) |
| Business Logic | nur Vorschau (Ziehen, Skizze, Einpassen, Scan-Maßstab) und Formatierung; maßgeblich bleibt der Server (L5) |
| Große Komponenten | `OrganisationSeite.tsx` 728, `Zusatzdokumente.tsx` 469, `KatalogLinienOptionen.tsx` 463, `GabaritSchnitt.tsx` 437 Zeilen – groß, aber je ein Bildschirm |
| Tote Stellen | Prop `vatRate` in `configuration/Linien.tsx:20-24` (per `void` stillgelegt); vermutlich ungenutzte Übersetzungsschlüssel (Abschnitt 18) |
| Empfehlung | Keine Umstrukturierung nach `features/`. Die bestehenden Fachordner entsprechen dem Zielbild bereits weitgehend; ein Umzug kostet Importänderungen in ~150 Dateien ohne fachlichen Gewinn. |

## 15. Datenbank

| Aspekt | Befund |
|---|---|
| Tabellen | 62 in der Produktdatenbank (Plattform 14, Grundstück 13, Regeln 13, Katalog 13, Anfrage 4, übrige je 1–2), 4 in der gemeinsamen (`shared_setting`, `shared_audit`, `reference_list`, `reference_entry`) |
| PostGIS | `ST_Transform` (18×), `ST_Intersects`/`Intersection`/`DWithin`/`Covers` für Kataster-Kartenausschnitt, Nachbarn, Zonen und Überlagerungen, GIST-Indizes. **Essential**: Bbox-Suche über ~8 800 Parzellen je Gemeinde und Zonenschnitt. Berechnet wird in Shapely (Lambert-93). |
| Muster | UUID-Schlüssel, `created_at/created_by`, unveränderliche Versionen (`rule`, `rule_set_version`, Katalogversionen), Staging-Tabellen für Katasterimport |
| Doppelte Modelle | keine; `app_setting` (Migration 0016) ist durch `shared_setting` abgelöst und nur noch Quelle eines Einmal-Umzugs (`cli.py:423`) → **wahrscheinlich tot** (B-24) |
| Generische Tabellen | `feature_flag`, `audit_log` mit JSONB `before/after` – angemessen |
| Rollen | `migrator` (DDL), `app` (DML), `readonly` (angelegt, von keinem Dienst genutzt; für Auswertungen von Hand) |
| Drei Datenbanken | Produktdatenbanken getrennt (Abschnitt 4); die gemeinsame hat einen eigenen Alembic-Strang (`migrations_shared`, `alembic_shared.ini`), eigene Engine und eigene Sitzung (`platform/shared.py`). Ohne `EMPRISE_SHARED_DATABASE_URL` liegen ihre Tabellen bereits heute in der Produktdatenbank (Tests, Einzelinstanz) – der Code kann ohne gemeinsamen Server laufen. |

## 16. API

| Aspekt | Befund |
|---|---|
| Umfang | `backend/openapi.json` 480 KB aus dem vollen Profil beider Produkte |
| Schichten | Route → Service → Domain; Pydantic-Schemas je Modul (`schemas.py`), keine Repository-Schicht, keine DTO-Mapper-Klassen |
| Doppelte DTOs | keine gefunden; `analysis` nutzt `envelope.schemas`, `rules.schemas`, `site.schemas` wieder |
| Frontend-Typen | erzeugt (`pnpm run api:types`), in CI auf Aktualität geprüft; **beibehalten** |
| Fehler | RFC 9457 mit stabilem `code`; Texte im Frontend |
| Auffällig | `create_full_app` baut ein Profil nur für die OpenAPI-Datei – nötig, damit es eine Typdatei gibt; klein und begründet |

## 17. Dokumentation

### 17.1 Einordnung

| Datei | Größe | Einordnung | Begründung |
|---|---:|---|---|
| `AGENTS.md` | 8 KB | CURRENT, IMPORTANT | Einstieg, Dokumententabelle, Rangfolge |
| `CLAUDE.md` | 2 KB | CURRENT | Arbeitsweise |
| `HANDOFF.md` | 13 KB | CURRENT | Momentaufnahme |
| `README.md` | 28 KB | CURRENT, IMPORTANT | Aufbau, Start, Prüfbefehle, Stolperstellen |
| `docs/BETRIEB.md` | 59 KB | CURRENT, IMPORTANT | Betrieb je Modul |
| `docs/ANNAHMEN.md` | 162 KB | CURRENT, IMPORTANT | Festlegungen mit IDs, auf die der Code verweist |
| `docs/API_ANALYSE.md` | 4 KB | CURRENT | Anleitung für Büros |
| `deploy/unraid/README.md` | 12 KB | CURRENT (noch nicht ausgeführt) | Auslieferung |
| `BACKEND_SPEZIFIKATION.md` | 125 KB | **OUTDATED (teilweise)**, IMPORTANT | Rang 2, beschreibt aber Celery/Redis (Z. 110–150), Claude API statt OpenRouter, MinIO; Korrekturen S1–S17 offen (Anhang E.4) |
| `UMSETZUNGSPLAN.md` | 85 KB | CURRENT für Entscheidungen D1–D18 und Kapitel 7; HISTORICAL für die Modulabschnitte | nennt noch Scaleway als Anbieter (4 Stellen), Claude API (6), OpenRouter nicht |
| `docs/PLAN_*.md` (17) | 550 KB | HISTORICAL nach Umsetzung, IMPORTANT für Entscheidungs-IDs (E-AN…, E-VA…) und offene Punkte | tragen Prüfprotokolle und Abnahmen |
| `AENDERUNGEN.md` | 83 KB | HISTORICAL | nur der neueste Eintrag wird gelesen |
| `infra/README.md` | 5 KB | HISTORICAL (Zukunft) | Anforderungen an einen verwalteten Anbieter, derzeit nicht verfolgt (D3) |
| `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html` | 293 KB | HISTORICAL | Mockup vom 13.09.; das echte Frontend ersetzt es; steht aber noch in Rangfolge 3–4 und auf der Aufgabenliste (HANDOFF 4.6 „Einwilligung im Mockup“) |
| `tools/build-mockup.cjs` | – | HISTORICAL | nur für das Mockup |

**Keine Datei ist REMOVE**, weil Code und Dokumente per ID aufeinander verweisen (≈ 180 × „Spez.“, ≈ 440 × „Plan“/`PLAN_…`, ≈ 150 × ANNAHMEN-IDs). **MERGE** lohnt sich nur für ältere Einträge in `AENDERUNGEN.md` (archivieren). Ein Umbau auf `README / ARCHITECTURE / DOMAIN / ROADMAP / DECISIONS / AI_CONTEXT` wird **nicht** empfohlen: Die heutige Struktur hat dieselben Rollen (README, ANNAHMEN = DECISIONS/DOMAIN, HANDOFF = ROADMAP, AGENTS/CLAUDE = AI_CONTEXT); es fehlt nur eine knappe **Architekturbeschreibung aus dem Code** – dafür kann `REFACTORING_ARCHITECTURE.md` Abschnitt 1–4 die Vorlage sein (REF-005).

### 17.2 Widersprüche Dokument ↔ Code (Code = Ist)

| ID | Dokument/Kommentar | Aussage | Code |
|---|---|---|---|
| B-40 | `BACKEND_SPEZIFIKATION.md` 3.1 (Z. 110–150) | Worker Celery 5, Scheduler Celery Beat, Redis als Broker und Cache | PostgreSQL-Queue; Abweichung steht in Plan 7 (Z. 660), Spezifikation nicht nachgezogen |
| B-41 | `BACKEND_SPEZIFIKATION.md` | Claude API (13 Stellen), MinIO | OpenRouter (`integrations/openrouter.py`), SeaweedFS |
| B-42 | `UMSETZUNGSPLAN.md` | Scaleway als Anbieter, Claude API | Unraid (D3), OpenRouter |
| B-43 | `backend/app/config.py:37` | „Entscheidung D4 offen“ | D4 entschieden 14.09.2026 (Authentik) |
| B-44 | `backend/app/config.py:84` | „Entscheidung D1 offen“ | D1 entschieden 14.09.2026 (Treillières) |
| B-45 | `backend/app/config.py:62` | `s3_region = "fr-par"` (Scaleway) | Unraid setzt `us-east-1` |
| B-46 | `.github/workflows/ci.yml:2` | Auslieferung „folgt … in deploy.yml“ | keine `deploy.yml`; ausgeliefert wird per `deploy/unraid/deploy.sh` |
| B-47 | `backend/app/rules/pdf.py:6` | „OCR … ist noch nicht eingebaut“ | seit AN7 für hochgeladene Dokumente eingebaut (`rules/ocr.py`); für GPU-Importe weiterhin nicht |
| B-48 | `docs/PLAN_ANALYSE.md:51` | Modul `intake/` für den Upload | kein `intake/`; Upload liegt in `site/` und `rules/` (so auch `products.py`) |
| B-49 | `backend/app/cli.py:225` | `storage-init` „MinIO lokal“, „OpenTofu“ | SeaweedFS, kein OpenTofu (A21) |

## 18. Dead Code

| Fund | Ort | Einstufung | Beleg |
|---|---|---|---|
| `footprint_polygons`, `all_segments` | `backend/app/configuration/domain/placement.py:303, 308` | **CONFIRMED DEAD** | kein Aufruf in `app/` und `tests/` |
| Prop `vatRate` | `frontend/src/configuration/Linien.tsx:20-24` | **CONFIRMED DEAD** | nur `void vatRate` |
| leerer Ordner `backend;C` | Wurzel | **CONFIRMED DEAD** | leer, nicht versioniert |
| `presigned_get_url`, `public_client`, `s3_public_endpoint_url` | `platform/storage.py`, `config.py` | PROBABLY DEAD | nur ein Test nutzt sie; Spez. 10.1 sieht signierte URLs vor, die Anwendung streamt stattdessen |
| Tabelle `app_setting` + `_move_model_setting` | Migration 0016, `cli.py:423` | PROBABLY DEAD | Umzug nach `shared_setting` lokal gelaufen; auf Unraid nie ausgeliefert |
| Übersetzungsschlüssel `configurator.plan_layers`, `submission.disabled`, `…perM2` | `frontend/src/i18n/*.json` | PROBABLY DEAD | kein Treffer als Literal; Schlüssel können zusammengesetzt sein → per Skript prüfen |
| `renovate.json` | Wurzel | PROBABLY DEAD | nie ein Renovate-PR (`gh pr list` leer); App vermutlich nicht installiert |
| `sentry-sdk` | `main.py`, `worker.py`, `problems.py` | UNKNOWN | nur aktiv mit `SENTRY_DSN`; nirgends gesetzt; Fremdanbieter widerspräche D3/D4 → Nutzer fragen |
| Band `minio-data`, Stack `emprise-g1` | lokal/Unraid | PROBABLY DEAD | HANDOFF 4.5 Nr. 7 |
| Rolle `readonly` | Init-Skripte | ACTIVE (manuell) | „für Auswertungen“ (Plan 6.6) |
| Konfigurator-Tabellen in der Analyse-Datenbank | Migrationen 0007–0011 | ACTIVE (bewusst) | ein Migrationsstrang (PLAN_ANALYSE 3) |
| Feature-Flags `site_selection`, `rules_simulation`, `envelope_simulation`, `configurator`, `inquiry`, `submission` | `*/service.py` | ACTIVE | Einführung intern → Beta → alle |
| Umgebungsvariablen | `config.py` | ACTIVE | alle gelesen; `rules_runs`, `rules_gap_search` für Probeläufe |
| Docker-Dienste | Abschnitt 3 | ACTIVE | – |
| API-Routen | – | UNKNOWN | kein Nutzungsnachweis ohne Zugriffslogs; alle vom Frontend oder von der API-Anleitung referenziert (Stichprobe) |

## 19. Komplexitätsmatrix

| Bereich | Komplexität | Nutzen | Risiko | Vereinfachung | Begründung |
|---|---|---|---|---|---|
| Infrastructure | HIGH | MEDIUM | MEDIUM | HIGH | 19 Container, 4 PostgreSQL, 2 S3 auf einem Rechner; vor der Inbetriebnahme noch ohne Datenumzug zu vereinfachen |
| Backend | MEDIUM | HIGH | LOW | MEDIUM | saubere Schichten; nur große Dienstmodule und zwei Zyklen |
| Frontend | MEDIUM | HIGH | LOW | LOW | typisiert aus OpenAPI, keine Dopplungen von Bedeutung |
| Database | MEDIUM | HIGH | MEDIUM | LOW–MEDIUM | 62 Tabellen fachlich begründet; dritte Datenbank und `app_setting` entbehrlich |
| Worker | LOW | HIGH | LOW | – (Korrektur nötig) | schon PostgreSQL-basiert; Fehlerbild B-10 |
| Storage | MEDIUM | MEDIUM | MEDIUM | HIGH | S3-Server für vier Funktionen auf einem Host; Löschsemantik fraglich |
| LLM | HIGH | CRITICAL | HIGH | LOW | Komplexität ist fachlich (Vollständigkeit, Schranken); nicht vereinfachen |
| PDF | MEDIUM | HIGH | MEDIUM | LOW | drei Bibliotheken für drei Fähigkeiten; Zusammenlegung berührt Zitatprüfung |
| Auth | MEDIUM | CRITICAL | HIGH | LOW | sicherheitskritisch, gut getestet; nur absichern |
| Documentation | HIGH | HIGH | LOW | MEDIUM | 1,16 MB, veraltete Kernaussagen in Rang 2; Umbenennen verboten durch Code-Verweise |

## 20. Technische Schulden (Übersicht)

| ID | Schuld | Wirkung | Schritt |
|---|---|---|---|
| B-10 | eine Warteschlange für kurze und lange Jobs | abgelaufene Codes, verspätete Mails und PDFs, Fehlalarm | REF-001 |
| B-20/21/22 | S3-Server für vier Funktionen, Löschsemantik, verwaiste Dateien | Betriebsaufwand, Datenschutzrisiko | REF-002 |
| B-30 | dritter Stack für gemeinsame Daten | Container, Netz, Reihenfolge beim Ausliefern, zweiter Alembic-Strang | REF-003 |
| B-32 | lokale Stacks per externem Netz gekoppelt | Stolperstellen beim Start | REF-004 |
| B-40–49 | veraltete Aussagen in Spezifikation, Plan, Kommentaren | Fehlleitung neuer Sessions | REF-005 |
| B-24 u. a. | toter Code | Lesezeit | REF-006 |
| B-06 | große Dienstmodule `rules`, `site` | Navigation, Konflikte zwischen parallelen Sessions | REF-007, REF-008 |
| B-07 | Upload hängt an `plan_import` | falsche Richtung der Abhängigkeit | REF-009 |
| B-23 | Organisationsprüfung per Namenskonvention | stille Sicherheitslücke bei neuer Route | REF-010 |
| B-50 | Mockup noch in Rangfolge und Aufgabenliste | Pflege eines zweiten Frontends | REF-011 |
| B-05 | drei PDF-Renderer mit eigenem HTML/CSS | Dopplung | REF-012 (P3) |
| B-01 | Zyklus `inquiry` ⇄ `submission` | Verständnis | REF-015 (P3) |

## 21. Nachträge aus dem zweiten Auftrag (29.09.2026)

Befunde aus der Durchsicht der großen Dienstmodule und der Dokumentkette (Zeilen Stand `457db5d`).

| ID | Befund | Beleg | Schritt |
|---|---|---|---|
| B-60 | `_rules_for_zones` (166 Zeilen, 13 Parameter) mischt 9 Abfragen mit reiner Zonenauflösung; ein versteckter Rückkanal hängt `rules_updating` an die `warnings`-Liste des Aufrufers | `rules/service.py:621–786`, `:706` → `:468` | Plan Schritt 12 |
| B-61 | `apply_override`/`_override_out` sind rein, aber auf das API-Schema `RuleOut` typisiert | `rules/service.py:184–232` | Schritt 12 |
| B-62 | Reine Geometrie in `site/service.py`: Lage einpassen, Kandidatenwahl beim Upload, Kanteneinordnung; `SiteEdge`-Zuordnung doppelt | `site/service.py:776–814`, `:666–707`, `:318–321`, `:365–388` = `:500–523` | Schritt 13 |
| B-63 | `_rings` dreifach | `site/service.py:1082`, `envelope/domain/local.py:18`, `configuration/service.py:235,593` | Schritt 13 |
| B-64 | Entscheidung einer Konfigurationsänderung steckt im Service und wirft HTTP-Fehler | `configuration/service.py:684–755`, `:503–533` | Schritt 14 |
| B-65 | Bruttoformel doppelt, Rundung der €/m²-Preise unterschiedlich (netto gerundet vs. gerundeter Brutto-Einheitspreis) | `configuration/domain/costs.py:103,127`, `configuration/outputs.py:82–83,252–254` | Schritt 14 (erst Befund sichern) |
| B-66 | Angebotsregeln des Katalogs im Service | `catalog/service.py:1007–1166`, `:211–222` | Schritt 15 |
| B-67 | `_rule_input` doppelt | `analysis/service.py:131–149` = `envelope/service.py:67–89` | Schritt 16 |
| B-68 | Transitiver Import des LLM-Adapters in reine Lesepfade: `envelope/service` und `analysis/service` → `rules/service:31` → `rules/extract` → `openrouter` (`import openai`) | `rules/service.py:31`, `plan_import.py:44` | Schritt 10/11 |
| B-69 | Schnittstelle der Extraktion (`ExtractionRequest`, `ExtractionError`, `RuleExtractor`) im Adapter statt in der Domäne | `integrations/openrouter.py:52–96` | Schritt 11 |
| B-70 | GPU-Import und Upload lesen PDFs über getrennte Abläufe; nur der Upload erkennt Scans | `plan_import.py:418–430`, `documents.py:398–457` | Schritt 17; OCR für GPU ist Erweiterung (ROADMAP) |
| B-71 | **Fehler:** Beim automatischen Text-Rückfall über 20 MB geht OCR-Text an das LLM, aber der OCR-Stand fehlt in `input_hash` – eine alte Auswertung kann fälschlich wiederverwendet werden | `rules/extract.py:113–140`, `:333–338` | Schritt 18 |
| B-72 | Verdeckter Zyklus `rules.jobs` ⇄ `rules.*`, nur durch lokale Importe umgangen | `rules/service.py:1329,1349,1386`, `documents.py:387`, `ocr.py:83`, `plan_import.py:343`, `extract.py:894` | beobachten |
| B-73 | Produktprofil (`EMPRISE_PRODUCT`) wirkt nur an wenigen Stellen: Router, Job-Module, periodische Aufgaben, Startseite nach Anmeldung, anonyme Projekte | `products.py`, `main.py:75`, `registry.py:11`, `worker.py:162`, `auth/staff.py:123,133`, `platform/projects.py:125` | Schritt 1 |

Bestätigt ohne Handlungsbedarf: Services von Analyse und Baurahmen folgen schon dem Muster „laden → rein rechnen → ausgeben“; Parzellen-PDFs (pdfminer) sind eine eigene Domäne und bleiben getrennt; die Unterscheidung Scan/Text nach der Normalisierung dient nur Hinweisen an den Nutzer (`scan_unconfirmed`, unsichere Seiten) und ist gewollt.
