# AN7 – Gescannte PDFs (Emprise Analyse)

> **Status:** geplant und umgesetzt am 29.09.2026 (Auftrag: „weiter mit AN6 und AN7“; AN7 zuerst, weil RA2 vor RA3); Befunde beim Bau in 7.5, Abnahme in 6 · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN7), 6 (E-A7); [PLAN_AN1_PARZELLE.md](PLAN_AN1_PARZELLE.md) 8 (PDF-Plan, UP13–UP16); [PLAN_AN2_PLU.md](PLAN_AN2_PLU.md) (Reglement hochladen, PU03); [PLAN_AN3_ANALYSE.md](PLAN_AN3_ANALYSE.md) 3.7 (Zusatzdokumente); ANNAHMEN RW03 (Scan → Meldung), UP16 (`upload_pdf_no_vector`), PU12 (Text statt PDF) · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN7 (SC01 ff.)
> **Voraussetzung:** AN0–AN5. Fachregeln: `BACKEND_SPEZIFIKATION.md` 1.2 (L3 Zitatpflicht, L5 Server maßgeblich), 5.2.3 (Seitentexte, Zitatprüfung), 10.1 (Dateien aus fremder Hand).

---

## 1. Zweck und Umfang

Heute weist Emprise Analyse gescannte Unterlagen ab: Ein Parzellenplan ohne Linien endet mit `422 upload_pdf_no_vector` (UP16), ein Reglement mit mehr als der Hälfte Seiten ohne Text mit `document_no_text` (RW03, PU03). Einzelne Seiten ohne Text in einem sonst lesbaren Reglement zählen als leer; Werte von dort bleiben „nicht ermittelt“. In der Praxis liegen aber gerade ältere PLU, Änderungsstände, règlements de lotissement und Pläne des Geometers oft nur als Scan vor.

**Entscheidungen des Nutzers (29.09.2026)** auf drei Fragen mit Empfehlung:

| Frage | Entscheidung | Folge |
|---|---|---|
| Wie werden gescannte Reglements und Zusatzdokumente gelesen? | **Lokale Texterkennung** (Tesseract im Worker) | Keine Kosten je Seite; der Hinweis vor der Verarbeitung nennt Dauer und Grenzen statt Mehrkosten (E-A7 angepasst, 3.2) |
| Wie wird eine gescannte Parzelle eingebracht? | **Scan als Vorlage nachzeichnen** | Keine KI; Maßstab aus dem Plan oder über zwei Punkte; die Geometrie bleibt in der Hand des Architekten (3.5) |
| AN6 | Plan und technische Basis nach AN7 | eigener Plan `docs/PLAN_AN6_MANDANTEN.md` |

**Enthalten:**

1. Reglement und Zusatzdokumente als Scan: Hinweis, Bestätigung, Texterkennung als Job in Teilen, danach Kapitel, Zonenwahl und Auswertung wie bei einem PDF mit Text.
2. Einzelne Seiten ohne Text in einem lesbaren Dokument auf Wunsch nachträglich erkennen.
3. Zitatprüfung (L3) gegen den erkannten Text; die vorhandene Zahlenprüfung greift dort ebenso (3.3). Kennzeichnung „aus Scan“ an Regel, Zitat und im Bericht.
4. Parzelle aus gescanntem PDF oder aus einem Bild (JPEG, PNG) nachzeichnen: Seite als Hintergrund, Maßstab, Ecken klicken, Längen korrigieren, dann wie Weg E.

**Nicht enthalten:** Texterkennung im GPU-Weg des Konfigurators (E-AN7-6), Handschrift, Erkennung von Tabellenstruktur, automatische Umrisserkennung aus dem Bild, KI-Abschrift (verworfen, 7.2).

---

## 2. Befund

| Stelle | Stand | Folge für AN7 |
|---|---|---|
| `app/rules/pdf.py::read_text` | `pypdf`, Seiten unter 40 Zeichen gelten als leer (`empty_pages`) | Grundlage bleibt; erkannte Seiten ersetzen den leeren Text |
| `app/rules/documents.py::read_document` | mehr als 50 % leer → `failed: document_no_text`, **ohne** `source_file` | stattdessen Datei und Seiten speichern, Status `scan`, Hinweis anbieten |
| `source_page` | Textschicht je Seite; Grundlage von Kapitelsuche, Zitatprüfung, Nachsuche | erkannte Texte landen hier; neue Spalte kennzeichnet sie (4.1) |
| `rules/domain/text.py::verify_quote` | Ähnlichkeit ≥ 0,9 über einen gleich langen Ausschnitt (`partial_match`); jede Zahl des Zitats muss im Ausschnitt stehen (`_numbers_match`) – im Entwurf übersehen (7.5 Nr. 1) | trägt Erkennungsfehler von 2–5 % (Messung 7.1); auf Scan-Seiten prüft sie die Zahlen gegen den erkannten Text |
| `rules/domain/assess.py::assess_rule` | Zahlen der Parameter müssen **im Zitat des Modells** stehen (`values_in_quote`) | unverändert; mit `_numbers_match` ist die Kette Parameter → Zitat → Seite geschlossen (3.3) |
| `integrations/openrouter.py` | PDF-Auszüge als `file` (Modelle mit PDF-Eingabe) oder Textschicht (PU12) | Claude liest Scan-Seiten als Bild; im Textmodus geht der erkannte Text. OpenRouter nutzt ohne Angabe die PDF-Eingabe des Modells, **sonst Mistral OCR für 2 $ je 1 000 Seiten** (Doku, abgerufen 29.09.2026) – im Textmodus fällt das nicht an |
| `extract.input_hash` | enthält Quelle, Kapitel, Modell, Prompt – **nicht** die Seitentexte | im Textmodus ändert die Erkennung die Eingabe → Kennung der Erkennung in den Hash (3.4) |
| `site/domain/pdfplan.py` | Linien per `pdfminer.six`, Maßstab aus dem Text, `PdfWithoutLines` bei Scans | Scan führt statt zur Ablehnung zum Nachzeichnen (3.5) |
| `site/FreiesZeichnen.tsx`, `site/manual.ts` | Punkte auf 40-m-Raster klicken → Kanten (Länge, Azimut) bearbeiten → `PUT /site` mit `edges` | derselbe Weg, nur mit Scan als Hintergrund und Maßstab |
| Worker | ein Prozess, Jobs nacheinander, Reihenfolge `run_after, created_at` | Erkennung in Teilen zu 20 Seiten, damit andere Jobs dazwischen laufen (3.2) |
| Image | `python:3.12-slim-bookworm`, WeasyPrint-Bibliotheken | dazu `tesseract-ocr`, `tesseract-ocr-fra` (Debian 5.3.0, mit `osd`), Python `pypdfium2` (BSD-3/Apache-2.0), `pillow` ausdrücklich |
| CI | Backend auf `ubuntu-24.04` mit `uv`, ohne Docker | Schritt `apt-get install tesseract-ocr tesseract-ocr-fra` |

