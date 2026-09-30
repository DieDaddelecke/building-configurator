# Refactoring: Risiken und Rückrollen

> **Stand:** 29.09.2026 (zweite Fassung: R-34, R-60 bis R-70 für den Merge und Phase 3 ergänzt; R-01 bis R-51 beziehen sich auf die alten Nummern REF-…, die der Plan in S1–S26 aufgenommen hat). Risiken `R-…` gehören zu den Schritten `REF-…` in [REFACTORING_PLAN.md](REFACTORING_PLAN.md); Befunde `B-…` in [REFACTORING_ANALYSIS.md](REFACTORING_ANALYSIS.md).
> **Grundlage der Einschätzung:** Es gibt noch **keinen Produktivbetrieb** (Unraid nicht in Betrieb, HANDOFF 4.5). Lokal liegen Test- und Messdaten, darunter bezahlte Auswertungen und hochgeladene Reglements. Das senkt das Datenrisiko der Infrastrukturschritte deutlich – solange sie **vor** der Inbetriebnahme kommen.

## 1. Risikomatrix

Eintritt und Wirkung: LOW, MEDIUM, HIGH.

| Nr. | Schritt | Risiko | Eintritt | Wirkung | Gegenmaßnahme |
|---|---|---|---|---|---|
| R-01 | REF-001 | `worker-long` fehlt in einer Umgebung → lange Jobs bleiben liegen | MEDIUM | MEDIUM | `/health/jobs` meldet auch `long` (großzügige Schwelle); `deploy.sh` startet `worker-long` ausdrücklich; lokal bedient ein Worker beide Warteschlangen |
| R-02 | REF-001 | zwei Worker führen die Wartung doppelt aus | HIGH | LOW | bereits sicher: `ON CONFLICT`, `FOR UPDATE SKIP LOCKED`, Idempotenzschlüssel `periodic:<name>:<slot>` |
| R-03 | REF-001 | zwei gleichzeitige Auswertungen (je Worker eine) verdoppeln die Kosten je Zeit | LOW | MEDIUM | nur **ein** `worker-long`; das Monatsbudget (`rules_budget_month_usd`) und die Budgets je Organisation greifen unverändert |
| R-10 | REF-002 | Dateirechte: Container läuft als UID 10001, Volume gehört `root` | HIGH ohne Vorsorge | HIGH (kein Upload, keine PDFs) | Verzeichnis im Image mit Eigentümer 10001 anlegen (benanntes Volume erbt es); auf Unraid `chown 10001` im Einrichtungsschritt; `storage-init` schreibt eine Probe und bricht sonst ab; `/admin/ops/status` meldet `storage_ok` |
| R-11 | REF-002 | lokale Dateien gehen beim Umzug verloren (Reglements, Dossiers, Berichte) | LOW | MEDIUM (Neuauswertung kostet Geld; Zitat-PDFs fehlen) | nur kopieren, nicht löschen; Reglements über `sha256` im Schlüssel prüfen; SeaweedFS-Volume erst nach Kontrolle entfernen; `db`-Dump vorher |
| R-12 | REF-002 | späterer zweiter Rechner oder verwalteter Anbieter braucht S3 | MEDIUM (später) | LOW | Schnittstelle bleibt bei vier Funktionen; Auslöser dokumentiert (ARCHITECTURE 7) |
| R-13 | REF-002 | ohne Versionierung schützt nichts vor versehentlichem Überschreiben | LOW | LOW | Schlüssel sind unveränderlich (Prüfsumme oder eindeutige ID); Überschreiben kommt im Code nicht vor; Sicherung 14 Tage |
| R-14 | REF-002 | Sicherung: Appdata Backup kopiert während eines Schreibvorgangs | LOW | LOW | Schreiben atomar (`os.replace`); halbe Dateien heißen `.tmp-…` und werden beim Wiederherstellen ignoriert bzw. von `storage-init` entfernt |
| R-15 | REF-002 | Pfad-Traversal über einen manipulierten Schlüssel | LOW (Schlüssel entstehen im Server) | HIGH | Schlüssel prüfen (keine `..`, kein führender `/`, nur erwartete Zeichen), aufgelösten Pfad gegen `files_dir` prüfen; Unit-Test |
| R-20 | REF-003 | Referenzliste geht beim Export/Import verloren | LOW | MEDIUM (Prüfarbeit des Nutzers) | vor dem Umstellen alle Listen exportieren und als Datei ablegen; nach dem Import Anzahl Einträge und Status „geprüft“ vergleichen; `emprise_shared` erst danach löschen |
| R-21 | REF-003 | Produkte nutzen unbemerkt verschiedene Modelle | MEDIUM | LOW | Modell steht in `/verwaltung` und an jedem Auswertungslauf; BETRIEB-Eintrag „Modell in beiden Instanzen setzen“ |
| R-22 | REF-003b | Migration trifft vorhandene gemeinsame Tabellen mit abweichendem Stand | MEDIUM | MEDIUM | Migration prüft Existenz und Spalten; Test gegen eine Kopie der lokalen Datenbank mit `shared-migrate`-Stand |
| R-30 | REF-004 | Befehle in Doku, Hand-off und Gewohnheit veralten | HIGH | LOW | `grep -r "compose.analyse.yaml"` über alle Dokumente; README-Abschnitt „Lokal starten“ zuerst |
| R-31 | REF-005 | Information geht beim Archivieren von AENDERUNGEN verloren | LOW | MEDIUM | verschieben statt kürzen; Token-Vergleich (IDs, Zahlen, Pfade) gegen den Git-Stand |
| R-32 | REF-006 | zusammengesetzter Übersetzungsschlüssel doch in Gebrauch | MEDIUM | LOW (Schlüssel statt Text sichtbar) | nur nach Skriptprüfung und Einzelbestätigung löschen; `check-texte.test.ts`; Sichtprüfung der betroffenen Seiten |
| R-33 | REF-011 | Gestaltung, die nur im Mockup steht, geht verloren | LOW | LOW | Mockup bleibt als Datei; vorher Abgleich Mockup ↔ Frontend (Dokumentation.html als Liste) |
| R-40 | REF-007/008/009 | Konflikte mit parallelen Sessions an denselben Dateien | MEDIUM | MEDIUM | vor Beginn per `ListAgents` abstimmen (README-Stolperstelle); kleine Commits nur mit Verschiebungen |
| R-41 | REF-007/008 | zirkulärer Import durch neue Dateien | MEDIUM | LOW (fällt beim Import sofort auf) | Lesemodelle (`outputs.py`, `footprint.py`) ohne Rückimport des Service; `mypy` und voller Testlauf |
| R-42 | REF-010 | neuer Test meldet bestehende Routen | MEDIUM | LOW | begründete Ausnahmeliste im Test |
| R-50 | Phase 2 | Unraid geht vor Phase 2 in Betrieb | MEDIUM | HIGH (Datenumzug in Produktion) | Phase 2 als Voraussetzung in HANDOFF 4.5 eintragen |
| R-51 | alle | CI rot zu Beginn verdeckt neue Fehler | HIGH (heute) | MEDIUM | Vorbedingung 1 im Plan |
| R-34 | S26 | neue Session findet Stand und offene Punkte nicht mehr (HANDOFF/AENDERUNGEN entfallen) | MEDIUM | MEDIUM | ROADMAP trägt Stand und nächsten Schritt; `/handoff` und CLAUDE.md verweisen darauf; Probelesen wie eine neue Session |
| R-60 | S1 | Router, Job-Modul oder periodische Aufgabe fehlt nach dem Zusammenführen | LOW | HIGH | Vereinigung aus der bisherigen Liste; `test_module_boundaries.py` prüft Existenz und Eindeutigkeit; `openapi.json` unverändert |
| R-61 | S1 | abgelehnte Anmeldung landet für Analyse-Nutzer auf der Büro-Seite | MEDIUM | LOW | Ziel nach Bereich von `next`; Test |
| R-62 | S1 | anonyme Kunden erreichen Analyse-Funktionen mit Kosten | LOW | HIGH | ausgeschlossen: `require_owned_project` für Analyse und PLU-Upload; `test_access_policies.py` über alle Routen |
| R-63 | S2 | absolute Links im Analyse-Bereich zeigen auf den Konfigurator | MEDIUM | LOW | eigener Router mit `basename: "/analyse"`; Smoke-Test aller Analyse-Seiten |
| R-64 | S2 | CSS-Tokens (`--accent`) der Bereiche mischen sich | LOW | LOW | Wechsel zwischen den Bereichen per Neuladen; Analyse-CSS nur im Analyse-Chunk |
| R-65 | S3 | Befehle mit `compose.analyse.yaml`, Port 8180/8100 oder `EMPRISE_PRODUCT` in Doku und Gewohnheit | HIGH | LOW | Grep über alle Dateien; README zuerst |
| R-66 | S8 | Bericht und DXF ändern ihr Aussehen ohne Erscheinungsbild | HIGH | LOW | gewollt (Entscheidung); `REPORT_VERSION` erhöhen, falls Berichte schon ausgeliefert wären (lokal nicht) |
| R-67 | S8 | Entfernen des Bearer-Wegs öffnet oder schließt Routen ungewollt | LOW | HIGH | `test_access_policies.py`; CSRF-Ausnahme für Bearer entfällt mit; Tests für Sitzung und Cookie unverändert |
| R-68 | S12–S16 | Verhalten ändert sich beim Herauslösen reiner Funktionen | MEDIUM | HIGH | nur verschieben, Signaturen mit einfachen Daten; bestehende Tests unverändert grün; `envelope-check --commune 44209` vorher/nachher gleich |
| R-69 | S14 | Preise ändern sich beim Vereinheitlichen der Bruttoformel (unterschiedliche Rundung, B-65) | MEDIUM | HIGH | zuerst Test mit heutigen Werten; nur vereinheitlichen, wenn gleich, sonst Befund an den Nutzer |
| R-70 | S17 | gemeinsame Leseroutine ändert Seitentext und damit Kapitelerkennung oder Zitatprüfung | LOW | HIGH | gleiche Bibliothek (pypdf) und gleiche Aufrufe; `test_rules_upload.py`, `test_rules.py`; Vergleich der Seitentexte eines Beispiel-PDFs vorher/nachher |

