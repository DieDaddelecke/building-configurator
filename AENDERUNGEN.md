# Änderungsprotokoll

Neueste Einträge zuerst. Ein Eintrag je Session, geschrieben von `/handoff`. Der aktuelle Stand steht in [HANDOFF.md](HANDOFF.md).

---

## 18.09.2026 – A Anfrage: Plan und Umsetzung (Backend und Frontend)

**Neu**
- `docs/PLAN_A_ANFRAGE.md` – Plan des Moduls A mit Selbstprüfung (Prüfprotokoll 11): Ablauf, E-Mail-Code, Snapshot, Vorgangsnummer, Lotissement-Frage, Anfrage ohne Baurahmen, Zustände, Export und Löschung, Rechtstexte.
- `backend/app/inquiry/` – Modul A: `models.py` (`customer`, `inquiry`, `consent`), `schemas.py`, `service.py` (Kontakt, Codebestätigung, Snapshot, Export, Löschung, Büro-Sicht), `api.py`, `texts.py` (vorläufige Rechtstexte fr/de).
- `backend/migrations/versions/0008_inquiry.py` – Tabellen, Sequenz `inquiry_number_seq` (mit eigenem `GRANT`), Trigger `consent_append_only`/`consent_no_truncate`.
- `backend/tests/integration/test_inquiry.py` – 12 Fälle: Ablauf, beide Einwilligungen, falscher Code, Versuchsgrenze, Rate-Limit je E-Mail, Weg E, Export, Löschung vor und nach der Anfrage, Büro-Liste/-Detail/Status, Rollen.
- `frontend/src/api/inquiry.ts`, `frontend/src/inquiry/AnfrageFormular.tsx`, `DatenschutzAktionen.tsx`, `anfrageFormular.test.tsx` (3 Fälle) – Kundenstrecke.
- `frontend/src/pages/buero/Anfragen.tsx`, `AnfrageDetail.tsx` – Büro-Liste mit Statusfilter und Detailseite (Kontakt, Status, Baurahmen, Kanten, Regeln).

**Geändert**
- `backend/app/site/service.py` – `review_queue(require_inquiry=True)`: Grundstücks-Prüfliste zeigt nur Projekte mit Anfrage (G21).
- `backend/app/envelope/api.py` – `POST`/`GET /admin/projects/{id}/envelope/sheet` für das Büro; `frontend/src/api/envelope.ts`, `frontend/src/envelope/Baurahmen.tsx` – Steckbrief-Knopf auch für `rolle="architect"`.
- `backend/app/platform/legal.py` – `publish()` aus dem Endpunkt herausgelöst; `rate_limit.py` – `check_value` (Schlüssel je E-Mail); `config.py` – `office_email`, `inquiry_*`; `cli.py` – `legal-seed`; `main.py`, `migrations/env.py`, `locales/{de,fr}.json` (Mailvorlagen, Fehlertexte), `pyproject.toml`/`uv.lock` (`email-validator`), `openapi.json`, `tests/conftest.py`, `tests/integration/test_site.py` (Hilfe `stub_inquiry`, neue Aussage „ohne Anfrage unsichtbar“).
- `frontend/src/pages/grundstueck/GrundstueckSeite.tsx`, `pages/buero/BueroLayout.tsx`, `pages/buero/Grundstuecke.tsx` (Exporte `Detail`, `ProjektRegeln`, `Fehler`), `App.tsx`, `i18n/{de,fr}.json`, `api/schema.d.ts`.
- `UMSETZUNGSPLAN.md` (Status, Hinweis in 3.6), `AGENTS.md` (Stand, Dokumententabelle), `docs/ANNAHMEN.md` (Abschnitt „A – Anfrage“, AF01–AF12), `docs/BETRIEB.md` (Abschnitt 11).

**Entschieden**
- Nutzer: „setze modul A um“ – Empfehlungen des Plans gelten als entschieden (`feedback-plan-dann-umsetzen`): Steckbrief nur als Link (kein Mailanhang), Löschung nach einer Anfrage gesperrt (`409`, D6 offen), vorläufige Rechtstexte selbst entworfen. Alle als Annahmen in ANNAHMEN AF01–AF05 festgehalten, keine ausdrückliche Bestätigung des Nutzers.
- Nutzer: „comitte und pushe“ – Commit `d66ee11` gepusht, CI-Lauf 35389397303 grün.

**Ohne Dateiänderung**
- Beim Bau gefundene und behobene Fehler: fehlender `GRANT` auf die neue Sequenz (`permission denied for sequence`, jetzt in Migration und ANNAHMEN AF07); zwei G1-Tests setzten Projekte ohne Anfrage voraus (angepasst); `unwrap` erwartet Nutzdaten und scheitert an `204` (Löschroute umgangen).
- Browserprüfung am lokalen Stack: Kontakt → Code aus Mailpit → Bestätigung → `EMP-2026-000001` → Büro-Liste → Detail → Statuswechsel → Export. Die Löschung mit `window.confirm` ließ sich im Browser nicht auslösen (Dialog wurde abgebrochen); nur im Backend-Test geprüft.
- Beim Handoff aufgefallen (jetzt in ANNAHMEN AF11 und PLAN_A 3.6): Adressen außerhalb des Einzugsgebiets haben keine Anfragestrecke; der Hinweis `site.outside` verspricht sie.
- E2E (Playwright) lokal nicht gelaufen; die CI war grün.

