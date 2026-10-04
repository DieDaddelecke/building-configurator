# Architektur

> Stand 04.10.2026, aus dem Code nach dem Refactoring vom 29./30.09.2026 und HM0, HM1 und HM3 des Hausmodells. Warum es so ist: [DECISIONS.md](DECISIONS.md). Fachbegriffe: [DOMAIN.md](DOMAIN.md). Befehle: [README.md](README.md).

## 1. Überblick

Eine Anwendung mit drei Bereichen unter einem Hostnamen: Hauskonfigurator für Kunden (`/`), Büro (`/buero`) und „Emprise Analyse“ für Architekten (`/analyse`). Ein modularer Monolith: eine React-App, eine FastAPI-App, eine PostgreSQL-Datenbank mit PostGIS, ein Dateiverzeichnis, Worker aus demselben Image. Kein Redis, kein Celery, kein Objektspeicher.

```text
                          Browser
                             │  HTTPS, ein Hostname (TLS am Reverse Proxy)
                             ▼
          web: Caddy – SPA (/, /buero, /analyse), CSP, /api/* → api:8000
                             │
                             ▼
                       api: FastAPI ──────────────► Authentik (OIDC mit MFA, nur Büro und Analyse)
                             │  ──────────────────► Behördendienste (Suche, Karte)
        ┌────────────────────┼──────────────────────────┐
        ▼                    ▼                          ▼
  PostgreSQL + PostGIS   /data/files (Volume)    worker (Queue default)     worker-long (Queue long)
  Fachdaten, Jobs,       api, worker, migrate    Mail, PDFs, Anreicherung,  Regelauswertung, Lesen, OCR,
  Sitzungen, Rate-                               Wartung                    PLU- und Katasterimport
  Limits, Kataster,                                   │                          │
  Modellwahl,                                         ▼                          ▼
  Referenzlisten                                    SMTP              OpenRouter (LLM), Behördendienste
```

`migrate` ist ein Einmal-Job vor jedem Start: `alembic upgrade head` und `storage-init` (legt `/data/files` an, Schreibprobe).

Dazu kommt seit HM0 der Rechendienst `engine` (Node 24, ohne Zustand, nur im Compose-Netz, Port 8090). Er rechnet mit dem Rechenkern `packages/domain`, den später auch der Browser lädt: `/evaluate` (Auswahl bis Hausbeschreibung, mit Kandidaten) und `/compatibility`. Die API ruft `/compatibility` bei der Prüfung eines Haustyps aus IFC (HM3, 4.5), `/evaluate` ab dem Kundenweg ([docs/PLAN_HAUSMODELL.md](docs/PLAN_HAUSMODELL.md) 3, E-HM-1).

## 2. Auslieferung

### 2.1 Lokal (`compose.yaml`)

| Dienst | Zweck |
|---|---|
| `db` | PostgreSQL 16 + PostGIS 3.5, Datenbank `emprise`; Rollen `migrator` (DDL), `app` (DML), `readonly` (von Hand) |
| `mailpit` | versandte Mails ansehen (Port 8025) |
| `oidc` | OIDC-Testdienst statt Authentik (Port 8081) |
| `migrate` | Einmal-Job, baut das Image `emprise-backend:local` |
| `api` | FastAPI (Port 8000) |
| `worker` | bedient lokal beide Warteschlangen (`EMPRISE_WORKER_QUEUES=["default","long"]`) |
| `web` | Caddy mit der SPA (Port 8080); Build-Kontext ist der Wurzelordner (pnpm-Workspace) |
| `engine` | Rechendienst des Hausmodells, ohne Port nach außen, Gesundheitsprüfung über `/health` |
| `backend-dev` (Profil `dev`) | Tests und Werkzeuge; bindet `./backend` ein und lesend `./packages/domain` (Testdaten des Hausmodells) |

Volumes `db-data` und `files-data`. `compose.e2e.yaml` ist der Aufsatz für die Ende-zu-Ende-Tests (fremde Dienste auf `127.0.0.1:9`).

### 2.2 Unraid (bis zur Beta, noch nicht in Betrieb)

