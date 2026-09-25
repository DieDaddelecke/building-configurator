# AN2 – PLU selbst hochladen (Emprise Analyse)

> **Status:** geplant und umgesetzt am 25.09.2026 (Befunde beim Bau in 7.4) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN2), 8.1 Nr. 1 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN2 (Präfix `PU`)
> **Voraussetzung:** AN0 (PS01–PS09), AN1 (UP01–UP16). Fachregeln: `BACKEND_SPEZIFIKATION.md` 5.2, Umsetzung G2 nach ANNAHMEN RW01–RW27.

---

## 1. Zweck und Umfang

Der Architekt lädt das règlement écrit des PLU als PDF hoch, wählt die Zone seines Grundstücks, und die vorhandene Auswertung (G2) liefert daraus die Regeln – mit Zitat, Seite, Schranken, Gegenprüfung und Kostenzählung wie im Hauskonfigurator. Der Baurahmen (G3) rechnet damit auch für Grundstücke aus einer Datei oder einer Zeichnung. Damit schließt AN2 die Lücke aus PLAN_ANALYSE 8.1 Nr. 1: `resolve_rules` bekommt einen zweiten Einstieg, der nicht bei Gemeinde und Zonengeometrie des GPU beginnt.

**Enthalten:** Upload und Lesen des PDF; erkannte Zonenkapitel zur Auswahl, Seitenbereich von Hand; Zonencode mit Vorschlägen aus dem Kapiteltext; Auswertung nur des gewählten Kapitels; zweiter Einstieg in `resolve_rules`; Baurahmen für Grundstücke ohne Kataster mit hochgeladenem PLU; Zitate mit Sprung auf die Seite der hochgeladenen Datei; Oberfläche im Analyse-Produkt (Dokument, Zone, Stand der Auswertung mit Kosten, Regeln, Baurahmen).

**Nicht enthalten:** Zusatzdokumente (règlement de lotissement, cahier des charges – verschoben nach AN4, E-AN2-5); Zonenplan, überlagernde Vorgaben und Servituden aus Dateien; mehrere Zonen je Grundstück (E-A3); OCR gescannter Reglements (RW03); Nutzfläche und Analyse (AN3); Regelformular (AN4); Bericht (AN5).

## 2. Befund

| Baustein | Stand | Folge für AN2 |
|---|---|---|
| `resolve_rules` | Gemeinde (INSEE) → `rules_commune` → aktiver `land_use_plan` → Zonen per `ST_Intersection` → Regelwerke je Zonencode; Rückfall auf den vorigen Planstand | zweiter Einstieg nötig; die Zusammenstellung ab „Zonenzeilen liegen vor“ (Regelwerk, Version, Kapitelstatus, Korrekturen, Zitat-URL) ist für beide Wege gleich und wird herausgelöst |
| `land_use_plan` | ein Planstand des GPU, `gpu_doc_id` Pflicht und eindeutig | trägt Kapitel, Regelwerke und Läufe (Fremdschlüssel). Ein hochgeladenes Dokument wird deshalb ein `land_use_plan` mit `origin = 'upload'` – sonst wäre die ganze Kette Kapitel → Lauf → Regelwerk doppelt zu bauen |
| `plan_import.py` | GPU-Teil (Gemeinde, Partition, Dokument, Download) und PDF-Teil (Text, Struktur, `source_file`, Kapitel, Job) in einer Funktion | PDF-Teil als Bausteine herauslösen: `store_source`, `ensure_chapter` (ein Kapitel anlegen oder angleichen, bei geänderter Eingabe `pending` und Job) |
| `extract_chapter` | arbeitet nur auf Kapitel, Quelle und Sektoren; prüft `plan.status == 'active'` | unverändert nutzbar; Einheit bleibt Kapitel mit Sektoren (RW05) |
| `detect_structure` | Inhaltsverzeichnis, sonst Seitenüberschriften | unverändert; ohne Ergebnis Seitenbereich von Hand |
| `rules_housekeeping` | nimmt Kapitel aktiver Planstände mit Sektoren wieder auf | greift auch für hochgeladene Dokumente (Schlüssel eingetragen, Budget wieder frei) |
| `envelope/service.py` | `NO_RULES_ORIGINS = (manual_sketch, upload)` → kein Baurahmen | gilt künftig nur, solange kein PLU hochgeladen ist |
| `source_url` | `SourceFile.url` (öffentliche Adresse im GPU) + `#page=` | für Uploads eine API-Adresse, die das PDF ausliefert |
| Zugriff | `require_project_access` erlaubt Cookie **oder** Architekt | Upload und Zonenwahl lösen Kosten aus → nur Architekt und nur eigene Projekte (Projekt mit Eigentümer) |