**Machbarkeit gemessen (29.09.2026, lokal, 12 Kerne):** Vier Seiten des Kapitels UC von Beyenes als Scan nachgebildet (200 dpi, 0,7° schief, leicht unscharf, JPEG 70 %), mit `pypdfium2` bei 300 dpi gerendert, Tesseract 5.3.0 `-l fra --psm 1`:

| Seite | Rendern | Erkennung | Ähnlichkeit zur Textschicht (ganze Seite, ohne Leerraum) |
|---|---|---|---|
| 9 | 154 ms | 2,5 s | 0,972 |
| 12 | 154 ms | 1,9 s | 0,951 |
| 15 | 142 ms | 2,4 s | 0,975 |
| 18 | 118 ms | 2,8 s | 0,978 |

Ein Thread ist kaum langsamer (2,2–2,5 s). Eine um 90° gedrehte Seite liest `--psm 1` mit 0,975, `--psm 3` mit 0,092. Typische Fehler: „ef“ statt „et“, fehlende Kopf- und Fußzeilen. Platz im Image: etwa 16 MB Sprachdaten, 6 MB Bibliotheken, 8 MB `pypdfium2`.

---

## 3. Fachliche Festlegungen

### 3.1 Wann ein Dokument ein Scan ist

- **Scan:** mehr als die Hälfte der Seiten ohne Text (`NO_TEXT_SHARE`, unverändert). Das Dokument wird gespeichert (Datei, Seiten, `source_file`), bekommt den Status `scan` und ist erst nach der Erkennung nutzbar.
- **Einzelne Seiten ohne Text:** das Dokument ist sofort nutzbar wie heute. Die Zeile „n Seiten ohne Text“ bekommt die Schaltfläche „Text dieser Seiten erkennen“. Das lohnt sich bei eingefügten Änderungsseiten; bei Plänen und Abbildungen bleibt die Seite danach weitgehend leer.
- Erkannt werden immer nur Seiten ohne Textschicht. Eine vorhandene Textschicht ist genauer als jede Erkennung und bleibt.

### 3.2 Hinweis, Bestätigung, Ablauf

E-A7 verlangte einen Hinweis vor der Verarbeitung, weil ein Scan mehr kostet. Mit lokaler Erkennung kostet er kein Geld, aber Zeit, und der Text ist fehleranfälliger. Der Hinweis bleibt deshalb, mit anderem Inhalt:

> „Dieses PDF ist ein Scan (74 von 74 Seiten ohne Text). Emprise kann den Text erkennen; das dauert etwa 4 Minuten. Erkannter Text kann Lesefehler enthalten; Tabellen und Handschrift werden schlecht gelesen. Werte aus erkannten Seiten sind als ‚aus Scan‘ gekennzeichnet; lässt sich ein Zitat im Scan nicht bestätigen, bleibt der Wert ‚nicht ermittelt‘.“ – [Text erkennen]

- Die geschätzte Dauer ist Seitenzahl × `EMPRISE_OCR_SECONDS_PER_PAGE` (Vorgabe 3 s, auf Unraid nachmessen).
- Nach der Bestätigung (`POST /projects/{id}/regulations/{document_id}/ocr`, `202`) plant der Server den Job `rules_document_ocr`. Er erkennt höchstens 20 Seiten je Lauf, speichert jede Seite sofort und plant den nächsten Teil. Andere Jobs (Gelände, Bericht, Auswertung) warten so höchstens einen Teil ab (20 × 3 s ≈ 1 min), nicht die ganze Erkennung.
- Danach läuft die Kapitelsuche (bei einem Scan) bzw. eine Nachsuche nach neuen Kapiteln (bei einzelnen Seiten; vorhandene Kapitel bleiben unberührt). Der Status wechselt auf `active`.
- Die Oberfläche zeigt den Fortschritt („Seite 40 von 74“). Nach der Erkennung erscheint eine Zeile: „74 Seiten erkannt, 3 davon unsicher (S. 12, 40, 41); 2 auch danach ohne Text“. Als **unsicher** gilt eine Seite mit mittlerer Wortsicherheit unter 70 (Tesseract, 0–100).
- Dasselbe Dokument (gleiche Prüfsumme) wird nur einmal erkannt, auch wenn mehrere Projekte es nutzen (E-AN2-1).
- Scheitert die Erkennung (Zeitlimit, defekte Seite), bleibt die Seite leer und der Lauf geht weiter. Nur wenn nichts erkannt wurde, steht das Dokument auf `failed: ocr_failed`, mit der Möglichkeit, es erneut zu versuchen.

### 3.3 Zitatprüfung auf Scan-Seiten (L3)

Das Modell liest im PDF-Modus die Seitenbilder, Tesseract liest dieselben Bilder unabhängig davon. Stimmen beide Lesungen überein, ist das ein stärkerer Beleg als jede einzelne. Daraus folgt:

