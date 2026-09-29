# AN2 – PLU selbst hochladen (Emprise Analyse)

> **Status:** geplant und umgesetzt am 25.09.2026 (Befunde beim Bau in 7.4), KI-Modell der Auswertung wählen am 28.09.2026 (Kapitel 8), Text statt PDF für Modelle ohne PDF-Eingabe am 28.09.2026 (Kapitel 9) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN2), 8.1 Nr. 1 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN2 (Präfix `PU`)
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
| E-AN2-5 | Zusatzdokumente (lotissement, cahier des charges) in AN2? | **Nach AN4 verschieben.** Sie gelten neben dem PLU (das Strengere bindet); eine automatische Verrechnung je Regelart wäre eine eigene, rechtlich heikle Logik. Sie haben keine Zonenkapitel und bräuchten einen eigenen Prompt. AN4 bringt das Regelformular – dort übernimmt der Architekt Werte aus einem Zusatzdokument mit Zitat als Projektkorrektur. Bis dahin nennt `notice.rules_upload` die Lücke. **Entschieden am 25.09.2026 (Nutzer): in AN3 vorgezogen** – Hochladen, Auswerten und Anzeige neben den PLU-Regeln ([PLAN_AN3](PLAN_AN3_ANALYSE.md)); die Übernahme als Projektkorrektur bleibt bei AN4 |
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

## 8. Nachtrag 28.09.2026: KI-Modell der Auswertung wählen

**Auftrag des Nutzers:** „Kannst du einen Auswahldialog erstellen, in dem man die Möglichkeit hat, das verwendete Modell in OpenRouter zu ändern?“ – „Mir ging es darum, das KI-Modell, welches zur Auswertung der PLU verwendet wird, einstellen zu können.“ Auf die Rückfrage gewählt: **eine Einstellung für alle**, als Auswahldialog auf der Startseite von Emprise Analyse; das Modell gilt für alle künftigen Auswertungen, bis man es wieder ändert. Festlegung: ANNAHMEN PU11.

### 8.1 Befund

- Modell und Preise kommen bisher nur aus der Umgebung (`EMPRISE_RULES_MODEL`, `EMPRISE_RULES_PRICE_*`, seit 28.09.2026 über die `.env` einstellbar); eine Änderung wirkt erst nach dem Neuerstellen der Container. Vorgabe `anthropic/claude-opus-5` (seit 28.09.2026 abends `anthropic/claude-opus-5.5`, RW28).
- Das Modell steckt in jedem Aufruf, im Eingabe-Hash (Wiederverwendung gespeicherter Teilantworten), in der Kostenrechnung (Monatsbudget) und in jedem Lauf (`rule_extraction_run.model`). Die Preise müssen zum Modell passen, sonst stimmt das Budget nicht.
- OpenRouter veröffentlicht die Modellliste ohne Schlüssel (`GET /api/v1/models`): Kennung, Name, Preise je Token (Eingabe, Ausgabe, Cache), Eingabearten, unterstützte Parameter. Am 28.09.2026 unter anderem `anthropic/claude-opus-5` (5 $/25 $ je Mio. Token), `anthropic/claude-opus-5.5` (4 $/20 $), `anthropic/claude-sonnet-5` (2 $/10 $), dazu Varianten `:batch` und gleitende Namen wie `~anthropic/claude-opus-latest`.

### 8.2 Festlegungen

