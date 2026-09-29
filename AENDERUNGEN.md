# Änderungsprotokoll

Neueste Einträge zuerst. Ein Eintrag je Session, geschrieben von `/handoff`. Der aktuelle Stand steht in [HANDOFF.md](HANDOFF.md). Einträge bis 18.09.2026 sind verdichtet: welche Dateien ein Commit geändert hat, zeigt `git show --stat <commit>`.

---

## 28.09.2026 – AN4, Parzellen-Upload (UP17–UP19), KI-Modell (PU11, PU12) und vollständige Regelauswertung

**Auftrag:** „Stelle AN4 fertig“; danach Zurufe aus der Praxis:
- Konturen nach dem Upload „hinzu- und abwählen“.
- Linien „zusammenführen, wenn Punkte zu eng beieinander liegen“.
- „Kerben der Beschriftung“ bearbeiten.
- Das KI-Modell der PLU-Auswertung einstellen.
- Text statt PDF an das Modell geben.
- Modellvergleiche.
- Ein automatischer zweiter Durchlauf, der nach fehlenden Angaben sucht („nicht möglichst viele, sondern alle Regeln“).

Am Ende „beende alle offenen Punkte dieses chats“ und „committe und pushe wie vorgeschlagen, danach /handoff“.

**Commits** (gepusht auf `main`, thematisch getrennt; gemischte Abschnitte stecken im jeweils späteren Commit, deshalb ist erst `adf7ac4` für sich prüfbar):

| Commit | Inhalt |
|---|---|
| `18018d3` | Hand-off der AN3-Session |
| `219a285` | AN4 |
| `f184906` | UP17 |
| `3a391cc` | UP18 |
| `d9f57ec` | UP19 |
| `c799735` | PU11 |
| `1c4ba2b` | PU12 und Modell über die Umgebung |
| `adf7ac4` | G2-Vollständigkeit samt OpenAPI und Frontend-Typen |

**Neu**
- Pläne mit Selbstprüfung:
  - [docs/PLAN_AN4_KORREKTUR.md](docs/PLAN_AN4_KORREKTUR.md)
  - [docs/PLAN_G2_VOLLSTAENDIGKEIT.md](docs/PLAN_G2_VOLLSTAENDIGKEIT.md), mit Probelauf in 7.5
  - Nachträge PLAN_AN1 9–11 (UP17–UP19) und PLAN_AN2_PLU 8–9 (PU11, PU12, Modellvergleiche)
- **AN4:**
  - Regelformular aus `GET /admin/rule-kinds`, auch im Büro (RW15).
  - Korrekturen je Projekt mit Begründung und Fundstelle (Migration 0015).
  - Übernahme aus Zusatzdokumenten, zwei Stände vergleichen.
- **G2:**
  - Modellwahl (Migration 0016, später in die gemeinsame Datenbank verschoben).
  - Textschicht für Modelle ohne PDF-Eingabe.
  - Anweisung `g2-prompt-5`.
  - Rückfall für Modelle ohne erzwungenen Funktionsaufruf.
  - Nachsuche (Lauf 3) mit Alternativbezeichnungen und Zusatzseiten.
  - Abdeckung der Textstellen (Migration 0017).
  - Referenzlisten mit Messung, Entwurf `backend/app/rules/reference_seed/beyenes_uc.json`.
- **Gemeinsame Datenbank** `emprise_shared` für beide Produkte:
  - eigene Migrationen `backend/migrations_shared`
  - `shared-migrate`
  - Verwaltung `/verwaltung` in Konfigurator und Analyse
  - auf Unraid eigener Stack `deploy/unraid/compose.shared.yaml`

**Geändert**
- ANNAHMEN:
  - neu: KR01–KR09, UP17–UP19, PU11, PU12, VA01–VA10
  - angepasst: G16, RW03, RW15, PS08, EA12
- BETRIEB: 9 (Modell, Nachsuche, Kosten), 15 (AN4, Modellwahl), neu 16 (gemeinsame Verwaltung).
- Unraid README:
  - Hostname der Analyse
  - neu Abschnitt 10 (gemeinsamer Stack)
- README, neue Stolperstellen:
  - Regelarten und Formular
  - abgebrochenes `docker compose run` läuft weiter
  - gemeinsame Alembic-Umgebung
  - Laufzeit-Image
- PLAN_ANALYSE: AN4 umgesetzt, AN7 und E-A7 neu.
- UMSETZUNGSPLAN D18 und R1.
- AGENTS: Stand, Tabelle, Präfixe KR, VA.
- Beim lokalen Neustart gefunden und behoben (PLAN_G2 7.4 Nr. 14–15):
  - Das Laufzeit-Image kopierte die gemeinsamen Migrationen nicht.
  - Relative Links in der Splat-Route der Verwaltung.
  - Beim Umzug der Modellwahl fehlte der Anzeigename.

**Entschieden**
- E-AN4-1 bis E-AN4-9 nach Empfehlung, mit dem Auftrag „Stelle AN4 fertig“.
- Auf „welche Fragen bleiben offen“:
  - **E-A7:** Gescannte PDFs werden gelesen, mit Hinweis auf die Mehrkosten und eigenem Limit im Abo, als Modul AN7.
  - **Hostname** `emprise-analyse.aslani.work` (PS08).
  - **Hinweistexte L7** schreibt der Nutzer selbst und ersetzt die Rückfalltexte nach und nach (G16).
- PU11: Die Modellwahl ist „eine Einstellung für alle“. PU12: Text für Modelle ohne PDF-Eingabe, Claude bleibt bei PDF.
- G2-Vollständigkeit (PLAN_G2_VOLLSTAENDIGKEIT, Kontext und 3):
  - Nicht gefundene Pflichtangaben bleiben offen; der Architekt bestätigt sie.
  - Referenzliste Beyenes UC, von Hand erweiterbar in einer programmweiten Verwaltung.
  - Die Nachsuche nutzt dasselbe Modell.
  - Die Verwaltung ist gemeinsam für beide Produkte, die Modellwahl zieht dorthin.
  - Auf Unraid ein eigener kleiner Stack.
  - Probelauf E freigegeben.
  - E-VA-1 bis E-VA-4 nach Empfehlung.

**Ohne Dateiänderung**
- **Erste echte Auswertungen** (Beyenes UC, Opus 5, PDF: 0,73 $, 13 Werte) und alle Modellvergleiche: in PLAN_AN2_PLU 9 und PLAN_G2 7.5.
- **OpenRouter:** Laut OpenRouter sind 3,84 $ von 10 $ verbraucht (Stand beim Hand-off; die Anzeige hinkt nach).
- **Berichtigt:** Die abgelehnte DeepSeek-Auswertung lief trotzdem, 21 Minuten in der Kopie, 0,013 $. Meine erste Aussage „keine Kosten“ war falsch; die Stolperstelle steht im README.
- **Lokal:**
  - Beide Stacks sind neu gebaut.
  - Die Modellwahl der Analyse (Opus 5.5) gilt jetzt gemeinsam.
  - Die Referenzliste ist eingespielt.
  - `/verwaltung` ist in beiden Apps im Browser geprüft (PLAN_G2 7.6).
- **Cloudflare-Tunnel:** Er lief zeitweise für den Fernzugriff und ist beendet. Die Anmeldung darüber ging nicht, weil der OIDC-Testdienst nur lokal erreichbar ist.

**Memory:**
- geändert: `feedback-plan-dann-umsetzen`
- neu: `project-vollstaendige-regelauswertung`, `feedback-kosten-und-abgelehnte-aufrufe`

---

## 28.09.2026 – Emprise Analyse: AN3 vollständig (Gabarit und Schnitt)

**Auftrag:** „welches ist der nächste Schritt, um Emprise Analyse abzuschließen?“ – Antwort: RA2 (Rest von AN3, AN4, AN5), als Nächstes Gabarit und Schnitt, parallel Schlüssel und echte Unterlagen. Darauf „ja, beginne mit dem Modulplan für Gabarit und Schnitt – beende AN3“, am Ende „committe und pushe alle Änderungen, danach /handoff“.

**Commits:** `ec5a6e1` Emprise Analyse: AN3 vollständig (Gabarit und Schnitt), gepusht; CI lief beim Hand-off noch. Die CI zu `e87bb5e` (Hand-off der OpenRouter-Session) ist grün.

**Neu**
- Modulplan [docs/PLAN_AN3_GABARIT.md](docs/PLAN_AN3_GABARIT.md) mit Selbstprüfung (13 Befunde vor dem Bau, 4 beim Bau, geprüfte Alternativen, Browserprüfung).
- Backend: `analysis/domain/gabarit.py` (Stufen in beiden Auslegungen), `analysis/domain/section.py` (Schnitte A–A', B–B'), Tests `tests/unit/test_analysis_gabarit.py`.
- Frontend: `products/analyse/GabaritSchnitt.tsx` (Lageplan mit Höhenlinien, Stufentabelle, Schnitt) mit `gabarit-schnitt.test.tsx`.

**Geändert**
- Kern G3 ohne Verhaltensänderung: `setbacks.at_height`, `derive.contour_at_height`, `heights.from_storeys` mit optionaler Geschosshöhe.
- Nutzfläche je Geschoss aus dem Gabarit (EA15); `NOT_COUNTED` ohne `boundary_height`, `upper_setbacks`; `ENGINE_VERSION an3-1.1.0`; `AnalysisOut.gabarit`, `.sections`, Geschossflächen; `openapi.json`, `schema.d.ts`.
- Telefonbreite der Projektseite (Fehler seit AN1): `min-w-0` an den Rasterkindern, `relative` am Rahmen von `site/KantenListe.tsx`.
- Dokumente: ANNAHMEN EA13–EA17 (EA05, EA11 angepasst), PLAN_ANALYSE (Kopf, AN3, RA2), PLAN_AN3_ANALYSE (Verweise, 7.1 Nr. 9 gelöst), BETRIEB 15 (Gabarit, Laufzeit, Störung), README (Stolperstelle Telefonbreite; beim Hand-off: Hinweis zu `uv lock` aus HANDOFF 6 dorthin verschoben, veralteter Verweis auf `integrations/claude.py` berichtigt, Browserprüfung mit vorübergehender Büro-Korrektur), AGENTS (Stand, Dokumententabelle), UMSETZUNGSPLAN D18, Startseitentext de/fr.

**Entschieden**
- E-AN3G-1 bis E-AN3G-8 (PLAN_AN3_GABARIT 6) nach Empfehlung mit dem Auftrag „beende AN3“: beide Auslegungen, Stufen 3 m plus kennzeichnende Höhen, zwei feste Schnitte, Gelände eben bis AN5, 3D-DXF mit AN5, Nutzfläche aus dem Gabarit, keine Dachneigung, Rechnung im Backend.

**Ohne Dateiänderung**
- Prüflauf: Backend 606 Tests mit `TEST_S3=1`, Frontend 178, ruff, Format, mypy, Typprüfung, Lint grün (PLAN_AN3_GABARIT 7.4).
- Browserprüfung mit vorübergehender Büro-Korrektur im Testprojekt „Testparzelle Zone Uh“ (danach gelöscht, im Audit-Log sichtbar); Ergebnis in PLAN_AN3_GABARIT 7.4, Laufzeit (Median 59 ms) in BETRIEB 15.
- Lokale Images neu gebaut (`docker compose build migrate web`), beide Stacks neu gestartet: Die Container haben jetzt auch das `openai`-Paket (HANDOFF 4.6 Punkt 1, erster Teil erledigt).

**Memory:** `feedback-plan-dann-umsetzen` um den Ablauf dieser Session ergänzt.

---

## 26.09.2026 – G2: Schnittstelle auf OpenRouter umgestellt

**Auftrag:** Schnittstelle für OpenRouter statt der Claude API einrichten (Nutzerfrage „kannst du eine Schnittstelle für OpenRouter einstellen?“); nach kurzer Klärung (Zweck: vollständiger Ersatz; Drittanbieter für Planunterlagen akzeptiert) umgesetzt. Am Ende „pushe und comitte alle Änderungen, dann /handoff“.

**Commits:** `86869ed` Hand-off-Dokumente der AN3-Session (nachgeholt), `16ac599` Regelauswertung (G2): Schnittstelle auf OpenRouter umgestellt. Beide gepusht; CI nicht abgewartet.

