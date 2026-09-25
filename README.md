# Emprise

Hauskonfigurator für Bauinteressenten in Frankreich. Projektbeschreibung, Dokumente und Arbeitsweise: [AGENTS.md](AGENTS.md).

## Aufbau

| Ordner | Inhalt |
|---|---|
| `backend/` | FastAPI-Anwendung, je Fachmodul ein Paket mit reinem `domain/` (Plan 3.2): `app/platform` (P), `app/site` (G1), `app/rules` (G2), `app/envelope` (G3), `app/inquiry` (A), `app/catalog` (H1), `app/configuration` (H2), `app/submission` (V); Adapter externer Dienste in `app/integrations`, Lageplan und DXF in `app/plan`. `app/products.py` sagt, welche Module welches Produkt lädt (AN0) |
| `frontend/` | Vite, React, TypeScript, Tailwind, MapLibre; Web-Container mit Caddy |
| `infra/` | Lokale Datenbankrollen, OIDC-Testdienst; Anforderungen an einen späteren verwalteten Anbieter |
| `deploy/unraid/` | Betrieb bis zur Beta: Emprise-Stack, Authentik, Sicherung, Anleitung |
| `docs/` | [ANNAHMEN.md](docs/ANNAHMEN.md), [BETRIEB.md](docs/BETRIEB.md), Modulpläne `PLAN_<Modul>.md` |
| Wurzel | Spezifikation, Umsetzungsplan, Mockup (siehe AGENTS.md) |

## Lokal starten

Voraussetzungen: Docker Desktop, Node 24 mit Corepack (nur für Frontend-Entwicklung).

```bash
docker compose up --build
```

```bash
docker compose exec api python -m app.cli staff-add ops@emprise.local ops architect
```

Der Worker importiert beim ersten Start selbst das Kataster von Treillières (G1) und den Planstand aus dem Géoportail de l’Urbanisme (G2); Internetzugang nötig, von Hand `cadastre-import` bzw. `plu-import`. Ausgewertet werden die Zonenkapitel nur mit Schlüssel der Claude API (`EMPRISE_ANTHROPIC_API_KEY` in der Shell oder in einer `.env` neben `compose.yaml`; Budget `EMPRISE_RULES_BUDGET_MONTH_USD`, lokal standardmäßig 20 $).

Module intern für Architekten freischalten (Flags je Modul: [BETRIEB.md](docs/BETRIEB.md) Abschnitt 1), vorläufige Rechtstexte für die Anfrage veröffentlichen und erfundene Demo-Daten für den Konfigurator anlegen (Typen `demo_*`, Linien, Optionen, Preise und veröffentlichter Preiskatalog; nie in Produktion):

```bash
for f in site_selection rules_simulation envelope_simulation inquiry configurator; do docker compose exec api python -m app.cli flag-set $f --role architect; done
```

```bash
docker compose exec api python -m app.cli legal-seed
```

```bash
docker compose --profile dev run --rm backend-dev python -m tests.e2e_seed_types
```

Danach als `ops@emprise.local` unter `/buero` anmelden und http://localhost:8080/grundstueck öffnen; Abdeckung und Kosten der Regelwerke unter `/buero/regeln`, Katalogpflege unter `/buero/katalog`.

| Adresse | Zweck |
|---|---|
| http://localhost:8080 | Anwendung |
| http://localhost:8080/buero | Büro; Anmeldung über den lokalen OIDC-Testdienst (Port 8081) als `ops@emprise.local` |
| http://localhost:8000/api/v1/docs | API-Beschreibung |
| http://localhost:8025 | Mailpit (versandte Mails, Bestätigungscodes) |
| http://localhost:9000 | Objektspeicher (SeaweedFS, S3-Anschluss; Zugang `emprise` / `emprise-local-secret`, keine Konsole) |

Das zweite Produkt „Emprise Analyse“ (AN0–AN2: Parzelle als DXF, GeoJSON, PDF oder Zeichnung einbringen, Kanten einordnen, règlement écrit hochladen und Zone wählen) läuft als Aufsatz auf diesen Stack – eigene Datenbank `emprise_analyse`, eigener Bucket, Anwendung http://localhost:8180, API http://localhost:8100:

```bash
docker compose -f compose.analyse.yaml up -d
```

```bash
docker compose -f compose.analyse.yaml exec api-analyse python -m app.cli staff-add ops@emprise.local architect
```

```bash
docker compose -f compose.analyse.yaml exec api-analyse python -m app.cli flag-set site_selection --role architect
```

Frontend mit Hot Reload (API aus Compose):