**Unverändert:** `BACKEND_SPEZIFIKATION.md` (S1–S14 weiter offen), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `docs/PLAN_H1_HAUSKATALOG.md`, `deploy/unraid/`, `platform/tasks.py` (Aufbewahrung greift über `status = 'submitted'`, AF10).

**Memory:** `feedback-plan-dann-umsetzen` ergänzt (Commit und Push nur auf Aufforderung).

**Hand-off:** HANDOFF.md neu geschrieben; aus der vorigen Fassung erledigt: „Modul A nachholen?“ (Abschnitt 3, 4.4, 5), H1 4.1 Punkt 5 (lokaler Stack neu gebaut, Migrationen 0007 und 0008 angewendet). Alle übrigen Punkte bleiben offen; neu: Anfrage außerhalb des Einzugsgebiets (AF11), Zugangslink und Antwortvorlage aus Plan 3.6 (AF12), endgültige Rechtstexte, Büro-Postfach, Test zur Aufbewahrung (AF10), Abstimmung mit dem Büro zur Anfragebearbeitung.

---

## 18.09.2026 – H1 Hauskatalog: Plan und Backend-Umsetzung

**Neu**
- `docs/PLAN_H1_HAUSKATALOG.md` – Plan des Moduls H1: fachliche Festlegungen (XLSX/DXF-Erfassung ohne IFC, Konsistenzprüfung, Preismodell, Veröffentlichungszustände), Architektur, Arbeitsschritte, Prüfprotokoll, Anhang mit den fünf Platzhalter-Typen (Kapitel 12: neu erarbeitet Carré und Attique, gegen `REGELWERK`/`BEBAUBARE_FLAECHE` aus dem Mockup geprüft).
- `backend/app/catalog/` – Modul H1: `domain/` (`tolerances`, `consistency` – Neigungsprüfung nur `gable`/`hip`, Raumflächen-Warnschwelle; `xlsx` – Typdatenblatt mit drei Blättern; `dxf` – Umriss aus zwei Layern), `models.py` (Typen/Linien/Optionen/Preiskatalog als Identität+Version), `schemas.py`, `service.py`, `api.py` (nur `/admin/catalog/...`, kein Kundenschritt).
- `backend/migrations/versions/0007_catalog.py` – neue Tabellen sowie der bedingte Trigger `forbid_published_modification` (blockt UPDATE/DELETE nur bei `status = 'published'`, L4).
- `backend/tests/unit/test_catalog_domain.py` (18 Fälle: XLSX-Schema, DXF-Umriss, Neigungsprüfung gegen alle fünf Platzhalter-Typen), `backend/tests/integration/test_catalog.py` (10 Fälle: Rollen, Import, Konsistenzsperre, Veröffentlichung inkl. Trigger per Rohzugriff, Preisübernahme, RE2020).

**Geändert**
- `UMSETZUNGSPLAN.md` – Entscheidung D14 (Kapitel 9), Ergänzung zu Modul A (2.1, 3.6): bleibt Notausgang neben dem Weg G3 → H2 → H3 → V.
- `AGENTS.md` – Dokumententabelle um `docs/PLAN_H1_HAUSKATALOG.md` ergänzt.
- `docs/ANNAHMEN.md` – Abschnitt „H1 – Hauskatalog“ (H01–H09), u. a. Rolle `catalog_admin` statt `architect`, RE2020 nicht im Typdatenblatt, Trigger-Entwurf.
- `backend/app/main.py`, `migrations/env.py`, `platform/locales/{de,fr}.json`, `pyproject.toml` (openpyxl, ezdxf, python-multipart), `uv.lock`, `tests/conftest.py` (neue Tabellen in `CLEAN_TABLES`), `openapi.json`, `frontend/src/api/schema.d.ts` – Verdrahtung, Abhängigkeiten, generierte Dateien.