```text
Unraid-Host
├── Reverse Proxy (vorhanden)   building-configurator.aslani.work · auth.aslani.work
├── Stack „emprise“             db · migrate · api · worker · worker-long · web · engine · backup    (8, davon 1 Einmal-Job)
└── Stack „authentik“           postgresql · server · worker                                (3)
Daten:     ${APPDATA_DIR}/postgres, ${APPDATA_DIR}/files (Eigentümer 10001)
Sicherung: pg_dump täglich (Dienst backup) + Dateiverzeichnis über Unraid „Appdata Backup“
```

Einrichtung, Aktualisieren, Rückrollen, Sicherung: [deploy/unraid/README.md](deploy/unraid/README.md).

### 2.3 CI (`.github/workflows/ci.yml`)

| Job | Inhalt |
|---|---|
| `backend` | PostGIS-Dienst, Tesseract; ruff, ruff format, mypy, pytest (Dateien in einem temporären Verzeichnis) |
| `frontend` | API-Typen aus `openapi.json` aktuell, Lint, Typen, Vitest, Build |
| `domain` | Rechenkern und Rechendienst: Vertragstypen aus `openapi.json` aktuell, Lint, Typen, Vitest mit fast-check, Szenarien P 19.7, Bündel mit esbuild und Startprobe |
| `e2e` | ganzer Stack mit `compose.e2e.yaml`, Playwright |
| `security` | gitleaks, Trivy auf Backend-, Web- und `engine`-Image (Caddy mit `xcaddy` gebaut) |

## 3. Backend

### 3.1 Module

| Paket | Modul | Inhalt |
|---|---|---|
| `app/platform` | P | Querschnitt: Datenbank, Auth (`auth/`), Jobs (`jobs/`), Flags, Audit, Rate-Limit, Dateien (`storage.py`), Organisationen, Rechtstexte, Mail, Texterkennung (`scan.py`), Aufräumen (`tasks.py`) |
| `app/integrations` | – | Adapter: Kataster (Etalab), Géoplateforme, IGN BD TOPO, Géorisques, GPU, OpenRouter, SMTP |
| `app/site` | G1 | Grundstück: Suche (`search.py`), aus Kataster bilden (`service.py`), Skizze, Upload und Scan (`manual.py`), Lage (`position.py`), Kanten korrigieren und Prüfliste (`corrections.py`), gemeinsame Hilfen (`store.py`), Katasterimport |
| `app/rules` | G2 | Regeln: GPU-Import (`plan_import.py`), Upload (`documents.py`), Quellen und Kapitel (`sources.py`), Texterkennung (`ocr.py`), LLM-Auswertung (`extract.py`, `runs.py`), Auflösung für ein Grundstück (`service.py`), Büro (`office.py`), Projektkorrekturen (`overrides.py`), Einplanen und Wiederaufnahme (`scheduling.py`), Modellwahl, Referenzlisten |
| `app/envelope` | G3 | Baurahmen (rein) und Steckbrief-PDF |
| `app/plan` | – | Lageplan-Geometrie und DXF |
| `app/catalog` | H1 | Hauskatalog: Typen, Linien, Optionen, Preise, Plandokumente, Angebot je Typ |
| `app/configuration` | H2/H3 | Konfiguration: Lage, Prüfungen, Linie, Optionen, Kosten |
| `app/inquiry` | A | Anfrage, Einwilligung, Kundenzugang |
| `app/submission` | V | Vorentwurf-Übergabe, Dossier-PDF |
| `app/analysis` | AN3–AN5 | Analyse: Grundfläche, Geschosse, Nutzfläche, Gabarit, Schnitt, Bericht, DXF, GeoJSON |
| `app/house` | Hausmodell | Vertrag mit dem Rechenkern (`contract.py`: Template, Katalog, Auswahl, Ergebnis, Hausbeschreibung); IFC lesen im Kindprozess (`ifc_process.py` startet `ifc_reader.py`), rein in `domain/` (Zonen erkennen, Template und Importbericht bilden, Angaben des Büros); Büro-API für Haustypen aus IFC und Katalogversionen (`api.py`, `service.py`); Aufrufe von `engine` (`engine.py`) |

`app/products.py` listet Router und Job-Module der Anwendung; `app/cli.py` die Befehle (`python -m app.cli --help`).

**Zuordnung zum Zielbild des Auftrags:** `platform` ≙ infrastructure, `integrations` ≙ Adapter (auch LLM), `<modul>/domain` ≙ calculations, `<modul>/service.py` ≙ Anwendungsfälle. Die Ordner heißen weiter wie bisher (DECISIONS ADR-09).