## 2. Mögliche Regressionen je Bereich

| Bereich | Mögliche Regression | Wodurch erkannt |
|---|---|---|
| Jobs | Job landet in einer Warteschlange ohne Abnehmer; Zeitlimit greift nicht | `test_jobs.py`, Health-Endpunkt, BETRIEB „Jobs“ |
| Anfrage (A) | Code-Mail kommt trotzdem spät (Worker `default` durch anderen Job belegt) | lokaler Test mit laufender Auswertung; Mailpit |
| Dateien | PDFs nicht mehr lesbar, Zitat-PDF leer, Logo fehlt in Bericht und DXF | Integrationstests mit `memory_storage` decken die Logik, **nicht** das Dateisystem → neue Unit-Tests + Handprüfung (Bericht, Dossier, Zitat, Logo) |
| Löschung | Projekt gelöscht, Dateien bleiben (B-22) | Test zu `retention_cleanup` mit Dateien (REF-002 Schritt 7) |
| Verwaltung | Modellwahl oder Referenzlisten fehlen nach REF-003 | Handprüfung `/verwaltung` in beiden Produkten; `test_reference_lists.py`, `test_rules_model.py` |
| Regeln | andere Regeln nach Umbau von `rules/service.py` | Tests unverändert grün; `envelope-check --commune 44209` vorher/nachher gleich (BETRIEB 10) |
| Grundstück | andere Kanteneinordnung nach Umbau von `site/service.py` | `test_site.py`, `test_site_upload.py`, E2E `site.spec.ts` |
| OpenAPI | Schemanamen ändern sich durch Verschieben von Klassen | CI-Schritt „API-Typen aktuell“; `openapi.json` vorher/nachher vergleichen |
| Auth | neue Policy-Namen brechen `test_access_policies.py` oder Frontend-Verhalten | Test; keine Änderung am Prüfverhalten, nur am Namen |