**Geändert**
- `backend/app/integrations/claude.py` → `backend/app/integrations/openrouter.py`: OpenAI-kompatible Chat-Completions-API von OpenRouter statt der Anthropic-Messages-API. Modell frei über `EMPRISE_RULES_MODEL` wählbar (Vorgabe `anthropic/claude-opus-5`), strukturierte Ausgabe über einen erzwungenen Funktionsaufruf statt `response_format` (breiter über Anbieter hinweg unterstützt), Denkaufwand über den herstellerübergreifenden `reasoning`-Parameter. Entfällt: das zugesicherte 1-Stunden-Zwischenspeichern der Dokumente und der serverseitige Fallback-Beta-Header (beides Anthropic-spezifisch, kein verlässliches Gegenstück über OpenRouter).
- Schlüssel umbenannt: `EMPRISE_ANTHROPIC_API_KEY` → `EMPRISE_OPENROUTER_API_KEY` (Unraid: `ANTHROPIC_API_KEY` → `OPENROUTER_API_KEY`) in `app/config.py`, allen Compose- und `.env.example`-Dateien, CI, Playwright-Kommentar, `tests/e2e_seed_rules.py`.
- Abhängigkeit `anthropic` → `openai` in `backend/pyproject.toml`; `uv.lock` minimal aktualisiert (nur der nötige Wechsel, ohne Fremdupgrades anderer Pakete – erster Lock-Versuch ohne die bestehende `uv.lock` als Grundlage hatte ungewollt viele Transitiv-Pakete mit hochgezogen, deshalb verworfen und mit vorhandenem Lock als Basis neu aufgelöst).
- Nutzertexte `frontend/src/i18n/{de,fr}.json` (Büro-Oberfläche „Regelwerke“, Fehlertext `rules.notices.not_configured`): „Claude API“ → „OpenRouter“.
- Dokumente: README (Stolperstellen, Prüfbefehle), `docs/BETRIEB.md` (Abschnitt 1 und 15), `deploy/unraid/README.md`.
- Tests: `tests/unit/test_rules_integrations.py` komplett neu für die OpenRouter-Antwortform (OpenAI-Chat-Completion mit erzwungenem Tool-Call statt Anthropic-Stream-Events); `tests/rules_support.py` (`FakeExtractor`), betroffene Integrationstests auf den neuen Schlüsselnamen umgestellt.

**Entschieden** (Nutzer, 26.09.2026)
- OpenRouter ersetzt die Claude API vollständig als Schnittstelle der Regelauswertung (G2), nicht nur als Fallback.
- Damit ein weiterer Drittanbieter im Datenweg neben der bisherigen Ausnahme der Claude API (D3/D4) – akzeptiert, weil weiterhin nur öffentliche Planunterlagen gesendet werden, nie Kundendaten (L8). Festgehalten als **RW28** in `docs/ANNAHMEN.md`.

**Ohne Dateiänderung**
- Geprüft im Container (`backend-dev`-Image neu gebaut): Backend 585 Tests (davon 10 im neuen `test_rules_integrations.py`, vorher 588 – Differenz durch eine nicht mehr einzeln nachgebildete Anthropic-Fehlerart im Test, die Fehlerbehandlung selbst bleibt im Code), Frontend 172, dazu ruff, `ruff format --check`, mypy und der Frontend-Typecheck/Lint grün.
- Die laufenden Container `api`/`worker` nutzen weiterhin das alte Image `emprise-backend:local` ohne `openai`-Paket; vor dem nächsten echten Auswertungslauf `docker compose build migrate web` und Neustart nötig (siehe HANDOFF 4.6).

**Memory:** keine Änderung.

---

## 26.09.2026 – Entscheidungen zu Betrieb und Zusatzdokumenten, Emprise Analyse: AN3

**Auftrag:** Stand zusammenfassen, Hand-off-Dokumente der Vorsession committen, A28 nachtragen, Priorität 1 und E-AN2-5 in höchstens drei Fragen entscheiden, dann AN3 (Modulplan mit Selbstprüfung, Umsetzung). Am Ende „committe und pushe alle änderungen, danach /handoff“. Begonnen am 25.09., abgeschlossen am 26.09.2026.

**Commits:** `92e00fd` Hand-off-Dokumente der AN2-Session, `0c2b42c` A28 in ANNAHMEN, `d2c5765` Modulplan `docs/PLAN_AN3_ANALYSE.md`, `91fa1e3` AN3 (Code, Tests, Dokumente, eingetragene Entscheidungen). Alle gepusht; CI-Lauf 36227653123 vollständig grün, auch e2e.

**Neu**
- Backend: Modul `app/analysis/` (nur Analyse-Produkt; `domain/` mit `footprint`, `storeys`, `floor_area`, `compare`, `analyse`, `parameters`), Migration `0014_analysis.py`, Tests `tests/unit/test_analysis_domain.py` (34), `tests/integration/test_analysis.py` (9).
- Frontend: `src/api/analysis.ts`, `src/products/analyse/Analyse.tsx`, `Zusatzdokumente.tsx`, `abstand.ts` mit drei Testdateien.
- Dokumente: `docs/PLAN_AN3_ANALYSE.md` (Plan, Selbstprüfung 7.1–7.3, Befunde beim Bau 7.4, Prüflauf, Browserprüfung); ANNAHMEN Abschnitt AN3 (EA01–EA12) und A28.

**Geändert**
- G2 (wirkt auch im Hauskonfigurator): Regelart `max_area` (Höchstflächen SDP und Grundfläche in m²), PLU-Prompt `g2-prompt-4`; eigener Prompt für Zusatzdokumente ohne Pflichtarten, Prüfsumme je Dokumentart; Upload mit `lotissement`/`cahier_des_charges`, Kapitel `DOC`, Lotwahl `PUT …/regulations/{id}/lot`; `match_sector` mit Rückfall ohne Trennzeichen. Der Konfigurator zeigt `max_area`, prüft sie nicht (EA06).
- `openapi.json` aus der Vereinigung aller Produktprofile (`products.ALL_ROUTERS`).
- Oberfläche: `Bebauungsplan` nimmt das PLU nach Rolle, Neuladen über alle Dokumente; Startseite des Analyse-Produkts (Nutzfläche vorhanden, PDF als Parzellenformat); Rückfalltext `rules.notices.upload`.
- Dokumente: BETRIEB (9 Budget, Modultabelle G2 mit 0014, 15 um AN3), `deploy/unraid/README.md` (Authentik-Hostname, DNS only), PLAN_ANALYSE (AN3 umgesetzt, AN4 nur noch Übernahme mit Zitat), PLAN_AN2 (E-AN2-5), README (Stolperstellen), AGENTS, UMSETZUNGSPLAN (D18).

**Entschieden** (Nutzer, 25.09.2026)
- Monatsbudget der Claude API 150 $ je Stack, lokal 20 $; den Schlüssel trägt der Nutzer selbst ein.
- Authentik unter `auth.aslani.work`, alle Cloudflare-Einträge „DNS only“ (A26).
- E2 Mailanbieter: später. Name und Sammeladresse des Büros nicht genannt.
- **E-AN2-5 gegen die Empfehlung:** Zusatzdokumente in AN3 vorgezogen – als Anzeige neben den PLU-Regeln, ohne Verrechnung; Übernahme als Projektkorrektur bleibt AN4.
- Mit dem Auftrag gelten E-AN3-1 bis E-AN3-7 des Plans als entschieden (EA01–EA12).

**Ohne Dateiänderung**
- Zu Beginn lief Docker nicht; Docker Desktop gestartet, beide lokalen Stacks neu gebaut (Migration 0014).
- Prüfläufe: Backend 588 Tests (vorher 541), Frontend 172 (157), ruff, Format, mypy, Typprüfung, Lint, Build grün. Browserprüfung am Analyse-Stack: steht in PLAN_AN3 7.4.
- In der Analyse-Datenbank liegt jetzt zusätzlich das Test-Zusatzdokument „Règlement du lotissement Les Chênes“ (Lot 12) mit einem Scheinlauf von 0,16 $; Monatskosten dort 0,32 $.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Entscheidungsrunde zu Sessionbeginn: Empfehlung nicht immer übernommen; gewählte Option genau so umsetzen).

---

## 25.09.2026 – Emprise Analyse: AN2 (Bebauungsplan hochladen)

**Auftrag:** Stand zusammenfassen, dann „fahre mit AN2 fort“, am Ende „comitte und pushe alle änderungen“.

**Commits:** `6241363` AN2 (Plan, Code, Tests, Dokumente, dazu `Caddyfile` und `compose.yaml` aus der Browserprüfung), `aaa8bf6` CI e2e ohne Zugriff auf fremde Dienste – liegengebliebene Arbeit einer parallelen Session (`ci.yml`, `compose.e2e.yaml`), getrennt committet. Beide gepusht. Während der Session hatte die parallele Session selbst `d1d5007` (SeaweedFS) und `c240195` committet und gepusht (voriger Eintrag).

**Neu**
- Backend: `app/rules/documents.py` (Upload, Lese-Job, Zonenwahl, Entfernen), Migration `0013_regulation_upload.py`, `tests/integration/test_rules_upload.py` (14 Tests, darunter die Gegenprobe GPU ↔ Upload und der Wettlauf-Test).
- Frontend: `src/api/regulations.ts`, `src/products/analyse/Bebauungsplan.tsx`, `bebauungsplan.test.tsx`.
- Dokumente: `docs/PLAN_AN2_PLU.md` (Modulplan mit Selbstprüfung, 7.4 Befunde beim Bau, Prüflauf, Browserprüfung).

**Geändert**
- G2 (wirkt auch im Hauskonfigurator): `plan_import.py` mit den gemeinsamen Bausteinen `store_source` und `ensure_chapter`; `extract.py` plant einen Folgeauftrag, wenn während einer Auswertung ein Sektor dazukam (vorher blieb er dauerhaft ohne Regeln, PU07); `service.py` mit zweitem Einstieg und gemeinsamer Zusammenstellung `_rules_for_zones`.
- G3: Baurahmen auch ohne Kataster, sobald ein PLU hochgeladen ist; Hinweis `notice.site_without_cadastre`.
- Oberfläche: Texte für Architekten statt für Kunden (`rules.simulation.textOffice`, Hinweis auf die Anfrage nur für Kunden, „aus Grundstück und Planunterlagen“); AN1-Fehlertext „höchstens 8 MB“ auf 20 MB korrigiert.
- `frontend/Caddyfile`: keine Seiten-CSP für `/api/v1/regulation-files/*` (Chrome zeigt PDFs unter `object-src 'none'` nicht an). `compose.yaml`: SeaweedFS mit `-volume.max=0`.
- Dokumente: `docs/ANNAHMEN.md` (Abschnitt AN2 mit PU01–PU10; Verweise an UP12 und RW22), `docs/PLAN_ANALYSE.md` (AN2 umgesetzt, Zusatzdokumente nach AN4), `docs/BETRIEB.md` (G2 mit 0013 und `rules_document_read`, Abschnitt 15 für AN2, Operationen je Profil 91/51), `README.md` (Stolperstellen SeaweedFS und Browserprüfung), `AGENTS.md`, `UMSETZUNGSPLAN.md` (D18).

**Entschieden**
- Mit dem Auftrag gelten die Empfehlungen E-AN2-1 bis E-AN2-7 des Plans als entschieden (PU01–PU10). **Abweichung vom Gesamtplan:** Die Zusatzdokumente (lotissement, cahier des charges) sind nach AN4 verschoben (E-AN2-5, PU09) – zur Bestätigung in HANDOFF 3.