1. Das Zitat muss wie bisher mit Ähnlichkeit ≥ 0,9 auf der Seite stehen (`verify_quote`). Erkennungsfehler von 2–5 % senken die Ähnlichkeit eines Zitats kaum unter diese Schwelle (Messung 7.1 Nr. 2; Abnahme 3: 0,986–1,0).
2. **Zahlen:** `values_in_quote` verlangt jede Zahl der Parameter im Zitat, `_numbers_match` in `verify_quote` jede Zahl des Zitats im gefundenen Ausschnitt der Seite – auf einer Scan-Seite also im erkannten Text. Liest Tesseract eine 5 statt einer 6, fällt das Zitat durch. Eine neue Prüfung braucht es deshalb nicht (7.5 Nr. 1). Die Hochzahl von m² und m³ zählt dabei nicht als Zahl: Die Texterkennung liest sie als „m?“ oder „m°“ (7.5 Nr. 4).
3. **Grund:** Eine nicht bestätigte Regel auf einer Scan-Seite bekommt statt `quote_unverified` den Grund `scan_unconfirmed` („nicht ermittelt: im Scan nicht sicher lesbar, im Dokument prüfen“; `extract.scan_reasons`). Ohne Fundstelle (keine Seite erreichte eine Ähnlichkeit) entscheidet das Kapitel: Liegt es ganz im Scan, gilt der Grund auch dann (7.5 Nr. 5).
4. Regeln mit Zitat auf einer Scan-Seite tragen `from_scan: true` (abgeleitet aus `rule.source_file_id` und `page`, keine neue Spalte an `rule`), ebenso Fundstellen im Baurahmen und in der Analyse (`CitationOut.from_scan`, nicht Teil der Prüfsumme des Baurahmens). Die Oberfläche zeigt am Zitat „aus Scan“; im Bericht steht „(Scan)“ hinter der Seite.
5. Die Gegenprüfung (RW19) und die Nachsuche arbeiten unverändert. Beide lesen dieselbe Eingabe wie die Auswertung.

Kein neues `ENGINE_VERSION`: Grund und Hochzahl wirken nur, wo Zitat und Seite verschieden gelesen wurden – auf einer Textschicht haben beide dieselbe Form. Eine neue Version ließe `rules_housekeeping` alle Kapitel neu bewerten (BETRIEB 15).

### 3.4 Eingabe an das Modell

- **PDF-Modus (Standard, Claude):** unverändert der Seitenauszug; Scan-Seiten gehen als Bild. Wird ein Auszug größer als `PDF_REQUEST_MAX_BYTES` (`extract.py`, 20 MB; ein Scan mit 300 dpi hat 0,3–1 MB je Seite), geht für diesen Aufruf der erkannte Text statt des PDF (Log `rules_input_as_text`). Die Grenze der Anbieter liegt bei etwa 32 MB je Anfrage, und Base64 macht ein Drittel mehr.
- **Textmodus (PU12):** der erkannte Text mit denselben Seitenmarken. `input_hash` bekommt eine Kennung der Erkennung (`ocr_stamp`: Zeitpunkt der abgeschlossenen Erkennung, `ocr_finished_at`), aber **nur** im Textmodus und **nur**, wenn eine Erkennung abgeschlossen ist. Alle bisherigen Kennungen und gespeicherten Teilantworten bleiben dadurch gültig.
- Nach einer nachträglichen Erkennung einzelner Seiten (3.1) bleiben die Antworten im PDF-Modus gültig, weil das Modell dieselben Bilder sah. Eine neue Bewertung ohne Aufruf („Neu bewerten“ aus AN4 bzw. `force`) prüft die Zitate dann gegen den erkannten Text.

### 3.5 Parzelle nachzeichnen

**Ablauf:**

1. Der Architekt lädt ein PDF hoch. Bei `upload_pdf_no_vector` fragt die Oberfläche: „Das PDF ist ein Scan. Als Vorlage nachzeichnen?“. Ein Bild (JPEG, PNG) führt direkt dorthin.
2. `POST /projects/{id}/site/scan` (Datei, optional `page`) gibt die Seite als JPEG zurück, zusammen mit Seitenzahl, Pixelmaß, Papiermaß in mm (aus dem PDF bzw. aus den dpi eines Bilds, wenn vorhanden) und den im erkannten Text gefundenen Maßstäben (`SCALE_PATTERN` aus `pdfplan.py`). Gespeichert wird nichts (3.6).
3. **Maßstab:** Gibt es ein Papiermaß und genau einen Maßstab (bei Bildern nur mit mindestens 150 dpi in den Metadaten; 72 und 96 dpi sind Vorgaben von Kameras und Programmen, keine Messung), rechnet die Oberfläche daraus Meter je Pixel („Maßstab 1:500 aus dem Plan“). Sonst, oder wenn der Architekt es wählt, **zwei Punkte mit bekanntem Abstand** anklicken und die Länge eintragen. Das ist der sichere Weg, weil er auch Kopien mit 95 % oder 141 % Vergrößerung richtig misst.
4. Ecken der Parzelle im Uhrzeigersinn anklicken, mit Zoom (1×–4×) und Rückgängig. Norden gilt als oben, wie bei UP15; die Lage folgt später per AN5.
5. Danach der bekannte Schritt aus Weg E: Kanten mit Länge und Richtung, von Hand nach den Maßen im Plan zu korrigieren, dann `PUT /site` mit `edges`. Der Server bildet daraus das Polygon (L5).
6. Die Herkunft steht in `source_info.trace`: Dateiname, Seite, Maßstabsweg (`plan` mit Zahl oder `calibrated` mit Bezugslänge). Die Oberfläche zeigt „nachgezeichnet nach Scan <Datei>“. `origin` bleibt `manual_sketch`, es gibt keine neue Herkunftsart.