```bash
cd frontend && corepack pnpm install && corepack pnpm dev
```

## Prüfen

Backend (Lint, Typen, Tests gegen PostGIS und den Objektspeicher; `storage` und `mailpit` müssen laufen, sonst scheitert `test_storage_ops`; rund 3,5 Minuten; in Git-Bash `MSYS_NO_PATHCONV=1` davor):

```bash
docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"
```

Frontend:

```bash
cd frontend && corepack pnpm run typecheck && corepack pnpm run lint && corepack pnpm run test
```

Ende-zu-Ende (laufende Compose-Umgebung, Konto `ops@emprise.local` freigeschaltet, Kataster-Ausschnitt importiert: `docker compose cp backend/tests/fixtures/site api:/tmp/site-fixtures` und `docker compose exec api python -m app.cli cadastre-import --from-dir /tmp/site-fixtures --release e2e --force`; `--force`, weil der Worker parallel den vollständigen Stand laden kann; für G2 zusätzlich `docker compose cp backend/tests api:/tmp/tests` und `docker compose exec -T -e EMPRISE_ANTHROPIC_API_KEY=e2e-ohne-aufruf -e PYTHONPATH=/tmp api python -m tests.e2e_seed_rules`). Unter Windows läuft lokal nur der Kundenpfad (Stolperstellen, Frontend):

```bash
cd frontend && corepack pnpm exec playwright install chromium && corepack pnpm e2e
```

## Änderungen an der API

1. Endpunkt mit genau einer Zugriffsregel aus `app/platform/auth/context.py` versehen (`public`, `require_roles`, `require_project_access`, `checked_in_handler`). Ein Test durchläuft alle Routen (`iter_route_contexts`); neue **öffentliche** Routen in `test_access_policies.py` eintragen, Projekt- und Rollenrouten brauchen keinen Eintrag.
2. `python -m app.cli openapi openapi.json` im Backend-Container, danach im Ordner `frontend` `corepack pnpm run api:types`; `test_committed_openapi_matches_code` prüft die committete Datei. Pydantic-Modellnamen über alle Module eindeutig halten: gleiche Namen (`PlacementIn` in Katalog und H2) benennt OpenAPI um, das bricht die generierten Frontend-Typen. Listenfelder in Antwortmodellen ohne Standardwert lassen, sonst werden sie im Frontend-Typ optional.
   Felder mit Standardwert in einem Anfragekörper (`ModuleIn.kind`, `PackageIn.regulatory`) sind im erzeugten TypeScript-Typ Pflicht; Aufrufer müssen sie senden (Katalogpflege).
3. Datenbankänderungen nur über Alembic: `alembic revision --autogenerate -m "…"`, prüfen, abwärtskompatibel halten. `pytest` enthält `alembic check`. Neue Sequenzen brauchen ein eigenes `GRANT` in der Migration (AF07); `TRUNCATE … RESTART IDENTITY` setzt `inquiry_number_seq` nicht zurück, Tests erwarten keine feste Nummer.
4. Unveränderliche Tabellen: bedingt `forbid_published_modification` (nur bei `status = 'published'`, H1), unbedingt `forbid_modification` (`audit_log`, `legal_text`, `consent`) bzw. `rule_no_update` (`rule`); `inquiry` hat bewusst keinen Trigger.
5. Neue Jobarten: Wer `enqueue` aufruft (auch die CLI), muss `app.registry` importieren, sonst „Unbekannte Jobart“; `app/rules` importiert `app.rules.jobs` lokal in den Funktionen (sonst Importzyklus).
   Ein neuer Router, ein neues Job-Modul oder eine neue periodische Aufgabe gehört in `backend/app/products.py` (je Produkt); sonst läuft sie nirgends oder im falschen Produkt. `test_module_boundaries.py` prüft das und verbietet Importe aus `app.catalog`, `app.configuration`, `app.inquiry` und `app.submission` in `platform`, `integrations`, `site`, `rules`, `envelope` und `plan` (AN0, ANNAHMEN PS01–PS09).
6. Neue oder geänderte Texte von Prüfungen: Das Dossier-PDF (V) benutzt dieselben Sätze wie der Konfigurator. Nach einer Änderung an `configurator.check`, `…reason`, `…orientation`, `…material`, `types.roof`, `…edge`, `…status`, `…compass`, `design.area` oder `site.risks` in `frontend/src/i18n/*.json` einmal `node tools/sync-check-texts.cjs` laufen lassen; `check-texte.test.ts` prüft den Abgleich (`--check` meldet ihn ohne zu schreiben).