**Ohne Dateiänderung**
- Zu Beginn: Widerspruch gemeldet – HANDOFF nannte „nichts committet“, AN0/AN1 waren aber schon gepusht; der Wechsel auf SeaweedFS lag damals noch uncommittet im Arbeitsbaum.
- Browserprüfung, Befunde und Prüflauf stehen jetzt in PLAN_AN2 7.4. Die Anzeige der PDFs in Chrome selbst ist ungeprüft (das Browserwerkzeug lädt PDFs nur herunter).
- CI: Der Lauf nach dem Speicherwechsel (`c240195`) war im Job `e2e` bei `pnpm install --frozen-lockfile` gescheitert; der Lauf nach `aaa8bf6` (36188401453) ist vollständig grün, auch e2e.
- Lokal steht in der Analyse-Datenbank ein Testprojekt „Testparzelle Zone Uh“ mit einem Scheinlauf (0,16 $) aus der Browserprüfung.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Modulauftrag nach Zusammenfassung; „alle Änderungen“ schließt Arbeit paralleler Sessions ein, getrennt committet).

---

## 25.09.2026 – Emprise Analyse: AN0 (Produktschnitt) und AN1 (Parzelle einbringen), Parzelle auch aus PDF

**Auftrag:** „Fange mit AN0 an“, danach „weiter mit AN1“, dann „kannst du eine lokale Instanz starten“ und „Es sollte auch möglich sein, PDF-Dateien hochzuladen, aus denen dann die Parzelle gelesen wird“. Gearbeitet am 20./21.09.2026, Hand-off am 25.09.2026.

**Commits:** `8c9707f` Vorgehensplan „Emprise Analyse“ (Dokument der Vorsession), `d97da2c` AN0 und AN1 samt Hand-off-Dokumenten beider Vorsessions, `d1d5007` Objektspeicher lokal und in CI von MinIO auf SeaweedFS. Getrennt ließ sich nur das Plandokument; HANDOFF, AENDERUNGEN, AGENTS und UMSETZUNGSPLAN tragen die Änderungen beider Sessions in denselben Zeilen.

**Nachtrag nach dem Push: CI rot ohne Codefehler**

- `quay.io/minio/minio` ist seit dem 25.09.2026 nicht mehr anonym abrufbar („unauthorized“, mit anonymem Pull-Token gegengeprüft). Der Backend-Job scheiterte beim Start von MinIO, `e2e` wurde übersprungen; `security` und `frontend` waren grün.
- Umgestellt auf **SeaweedFS 3.97** – den in A16 vorgesehenen Ersatz, der auf Unraid schon läuft (A22): `.github/workflows/ci.yml`, `compose.yaml` (Dienst `storage`, S3 auf 8333, Port 9000, Gesundheitsprüfung, Band `storage-data`) und `compose.analyse.yaml`. Keine Konsole mehr; der alte Band `minio-data` bleibt ungenutzt liegen, lokale Dossiers sind über „Dossier neu erzeugen“ wiederherstellbar.
- Gegengeprüft: `test_storage_ops` und `test_submission` gegen SeaweedFS, danach der volle Lauf mit 526 Tests.

**Neu**
- Backend: `app/products.py` (Router, Job-Module, periodische Aufgaben und Startseite je Produkt), `app/plan/` (`geometry.py`, `dxf.py` – aus `submission/dossier/` verschoben), `app/site/domain/upload.py` (DXF, GeoJSON), `app/site/domain/pdfplan.py` (vektorielles PDF), `app/submission/dossier/plan.py` (nur noch `from_snapshot`), Migration `0012_parcel_upload.py`.
- Tests: `unit/test_module_boundaries.py`, `unit/test_site_upload_domain.py`, `unit/test_site_pdf_domain.py`, `integration/test_site_upload.py`, `tests/site_pdf_support.py`.
- Frontend: `analyse.html`, `src/products/analyse/` (`main.tsx`, `App.tsx`, `AnalyseLayout.tsx`, `Schaufenster.tsx`, `Projekte.tsx`, `ProjektSeite.tsx`, `ParzelleHochladen.tsx`, `KonturWahl.tsx`, `styles.css`, zwei Testdateien), `src/components/NichtGefunden.tsx`.
- Auslieferung: `compose.analyse.yaml` (lokal), `deploy/unraid/compose.analyse.yaml` und `.env.analyse.example`, `infra/local/postgres-init-analyse.sql`.
- Dokumente: `docs/PLAN_AN1_PARZELLE.md` (Modulplan mit Selbstprüfung, Kapitel 8 zum PDF-Nachtrag); `docs/PLAN_ANALYSE.md` war aus der Vorsession noch uncommittet.

**Geändert**
- Backend: `main.py`, `registry.py`, `config.py` (`EMPRISE_PRODUCT`, `site_upload_max_bytes` 20 MB), `platform/jobs/worker.py` (periodische Aufgaben je Produkt), `platform/auth/staff.py` (Startseite je Produkt, `safe_next` erlaubt jedes relative Ziel), `platform/auth/context.py` (`require_project_access` für Architekten), `platform/projects.py` (Eigentümer, Projektliste, Löschung mit Erweiterungspunkt), `platform/tasks.py`, `platform/models.py`, `platform/locales/*.json` (Fehlertexte der Upload-Codes), `site/{api,models,schemas,service}.py`, `envelope/service.py` (`NO_RULES_ORIGINS`), `configuration/domain/context.py`, `inquiry/{api,service}.py`, `submission/schemas.py`, `submission/dossier/{__init__,pdf}.py`, `cli.py`, `openapi.json`, `pyproject.toml`/`uv.lock` (neu: `pdfminer.six`, MIT).
- Frontend: `vite.config.ts` (zweiter Einstieg), `Caddyfile` (`SPA_INDEX`), `src/App.tsx`, `src/api/site.ts`, `src/api/schema.d.ts`, `src/i18n/{de,fr}.json`.
- Dokumente: `docs/ANNAHMEN.md` (neue Abschnitte AN0 mit PS01–PS09 und AN1 mit UP01–UP16), `docs/BETRIEB.md` (Abschnitt 15, Migration 0012 in der Modultabelle), `README.md`, `AGENTS.md`, `UMSETZUNGSPLAN.md` (D17 ergänzt, D18 neu), `deploy/unraid/README.md`, `deploy/unraid/deploy.sh` (Stack-Parameter), `.gitignore` (`.env.*.example` bleibt versioniert).

**Entschieden** (Nutzer)
- **D18 (20.09.2026):** „Emprise Analyse“ ist beauftragt, Modul für Modul; AN0 und AN1 umgesetzt, AN2 folgt.
- **D17 ergänzt (21.09.2026):** Die Parzelle kommt auch aus einem **vektoriellen PDF** (Katasterauszug, Plan des Geometers). Das hebt die Empfehlung E-A2 („kein PDF-Plan“) auf; gescannte PDFs bleiben offen.
- Die übrigen Empfehlungen der Pläne (E-A1, E-A3 bis E-A6, E-AN1-1 bis E-AN1-5) gelten mit dem Auftrag als entschieden und stehen als Festlegungen in `docs/ANNAHMEN.md`.

**Ohne Dateiänderung**
- **Prüfläufe:** Backend 526 Tests (vor der Session 474), Frontend 150 (143), dazu ruff, Format, mypy, Typprüfung, Lint und Build grün. `openapi.json` und `schema.d.ts` neu erzeugt.
- **Browserprüfung** am Analyse-Stack in Deutsch und Französisch, auch in Telefonbreite: Anmeldung, Projekt anlegen, GeoJSON mit zwei Konturen, Kante als Straße setzen (Hauptstraße und Azimute entstehen), PDF-Auszug mit 39 Flächen, Parzelle 65 angeklickt und übernommen.
- **Gegenprobe mit echten Daten:** Aus dem Kataster von Treillières wurde ein Auszug wie von cadastre.gouv.fr gesetzt (22 Parzellen, 23 Gebäude, 458 Schraffurlinien, Rahmen, Karte auf Seite 2). In 0,33 s gelesen, Maßstab 1:500 aus „Échelle d'édition“ erkannt, AD 65 mit 926,1 m² – **gleich der Katasterfläche**. Die Datei liegt nur im Scratchpad dieser Session; der Nutzer hat sie zum Ausprobieren bekommen.
- **Befunde der Selbstprüfung** stehen in den Plänen: PLAN_ANALYSE 8.1 Nr. 9–12 (AN0), PLAN_AN1 7.1a Nr. 1–6 und 8.4 Nr. 1–6 (AN1 und PDF). Die zwei schwersten: Beide lokalen Stacks hatten gleich benannte Dienste im selben Netz, sodass die Analyse-Oberfläche abwechselnd beim Hauskonfigurator landete; und `safe_next` ließ nach der Anmeldung nur `/buero` zu, das es im zweiten Produkt nicht gibt.
- **Lokale Instanz** läuft: Hauskonfigurator auf 8080/8000, „Emprise Analyse“ auf 8180/8100, beide mit Konto `ops@emprise.local` und Flag `site_selection`.