## 3. Datenbankrisiken

| Risiko | Schritt | Bewertung | Maßnahme |
|---|---|---|---|
| Migration 0021 (Warteschlangen) | REF-001 | nur `UPDATE` wartender Jobs | Rückweg per `UPDATE … SET queue = 'default'` |
| Migration `DROP TABLE app_setting` | REF-006 | Datenverlust nur, wenn der Umzug nicht lief | vorher `SELECT` in jeder Instanz; Downgrade legt die leere Tabelle an |
| Migration 0022 (gemeinsame Tabellen) | REF-003b | vorhandene Tabellen übernehmen | Existenzprüfung, Test gegen Kopie |
| `DROP DATABASE emprise_shared` | REF-003 | endgültig | erst nach Export, Import und Kontrolle; `pg_dump` vorher |
| Abwärtskompatibilität beim Rückrollen per `deploy.sh rollback` | alle mit Migration | Plan 6.5: Migrationen nur erweiternd | 0021 und 0022 erweitern bzw. passen Daten an; ein älteres Image läuft mit dem neuen Schema weiter (Spalte `queue` existiert schon) |
| Zwei Worker, doppelte Verbindungen | REF-001 | +10 Verbindungen je Produkt (Pool 5 + 5) | PostgreSQL-Vorgabe 100 Verbindungen reicht |

## 4. Storage-Risiken