**Entschieden**
- D14: Modul A (Anfrage direkt nach G3, ohne Konfiguration) bleibt dauerhaft als Notausgang bestehen, auch mit gültigem Baurahmen und auch nachdem H1–H3 und V den vollständigen Weg anbieten.
- H1-Plan Kapitel 9 Punkt 1: Start mit fünf Platzhalter-Typen statt drei (Nutzer: „erarbeite 5 Mockup Typen“).
- H1-Plan Kapitel 9 Punkt 2: zunächst „architect ist okay“ freigegeben, während der Umsetzung als Rechercheversehen erkannt und auf `catalog_admin` korrigiert (H01) – der Nutzer hat diese Korrektur nicht gesondert bestätigt, sie steht als Annahme im Protokoll.
- H1-Plan Kapitel 9 Punkt 3: Grundriss-PDF bleibt rein intern in H1 (Nutzer: „ja“).
- Nutzer: „Setze H1 um“ – Empfehlungen des Plans gelten als entschieden (`feedback-plan-dann-umsetzen`); Backend umgesetzt, committet (`596e075`).
- Nutzer: „push it“ – gepusht, CI grün (Lauf 35308790615).

**Ohne Dateiänderung**
- Nachgeholte CI-Prüfung für den zu Sessionbeginn bereits committeten, aber laut `HANDOFF.md` fälschlich als „nicht gepusht“ vermerkten Stand (`11a6e64`/`a37e76d`, G1 Weg E): tatsächlich schon gepusht, CI-Lauf 35258574782 grün; Vermerk in `HANDOFF.md` korrigiert.
- Klärung auf Nachfrage: Es gibt kein Modul „G4“, die G-Kette endet bei G3; Modul-Landkarte (A, H1–H3, V, X2–X5) und der Inhalt von Modul A im Detail erläutert.
- Nutzer erinnerte an die ursprünglich geplante Reihenfolge (Kunde konfiguriert frei, Anfrage erst am Ende) – abgeglichen mit dem Gesamtablauf der Spezifikation (3.4) und als für R2 weiterhin gültig bestätigt; daraus D14.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `docs/BETRIEB.md` (H1 hat keine Hintergrundjobs oder externen Dienste – Abschnitt folgt, sobald etwas Betriebliches zu dokumentieren ist), `deploy/unraid/`.

**Hand-off:** HANDOFF.md neu geschrieben; aus der vorigen Fassung erledigt: Push-Punkt 5.1 (war tatsächlich schon erledigt, nur der Vermerk fehlte). Alle Punkte aus 4.1–4.5 der vorigen Fassung bleiben offen und stehen unten erneut; neu hinzugekommen: H1-Frontend (Katalogpflege-Oberfläche) und die fünf Platzhalter-Typen als echte XLSX/DXF-Dateien.

---

## 17.09.2026 – G1: Weg E, Grundstück frei zeichnen ohne Kataster

**Neu**
- `backend/app/site/domain/manual.py` – Polygon aus `n − 1` bemaßten Kanten (Länge, Azimut) bauen und prüfen (Selbstüberschneidung, Mindest-/Höchstfläche und -kantenlänge); die letzte Kante schließt automatisch.
- `backend/migrations/versions/0006_manual_sketch.py` – Spalten `site.origin` (`parcel`/`manual_sketch`), `site.address_label`.
- `frontend/src/site/FreiesZeichnen.tsx` – Zeichen- und Bemaßungswerkzeug: Punkte auf freiem Koordinatenraster klicken, Kantenlängen mit Live-Vorschau bearbeiten, Adresse als Pflichtfeld.
- `frontend/src/site/manual.ts`, `manual.test.ts` – Geometrie fürs Frontend (Azimut, Punkte ↔ Kanten, Fläche), rein zur Vorschau; der Server prüft (L5).

**Geändert**
- `backend/app/site/schemas.py` – `SiteIn` nimmt entweder `parcel_idus` oder `edges` (+ `address_label` Pflicht dabei), wie `LookupIn._exactly_one`; `SiteOut` um `origin`, `address_label`.
- `backend/app/site/service.py` – `form_manual_site`, eigene schlanke `load_site`-Ausgabe für `manual_sketch` (keine Kanten, kein Gelände, keine Risiken, keine Umgebung); Sperre gegen Wechsel der Herkunft am selben Projekt (`site_origin_mismatch`, 409); `EnvelopeSite.origin` für G3.
- `backend/app/site/api.py` – `PUT …/site` verzweigt nach `edges`/`parcel_idus`.
- `backend/app/site/domain/tolerances.py` – `MANUAL_MIN_EDGES`/`MAX_EDGES`, `MANUAL_MIN_EDGE_M`/`MAX_EDGE_M`, `MANUAL_MIN_AREA_M2`/`MAX_AREA_M2`.
- `backend/app/envelope/service.py` – `build_envelope`/`project_envelope` liefern für `manual_sketch` sofort `status = unavailable, reason = manual_sketch`, **ohne** `rules_service.envelope_rules` aufzurufen (G2 entfällt, D13); `request_sheet`/`sheet_bytes` lehnen mit `409 sheet_unavailable_manual_sketch` ab.
- `backend/app/platform/locales/{de,fr}.json` – `problem.manual_polygon_invalid`, `problem.site_origin_mismatch`, `problem.sheet_unavailable_manual_sketch`.
- `frontend/src/api/site.ts` – `useFormManualSite`; `frontend/src/pages/grundstueck/GrundstueckSeite.tsx` – Umschalter „selbst zeichnen“, eigene schlanke Ergebnisansicht `ManuelleZeichnungAnsicht` (kein Baurahmen-/Regeln-Abschnitt für Weg E).
- `frontend/src/i18n/{de,fr}.json` – Texte `site.manual.*`, Hinweis `site.notices.manual_sketch`.
- `backend/openapi.json`, `frontend/src/api/schema.d.ts` – neu erzeugt.
- `backend/tests/unit/test_site_domain.py`, `integration/test_site.py`, `integration/test_envelope.py` – Domäne (Schließung, Selbstüberschneidung, Eigenschaftstest), Endpunkt, Zusammenspiel mit G3. Backend insgesamt 262 Tests, alle grün.
- `frontend/src/pages/grundstueck/grundstueck-seite.test.tsx` – Umschalter, Ergebnisansicht ohne Baurahmen/Regeln. Frontend insgesamt 40 Tests, alle grün.
- `UMSETZUNGSPLAN.md` – Zusatz zu 3.3 (Zweck, Umfang, Daten, Ablauf, Abnahme, Größe), Abweichung in Kapitel 7, offene Entscheidung D13 (Kapitel 9), Prüfprotokoll 10.4 (vier gefundene und behobene Logikfehler, u. a. dass ein vollständig bemaßtes Polygon mathematisch überbestimmt ist), Status im Kopf.
- `docs/ANNAHMEN.md` – Abschnitt „G1 – Weg E“ (G26–G30).