**Unverändert**
- Der Hauskonfigurator verhält sich gleich; berührt wurden nur Weg E (legt jetzt Kanten an, UP02) und die Löschung eines Projekts (liegt im Kern, Sperre aus Modul A bleibt).
- `EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `.env.example` weiter nicht verdrahtet (HANDOFF 4).

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (knappe Modulaufträge „weiter mit AN1“; unbeantwortete Fragen am Rundenende nicht wiederholen) und um den Fall erweitert, dass der Nutzer eine Empfehlung des Plans durch einen Praxisfall aufhebt.

---

## 20.09.2026 – Vorgehensplan „Emprise Analyse“: eigenständige Web-App aus G1–G3

**Auftrag:** „Plange eine Vorgehensweise, wie man aus G1–G3 eine eigenständige Web-App erstellen könnte“ – ein Werkzeug, das Architekten hilft, Parzelle und PLU zu analysieren und daraus einen Baurahmen für den weiteren Entwurf abzuleiten (Höhe, Abstände je Grenze, bebaubare Fläche, Nutzfläche, grafische Ableitung auf der Parzelle). **Nur Planung, keine Umsetzung, kein Code.**

**Commits:** keine. Alles liegt uncommittet im Arbeitsbaum, zusammen mit den Dokumenten der V-Session; `main` steht weiter auf `35d8b43`.

**Neu**
- [docs/PLAN_ANALYSE.md](docs/PLAN_ANALYSE.md) – Vorgehensplan für das zweite Produkt: Befund (was G1–G3 liefern, was fehlt), Architektur „ein Repo, zwei Produkte“, Module AN0–AN6, Releases RA1–RA3, sechs offene Entscheidungen E-A1–E-A6 mit Empfehlung, Abnahme, Prüfprotokoll (8.1 Fehler, 8.2 Alternativen, 8.3 Grenzen). Status: geplant, nicht umgesetzt.

**Geändert**
- `UMSETZUNGSPLAN.md` Kapitel 9: **D15, D16, D17** neu und entschieden (unten).
- `AGENTS.md`: Zeile für `docs/PLAN_ANALYSE.md` in der Dokumententabelle.

**Entschieden** (Nutzer, 20.09.2026)
- **D15 Zielgruppe:** zuerst nur das eigene Büro; ein Abo für fremde Büros mit eigenem Branding und eigener API bleibt das Ziel (Ausbaustufe AN6). Vorbereitet wird dafür jetzt nur die nullable Spalte `organisation_id`.
- **D16 Codeschnitt:** ein Repository, zwei Produkte aus gemeinsamem Kern; kein Fork.
- **D17 Datenbeschaffung:** kein Vorausdenken von Gebieten – der Nutzer lädt Parzelle und PLU selbst hoch: „das Produkt ist die Analyse, die Kunden liefern das zu analysierende Material“. Kataster-Massenimport und GPU-Abruf bleiben Komfortweg. Für den Hauskonfigurator bleibt D1 unberührt.

**Ohne Dateiänderung**
- **Kartierung von G1–G3** (Backend und Frontend, zwei Erkundungsläufe): Der Schnitt ist sauber – `site/`, `rules/` und `envelope/` importieren nur aus `platform/`, `integrations/` und untereinander; kein Fremdschlüssel aus `catalog`, `configuration`, `inquiry` oder `submission` zeigt auf eine G-Tabelle; Migrationen 0002–0006 sind ein Block. Die schwerste Kopplung läuft umgekehrt: `configuration/domain` rechnet direkt mit `envelope/domain`. Ergebnis steht in PLAN_ANALYSE 2 und 3.
- **Fünf Befunde**, die die Herauslösung betreffen und im Plan verankert sind (PLAN_ANALYSE 8.1): `resolve_rules` startet zwingend bei Gemeinde-INSEE und GPU-Zonengeometrie (größter verdeckter Aufwand, AN2); Weg E legt keine `site_edge` an; `require_project_access` kennt nur den Projekt-Cookie; `retention_cleanup` löscht Projekte nach 90 Tagen; der DXF-Schreiber liegt in `submission/dossier/` (Modul V).
- **Fachliche Lücke für Architekten:** Die Nutzfläche (surface de plancher) fehlt in G3 vollständig, und der bindende Grenzwert der Grundfläche (Minimum aus Kontur und Grundflächenzahl) wird nicht gebildet. Umgekehrt ist ein gestufter Hüllkörper fast geschenkt, weil `envelope/domain/setbacks.py` den höhenabhängigen Abstand bereits rechnet.
- **Keine Prüfläufe:** kein Testlauf, kein Build, keine Browserprüfung – es wurde kein Code geändert.

**Unverändert**
- Kein Code, keine Migration, keine Übersetzung, keine API. Der Hauskonfigurator ist von dieser Session nicht berührt.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Antworten auf Auswahlfragen können die Frage umdeuten statt eine Option zu wählen).

---

## 20.09.2026 – V: Vorentwurf-Übergabe (Plan und Umsetzung), H3 und V committet

**Auftrag:** Startprompt des Hand-offs: Stand zusammenfassen, Priorität-1-Entscheidungen nennen, D8 und D10 erfragen, danach V nach Umsetzungsplan 3.10 mit Selbstprüfung planen und umsetzen; committen und pushen erst auf Anweisung (kam am Ende der Session).

**Commits:** `72a73ab` H3 und V (Code, Tests, Dokumente – H3 lag uncommittet im Arbeitsbaum und V ändert dieselben Dateien, deshalb ein Commit), `35d8b43` Hand-off der H3-Session (HANDOFF, AENDERUNGEN). `main` steht auf `35d8b43`, CI-Lauf 35489847956 grün (security, frontend, backend, e2e; 9:13 min).

**Neu**
- `docs/PLAN_V_VORENTWURF_UEBERGABE.md` – Plan mit Selbstprüfung (9.1 Entwurf, 9.1a Bau, 9.2 Alternativen, 9.3 Grenzen), Abnahmeergebnis in Kapitel 6, Festlegungen mit Empfehlung in Kapitel 8 (E-V1–E-V8).
- Backend: `app/submission/` (`models`, `schemas`, `service`, `api`, `views`, `jobs`, `texts`, `dossier/` mit `format`, `plan`, `pdf`, `dxf`), `app/configuration/review.py` (Prüfstempel), `app/inquiry/access.py` (Zugangslink), Migration `0011_submission.py`.
- Tests: `test_submission.py` (18 Integrationstests), `test_submission_domain.py` (12 Einheitstests).
- Frontend: `api/submission.ts`, `configuration/Uebergabe.tsx`, `inquiry/ZugangAnfordern.tsx`, `pages/vorgang/{VorgangSeite,ZugangSeite}.tsx`, `pages/buero/AnfrageFassungen.tsx`, Tests `uebergabe`, `vorgang`, `anfrage-fassungen`, `check-texte`.
- `tools/sync-check-texts.cjs` – übernimmt die Texte der Prüfungen aus dem Frontend in die Übersetzungen des Backends (Dossier-PDF).

**Geändert**
- `configuration/service.py`, `schemas.py`: `review_stamp` in jeder Antwort, `design_review` mit Katalogkopie; `envelope/service.py`: `fingerprint_parts` teilt die G3-Prüfsumme in `site` und `rules`.
- `inquiry/`: Fassungen und Nachrichten in Modell, Schemas, Dienst und API; Zustände `rueckfrage`/`zurueckgezogen`, `customer.locale`, Export um Fassungen und Nachrichten, Zugangslink öffentlich; `cli.py` (`legal-seed` auch für die V-Texte), `config.py` (Einstellungen für Übergabe, Nachrichten, Zugangslink).
- Übersetzungen des Backends: Mails, Fehlertexte, Dossier-Texte und die aus dem Frontend übernommenen Prüftexte; `openapi.json` und `schema.d.ts` neu erzeugt.
- Frontend: Übergabe im Schritt Vorentwurf, Routen `/vorgang` und `/zugang`, Fassungen und Nachrichten im Anfrage-Detail, Spalte „Vorentwurf“ in der Anfragenliste, `deviationsOf` in `configuration/format.ts`, Texte in `i18n/{de,fr}.json`.
- Dokumente: `docs/ANNAHMEN.md` (VU01–VU16; G17, AF12 und HK10 nachgezogen), `docs/BETRIEB.md` (Modultabelle, Alarm `dossier_failed`, Abschnitt 14 mit ArchiCAD-Vorgehen), `UMSETZUNGSPLAN.md` (Kopf, 3.10 umgesetzt, Kapitel 7 mit fünf neuen Abweichungen, D8/D10 bestätigt), `BACKEND_SPEZIFIKATION.md` (E.4: S3 und S5 gelöst), `README.md` (Regel für die Prüftexte, zwei Stolperstellen), `AGENTS.md` (Stand, Dokumententabelle).

**Entschieden** (Nutzer, 19.09.2026)
- D8 bleibt: die Spanne ist eine unverbindliche Schätzung der Baukosten, Wortlaut unverändert.
- D10 bleibt: netto speichern, brutto mit dem Satz des Katalogs anzeigen.
- G17 (ODbL): Quellenangabe in PDF und DXF genügt; die rechtliche Prüfung vor der Beta bleibt offen (VU11).

**Ohne Dateiänderung**
- Browserprüfung am lokalen Stack (AD 65, Deutsch und Französisch, auch Telefonbreite): Kontakt, Code aus Mailpit, Übergabe → EMP-2026-000002 Fassung 1 mit Dossier, Büro- und Kundenmail, Nachricht des Büros → `rueckfrage`, Antwort des Kunden → `in_bearbeitung`, Zugangslink eingelöst, PDF-Download, Regeländerung → `review_changed` mit `rules` und `result`, danach Fassung 2 und Fassung 1 `superseded`. Fand drei Fehler (Plan V 9.1a Nr. 15–17).
- Messung lokal: Übergabe 0,8–1,0 s, abgelehnte Übergabe 0,6 s, Dossier-Job 2,2–3,7 s, Snapshot 17,5 KB, Prüfstempel 1–2 ms je Abruf; `GET …/configuration` rund 0,5 s im Container (aus H2/H3). Plan V 6.
- Volllauf: Backend 474 Tests (vorher 444), Frontend 143 (vorher 132), ruff, Format, mypy, Typprüfung, Lint und Build grün. Playwright lief lokal nicht.
- Lokaler Stack auf dem neuen Stand: Migration 0011, `legal-seed` für die zwei neuen Rechtstexte, Flag `submission` für `architect`; die Regelkorrektur der Browserprüfung wurde wieder entfernt.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (gezielte Rückfragen mit Empfehlung; Commit-Zuschnitt, wenn zwei Module ineinandergreifen).

---

## 19.09.2026 – H3: Konfiguration und Kosten (Plan und Umsetzung)

**Auftrag:** Startprompt des Hand-offs: Stand zusammenfassen, Priorität-1-Entscheidungen nennen, HP03, D12/D13 und die Maße von Terrasse und Carport erfragen, danach H3 nach Umsetzungsplan 3.9 mit Selbstprüfung planen und umsetzen; CI-Lauf 35431041895 prüfen.

**Commits:** keine. Alles liegt uncommittet im Arbeitsbaum (H3 und die Dokumente der beiden Vorsessions); `main` steht weiter auf `a5fc5e3`.

**Neu**
- `docs/PLAN_H3_KONFIGURATION_KOSTEN.md` – Plan mit Selbstprüfung (10.1 Entwurf, 10.1a Bau, 10.2 Alternativen, 10.3 Grenzen) und Abnahmeergebnis (6).
- `backend/app/configuration/domain/` – `options`, `outbuildings`, `areas`, `compliance`, `costs`, `energy`, `orientation`, `design` (`type_part`, `site_part`, `evaluate_design`); `outputs.py`; `backend/app/catalog/domain/offer.py`, `options.py`; Migration `0010_configuration_options.py`.
- Frontend: `Linien`, `Optionen`, `Kostenleiste`, `Nebenbauten`, `Vorentwurf` unter `frontend/src/configuration/`, Schritte in `KonfiguratorSeite.tsx`, Felder in `KatalogLinienOptionen.tsx`, Texte in `i18n/{de,fr}.json`.
- Tests: `test_design_domain.py` (58), `test_configuration_options.py` (24), `optionen-linien.test.tsx` (29), `katalog-linien-optionen.test.tsx` (5), Erweiterung von `konfigurator-seite.test.tsx`.

**Geändert**
- `catalog/service.py`: `offer_for_type`, Arten und Maße von Optionen, Veröffentlichung von Linie und Option nur aus `draft`/`review` mit `current_version_id` = höchste veröffentlichte Version, **neuer Preiskatalog-Entwurf übernimmt die Zeilen der veröffentlichten Version** (H1-Lücke, Plan H3 10.1a Nr. 12). `configuration/service.py`, `schemas.py`, `api.py`, `domain/surface.py` (`building_kind`, `use_bands`, `allow_assumed`), `domain/house.py` (Garagentor), `ENGINE_VERSION = "h3-1.0.0"`. Problemtexte `invalid_selection`, `selection_blocked`, `version_not_publishable`.
- `backend/tests/e2e_seed_types.py` legt zusätzlich Linien, Optionen, Preise (erfunden), RE2020-Befund und veröffentlichten Preiskatalog an; `openapi.json`, `schema.d.ts` neu erzeugt.
- Dokumente: `docs/ANNAHMEN.md` (HK01–HK17; HP01–HP03 als bestätigt), `docs/BETRIEB.md` (Modultabelle, Abschnitt 13), `UMSETZUNGSPLAN.md` (3.9 umgesetzt, Kapitel 7, D8/D10/D12/D13), `AGENTS.md` (Stand, Dokumententabelle), `README.md` (Stolperstellen, Demo-Daten, Browserprüfung).

**Entschieden** (Nutzer, 19.09.2026)
- HP03 bleibt: Terrasse, Carport und Zufahrt kommen mit H3.
- D12 und D13 bestätigt.
- Terrasse: 3 m tief, Breite der Gartenfassade, Preis je m². Carport: beide Größen (einstellig 3 × 5 m, zweistellig 6 × 5 m) als zwei Optionen.
- **Nach Empfehlung genommen, nicht gefragt:** D8 (nur Wortlaut der Spanne), D10 (netto gespeichert, brutto angezeigt, 20 %); beides HK10, umkehrbar.

**Ohne Dateiänderung**
- CI-Lauf 35431041895 zu `a5fc5e3` grün (security, frontend, backend, e2e).
- Browserprüfung am lokalen Stack (AD 65, Deutsch und Französisch): Linie, Optionen mit Preisen, Ausschluss der Carports, Vorentwurf, Kostenleiste. Fand zwei Fehler, die die Rechteck-Tests nicht fanden: Carport hinter dem Haus mit Zufahrt durch das Haus, Carport überlappt Terrasse (beide behoben, Plan H3 10.1a Nr. 15–16).
- Messung lokal (AD 65 mit Terrasse und Carport): `GET …/configuration` 13–79 ms, `GET …/catalog/options` 14–36 ms; Plan H3 6.
- Volllauf: Backend 444 Tests (vorher 362), Frontend 132 (vorher 91), ruff, mypy, Typprüfung, Lint, Build grün. Playwright lief nicht.
- Lokaler Stack: Migration 0010 angewendet, Demo-Katalog eingespielt, Flags nach der Prüfung wieder nur für `architect`.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Ablauf mit gezielten Fragen vor Plan und Umsetzung; ungefragte Entscheidungen gelten als nach Empfehlung genommen).

---

## 19.09.2026 – Dokumentation verdichtet

**Auftrag:** Nutzer: Dokumentation optimieren, Dateien zusammenlegen, Dopplungen vermeiden, Ausführungen komprimieren, keine Informationen verlieren, gründlich und mit Selbstprüfung. Erst Plan nach vollständiger Durchsicht aller Dokumente, dann Umsetzung.

**Commits:** `7cecdb5` (Sicherung des Ausgangsstands), `a5fc5e3` (Verdichtung), beide auf `main` gepusht; CI-Lauf 35431041895 bei Abschluss noch in Arbeit.

**Entschieden** (Nutzer, 19.09.2026)
- Die Spezifikation wird kapitelweise gelesen: Kapitel 0–2 und die im Modulabschnitt des Umsetzungsplans genannten Kapitel. Beantwortet die seit 13.09.2026 offene Frage zum Lesen großer Dokumente (Spez. 0 Punkt 1, CLAUDE.md Punkt 4).
- Ältere Einträge dieses Protokolls verdichten: Dateilisten durch Commit-Kennungen ersetzen; Entscheidungen, Befunde und Messwerte bleiben.
- Den Ausgangsstand vorher sichern: Commit `7cecdb5` (Hand-off-Dokumente der H2-Session).
- Nutzer: „comitte und pushe“ – `a5fc5e3` committet und zusammen mit `7cecdb5` gepusht.

**Grundsatz:** Jeder Inhalt steht an einer Stelle (AGENTS.md unter der Dokumententabelle). Dateinamen, Kapitelnummern und IDs bleiben unverändert, weil der Code über 300-mal darauf verweist (`Spez. 5.3.4`, `Plan H1 3.5`, `BR03`). Keine ganzen Dateien zusammengelegt: Modulpläne werden je Modul gelesen und vom Code per Dateiname referenziert; zusammengelegt würde der nötige Kontext größer.

**Geändert**
- `CLAUDE.md` – Leseregeln: neuester Protokolleintrag, Spezifikation kapitelweise, große Dokumente (auch ANNAHMEN) nur abschnittsweise.
- `AGENTS.md` – Stand auf drei Sätze; Dokumententabelle (Modulpläne in einer Zeile, D1–D14, E1–E12, Anhang E.4, README mit Stolperstellen); Grundsatz „eine Quelle je Inhalt“; Rangfolge ohne feste Modulliste.
- `HANDOFF.md` – ohne Dopplungen zu AGENTS und AENDERUNGEN; Stolperstellen nach README; zurückgeholte und neue Arbeitspunkte (4.1, 4.5, 4.7, 4.9).
- `README.md` – Aufbau mit allen Modulpaketen; Start mit allen Flags, `legal-seed` und Demo-Typen; Prüfbefehle vereinheitlicht; API-Regeln ergänzt (Modellnamen, Trigger, Jobarten, Sequenzen); neuer Abschnitt **Stolperstellen** aus allen 13 Fassungen von HANDOFF.md.
- `BACKEND_SPEZIFIKATION.md` – Kapitel 0 Punkt 1 (kapitelweise), 7 (Pfad `docs/ANNAHMEN.md`), 8 (Verweis auf Abweichungen); neuer Anhang **E.4** mit den offenen Korrekturen S1–S17.
- `UMSETZUNGSPLAN.md` – Zeile 1 repariert: Die Vermerke zu D12/D13 standen seit `98fce8f` vor der Überschrift, jetzt in Kapitel 9. Kopfzeile verdichtet, Blöcke „Umgesetzt“ in 3.3, 3.5–3.8 auf je einen Absatz mit IDs; Hinweis zum Paket `configuration/` (3.2); Kapitel 7: `/buildable` entfällt (HP04); 10.4: D13 erledigt.
- `docs/ANNAHMEN.md` – Einleitungen ohne Testzahlen und Erzählung, Einträge gestrafft, Bezüge der H2-Einträge eindeutig („Plan H2 …“); **H01 korrigiert** (Befunde); G04 um Lotissement-Straßen als „voie“ ergänzt (aus HANDOFF `cc48386`); G18, A11, RW13, RW16, G21 mit Verweis auf den heutigen Stand.
- `docs/BETRIEB.md` – Abschnitt 1 mit Tabelle „Module im Betrieb“ (Migration, Flag, Jobs, ausgehender Zugang, Voraussetzungen) und Log-Alarmen; damit erledigt: HANDOFF 4.5 Punkt 4 (Betrieb für H1). Abschnitte 8, 9, 11, 12 ohne die dorthin gewanderten Schritte.
- `deploy/unraid/README.md` – Abschnitte 9–11 zu „9. Module auf Unraid“ zusammengelegt (nur Unraid-Eigenes, Verweis auf BETRIEB 1).
- `infra/README.md` – Abschnitt 4: Remote besteht, Zweigschutz offen.
- `docs/PLAN_G3_BAURAHMEN.md`, `PLAN_H1_HAUSKATALOG.md`, `PLAN_A_ANFRAGE.md`, `PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md` – veraltete Stellen mit Kurzverweis auf die geltende Festlegung (AF01, HP04, BR03, H01, AF11, HP16); Kopfzeilen von H1 und A.
- `.claude/skills/handoff/SKILL.md` – Dauerhaftes nie nur in HANDOFF; Protokolleinträge mit Commit statt Dateiliste; Prüfschritte gegen verlorene Punkte.
- `AENDERUNGEN.md` – Einträge vom 18.09. bis 14.09. verdichtet; der H2-Eintrag und die Einträge bis 13.09. (vor Git) bleiben wörtlich.

**Befunde der Durchsicht**
- **Verloren:** Die Liste S1–S13 der Spezifikationskorrekturen stand nur noch in `git show 1f4b646:HANDOFF.md`, S14 in `91e84f6:HANDOFF.md`; HANDOFF verwies seit 14.09. auf „AENDERUNGEN 14.09.“, wo sie nie stand. Jetzt Spez. Anhang E.4, ergänzt um S15–S17 aus H2.
- **Verloren:** rund 15 Stolperstellen früherer HANDOFF-Fassungen (u. a. Playwright unter Windows, Corepack aus dem Wurzelordner, `python` als Store-Platzhalter, `ruff format`, `# type: ignore` in `claude.py`, parallele Sessions, Massentests, `FakeExtractor`); am Code geprüft und nach README übernommen. Bewusst nicht übernommen, weil erledigt oder anderswo geregelt: erster Hand-off von Hand (Eintrag 13.09.), „Modul A übersprungen“, einzelne CI-Läufe (`8cf8a27`, `596e075`, `11a6e64`), „große Dokumente kapitelweise lesen“ (jetzt CLAUDE.md), Ordnername `Codex_Projet` und Rolle von AGENTS/CLAUDE, Commit nur auf Aufforderung (Memory).
- **Verloren:** offene Punkte Playwright für Weg E, Log-Alarme `rules_extract_failed`/`rules_budget_exceeded`/`road_import_implausible`, Lotissement-Straßen als „voie“, alter Test-Stack `emprise-g1` (Container und Volume bestehen noch); zurück in HANDOFF, BETRIEB 1 und G04. Ebenso Einzelheiten zu offenen Punkten (XLSX-Vorlage „bisher nur Beschreibung im Importformular“, Löschung „danach Weiterleitung auf `/`“, Hinweis zur Empfehlung bei RW19) und der Befund zum Import von `plateau` (Eintrag 18.09., H1-Oberfläche).
- **H01 widersprach dem Code:** Seit `596e075` bearbeiten laut `catalog/api.py` (`Editor`) `architect` und `catalog_admin`, `ops` liest; H01 sagte „`catalog_admin` statt `architect`, `architect`/`ops` lesen mit“. H01 korrigiert; der Docstring in `catalog/api.py` steht als Arbeitspunkt in HANDOFF 4.5.
- **Nebenbefunde im Code (nicht geändert):** `EMPRISE_OFFICE_EMAIL` fehlt in `deploy/unraid/compose.yaml` und `.env.example`; das Log `envelope_derive_failed` aus Plan G3 6.2 gibt es nicht (HANDOFF 4.7, 4.9).
- CI-Lauf 35427795221 zu `98fce8f` (H2) und 35398360953 zu `df4fa3d` (H1-Oberfläche) sind grün.

