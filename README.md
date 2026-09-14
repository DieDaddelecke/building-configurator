# Emprise

Hauskonfigurator für Bauinteressenten in Frankreich. Projektbeschreibung, Dokumente und Arbeitsweise: [AGENTS.md](AGENTS.md).

## Aufbau

| Ordner | Inhalt |
|---|---|
| `backend/` | FastAPI-Anwendung: `app/platform` (Modul P), später je Fachmodul ein Paket (Plan 3.2) |
| `frontend/` | Vite, React, TypeScript, Tailwind; Web-Container mit Caddy |
| `infra/` | Lokale Datenbankrollen, OIDC-Testdienst; Anforderungen an einen späteren verwalteten Anbieter |
| `deploy/unraid/` | Betrieb bis zur Beta: Emprise-Stack, Authentik, Sicherung, Anleitung |
| `docs/` | [ANNAHMEN.md](docs/ANNAHMEN.md), [BETRIEB.md](docs/BETRIEB.md) |
| Wurzel | Spezifikation, Umsetzungsplan, Mockup (siehe AGENTS.md) |

## Lokal starten

Voraussetzungen: Docker Desktop, Node 24 mit Corepack (nur für Frontend-Entwicklung).

```bash
docker compose up --build
```

```bash
docker compose exec api python -m app.cli staff-add ops@emprise.local ops
```

| Adresse | Zweck |
|---|---|
| http://localhost:8080 | Anwendung |
| http://localhost:8080/buero | Büro; Anmeldung über den lokalen OIDC-Testdienst als `ops@emprise.local` |
| http://localhost:8000/api/v1/docs | API-Beschreibung |
| http://localhost:8025 | Mailpit (versandte Mails) |
| http://localhost:9001 | MinIO-Konsole (`emprise` / `emprise-local-secret`) |

Frontend mit Hot Reload (API aus Compose):

```bash
cd frontend && corepack pnpm install && corepack pnpm dev
```

## Prüfen

Backend (Lint, Typen, Tests gegen PostGIS und MinIO):

```bash
docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"
```

Frontend:

```bash
cd frontend && corepack pnpm lint && corepack pnpm typecheck && corepack pnpm test
```

Ende-zu-Ende (laufende Compose-Umgebung, Konto `ops@emprise.local` freigeschaltet):

```bash
cd frontend && corepack pnpm exec playwright install chromium && corepack pnpm e2e
```

## Änderungen an der API

1. Endpunkt mit genau einer Zugriffsregel aus `app/platform/auth/context.py` versehen (`public`, `require_roles`, `require_project_access`, `checked_in_handler`). Ein Test prüft das für alle Routen.
2. `python -m app.cli openapi openapi.json` im Backend-Container, danach im Frontend `pnpm api:types`.
3. Datenbankänderungen nur über Alembic: `alembic revision --autogenerate -m "…"`, prüfen, abwärtskompatibel halten. `pytest` enthält `alembic check`.
