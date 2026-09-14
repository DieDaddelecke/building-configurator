# Änderungsprotokoll

Neueste Einträge zuerst. Ein Eintrag je Session, geschrieben von `/handoff`. Der aktuelle Stand steht in [HANDOFF.md](HANDOFF.md).

---

## 14.09.2026 – G1 Grundstück (Session `building-configurator-a7`, parallel zu R0/Unraid)

**Neu**
- `backend/app/site/` – Modul G1: Fachlogik (`domain/`: Grundstück bilden, Kanten zerlegen und einordnen mit Nachbarparzellen und BD-TOPO-Straßenachsen, Gelände), Modelle, Import je Gemeinde mit Plausibilitätsprüfung (`cadastre_import.py`), Anwendungsfälle, API, Jobs `site_enrich`, `cadastre_import` (wöchentlich), `site_housekeeping`.
- `backend/app/integrations/` – `http.py`, `geoplateforme.py` (Geokodierung, Höhen), `georisques.py`, `etalab_cadastre.py`, `ign_bdtopo.py`.
- `backend/migrations/versions/0002_site.py` – `ref_*`, `site`, `parcel`, `site_edge`, `terrain`, `site_risk`, `geocode_cache`.
- `backend/tests/` – `unit/test_site_domain.py`, `unit/test_site_integrations.py`, `integration/test_site.py`, `fixtures/site/` (echte Daten Treillières mit README).
- `frontend/src/components/karte/Katasterkarte.tsx` (MapLibre 6), `frontend/src/site/` (Lageplan, Kantenliste, Parzellenwahl, Prüfansicht), `frontend/src/api/site.ts`, `frontend/src/pages/grundstueck/`, `frontend/src/pages/buero/Grundstuecke.tsx`, Tests; `frontend/e2e/site.spec.ts`.

**Geändert**
- `backend/app/cli.py` – Befehle `cadastre-import`, `flag-set`.
- `backend/app/config.py`, `main.py`, `registry.py`, `platform/locales/*.json`, `platform/logging.py` (HTTP-Bibliotheken ohne URL-Logs), `migrations/env.py`, `pyproject.toml`/`uv.lock` (shapely, hypothesis), `openapi.json`, `tests/conftest.py`, `tests/integration/test_access_policies.py`, `test_flags_legal_audit.py`.
- `frontend/` – `App.tsx`, `Start.tsx` (Einstieg hinter Flag), `BueroLayout.tsx`, `BueroStart.tsx`, `PlanSvg.tsx`, `index.css` (`.field`), `i18n/*.json`, `vite.config.ts` (`EMPRISE_API_URL`), `package.json`/`pnpm-lock.yaml` (maplibre-gl, @types/geojson), `schema.d.ts`, `Caddyfile` (CSP: `data.geopf.fr`, `worker-src 'self'`).
- `.github/workflows/ci.yml` – E2E importiert Kataster-Ausschnitt.
- `docs/ANNAHMEN.md` – Abschnitt G1 (G01–G21). `docs/BETRIEB.md` – Abschnitt 8. `README.md` – G1 lokal starten, E2E-Voraussetzung. `deploy/unraid/README.md` – `flag-set` in Abschnitt 9.
- `UMSETZUNGSPLAN.md` – 3.3 Abnahme ohne Testmenge, 3.6 Grenzprüfung bei Anfrage, 8 Testmenge gestrichen, 9 D1 und D2 entschieden.
- `AGENTS.md` – Stand G1 und Entscheidungen.

**Entschieden**
- D1 – Bis zur Beta nur Treillières (44209).
- D2 – G1 intern für die Rolle `architect` freigeschaltet; Beta und öffentlich offen.
- Einordnung von Lotissement-Straßen (eigene Parzelle = Straße), Eck- und Pfeifenstielgrundstücken bestätigt.
- Keine Abnahme-Testmenge von 40 Grundstücken; der Architekt prüft die Grenzen erst beim Eingang einer Anfrage (Modul A).
- Commits getrennt nach R0-Nacharbeiten (`c606387`) und G1 (`cc48386`).
- Repository: privates GitHub-Repo `DieDaddelecke/building-configurator` als `origin`, `main` gepusht.
- Erster CI-Lauf: Backend (111 Tests), Frontend und E2E grün nach Korrektur von `ci.yml` (pnpm-Version, Trivy-Action per SHA). Trivy fand HIGH-Lücken in den Basis-Images → `backend/Dockerfile` mit Debian-Updates, `frontend/Dockerfile` mit selbst gebautem Caddy (ANNAHMEN A27). Danach alle CI-Jobs grün.

