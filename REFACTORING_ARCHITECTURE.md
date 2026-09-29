# Refactoring: Architektur heute und Zielbild

> **Stand:** 29.09.2026. Abschnitte 1–4 zeigen die **tatsächliche** Architektur aus dem Code, Abschnitte 5–7 das Zielbild (zweite Fassung nach den Entscheidungen vom 29.09.2026: eine Anwendung). Befunde `B-…` stehen in [REFACTORING_ANALYSIS.md](REFACTORING_ANALYSIS.md), Schritte `REF-…` in [REFACTORING_PLAN.md](REFACTORING_PLAN.md).

## 1. Laufzeitarchitektur heute (je Produkt-Instanz)

```text
                         Browser
                            │  HTTPS (TLS endet am Reverse Proxy auf Unraid)
                            ▼
              ┌──────────────────────────────┐
              │ web: Caddy (selbst gebaut)   │  statische SPA (index.html | analyse.html über SPA_INDEX),
              │                              │  CSP, /api/* → api:8000
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐        ┌─────────────────────────────┐
              │ api: FastAPI (uvicorn)       │◄──────►│ Authentik (OIDC, MFA)       │  nur Büro-Anmeldung
              │ Router je Produkt (products) │        └─────────────────────────────┘
              │ Auth: Sitzung | Projekt-Cookie│
              │       | API-Schlüssel (AN6)  │
              └──┬─────────┬──────────┬──────┘
                 │         │          │ HTTP (Géoplateforme, Géorisques, IGN, GPU) für Suche und Karte
                 │         │          ▼
                 │         │   Behördendienste
                 │         ▼
                 │   ┌───────────────┐
                 │   │ storage:      │ SeaweedFS, S3, Bucket mit Versionierung
                 │   │ SeaweedFS     │◄───────────────┐
                 │   └───────────────┘                │
                 ▼                                    │
   ┌───────────────────────────────┐                  │
   │ db: PostgreSQL 16 + PostGIS   │                  │
   │  Fachdaten, job, Sitzungen,   │◄──────┐          │
   │  Rate-Limits, Kataster        │       │          │
   └───────────────────────────────┘       │          │
                 ▲                          │          │
                 │ shared-Netz              │          │
   ┌─────────────┴─────────────┐   ┌───────┴──────────┴───────┐      ┌────────────────────┐
   │ shared-db (eigener Stack) │◄──┤ worker: gleicher Code,   ├─────►│ OpenRouter (LLM)   │
   │ Modellwahl, Referenzlisten│   │ EINE Warteschlange,      │      └────────────────────┘
   └───────────────────────────┘   │ EIN Prozess (B-10)       ├─────► SMTP (Mail)
                                   │ + Tesseract (OCR)        ├─────► Behördendienste (Import, Anreicherung)
                                   └──────────────────────────┘
   migrate: Einmal-Job (alembic upgrade, shared-migrate, storage-init)
   backup:  pg_dump täglich (Dateien über Unraid-Plugin „Appdata Backup“)
```

## 2. Auslieferung heute

### 2.1 Unraid (vorbereitet, noch nicht in Betrieb)

```text
Unraid-Host
├── Reverse Proxy (vorhanden)  building-configurator.aslani.work · emprise-analyse.aslani.work · auth.aslani.work
├── Stack „emprise“            db · storage · migrate · api · worker · web · backup          (7)
├── Stack „emprise-analyse“    db · storage · migrate · api · worker · web · backup          (7)
├── Stack „emprise-shared“     shared-db · backup                                            (2)
└── Stack „authentik“          postgresql · server · worker                                   (3)
                                                                                         Σ 19 Container
Netze: intern (je Produkt), extern (web), emprise-shared (migrate/api/worker beider Produkte ↔ shared-db)
Reihenfolge: ./deploy.sh shared → ./deploy.sh → ./deploy.sh analyse
```

### 2.2 Lokal