### 3.2 Schichten je Modul

```text
api.py        FastAPI-Router: genau eine Zugriffsregel je Route, Rate-Limit, Feature-Flag
service.py    Anwendungsfälle und Transaktionen; andere Module nur über deren service
domain/       rein: keine Datenbank, kein Netz, kein FastAPI; deterministisch, mit hypothesis getestet
models.py     SQLAlchemy 2, Geometrien mit GeoAlchemy2 in Lambert-93 (SRID 2154)
schemas.py    Pydantic → backend/openapi.json → frontend/src/api/schema.d.ts
jobs.py       @job-Handler mit Warteschlange, Zeitlimit und Versuchen; periodische Aufgaben per periodic(...)
```

Keine Repository-Schicht, keine generischen Basisklassen, kein DI-Container.

### 3.3 Abhängigkeiten

```text
analysis ─────────────┐
                      ▼
submission ⇄ inquiry → configuration → catalog
                           │             │
                           ▼             ▼
                        envelope ───► rules ───► site ───► integrations ⇄ platform
                           │            │
                           └── plan ◄───┘ (analysis, submission)
```

`house` hängt bisher nur von `platform` und `rules/domain` (Dachformen der G2-Regeln) ab.

Per Test gesichert (`backend/tests/unit/test_module_boundaries.py`):
- Der Kern (`platform`, `integrations`, `site`, `rules`, `envelope`, `plan`) importiert kein Produktmodul (`catalog`, `configuration`, `inquiry`, `submission`, `analysis`, `house`).
- Reine Lesepfade (`envelope`, `analysis`, `configuration`, `site`) laden das OpenAI-SDK nicht; `rules/domain` importiert keinen Adapter.
- Jedes Modul mit Router oder Jobs steht in `products.py`.

Bekannte Zyklen: `inquiry` ⇄ `submission` (Detailansicht ↔ Übergabe), `rules.jobs` ⇄ `rules.*` (lokale Importe). Beide funktionieren; ROADMAP 5.

## 4. Abläufe

### 4.1 Anfrage an die API

```text
Browser → web → api: Request-ID, Logs → CSRF (Double-Submit-Cookie) → Sitzung oder Projekt-Cookie
       → Zugriffsregel der Route → Feature-Flag → Rate-Limit (eigene Transaktion) → service → domain
       → commit im Endpunkt → Antwort; Fehler als RFC 9457 mit stabilem code
```

### 4.2 Jobs

```text
service:  enqueue(session, kind, …) in derselben Transaktion wie die Fachänderung
worker:   alle 30 s Wartung: periodische Jobs einplanen, verwaiste zurückstellen
          claim: UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1), nur eigene Warteschlangen
          Handler mit Zeitlimit (SIGALRM) → complete | fail mit Backoff 30 s · 2^n, höchstens 1 h
```

Warteschlange `long`: `plu_import`, `rules_extract`, `rules_document_read`, `rules_document_ocr`, `cadastre_import`, `house_ifc_import`. Alle anderen in `default`, damit ein Bestätigungscode (10 min gültig) nicht hinter einer Auswertung (bis 60 min) wartet. `/api/health/jobs` meldet je Warteschlange (Schwellen `job_waiting_alarm_minutes`, `…_long`).

### 4.3 Regeln: LLM liest, Python rechnet, Mensch prüft

```text
PDF (GPU-Download oder Upload)
 → rules/pdf.py: Text je Seite (pypdf), Scan-Erkennung
 → [Scan, nur Upload] rules/ocr.py: Tesseract lokal, nach Bestätigung
 → source_page + regulation_chapter                         (strukturierte Eingabe)
 → rules/extract.py: Lauf 1 Auswertung (OpenRouter)          → ExtractedRule (Kandidaten)
 → rules/domain/assess.py: Zitat auf der Seite, Zahlen im Zitat, Sektor, Parameter   (deterministisch)
 → Lauf 2 Gegenprüfung: liest Werte ohne Vorgabe; nur übereinstimmende Werte wirken
 → Lauf 3 Nachsuche: fehlende Pflichtarten und offene Stellen
 → fehlende Pflichtarten = unknown, nie Standardwert
 → rule_set_version + rule (unveränderlich, mit Fundstelle)
 → Büro: Bürofassung je Zone; Projekt: Korrektur mit Begründung und Fundstelle   (Mensch)
 → rules/service.py + rules/domain/resolve.py: Regeln für ein Grundstück auflösen
 → envelope/domain/derive.py → analysis/domain, configuration/domain                (rein)
```