## 3. Fachliche Festlegungen

### 3.1 Dokument statt Planstand aus dem GPU

`land_use_plan` bekommt `origin ∈ {gpu, upload}`; für Uploads ist `gpu_doc_id` leer und `document_sha256` gesetzt (eindeutig). **Dasselbe PDF ist dasselbe Dokument** – ein zweites Projekt in derselben Gemeinde nutzt Kapitel, Läufe und Regelwerke mit, ohne neue Kosten (E-AN2-1). Titel (Vorgabe: Dateiname) und Art (`PLU`, `PLUi`, `PSMV`) gibt der Architekt an; `partition` und `communes` bleiben leer. Ein Dokument gehört dem Büro, nicht dem Projekt: Es bleibt beim Löschen eines Projekts bestehen (E-AN2-4).

Die Verbindung Projekt → Dokument hält die neue Tabelle `project_regulation` (Projekt, Dokument, Rolle `plu`, gewählter Zonencode, Kapitelcode). In AN2 hat ein Projekt höchstens ein PLU; die Rolle ist für die Zusatzdokumente aus AN4 offengehalten.

### 3.2 Hochladen und Lesen

`POST /projects/{id}/regulations` (Datei, Titel, Art). Die API prüft nur das Nötigste – Größe (`EMPRISE_REGULATION_UPLOAD_MAX_BYTES`, 100 MB wie `pdf.MAX_PDF_BYTES`), `%PDF`, nicht verschlüsselt –, legt die Datei unter `rules/uploads/<sha256>.pdf` in den Objektspeicher und plant den Job **`rules_document_read`** ein (E-AN2-3). Der Job liest die Seitentexte (`pdf.read_text`), erkennt die Struktur (`detect_structure`), speichert `source_file` und `source_page` und legt für **jedes erkannte Kapitel** eine Zeile `regulation_chapter` **ohne Sektoren** an – samt Vorschlägen für Zonencodes (3.3). Kapitel ohne Sektoren wertet niemand aus; Kosten entstehen erst mit der Zonenwahl.

- Mehr als die Hälfte der Seiten ohne Text → `failed: document_no_text` (Scan, RW03).
- Keine Kapitel erkannt → Dokument trotzdem aktiv; der Architekt gibt den Seitenbereich an.
- Ist dasselbe PDF schon vorhanden, entfällt das Lesen; ein früher gescheitertes Lesen wird neu eingeplant.
- Die Oberfläche fragt nach, bis das Dokument `active` oder `failed` ist.

### 3.3 Zone wählen

`PUT /projects/{id}/regulations/{document_id}/zone` mit Zonencode und entweder einem erkannten Kapitel oder einem Seitenbereich (Kapitel, optional allgemeine Bestimmungen). Der Zonencode ist der **Sektor**, für den ausgewertet wird (RW05): `Uba` im Kapitel `Ub`. Vorschläge liefert der Job aus dem Kapiteltext (Wörter, die mit dem Kapitelcode beginnen und ein Zonenkürzel sind, z. B. `Uba`, `Ub1`; nicht die Codes anderer Kapitel) – der Architekt wählt oder schreibt selbst.

Der Sektor kommt zu den Sektoren des Kapitels hinzu. Wie beim GPU-Import (`_sync_chapters`) gilt: geänderte Eingabe → `pending` und Job mit Idempotenzschlüssel über die Eingabe; unveränderte Eingabe → nichts. **Kosten entstehen hier**, einmal je Kapitel und Sektorenmenge (E-AN2-2). Kapitel und allgemeine Seiten zusammen über 150 Seiten → sofort `422 chapter_too_long` (RW23), nicht erst im Job. Ein Seitenbereich von Hand legt ein Kapitel mit `detection = 'manual'` an oder gleicht das gleichnamige an; ohne eigene Angabe übernimmt es die erkannten allgemeinen Seiten des Dokuments. Solange das Dokument gelesen wird, ist keine Zonenwahl möglich (`409 document_not_ready`).