## Stolperstellen

Gesammelt aus allen Fassungen von HANDOFF.md; neue dauerhafte Stolperstellen hier eintragen, nicht nur in HANDOFF.

**Windows und Werkzeuge**
- Docker Desktop beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- Der vollständige Backend-Lauf dauert 5–17 Minuten (die PDF-Tests setzen PDFs mit WeasyPrint). Wird die Ausgabe umgeleitet oder läuft der Befehl im Hintergrund, `docker compose run -T` benutzen, sonst fehlt die Ausgabe von `pytest`; Werkzeugaufrufe über 10 Minuten wandern von selbst in den Hintergrund, das Ergebnis steht dann in der Ausgabedatei der Aufgabe.
- Große Dateien mit dem Schreibwerkzeug anlegen, nicht mit einem Heredoc im Bash-Werkzeug: bestimmte Zeichenfolgen brechen dort mit „unexpected EOF“ ab.
- Lokal gibt es kein Python (`python` im Host ist ein Store-Platzhalter, `python3` fehlt): Backend-Befehle immer im Container. `backend-dev` sieht nur `backend/`, nicht `frontend/`, und nutzt die Umgebungsvariablen des lokalen Stacks: Skripte wie `python -m tests.e2e_seed_types` laufen gegen die lokale Datenbank `emprise`; pytest legt eine eigene Testdatenbank an.
- Git-Bash: `MSYS_NO_PATHCONV=1` nur vor `docker …`-Befehlen mit Linux-Pfaden (`docker -v`, `docker exec -w`, `docker compose … run`). Vor `corepack pnpm …` zerbricht die Variable den Pfad zu `corepack.js` („Cannot find module C:\c\Program Files…“); tritt der Fehler trotzdem auf, PowerShell nehmen. `corepack pnpm …` nur im Ordner `frontend` (aus dem Wurzelordner zieht Corepack pnpm 12 und bricht ab).
- Heredocs und `node -e "…"` im Bash-Werkzeug zerbrechen an einer ungeraden Zahl von Apostrophen (französische Zitate), an Backticks und `$$` (ein `$$` in einer Migration wurde zu `$`). Längere Dateien mit dem Write-Werkzeug schreiben oder als Skript im Scratchpad ablegen und mit `node` ausführen; Git-Bash-`/tmp` ist nicht das `C:\tmp` von Node; Skripte nicht `inspect.py` nennen (verdeckt die Standardbibliothek).
- `ruff format` ändert Dateien: danach vor dem Edit-Werkzeug neu lesen. Das `# type: ignore[arg-type]` an `messages=` in `backend/app/integrations/claude.py` ist nötig, auch wenn mypy es einmal als unbenutzt meldet.
- Unsichtbare Zeichen: `backend/app/rules/domain/text.py` enthält in `_TRANSLATE` geschützte Leerzeichen (U+00A0, U+202F) und einen weichen Trennstrich; beim vollständigen Neuschreiben gingen sie verloren – mit `git diff` prüfen.
- Zweites Produkt lokal: `compose.analyse.yaml` hängt am Netz `emprise_default` und an den Images des Hauptstacks. Der Hauptstack muss also laufen (`docker compose up -d`), und nach Codeänderungen erst dort `docker compose build migrate web`, sonst startet der Analyse-Stack den alten Stand. Die Datenbank `emprise_analyse` bleibt beim `down` bestehen; neu aufsetzen mit `docker exec emprise-db-1 psql -U postgres -c "DROP DATABASE emprise_analyse"`. Konto und Flag gelten je Datenbank: `docker compose -f compose.analyse.yaml exec api-analyse python -m app.cli staff-add ops@emprise.local architect` und `… flag-set site_selection --role architect`. Die Dienste heißen `…-analyse`, weil beide Stacks dasselbe Netz benutzen und ein zweiter Dienst `api` den Namen mehrdeutig machte. Beide Produkte teilen lokal außerdem den Cookie-Vorrat (derselbe Host `localhost`, nur andere Ports): Eine Anmeldung im einen verdrängt die im anderen; auf Unraid haben sie eigene Hostnamen.
- Objektspeicher: seit dem 25.09.2026 SeaweedFS statt MinIO (A16), Dienst `storage`, S3 im Netz auf `storage:8333`, auf dem Rechner `localhost:9000`, keine Konsole. Er braucht nach dem Start rund 15 Sekunden, bis der S3-Anschluss antwortet (Gesundheitsprüfung im Compose). Jeder Bucket belegt bis zu sieben Volumes; mit dem festen Standard von acht Plätzen scheiterte jeder Upload, sobald auch der Analyse-Stack seinen Bucket nutzte (`failing to assign a file id`, im API-Log nur ein hängender Upload) – deshalb `-volume.max=0` in `compose.yaml`. Der alte Band `minio-data` bleibt liegen: Dossiers aus der Zeit davor sind im neuen Speicher nicht vorhanden und im Büro über „Dossier neu erzeugen“ wiederherstellbar; aufräumen mit `docker volume rm emprise_minio-data`.
- Parallele Sessions im selben Ordner: Abstimmung per `ListAgents`/`SendMessage`, Dateien vor jeder Änderung neu einlesen. `docker compose up --build` baut den Arbeitsstand samt fremder halbfertiger Dateien; für isolierte Tests ein eigenes Compose-Projekt (`-p <name>` mit Override `ports: !reset []`) oder `git worktree`.
- CI: Der Security-Job baut Caddy mit `xcaddy`; Netzfehler zu `sum.golang.org` sind kein Codefehler, wiederholen mit `gh run rerun <id> --failed`.