**Grenzen:** Maximal 3 Seiten (wie `pdfplan.MAX_PAGES`). Gerendert wird mit höchstens 4 000 Pixel an der langen Seite (`SCAN_RENDER_PX`, A3 bei etwa 240 dpi). Über das Netz geht ein JPEG mit höchstens 2 500 Pixeln (etwa 0,3–0,8 MB). Die Maßstabssuche mit Tesseract dauert 2–3 s und läuft im Aufruf; sie ist durch `site_write` begrenzt. Nennt der Plan mehrere Maßstäbe, gilt der ausdrücklich benannte der Ausgabe („Échelle d'édition“). Scheitert die Texterkennung, kommt die Vorschau ohne Maßstab (Log `site_scan_ocr_failed`); dann kalibrieren.

### 3.6 Daten, Sicherheit, Datenschutz

- Hochgeladene Scans des Reglements liegen wie jedes Reglement im Objektspeicher (öffentliche Unterlagen, E-AN2-4). Der Scan einer Parzelle wird **nicht** gespeichert: Er dient nur als Vorlage, und Pläne des Geometers können Namen der Eigentümer enthalten (Datenminimierung).
- PDFs und Bilder kommen aus fremder Hand (Spez. 10.1). Größe und Seitenzahl sind wie bisher begrenzt. Beim Rendern gilt eine Pixelobergrenze (kein Bild über 40 Megapixel; `Image.MAX_IMAGE_PIXELS`), `pypdfium2` wird aktuell gehalten, Tesseract bekommt nur Bilder. Jede Seite hat ein eigenes Zeitlimit (`subprocess` mit `timeout=60`).
- Tesseract läuft als eigener Prozess, `OMP_THREAD_LIMIT=1`: Mehr Threads bringen laut Messung kaum etwas und nähmen API und Datenbank auf dem Unraid-Server Rechenzeit weg.
- Nichts geht an Dritte. Die Erkennung ändert den Datenweg nicht (D3/D4).

### 3.7 Oberfläche

- **Bebauungsplan, Zusatzdokumente:** Status `scan` → Hinweis (3.2) mit [Text erkennen]; während der Erkennung Fortschritt und die Zeile „Andere Aufgaben laufen dazwischen weiter“; danach die Zusammenfassung. Bei einzelnen leeren Seiten die Schaltfläche an der vorhandenen Zeile.
- **Regeln (Analyse, `RegelnSimulation`), Zusatzdokumente, Vergleich, Korrektur:** Marke „aus Scan“ am Zitat (`AusScan`), mit dem Titel „Zitat aus der Texterkennung – Lesefehler möglich, im Dokument prüfen“; in Zusatzdokumenten und Vergleich über `CitationOut.from_scan`. Dazu der neue Grund `scan_unconfirmed` in den Übersetzungen (`rules.reason`, gespiegelt ins Backend, README Regel 6).
- **Parzelle hochladen:** Formate „DXF, GeoJSON, PDF – auch gescannt – oder Bild“; Nachzeichnen als eigener Schritt (`ScanNachzeichnen.tsx`). Die Kantenbearbeitung aus `FreiesZeichnen` wird gemeinsam genutzt.
- **Bericht:** in der Dokumententabelle „Scan, Text erkannt (n Seiten)“; bei Regeln „S. 12 (Scan)“; in der Herkunft der Parzelle „nachgezeichnet nach Scan“.

---

## 4. Architektur

### 4.1 Datenmodell (Migration 0019)

| Tabelle | Änderung |
|---|---|
| `land_use_plan` | Status `scan` zulassen (Prüfbedingung `status_known`) |
| `source_file` | `ocr_state varchar(10) NOT NULL DEFAULT 'none'` (`none`, `offered`, `running`, `done`, `failed`), `ocr_error text`, `ocr_started_at`, `ocr_finished_at` |
| `source_page` | `ocr_confidence real NULL` – NULL: Textschicht; sonst erkannt, mittlere Wortsicherheit 0–100 |

`empty_pages` bleibt die Liste der Seiten ohne Textschicht. Fortschritt = erkannte unter ihnen / alle. Keine Spalte an `rule`: `from_scan` wird beim Lesen abgeleitet.

### 4.2 Backend

- **`app/platform/scan.py`** (Kern, von `rules` und `site` genutzt): `page_count(data)`, `render(data, page, *, dpi, max_px) -> PIL.Image` (PDF über `pypdfium2`, Bild über Pillow, EXIF-Drehung beachtet), `recognize(image) -> Recognized(text, confidence)` (Tesseract TSV → Text nach Block, Absatz und Zeile; mittlere Sicherheit der Wörter), `ScanProblem` mit Fehlercodes. Keine Datenbank, keine Fachlogik.
- **`app/rules/ocr.py`:** `request(db, project_id, document_id, actor)` (prüft Zugriff über `project_regulation`, `409 document_not_ready`/`ocr_not_needed`, Audit `regulation_document.ocr`), `run_batch(db, source_id)` (Job), `finish(db, source_id)` (Kapitel suchen bzw. ergänzen, Status `active`), `mark_failed`. Den Hinweis setzt `read_document` selbst (`ocr_state = offered`). Die Kapitelsuche steht in `documents.index_document`, die Lesen und Erkennung nutzen.
- **Job `rules_document_ocr`** (`max_attempts=3`, `timeout_seconds=900`, Teil zu 20 Seiten `BATCH_PAGES`, nächster Teil per `enqueue` mit Schlüssel `rules_document_ocr:<source>:<erste offene Seite>`). Scheitert er dreimal, steht der Fehlercode der Erkennung am Dokument (`ocr_unavailable`), sonst `interrupted:<Art>`.
- **`documents.read_document`:** speichert bei einem Scan Datei und Seiten, setzt `scan` und `ocr_state = offered`; `document_no_text` entfällt als Fehler des Lesens.
- **Schemas:** `RegulationDocumentOut` bekommt `status: … | "scan"` und `ocr: OcrOut | null` (`state`, `pages_total`, `pages_done`, `uncertain_pages`, `still_empty_pages`, `estimated_seconds`, `error`); `RuleOut` und `CitationOut` bekommen `from_scan`.
- **Zitatprüfung:** `QuoteCheck` bleibt unverändert (7.5 Nr. 1); `_numbers_match` übergeht Hochzahlen von Einheiten; `extract.scan_reasons` setzt den Grund. `extract._Calls` lädt `scan_pages`.
- **Kapitelsuche** (`chapters.detect_structure`): Seiten mit mindestens drei Zonenüberschriften gelten als Inhaltsverzeichnis (`TOC_MIN_HEADINGS`); finden die Überschriften mehr Kapitel als das Verzeichnis, gelten sie (7.5 Nr. 2–3). Gilt für alle Dokumente, auch mit Textschicht und im GPU-Weg.
- **`app/site`:** `POST /projects/{id}/site/scan` → `ScanPreviewOut`; `SiteIn.trace: TraceIn | None` → `source_info.trace`; Upload erlaubt `.jpg`, `.jpeg`, `.png` nur für die Vorschau (der Upload der Parzelle selbst bleibt bei DXF, GeoJSON, PDF).
- **Bericht:** `analysis/report.py` liest `from_scan` (Quelle „(Scan)“), `ocr` (Unterlagen „Scan, Text erkannt (n Seiten)“) und `source_info.trace` (Herkunft „nachgezeichnet nach Scan“, Datei, Maßstab).

### 4.3 Frontend

- `api/regulations.ts`: `useRequestOcr`; die Abfrage wird alle 5 s neu geladen, solange `ocr.state = running` (höchstens eine Stunde), sonst wie beim Lesen.
- `products/analyse/Bebauungsplan.tsx`, `Zusatzdokumente.tsx`: gemeinsame Komponente `ScanHinweis.tsx`; Fehlertexte in `fehler.ts` (sonst Importzyklus, 7.5 Nr. 11).
- `products/analyse/ScanNachzeichnen.tsx` und `scan-nachzeichnen.ts` (reine Rechnung: Meter je Pixel aus Maßstab oder zwei Punkten, Pixel → lokale Meter), `site/KantenBearbeiten.tsx` aus `site/FreiesZeichnen.tsx` herausgelöst; `api/site.ts`: `useScanPreview`, `useFormManualSite` mit `trace`.
- Marke „aus Scan“ (`AusScan`) in `rules/RegelnSimulation.tsx` (und damit überall, wo Regeln mit Zitat erscheinen) und an Werten der Zusatzdokumente.

---

## 5. Arbeitsschritte

1. **Werkzeuge:** Dockerfile (`tesseract-ocr`, `tesseract-ocr-fra`), `pypdfium2` und `pillow` in `pyproject.toml`, CI-Schritt `apt-get install`. `app/platform/scan.py` mit Tests (erzeugtes Bild mit französischem Text, gedrehte Seite, Bild zu groß, defektes PDF).
2. **Migration 0019** und Modelle.
3. **Reglement:** `read_document` für Scans, `rules/ocr.py`, Job, Endpunkt, Schemas, OpenAPI. Integrationstest: Scan-PDF im Test erzeugen (WeasyPrint → `pypdfium2` → Pillow, also ohne Binärdatei im Repo), hochladen, bestätigen, Job in Teilen laufen lassen, Kapitel und Seiten prüfen; einzelne leere Seiten nachträglich erkennen.
4. **Zitatprüfung:** Ausschnitt in `QuoteCheck`, Zahlenprüfung auf Scan-Seiten, `from_scan`, `input_hash` im Textmodus, Größengrenze für PDF-Auszüge. Einheitstests.
5. **Parzelle:** `POST /site/scan`, `trace` im `SiteIn`. Tests: Bild mit Maßstabstext, PDF-Scan, zu großes Bild, Kanten mit `trace`.
6. **Oberfläche:** Hinweis und Fortschritt, Marke, Nachzeichnen mit Maßstab und Zoom, Texte de/fr, Spiegelung der Gründe (`tools/sync-check-texts.cjs`). Komponententests.
7. **Bericht:** Kennzeichnungen.
8. **Abnahme** (5.) und Dokumentation: ANNAHMEN SC01 ff., BETRIEB 15, PLAN_ANALYSE, README (Stolperstellen), AGENTS.

---

## 6. Abnahme

1. **Vollständiger Prüflauf:** Backend (ruff, Format, mypy, pytest) und Frontend (Typprüfung, Lint, Tests, Build); `schema.d.ts` aus `api:types` unverändert eingecheckt.
2. **Kapitel aus dem Scan:** Beyenes (74 Seiten) als Scan nachgebildet hochladen → Hinweis mit Dauer → Erkennung → dieselben neun Kapitel mit denselben Seitenbereichen wie aus der Textschicht (UC 9–20 … N 68–74). Dauer je Seite messen und in BETRIEB eintragen.
3. **Zitatprüfung ohne Kosten:** Die gespeicherten Antworten der Beyenes-Auswertung (Kapitel UC) ohne neuen Aufruf gegen den erkannten Text bewerten. Belegte Zitate: mindestens 95 % des Werts mit Textschicht; jede Abweichung erklärt (Zahl im Scan anders gelesen → `scan_value_unconfirmed`, sonst Befund).
4. **Eine bezahlte Auswertung** des Scan-Kapitels UC nur nach Freigabe des Nutzers (geschätzt wie mit Text, etwa 1,5 $ mit Opus 5.5). Ohne Freigabe entfällt der Punkt und steht im Bericht als offen.
5. **Parzelle:** ein Katasterauszug als Bild und als Scan-PDF (im Test erzeugt: Umriss, Maßzahlen, „Échelle 1/500“) → Maßstab aus dem Plan erkannt → Ecken klicken → Fläche weicht höchstens 2 % vom Sollwert ab; derselbe Plan mit zwei Punkten kalibriert.
6. **Nebenläufigkeit:** Während einer Erkennung laufen ein Geländeabruf und ein Bericht; beide warten höchstens einen Teil.
7. **Browser:** Deutsch und Französisch, Telefonbreite ohne seitliches Scrollen.

**Ergebnis (29.09.2026, lokal):**

| Nr. | Ergebnis |
|---|---|
| 1 | Backend 767 bestanden, 2 übersprungen (S3) nach allen Änderungen aus 7.5; ruff, Format, mypy sauber. Frontend 35 Dateien, 238 Tests, Typprüfung, Lint, Build; `schema.d.ts` unverändert zu `api:types` |
| 2 | Scan nachgebildet wie in 2 (150 dpi, 0,4° gedreht, JPEG 70 %, 19,8 MB). Hinweis „74 von 74 Seiten ohne Text … etwa 4 Minuten“. Erkennung 74 Seiten in 223 s (**3,0 s je Seite**, Teile 51/61/58/44 s; erster Lauf parallel zur vollständigen Testsuite 232 s). Erster Lauf nur 3 Kapitel (7.5 Nr. 3), nach der Änderung: **10 Kapitel mit denselben Seitenbereichen** wie die Kapitelsuche auf der Textschicht (UC 9–20, UR 21–32, UE 33–36, UAE 37–41, UGD 42–46, UIg 47–50, AUR 51–57, AU 58–59, A 60–67, N 68–74); Abweichungen: Kürzel „Uig“ (7.5 Nr. 15), allgemeine Seiten 1–8 statt 5–8 (das Verzeichnis ist unlesbar, es gilt die Vorgabe der Überschriftensuche), Sektorvorschläge UR2–UR4 statt UR1–UR4 und N mit zusätzlichem „Ni“. Zusammenfassung „74 Seiten per Texterkennung gelesen, davon 1 unsicher (S. 3); 1 auch danach ohne Text (S. 2)“ |
| 3 | Gespeicherte Antworten des Kapitels UC (18 Regeln mit belegtem Zitat), ohne Aufruf gegen den erkannten Text bewertet: erster Lauf 13 von 18 (7.5 Nr. 4), danach **18 von 18** mit gleichem Status und gleichen Werten; Ähnlichkeit 0,986–1,0 |
| 4 | **Offen:** bezahlte Auswertung des Scan-Kapitels UC (etwa 1,5 $ mit Opus 5.5) wartet auf die Freigabe des Nutzers |
| 5 | Katasterauszug als PNG (200 dpi) im Browser: „Im Plan gefunden: 1:500, Blatt 210 × 148 mm“, vier Ecken geklickt, Blattbreite 105 m; Kanten 29,8/19,7/30,6 m → 606 m², nach Korrektur auf die Maße 610,9 m² (Soll 600 m², +1,8 %, 7.5 Nr. 13). Herkunft „nachgezeichnet nach Scan“, Datei und Maßstab in Projektseite und Bericht. PDF-Scan und Kalibrierung über zwei Punkte in Tests (`test_scanned_plan_becomes_a_template_with_its_scale`, `scan-nachzeichnen.test.ts`: Kopie mit 141 % richtig gemessen); im Browser nur bis zur Aufforderung zum Kalibrieren geprüft |
| 6 | Während der Erkennung ein Bericht und ein Geländeabruf angestoßen: Bericht wartete 43 s (Ende des ersten Teils), Geländeabruf 41 s; Géorisques scheiterte dabei einmal von außen (`RemoteProtocolError`), der zweite Versuch lief nach dem nächsten Teil. Beide warteten höchstens einen Teil |
| 7 | Deutsch und Französisch geprüft (Hinweis, Fortschritt, Zusammenfassung, Zonenwahl, Nachzeichnen); Telefonbreite 375 px ohne seitliches Scrollen, auch beim Nachzeichnen mit Zoom 4× (Bild scrollt in seinem Rahmen). Gefunden: französische Zusammenfassung ohne Leerzeichen vor „;“ → Trennzeichen in die Übersetzung (`analyse.scan.withEmpty`). Die Fortschrittsanzeige steht still, solange der Tab verborgen ist (React Query fragt dann nicht nach) und holt beim Zurückkehren auf |

---

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | E-A7 begründete Hinweis und Bestätigung mit Mehrkosten. Mit lokaler Erkennung gibt es keine Mehrkosten | Ein Hinweis „kostet mehr“ wäre falsch | 3.2: Hinweis nennt Dauer und Grenzen; die Bestätigung bleibt, weil eine lange Erkennung den einzigen Worker belegt und ein Fehlupload sonst Minuten kostet |
| 2 | Die Messung vergleicht ganze Seiten; die Zitatprüfung arbeitet auf Ausschnitten. Ein kurzes Zitat mit einem Lesefehler hat anteilig mehr Fehler | Kurze Zitate könnten unter 0,9 fallen | Abnahme 3 misst es an echten Antworten; `QUOTE_MIN_CHARS` verhindert ganz kurze Zitate schon heute. Liegt der Anteil unter 95 %, wird für Scan-Seiten eine eigene Schwelle erwogen – nicht vorab gesenkt |
| 3 | `input_hash` enthält keine Seitentexte | Im Textmodus würden nach einer Erkennung alte Antworten auf leere Seiten wiederverwendet | 3.4: Kennung der Erkennung, nur im Textmodus |
| 4 | Eine einzige Aufgabe für 333 Seiten (etwa 15 min) belegt den einzigen Worker; das Zeitlimit von 900 s reicht auf einem langsameren Server nicht | Gelände und Bericht warten, der Job bricht ab | 3.2: Teile zu 20 Seiten, jede Seite sofort gespeichert; ein Abbruch verliert höchstens eine Seite |
| 5 | Scan-Seiten als PDF-Auszug können groß werden (0,3–1 MB je Seite) | Anfrage über der Grenze des Anbieters → Fehler, der Lauf kostet trotzdem | 3.4: Grenze 20 MB, darüber erkannter Text |
| 6 | OpenRouter nutzt ohne PDF-Eingabe des Modells Mistral OCR (kostenpflichtig) | Ein Modell ohne PDF-Eingabe im PDF-Modus erzeugte stille Zusatzkosten | Besteht schon heute; PU12 (Textmodus) vermeidet es. In BETRIEB 15 als Stolperstelle vermerkt |
| 7 | `read_document` speichert bei `document_no_text` keine Datei | Für den Hinweis fehlten Seitenzahl und Datei | 3.1: Datei und Seiten immer speichern |
| 8 | Ein Dokument ist über die Prüfsumme mehreren Projekten zugeordnet | Zwei Bestätigungen würden doppelt erkennen | 3.2: Zustand am `source_file`; eine zweite Bestätigung bei `running` oder `done` ändert nichts (`202` mit dem Zustand) |
| 9 | Das Nachzeichnen hat keinen verlässlichen Maßstab, wenn der Scan nicht in Originalgröße vorliegt | Alle Längen falsch um denselben Faktor | 3.5: Zwei-Punkt-Kalibrierung angeboten und empfohlen; die Kantenlängen bleiben von Hand korrigierbar |
| 10 | Pläne des Geometers können Eigentümernamen enthalten | Personenbezogene Daten ohne Zweck gespeichert | 3.6: Scan der Parzelle wird nicht gespeichert |
| 11 | Ein neuer Grund (umgesetzt als `scan_unconfirmed`) muss in Frontend, Backend-Übersetzungen und Bericht vorkommen | Sonst roher Schlüssel im Bericht (Befund aus AN5) | 3.7, Schritt 6: über `sync-check-texts.cjs` gespiegelt; Test prüft es |
| 12 | Viele Scanner legen selbst eine Textschicht ins PDF („durchsuchbares PDF“) | Solche Scans gelten als PDF mit Text, ohne Marke „aus Scan“ und ohne Zahlenprüfung; ihre Lesefehler bemerkt nur die Ähnlichkeitsschwelle | 7.3 als Grenze benannt; Erkennung der Herkunft einer Textschicht ist unsicher und bleibt draußen |
| 13 | `verify_quote` vergleicht in der Vergleichsform ohne Leerraum; ein Ausschnitt daraus verschmilzt benachbarte Zahlen | Zahlenprüfung fände „103“ statt „10“ und „3“ – falsche Bestätigung oder falsche Ablehnung | Entfallen: keine neue Prüfung (7.5 Nr. 1). Die vorhandene vergleicht Zitat und Seite in derselben Form; beide verschmelzen gleich |
| 14 | Bilder tragen oft 72 oder 96 dpi als Vorgabe, nicht als Messung | Papiermaß und damit der Maßstab still falsch | 3.5 Punkt 3: dpi nur ab 150; sonst Kalibrierung über zwei Punkte |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| KI-Abschrift über OpenRouter | 0,002–0,03 $ je Seite; Abschrift und Auswertung aus derselben Quelle schwächen die Zitatprüfung; entschieden am 29.09.2026 | Tabellen oder schlechte Scans an echten Unterlagen messbar scheitern – dann als Zuschaltung je Dokument |
| OpenRouter mit `mistral-ocr` (2 $ je 1 000 Seiten) | Text nur als Nebenprodukt einer Chat-Anfrage, Kopplung an eine Eigenheit von OpenRouter, Daten an einen weiteren Dienst | eine Erkennung von Tabellen gebraucht wird und lokal nicht reicht |
| `ocrmypdf` (erzeugt ein PDF mit Textschicht) | zusätzliche Abhängigkeiten (Ghostscript, AGPL), schreibt die Datei neu – Prüfsumme und Zitat-PDFs änderten sich | ein durchsuchbares PDF für den Architekten selbst gewünscht ist |
| PyMuPDF zum Rendern | AGPL (Spez. 5.2.3, `rules/pdf.py`) | nie im öffentlichen Dienst |
| `pdftoppm` (Poppler) | eigenes Programm mit GPL, keine Python-Schnittstelle; `pypdfium2` ist kleiner und schneller | – |
| Erkennung ohne Bestätigung, sofort beim Hochladen | widerspricht E-A7; ein Fehlupload belegte den Worker minutenlang | die Erkennung auf einem eigenen Worker läuft |
| Eigener Worker für die Erkennung | mehr Infrastruktur (zweiter Container je Stack) für wenige Dokumente im Monat | Scans regelmäßig vorkommen und Wartezeiten stören |
| Umriss automatisch aus dem Bild (Linien erkennen) | unsicher bei Schraffuren, Beschriftungen und Verzerrung; muss ohnehin geprüft werden | viele Scans derselben Art (z. B. nur Katasterauszüge) vorkommen |
| Scan im Browser mit pdf.js rendern | 1 MB zusätzlich im Frontend, Maßstabssuche bräuchte trotzdem den Server | – |

### 7.3 Bewusste Grenzen

Keine Handschrift, keine Erkennung von Tabellenstruktur (Tabellen kommen zeilenweise als Text), nur Französisch, keine Unterscheidung einer Textschicht des Scanners von einer echten (7.1 Nr. 12), keine Texterkennung im GPU-Weg des Konfigurators (E-AN7-6), keine Speicherung des Parzellenscans, kein durchsuchbares PDF als Ausgabe. Zonenkürzel aus erkannten Überschriften können verlesen sein („Uig“ statt „UIg“, 7.5 Nr. 15); der Architekt wählt dann das verlesene Kürzel. Bereits gelesene Dokumente behalten ihre Kapitel, auch wenn die Kapitelsuche heute mehr fände (7.5 Nr. 3).

### 7.4 Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN7-1 | Lesen | **Entschieden (Nutzer, 29.09.2026):** lokal mit Tesseract |
| E-AN7-2 | Parzelle | **Entschieden (Nutzer, 29.09.2026):** nachzeichnen |
| E-AN7-3 | Bestätigung auch bei einzelnen leeren Seiten? | Ja, dieselbe Schaltfläche; es sind oft Pläne, deren Erkennung nichts bringt |
| E-AN7-4 | Zahlen auf Scan-Seiten gegen den erkannten Text prüfen | **Erledigt ohne neue Prüfung:** `_numbers_match` prüft sie für alle Seiten schon (7.5 Nr. 1) |
| E-AN7-5 | Schwelle „unsicher“ | mittlere Wortsicherheit unter 70; an echten Scans nachstellen |
| E-AN7-6 | Texterkennung im GPU-Weg des Konfigurators | Nicht in AN7: G2 läuft dort ohne Büro, eine Bestätigung fehlt; die Funktion aus `platform/scan.py` ist wiederverwendbar, sobald ein gescanntes PLU dort auftaucht |
| E-AN7-7 | Scan-Limit im Abo (E-A7, AN6) | Wird zur Grenze der erkannten Seiten je Organisation und Monat (Rechenzeit statt Geld), festzulegen in AN6 |

### 7.5 Beim Bau gefunden

| Nr. | Befund | Folge |
|---|---|---|
| 1 | `verify_quote` prüft schon jede Zahl des Zitats an der Fundstelle (`_numbers_match`); der Befund in 2 hatte das übersehen | Keine neue Zahlenprüfung, `QuoteCheck` unverändert. Neu ist nur der Grund `scan_unconfirmed` (3.3). 7.1 Nr. 13 entfällt |
| 2 | Die Texterkennung verliert im Inhaltsverzeichnis Füllpunkte und Seitenzahlen; aus „CHAPITRE 1 : LA ZONE Ua …… 13“ wird eine Überschrift, die Verzeichnisseite galt als Kapitelanfang | `TOC_MIN_HEADINGS`: eine Seite mit drei oder mehr Zonenüberschriften ist ein Verzeichnis |
| 3 | **Abnahme 2, erster Lauf:** Das Verzeichnis von Beyenes wird im Scan schlecht gelesen (Seite 3: Sicherheit 54, „ZONE cameras“ statt „ZONE UC“, „Nan“ statt „N“); der Weg über das Verzeichnis fand 3 von 9 Kapiteln, ohne allgemeine Seiten. Zugleich zeigte der Vergleich: Das Verzeichnis selbst lässt **Zone UE (S. 33–36)** aus – auch mit Textschicht lagen ihre Seiten still im Kapitel UR und Zone UE war nicht wählbar | `detect_structure`: Finden die Überschriften mehr Kapitel, gelten sie; Titel und allgemeine Seiten bleiben aus dem Verzeichnis, soweit es sie hat. Vorher an allen sechs Dokumenten beider lokalen Datenbanken gemessen: Nur Beyenes ändert sich (Text: UE dazu, UR 21–32; Scan: 3 → 10 Kapitel), der PLUi Erdre et Gesvres (333 Seiten) und die übrigen bleiben gleich. Bereits gelesene Dokumente behalten ihre Kapitel (7.3; HANDOFF) |
| 4 | **Abnahme 3, erster Lauf:** 13 von 18 belegten Zitaten auch im Scan belegt (72 %). Ursache: NFKC macht aus „m²“ „m2“; die Hochzahl galt als Zahl 2, Tesseract liest „m?“ oder „m°“ | `_UNIT_EXPONENT` in `_numbers_match`: Hochzahlen von m² und m³ zählen nicht. Danach 18 von 18. Auf einer Textschicht haben Zitat und Seite dieselbe Form, deshalb kein neues `ENGINE_VERSION` |
| 5 | Ein nicht bestätigtes Zitat, das auf keiner Seite eine Ähnlichkeit erreicht (fehlende Zahl → 0), hat keine Seite; `scan_reasons` griff dann nie | Ohne Seite entscheidet das Kapitel: liegt es ganz im Scan, gilt `scan_unconfirmed` |
| 6 | `dict(db.execute(select(a, b)))` baut aus einem `Result` kein Wörterbuch der Zeilen (es hat `keys()`) | `dict(….tuples().all())` in `ocr.finish` und im Test; README Stolperstellen |
| 7 | Vorschau des Parzellenscans zuerst ohne Seitengrenze und mit der Auflösung der Erkennung (5 000 Pixel) | an `pdfplan.MAX_PAGES` (3) angeglichen, gerendert mit 4 000 Pixeln (`SCAN_RENDER_PX`) |
| 8 | Fehlt Tesseract oder scheitert die Erkennung, schlug die ganze Vorschau fehl | Vorschau ohne Maßstab, Log `site_scan_ocr_failed`; der Architekt kalibriert |
| 9 | Der Job meldete nach drei Versuchen `interrupted:ScanProblem` statt des Grunds | Fehlercode der Erkennung bleibt (`ocr_unavailable`); die Oberfläche zeigt ihn |
| 10 | Zusatzdokumente und Vergleich zeigen Fundstellen über `CitationOut`, nicht über `RuleOut` | `from_scan` auch an `CitationOut` und `Citation` (G3), nicht in der Prüfsumme des Baurahmens; die Prüfsumme des Berichts ändert sich einmal (README: neues Feld in den Ausgaben) |
| 11 | `ScanHinweis` brauchte die Fehlertexte aus `Bebauungsplan.tsx`, das `ScanHinweis` einbindet | Fehlertexte nach `products/analyse/fehler.ts` |
| 12 | i18next wählt im Französischen für 0 die Einzahl; der Kalibrierhinweis „noch 0 Punkte“ passte nicht | eigene Schlüssel `calibrateFirst`, `calibrateSecond`, `calibrateLength` statt einer Zählform |
| 13 | Abnahme 5: Beim Nachzeichnen folgt die Schlusskante aus den geklickten Richtungen; nach Korrektur der drei anderen Längen auf 30/20/30 m ergab sich 610,9 m² statt 600 m² (+1,8 %) | innerhalb der 2 %; der Hinweis der Kantenbearbeitung fordert ohnehin die Maße aus dem Plan |
| 14 | Im Browser der Abnahme blockt die CSP (`connect-src 'self'`) Testdateien von einem anderen Port | Bild im Browser erzeugt und per `DataTransfer` gesetzt; README nennt den Weg über die Web-Ebene schon |
| 15 | Tesseract liest „UIg“ in Kopfzeile und Überschrift verschieden („Uig“, „Ulg“) | Kapitelcode aus dem Scan „Uig“; als Grenze in 7.3, keine Korrektur (keine sichere Regel für I/l/i) |