**Entschieden**
- Nutzer: Idee zum freien Zeichnen ausarbeiten, dann in `UMSETZUNGSPLAN.md` (3.3) fassen, dann umsetzen – Empfehlungen des Plans gelten damit als entschieden (`feedback-plan-dann-umsetzen`): Zusatz zu G1 statt eigenem Modul, freies Koordinatenraster ohne Kartenbezug, Adresse Pflicht.
- Nutzer: „so viel wie möglich lokal, keine Drittanbieter“ – auf Nachfrage präzisiert: Mailversand (E2) darf ein EU-Drittanbieter sein (Brevo/Scaleway TEM), kein Eigenbetrieb; die Claude API ist als Kernfunktion ausdrücklich ausgenommen. Betrifft nur die Abwägung künftiger Infrastrukturentscheidungen, E2 selbst (welcher Anbieter) bleibt offen.
- Nutzer: committen (`11a6e64`); Push nicht beauftragt.

**Ohne Dateiänderung**
- Browserprüfung von Weg E am lokalen Stack: Zeichnen, Bemaßen mit Live-Vorschau (Längenänderung aktualisiert Umriss und Fläche sofort), Absenden, Ergebnisansicht, Selbstüberschneidung vom Server abgelehnt, Deutsch/Französisch. Dabei zwei Befunde gefunden und noch in dieser Session behoben: Label „Surface (cadastre)“ für ein Grundstück ohne Kataster (jetzt eigenes Label), ungerundete Klickkoordinaten in den Bemaßungsfeldern (jetzt auf 0,1 m/0,1° gerundet).

**Unverändert:** `BACKEND_SPEZIFIKATION.md` (S1–S14 weiter offen), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `docs/PLAN_G3_BAURAHMEN.md`, `docs/BETRIEB.md`, `deploy/unraid/`.

**Memory:** `project-hosting-unraid` präzisiert (Mail als EU-Drittanbieter akzeptiert, Claude API ausgenommen von „keine Drittanbieter“).

**Hand-off:** HANDOFF.md neu geschrieben; aus der vorigen Fassung erledigt: nichts (Weg E kam als neue Idee dazu, nicht aus Abschnitt 4 der vorigen Fassung). Alle Punkte aus 4.1–4.5 der vorigen Fassung bleiben offen und stehen unten erneut; neu hinzugekommen: D13 (H2 ohne Baurahmen für Weg E, vor R2 zu entscheiden), Weg E im Browser durch das Büro/echte Kunden ausprobieren lassen.

---

## 16.09.2026 – G3 Baurahmen: Plan und Umsetzung

**Neu**
- `docs/PLAN_G3_BAURAHMEN.md` – Plan des Moduls G3 mit fachlichen Festlegungen, Architektur, Arbeitsschritten, Prüfprotokoll und Stand der Umsetzung (Abschnitt 12).
- `backend/app/envelope/` – Modul G3: `domain/` (`inputs`, `setbacks`, `bands`, `heights`, `overlays`, `local`, `derive`, `tolerances`; `ENGINE_VERSION g3-1.0.0`), `models.py`, `schemas.py`, `service.py`, `api.py`, `jobs.py` (`envelope_sheet`), `sheet.py` (HTML und Lageplan-SVG des Steckbriefs).
- `backend/migrations/versions/0005_envelope.py` – Tabelle `envelope_sheet` (Projekt, Prüfsumme, Speicherschlüssel).
- `backend/tests/` – `envelope_support.py`, `unit/test_envelope_domain.py` (24 Fälle: Parität, D4, D10, Bauband, Grenzbebauung, fehlende Werte, Zonen, Vorgaben, Höhen, Eigenschaftstests), `integration/test_envelope.py` (13 Fälle gegen PostGIS).
- `frontend/src/api/envelope.ts`, `frontend/src/envelope/` (`Baurahmen.tsx`, `BaurahmenPlan.tsx`, `format.ts`, `baurahmen.test.tsx`, Fixture aus der echten API-Antwort für AD 65).