- **Einstellung in der Datenbank:** neue Tabelle `app_setting` (Schlüssel, Wert als JSON, geändert am, geändert von) mit dem Eintrag `rules_model`: Kennung und Preise je Million Token (Eingabe, Ausgabe, Cache lesen, Cache schreiben). Ohne Eintrag gilt die Umgebung (**Vorgabe**). Die Einstellung gilt für die ganze Instanz, also für alle Projekte und alle Nutzer von Emprise Analyse.
- **Wirksam ohne Neustart:** Jede Auswertung eines Kapitels liest die Einstellung beim Start einmal und rechnet damit – Aufruf, Eingabe-Hash, Kosten, Lauf. Eine laufende Auswertung bleibt beim Modell, mit dem sie begann. Schlüssel, Budget, Denkaufwand und Zahl der Läufe bleiben in der Umgebung.
- **Auswahl nur aus der Liste von OpenRouter:** Der Server holt sie ohne Schlüssel und hält sie eine Stunde vor. Angeboten werden nur Modelle, die **PDF lesen** (Eingabeart `file`) und **ein Werkzeug erzwingen** können (`tools`, `tool_choice`) – ohne beides scheitert jeder Aufruf. Ausgeschlossen: Varianten mit Doppelpunkt (`:batch`, `:free`), gleitende Namen (`~…`) und Modelle ohne festen Preis.
- **Preise übernimmt der Server aus der Liste**, nie von Hand. Fehlen die Cache-Preise, gelten wie bisher 10 % (lesen) und 200 % (schreiben) des Eingabepreises.
- **Zurück zur Vorgabe:** Wer das Modell der Umgebung wählt, löscht den Eintrag; dann gelten wieder Modell und Preise der Umgebung.
- **Rechte:** Ändern dürfen `ops` und `rules_admin`, weil die Wahl die Kosten aller Projekte bestimmt; `architect` sieht das eingestellte Modell ohne Knopf. Jede Änderung steht im Audit-Log mit altem und neuem Modell.
- **Keine neue Auswertung von selbst:** Ausgewertete Kapitel bleiben, bis jemand sie neu auswertet (Kosten, D11).
- **Startseite (Projektliste):** Abschnitt „KI-Modell der Auswertung“ unter der Liste mit Modell, Preisen und Kosten des Monats gegen das Budget, dazu „Ändern“. **Dialog:** modales Fenster mit Suchfeld und Liste (Name, Kennung, Preis für Eingabe und Ausgabe je Mio. Token), markiert „eingestellt“ und „Vorgabe“; Hinweise: gilt für künftige Auswertungen; auf Claude abgestimmt (Prompt `g2-prompt-4`), andere Anbieter sind nicht geprüft. „Übernehmen“ speichert, „Abbrechen“ und Escape schließen.
- **Hauskonfigurator:** keine Oberfläche; die Seite „Regelwerke“ zeigt wie bisher das wirksame Modell. Die Endpunkte gehören zum Kern und wirken dort, falls jemand sie aufruft, ebenfalls nur auf die eigene Instanz.

### 8.3 Schnittstelle

| Methode | Pfad | Rollen | Inhalt |
|---|---|---|---|
| GET | `/admin/rules/model` | architect, rules_admin, ops | eingestelltes Modell, Herkunft (`setting`/`default`), Vorgabe, Preise, Kosten des Monats, Budget, geändert am |
| GET | `/admin/rules/models` | rules_admin, ops | wählbare Modelle mit Preisen; `503 models_unavailable`, wenn OpenRouter nicht antwortet |
| PUT | `/admin/rules/model` | rules_admin, ops | `{model}`; `422 model_not_available`, wenn das Modell nicht (mehr) wählbar ist |

### 8.4 Arbeitsschritte

1. Migration 0016 `app_setting`; Modell `AppSetting` in `platform/models.py`.
2. `app/rules/model_choice.py`: Liste lesen und filtern, Zwischenspeicher, wirksame Einstellung, Wahl speichern.
3. Einbau: Job `rules_extract` und CLI `rules-extract` rechnen mit der wirksamen Einstellung; `coverage` zeigt sie; `prices` nimmt Cache-Preise, wenn gesetzt.
4. API, Schemas, Problemtexte de/fr; `openapi.json`, `schema.d.ts`.
5. Frontend: `api/rules.ts`, `products/analyse/ModellWahl.tsx` (Abschnitt und Dialog), Einbau in `Projekte.tsx`; Texte de/fr.
6. Tests: Einheit (Filter, Preise, wirksame Einstellung), Integration (Lesen, Wählen, Vorgabe, Rechte, unbekanntes Modell, OpenRouter nicht erreichbar, Auswertung rechnet mit dem gewählten Modell), Komponenten (Suche, Auswahl, Speichern, ohne Rolle kein Knopf).
7. Browser; ANNAHMEN PU11, BETRIEB 9 und 15.

### 8.5 Grenzen

- Nur Claude-Modelle sind mit dem Prompt erprobt; andere Anbieter bietet der Dialog an, weist aber darauf hin.
- Ein Wechsel ändert den Eingabe-Hash: Gespeicherte Teilantworten des alten Modells werden nicht wiederverwendet.
- Kein Modell je Projekt oder Dokument (auf Rückfrage bewusst so gewählt); keine Wahl des Denkaufwands.
- Ist OpenRouter nicht erreichbar, lässt sich das Modell nicht ändern; die Auswertung läuft mit der bisherigen Einstellung weiter.