Das Modell liefert nur Kandidaten mit Zitat. Es rechnet nichts und entscheidet nichts Rechtliches; das Ergebnis ist eine Simulation, das Büro prüft nach Kontakt (D11). Die Schnittstelle (`ExtractionRequest`, `RuleExtractor`) liegt in `rules/domain/extraction.py`, der Adapter in `integrations/openrouter.py`. `rules/runs.py::input_hash` entscheidet, ob gespeicherte Antworten wiederverwendet werden; jede Änderung an Prompt oder Schema erzwingt eine neue, bezahlte Auswertung.

### 4.4 Dateien

```text
platform/storage.py: put_bytes · get_bytes · delete · roundtrip_check  →  EMPRISE_FILES_DIR (/data/files)
atomar über os.replace, Pfad-Traversal abgewiesen, Downloads nur durch die API (Zugriffsregel)
Schlüssel: rules/<partition>/<doc>/<sha256>.pdf · catalog/<slug>/… · dossiers/<project>/<submission>/…
           envelope-sheets/… · Berichte der Analyse · house/ifc/<sha256>.ifc
```

Metadaten (Schlüssel, Typ, sha256) stehen in den Fachtabellen.

### 4.5 Hausmodell: Haustyp aus IFC (HM3)

```text
Büro (catalog_admin): Upload /admin/house/templates/{slug}/versions      Prüfung Endung, Kopf, Größe; Audit
 → house/ifc/<sha256>.ifc + house_template_version (draft) + Job house_ifc_import (long)
 → Kindprozess: Adressraum begrenzen, dann IfcOpenShell → gelesenes Modell (raw, JSONB)   (E-HM-19, E-HM-43)
 → domain/assemble.py mit der zuletzt veröffentlichten Katalogversion
       Wände vereinigen → Bezugskontur, Räume zwischen den Wänden, Zonen → Raumtyp (zones.py),
       Öffnungen auf ihren Wänden, Typ über die Maße, Bodenplatte, Flachdach
   → Template-Entwurf + Importbericht (Befunde error · open · warning · info)
 → Büro: Angaben (decisions) → Entwurf und Bericht neu aus raw, ohne die Datei erneut zu lesen   (E-HM-39)
 → Prüfen: engine /compatibility → house_catalog_compatibility; kompatibel → reviewed
 → Freigeben: Befund bestätigt, Version published und aktuell; Trigger halten beides fest (L4)
```

Katalogversionen (`house_catalog_version`) kommen bis HM6 nur über die CLI (`house-catalog-import`). Ablauf und Rollen: DECISIONS E-HM-37 bis E-HM-46.

## 5. Frontend

| Ort | Inhalt |
|---|---|
| `src/main.tsx` | wählt nach dem Pfad: `/analyse…` lädt `analyse/App` (eigener Chunk, eigener Router mit `basename: "/analyse"`), sonst `App` (Konfigurator und Büro). Wechsel zwischen den Bereichen per Link mit Neuladen |
| `src/App.tsx` | Routen des Konfigurators (`/`, `/grundstueck`, …), des Büros (`/buero/*`); `/verwaltung/*` leitet auf `/analyse/verwaltung` weiter |
| `src/api/` | Hooks mit `openapi-fetch`; Typen aus `schema.d.ts` (`pnpm run api:types`), keine handgeschriebenen DTOs außer `Problem` (RFC 9457) und einzelnen Frontend-Typen |
| Fachordner | `site`, `rules`, `envelope`, `configuration`, `katalog`, `haus` (Hausmodell; bisher der IFC-Import im Büro unter `/buero/katalog/hausmodell`), `inquiry`, `verwaltung`, `analyse`, `components`, `pages` |
| `src/i18n/` | Französisch (führend) und Deutsch; die Texte der Prüfungen gleicht `tools/sync-check-texts.cjs` ins Backend ab (Dossier-PDF) |

Technik: React 19, React Router, TanStack Query, openapi-fetch, MapLibre, Tailwind 4, i18next, Vite. Rechnungen im Browser sind nur Vorschau; maßgeblich ist der Server (L5).