```text
compose.yaml (Projekt „emprise“)          db · storage · mailpit · oidc · db-init-shared · migrate · api · worker · web
                                          [+ backend-dev im Profil dev]
compose.analyse.yaml (Projekt „emprise-analyse“)
                                          db-init-analyse · migrate-analyse · api-analyse · worker-analyse · web-analyse
                                          hängt am externen Netz emprise_default und an den Images des Hauptstacks (B-32)
compose.e2e.yaml                          setzt fremde Dienste auf 127.0.0.1:9 (A28)
Datenbankserver db: emprise · emprise_analyse · emprise_shared · emprise_probe
```

### 2.3 CI

```text
backend   PostGIS-Dienst + SeaweedFS-Container + Tesseract → ruff, mypy, pytest (776)
frontend  Typen aus OpenAPI prüfen, Lint, tsc, Vitest (243), Build
e2e       compose.yaml + compose.e2e.yaml, Playwright
security  gitleaks, Trivy (Backend, Web mit xcaddy-Caddy)
```

## 3. Domänengrenzen

### 3.1 Module und Produkte

```text
                    ┌──────────────────────── Kern (beide Produkte) ─────────────────────────┐
                    │ platform    DB, Auth, Jobs, Flags, Audit, Rate-Limit, Speicher,         │
                    │             Organisationen, Recht, Mail                                  │
                    │ integrations Kataster, IGN, Géorisques, GPU, OpenRouter, SMTP            │
                    │ site  (G1)  Grundstück: Kataster · Skizze · Upload · Scan · Lage · Kanten│
                    │ rules (G2)  Planstand · Upload · OCR · LLM-Auswertung · Schranken ·     │
                    │             Korrekturen · Referenzlisten                                 │
                    │ envelope (G3) Baurahmen (rein) · Steckbrief                              │
                    │ plan        Lageplan-Geometrie · DXF                                     │
                    └─────────────────────────────────────────────────────────────────────────┘
   Produkt „configurator“: catalog (H1) · configuration (H2/H3) · inquiry (A) · submission (V)
   Produkt „analyse“:      analysis (AN3–AN5)
```

Die Grenze „Kern importiert kein Produktmodul“ prüft `backend/tests/unit/test_module_boundaries.py`.

### 3.2 Abhängigkeiten (tatsächlich)

```text
analysis ─────────────┐
                      ▼
submission ⇄ inquiry → configuration → catalog
     │          │          │             │
     └──────────┴──────────┼─────────────┤
                           ▼             ▼
                        envelope ───► rules ───► site ───► integrations ⇄ platform
                           │            │                        │
                           └────────────┴──── plan (nur analysis, submission)
```

Zyklen: `inquiry ⇄ submission` (B-01), `platform ⇄ integrations` (Logging/SMTP, harmlos). `integrations/openrouter.py → rules.domain.extraction` (B-02).

### 3.3 Schichten je Modul

```text
api.py        FastAPI-Router, genau eine Zugriffsregel je Route, Rate-Limit, Feature-Flag
service.py    Anwendungsfälle, Transaktionen, Aufrufe anderer Module nur über deren service
domain/       rein: keine DB, kein Netz, kein FastAPI → deterministisch, mit hypothesis getestet
models.py     SQLAlchemy 2 (GeoAlchemy2 für Geometrien in Lambert-93)
schemas.py    Pydantic → openapi.json → frontend/src/api/schema.d.ts
jobs.py       @job-Handler; periodische Aufgaben je Produkt in products.py
```

## 4. Datenflüsse heute

### 4.1 Anfrage (lesend oder schreibend)

```text
Browser → web → api: RequestContext (Request-ID, Logs) → CSRF → Sitzung/Cookie/Schlüssel auflösen
       → Zugriffsregel → Feature-Flag → Rate-Limit (eigene Transaktion) → service → domain
       → db.commit() im Endpunkt → Antwort (RFC 9457 bei Fehler)
```

### 4.2 Job

```text
service: enqueue(session, kind) in derselben Transaktion wie die Fachänderung
worker:  alle 30 s Wartung (periodische Jobs einplanen, verwaiste zurückstellen)
         claim (UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1))
         Handler mit SIGALRM-Zeitlimit → complete | fail (Backoff 30 s · 2^n, max. 1 h)
```