### 8.6 Prüfprotokoll

**Vor dem Bau:**

| Nr. | Befund | Folge | Festlegung |
|---|---|---|---|
| 1 | Preise von Hand im Dialog | Falsche Kosten, das Budget greift zu früh oder zu spät | Preise aus der Liste von OpenRouter (8.2) |
| 2 | Gleitende Namen (`~…-latest`) | Das Modell wechselt still, Ergebnisse und Preise mit | Ausgeschlossen |
| 3 | Varianten `:batch` rechnen asynchron ab, `:free` hat enge Grenzen | Aufruf scheitert oder bricht ab | Ausgeschlossen |
| 4 | Modelle ohne PDF-Eingabe oder ohne erzwungenes Werkzeug | Jeder Aufruf scheitert (`bad_request`) | Nur Modelle mit `file`, `tools`, `tool_choice` |
| 5 | Wechsel während einer Auswertung | Teile eines Kapitels mit verschiedenen Modellen; Hash und Kosten gemischt | Einstellung einmal beim Start des Jobs lesen |
| 6 | Nach einem Wechsel alles neu auswerten? | Unerwartete Kosten | Nein; neu auswerten bleibt eine Entscheidung je Kapitel |
| 7 | Jeder Architekt könnte das Modell für alle umstellen | Kosten für alle Projekte ändern sich ohne Absprache | Nur `ops` und `rules_admin`; Audit-Log |
| 8 | Die Liste holt die API, nicht der Worker | Ausgehender Zugang der API zu `openrouter.ai` | Wie für den Worker freigegeben (BETRIEB 1); eine Stunde Zwischenspeicher |

**Geprüfte Alternativen:**

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Modell beim Hochladen je Dokument wählen | Auf Rückfrage nicht gewählt | Architekten Modelle vergleichen wollen |
| Freitextfeld für die Kennung | Tippfehler erst beim nächsten Aufruf sichtbar, Preise fehlen | – |
| Feste Liste im Code | Veraltet schnell (am 28.09. war die Vorgabe schon nicht mehr das neueste Opus) | OpenRouter aus der API nicht erreichbar sein darf |
| Weiter nur über die Umgebung | Neustart nötig, kein Dialog | nur der Betrieb das Modell ändern soll |

**Beim Bau gefunden:**

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Die Liste von OpenRouter bot am 28.09.2026 98 geeignete Modelle, sortiert nach Anbieter; das eingestellte stand beim Öffnen außer Sicht | Man sah nicht, was gerade gilt | Der Dialog rückt das eingestellte Modell beim Öffnen in die Mitte der Liste |
| 2 | Die Cache-Preise von OpenRouter weichen von der bisherigen Ableitung ab (Opus 5.5: Cache lesen 0,20 $ statt 10 % = 0,40 $) | Mit der Ableitung wären die Kosten zu hoch gezählt | Preise des Cache aus der Liste (`rules_price_cache_*`), sonst wie bisher abgeleitet |

**Prüflauf:** Backend 657 Tests mit `TEST_S3=1` (vorher 649; neu 4 Einheitstests zu Filter, Zwischenspeicher und Preisen, 4 Integrationstests zu Rechten, Wahl, Vorgabe, Ausfall von OpenRouter und dem Job), ruff, Format und mypy grün; Migration 0016 in beiden lokalen Datenbanken. Frontend 202 Tests (vorher 197; Anzeige, Suche und Wahl, Hinweis bei anderen Anbietern, Escape, Vorgabe ohne Liste, fehlender Schlüssel), Lint, Typprüfung und Build grün. `openapi.json` und `schema.d.ts` neu erzeugt.