Ändert sich die Eingabe, **während** das Kapitel ausgewertet wird (zweites Projekt, anderer Sektor), überspringt der neue Job die laufende Auswertung (`already_running`), und der neue Sektor bliebe ohne Ergebnis. Deshalb prüft `extract_chapter` beim Schreiben, ob die Eingabe noch dieselbe ist; wenn nicht, schreibt es die ausgewerteten Sektoren, setzt das Kapitel auf `pending` und plant einen Folgeauftrag ein (7.1 Nr. 11). Das gilt für den GPU-Weg genauso.

### 3.4 Zweiter Einstieg in `resolve_rules`

Hat das Projekt ein hochgeladenes PLU, gilt es – **vor** dem GPU-Weg, auch für ein Kataster-Grundstück (E-AN2-6). Es gibt dann genau eine Zonenzeile: Code = gewählter Zonencode, Teilfläche = ganzes Grundstück, Kapitel = gewähltes Kapitel. Ab dort dieselbe Zusammenstellung wie beim GPU-Weg (Regelwerk, Version, Kapitelstatus, Projektkorrekturen, Zitat-URL), also dieselbe Ausgabe `RulesResult` – `envelope_rules`, Regelanzeige und Baurahmen bleiben unverändert (BR15). Kein Rückfall-Planstand, keine überlagernden Vorgaben, keine Gemeinde.

| Lage | Ausgabe |
|---|---|
| Dokument wird gelesen | `in_progress` |
| Lesen gescheitert | `unavailable`, Grund aus dem Dokument (`document_no_text`, `pdf_unreadable` …) |
| keine Zone gewählt | `unavailable`, `zone_not_chosen` |
| Kapitel `pending`/`extracting` | Zone `in_progress` (wie GPU) |
| Kapitel gescheitert | Zone `unavailable` mit Grund (`not_configured`, `budget_exceeded` …) |

Hinweise: `notice.rules_simulation` und neu `notice.rules_upload` („ausgewertet ist nur das hochgeladene règlement écrit; Zonenplan, überlagernde Vorgaben, Servituden und Zusatzdokumente sind nicht berücksichtigt“).

### 3.5 Baurahmen

`NO_RULES_ORIGINS` greift nur noch, solange kein PLU hochgeladen ist. Mit PLU läuft für `upload` und `manual_sketch` die normale Ableitung: Umriss und Kanten aus AN1 (nicht eingeordnete Kanten eng ausgelegt, BR03), Regeln aus 3.4, kein Gelände (BR09 → Hinweis `terrain_unavailable`). Der Hinweis `notice.cadastre_accuracy` entfällt für diese Herkünfte, `notice.<origin>` bleibt. Im Hauskonfigurator ändert sich nichts: Kundenprojekte können kein PLU hochladen (3.7), Weg E bleibt ohne Baurahmen (D13).

### 3.6 Zitate

`source_file.url` eines Uploads ist `/api/v1/regulation-files/<id>`; der Endpunkt liefert das PDF aus dem Objektspeicher **inline** (`application/pdf`, `nosniff`), damit `#page=` im Browser auf die Seite springt. Zugriff: Rollen `architect`, `rules_admin`, `ops` (wie das Lesen der Regelwerke).

### 3.7 Zugriff

Neue Zugriffsregel `require_owned_project`: angemeldeter `architect` und ein Projekt **mit** Eigentümer (UP05), sonst `404`. Sie trägt alle Endpunkte unter `/projects/{id}/regulations`. Das Projekt-Cookie reicht nicht: Ein Kunde des Hauskonfigurators soll keine Auswertung auslösen können, die Geld kostet.

### 3.8 Oberfläche des Analyse-Produkts