**Geändert**
- `backend/app/rules/domain/kinds.py`, `extraction.py`, `__init__.py` – Parameter `setback_street.band` (`building` oder `facade`), Prompt dazu, `PROMPT_VERSION g2-prompt-3`, `ENGINE_VERSION g2-1.2.0`.
- `backend/app/rules/service.py` – `envelope_rules`/`resolve_rules`: dieselbe Auswahl von Planstand, Zonen und Korrekturen wie `project_rules`, zusätzlich Geometrie der Teilflächen und Vorgaben.
- `backend/app/site/service.py` – `envelope_site` als Eingabe für G3 (Umriss, Kanten, Gelände, Warnungen).
- `backend/app/cli.py` – `envelope-check` (Robustheitslauf über echte Parzellen, rollt jede Transaktion zurück).
- `backend/app/config.py` (Rate-Limits), `main.py`, `registry.py`, `migrations/env.py`, `platform/locales/*.json` (Steckbrief- und Baurahmentexte), `Dockerfile` (WeasyPrint mit Pango und DejaVu), `pyproject.toml`/`uv.lock` (weasyprint), `openapi.json`.
- `backend/tests/rules_support.py`, `unit/test_rules_domain.py`, `integration/test_rules.py` – `band` in der aufgezeichneten Antwort und in den Erwartungen.
- `frontend/src/pages/grundstueck/GrundstueckSeite.tsx` – Baurahmen zwischen Grundstück und Regeln; Regeln als aufklappbare Herleitung, sobald der Baurahmen sichtbar ist.
- `frontend/src/i18n/*.json`, `api/schema.d.ts`, `e2e/rules.spec.ts` (Baurahmen und Steckbrief im Kundenpfad).
- `docs/ANNAHMEN.md` (Abschnitt G3, BR01–BR15), `docs/BETRIEB.md` (Abschnitt 10), `deploy/unraid/README.md` (Abschnitt 11), `README.md`, `AGENTS.md`, `UMSETZUNGSPLAN.md` (Status, 3.5 „Umgesetzt“, Kapitel 7 mit vier neuen Abweichungen).

**Entschieden**
- Nutzer: G3 nach dem Plan umsetzen; die Empfehlungen des Plans zu E-G3-1 bis E-G3-4 gelten damit als entschieden – Teilflächen ohne Regeln nicht bebaubar, Wirkung der CNIG-Vorgaben, G2-Erweiterung vor dem API-Schlüssel, Steckbrief in G3.
- Nutzer: committen und pushen (`2dfbc88` G3, `b8cae60` Nacharbeiten); CI vollständig grün.

**Ohne Dateiänderung**
- Messung mit `envelope-check` über 200 Parzellen der Zone Uh: 0 Ausnahmen, 0 ungültige Geometrien, 133 `ok`, 42 `partial`, 25 `unavailable`, Median 75 ms, p95 122 ms. Die 25 ohne Baurahmen liegen in Zonen ohne ausgewertetes Kapitel (kein API-Schlüssel), die 42 ohne Fläche sind Parzellen von 10 bis 160 m². Werte stehen in ANNAHMEN BR12.
- Browserprüfung des Kundenpfads am lokalen Stack (Zone Uh, AD 65): Tabelle, Lageplan mit beiden Konturen, Bauband, Hinweise, Steckbrief. Die dort gespeicherte Auswertung stammt aus der Zeit vor dem Parameter `band` und zeigt deshalb zu Recht `band_unclear` (826 m² weiteste, 211 m² engste Auslegung).
- Zwei Befunde aus Ende-zu-Ende-Läufen behoben: Der Steckbrief-Job übersprang jeden Auftrag mit veralteter Prüfsumme und kam nie zum Ziel, solange das Gelände noch eintraf; die Oberfläche verlangte für jeden Versuch einen neuen Klick (ANNAHMEN BR10).
- Verworfen: Heuristik für das Bauband nach Banddicke statt eines Parameters in G2 – vor dem API-Schlüssel kostet die saubere Lösung nichts (Plan G3 11.2).