**Browserprüfung am 28.09.2026** (Analyse-Stack mit neuen Images, Liste echt von OpenRouter, Schlüssel noch nicht aktiv): Startseite zeigt „KI-Modell der Auswertung“ mit `anthropic/claude-opus-5`, „Vorgabe“, 5 $/25 $ je Mio. Token, Kosten des Monats und den Hinweis auf den fehlenden Schlüssel → „Ändern“ → Dialog mit 98 Modellen → Suche „opus 5“ → Opus 5.5 gewählt → „Übernehmen“ → Abschnitt zeigt `anthropic/claude-opus-5.5` mit 4 $/20 $; in `app_setting` Modell und Preise (Cache lesen 0,20 $, schreiben 5 $), im Audit-Log der Wechsel → „Vorgabe wiederherstellen“ → wieder `anthropic/claude-opus-5`, Eintrag gelöscht.

## 9. Nachtrag 28.09.2026: Text statt PDF für Modelle ohne PDF-Eingabe

**Auftrag des Nutzers:** „Warum wird eine PDF an das Modell übergeben – gibt es eine Möglichkeit, die PDF vorher in Text umzuwandeln?“ Auf den Vorschlag (Text für Modelle ohne PDF-Eingabe, Claude bleibt beim PDF, Vergleich an einem echten Kapitel): „Ja, setze deinen Vorschlag so um.“ Festlegung: ANNAHMEN PU12.

### 9.1 Befund

- Spez. 5.2.3 schickt das Zonenkapitel und die allgemeinen Bestimmungen als ausgeschnittene PDFs. Claude liest daraus Text und Seitenbild – Tabellen, Aufbau, Skizzen. Die Eingabe zählt deshalb doppelt: Kapitel UC von „PLU Beyenes“ (16 Seiten) kostete 46 841 Eingabe-Token, gut 2 900 je Seite.
- Die Textschicht jeder Seite liegt ohnehin in `source_page` (Kapitelsuche, Zitatprüfung); für UC rund 44 000 Zeichen.
- Viele günstige Modelle lesen kein PDF, etwa `deepseek/deepseek-v4-flash-0731`; der Dialog (Kapitel 8) bot sie deshalb nicht an. OpenRouter wandelt ein PDF für solche Modelle selbst um – ein erster Lauf so brauchte 21 Minuten und wurde abgebrochen (9.5, beim Bau Nr. 1).

### 9.2 Festlegungen

- **Eingabeform je Modell:** Modelle mit PDF-Eingabe (`file` in der Liste von OpenRouter) bekommen weiter die PDF-Auszüge; alle anderen die **Textschicht aus `source_page`** – dieselbe, gegen die die Zitate geprüft werden. Die Wahl im Dialog speichert die Eingabeform mit (`app_setting.value.input`); für die Vorgabe der Umgebung gilt `EMPRISE_RULES_INPUT` (Standard `pdf`).
- **Gleiche Dokumente, gleiche Seiten:** Der Text steht je Auszug in einem Element `<document name="general.pdf">` bzw. `chapter-….pdf`; jede Seite beginnt mit `=== page n ===`, gezählt ab 1 wie im PDF-Auszug. Systemprompt, Ausgabeschema und Rückrechnung der Seiten bleiben unverändert; ein kurzer Vorspann (`TEXT_INPUT_NOTE`) erklärt die Marken und warnt vor Tabellen.
- **Eigener Eingabe-Hash** nur für Text (Marke und Prüfsumme des Vorspanns): Gespeicherte Antworten aus PDF-Läufen werden nicht für Text verwendet und umgekehrt; der Hash der PDF-Läufe bleibt, wie er war.
- **Dialog:** zeigt auch Modelle ohne PDF-Eingabe, markiert „liest Text statt PDF“; ist eines gewählt, sagt ein Hinweis, dass Tabellen ihre Spalten verlieren und Skizzen fehlen. Der Abschnitt auf der Startseite zeigt die Marke, wenn das eingestellte Modell Text bekommt.
- **Claude bleibt beim PDF** (Vergleich 9.5).

### 9.3 Arbeitsschritte

1. `config.rules_input`; `ExtractionRequest.chapter_text`/`general_text`; `build_messages` mit Text-Elementen und Vorspann; `extract._Calls._texts` aus `source_page`; Eingabe-Hash.
2. `model_choice`: Modelle mit Texteingabe und erzwungenem Werkzeug, `reads_pdf`, Eingabeform in der Einstellung; `RulesModelOut.input`, `ModelOptionOut.reads_pdf`.
3. Dialog und Abschnitt; Texte de/fr.
4. Tests; Vergleich an Kapitel UC in einer Kopie der Analyse-Datenbank (`emprise_probe`), damit das Ergebnis im Projekt unberührt bleibt.