Auf der Projektseite unter dem Grundstück ein Abschnitt **Bebauungsplan**: PDF hochladen (Titel, Art) → „wird gelesen“ → erkannte Kapitel zur Auswahl mit Seiten, Zonencode mit Vorschlägen, Seitenbereich von Hand als zweiter Weg → „Zone übernehmen und auswerten“ → Stand der Auswertung (wartet, läuft, fertig, gescheitert mit Grund) mit Zahl der Aufrufe und Kosten. Darunter die Regeln (`RegelnSimulation`) und der Baurahmen (`Baurahmen`, Rolle `architect`) über die Büro-Endpunkte (E-AN2-7), mit Nachfragen, solange die Auswertung läuft.

## 4. Arbeitsschritte

1. Migration `0013`: `land_use_plan.origin`, `gpu_doc_id` nullable, `document_sha256`; `regulation_chapter.suggested_sectors`; Tabelle `project_regulation`.
2. `rules/domain/chapters.py`: `sector_candidates` (rein, mit Einheitstests).
3. `rules/plan_import.py`: `store_source` und `ensure_chapter` herauslösen, GPU-Weg darauf umstellen (Verhalten gleich, Tests grün).
4. Neues Modul `rules/documents.py`: Upload, Lesen (Job `rules_document_read` in `rules/jobs.py`), Zonenwahl, Auflisten, Entfernen, PDF ausliefern.
5. `rules/service.py`: `resolve_rules` mit zweitem Einstieg; Zusammenstellung herausgelöst; `PlanOut` mit `origin`.
6. `envelope/service.py`: Baurahmen mit hochgeladenem PLU.
7. API: Endpunkte in `rules/api.py`, Zugriffsregel in `platform/auth/context.py`; `openapi.json` und `schema.d.ts` neu.
8. Frontend: `src/api/regulations.ts`, `src/products/analyse/Bebauungsplan.tsx`, Einbau in `ProjektSeite`, Regeln und Baurahmen; Übersetzungen de/fr; Fehlertexte im Backend.
9. Tests: Einheit (Vorschläge), Integration (Upload, Lesen, Scan, Duplikat, Zonenwahl, Kapitel zu lang, Zugriff, Regeln, Baurahmen, Gegenprobe GPU ↔ Upload), Komponententest der Oberfläche.
10. Dokumente: ANNAHMEN (Abschnitt AN2), BETRIEB 15, PLAN_ANALYSE (AN2 umgesetzt, AN4 um Zusatzdokumente erweitert), README.

## 5. Abnahme