| Risiko | Bewertung | Maßnahme |
|---|---|---|
| Bisherige „gelöschte“ Dateien liegen als alte Versionen in SeaweedFS (B-21) | lokal Testdaten; auf Unraid nie in Betrieb | Befund in REF-002 Schritt 1 prüfen; beim Umzug werden nur **aktuelle** Objekte kopiert, das SeaweedFS-Volume danach gelöscht – alte Versionen verschwinden damit |
| Datenmenge wächst (PLUi 333 Seiten, Scans) | ein Reglement bis 100 MB, Dateien werden je Prüfsumme nur einmal gespeichert | Plattenplatz im Unraid-Array; Warnung über Uptime Kuma optional |
| Sicherung der Dateien | Appdata Backup deckt `${APPDATA_DIR}/files` | erste Wiederherstellungsübung mit einer Datei (HANDOFF 4.5 Nr. 5) |
| API und Worker auf verschiedenen Hosts | heute ausgeschlossen (Compose auf einem Host) | Auslöser für S3 (ARCHITECTURE 7) |

## 5. Auth-Risiken

| Risiko | Bewertung | Maßnahme |
|---|---|---|
| Vereinfachung schwächt Zugriffsschutz | kein Schritt entfernt eine Prüfung; REF-010 **verschärft** | Nicht-Vereinfachen-Liste im Plan 5 |
| Neue Dateien in `site`/`rules` (REF-007/008) verlieren eine Zugriffsregel | Zugriffsregeln hängen an den Routen in `api.py`, nicht an den Services | `test_access_policies.py` läuft über alle Routen |
| Organisationsprüfung per Pfadname (B-23) | bis REF-010 offen | README-Stolperstelle beachten; REF-010 früh in Phase 3 |
| Mandanten eingefroren, aber API-Schlüssel aktiv | Schlüssel nur für `/api/v1/projects`, Rate-Limit, fremde Büros gesperrt | unverändert lassen |
| Authentik-Anwendungen je Produkt | unverändert | – |

## 6. Migrationsrisiken (Reihenfolge)

| Risiko | Maßnahme |
|---|---|
| Phase 2 nach der Inbetriebnahme | R-50: Phase 2 ist Voraussetzung für HANDOFF 4.5 |
| REF-002 und REF-004 ändern dieselben Compose-Dateien | Reihenfolge REF-003 → REF-002 → REF-004 |
| Große Verschiebungen (REF-007/008) während paralleler Arbeit an G2 (HANDOFF 4.1) | Zeitfenster ohne parallele Sessions wählen; je Datei ein Commit |
| Zwischenstände bauen einzeln nicht | jeder REF-Schritt endet grün; Übergangsbefehl in REF-002 bleibt bis zum Folgecommit |
| Bezahlte Läufe bei Tests | kein Schritt verlangt eine Neuauswertung; `run_one` in Tests mit PLU nimmt die Auswertung (README) – mit Schlüssel ein bezahlter Lauf, deshalb ohne `EMPRISE_OPENROUTER_API_KEY` testen |

## 7. Rückroll-Strategien

| Schritt | Rückrollen | Daten betroffen? |
|---|---|---|
| REF-001 | Revert; `UPDATE job SET queue = 'default' WHERE status = 'queued'`; `worker-long` stoppen | nein |
| REF-002 bis Schritt 4 | Einstellung zurück, `storage`-Dienst starten; SeaweedFS-Daten unverändert | nein (nur kopiert) |
| REF-002 nach Schritt 5 | Revert beider Commits; Dateien per Gegenbefehl nach S3 kopieren | ja, Kopie nötig |
| REF-003 | Variablen und Stack wieder einrichten; Listen zurückspielen | Listen, Modellwahl |
| REF-003b | `downgrade` von 0022 stellt `alembic_version_shared` her; Revert | nein |
| REF-004 | Revert; `docker compose -f compose.analyse.yaml up -d` | nein |
| REF-005, REF-011 | Revert | nein |
| REF-006 | Revert; Downgrade legt `app_setting` leer an | nein |
| REF-007 bis REF-010 | Revert je Commit | nein |
| Unraid allgemein | `./deploy.sh rollback <release>` (Image-Tags, `releases.log`); Migrationen bleiben stehen (abwärtskompatibel) | nein |

## 8. Prüfliste vor jedem Schritt

1. `git status` sauber oder fremde Arbeit abgestimmt; parallele Sessions per `ListAgents` prüfen.
2. CI-Stand grün.
3. Lokaler Dump: `docker exec emprise-db-1 pg_dumpall -U postgres > …` (vor REF-001, REF-002, REF-003, REF-003b, REF-006).
4. Ohne `EMPRISE_OPENROUTER_API_KEY` testen (keine bezahlten Läufe).
5. Nach dem Schritt: voller Backend- und Frontend-Lauf, `envelope-check --commune 44209` gegen den Stand vorher, OpenAPI-Abgleich, bei Compose-Änderungen beide Produkte im Browser öffnen.
6. BETRIEB, README-Stolperstellen, ANNAHMEN und AENDERUNGEN im selben Zug nachziehen.