**Rechenkern `packages/domain`** (`@emprise/domain`, HM0/HM1): TypeScript ohne React, DOM und Datenbank; exportiert Quelltext, den Vite, Vitest und Node 24 (Type-Stripping) direkt lesen und esbuild für `engine` bündelt. Geometrie ganzzahlig in 0,1 mm, Offset und Vereinigung mit `clipper2-ts` nach Prüfung jedes Rings (`polygonDefect`, E-HM-27). `evaluate` ist eine reine Funktion von Template, Katalog und Auswahl, ohne Zwischenspeicher:

```text
resolve.ts     Auswahl → wirksamer Wert je Slot und Bauteil, Notizen (Element → Raum → global → Standard)
derive.ts      Schichten, Fassaden- und Wärmekontur, Öffnungen, Dach (HM1: ein Geschoss, Flachdach)
quantities.ts  Mengen mit Herkunft → pricing.ts Preis mit Positionen je Preiseintrag, Aufpreise je Slot
rules.ts       Prüfung der Öffnungen und Katalogregeln (expr.ts) → Status
energy.ts      U-Werte, Fensteranteile · facts.ts Hausbeschreibung für die Prüfung in Python (E-HM-4)
compatibility.ts  Template ↔ Katalog vor dem Veröffentlichen
codes.ts       Codes des Kerns als geschlossene Listen; die Oberfläche übersetzt sie (E-HM-47)
```

Typen an der Grenze kommen aus `src/contract.gen.ts`, erzeugt aus `openapi.json` (E-HM-29). Das Frontend bindet ihn ab HM2 ein (bis dahin liest ein Frontend-Test nur `codes.ts`, ohne Paketabhängigkeit); `spike/roof` enthält den Dach-Prototyp (gewichtetes Skelett, nicht exportiert).

## 6. Anmeldung und Zugriff

| Weg | Wer | Umsetzung |
|---|---|---|
| Sitzung | Büro, Architekten (Analyse) | OIDC (Authentik, lokal Testdienst), PKCE, zweiter Faktor Pflicht (`amr`), keine automatische Kontoanlage; Sitzung als Token-Hash in `staff_session` |
| Projekt-Cookie | Kunden | anonymes Projekt, Token-Hash; Zugangslink per Mail (V) |

- Rollen `architect`, `rules_admin`, `catalog_admin`, `ops`; die drei letzten nur in der Organisation des Betreibers (`operator`).
- Organisationen mit Mitgliedern trennen die Projekte der Architekten. Fremde Büros bleiben gesperrt (`EMPRISE_EXTERNAL_ORGANISATIONS=false`), bis E-A5 geklärt ist.
- Genau eine Zugriffsregel je Route (`public`, `require_roles`, `require_project_access`, `require_owned_project`, `checked_in_handler`), per Test über alle Routen erzwungen (`test_access_policies.py`). `/admin`-Routen mit Projekt nennen den Pfadparameter `project_id`; ein Test verhindert das Umgehen über andere Namen.
- Analyse-Routen verlangen ein Projekt der eigenen Organisation (`require_owned_project`); das Kunden-Cookie reicht dort nicht.

Feature-Flags je Modul (`site_selection`, `rules_simulation`, `envelope_simulation`, `inquiry`, `configurator`, `submission`) schalten die Kundenwege frei: intern (Rolle) → Beta → alle.

## 7. Auslöser für spätere Bausteine

| Baustein | Erst einführen, wenn … |
|---|---|
| S3-Speicher | ein zweiter Rechner Dateien braucht oder ein verwalteter Anbieter kommt; Umstellung nur in `platform/storage.py` |
| Signierte URLs | Downloads die API messbar belasten |
| Redis | mehrere API-Instanzen einen gemeinsamen schnellen Zähler brauchen und PostgreSQL das messbar nicht trägt |
| Weitere Warteschlangen oder Worker | `/api/health/jobs` für `default` trotz Trennung anschlägt |
| Mandantenausbau (API-Schlüssel, Budget je Organisation, Erscheinungsbild; Stand in Git `24d3627`) | E-A5 entschieden ist und fremde Büros zugelassen werden |
| Getrennte Datenbank für Berufs- und Kundendaten | Datenschutzrollen (D6) oder E-A5 eine Trennung verlangen |