1. Das Test-Reglement (Inhaltsverzeichnis + Kapitel Uh, `tests/rules_support.py`) hochladen → Job liest es, Kapitel `Uh` mit Seiten und allgemeinen Seiten erscheint, noch kein Auswertungsjob.
2. Zone `Uh` wählen → Kapitel `pending`, genau ein Job; mit der aufgezeichneten Antwort ausgewertet → Regeln mit Zitat-Link auf `/api/v1/regulation-files/…#page=…`.
3. **Gegenprobe** (PLAN_ANALYSE 7 Punkt 5): dasselbe Grundstück AD 65 über den GPU-Weg und über den Upload-Weg → dieselben Regeln (Art, Baukörper, Status, Werte) und derselbe Baurahmen (Flächen beider Konturen bis auf Rundung).
4. Scan → `document_no_text`; PDF ohne Inhaltsverzeichnis → Seitenbereich von Hand; Kapitel über 150 Seiten → `422`.
5. Dasselbe PDF in zwei Projekten → ein Dokument, ein Kapitel, ein Job. Ein zweiter Sektor desselben Kapitels → Kapitel neu eingeplant, das bisherige Regelwerk bleibt bis dahin wirksam.
6. Zugriff: Kunde mit Cookie → `404`; Architekt auf Kundenprojekt → `404`; PDF nur mit Rolle.
7. Grundstück aus Datei mit PLU → Baurahmen `ok`/`partial`; ohne PLU unverändert `unavailable` (`upload`). Hauskonfigurator unverändert, alle bisherigen Tests grün, Grenz-Test hält.
8. Browser (Analyse-Stack, Deutsch und Französisch, Telefonbreite): Upload → Kapitelwahl → Auswertung (ohne Schlüssel: „nicht eingerichtet“; mit aufgezeichneter Antwort: Regeln und Baurahmen).

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN2-1 | Dokument je Projekt oder für das Büro gemeinsam? | **Gemeinsam, erkannt am SHA-256.** Dasselbe PLU gilt für viele Projekte einer Gemeinde; jede Auswertung kostet. Korrekturen des Büros für eine Zone wirken dann für alle Projekte mit diesem Dokument – wie im Hauskonfigurator. Mit AN6 je Organisation trennen |
| E-AN2-2 | Welche Sektoren eines Kapitels auswerten? | **Die gewählten** (wie beim GPU die Sektoren der Gemeinden). Ein neuer Sektor im selben Kapitel wertet das Kapitel neu aus (Kosten eines Kapitels; die bisherigen Regeln bleiben bis dahin wirksam, neue Versionen stehen in der Historie). Die Vorschläge vorab mit auszuwerten, spart das, wertet aber auch falsche Vorschläge aus |
| E-AN2-3 | PDF im Request oder im Job lesen? | **Im Job.** Ein Reglement mit 300 Seiten braucht zum Lesen rund eine halbe Minute; im Request drohen Zeitüberschreitungen am Reverse Proxy, und der API-Prozess wäre blockiert |
| E-AN2-4 | Dokument mit dem Projekt löschen? | **Nein.** Ein PLU enthält keine personenbezogenen Daten; mit dem Dokument verschwänden die Läufe und damit die Monatskosten (RW11, das Budget begänne neu). Aufräumen ungenutzter Dokumente erst bei Bedarf, mit AN6 neu bewerten |
| E-AN2-5 | Zusatzdokumente (lotissement, cahier des charges) in AN2? | **Nach AN4 verschieben.** Sie gelten neben dem PLU (das Strengere bindet); eine automatische Verrechnung je Regelart wäre eine eigene, rechtlich heikle Logik. Sie haben keine Zonenkapitel und bräuchten einen eigenen Prompt. AN4 bringt das Regelformular – dort übernimmt der Architekt Werte aus einem Zusatzdokument mit Zitat als Projektkorrektur. Bis dahin nennt `notice.rules_upload` die Lücke |
| E-AN2-6 | Hochgeladenes PLU auch für Kataster-Grundstücke? | **Ja, und es geht vor.** Der Architekt entscheidet, welches Dokument gilt (z. B. neuerer Stand als im GPU); ohne Upload bleibt der GPU-Weg |
| E-AN2-7 | Regeln und Baurahmen im Analyse-Produkt über Kunden- oder Büro-Endpunkte? | **Büro-Endpunkte** (Rolle statt Flag). Im Analyse-Produkt gibt es nur Mitarbeitende; die Flags `rules_simulation` und `envelope_simulation` wären dort nur ein weiterer Schalter zum Vergessen |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Erster Gedanke: für Uploads eine Schein-Gemeinde in `rules_commune` anlegen, dann liefe `resolve_rules` unverändert | Gemeinden sind nach INSEE geteilt; Projekte verschiedener Dokumente fielen zusammen, Rückfall-Logik und wöchentlicher Import griffen ins Leere | 3.4: eigener Einstieg über `project_regulation` |
| 2 | Alle erkannten Kapitel sofort auswerten wäre bequem | 20–30 Kapitel je Reglement, jedes kostet – für eine einzige Zone | 3.2/3.3: Kapitel ohne Sektoren, Auswertung erst mit der Zonenwahl |
| 3 | Dokument mit dem Projekt löschen (Kaskade) | löscht `rule_extraction_run` und senkt `month_cost` – das Budget ließe sich durch Löschen umgehen | E-AN2-4 |
| 4 | Upload über `require_project_access` | ein Kunde mit Projekt-Cookie könnte im Hauskonfigurator Auswertungen auslösen | 3.7: `require_owned_project` |
| 5 | Ein neuer Sektor ändert die Eingabe des Kapitels (`input_hash` enthält die Sektoren) | Neuauswertung auch für Projekte, die den anderen Sektor nutzen; Werte können sich ändern | E-AN2-2 benennt es; Versionen bleiben erhalten, eine Korrektur des Büros (`office_reviewed`) bleibt wirksam (RW10) |
| 6 | `NO_RULES_ORIGINS` sperrte den Baurahmen allein nach Herkunft | ein Upload mit PLU bliebe ohne Baurahmen | 3.5 |
| 7 | Kapitel über 150 Seiten scheiterten erst im Job | Wartezeit ohne Aussicht | 3.3: sofort `422` |
| 8 | Zitat-URL des GPU (`data.geopf.fr`) gibt es für Uploads nicht; eine vorsignierte Adresse des Objektspeichers verfällt und ist auf Unraid nicht öffentlich | tote Links an jedem Wert | 3.6: API-Endpunkt, feste Adresse in `source_file.url` |
| 9 | Liefert der Endpunkt das PDF als Anhang (wie Steckbrief und Dossier), springt `#page=` nicht | Zitat ohne Seite | 3.6: `inline`; nur Rollen des Büros, Dateiart geprüft, `nosniff` |
| 10 | Dasselbe PDF als GPU-Planstand und als Upload | Kollision über die Prüfsumme? | nein: `document_sha256` ist nur für Uploads gesetzt; beide bleiben getrennte Dokumente |
| 11 | Sektor kommt hinzu, während das Kapitel läuft: der neue Job endet mit `already_running`, der laufende schreibt `succeeded` mit der **alten** Eingabe; Idempotenzschlüssel sind dauerhaft, `rules_housekeeping` nimmt `succeeded` nicht wieder auf | neuer Sektor dauerhaft ohne Regeln, Anzeige „nicht verfügbar: succeeded“. Im GPU-Weg selten (neue Gemeinde während einer Auswertung), bei gemeinsam genutzten Dokumenten naheliegend | 3.3: Eingabe beim Schreiben erneut prüfen, sonst `pending` und Folgeauftrag |
| 12 | Titel und Art beim zweiten Upload desselben PDF | Welcher Titel gilt? | der des ersten Uploads; das Dokument ist dasselbe (E-AN2-1) |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Eigene Tabellen für hochgeladene Dokumente | Kapitel, Läufe, Regelwerke und Korrekturen hängen an `land_use_plan`; alles doppelt | die Produkte fachlich auseinanderlaufen |
| Regelwerk je Projekt statt je Dokument | dieselbe Auswertung mehrfach bezahlt | Dokumente fast nie wiederkehren |
| Vorgeschlagene Sektoren gleich mit auswerten | wertet auch falsche Treffer aus („Ne“ am Satzanfang bei Zone N) | Büros häufig mehrere Sektoren desselben Kapitels nutzen |
| Eigene PDF-Ansicht (pdf.js) mit Hervorhebung des Zitats | zusätzlicher Baustein (RW15) | Zitate in langen Seiten schwer zu finden sind |
| Zonenplan als Datei hochladen und verschneiden | braucht Georeferenz und mehrere Zonen je Grundstück (E-A3) | AN5 die Georeferenzierung bringt |