**Selbstprüfung**
- Token-Vergleich aller Dokumente und Memory-Dateien gegen `7cecdb5` (Backtick-Codes, IDs, Zahlen mit Einheit, URLs, Pfade, Commits; Skript im Scratchpad): von 3.016 Tokens fehlten vor diesem Eintrag 150. Davon 132 aus den verdichteten Protokolleinträgen: alle 101 Pfade stehen in den genannten Commits (`git log --name-only`), die übrigen sind Bezeichner, die im Code stehen, oder Testzahlen, die umformuliert erhalten sind. Die 18 übrigen sind begründet: korrigierte Pfade (`backend/docs/ANNAHMEN.md`, `pages/buero/Katalog.tsx`), die alte Leseregel (`^#{2,3}`, „6 Punkte“), in README oder BETRIEB zusammengeführte Befehle, das erledigte `gh run list`.
- Beim Wort-Diff von ANNAHMEN gefundene weggefallene Nuancen wiederhergestellt (H10, H11, H12, AF02, AF03, G29, G30, BR07) und im Protokoll die Zuordnung der Tests zu den Prüfbefunden (A1–A4, E15, E19, F22).
- Verweise: 0 kaputte Links; alle 145 IDs der ANNAHMEN definiert, keine referenzierte ID fehlt; alle Kapitelverweise aus Code und Doku auf Spezifikation, Umsetzungsplan, Modulpläne, BETRIEB und HANDOFF lösen sich auf (einziger Rest: `Spez. 5.1.4.6` im Code meint 5.1.4 Punkt 6). Unraid-Verweise auf die früheren Abschnitte 10/11 auf 9 umgestellt; flüchtige HANDOFF-Abschnittsnummern in Plan G3 und Plan A durch Namen ersetzt.
- Größen (Bytes; Summe aller Dokumente 573.538 → 572.318, weil README, Spezifikation und dieser Eintrag wachsen): HANDOFF 18.762 → 13.697, AGENTS 7.452 → 5.446, AENDERUNGEN 46.816 → 40.019 (mit diesem Eintrag von rund 8.000), ANNAHMEN 67.680 → 64.331, Umsetzungsplan 79.852 → 78.806; gewachsen README (3.967 → 13.762, Stolperstellen) und Spezifikation (120.886 → 124.704, Anhang E.4).
- Pflichtkontext je Session (CLAUDE, AGENTS, MEMORY-Index, HANDOFF, neuester Eintrag): rund 33 KB → rund 26 KB; das Ziel von 20 KB ist nicht erreicht, weil HANDOFF 18 offene Entscheidungen und neun Gruppen offener Arbeitspunkte trägt. Backend-Sessions lesen statt der ganzen Spezifikation (125 KB) Kapitel 0–2 (7 KB) plus die Modulkapitel, statt ganz ANNAHMEN (64 KB) den Abschnitt des Moduls (5–16 KB).

**Unverändert:** `Dokumentation.html`, `emprise.html`, `Hauskonfigurator.jsx` (kein Artefakt neu veröffentlicht); der normative Text der Spezifikation (nur Kapitel 0 und Anhang E.4).

**Memory:** `feedback-plan-dann-umsetzen` und `project-hosting-unraid` verdichtet (Repo-Fakten per Verweis); neu `feedback-kompakte-dokumentation`.

**Hand-off:** HANDOFF nach dem Push nachgezogen (Git-Stand, nächster Schritt, Startprompt); aus der Fassung in `a5fc5e3` erledigt: Abschnitt 5 Punkt 1 (committen und pushen). Alle übrigen Punkte bleiben offen.

---

## 19.09.2026 – H2: Zulässigkeit und Implantation (Plan und Umsetzung), Hand-off

