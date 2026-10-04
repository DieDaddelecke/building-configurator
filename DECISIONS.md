# Entscheidungen

> Stand 03.10.2026. Maßgebliche Liste der Entscheidungen mit ihren ursprünglichen IDs, auf die der Code verweist. Offene Fragen stehen in [ROADMAP.md](ROADMAP.md) 3, die Fachregeln in [DOMAIN.md](DOMAIN.md).

**So wird diese Datei gepflegt:** Neue Entscheidungen und Festlegungen kommen hierher, als ADR in Abschnitt 1 (Architektur, Betrieb, Arbeitsweise) oder als Zeile in Abschnitt 4 (Fachfestlegung mit neuer ID `F01` ff.). Eine überholte Entscheidung bleibt stehen und bekommt „aufgehoben durch …“. Die vollständigen Texte der älteren IDs stehen unverändert im Archiv (Abschnitt 5).

## 1. Architekturentscheidungen (ADR)

### ADR-01 – Das Sprachmodell liest, Python rechnet, der Mensch prüft (29.09.2026)

- **Kontext:** Regeln stehen nur als Text im règlement écrit. Ein Sprachmodell liest sie gut, rechnet aber nicht verlässlich und darf nichts Rechtliches entscheiden (L7, D11).
- **Entscheidung:** Das Modell (OpenRouter, D19) liefert nur Kandidaten: Regelart, Parameter, Zitat mit Seite. Deterministische Schranken in `rules/domain/assess.py` prüfen Zitat, Zahlen, Sektor und Parameter; eine Gegenprüfung (RW19) und eine Nachsuche (E-VA-3) folgen. Gerechnet wird ausschließlich in `envelope/domain`, `analysis/domain` und `configuration/domain`. Büro und Architekten korrigieren mit Begründung und Fundstelle; das Büro prüft nach Kontakt.
- **Folgen:** Die Schnittstelle der Extraktion liegt in `rules/domain/extraction.py`; ein Test verhindert, dass reine Lesepfade das OpenAI-SDK laden (`test_module_boundaries.py`). Keine Kundendaten an das Modell (L8).

### ADR-02 – Eine Anwendung für Konfigurator und Analyse (29.09.2026, Nutzer)

- **Kontext:** Beide Produkte waren im Code schon eine Anwendung, liefen aber als zwei Instanzen mit eigener Datenbank, eigenem Objektspeicher und drittem Stack für gemeinsame Daten (19 Container auf einem Rechner).
- **Entscheidung:** Ein API-Prozess mit allen Routern, eine Datenbank, ein Frontend-Build, ein Worker-Image. Die Bereiche trennt das Frontend (`/`, `/buero`, `/analyse`).
- **Hebt auf:** D16 (zwei Profile und Auslieferungen), E-A4 (Datenbank je Produkt), ANNAHMEN PS01–PS09 und PLAN_ANALYSE 3 (Produktschnitt), den gemeinsamen Stack vom 28.09.2026 (VA09 in dieser Form).
- **Folgen:** Architekten sehen unter `/analyse` alle Projekte ihrer Organisation, auch im Konfigurator angelegte. Analyse-Routen verlangen `require_owned_project`; das Kunden-Cookie reicht dort nicht. Der Kern darf weiterhin keine Konfigurator-Module importieren (Test).

### ADR-03 – Ein Hostname, eine Authentik-Anwendung (29.09.2026, Nutzer)

- **Entscheidung:** Konfigurator unter `/`, Büro unter `/buero`, Analyse unter `/analyse`, Verwaltung unter `/analyse/verwaltung` (`/verwaltung` leitet weiter). Nach der Anmeldung geht es nach `/buero`; zielt `next` in den Analyse-Bereich, dorthin.
- **Folgen:** `emprise-analyse.aslani.work` entfällt; der Reverse Proxy leitet ihn bei Bedarf auf `/analyse` weiter (ROADMAP 4.5).

### ADR-04 – Eine Datenbank; gemeinsame Daten in `emprise` (29.09.2026)

- **Entscheidung:** Modellwahl (`app_setting`), Referenzlisten (`reference_list`, `reference_entry`) und ihr Audit (`audit_log`) liegen in der Hauptdatenbank; ein Alembic-Strang (Migration 0021).
- **Hebt auf:** VA09 (Datenbank `emprise_shared`, eigene Alembic-Umgebung, `shared_audit`).
- **Folgen:** Die alten Datenbanken `emprise_analyse` und `emprise_shared` bleiben lokal liegen, bis ihre Löschung freigegeben ist (ROADMAP 4.7).

### ADR-05 – Warteschlange in PostgreSQL mit zwei Warteschlangen (29.09.2026)

- **Kontext:** Es gab nie Redis oder Celery; die Jobtabelle mit `FOR UPDATE SKIP LOCKED` genügt. Aber ein Worker für alles ließ Mails hinter Regelauswertungen (bis 60 min) warten, der Bestätigungscode gilt 10 min.
- **Entscheidung:** Jobtabelle `job` bleibt. Lange Jobs (`plu_import`, `rules_extract`, `rules_document_read`, `rules_document_ocr`, `cadastre_import`) laufen in `long`, alle anderen in `default` (Migration 0022). Auf Unraid zwei Dienste aus einem Image (`worker`, `worker-long`), lokal ein Worker für beide. Health je Warteschlange.
- **Abweichung** vom Zielbild „ein Worker“, bewusst. **Hebt auf:** A20 (alle Jobs in `default`).

### ADR-06 – Dateiverzeichnis statt Objektspeicher (29.09.2026)