### 7.3 Bewusste Grenzen

Ein PLU je Projekt, eine Zone je Grundstück. Stehen die allgemeinen Bestimmungen in einer anderen Datei als die Zonenkapitel (mehrbändige Reglements, RW23), lassen sie sich nicht zusammenführen – Ausweg: beide Bände zu einem PDF verbinden und den Seitenbereich der allgemeinen Bestimmungen von Hand angeben. Keine OCR, keine Zusatzdokumente, keine überlagernden Vorgaben, keine Servituden, keine Kostenvorschau vor der Auswertung (die Kosten stehen danach am Kapitel).

### 7.4 Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Die Zeilen der Zonenabfrage (SQL) und die eine Zone des Uploads haben verschiedene Formen | Zwei Zusammenstellungen der Regeln – genau das, was BR15 verhindern soll | `_ZoneRow` und `_rules_for_zones` in `rules/service.py`: beide Einstiege liefern Zonenzeilen, der Rest ist gemeinsam |
| 2 | Der Hinweis `notice.manual_sketch` („nicht mit dem Bebauungsplan abgeglichen“) stünde im Baurahmen einer gezeichneten Parzelle **mit** hochgeladenem PLU | Falsche Aussage | neuer Hinweis `notice.site_without_cadastre` für Grundstücke ohne Kataster im Baurahmen (PU05) |
| 3 | Der Upload lief im Event-Loop der API: PDF prüfen und bis zu 100 MB ablegen blockieren alle anderen Anfragen | Stillstand der API für Sekunden | `run_in_threadpool` im Endpunkt |
| 4 | Regeln und Baurahmen fragen nur zehn Minuten nach; eine Auswertung kann länger dauern | Ergebnis erscheint erst nach Neuladen | `useRefreshWhenStateChanges`: Wechselt der Stand von Dokument oder Kapitel, lädt die Seite Regeln und Baurahmen neu |
| 5 | Browser: Der Upload hing ohne Eintrag im API-Log. Ursache war der lokale Objektspeicher (SeaweedFS, acht Volume-Plätze, alle belegt), verschärft durch den Upload selbst: Er hielt beim Ablegen die Zeile des Dokuments gesperrt | Ein gestörter Speicher hätte weitere Uploads derselben Datei blockiert | Ablegen **vor** jeder Sperre und bei jedem Upload (PU03); lokal `-volume.max=0` in `compose.yaml` (README, Stolperstellen) |
| 6 | Browser: Chrome zeigt ein PDF unter der Seiten-CSP des Web-Containers nicht an (`object-src 'none'`, `style-src 'self'`; Chromium-Fehler 40328564) | Zitat-Links führten auf eine leere Seite | `frontend/Caddyfile`: CSP nur für `@seiten`, nicht für `/api/v1/regulation-files/*` (PU06). Geprüft ist die Kopfzeile; die Anzeige in Chrome selbst nicht, weil der eingebaute Browser PDFs nur herunterlädt |
| 7 | Browser: Unter „Baurahmen“ und über den Regeln standen Sätze für Kunden („Anfrage an das Architekturbüro möglich“, „prüft sie, wenn Sie eine Anfrage senden“), der Baurahmen hieß „aus Kataster und Planunterlagen“ | Im Architektenprodukt falsch | Kundenhinweis nur für die Rolle `customer`, eigener Text `rules.simulation.textOffice`, „aus Grundstück und Planunterlagen“ |
| 8 | Die Fehlermeldung des Parzellen-Uploads (AN1) nannte „höchstens 8 MB“, die Grenze ist seit UP13 20 MB | Falsche Angabe | Text in de/fr korrigiert |