**Ohne Dateiänderung**
- Externe Dienste am 14.09.2026 live geprüft: Géoplateforme (Geokodierung, Höhen, WMTS, WFS BD TOPO), Etalab je Gemeinde (Stand 2026-06-01), Géorisques v1 ohne Token, v2 mit Token (ANNAHMEN G-Einleitung, G12, G13).
- Echte Daten: Regel ohne Straßenachsen versagt bei Lotissements; Stichprobe 300 Parzellen: Eckgrundstücke 38 % → 17 % nach neuer Regel, zwei Zeichnungsraster durchgesehen (G04, G05).
- Leistung lokal: Parzelle am Punkt p95 17 ms, Grundstück bilden p95 98 ms, Import Treillières 12 s (G20).
- Browsertest und E2E fanden Fehler: Parzellenwahl verlor Eingaben bei Projektanlage, leere Umgebungsringe im Lageplan, Koordinaten in HTTP-Logs; behoben. Selbstprüfung: Doppelklick beim ersten Grundstück, unbegrenzter Adress-Cache, verrauschte Büro-Prüfliste; behoben.
- Lizenzen und Abfragegrenzen der Géoplateforme (G13, G17).
- Lokaler Stack `emprise` mit G1 neu gebaut, Treillières importiert, `site_selection` für `architect` gesetzt, im Browser geprüft.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`.

**Memory:** `feedback-pruefung-erst-bei-anfrage` angelegt.

**Hand-off:** HANDOFF.md auf Basis der Fassung der R0-Session neu geschrieben; erledigt aus der vorigen Fassung: D1, G1 abschließen, Prüfung der Kartendienst-Bedingungen (HANDOFF 4.4 Punkt 2).

---

## 14.09.2026 – R0 Plattform, Betrieb auf Unraid mit Authentik

**Neu**
- Git-Repository (`main`), erster Commit `1f4b646` mit allen Dokumenten und R0.
- `backend/` – FastAPI-Plattform (Modul P): OIDC-Anmeldung Büro mit MFA-Prüfung, Rollen, Projekt-Cookie, CSRF, Zugriffsregel je Route (per Test erzwungen), Audit-Log und Rechtstexte unveränderlich, Job-Queue in PostgreSQL, Mail, S3, Feature-Flags, Rate-Limits, Fehler nach RFC 9457 auf fr/de, Gesundheitsprüfungen, CLI; Migration `0001`; 50 Tests.
- `frontend/` – Vite, React, TypeScript, Tailwind, i18n fr/de; Gestaltung, Planblatt und Maßketten aus dem Mockup; Startseite, Büro-Rahmen `/buero`; Caddy-Web-Container mit CSP; 7 Unit-Tests, 3 Playwright-Tests.
- `compose.yaml` – lokale Umgebung mit PostGIS, MinIO, Mailpit, OIDC-Testdienst, migrate, api, worker, web.
- `.github/workflows/ci.yml`, `renovate.json` – CI und Abhängigkeitspflege (CI noch nie gelaufen).
- `README.md`, `docs/ANNAHMEN.md` (A1–A26), `docs/BETRIEB.md`, `infra/README.md`, `infra/local/*`.
- `deploy/unraid/` – Emprise-Stack für Unraid (PostGIS, SeaweedFS, migrate, api, worker, web, backup), `deploy.sh` mit Rückrollen, Authentik-Stack mit Blueprint, Anleitung.

**Geändert**
- `UMSETZUNGSPLAN.md` – Status im Kopf; Kapitel 9: D3 und D4 entschieden.
- `AGENTS.md` – Stand, Dokumententabelle, Hinweis zur Geltung des Plans für beauftragte Module.
- `.claude/skills/handoff/SKILL.md` – Ort der Annahmen `docs/ANNAHMEN.md`.
- Nach dem Commit, noch nicht committet: `backend/app/cli.py` (`storage-init`), `compose.yaml`, `ci.yml`, `frontend/Caddyfile` (trusted_proxies), `frontend/src/i18n/*.json` (Hinweis nach MFA-Einrichtung), `.gitignore`, `README.md`, Dokumente oben.

**Entschieden**
- D3 – Hosting bis zur Beta selbst betrieben auf Unraid; vor öffentlichem R1 neu entscheiden.
- D4 – Eigener Identitätsdienst, kein Microsoft/Google; Authentik.
- R0 und G1 aus dem Plan beauftragt; der Plan als Ganzes bleibt Vorschlag.
- Vorläufige Adresse `https://building-configurator.aslani.work`; Reverse Proxy auf Unraid vorhanden.

**Ohne Dateiänderung**
- Procrastinate: transaktionale Job-Anlage mit psycopg 3 nicht belegbar → eigene Queue (ANNAHMEN A2).
- Authentik: `amr: mfa` nur mit bereits eingerichtetem Gerät; 2026 verlangt `grant_types`; Passkey ohne Passwort = `user` (ANNAHMEN A23–A25).
- SeaweedFS 3.97: Bucket, Versionierung, signierte URLs geprüft (A22).
- Selbstprüfung: `/ready` hätte nach Rückrollen 503 gemeldet → `migration_state` eingeführt (BETRIEB 2). Sicherung enthielt `spatial_ref_sys` → ausgeschlossen, Wiederherstellung fehlerfrei (BETRIEB 6).
- DNS 14.09.2026: `building-configurator.aslani.work` existiert noch nicht; `aslani.work` liegt bei Cloudflare (HANDOFF 2 und 3).
- Parallele Session `building-configurator-a7` setzt G1 um; Dateien abgestimmt, Stand in HANDOFF 1.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`.

**Memory:** `project-hosting-unraid` angelegt (D3/D4, keine Microsoft-/Google-Dienste, Cloudflare-Hinweis).

**Hand-off:** `/handoff` erstmals als Befehl aufgerufen und ausgeführt (Punkt aus HANDOFF 4.2 erledigt).

---

## 13.09.2026 – Prüfung Spezifikation, Umsetzungsplan, Session-Übergabe

**Neu**
- `UMSETZUNGSPLAN.md` – Module P, G1–G3, A, H1–H3, V, X1–X5; Releases R0–R2; technische Umsetzung je Modul; IT-Infrastruktur; 20 Abweichungen von der Spezifikation; Entscheidungen D1–D10; Prüfprotokoll mit 20 behobenen Logikfehlern und 15 Alternativen. Status: Vorschlag.
- `HANDOFF.md` – Momentaufnahme für die nächste Session.
- `AENDERUNGEN.md` – dieses Protokoll.
- `.claude/skills/handoff/SKILL.md` – Befehl `/handoff`.

**Geändert**
- `AGENTS.md` – Stand um Umsetzungsplan ergänzt; Dokumententabelle um `UMSETZUNGSPLAN.md`, `HANDOFF.md`, `AENDERUNGEN.md`.
- `CLAUDE.md` – Ablauf zu Beginn jeder Session und Verweis auf `/handoff`.

**Ohne Dateiänderung**
- Rückmeldung zur Spezifikation: Umfang, Reihenfolge, 12 Logikfehler, Effizienzvorschläge. Offene Punkte stehen in `HANDOFF.md` 4.1.
- Funktionsprüfung des Mockups im Browser: Durchlauf Ligne/Confort/Lärche/Terrasse ergibt „ca. 384.000 – 418.000 €“, Schnellstellung straßennah 5/18/4/4 m, Begrenzung und Formularprüfung funktionieren.
- Erklärung, wie Kataster- und Bebauungspläne in Grundstück, Regelwerk, bebaubare Fläche und Oberfläche übergehen.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `tools/build-mockup.cjs`.

**Memory:** Erste Einträge angelegt (Sprache und Schwerpunkte des Nutzers, Selbstprüfung von Dokumenten, schrittweise produktive Umsetzung).

**Hand-off:** Am Sessionende erstmals ausgeführt, von Hand nach `SKILL.md`. `HANDOFF.md` ergänzt um die offene Frage, ob große Dokumente zu Sessionbeginn vollständig gelesen werden sollen, und um den ausstehenden Test von `/handoff`. Memory geprüft, keine Änderung nötig.

---

## Bis 13.09.2026 – frühere Sessions

Aus Dateiständen und `AGENTS.md` rekonstruiert, ohne Einzelheiten:
- Klickbares Mockup `Hauskonfigurator.jsx` mit Build-Skript `tools/build-mockup.cjs` und erzeugter Seite `emprise.html`; als Artefakt veröffentlicht.
- Fachdokumentation `Dokumentation.html`; als Artefakt veröffentlicht.
- `BACKEND_SPEZIFIKATION.md` mit Prüfprotokoll (Anhang E).
- `AGENTS.md` und `CLAUDE.md` angelegt.