- **Kontext:** SeaweedFS lief als Einzelknoten; genutzt wurden vier Funktionen, signierte URLs nie; Löschen im versionierten Bucket war fraglich.
- **Entscheidung:** `platform/storage.py` schreibt nach `EMPRISE_FILES_DIR` (`/data/files`, Eigentümer 10001), atomar, Traversal abgewiesen, Schlüssel unverändert. `boto3` entfällt.
- **Hebt auf:** A16 (SeaweedFS lokal und in CI), die S3-Teile von A21. **Auslöser für S3:** ARCHITECTURE 7.

### ADR-07 – AN6-Zusätze zurückgebaut (29.09.2026, Nutzer)

- **Entscheidung:** Entfernt: API-Schlüssel (Bearer-Weg), Budget und Scan-Kontingent je Organisation (`usage_record`), Erscheinungsbild in Bericht und DXF, CLI `org-set-budget` (Migration 0023, `downgrade` legt die Tabellen leer an). Bleiben: Organisationen mit Mitgliedern, Rollen `admin`/`member`, die Sperre für fremde Büros und das globale Monatsbudget.
- **Hebt auf:** E-AN6-4, E-AN6-5, E-AN6-6, E-AN7-7 und die entsprechenden Teile von MA01–MA09; E-A6 ist damit wieder offen (ROADMAP 3). **Rückweg:** Stand in Git `24d3627`, Auslöser ARCHITECTURE 7.

### ADR-08 – Dokumentation in sechs Dateien plus Archiv (29.09.2026, Nutzer)

- **Entscheidung:** README, ARCHITECTURE, DOMAIN, DECISIONS, ROADMAP, AI_CONTEXT; dazu der Betrieb in `deploy/unraid/README.md`. Spezifikation, Umsetzungsplan, Modulpläne, ANNAHMEN, Hand-off, Änderungsprotokoll, Mockup und Refactoring-Analyse liegen unverändert in `docs/archiv/`.
- **Folgen:** `AENDERUNGEN.md` endet; das Änderungsprotokoll ist das Git-Log. HANDOFF geht in ROADMAP auf; `/handoff` pflegt ROADMAP und DECISIONS. Die Spezifikation ist nicht mehr Rang 2; ihre offenen Korrekturen S1–S17 (Anhang E.4) werden nicht mehr eingearbeitet, fachlich offene stehen in ROADMAP 5.

### ADR-09 – Ordner bleiben (29.09.2026)

- **Entscheidung:** Kein Umbau nach `domains/`, `calculations/`, `infrastructure/` oder `features/`. `platform` ≙ infrastructure, `<modul>/domain` ≙ calculations; im Frontend Fachordner, nur `src/products/analyse` wurde `src/analyse`.
- **Grund:** gleiche Struktur unter anderen Namen, rund 300 Importänderungen ohne Gewinn. Große Dienstmodule wurden stattdessen nach Anwendungsfall geteilt (`rules/office.py`, `overrides.py`, `scheduling.py`; `site/search.py`, `manual.py`, `position.py`, `corrections.py`, `store.py`).

### ADR-10 – Feature-Flags bleiben bis zum öffentlichen Start (29.09.2026)

- **Entscheidung:** Die Modul-Flags `site_selection`, `rules_simulation`, `envelope_simulation`, `inquiry`, `configurator`, `submission` sind der Freischaltweg (intern → Beta → alle, D2) und gelten für die ganze Anwendung. `EMPRISE_EXTERNAL_ORGANISATIONS` ist eine Sicherheitssperre, kein Flag. Wann die Flag-Prüfungen entfallen: ROADMAP 4.5.

### ADR-11 – Cloudflare-Proxy vor Emprise und Authentik (03.10.2026, Nutzer)