**Neu**
- `docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md` – Plan des Moduls H2 mit Herleitung der Fläche zulässiger Ursprünge, Wirkung der Regeln (D12), Drehung, Weg E, Prüfprotokoll (10: Befunde beim Bau, verworfene Alternativen, Grenzen).
- `backend/app/configuration/` – Modul H2: `domain/` (rein: `house`, `geometry`, `context`, `checks`, `rotations`, `surface`, `placement`, `presets`, `fit`, `tolerances`), `models.py` (`configuration`), `schemas.py`, `service.py`, `api.py`.
- `backend/migrations/versions/0009_configuration.py` – Tabelle `configuration` (ein Datensatz je Projekt, Typversion, Lage in Lambert-93, Grenzschalter, Revision).
- `backend/tests/unit/test_configuration_domain.py` (38 Fälle: Parität Spez. 11.2, Bauband, Grenze, Höhen, Zonen, Drehung, `hypothesis`), `backend/tests/integration/test_configuration.py` (19 Fälle gegen PostGIS, echtes Testgrundstück AD 65 und Weg E), `backend/tests/configuration_support.py`, `backend/tests/e2e_seed_types.py` (drei Demo-Typen `demo_*` für den lokalen Stack).
- `frontend/src/api/configuration.ts`, `frontend/src/configuration/` (`geometry.ts`, `format.ts`, `TypKarten.tsx`, `Implantation.tsx`, Tests, `__fixtures__/konfiguration.ts`), `frontend/src/pages/konfigurator/KonfiguratorSeite.tsx` (+ Test) – Route `/konfigurator`; 28 neue Tests der Oberfläche.

**Geändert**
- `backend/app/catalog/service.py` – `published_types`, `type_by_version_id` (Lesezugriff für H2); `backend/app/envelope/service.py` – `derived` (reine Ableitung statt Ausgabeform); `backend/app/main.py`, `config.py` (`configuration_limit_per_minute`), `migrations/env.py`, `tests/conftest.py` (Tabelle in der Bereinigung), Fehlertexte `problem.type_blocked` u. a. in `backend/app/platform/locales/{de,fr}.json`.
- `backend/openapi.json`, `frontend/src/api/schema.d.ts` – neu erzeugt (Modell `PlacementRequest`, weil `PlacementIn` schon im Katalog vergeben ist).
- `frontend/src/App.tsx`, `pages/grundstueck/GrundstueckSeite.tsx` (Knopf „Haus wählen“ hinter dem Flag), `i18n/{de,fr}.json` (Block `configurator`, beide Sprachen deckungsgleich).
- `docs/ANNAHMEN.md` (HP01–HP20), `docs/BETRIEB.md` (12), `UMSETZUNGSPLAN.md` (Umsetzungsstand 3.8; D12/D13 vermerkt), `AGENTS.md` (Stand, Dokumententabelle), `HANDOFF.md`.

**Entschieden**
- Nutzer: „erstelle den hauskonfigurator“ – ich habe das als Release R2 gelesen und mit H2, dem ersten Modul der Kette, begonnen; H3 und V blieben aus, das habe ich gesagt. Keine Rückfrage.
- **D12 und D13** nach der Empfehlung des Plans genommen (Auftrag als Umsetzung gewertet, Memory `feedback-plan-dann-umsetzen`); vom Nutzer nicht ausdrücklich bestätigt, umkehrbar. D13 erweitert: Freier Modus auch bei Kataster-Grundstücken ohne verfügbare Regeln (ANNAHMEN HP02).
- Abweichung vom Umsetzungsplan 3.8: Terrasse, Carport und Zufahrt kommen mit H3 (HP03); `/buildable` entfällt zugunsten der Fläche zulässiger Ursprünge (HP04).
- Nutzer: „commit und pushe“ – zwei Commits, `4423903` (offene Hand-off-Dokumente der Vorsession) und `98fce8f` (H2), auf `main` gepusht. CI-Lauf 35427795221 war bei Abschluss noch in Arbeit.

**Ohne Dateiänderung**
- Browserprüfung am lokalen Stack (Französisch und Deutsch, Grundstück AD 65 über die Katasterreferenz): Typkarten, Typwahl, Schnellstellung „Près de la rue“ (Straße 5,00 m), Drehen, Ziehen mit dem Zeiger, Grenzschalter. Dabei gefunden und behoben: „2,99 m von 3,00 m“ (HP11), Schwenken um die Ecke beim Drehen (HP19), Hinweise auf jeder Karte wiederholt. Alles in Plan 10.1.
- Lokaler Stack neu gebaut (Migration 0009 angewendet), Flag `configurator` für `architect` gesetzt, drei `demo_*`-Typen in der lokalen Datenbank (zusätzlich zu den zwei H1-Testtypen `ligne`, `plateau`).
- Vollständiger Backend-Lauf: 362 Tests, ruff, mypy grün; Frontend: 91 Tests, Typprüfung und Lint grün.
- Nicht gelaufen: Playwright (E2E). Nicht im Browser gesehen: ein gesperrter Typ mit echten Regeln, Ziehen per Berührung, Grundstück mit mehreren Zonen.

**Unverändert:** `BACKEND_SPEZIFIKATION.md` (S1–S14 weiter offen), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `docs/PLAN_G3_BAURAHMEN.md`, `docs/PLAN_A_ANFRAGE.md`.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Umgang mit einem Auftrag für ein ganzes Release; getrennte Commits).

---

## 18.09.2026 – H1: Katalogpflege-Oberfläche

**Commits:** `df4fa3d`, Hand-off `4423903`; CI-Lauf 35398360953 grün.

**Umfang:** Büro-Oberfläche `/buero/katalog` in `frontend/src/pages/buero/katalog/` (Typenliste mit Import XLSX + DXF, Typstand, Linien und Optionen, Preise; 11 Tests) und `frontend/src/katalog/` (Kanten, Vorschlag der Fassadenrollen, Platzierung mit 8 Tests; Grundriss mit Rollen, Eingang, Garagentor; Axonometrie nach Plan H1 3.6, clientseitig; Formulare für Rollen, Lage, RE2020, Grundriss-PDF); `frontend/src/api/catalog.ts`; Routen, Navigation, Übersetzungen `catalog.*` in beiden Sprachen. Backend: `TypeSummaryOut.versions`, `GET .../lines` und `.../options` mit allen Versionen, `PackageIn.included_option_slugs` (unbekannte Option `422 catalog_reference_unknown`), Katalogtests jetzt 13. ANNAHMEN H10–H14, Plan-Statuszeilen.

**Entschieden**
- Nutzer: „erstelle erst eine Oberfläche für H1 – beachte alle Vorlagen und Vorgaben“; keine Rückfragen nötig, Plan H1 4.4/5 galt. Festlegungen der Umsetzung als Annahmen H10–H14 (nicht ausdrücklich bestätigt): Format `{edge, position}` für Eingang/Garagentor, links/rechts von der Straße aus gesehen, schematische Axonometrie, Umfang der Oberfläche.
- Nutzer: „comitten und pushen“.

**Ohne Dateiänderung**
- Browserprüfung am lokalen Stack (Deutsch und Französisch): Import zweier Beispieltypen über das echte Formular (Rechteck `ligne`, L-Form `plateau`), Fassadenrollen-Vorschlag und Speichern, Eingang und Garagentor, Option `pv` und Linie `confort` (mit `enthalten_in`) angelegt und veröffentlicht, RE2020-Befund gespeichert und im Preiskatalog sichtbar, `ligne` veröffentlicht und gesperrt, Fehlermeldung bei ungültiger XLSX. Testdaten bleiben im lokalen Stack.
- Beim Bau gefunden: Entwürfe standen in keiner Liste (H11), `enthalten_in` war über die API nicht pflegbar (H12), die Rollenvorschläge übersahen bei der L-Form die zweite Gartenkante (jetzt jede Gegenkante = Garten).
- Import von `plateau` (Flachdach): Neigungsprüfung entfällt, nur der Raumflächen-Hinweis erscheint (Plan H1 3.5); die 75–95 %-Warnung trifft beide Beispieltypen, weil die Beispielräume kurz sind (aus HANDOFF `4423903`).
- Nicht gelaufen: Playwright, die vollständige Backend-Suite (nur Katalog- und Domänentests, ruff und mypy über alles).

**Memory:** unverändert.

---

## 18.09.2026 – A Anfrage: Plan und Umsetzung (Backend und Frontend)

**Commits:** `d66ee11`, Hand-off `6fae882`; CI-Lauf 35389397303 grün.

**Umfang:** `docs/PLAN_A_ANFRAGE.md` (Plan mit Selbstprüfung); `backend/app/inquiry/` (Kontakt, Codebestätigung, Snapshot, Export, Löschung, Büro-Sicht, vorläufige Rechtstexte fr/de in `texts.py`); Migration `0008_inquiry.py` (`customer`, `inquiry`, `consent`, Sequenz `inquiry_number_seq` mit eigenem `GRANT`, Trigger `consent_append_only`/`consent_no_truncate`); 12 Integrationsfälle. Frontend: Kundenstrecke (`AnfrageFormular.tsx`, `DatenschutzAktionen.tsx`, 3 Tests), Büro-Liste mit Statusfilter und Detailseite (`Anfragen.tsx`, `AnfrageDetail.tsx`). Geändert: `review_queue(require_inquiry=True)` (G21), Büro-Routen für den Steckbrief, `legal.publish()`, `rate_limit.check_value`, CLI `legal-seed`, `email-validator`. ANNAHMEN AF01–AF12, BETRIEB 11, Plan 3.6.

**Entschieden**
- Nutzer: „setze modul A um“ – Empfehlungen des Plans gelten als entschieden (`feedback-plan-dann-umsetzen`): Steckbrief nur als Link (kein Mailanhang), Löschung nach einer Anfrage gesperrt (`409`, D6 offen), vorläufige Rechtstexte selbst entworfen. Alle als Annahmen AF01–AF05, keine ausdrückliche Bestätigung des Nutzers.
- Nutzer: „comitte und pushe“.

**Ohne Dateiänderung**
- Beim Bau gefunden und behoben: fehlender `GRANT` auf die neue Sequenz (`permission denied for sequence`, AF07); zwei G1-Tests setzten Projekte ohne Anfrage voraus (angepasst); `unwrap` erwartet Nutzdaten und scheitert an `204` (Löschroute umgangen).
- Browserprüfung: Kontakt → Code aus Mailpit → Bestätigung → `EMP-2026-000001` → Büro-Liste → Detail → Statuswechsel → Export. Die Löschung mit `window.confirm` ließ sich im Browser nicht auslösen (Dialog abgebrochen); nur im Backend-Test geprüft.
- Beim Handoff aufgefallen: Adressen außerhalb des Einzugsgebiets haben keine Anfragestrecke, der Hinweis `site.outside` verspricht sie (AF11, Plan A 3.6).
- E2E (Playwright) lokal nicht gelaufen; die CI war grün.

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Commit und Push nur auf Aufforderung).

**Hand-off:** erledigt „Modul A nachholen?“ und der Neubau des lokalen Stacks (Migrationen 0007, 0008); neu offen: AF11, AF12 (Zugangslink, Antwortvorlage), endgültige Rechtstexte, Büro-Postfach, Test zur Aufbewahrung (AF10), Abstimmung mit dem Büro zur Anfragebearbeitung.

---

## 18.09.2026 – H1 Hauskatalog: Plan und Backend-Umsetzung

**Commits:** `596e075`, Hand-off `25bcf64`; CI-Lauf 35308790615 grün.

**Umfang:** `docs/PLAN_H1_HAUSKATALOG.md` (fachliche Festlegungen: XLSX/DXF-Erfassung ohne IFC, Konsistenzprüfung, Preismodell, Veröffentlichungszustände; Anhang Kapitel 12 mit den neu erarbeiteten Typen Carré und Attique, gegen `REGELWERK`/`BEBAUBARE_FLAECHE` aus dem Mockup geprüft). `backend/app/catalog/` (`domain/`: `tolerances`, `consistency` – Neigungsprüfung nur `gable`/`hip`, Raumflächen-Warnschwelle; `xlsx` – Typdatenblatt mit drei Blättern; `dxf` – Umriss aus zwei Layern; Modelle als Identität + Version; API nur `/admin/catalog/...`), Migration `0007_catalog.py` mit bedingtem Trigger `forbid_published_modification`, Tests (18 Domänen-, 10 Integrationsfälle). Abhängigkeiten openpyxl, ezdxf, python-multipart. Plan: D14 (Kapitel 9), Ergänzung zu A (2.1, 3.6). ANNAHMEN H01–H09.