### 4.3 Regeln bis zur Berechnung

```text
GPU-Import (Konfigurator) ─┐                                   ┌─ LLM: Auswertung, Gegenprüfung, Nachsuche
Upload (Analyse) ──────────┼→ source_file/source_page → Kapitel ┤
OCR (nur Upload, Scan) ────┘                                   └─ Schranken (rein) → rule_set_version
                                                                  → Korrekturen (Büro, Projekt)
                                                                  → envelope_input → derive_envelope (rein)
                                                                  → analysis / configuration (rein)
```

### 4.4 Dateien

```text
put_bytes/get_bytes/delete (4 Funktionen) → S3 (SeaweedFS)
Downloads immer über die API (Zugriffsregel), nie per signierter URL
Schlüssel: rules/<partition>/<doc>/<sha256>.pdf · catalog/<slug>/… · dossiers/<project>/<submission>/… ·
           envelope-sheets/… · organisations/<id>/logo-… · Berichte der Analyse
```

## 5. Zielarchitektur

> Zweite Fassung nach den Entscheidungen des Nutzers vom 29.09.2026: **eine** Anwendung für Konfigurator und Analyse (die erste Fassung hielt zwei Instanzen).

### 5.1 Prüfung des Zielbilds aus dem Auftrag

| Bestandteil | Heute | Ziel | Begründung |
|---|---|---|---|
| React / TypeScript | ein Paket, zwei Einstiege | ein Einstieg, zwei Router (`/`, `/analyse`) | eine Anwendung, ein Build |
| FastAPI | zwei Instanzen je Produkt | eine Instanz mit allen Routern | Produktprofil wirkt nur an wenigen Stellen (B-73) |
| PostgreSQL + PostGIS | 3 Datenbanken, 4 Server auf Unraid | eine Datenbank | Entscheidung des Nutzers |
| Worker | ein Prozess je Produkt | `worker` (default) + `worker-long` (long) | B-10; Abweichung vom Zielbild „ein Worker“ |
| Dateien | SeaweedFS (S3) | Verzeichnis `/data/files` | ein Host, vier Funktionen |
| LLM | OpenRouter | unverändert | Grenze eingehalten, per Test gesichert |
| Reverse Proxy | vorhandener Proxy + Caddy im Web-Container | unverändert | Caddy liefert die SPA und leitet `/api` weiter |
| Authentik | eigener Stack, zwei Anwendungen | eigener Stack, eine Anwendung | D4, MFA |
| Redis, Celery | gibt es nicht | – | – |

### 5.2 Zielbild

```text
                          Browser
                             │  building-configurator.aslani.work
                             ▼
          web (Caddy: SPA mit Bereichen / · /buero · /analyse, /api-Weiterleitung)
                             │
                             ▼
                       api (FastAPI) ─────────────► Authentik (OIDC, eine Anwendung)
                             │
        ┌────────────────────┼─────────────────────────────┐
        ▼                    ▼                             ▼
  PostgreSQL + PostGIS   /data/files (Volume)     worker (Queue default)  worker-long (Queue long)
  eine Datenbank: Fach-  api, worker, backup      Mail, PDFs, Anreiche-   Regelauswertung, Lesen,
  daten, Jobs, Modell-                            rung, Wartung           OCR, PLU-/Katasterimport
  wahl, Referenzlisten                                  │                        │
                                                        ▼                        ▼
                                                      SMTP          OpenRouter (LLM), Behördendienste
```

### 5.3 Zielauslieferung Unraid

```text
Unraid-Host
├── Reverse Proxy (vorhanden)   building-configurator.aslani.work · auth.aslani.work
│                               (emprise-analyse.aslani.work → Weiterleitung auf /analyse)
├── Stack „emprise“             db · migrate · api · worker · worker-long · web · backup   (7, davon 1 Einmal-Job)
└── Stack „authentik“           postgresql · server · worker                               (3)
                                                                                      Σ 10 Container
entfällt: Stack emprise-analyse (7), Stack emprise-shared (2), storage, Netz emprise-shared,
          Reihenfolge „shared zuerst“, zweite Authentik-Anwendung
Volumes:  ${APPDATA_DIR}/postgres, ${APPDATA_DIR}/files
Sicherung: pg_dump täglich + Dateiverzeichnis über Appdata Backup
```