**Unverändert:** `BACKEND_SPEZIFIKATION.md` (Anpassungen S1–S14 weiter offen; die vier neuen Abweichungen stehen in Plan 7), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`.

**Memory:** `feedback-plan-dann-umsetzen` neu (Empfehlungen eines eigenen Plans gelten mit dem Auftrag zur Umsetzung als entschieden).

**Hand-off:** HANDOFF.md neu geschrieben; erledigt aus der vorigen Fassung: alle G3-Punkte aus 4.3 (Zonenstatus und Warnungen, Vorrang spezifischer Regeln, Wirkung überlagernder Vorgaben, Standard-Geschosshöhen, Abstände `unknown` markieren, unsichere Straßenkanten). Offen bleiben der API-Schlüssel (4.1), Unraid (4.2), die Spezifikationskorrekturen (4.4) und die Oberflächenprüfung der Büro-Knöpfe aus G2.

---

## 14.09.2026 – Prüfung von G1 und G2 und Behebung aller 23 Befunde

**Neu**
- `backend/migrations/versions/0004_rules_robustness.py` – nur neue Spalten: Rückfall-Planstand je Gemeinde, Version der Schranken je Kapitel, Teil je Aufruf; Status `multiple_regulations`.

**Geändert**
- `backend/app/rules/domain/text.py` – Zitatprüfung: Zahl nach Auslassung, Reihenfolge der Abschnitte, Verneinungswörter, Formeln für „nicht geregelt“, Prozent/Kehrwert nur je Parameterart (RW24, RW25).
- `backend/app/rules/domain/assess.py` – Sektor-Zuordnung über Satzteile, `not_regulated` nur mit Formel, Gegenprüfung (`claim_for`, `verify`) statt Abgleich zweier gleicher Läufe (RW19).
- `backend/app/rules/domain/extraction.py`, `kinds.py`, `chapters.py`, `__init__.py` – Schema und Aufgabe der Gegenprüfung, Prüfsumme über Prompts, Bauband bei Mindestabstand mit Obergrenze, Kapitelende trotz Artikeleinträgen, `ENGINE_VERSION g2-1.1.0`, `PROMPT_VERSION g2-prompt-2`.
- `backend/app/rules/extract.py` – Aufrufe in Teilen mit Wiederverwendung, Aufteilung bei `max_tokens`, Budget vor jedem Aufruf, Zeitbudget des Jobs, Neubewertung ohne Aufruf, kein Hängenbleiben auf `extracting` (RW22, RW26).
- `backend/app/rules/plan_import.py` – Planstand am Ort aktualisieren statt löschen (`--force`, geändertes Datum), Rückfall auf den vorigen Planstand, mehrere Reglement-Dateien nicht auswerten, `chapter_too_long` ohne Aufruf (RW20, RW21, RW23).
- `backend/app/rules/service.py`, `jobs.py`, `schemas.py`, `models.py` – Kunden sehen vorigen Planstand als `outdated`, Warnung `zone_coverage_incomplete` mit `uncovered_share`, Projektkorrektur spezifisch vor allgemein, Büro-Auswertung ohne Doppeljob, Job `rules_housekeeping` (stündlich), `rules_extract` bis 5 Versuche, `ExtractIn.force` Standard `false`.
- `backend/app/integrations/claude.py` (Gegenprüfung, SDK ohne Wiederholung), `gpu.py` (`regulation_files`), `georisques.py` (unerwartete Antwort als Dienstfehler).
- `backend/app/site/domain/edges.py`, `domain/__init__.py`, `service.py` – Hauptstraße nach Sicherheit, dann Länge; `ENGINE_VERSION g1-1.1.0` (G23).
- `backend/app/site/jobs.py`, `cadastre_import.py`, `api.py` – `site_enrich` endet nie auf `pending`, `site_housekeeping` räumt hängende Abfragen auf, unplausibel wenige Straßenachsen behalten die bisherigen, Adress-Cache nur im Arbeitsspeicher (G22, G24, G25).
- `backend/app/cli.py` (Hilfetexte), `backend/openapi.json`.
- `backend/tests/` – `unit/test_rules_domain.py` (neu gegliedert, Fälle A1–A4, E15, E19, F22), `unit/test_rules_integrations.py`, `unit/test_site_domain.py`, `unit/test_site_integrations.py`, `integration/test_rules.py` (Planstand erneuern, Rückfall, Aufteilung, Neubewertung, Abbruch, Zeitbudget, Wiederaufnahme, Abdeckung, Korrekturvorrang), `integration/test_site.py`, `rules_support.py` (`FakeExtractor` bildet Gegenprüfungen). Backend 196 Tests.
- `frontend/src/rules/format.ts` (jeder Parameter, nie leerer Wert), `RegelnSimulation.tsx` (Status „veraltet“, Warnungen mit Anteil), `pages/buero/Regeln.tsx` („Erneut versuchen“ ohne `force`, „Neu auswerten“ mit Rückfrage, Rückfall-Planstand), `api/rules.ts`, `api/site.ts` (alte Regeln nach Parzellenwechsel verwerfen), `i18n/*.json`, `api/schema.d.ts`, `rules/regeln.test.tsx`. Frontend 26 Tests.
- `docs/ANNAHMEN.md` – G22–G25, RW19–RW27, Verweise in G13, G21, RW06–RW08, RW11, RW12, RW18.
- `docs/BETRIEB.md` – Abschnitte 8 und 9 (Wiederaufnahme, Fehlergründe, Planstand erneuern, Rückfall).
- `deploy/unraid/README.md` – Abschnitt 10: Auswertung nach Eintragen des Schlüssels automatisch.
- `AGENTS.md`, `HANDOFF.md`.

**Entschieden**
- Nutzer: alle 23 Befunde der Prüfung mit den vorgeschlagenen Lösungsansätzen umsetzen. Daraus die Abweichung vom Plan 3.4: Gegenprüfung statt zweitem gleichem Lauf (RW19).

**Ohne Dateiänderung**
- Prüfung von G1 und G2 mit 23 Befunden in sechs Gruppen (A Zitatprüfung, B Datenverlust/hängende Zustände, C Kanten, D Kosten, E Anzeige/Planerkennung, F Kleines); stehen jetzt je als Annahme (G22–G25, RW19–RW27) und als Test.
- Im API-Container nachgestellt (vor der Behebung): „… 2 m“ belegte 2 m gegen Text 5 m; Zitat ohne „ne … pas“ Ähnlichkeit 0,961 und `allow_on_boundary` wirksam; `not_regulated` mit beliebigem Satz; Wert des Sektors Uba für Ub belegt; `min_m 0,5` über „H/2“; Hauptstraße = 20-m-Kante mit Sicherheit 0,55 statt 12-m-Front mit 0,95. Verworfen: Verdacht, schmale Grundstücke bekämen zu wenige Geländestichproben (nachgestellt, trifft nicht zu).
- Lokaler Stack neu gebaut, Migration 0004 auf den Daten von Treillières: Abdeckung und Regeln vorhandener Grundstücke fehlerfrei, Kapitelgrenzen mit der neuen Inhaltsverzeichnis-Logik unverändert (12 Kapitel), `rules_housekeeping` läuft.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `UMSETZUNGSPLAN.md` (Abweichung RW19 steht in ANNAHMEN), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `frontend/e2e/`.

**Hand-off:** HANDOFF.md neu geschrieben; aus der vorigen Fassung erledigt: nichts aus Abschnitt 4 (die Punkte hängen am API-Schlüssel und an Unraid). 4.1 Punkt 1 vereinfacht: Kapitel werden nach Eintragen des Schlüssels automatisch ausgewertet. Auf Wunsch des Nutzers committet und gepusht (`13092f9` Nacharbeiten, `b2545db` Hand-off); CI am 15.09.2026 vollständig grün. Der rote Lauf des vorigen Hand-off-Commits `8cf8a27` war ein Netzfehler beim Caddy-Bau im Security-Job (HANDOFF 6).

---

## 14.09.2026 – G2 Regelwerk als automatische Simulation (Session `building-configurator-a7`, Fortsetzung)

**Neu**
- `backend/app/rules/` – Modul G2: `domain/` (Regelarten mit Plausibilitätsgrenzen, Zitat- und Zahlenprüfung, Kapitelsuche, Prompt und Ausgabeschema, Schranken und Abgleich zweier Läufe), `pdf.py` (pypdf), `plan_import.py`, `extract.py`, `service.py`, `api.py`, `jobs.py` (`plu_import` wöchentlich, `rules_extract`), `models.py`.
- `backend/app/integrations/gpu.py` (API Carto GPU, Dokumente, Dateien), `backend/app/integrations/claude.py` (Claude API, Streaming, strukturierte Ausgabe, Kosten).
- `backend/migrations/versions/0003_rules.py` – Planstände, Planunterlagen, Seiten, Zonen, Vorgaben, Kapitel, Läufe, Regelwerke, Regeln (UPDATE gesperrt), Projektkorrekturen.
- `backend/tests/` – `unit/test_rules_domain.py`, `unit/test_rules_integrations.py`, `integration/test_rules.py`, `rules_support.py`, `e2e_seed_rules.py`, `fixtures/rules/` (GPU-Antworten, Textschicht des règlement, README).
- `frontend/src/api/rules.ts`, `frontend/src/rules/` (Anzeige als Simulation, Formatierung, Tests, Fixture), `frontend/src/pages/buero/Regeln.tsx`, `frontend/e2e/rules.spec.ts`.

**Geändert**
- `UMSETZUNGSPLAN.md` – G2 vollautomatisch als Simulation (D11): Grundsatz 7, 2.1–2.3, 3.1, 3.4 neu, 3.5, 3.6, 3.8, 3.10, 3.11 (X1 entfällt), 4.2, 5, 6.2–6.11, 7, 8, 9 (D9 entfällt, D11 entschieden, D12 neu), Prüfprotokoll 10.3; Status: G2 beauftragt.
- `backend/app/config.py` (GPU, Claude API, Budget, leere Schlüssel = nicht gesetzt), `cli.py` (`plu-import`, `rules-extract`), `main.py`, `registry.py`, `migrations/env.py`, `integrations/http.py` (POST, Zeitlimit je Aufruf), `site/service.py` (`site_footprint` für andere Module), `platform/locales/*.json`, `pyproject.toml`/`uv.lock` (anthropic, pypdf), `openapi.json`, `tests/conftest.py`.
- `frontend/` – `App.tsx`, `GrundstueckSeite.tsx`, `Grundstuecke.tsx` (Regeln und Korrektur je Projekt), `BueroLayout.tsx`, `BueroStart.tsx`, `GrundstueckPruefen.tsx` (`useNotices` exportiert), `i18n/*.json`, `schema.d.ts`.
- `compose.yaml`, `deploy/unraid/compose.yaml`, `deploy/unraid/.env.example`, `deploy/unraid/README.md` (Abschnitt 10), `.github/workflows/ci.yml` (E2E spielt Planstand und Auswertung ein).
- `docs/ANNAHMEN.md` (RW01–RW18), `docs/BETRIEB.md` (Abschnitt 9), `README.md`, `AGENTS.md`, `HANDOFF.md`.

**Entschieden**
- D11 – G2 darf nicht auf Eingaben des Büros angewiesen sein; das Ergebnis ist eine nicht kontraktuelle Simulation; das Büro prüft erst nach der Kontaktaufnahme.

**Ohne Dateiänderung**
- GPU live geprüft: Treillières gehört zum PLUi Erdre et Gesvres (`DU_244400503`); am Gemeinderand kommen Zonen von Nantes Métropole mit; Dateien unter `data.geopf.fr/annexes/gpu/documents`; `urlfic` verweist teils auf ältere Stände (RW01, RW02).
- Zitatprüfung am echten Text: Ähnlichkeit allein ließ einen falschen Zahlenwert als belegt durch; Zahlenprüfung ergänzt (RW07).
- Live-Import ohne Schlüssel und Browserprüfung (Kundenseite, Abdeckung, Regelwerk, Korrektur je Projekt); gefundene Anzeigefehler behoben (zentrierte Zeilenköpfe, feste Seitenabkürzung, Reihenfolge, überholter Hinweistext, Beschriftung „wirksam“).
- Selbstprüfung: doppelte Auswertung eines laufenden Kapitels, Wiederholung nach Absturz, Hinweise auf Englisch; behoben (RW08, RW12).

**Unverändert:** `BACKEND_SPEZIFIKATION.md` (Anpassung an D11 als S14 offen), `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`.

**Memory:** `feedback-pruefung-erst-bei-anfrage` um D11 erweitert.

**Hand-off:** HANDOFF.md neu geschrieben; erledigt aus der vorigen Fassung: Commit-Entscheidung (Nutzer: nach dem Hand-off committen und pushen; Commits `a59911d` Plan D11, `91e84f6` G2, CI grün), G2 umsetzen. Neu offen: Schlüssel der Claude API, Referenzmenge (HANDOFF 4.1), G2 auf Unraid, Anpassung der Spezifikation S14.

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
- `UMSETZUNGSPLAN.md` – 3.3 Abnahme ohne Testmenge, 3.6 Grenzprüfung bei Anfrage, 8 Testmenge gestrichen, 9 D1 und D2 entschieden. Danach **G2 überarbeitet (D11):** Grundsatz 7 „Simulation vor Prüfung“, 3.4 vollautomatische Regelauswertung per Claude mit Schranken statt Freigabe, 3.5 Standard-Geschosshöhen und `unknown`-Abstände, 3.6 Prüfung der Simulation bei Anfrage, X1 entfällt, Infrastruktur 6.x, Abweichungen 7 (Leitplanken L2/L6), Inhalte 8, D9 entfällt, D12 neu, Prüfprotokoll 10.3.
- `AGENTS.md` – Stand G1 und Entscheidungen.

**Entschieden**
- D1 – Bis zur Beta nur Treillières (44209).
- D2 – G1 intern für die Rolle `architect` freigeschaltet; Beta und öffentlich offen.
- Einordnung von Lotissement-Straßen (eigene Parzelle = Straße), Eck- und Pfeifenstielgrundstücken bestätigt.
- Keine Abnahme-Testmenge von 40 Grundstücken; der Architekt prüft die Grenzen erst beim Eingang einer Anfrage (Modul A).
- D11 – G2 darf nicht auf Eingaben des Büros angewiesen sein; Regeln entstehen automatisch, das Ergebnis ist eine nicht kontraktuelle Simulation; das Büro prüft erst nach der Kontaktaufnahme.
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

**Memory:** `feedback-pruefung-erst-bei-anfrage` angelegt und um D11 erweitert; `project-hosting-unraid` um GitHub als Repository ergänzt.

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