- **Kontext:** `aslani.work` liegt bei Cloudflare; die übrigen Dienste des Nutzers laufen über den Cloudflare-Proxy (orange Wolke) zum Nginx Proxy Manager auf Unraid.
- **Entscheidung:** `building-configurator.aslani.work` und `auth.aslani.work` bleiben „proxied“ (CNAME auf `aslani.work`); TLS zusätzlich am Nginx Proxy Manager (Let's Encrypt).
- **Hebt auf:** die Festlegung vom 25.09.2026 „nur DNS, graue Wolke“ ([Betrieb](deploy/unraid/README.md) Abschnitt 2).
- **Folgen:** Cloudflare sieht den Verkehr im Klartext, auch Anmeldedaten und Kundendaten – bewusste Ausnahme von L8 und Plan 6.9 (kein US-Anbieter im Datenweg) für den Datenweg; vor dem öffentlichen Start mit D3 neu bewerten. SSL-Modus „Full (strict)“. Die echte Client-IP kommt als `CF-Connecting-IP`; ohne Übernahme teilen sich Nutzer Rate-Limits und das Audit sieht Cloudflare-Adressen (vor dem öffentlichen Start einrichten). Anfragen sind bei Cloudflare Free auf 100 MB begrenzt (Reglement-Upload bis 100 MB). Bot- und Angriffsschutz von Cloudflare darf den Aufruf der API an Authentik (Token-Abruf) nicht blockieren.

## 2. Entscheidungen des Umsetzungsplans (D1–D19)

| Nr. | Frage | Stand |
|---|---|---|
| D1 | Einzugsgebiet | Entschieden 14.09.2026: bis zur Beta nur Treillières (44209); weitere Gemeinden vor der Beta neu entscheiden (G03). Erweitert 03.10.2026 (Nutzer): auf Unraid zusätzlich das Kataster der Île-de-France (Paris als Arrondissements 75101–75120, dazu alle Gemeinden der Départements 77, 78, 91–95), einmalig von Hand importiert, ohne Planstand und Regeln; nicht in `CADASTRE_COMMUNES`, damit der Worker dafür keinen Planstand lädt und nichts auswertet |
| D2 | R1 öffentlich oder intern | Erst intern, dann Beta, dann öffentlich. Entschieden 14.09.2026: G1 intern für `architect`; Beta und öffentlich offen |
| D3 | Hosting | Entschieden 14.09.2026: bis zur Beta selbst betrieben auf Unraid (A21); vor dem öffentlichen Start neu entscheiden |
| D4 | Anmeldung für Büro und Team | Entschieden 14.09.2026: eigener Dienst, kein Microsoft oder Google; Authentik auf Unraid (A23) |
| D5 | Wer betreibt die Plattform | **offen** – Vorschlag: Emprise mit benannter Betriebsverantwortung und Vertretung |
| D6 | Datenschutzrolle Emprise ↔ Büro | **offen** – vor R1 rechtlich festlegen |
| D7 | Sprache der Oberfläche | Französisch führend, Deutsch zusätzlich (A19) |
| D8 | Honorar oder Bauleistung | Bestätigt 19.09.2026: bestimmt nur den Wortlaut der Spanne („Schätzung, unverbindlich“, HK10) |
| D9 | Vier-Augen-Prinzip bei Regelfreigabe | entfällt mit D11 |
| D10 | Mehrwertsteuer in der Anzeige | Bestätigt 19.09.2026: netto gespeichert, brutto mit dem Satz des Katalogs angezeigt (HK10) |
| D11 | Herkunft und Verbindlichkeit der Regeln | Entschieden 14.09.2026: G2 vollautomatisch ohne Büro-Eingaben; Ergebnis ist eine unverbindliche Simulation; das Büro prüft nach Kontakt |
| D12 | Wie stark begrenzen simulierte Regeln den Konfigurator | Bestätigt 19.09.2026: nur wirksame Regeln sperren Typen und Lagen, Unbekanntes bleibt Hinweis; Anfrage bleibt immer möglich (HP01) |
| D13 | Grundstück ohne Baurahmen im Konfigurator | Bestätigt 19.09.2026: freier Modus im Umriss ohne Abstandsprüfung, auch ohne verfügbare Regeln (HP02) |
| D14 | Anfrage direkt nach G3 neben dem Konfigurator | Entschieden 17.09.2026: dauerhaft als Notausgang; V erweitert dieselbe Anfrage |
| D15 | Zielgruppe „Emprise Analyse“ | Entschieden 20.09.2026: zuerst nur das eigene Büro; fremde Büros als Ausbau nach E-A5 |
| D16 | Codeschnitt des zweiten Produkts | Entschieden 20.09.2026: ein Repository, zwei Profile und Auslieferungen. **Aufgehoben durch ADR-02** (eine Anwendung) |
| D17 | Datenbeschaffung der Analyse | Entschieden 20.09.2026: der Nutzer lädt Parzelle (DXF, GeoJSON, Zeichnung, ab 21.09. auch PDF) und PLU selbst hoch; Kataster und GPU bleiben Komfortweg |
| D18 | Beauftragung „Emprise Analyse“ | Entschieden 20.09.2026: Modul für Modul; AN0–AN7 umgesetzt bis 29.09.2026, AN6 danach auf Organisationen und Mitglieder zurückgebaut (ADR-07) |
| D19 | Schnittstelle zum Sprachmodell (im Code „E-D19“) | Entschieden 26.09.2026: OpenRouter statt Claude API unmittelbar, Modell frei wählbar (RW28); gilt nur für öffentliche Planunterlagen (L8). Nachgetragen, stand vorher in keiner Tabelle |

## 3. Offene Entscheidungen der Spezifikation (E1–E12)

| Nr. | Frage | Stand |
|---|---|---|
| E1 | Hosting-Anbieter und Region | bis zur Beta durch D3 beantwortet (Unraid); danach offen |
| E2 | Mail-Dienst | **offen** – Empfehlung Scaleway TEM, sonst Brevo; am 25.09.2026 „später“ |
| E3 | Kundenanmeldung | umgesetzt ohne Konto: anonymes Projekt-Cookie, Zugangslink per Mail (V, E-V5) |
| E4 | Preise brutto oder netto | durch D10 beantwortet |
| E5 | Flächenstandard im Dossier | Vorschlag: französisch (SHAB, SDP, Emprise); offen, ob DIN 277 dazukommt |
| E6 | Wer gibt Regelwerke frei | durch D11 überholt: keine Freigabe; Bürofassung durch `rules_admin` |
| E7 | Sprachmodell für PLU-Auswertung zulässig | ja, nur öffentliche Dokumente (D11, D19) |
| E8 | 3D-Viewer | nicht beauftragt |
| E9 | CRM-Anbindung des Büros | offen, später per Webhook |
| E10 | Aufbewahrungsfrist für Übergaben | Vorschlag 3 Jahre; offen mit D6 |
| E11 | Mehrere Büros (Mandanten) | Organisationen umgesetzt; fremde Büros gesperrt bis E-A5 |
| E12 | Wer liefert RE2020-Bewertungen | Vorschlag: Thermik-Büro im Auftrag des Katalogbetreibers; offen |

## 4. Entscheidungen der Module

Kurzfassung; Begründung und Alternativen im jeweiligen Modulplan im Archiv. „Aufgehoben“ heißt: gilt nicht mehr.

### 4.1 Emprise Analyse allgemein (E-A)

| Nr. | Entscheidung |
|---|---|
| E-A1 | **offen:** Arbeitstitel „Emprise Analyse“; endgültiger Name vor Nutzung außerhalb des Büros |
| E-A2 | Parzelle als DXF, GeoJSON, Zeichnung und vektorielles PDF (21.09.2026); kein DWG; Scans seit AN7 zum Nachzeichnen |
| E-A3 | Eine Zone je hochgeladenem Grundstück; Zonengrenze einzeichnen erst nach Auslöser (E-AN5-8) |
| E-A4 | Eigene Datenbank je Produkt. **Aufgehoben durch ADR-02** |
| E-A5 | **offen:** Rechtlicher Rahmen; bis dahin Hinweis „keine Rechtsauskunft, maßgeblich ist das Certificat d'urbanisme“; vor fremden Büros juristische Prüfung (Haftung, AGB, Auftragsverarbeitung, Urheberrecht) |
| E-A6 | **wieder offen (ADR-07):** Deckel je Organisation und Monat, bevor Dritte hochladen dürfen |
| E-A7 | Gescannte PDFs lesen: ja (28.09.2026), umgesetzt als AN7 mit lokaler Texterkennung |

### 4.2 AN1 – Parzelle (E-AN1)

| Nr. | Entscheidung |
|---|---|
| E-AN1-1 | Hochgeladene Datei nicht aufbewahren, nur Herkunft (Name, SHA-256, Ebene, Index) |
| E-AN1-2 | Kein DWG |
| E-AN1-3 | Koordinatensystem an der Größenordnung erkennen, anzeigen und festhalten |
| E-AN1-4 | Architekten sehen alle Projekte ihres Büros; seit AN6 je Organisation |
| E-AN1-5 | Gelände und Risiken erst mit geprüfter Lage (AN5) |

### 4.3 AN2 – Bebauungsplan hochladen (E-AN2)

| Nr. | Entscheidung |
|---|---|
| E-AN2-1 | Dokument für alle Projekte gemeinsam, erkannt am SHA-256 |
| E-AN2-2 | Nur die gewählten Sektoren auswerten; ein neuer Sektor wertet das Kapitel neu aus |
| E-AN2-3 | PDF im Job lesen, nicht im Request |
| E-AN2-4 | Dokument nicht mit dem Projekt löschen; Aufräumen ungenutzter Dokumente später |
| E-AN2-5 | Zusatzdokumente nicht in AN2; seit AN3 verglichen, seit AN4 übernehmbar |
| E-AN2-6 | Hochgeladenes PLU auch für Kataster-Grundstücke, und es geht dem GPU-Stand vor |
| E-AN2-7 | Regeln und Baurahmen in der Analyse über Büro-Endpunkte (Rolle statt Flag) |

### 4.4 AN3 – Analyse, Gabarit und Schnitt (E-AN3, E-AN3G)

| Nr. | Entscheidung |
|---|---|
| E-AN3-1 | Annahmen der Analyse je Projekt gespeichert |
| E-AN3-2 | Zusatzdokumente nicht einrechnen, nur vergleichen und melden |
| E-AN3-3 | `max_area` auch im PLU-Prompt |
| E-AN3-4 | Lot als Sektor eines Kapitels |
| E-AN3-5 | Nur mögliches Dachgeschoss unten nicht mitzählen |
| E-AN3-6 | Höchstens drei Zusatzdokumente je Projekt |
| E-AN3-7 | Gabarit und Schnitt in RA2; umgesetzt 28.09.2026 |
| E-AN3G-1 | Gabarit in beiden Auslegungen |
| E-AN3G-2 | Stufenhöhe 3,00 m plus kennzeichnende Höhen |
| E-AN3G-3 | Zwei feste Schnitte A–A und B–B; freie Linie erst auf Rückmeldung |
| E-AN3G-4 | Gelände im Schnitt eben bis AN5; seit AN5 mit Profil |
| E-AN3G-5 | Höhenstufen als 3D-DXF mit AN5 |
| E-AN3G-6 | Nutzfläche aus dem Gabarit, beide Enden mit derselben Formel |
| E-AN3G-7 | Keine Dachneigung im Hüllkörper: über der Traufe senkrecht bis zum First |
| E-AN3G-8 | Rechnen im Backend, in derselben Antwort wie die Analyse |

### 4.5 AN4 – Korrigieren und begründen (E-AN4)

| Nr. | Entscheidung |
|---|---|
| E-AN4-1 | Formularbeschreibung vom Server aus den Pydantic-Modellen |
| E-AN4-2 | Eine Fundstelle je Korrektur |
| E-AN4-3 | Übernahme aus Zusatzdokument: das Strengere je Parameter als Vorschlag |
| E-AN4-4 | Vergleich nach Übernahme gegen die wirksamen PLU-Werte (`adopted`) |
| E-AN4-5 | Stände gerechnet, nicht gespeichert; zwei feste Gegenüberstellungen |
| E-AN4-6 | Regeln und Korrekturen als eigener, offener Abschnitt nach den Zusatzdokumenten |
| E-AN4-7 | Herkunft bleibt `project`, kein Wert `architect` |
| E-AN4-8 | Keine Zonenkorrektur in der Analyse |
| E-AN4-9 | Büro-Formulare des Konfigurators nutzen dieselbe Komponente |

### 4.6 AN5 – Ausgabe und Projektakte (E-AN5)

| Nr. | Entscheidung |
|---|---|
| E-AN5-1 | Lage auf der Karte mit Katasterebene verschieben und drehen; Adresse nur Startpunkt |
| E-AN5-2 | DXF lokal relativ und in Lambert-93 mit m NGF |
| E-AN5-3 | 3D-Gabarit als Höhenlinien und geschlossene Körper je Stufe |
| E-AN5-4 | Gabarit folgt nicht dem Gelände; Stufen über der mittleren Geländehöhe, Hinweis ab 5 % Neigung |
| E-AN5-5 | Begründungen der Korrekturen stehen im Bericht |
| E-AN5-6 | Kein GeoJSON ohne Lage |
| E-AN5-7 | „Archivieren“ blendet nur aus |
| E-AN5-8 | Zonengrenze einzeichnen nicht in AN5, nach Auslöser |
| E-AN5-9 | Steckbrief in der Analyse ausgeblendet, der Bericht ersetzt ihn |
| E-AN5-10 | Bericht im Worker mit Ablage je Prüfsumme und Sprache; DXF und GeoJSON sofort im Request |

### 4.7 AN6 – Mandanten (E-AN6)

| Nr. | Entscheidung |
|---|---|
| E-AN6-1 | Eine Organisation je Konto |
| E-AN6-2 | Dokumente über Organisationen nach Prüfsumme teilen; Sichtbarkeit über eigene Projekte |
| E-AN6-3 | Rollen in der Organisation: `admin`, `member` |
| E-AN6-4 | Budget und Scan-Kontingent je Organisation. **Aufgehoben durch ADR-07** |
| E-AN6-5 | Rechte der API-Schlüssel. **Aufgehoben durch ADR-07** |
| E-AN6-6 | Logo-Formate. **Aufgehoben durch ADR-07** |
| E-AN6-7 | Kein Durchgriff des Betreibers auf fremde Projekte über die Oberfläche |
| E-AN6-8 | Fremde Büros technisch gesperrt (`EMPRISE_EXTERNAL_ORGANISATIONS`) bis E-A5 |
| E-AN6-9 | Mitglieder ohne Selbstregistrierung: `admin` trägt ein, der Betreiber legt das Konto bei Authentik an |
| E-AN6-10 | Monatsgrenze: Kalendermonat UTC |

### 4.8 AN7 – Gescannte PDFs (E-AN7)

| Nr. | Entscheidung |
|---|---|
| E-AN7-1 | Lesen lokal mit Tesseract (Nutzer, 29.09.2026) |
| E-AN7-2 | Gescannte Parzelle nachzeichnen (Nutzer, 29.09.2026) |
| E-AN7-3 | Bestätigung auch bei einzelnen leeren Seiten |
| E-AN7-4 | Zahlen auf Scan-Seiten prüft die bestehende Zahlenprüfung |
| E-AN7-5 | Schwelle „unsicher“: mittlere Wortsicherheit unter 70; an echten Scans nachstellen |
| E-AN7-6 | Keine Texterkennung im GPU-Weg des Konfigurators (ROADMAP 5) |
| E-AN7-7 | Scan-Limit je Organisation. **Aufgehoben durch ADR-07** |

### 4.9 G2-Vollständigkeit, G3 und V (E-VA, E-G3, E-V)

| Nr. | Entscheidung |
|---|---|
| E-VA-1 | Nachsuche für Zusatzdokumente später; zuerst am PLU messen |
| E-VA-2 | Alternativbezeichnungen zunächst im Code, Pflege in der Verwaltung später |
| E-VA-3 | Höchstens eine Nachsuche je Auswertung |
| E-VA-4 | Staffel der Grundflächenzahl: eigener Plan; bis dahin Hinweis und `not_expressible` |
| E-VA-5 | **offen, später mit dem Nutzer:** Auslegung mehrdeutiger und bedingter Vorschriften; bis dahin bleibt Mehrdeutiges sichtbar offen |
| E-G3-1 | Teilfläche ohne ausgewertete Regeln: nicht bebaubar, schraffiert (BR04) |
| E-G3-2 | Emplacement réservé und Espace boisé classé als Bauverbot, Risiko- und Schutzflächen nur in der engsten Auslegung (BR05) |
| E-G3-3 | Parameter `band` vor dem Eintragen des Schlüssels umgesetzt (BR13) |
| E-G3-4 | Steckbrief-PDF in G3 (BR10) |
| E-V1 | Tabelle `submission` je Fassung, Vorgang bleibt `inquiry` |
| E-V2 | Zustände der Anfrage um `rueckfrage` und `zurueckgezogen` erweitert |
| E-V3 | Konfiguration nach der Übergabe nicht gesperrt; Änderungen werden neue Fassung |
| E-V4 | Neuprüfung über den Inhalt in sechs benannten Teilen |
| E-V5 | Zugangslink ersetzt das Cookie |
| E-V6 | Dossier in beiden Sprachen |
| E-V7 | Linie nur Pflicht, wenn der Katalog Linien anbietet |
| E-V8 | Dossier-Fehler: Log-Alarm und Anzeige im Büro, keine Mail |

### 4.10 Übergreifende Festlegungen (Auswahl aus ANNAHMEN)

Festlegungen, die über ein Modul hinaus wirken. Alle übrigen IDs: Abschnitt 5.

| ID | Festlegung |
|---|---|
| A10 | `audit_log` und `legal_text` per Trigger unveränderlich, auch gegen `TRUNCATE` |
| A11 | `retention_cleanup` löscht Entwürfe 90 Tage nach der letzten Aktivität |
| A21 | Hosting bis zur Beta auf Unraid mit Compose, nächtlichem `pg_dump` und `deploy.sh`; kein OpenTofu, kein PITR (Objektspeicher aufgehoben durch ADR-06) |
| A23 | Authentik als eigener Stack, per Blueprint; zweiter Faktor Pflicht |
| G21 | Keine Abnahme-Testmenge; Kanten automatisch, Prüfung beim Eingang einer Anfrage |
| G27 | Weg E: Umriss aus Kanten (Länge, Azimut); die letzte Kante schließt |
| RW15 | Regelformular aus dem Schema statt JSON (seit AN4, KR01) |
| RW19 | Gegenprüfung statt zweitem gleichem Lauf |
| RW26 | `input_hash` über Prompt und Schemata; Aufrufe je Teil gespeichert und wiederverwendet; eine Änderung an Prompt oder Schema erzwingt eine neue Auswertung |
| RW28 | OpenRouter mit erzwungenem Funktionsaufruf (D19) |
| PU01 | Hochgeladenes Reglement ist `land_use_plan` mit `origin = 'upload'`; dasselbe PDF ist dasselbe Dokument |
| PU11 | Eine Modellwahl für alle Auswertungen, geändert durch `ops`/`rules_admin` ohne Neustart |
| PU12 | Modelle ohne PDF-Eingabe bekommen die Textschicht |
| SC06 | PDF-Modus mit Text-Rückfall über 20 MB; der OCR-Stand zählt im Eingabe-Hash, wo Text an das Modell ging (seit 30.09.2026) |
| BR01 | Zwei Konturen `lenient` und `strict` statt `B(0)`/`B(H_max)` |
| HP01 | D12 umgesetzt: nur `effective` bindet, Lage außerhalb → `422 placement_violation`. Im Hausmodell aufgehoben durch E-HM-6 (gilt im heutigen Konfigurator bis zur Ablösung) |
| HP02 | D13 umgesetzt: freier Modus im Umriss |
| HK10 | Kosten netto gerechnet, brutto angezeigt, auf 1.000 € gerundet mit „ca.“ |
| KR01 | `GET /admin/rule-kinds` beschreibt die Formulare aus den Pydantic-Modellen |
| VA03 | Referenzlisten messen die Vollständigkeit je Vorschrift |

### 4.11 Hausmodell (E-HM)

Plan: [docs/PLAN_HAUSMODELL.md](docs/PLAN_HAUSMODELL.md) (Prompt v3.1, Phasen HM0–HM6); Begründungen und Abschnittsverweise dort. Mit der Beauftragung der Umsetzung (03.10.2026) gelten die Empfehlungen des Plans als entschieden; HM0, HM1 und HM3 sind umgesetzt, HM3 auf Anweisung vor HM2 (04.10.2026).

| Nr. | Entscheidung |
|---|---|
| E-HM-1 | **Nutzer (1a):** Rechenkern `packages/domain` in TypeScript im Browser und im Dienst `engine` (Node 24); FastAPI bleibt; IFC-Import in Python mit IfcOpenShell |
| E-HM-2 | **Nutzer (2a):** Kunde sieht Gesamtpreis auf 1.000 € und Aufpreise auf 100 € gerundet mit „ca.“, ohne Positionen; exakte Beträge nur in Snapshot und Dossier (L1) |
| E-HM-3 | **Nutzer (3a):** alle klassischen Dachformen und R+1 vor der Ablösung; der heutige Konfigurator läuft bis dahin parallel (Fahne `configurator`) |
| E-HM-4 | Grenze TS ↔ Python ist die Hausbeschreibung (`HouseFacts`); Lage, Fläche zulässiger Ursprünge und PLU-Prüfung bleiben in `configuration/domain` |
| E-HM-5 | Typen an der Grenze als Pydantic-Modelle (`backend/app/house/contract.py`), nach TypeScript generiert; die API prüft jede Antwort von `engine` |
| E-HM-6 | Ergebnisarten `info`/`warning`/`block` und `deviation` (verletzte wirksame PLU-Regel, Übergabe mit Bestätigung); Status abgeleitet; unzulässige Auswahl oder Lage wird gespeichert. Hebt HP01 und HK08 im Hausmodell auf; D12 und D14 bleiben |
| E-HM-7 | Template- und Katalogversion werden mit der Konfiguration festgehalten; Grundstück und Regeln gelten aktuell, Änderungen zeigt der Prüfstempel |
| E-HM-8 | Katalogversion: ein Dokument je Markt mit Preisen |
| E-HM-9 | Template-Entwurf ist ein Status der Templateversion |
| E-HM-10 | **Nutzer:** jede Dachform für jeden Haustyp wählbar, voreingestellt die Form aus dem IFC; Dachaufbau eigener Slot; Neigung innerhalb der Katalogspanne einstellbar, Firstrichtung drehbar, nicht erzeugbare Formen gesperrt mit Begründung |
| E-HM-11 | Template trägt die Höhe des Erdgeschosses über Gelände, Standard 0,20 m |
| E-HM-12 | Fassaden- und Projektionsumriss wie heute; welcher für eine Regel gilt, entscheidet die Python-Prüfung |
| E-HM-13 | Fassadenrollen, Eingang und Garagentor werden im Entwurf bestätigt; Vorschlag aus dem IFC (Außentür in Entrée bzw. Garage) |
| E-HM-14 | Ausstattungslinie als Voreinstellung mehrerer Slots ohne eigenen Aufpreis; Terrasse und Carport als Slots `site`, Lage und Prüfung in Python |
| E-HM-15 | Keine Kundenkonten |
| E-HM-16 | Feld `market`, nur FR, eine Region |
| E-HM-17 | `docs/IFC_IMPORTVERTRAG.md` als einzige Ausnahme zu ADR-08: Leser ist das Büro beim Modellieren |
| E-HM-18 | Bilder im Dossier als SVG aus dem Kern, kein Rendering auf dem Server |
| E-HM-19 | IfcOpenShell läuft in einem Kindprozess mit Speicher- und Zeitgrenze; Datei nur über die API, Audit. Anfangswerte nach Spike HM0: 1 GB Adressraum, 120 s (Probedatei: 81 MB, 1,1 s; unter 160 MB scheitert schon der Start) |
| E-HM-20 | Einheitspreise des Katalogs gehen an den Browser (Richtpreise sind ohnehin öffentlich) |
| E-HM-21 | Neue Fahne `house_model`, entfällt mit der Ablösung |
| E-HM-22 | Keine Übernahme alter Konfigurationen bei der Ablösung; vorher auf Unraid prüfen, ob echte Vorgänge bestehen |
| E-HM-23 | **Nutzer:** Zonen immer richtig finden, Nummerierung ignorieren: Quellen in fester Reihenfolge (zuerst `IfcSpaceType`), Normalisierung, Aliasse im Katalog, Raumumriss aus den Wänden, Zone liefert nur den Typ |
| E-HM-24 | Innenseite der Platzhalter-Außenwand = Innenkante der innersten Profilschicht; Wände und Dach im IFC sind Platzhalter, ihr Aufbau kommt aus dem Katalog |
| E-HM-25 | **Nutzer:** alle klassischen Dachformen (Flach, Pult, Sattel, Walm/Zelt, Krüppelwalm, Mansarde) über Kantenprofile und ein gewichtetes Skelett mit Profilwechseln |
| E-HM-26 | Clipper2-Port `clipper2-ts` (ganzzahlig, richtig, 17 kB gzip, ohne Abhängigkeiten). `clipper2-js` rechnet den Offset falsch; `clipper2-wasm` ist der Rückfall (asynchron, Speicher von Hand, CSP bräuchte `'wasm-unsafe-eval'`) |
| E-HM-27 | Jeder Ring geht erst nach `polygonDefect` an Clipper2 (ganzzahlig, höchstens 1 km, einfach, kein Rücklauf); `clipper2-ts` läuft bei Rückläufen sonst endlos. `engine` antwortet mit 422 |
| E-HM-28 | Dach-Skelett als eigene Umsetzung im Kern: keine gewichtete Bibliothek in JS/TS; die CGAL-Pakete als WebAssembly sind ungewichtet und stehen unter GPL |
| E-HM-29 | Vertrag ohne Route: `main.py` nimmt die Wurzelmodelle aus `app/house/contract.py` in `components.schemas` auf und nennt sie in `x-house-contract`; `pnpm run contract:types` erzeugt daraus `packages/domain/src/contract.gen.ts`. Kein Feld mit Standardwert (Ein- und Ausgabeschema gleich). Die CI prüft `openapi.json`, `contract.gen.ts` und `schema.d.ts` |
| E-HM-30 | Rollladenkasten über dem Fenster: Sturz in der Wand = `head_height` + Kasten, Wandabzug und Laibung mit Höhe + Kasten; Fensterfläche für die Energie ohne Kasten |
| E-HM-31 | Jedes Hüllensegment, jede Öffnung und das Dach erhält seinen Typ aus genau einem Slot (sonst `type_slot_missing`/`type_slot_ambiguous` in der Kompatibilitätsprüfung). Bis HM5 ein Wandprofil je Geschosshülle (`mixed_wall_profiles`) |
| E-HM-32 | Raumüberschreibung an Bauteilen zwischen Räumen: Es zählen nur Räume mit Überschreibung; die höchste `override_priority` gilt. Bei Gleichstand greift die Stufe nicht, die Notiz `room_override_tie` nennt die Werte |
| E-HM-33 | Notizen und Geometrieprüfungen tragen Codes; Text nur aus dem Katalog (`unavailable_reason`, Regeltexte), sonst übersetzt die Oberfläche den Code |
| E-HM-34 | Ausdrücke ohne ausführbaren Code mit festem Verhalten: fehlender Pfad null, Pfad über Listen eine Liste ohne null; Größenvergleiche nur zwischen Zahlen, sonst false; Rechnen nur mit Zahlen, Division durch 0 null; nur true ist wahr. Listen in Ausdrücken enthalten nur Werte (sonst wäre der Typ über Listen rekursiv) |
| E-HM-35 | Höhen über ±0,00 = Oberkante Bodenplatte EG. Template: `bearing_height` (Oberkante Außenwand = Unterkante Dachdecke = Decke des Geschosses), Dachdecke als Platte `roof`, Attika über Oberkante Dachdecke; Fassadenhöhe = Bodenplatte + `bearing_height` + Dachdecke + Attika. Demohaus 0,20 + 2,50 + 0,10 + 0,40 = 3,20 m; die lichte Höhe 2,70 m aus P 19.1 passt nicht dazu (PLAN_HAUSMODELL 11.1 Nr. 29) |
| E-HM-36 | `engine` prüft nur die Hülle der Anfrage (Dokumente vorhanden, `schema_version` 1); den Inhalt prüft die API mit Pydantic vor dem Aufruf und die Antwort danach. Fehler des Kerns antworten mit 422 `{code, detail}`; Anfragen bis 4 MB |
| E-HM-37 | Typ jeder Öffnung aus dem Katalog über die Maße (Fenster: Breite, Höhe, Sturz, Rollladenkasten; Türen: Breite, Höhe; je ±1 mm). Kein oder mehrere Treffer: offener Punkt, das Büro wählt den Wert im Entwurf. Standard je Slot: Angabe des Büros, sonst der häufigste erkannte Wert, sonst der erste des Slots. Abweichende Bauteile stehen im Template unter `element_defaults` (Element → Slot → Wert); Auflösung Element → Raum → global → Standard des Bauteils → Standard des Slots |
| E-HM-38 | Umfang des Imports in HM3: Erdgeschoss mit geraden Wänden und Flachdach (Auflagerhöhe, Dachdecke, Attika, Überstand). Mehrere Geschosse mit Wänden oder Zonen, geneigte Dachflächen und ein fehlendes Dach sind Fehler, bis HM5 sie liest |
| E-HM-39 | Entwurf = gelesenes Modell (`raw`) + Angaben des Büros (`decisions`). Template und Importbericht entstehen bei jeder Änderung neu mit der zuletzt veröffentlichten Katalogversion des Markts, ohne die Datei erneut zu lesen; eine geänderte geprüfte Version fällt auf `draft` zurück, ihr Prüfbefund verfällt |
| E-HM-40 | Ablauf `draft` → Prüfen (`engine /compatibility`; kompatibel → `reviewed`) → Freigeben (bestätigt den Befund, nur gegen die aktuelle Katalogversion, sonst `409 house_catalog_changed`) → `published` und aktuelle Version des Haustyps → `retired` (aktuell wird die neueste andere veröffentlichte); `rejected` verwirft einen Entwurf. Hochladen, Bearbeiten, Prüfen und Freigeben nur `catalog_admin`, `architect` und `ops` lesen mit (3.6) |
| E-HM-41 | Tabellen `house_template` (Slug, aktuelle Version), `house_template_version` (E-HM-9), `house_catalog`, `house_catalog_version`, `house_catalog_compatibility` (ein Befund je Paar aus Template- und Katalogversion). Trigger: veröffentlichte Versionen nur noch `published` → `retired`, kein Löschen; ein freigegebener Befund ist unveränderlich (L4). Datei unter `house/ifc/<sha256>.ifc` |
| E-HM-42 | Upload: Endung `.ifc` und STEP-Kopf, höchstens 100 MB (`EMPRISE_HOUSE_IFC_MAX_BYTES`), nur mit veröffentlichter Katalogversion (`409 house_catalog_missing`). Dieselbe Datei für einen offenen Entwurf ergibt keine neue Version; war ihr Lesen gescheitert, wird sie neu gelesen. Kennung wie bei den Haustypen des H1-Katalogs `^[a-z][a-z0-9_]{1,59}$`, damit ein Haustyp unter demselben Slug weiterlebt |
| E-HM-43 | Kindprozess `python -m app.house.ifc_process`: setzt zuerst `RLIMIT_AS` und lädt dann IfcOpenShell, die Zeitgrenze hält der Elternprozess; kein `preexec_fn`, weil der Worker Threads hat. Eine unlesbare Datei ist ein Ergebnis (Bericht mit Fehler), kein Fehlschlag des Jobs; erst nach dem letzten Versuch `import_failed` |
| E-HM-44 | Zonentabelle im Katalog: Aliasse und `exterior_door_role` (Vorschlag für Eingang und Garagentor) je Raumtyp, dazu `ignored_zone_categories`; eindeutig nach der Normalisierung, geprüft bei jedem Laden der Katalogversion. Katalogversionen bis HM6 nur per CLI (`house-catalog-import`); dasselbe Dokument (Prüfsumme über sortierte Schlüssel) ergibt keine neue Version |
| E-HM-45 | Lehnt `engine` die Dokumente ab (422), ist die Version nicht kompatibel und der Code des Kerns wird zum Befund; Ausfall, Zeitüberschreitung, 5xx oder eine Antwort außerhalb des Vertrags ergeben `503 engine_unavailable` ohne Befund |
| E-HM-46 | Befundcodes des Imports als feste Liste `FINDING_CODES` (`domain/draft.py`), in der OpenAPI unter `x-codes`; Tests halten Liste, gemeldete Codes und die Texte in FR und DE gleich (E-HM-33). Die Version nennt zu ihren `…_by`-Feldern die Personen (`people`: Konto-ID → Anzeigename oder E-Mail) |
| E-HM-47 | Codes des Kerns als geschlossene Listen in `packages/domain/src/codes.ts` (`MODEL_ERROR_CODES`, `GEOMETRY_ERROR_CODES`, `RULE_CODES`, `COMPATIBILITY_CODES`); `ModelError`, `GeometryError` und die Befunde der Kompatibilitätsprüfung sind darauf typisiert, ein neuer Code kompiliert nur mit Eintrag. Ein Test im Frontend verlangt für jeden Code der Kompatibilitätsprüfung einen Text in FR und DE (`house.check.issue.<code>`, E-HM-33); einen unbekannten Code zeigt die Oberfläche roh |

## 5. Wo die übrigen IDs stehen

Die folgenden Dateien liegen unverändert in `docs/archiv/` ([Übersicht](docs/archiv/README.md)); Verweise im Code (z. B. „Spez. 5.3.1“, „Plan H3 3.8“, „PLAN_AN5 7.4“, „ANNAHMEN PU12“) lassen sich dort nachschlagen.

| Präfix oder Verweis | Datei |
|---|---|
| „Spez.“, L1–L8, E1–E12, S1–S17, M… | [BACKEND_SPEZIFIKATION.md](docs/archiv/BACKEND_SPEZIFIKATION.md) |
| „Plan“, D1–D18, X… | [UMSETZUNGSPLAN.md](docs/archiv/UMSETZUNGSPLAN.md) |
| „Plan G3/H1/H2/H3/A/V“, „PLAN_AN…“, „PLAN_G2…“, E-… | `docs/archiv/PLAN_<Modul>.md` |
| A (R0), G (G1), RW (G2), BR (G3), H (H1), AF (A), HP (H2), HK (H3), VU (V), PS (AN0), UP (AN1), PU (AN2), EA (AN3), KR (AN4), VA (G2-Vollständigkeit), AU (AN5), SC (AN7), MA (AN6) | [ANNAHMEN.md](docs/archiv/ANNAHMEN.md), je Modul ein Abschnitt |
| B-…, R-…, REF-…, S1–S26 des Refactorings | `docs/archiv/REFACTORING_*.md` |