### 5.4 Ziel lokal

```text
compose.yaml (Projekt „emprise“)
  immer:      db · mailpit · oidc · migrate · api · worker · web          (7)
  Profil dev: backend-dev
  Volumes:    db-data · files-data
compose.e2e.yaml   Aufsatz für die E2E-Tests (fremde Dienste auf 127.0.0.1:9)
Start: docker compose up -d   ·   Anwendung http://localhost:8080, Analyse http://localhost:8080/analyse
```

### 5.5 Was bleibt, wie es ist

| Bestandteil | Grund |
|---|---|
| Modularer Monolith mit `api → service → domain` | flach, ohne Repository-Schicht |
| Ordner `platform` (≙ infrastructure), `integrations` (≙ Adapter, LLM), `<modul>/domain` (≙ calculations) | entspricht dem Zielbild des Auftrags unter anderen Namen |
| Grenze „Kern importiert keine Konfigurator-Module“ | bleibt als Test, auch in einer Anwendung nützlich |
| PostgreSQL-Queue | ist bereits die einfache Lösung |
| OpenAPI → TypeScript | verhindert doppelte Typen |
| Auth mit Sitzung und Projekt-Cookie, Zugriffsregel je Route | sicherheitskritisch; API-Schlüssel entfallen (AN6-Rückbau) |
| Organisationen mit Mitgliedern | Projektzugriff im Büro; fremde Büros gesperrt bis E-A5 |
| LLM-Kette mit drei Läufen und Schranken | fachliche Anforderung |

## 6. Architekturprinzip: LLM → Extraktion → strukturierte Daten → deterministische Logik

```text
OpenRouter (LLM)                  integrations/openrouter.py        erzwungener Funktionsaufruf, nur Planunterlagen
  ↓
Extraktion                        rules/extract.py                  Läufe, Kosten, Wiederverwendung
  ↓
Strukturierte Daten (Kandidaten)  rules/domain/extraction.py        ExtractedRule, parse_output
  ↓
Schranken (deterministisch)       rules/domain/assess.py, kinds.py  Zitat, Zahlen, Sektor, Parameter, Gegenprüfung
  ↓
Validiertes Regelwerk             rule_set_version + rule           unveränderlich, mit Status und Fundstelle
  ↓
Deterministische Fachlogik        envelope/domain, analysis/domain, configuration/domain
  ↓
Ergebnis                          Simulation (D11); Büro prüft nach Kontakt; Auslegung offen (E-VA-5)
```

**Heute eingehalten**, aber nicht geprüft und transitiv verletzt: `envelope/service` und `analysis/service` laden über `rules/service` → `rules/extract` den Adapter samt `openai` (B-68). Absicherung in Plan S10/S11: Schnittstelle nach `rules/domain/extraction.py`, leichtes Modul für `input_hash`, Test in einem Unterprozess, dass reine Lesepfade `openai` nicht laden.

## 7. Auslöser für spätere Erweiterungen

| Baustein | Erst einführen, wenn … |
|---|---|
| S3-Speicher | ein zweiter Rechner Dateien braucht oder ein verwalteter Anbieter kommt (infra/README); Umstellung in `platform/storage.py` |
| Signierte URLs | Downloads die API messbar belasten |
| Redis | mehrere API-Instanzen einen gemeinsamen schnellen Cache oder Rate-Limit brauchen und PostgreSQL das messbar nicht trägt |
| Weitere Worker/Warteschlangen | `/api/health/jobs` für `default` trotz Trennung anschlägt |
| Ausbau Mandanten (API-Schlüssel, Budget je Organisation, Erscheinungsbild zurück aus Git `24d3627`) | E-A5 entschieden und fremde Büros zugelassen |
| Getrennte Datenbank für Berufs- und Kundendaten | Datenschutzrollen (D6) oder E-A5 eine Trennung verlangen |