### 9.4 Grenzen

- Tabellen kommen als Fließtext an, Skizzen gar nicht; Werte aus Tabellen können fehlen oder verrutschen. Mehrspaltiger Satz kann in falscher Reihenfolge ankommen.
- Seiten ohne Textschicht (Scans) sind in beiden Formen leer (AN7).
- Die Eingabeform folgt dem Modell; eine Wahl „Claude mit Text“ gibt es in der Oberfläche nicht, nur über `EMPRISE_RULES_INPUT` für die Vorgabe.

### 9.5 Prüfprotokoll

**Vor dem Bau:**

| Nr. | Befund | Folge | Festlegung |
|---|---|---|---|
| 1 | Text selbst aus dem PDF ziehen statt `source_page` | Zwei Textfassungen; Zitate würden gegen eine andere geprüft, als das Modell sah | Text aus `source_page` |
| 2 | Seitenmarken mit den Seitennummern des Originals | Rückrechnung der Seiten (Spez. 5.2.3) müsste sich je Eingabeform unterscheiden | Marken zählen ab 1 wie im PDF-Auszug |
| 3 | Den Systemprompt für Text umschreiben | Neue Prüfsumme, alle PDF-Kapitel gälten als geändert | Systemprompt unverändert, Vorspann nur in der Anfrage |
| 4 | Gleicher Eingabe-Hash für Text und PDF | Gespeicherte PDF-Antworten würden für Text wiederverwendet | Eigener Hash nur für Text |
| 5 | OpenRouter wandelt PDFs für Textmodelle selbst um | Unbekannte Umwandlung, Seitenmarken fehlen, Laufzeit (9.1) | Eigene Textschicht |

**Beim Bau gefunden:**

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Ein vom Nutzer abgebrochener Befehl (`docker compose run` mit DeepSeek und PDF) lief im Container weiter: 21 Minuten für den ersten Aufruf, 0,013 $, nur in der Kopie | Der Abbruch im Werkzeug beendet den Container nicht | Container von Hand gestoppt, Kapitel in der Kopie zurückgesetzt; Stolperstelle in README |
| 2 | `app_setting` fehlte in der Liste der Tabellen, die die Tests leeren | Eine Wahl aus einem Test galt im nächsten weiter | `tests/conftest.py` |

**Vergleich** (Kapitel UC von „PLU Beyenes“, 16 Seiten, Kopie der Analyse-Datenbank, je Auswertung und Gegenprüfung):

| | Opus 5, PDF | Opus 5, Text | DeepSeek V4 Flash, Text |
|---|---|---|---|
| Regeln mit Wert | 13 | 11 | 6 |
| nicht ermittelt | 4 | 5 | 13 |
| Kosten | 0,73 $ | 0,50 $ | 0,014 $ |
| Dauer | 1 min 44 s | 1 min 45 s | 10 min 29 s |
| Eingabe-Token (Auswertung) | 46 841 | 22 015 | 14 584 |

- **Opus mit Text** liest alle Werte, die es findet, genau wie mit PDF. Es verliert aber das Dach des Hauptgebäudes (Formen, Neigung 30–45°, Materialien, S. 15) und den hinteren Grenzabstand der Nebengebäude; dafür ein Texthinweis zu Nebengebäuden unter 12 m². Knapp ein Drittel billiger.
- **DeepSeek mit Text** stimmt bei allen gefundenen Werten mit Opus überein (Zaun 2 m, Stellplätze, Bäume, Abstand zwischen Gebäuden 4 m, Straßenabstand 2,5 m), nennt zusätzlich 2 m zwischen Nebengebäuden und beschreibt die Grundflächenzahl als „progressiv nach Grundstücksgröße“ statt 0,9. Seiten- und Hinterabstände, Höhe, Dach und Grundflächenzahl bleiben „nicht ermittelt“. Rund fünfzigmal billiger, sechsmal langsamer.
- **Folgerung:** Claude bleibt beim PDF. DeepSeek V4 Flash taugt für diese Auswertung nicht als Ersatz.

**Zweiter Vergleich** (gleiches Kapitel; Kimi, Qwen und DeepSeek mit Text, da keins PDF liest, Opus 5.5 mit PDF; Denkaufwand für den Probelauf unverändert an OpenRouter gegeben):