**Entschieden**
- D14: Modul A (Anfrage direkt nach G3, ohne Konfiguration) bleibt dauerhaft als Notausgang bestehen, auch mit gültigem Baurahmen und nachdem H1–H3 und V den vollständigen Weg anbieten.
- H1-Plan Kapitel 9 Punkt 1: Start mit fünf Platzhalter-Typen statt drei (Nutzer: „erarbeite 5 Mockup Typen“).
- H1-Plan Kapitel 9 Punkt 2: zunächst „architect ist okay“, beim Umsetzen um die Rolle `catalog_admin` ergänzt (H01, am 19.09. richtiggestellt) – vom Nutzer nicht gesondert bestätigt.
- H1-Plan Kapitel 9 Punkt 3: Grundriss-PDF bleibt rein intern in H1 (Nutzer: „ja“).
- Nutzer: „Setze H1 um“ – Empfehlungen des Plans gelten als entschieden (`feedback-plan-dann-umsetzen`). Nutzer: „push it“.

**Ohne Dateiänderung**
- Nachgeholte CI-Prüfung für den laut HANDOFF fälschlich als „nicht gepusht“ vermerkten Stand `11a6e64`/`a37e76d` (G1 Weg E): schon gepusht, CI-Lauf 35258574782 grün; Vermerk korrigiert.
- Klärung auf Nachfrage: Es gibt kein Modul „G4“, die G-Kette endet bei G3; Modul-Landkarte (A, H1–H3, V, X2–X5) und Modul A im Detail erläutert.
- Nutzer erinnerte an die ursprünglich geplante Reihenfolge (Kunde konfiguriert frei, Anfrage erst am Ende) – mit dem Gesamtablauf der Spezifikation (3.4) abgeglichen und für R2 bestätigt; daraus D14.

**Hand-off:** erledigt Push-Punkt 5.1 (war schon erledigt, nur der Vermerk fehlte); neu offen: H1-Frontend und die fünf Platzhalter-Typen als echte XLSX/DXF-Dateien.

---

## 17.09.2026 – G1: Weg E, Grundstück frei zeichnen ohne Kataster

**Commits:** `11a6e64`, Hand-off `a37e76d`; Push zunächst nicht beauftragt (später gepusht, CI-Lauf 35258574782 grün).

**Umfang:** `backend/app/site/domain/manual.py` (Polygon aus `n − 1` bemaßten Kanten mit Länge und Azimut, letzte Kante schließt automatisch; Selbstüberschneidung, Mindest-/Höchstfläche und -kantenlänge), Migration `0006_manual_sketch.py` (`site.origin`, `site.address_label`), `SiteIn` mit `parcel_idus` oder `edges` wie `LookupIn._exactly_one`, `form_manual_site`, Sperre `site_origin_mismatch` (409); G3 liefert für `manual_sketch` sofort `status = unavailable, reason = manual_sketch`, **ohne** `rules_service.envelope_rules` (D13), Steckbrief `409 sheet_unavailable_manual_sketch`; Fehlertexte `problem.manual_polygon_invalid`, `problem.site_origin_mismatch`, `problem.sheet_unavailable_manual_sketch`. Frontend: `FreiesZeichnen.tsx` (Punkte auf freiem Raster, Kantenlängen mit Live-Vorschau, Adresse Pflicht), `manual.ts` mit Test, Umschalter „selbst zeichnen“, `ManuelleZeichnungAnsicht`, Texte `site.manual.*` und `site.notices.manual_sketch`. Backend 262 Tests, Frontend 40 Tests. Plan 3.3 (Zusatz), 7, 9 (D13), 10.4 (vier behobene Logikfehler, u. a. das überbestimmte Polygon); ANNAHMEN G26–G30.

**Entschieden**
- Nutzer: Idee zum freien Zeichnen ausarbeiten, in `UMSETZUNGSPLAN.md` (3.3) fassen, dann umsetzen – Empfehlungen gelten damit als entschieden: Zusatz zu G1 statt eigenem Modul, freies Koordinatenraster ohne Kartenbezug, Adresse Pflicht.
- Nutzer: „so viel wie möglich lokal, keine Drittanbieter“ – auf Nachfrage präzisiert: Mailversand (E2) darf ein EU-Drittanbieter sein (Brevo/Scaleway TEM), kein Eigenbetrieb; die Claude API ist als Kernfunktion ausgenommen. Betrifft nur die Abwägung künftiger Infrastrukturentscheidungen; welcher Anbieter (E2), bleibt offen.
- Nutzer: committen; Push nicht beauftragt.

**Ohne Dateiänderung:** Browserprüfung von Weg E am lokalen Stack (Zeichnen, Bemaßen mit Live-Vorschau, Absenden, Ergebnisansicht, Selbstüberschneidung vom Server abgelehnt, Deutsch/Französisch). Zwei Befunde noch in der Session behoben: Label „Surface (cadastre)“ für ein Grundstück ohne Kataster (jetzt eigenes Label), ungerundete Klickkoordinaten in den Bemaßungsfeldern (jetzt 0,1 m/0,1°).

**Memory:** `project-hosting-unraid` präzisiert (Mail als EU-Drittanbieter akzeptiert, Claude API ausgenommen von „keine Drittanbieter“).

**Hand-off:** aus der vorigen Fassung nichts erledigt; neu: D13 (H2 ohne Baurahmen für Weg E), Weg E durch das Büro oder echte Kunden ausprobieren lassen.

---

## 16.09.2026 – G3 Baurahmen: Plan und Umsetzung

**Commits:** `2dfbc88` (G3), `b8cae60` (Nacharbeiten); CI vollständig grün.

**Umfang:** `docs/PLAN_G3_BAURAHMEN.md` (Plan mit Stand der Umsetzung in Abschnitt 12). `backend/app/envelope/` (`domain/`: `inputs`, `setbacks`, `bands`, `heights`, `overlays`, `local`, `derive`, `tolerances`; `ENGINE_VERSION g3-1.0.0`; Job `envelope_sheet`, `sheet.py` mit HTML und Lageplan-SVG), Migration `0005_envelope.py` (`envelope_sheet`), Tests (24 Einheits-, 13 Integrationsfälle). Frontend `frontend/src/envelope/` (Tabelle, Lageplan, Fixture aus der echten API-Antwort für AD 65); Baurahmen zwischen Grundstück und Regeln, Regeln als Herleitung; E2E um Baurahmen und Steckbrief. G2: Parameter `setback_street.band`, `PROMPT_VERSION g2-prompt-3`, `ENGINE_VERSION g2-1.2.0`, `envelope_rules`/`resolve_rules` mit derselben Auswahl wie `project_rules`; G1: `envelope_site`; CLI `envelope-check`; WeasyPrint mit Pango und DejaVu im `Dockerfile`. ANNAHMEN BR01–BR15, BETRIEB 10, Unraid README (heute Abschnitt 9), Plan 3.5 und Kapitel 7 (vier neue Abweichungen).

**Entschieden**
- Nutzer: G3 nach dem Plan umsetzen; die Empfehlungen zu E-G3-1 bis E-G3-4 gelten damit als entschieden – Teilflächen ohne Regeln nicht bebaubar, Wirkung der CNIG-Vorgaben, G2-Erweiterung vor dem API-Schlüssel, Steckbrief in G3.
- Nutzer: committen und pushen.

**Ohne Dateiänderung**
- Messung mit `envelope-check` über 200 Parzellen der Zone Uh (BR12, BR07): 0 Ausnahmen, 0 ungültige Geometrien, 133 `ok`, 42 `partial`, 25 `unavailable`, Median 75 ms, p95 122 ms.
- Browserprüfung des Kundenpfads (Zone Uh, AD 65): Tabelle, Lageplan mit beiden Konturen, Bauband, Hinweise, Steckbrief. Die gespeicherte Auswertung stammt aus der Zeit vor dem Parameter `band` und zeigt deshalb zu Recht `band_unclear` (826 m² weiteste, 211 m² engste Auslegung).
- Zwei Befunde aus Ende-zu-Ende-Läufen behoben: Der Steckbrief-Job übersprang jeden Auftrag mit veralteter Prüfsumme und kam nie zum Ziel, solange das Gelände noch eintraf; die Oberfläche verlangte für jeden Versuch einen neuen Klick (BR10).
- Verworfen: Heuristik für das Bauband nach Banddicke statt eines Parameters in G2 (Plan G3 11.2).
- Spezifikation: Anpassungen S1–S14 weiter offen; die vier neuen Abweichungen stehen in Plan 7.

**Memory:** `feedback-plan-dann-umsetzen` neu.

**Hand-off:** erledigt alle G3-Punkte (Zonenstatus und Warnungen, Vorrang spezifischer Regeln, Wirkung überlagernder Vorgaben, Standard-Geschosshöhen, Abstände `unknown` markieren, unsichere Straßenkanten). Offen blieben API-Schlüssel, Unraid, Spezifikationskorrekturen und die Oberflächenprüfung der Büro-Knöpfe aus G2.

---

## 14.09.2026 – Prüfung von G1 und G2 und Behebung aller 23 Befunde

**Commits:** `13092f9` (Nacharbeiten), Hand-off `b2545db` und `7c426bd`; CI am 15.09.2026 vollständig grün.

**Umfang:** Migration `0004_rules_robustness.py` (nur neue Spalten: Rückfall-Planstand je Gemeinde, Version der Schranken je Kapitel, Teil je Aufruf; Status `multiple_regulations`). G2: verschärfte Zitatprüfung (`text.py`, RW24, RW25), Gegenprüfung statt zweier gleicher Läufe (`assess.py`, `claim_for`, `verify`, RW19), Aufrufe in Teilen mit Wiederverwendung, Aufteilung bei `max_tokens`, Budget vor jedem Aufruf, Zeitbudget (`extract.py`, RW22, RW26), Planstand am Ort aktualisieren und Rückfall (`plan_import.py`, RW20, RW21, RW23), Kunden sehen den vorigen Planstand als `outdated`, `zone_coverage_incomplete`, Korrekturvorrang, Job `rules_housekeeping` (stündlich), `rules_extract` bis 5 Versuche, `ExtractIn.force` Standard `false` (RW27); `ENGINE_VERSION g2-1.1.0`, `PROMPT_VERSION g2-prompt-2`. G1: Hauptstraße nach Sicherheit, dann Länge (`edges.py`, `ENGINE_VERSION g1-1.1.0`, G23), `site_enrich` endet nie auf `pending`, Achsen bleiben bei unplausibler Antwort, Adress-Cache nur im Arbeitsspeicher (G22, G24, G25). Frontend: jeder Parameter mit Wert, Status „veraltet“, Warnungen mit Anteil, Büro-Knöpfe „Erneut versuchen“ (ohne `force`) und „Neu auswerten“ (mit Rückfrage), alte Regeln nach Parzellenwechsel verwerfen. `unit/test_rules_domain.py` neu gegliedert (Befunde A1–A4, E15, E19, F22), `rules_support.py`: `FakeExtractor` bildet Gegenprüfungen. Backend 196 Tests, Frontend 26 Tests. ANNAHMEN G22–G25, RW19–RW27; BETRIEB 8, 9; Unraid README (heute Abschnitt 9).

**Entschieden:** Nutzer: alle 23 Befunde mit den vorgeschlagenen Lösungsansätzen umsetzen. Daraus die Abweichung vom Plan 3.4: Gegenprüfung statt zweitem gleichem Lauf (RW19).

**Ohne Dateiänderung**
- Prüfung von G1 und G2 mit 23 Befunden in sechs Gruppen (A Zitatprüfung, B Datenverlust/hängende Zustände, C Kanten, D Kosten, E Anzeige/Planerkennung, F Kleines); jeder steht als Annahme (G22–G25, RW19–RW27) und als Test.
- Im API-Container nachgestellt (vor der Behebung): „… 2 m“ belegte 2 m gegen Text 5 m; Zitat ohne „ne … pas“ Ähnlichkeit 0,961 und `allow_on_boundary` wirksam; `not_regulated` mit beliebigem Satz; Wert des Sektors Uba für Ub belegt; `min_m 0,5` über „H/2“; Hauptstraße = 20-m-Kante mit Sicherheit 0,55 statt 12-m-Front mit 0,95. Verworfen: Verdacht, schmale Grundstücke bekämen zu wenige Geländestichproben (nachgestellt, trifft nicht zu).
- Lokaler Stack neu gebaut, Migration 0004 auf den Daten von Treillières: Abdeckung und Regeln vorhandener Grundstücke fehlerfrei, Kapitelgrenzen mit der neuen Inhaltsverzeichnis-Logik unverändert (12 Kapitel), `rules_housekeeping` läuft.