**Prüflauf:** Backend 541 Tests (vorher 526; neu `tests/integration/test_rules_upload.py` mit 14 Tests, ein Einheitstest für die Vorschläge), Frontend 157 (vorher 150; neu `bebauungsplan.test.tsx` mit 7 Tests), dazu ruff, Format, mypy, Typprüfung, Lint und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt. Die Gegenprobe aus 5 Punkt 3 ist `test_upload_matches_the_gpu_path_for_the_same_parcel`: gleiche Regeln, Konturflächen gleich bis auf 0,5 m², gleiche Abstände je Kante.

**Browserprüfung am 25.09.2026** (Analyse-Stack, Deutsch und Französisch, Telefonbreite ohne waagerechtes Verschieben): neues Projekt → Parzelle 20 × 30 m als DXF → Kante 3 als Straße → Test-Reglement (24 Seiten) als PLUi hochgeladen → „wird gelesen“ → Kapitel „Uh – CHAPITRE 4 : LA ZONE Uh (S. 4–24)“ vorgewählt → „Zone übernehmen und auswerten“ → „wartet auf die Auswertung“ → ohne Schlüssel „Auswertung gescheitert … Es fehlt der Schlüssel der Claude API“ → mit der aufgezeichneten Antwort ausgewertet: „ausgewertet · 2 Aufrufe · 0,16 $“, Baurahmen 300 m² (weiteste) und 210 m² (engste Auslegung), jede Zeile mit Seite, Zitat-Links auf `/api/v1/regulation-files/…#page=9` bis `#page=13`, Hinweise „nur das hochgeladene règlement écrit“ und „Parzelle nicht aus dem Kataster“.