| | Opus 5.5, PDF (high) | Kimi K3 (high) | Qwen3.8 Max 0902 (xhigh) | DeepSeek V4 Pro 0813 (high) |
|---|---|---|---|---|
| Regeln mit Wert | 14, dazu 1 Texthinweis | 12 | – | 8, dazu 2 Texthinweise |
| nicht ermittelt | 3 | 5 | – | 6 |
| Kosten | 0,66 $ | 0,33 $ | 0,31 $ für zwei Fehlversuche | 0,16 $ |
| Dauer | 2 min 0 s | 7 min 46 s | 9 min 19 s und 10 min 44 s, dann Abbruch | 3 min 31 s |

- **Grundflächenzahl (Artikel UC 9, S. 14):** Sie ist gestaffelt: 90 % bis 200 m² Grundstück, darüber 90 % der ersten 200 m², 50 % der nächsten 200 m², 20 % des Rests. Opus (PDF und Text) und Kimi machen daraus pauschal 0,9, und die Fundstelle gilt als bestätigt, weil der Satz wörtlich vorkommt. Opus 5.5 und beide DeepSeek-Modelle geben die Staffel als Texthinweis wieder und lassen die Zahl offen. Das Regelschema kennt nur einen Wert (`MaxFootprintRatio.ratio`); eine Staffel ist nicht abbildbar. Die Auswertung in der Analyse-Instanz trägt deshalb 0,9 als wirksam: bei 600 m² Grundstück 540 m² statt 320 m² Grundfläche. Offener Punkt: Staffel im Schema und in der Berechnung, bis dahin Hinweis in der Anweisung.
- **Kimi K3** stimmt bei allen Abständen, Zaun, Stellplätzen und Bäumen mit Opus überein und findet zusätzlich die 10 % unversiegelte Fläche (S. 20, bei Opus „nicht ermittelt“). Höhe, Dach und Fassade liest es richtig, zitiert aber zwei nicht zusammenhängende Sätze als ein Zitat; die Prüfung findet das Zitat nicht und setzt die Regeln auf „nicht ermittelt“. DeepSeek V4 Pro verhält sich dabei genauso.
- **Opus 5.5** lehnt den erzwungenen Funktionsaufruf ab (`tool_choice: type "tool" and "any" are not supported for this model`, bei allen Anbietern); die Modellliste von OpenRouter zeigt das nicht, der Dialog bietet das Modell also an, und jede Auswertung damit scheitert. Im Probelauf mit freiem Funktionsaufruf (`tool_choice: auto`) und der Bitte im Systemprompt, das Werkzeug zu nutzen, lief es sauber: gegenüber Opus 5 zusätzlich Staffel statt 0,9, hinterer Abstand des Hauptgebäudes, 10 % unversiegelt und 2 m zwischen Nebengebäuden; dafür fehlen Zaun (2 m) und der Hinweis auf die 6-m-Bauverbotszone an Wasserläufen, und beim hinteren Abstand fehlt die Höhengrenze von 3 m auf der Grenze.
- **Qwen3.8 Max** brach zweimal nach 20 000–23 000 Ausgabe-Token mit `finish_reason: error` des Anbieters ab; die Antwort war kein gültiges JSON (`invalid_json`).
- **Denkaufwand:** OpenRouter nimmt inzwischen `xhigh` und `max` an (je Modell `reasoning.supported_efforts` in der Modellliste); `_effort` in `openrouter.py` macht daraus noch `high`.
- **Kosten:** Der Stand `total_usage` von OpenRouter hinkt hinterher; drei der Zuwächse entsprechen auf den Cent einem von uns berechneten Aufruf (Kimi Gegenprüfung, beide DeepSeek-Pro-Aufrufe), die Rechnung nach Listenpreis passt also.

**Prüflauf:** Backend 660 Tests mit `TEST_S3=1` (vorher 657; neu je ein Test zum Aufbau der Anfrage mit Text, zur Eingabeform nach der Wahl und zur Auswertung eines Kapitels mit Textschicht und Seitenmarken), ruff, Format und mypy grün. Frontend 203 Tests (vorher 202; Kennzeichen und Hinweis „liest Text statt PDF“), Lint, Typprüfung und Build grün. `openapi.json` und `schema.d.ts` neu erzeugt.