**Hand-off:** aus Abschnitt 4 nichts erledigt (die Punkte hängen am API-Schlüssel und an Unraid); 4.1 Punkt 1 vereinfacht: Kapitel werden nach Eintragen des Schlüssels automatisch ausgewertet. Auf Wunsch committet und gepusht. Der rote Lauf des vorigen Hand-off-Commits `8cf8a27` war ein Netzfehler beim Caddy-Bau im Security-Job.

---

## 14.09.2026 – G2 Regelwerk als automatische Simulation (Session `building-configurator-a7`, Fortsetzung)

**Commits:** `a59911d` (Plan D11), `91e84f6` (G2), Hand-off `8cf8a27`; CI grün.

**Umfang:** `backend/app/rules/` (Regelarten mit Plausibilitätsgrenzen, Zitat- und Zahlenprüfung, Kapitelsuche, Prompt und Ausgabeschema, Schranken und Abgleich zweier Läufe; `pdf.py` mit pypdf, `plan_import.py`, `extract.py`, Jobs `plu_import` wöchentlich und `rules_extract`), Adapter `gpu.py` (API Carto GPU, Dokumente, Dateien) und `claude.py` (Streaming, strukturierte Ausgabe, Kosten), Migration `0003_rules.py` (Planstände, Planunterlagen, Seiten, Zonen, Vorgaben, Kapitel, Läufe, Regelwerke, Regeln mit UPDATE-Sperre, Projektkorrekturen), Tests mit `fixtures/rules/` und `e2e_seed_rules.py`. Frontend: Anzeige als Simulation, Büro `Regeln.tsx`, Regeln und Korrektur je Projekt, E2E `rules.spec.ts`. CLI `plu-import`, `rules-extract`; `site_footprint` für andere Module; Abhängigkeiten anthropic, pypdf; Compose, Unraid-Stack, CI (E2E spielt Planstand und Auswertung ein). Plan für D11 überarbeitet: Grundsatz 7, 2.1–2.3, 3.1, 3.4 neu, 3.5, 3.6, 3.8, 3.10, 3.11 (X1 entfällt), 4.2, 5, 6.2–6.11, 7, 8, 9 (D9 entfällt, D11 entschieden, D12 neu), Prüfprotokoll 10.3. ANNAHMEN RW01–RW18, BETRIEB 9.

**Entschieden:** D11 – G2 darf nicht auf Eingaben des Büros angewiesen sein; das Ergebnis ist eine nicht kontraktuelle Simulation; das Büro prüft erst nach der Kontaktaufnahme.

**Ohne Dateiänderung**
- GPU live geprüft: Treillières gehört zum PLUi Erdre et Gesvres (`DU_244400503`); am Gemeinderand kommen Zonen von Nantes Métropole mit; Dateien unter `data.geopf.fr/annexes/gpu/documents`; `urlfic` verweist teils auf ältere Stände (RW01, RW02).
- Zitatprüfung am echten Text: Ähnlichkeit allein ließ einen falschen Zahlenwert als belegt durch; Zahlenprüfung ergänzt (RW07).
- Live-Import ohne Schlüssel und Browserprüfung (Kundenseite, Abdeckung, Regelwerk, Korrektur je Projekt); behobene Anzeigefehler: zentrierte Zeilenköpfe, feste Seitenabkürzung, Reihenfolge, überholter Hinweistext, Beschriftung „wirksam“.
- Selbstprüfung: doppelte Auswertung eines laufenden Kapitels, Wiederholung nach Absturz, Hinweise auf Englisch; behoben (RW08, RW12).
- Spezifikation: Anpassung an D11 als S14 offen (heute Spez. Anhang E.4).

**Memory:** `feedback-pruefung-erst-bei-anfrage` um D11 erweitert.

**Hand-off:** erledigt Commit-Entscheidung (nach dem Hand-off committen und pushen) und G2; neu offen: Schlüssel der Claude API, Referenzmenge, G2 auf Unraid, S14.

---

## 14.09.2026 – G1 Grundstück (Session `building-configurator-a7`, parallel zu R0/Unraid)

**Commits:** `c606387` (R0-Nacharbeiten), `cc48386` (G1), `50c6bc7` (CI), `dcef07a` (Images), Hand-off `e00f2a6`.

**Umfang:** `backend/app/site/` (Grundstück bilden, Kanten mit Nachbarparzellen und BD-TOPO-Straßenachsen einordnen, Gelände; Import je Gemeinde mit Plausibilitätsprüfung in `cadastre_import.py`; Jobs `site_enrich`, `cadastre_import` wöchentlich, `site_housekeeping`), Adapter in `backend/app/integrations/` (`http.py`, `geoplateforme.py`, `georisques.py`, `etalab_cadastre.py`, `ign_bdtopo.py`), Migration `0002_site.py` (`ref_*`, `site`, `parcel`, `site_edge`, `terrain`, `site_risk`, `geocode_cache`), Tests mit echten Daten von Treillières (`fixtures/site/`). Frontend: `Katasterkarte.tsx` (MapLibre 6), `frontend/src/site/` (Lageplan, Kantenliste, Parzellenwahl, Prüfansicht), Grundstücksseite, Büro-Prüfliste `Grundstuecke.tsx`, E2E `site.spec.ts`; `PlanSvg`, CSP für `data.geopf.fr` und `worker-src 'self'`. CLI `cadastre-import`, `flag-set`; HTTP-Bibliotheken ohne URL-Logs. ANNAHMEN G01–G21, BETRIEB 8, README, Unraid README. Plan: 3.3 Abnahme ohne Testmenge, 3.6 Grenzprüfung bei Anfrage, 8 Testmenge gestrichen, 9 D1 und D2; danach G2 für D11 überarbeitet (Eintrag oben).

**Entschieden**
- D1 – Bis zur Beta nur Treillières (44209).
- D2 – G1 intern für die Rolle `architect` freigeschaltet; Beta und öffentlich offen.
- Einordnung von Lotissement-Straßen (eigene Parzelle = Straße), Eck- und Pfeifenstielgrundstücken bestätigt.
- Keine Abnahme-Testmenge von 40 Grundstücken; der Architekt prüft die Grenzen erst beim Eingang einer Anfrage (Modul A).
- D11 – G2 darf nicht auf Eingaben des Büros angewiesen sein; Regeln entstehen automatisch, das Ergebnis ist eine nicht kontraktuelle Simulation; das Büro prüft erst nach der Kontaktaufnahme.
- Commits getrennt nach R0-Nacharbeiten und G1. Repository: privates GitHub-Repo `DieDaddelecke/building-configurator` als `origin`, `main` gepusht.
- Erster CI-Lauf: Backend (111 Tests), Frontend und E2E grün nach Korrektur von `ci.yml` (pnpm-Version, Trivy-Action per SHA). Trivy fand HIGH-Lücken in den Basis-Images → `backend/Dockerfile` mit Debian-Updates, `frontend/Dockerfile` mit selbst gebautem Caddy (A27). Danach alle CI-Jobs grün.

**Ohne Dateiänderung**
- Externe Dienste am 14.09.2026 live geprüft: Géoplateforme (Geokodierung, Höhen, WMTS, WFS BD TOPO), Etalab je Gemeinde (Stand 2026-06-01), Géorisques v1 ohne Token, v2 mit Token (G12, G13).
- Echte Daten: Die Regel ohne Straßenachsen versagt bei Lotissements; Stichprobe 300 Parzellen: Eckgrundstücke 38 % → 17 % nach neuer Regel, zwei Zeichnungsraster durchgesehen (G04, G05).
- Leistung lokal: Parzelle am Punkt p95 17 ms, Grundstück bilden p95 98 ms, Import Treillières 12 s (G20).
- Browsertest und E2E fanden Fehler: Parzellenwahl verlor Eingaben bei Projektanlage, leere Umgebungsringe im Lageplan, Koordinaten in HTTP-Logs; behoben. Selbstprüfung: Doppelklick beim ersten Grundstück, unbegrenzter Adress-Cache, verrauschte Büro-Prüfliste; behoben.
- Lizenzen und Abfragegrenzen der Géoplateforme (G13, G17).
- Lokaler Stack `emprise` mit G1 neu gebaut, Treillières importiert, `site_selection` für `architect` gesetzt, im Browser geprüft.

**Memory:** `feedback-pruefung-erst-bei-anfrage` angelegt und um D11 erweitert; `project-hosting-unraid` um GitHub als Repository ergänzt.

**Hand-off:** auf Basis der Fassung der R0-Session neu geschrieben; erledigt D1, G1 abschließen, Prüfung der Kartendienst-Bedingungen.

---

## 14.09.2026 – R0 Plattform, Betrieb auf Unraid mit Authentik

**Commits:** `1f4b646` (Repository mit allen Dokumenten und R0); die Nacharbeiten danach (`storage-init`, `trusted_proxies`, Hinweis nach MFA-Einrichtung, `.gitignore`) in `c606387`.

**Umfang:** `backend/` als FastAPI-Plattform (Modul P): OIDC-Anmeldung Büro mit MFA-Prüfung, Rollen, Projekt-Cookie, CSRF, Zugriffsregel je Route (per Test erzwungen), Audit-Log und Rechtstexte unveränderlich, Job-Queue in PostgreSQL, Mail, S3, Feature-Flags, Rate-Limits, Fehler nach RFC 9457 auf fr/de, Gesundheitsprüfungen, CLI; Migration `0001`; 50 Tests. `frontend/`: Vite, React, TypeScript, Tailwind, i18n fr/de; Gestaltung, Planblatt und Maßketten aus dem Mockup; Startseite, Büro-Rahmen `/buero`; Caddy-Web-Container mit CSP; 7 Unit-Tests, 3 Playwright-Tests. `compose.yaml` (PostGIS, MinIO, Mailpit, OIDC-Testdienst, migrate, api, worker, web), CI und `renovate.json` (CI noch nie gelaufen), README, ANNAHMEN A1–A26, BETRIEB, `infra/README.md` und `infra/local/*`. `deploy/unraid/`: Emprise-Stack (PostGIS, SeaweedFS, migrate, api, worker, web, backup), `deploy.sh` mit Rückrollen, Authentik-Stack mit Blueprint, Anleitung. Plan: Status, D3 und D4; AGENTS: Stand, Dokumententabelle, Geltung des Plans für beauftragte Module; SKILL: Ort der Annahmen `docs/ANNAHMEN.md`.

**Entschieden**
- D3 – Hosting bis zur Beta selbst betrieben auf Unraid; vor öffentlichem R1 neu entscheiden.
- D4 – Eigener Identitätsdienst, kein Microsoft/Google; Authentik.
- R0 und G1 aus dem Plan beauftragt; der Plan als Ganzes bleibt Vorschlag.
- Vorläufige Adresse `https://building-configurator.aslani.work`; Reverse Proxy auf Unraid vorhanden.

**Ohne Dateiänderung**
- Procrastinate: transaktionale Job-Anlage mit psycopg 3 nicht belegbar → eigene Queue (A2).
- Authentik: `amr: mfa` nur mit bereits eingerichtetem Gerät; 2026 verlangt `grant_types`; Passkey ohne Passwort = `user` (A23–A25).
- SeaweedFS 3.97: Bucket, Versionierung, signierte URLs geprüft (A22).
- Selbstprüfung: `/ready` hätte nach Rückrollen 503 gemeldet → `migration_state` eingeführt (BETRIEB 2). Sicherung enthielt `spatial_ref_sys` → ausgeschlossen, Wiederherstellung fehlerfrei (BETRIEB 6).
- DNS 14.09.2026: `building-configurator.aslani.work` existiert noch nicht; `aslani.work` liegt bei Cloudflare.
- Parallele Session `building-configurator-a7` setzt G1 um; Dateien abgestimmt.

**Memory:** `project-hosting-unraid` angelegt (D3/D4, keine Microsoft-/Google-Dienste, Cloudflare-Hinweis).

**Hand-off:** `/handoff` erstmals als Befehl aufgerufen und ausgeführt.

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