**Lokaler Stack**
- Aktualisieren: `docker compose build migrate web`, dann `docker compose up -d migrate api worker web` (`api` und `worker` nutzen das Image `emprise-backend:local`, das der Dienst `migrate` baut; `backend-dev` ist ein eigenes Image `:dev`). Nach neuen Abhängigkeiten zuerst `uv lock` im Container, dann `docker compose --profile dev build backend-dev` (sonst z. B. `No module named 'pypdf'`).
- Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`. Beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen. Authentik: nach der ersten TOTP-Einrichtung neu anmelden (A24); Blueprint-Änderungen wirken nach einem Neustart von `worker`.
- Periodische Importe (Kataster, Planstand) starten beim ersten Worker-Start und belasten externe Dienste. Ein von Hand gestarteter Katasterimport mit anderem Stand scheitert an der Mengenprüfung (`--force` für Testdaten); Testregeln über `tests.e2e_seed_rules`.
- Massentests belasten externe Dienste: Jedes gebildete Grundstück erzeugt einen `site_enrich`-Job mit Aufrufen an Géorisques (3–6 s je Aufruf); nach Messläufen wartende Jobs löschen.
- Rate-Limits (429) bei vielen Projekten, Grundstücken oder Codes derselben IP bzw. Adresse: in `.env` hochsetzen (`EMPRISE_PROJECT_CREATE_LIMIT_PER_HOUR`, `EMPRISE_SITE_WRITE_LIMIT_PER_HOUR`, `inquiry_*`, `configuration_limit_per_minute`; Namen in `backend/app/config.py`).
- Kosten der Claude API: Jeder Aufruf mit Schlüssel kostet; `--force` und „Neu auswerten“ werten vollständig neu aus, ohne `force` werden gespeicherte Teile genutzt; das Budget steht in der Abdeckung. Eine Änderung an Prompt oder Ausgabeschema erzwingt eine neue Auswertung aller Kapitel (RW26) – solche Änderungen vor dem Eintragen des Schlüssels bündeln.

**Backend**
- H2: `backend/app/configuration/domain` ist rein und erhält `EnvelopeInput`/`Envelope` aus G3 (`envelope.service.derived`); Koordinaten dort lokal, in der Datenbank Lambert-93. Testgrundstück 20 × 31 m (Straße Norden) über `tests/configuration_support.py`.
- Die Tabelle `rule` ist unveränderlich: Tests ändern Regeln nur über `rules_service.set_override`. Fixtures des Baurahmen-Tests (`project`: Grundstück AD 65, Zone Uh) übernimmt `test_configuration.py` per Zuweisung (`project = _envelope.project`), nicht per Import (ruff F811).
- Tests G2: `FakeExtractor` bildet aus einer Auswertungsantwort die Gegenprüfung; `[uh_output(), uh_output(footprint=0.3)]` heißt „Gegenprüfung liest bei der Grundfläche anders“. Das Original-PDF (6,8 MB) liegt nicht im Repository; `backend/tests/rules_support.py` setzt aus der Textschicht ein PDF, Positionen im Kapitel-PDF sind im Ausschnitt und im Original gleich.
- G3: `envelope-check` legt nichts an (Transaktion wird zurückgerollt) und ist die schnellste Gegenprobe nach Änderungen an G1, G2 oder den Schranken. Der Baurahmen wird nie gespeichert; ändern sich die Eingaben, ändern sich `input_hash` und der Steckbrief.
- Weg E: Geometrie ohne geografischen Bezug (technisch SRID 2154), nie ohne Prüfung von `site.origin` als echte Lage behandeln; Schließung und Rundung in G27.
- WeasyPrint braucht Pango und DejaVu im Image (`backend/Dockerfile`, Stufe `base`); die Warnung zu HarfBuzz-Subset ist unkritisch.
- H1: Der Preiskatalog ist ein Entwurf je Region (`default`), wird bei Bedarf automatisch angelegt (erster Typ-Import, Linie oder Option, `GET .../price-catalog/draft`) und mit `POST /admin/catalog/price-catalog/publish` als Ganzes veröffentlicht.

**Frontend**
- `unwrap` scheitert an `204` ohne Rumpf (`useDeleteProject` umgeht das); Endpunkte mit `202` geben deshalb einen kleinen Rumpf zurück (`/access/request`).
- Vitest läuft über Vite: `new URL(…, import.meta.url)` wird zum Asset-Import und Pfade außerhalb von `frontend` werden abgelehnt (`Denied ID`). Dateien des Backends im Test über `resolve(process.cwd(), "../backend/…")` lesen (`check-texte.test.ts`).
- i18n ist verschachtelt (`inquiry.contact.name`), die Backend-Übersetzungen sind flach (`problem.…`) mit `{param}` statt `{{param}}`.
- Datei-Uploads: `openapi-fetch` mit `bodySerializer: () => formData` und Platzhalter-Rumpf (`frontend/src/api/catalog.ts`); Content-Type nicht setzen.
- React-Hooks-Lint (Version 7): keine Ref-Zugriffe beim Rendern, keine `setState`-Effekte; `Implantation` baut deshalb mit `key={revision}` neu auf.
- E2E unter Windows: Chromium von Playwright löst `oidc.localhost` nicht auf; Tests mit Büro-Anmeldung laufen nur in der CI. Lokal nur der Kundenpfad: Flags per `flag-set … --all`, `corepack pnpm exec playwright test -g Kunde`, danach wieder `--role architect`.

**Browserprüfung**
- Geometrie von Nebenbauten und Lage immer am echten, schiefen Grundstück AD 65 ansehen (Konfigurator, Schritt Vorentwurf): Die Rechteck-Tests (20 × 31 m) fanden weder den Carport hinter dem Haus mit Zufahrt durch das Haus noch die Überlappung von Carport und Terrasse (Plan H3 10.1a).
- Login `http://localhost:8080/api/v1/auth/staff/login` (Mock-OIDC ohne Eingabe, `ops@emprise.local` mit `architect` und `ops`, landet unter `/buero`); wer im selben Browser als `architect` angemeldet ist, sieht auch auf `/grundstueck` die Flags dieser Rolle. Danach `/grundstueck`: „Saisir la référence cadastrale“ (Section `AD`, Nummer `65`), „Valider le terrain“, „Choisir ma maison“.
- `left_click_drag` löst das Ziehen aus. Dateien in Formulare per `javascript_tool` (`DataTransfer` auf dem Dateifeld); die Daten über die Web-Ebene bereitstellen (`docker cp` nach `emprise-web-1:/srv/`, dann gleicher Ursprung; fremde Ursprünge blockt die CSP). `window.confirm` wird abgebrochen: vorher `window.confirm = () => true`. Ein Klick auf die App-Sprache wechselt sie für die ganze Sitzung.
- Screenshots scheitern mit „page did not finish rendering“, wenn das Fenster im Hintergrund liegt; `get_page_text`, `find` und `javascript_tool` arbeiten weiter. Screenshots von `localhost` funktionieren, von `file://` nicht; Lagepläne zur Prüfung mit matplotlib im Container als PNG erzeugen und ansehen.
- Modul V: Der Bestätigungscode steht in Mailpit (`curl -s "http://localhost:8025/api/v1/search?query=to:<adresse>"`, dann `/api/v1/message/<id>`); der Zugangslink der Kundenmail endet auf `/zugang#t=<Token>`. Dateien einer Fassung liegen im Objektspeicher: `docker compose exec api python -c "…storage.get_bytes(f['storage_key'])…"` und `docker cp`; PDFs lassen sich mit dem Lesewerkzeug ansehen, DXF mit `ezdxf` (matplotlib fehlt im Image).
- Mockup `emprise.html` (`file:///…`): Bedienung und Auslesen per `find` und `javascript_tool`; Typkarten sind keine `<button>`, sondern Elemente mit `role=button`; die Kontaktprüfung meldet Fehler erst beim Klick auf „Vorentwurf zur Prüfung übergeben“.
