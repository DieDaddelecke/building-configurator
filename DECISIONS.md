# Entscheidungen

> Stand 25.11.2026. Maßgebliche Liste der Entscheidungen mit ihren ursprünglichen IDs, auf die der Code verweist. Offene Fragen stehen in [ROADMAP.md](ROADMAP.md) 3, die Fachregeln in [DOMAIN.md](DOMAIN.md).

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

### ADR-12 – Service-Token für andere Dienste (25.11.2026, Nutzer)

- **Kontext:** Die Massenstudie (`DieDaddelecke/mass-study`) soll PLU-Regeln von Emprise als Vorschläge übernehmen (Entscheidung des Nutzers vom 25.11.2026: Anbindung als Dienst über eine API). Zugang gab es nur über die OIDC-Sitzung mit zweitem Faktor; die API-Schlüssel der Organisationen hat ADR-07 entfernt.
- **Entscheidung:** Tabelle `service_token` (Name, SHA-256 des Tokens, Rechte, Ablauf, Widerruf, letzte Nutzung), angelegt und widerrufen nur über die CLI mit Audit. Zugriffsregel `require_service_token("rules:read")` mit `Authorization: Bearer emps_…`; einziges Recht `rules:read` für die zwei Leserouten unter `/api/v1/service/rules` (docs/API_REGELDIENST.md). Rate-Limit je Token.
- **Abgrenzung zu ADR-07:** kein Bearer-Zugang zu Projekten, keine Organisation, keine Kosten; das Token handelt nicht als Person. `test_access_policies.py` listet die Routen mit Service-Token.
- **Folgen:** Das Token liegt beim Gegenüber im Server, nie im Browser. Hinter Cloudflare darf der Bot-Schutz `/api/v1/service/` nicht blockieren (ADR-11, Betrieb 27).

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

Plan: [docs/PLAN_HAUSMODELL.md](docs/PLAN_HAUSMODELL.md) (Prompt v3.1, Phasen HM0–HM6); Begründungen und Abschnittsverweise dort. Mit der Beauftragung der Umsetzung (03.10.2026) gelten die Empfehlungen des Plans als entschieden; HM0, HM1, HM3, HM4 und HM5 sind umgesetzt, HM3 bis HM5 auf Anweisung vor HM2 (04.10.2026).

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
| E-HM-31 | Jedes Hüllensegment, jede Öffnung und das Dach erhält seinen Typ aus genau einem Slot (sonst `type_slot_missing`/`type_slot_ambiguous` in der Kompatibilitätsprüfung). Ein Wandprofil je Geschosshülle (`mixed_wall_profiles`), auch nach HM5; Geschosse dürfen verschiedene Profile haben (E-HM-63) |
| E-HM-32 | Raumüberschreibung an Bauteilen zwischen Räumen: Es zählen nur Räume mit Überschreibung; die höchste `override_priority` gilt. Bei Gleichstand greift die Stufe nicht, die Notiz `room_override_tie` nennt die Werte |
| E-HM-33 | Notizen und Geometrieprüfungen tragen Codes; Text nur aus dem Katalog (`unavailable_reason`, Regeltexte), sonst übersetzt die Oberfläche den Code |
| E-HM-34 | Ausdrücke ohne ausführbaren Code mit festem Verhalten: fehlender Pfad null, Pfad über Listen eine Liste ohne null; Größenvergleiche nur zwischen Zahlen, sonst false; Rechnen nur mit Zahlen, Division durch 0 null; nur true ist wahr. Listen in Ausdrücken enthalten nur Werte (sonst wäre der Typ über Listen rekursiv) |
| E-HM-35 | Höhen über ±0,00 = Oberkante Bodenplatte EG. Template: `bearing_height` (Oberkante Außenwand = Unterkante Dachdecke = Decke des Geschosses), Dachdecke als Platte `roof`, Attika über Oberkante Dachdecke; Fassadenhöhe = Bodenplatte + `bearing_height` + Dachdecke + Attika. Demohaus 0,20 + 2,50 + 0,10 + 0,40 = 3,20 m; die lichte Höhe 2,70 m aus P 19.1 passt nicht dazu (PLAN_HAUSMODELL 11.1 Nr. 29) |
| E-HM-36 | `engine` prüft nur die Hülle der Anfrage (Dokumente vorhanden, `schema_version` 2 seit HM5, E-HM-58; `/roof` nur geneigte Formen); den Inhalt prüft die API mit Pydantic vor dem Aufruf und die Antwort danach. Fehler des Kerns antworten mit 422 `{code, detail}`; Anfragen bis 4 MB |
| E-HM-37 | Typ jeder Öffnung aus dem Katalog über die Maße (Fenster: Breite, Höhe, Sturz, Rollladenkasten; Türen: Breite, Höhe; je ±1 mm). Kein oder mehrere Treffer: offener Punkt, das Büro wählt den Wert im Entwurf. Standard je Slot: Angabe des Büros, sonst der häufigste erkannte Wert, sonst der erste des Slots. Abweichende Bauteile stehen im Template unter `element_defaults` (Element → Slot → Wert); Auflösung Element → Raum → global → Standard des Bauteils → Standard des Slots |
| E-HM-38 | Umfang des Imports in HM3: Erdgeschoss mit geraden Wänden und Flachdach (Auflagerhöhe, Dachdecke, Attika, Überstand). Mehrere Geschosse mit Wänden oder Zonen, geneigte Dachflächen und ein fehlendes Dach sind Fehler, bis HM5 sie liest. Seit HM5 liest der Import Geschosse mit derselben Bezugskontur (E-HM-63) und geneigte Dächer (E-HM-65); ein fehlendes Dach (`roof_missing`) und mehrere Dachkörper (`roof_multiple`) bleiben Fehler |
| E-HM-39 | Entwurf = gelesenes Modell (`raw`) + Angaben des Büros (`decisions`). Template und Importbericht entstehen bei jeder Änderung neu mit der zuletzt veröffentlichten Katalogversion des Markts, ohne die Datei erneut zu lesen; eine geänderte geprüfte Version fällt auf `draft` zurück, ihr Prüfbefund verfällt |
| E-HM-40 | Ablauf `draft` → Prüfen (`engine /compatibility`; kompatibel → `reviewed`) → Freigeben (bestätigt den Befund, nur gegen die aktuelle Katalogversion, sonst `409 house_catalog_changed`) → `published` und aktuelle Version des Haustyps → `retired` (aktuell wird die neueste andere veröffentlichte); `rejected` verwirft einen Entwurf. Hochladen, Bearbeiten, Prüfen und Freigeben nur `catalog_admin`, `architect` und `ops` lesen mit (3.6) |
| E-HM-41 | Tabellen `house_template` (Slug, aktuelle Version), `house_template_version` (E-HM-9), `house_catalog`, `house_catalog_version`, `house_catalog_compatibility` (ein Befund je Paar aus Template- und Katalogversion). Trigger: veröffentlichte Versionen nur noch `published` → `retired`, kein Löschen; ein freigegebener Befund ist unveränderlich (L4). Datei unter `house/ifc/<sha256>.ifc` |
| E-HM-42 | Upload: Endung `.ifc` und STEP-Kopf, höchstens 100 MB (`EMPRISE_HOUSE_IFC_MAX_BYTES`), nur mit veröffentlichter Katalogversion (`409 house_catalog_missing`). Dieselbe Datei für einen offenen Entwurf ergibt keine neue Version; war ihr Lesen gescheitert, wird sie neu gelesen. Kennung wie bei den Haustypen des H1-Katalogs `^[a-z][a-z0-9_]{1,59}$`, damit ein Haustyp unter demselben Slug weiterlebt |
| E-HM-43 | Kindprozess `python -m app.house.ifc_process`: setzt zuerst `RLIMIT_AS` und lädt dann IfcOpenShell, die Zeitgrenze hält der Elternprozess; kein `preexec_fn`, weil der Worker Threads hat. Eine unlesbare Datei ist ein Ergebnis (Bericht mit Fehler), kein Fehlschlag des Jobs; erst nach dem letzten Versuch `import_failed` |
| E-HM-44 | Zonentabelle im Katalog: Aliasse und `exterior_door_role` (Vorschlag für Eingang und Garagentor) je Raumtyp, dazu `ignored_zone_categories`; eindeutig nach der Normalisierung, geprüft bei jedem Laden der Katalogversion. Katalogversionen bis HM6 nur per CLI (`house-catalog-import`); dasselbe Dokument (Prüfsumme über sortierte Schlüssel) ergibt keine neue Version |
| E-HM-45 | Lehnt `engine` die Dokumente ab (422), ist die Version nicht kompatibel und der Code des Kerns wird zum Befund; Ausfall, Zeitüberschreitung, 5xx oder eine Antwort außerhalb des Vertrags ergeben `503 engine_unavailable` ohne Befund |
| E-HM-46 | Befundcodes des Imports als feste Liste `FINDING_CODES` (`domain/draft.py`), in der OpenAPI unter `x-codes`; Tests halten Liste, gemeldete Codes und die Texte in FR und DE gleich (E-HM-33). Die Version nennt zu ihren `…_by`-Feldern die Personen (`people`: Konto-ID → Anzeigename oder E-Mail) |
| E-HM-47 | Codes des Kerns als geschlossene Listen in `packages/domain/src/codes.ts` (`MODEL_ERROR_CODES`, `GEOMETRY_ERROR_CODES`, `RULE_CODES`, `COMPATIBILITY_CODES`); `ModelError`, `GeometryError` und die Befunde der Kompatibilitätsprüfung sind darauf typisiert, ein neuer Code kompiliert nur mit Eintrag. Ein Test im Frontend verlangt für jeden Code der Kompatibilitätsprüfung einen Text in FR und DE (`house.check.issue.<code>`, E-HM-33); einen unbekannten Code zeigt die Oberfläche roh |
| E-HM-48 | Kundenweg im Modul `configuration` (`house_api.py`, `house_service.py`, `house_schemas.py`, `domain/facts.py`, `domain/site_check.py`, `domain/outcomes.py`): `configuration` nutzt `house` (Versionen, Freigaben, Client von `engine`), nicht umgekehrt. Alle Kundenrouten hinter der Fahne `house_model` (sonst `403 feature_disabled`); das Büro liest ohne Fahne über `GET /admin/projects/{id}/house/configuration` mit Snapshot (Rollen wie H2) |
| E-HM-49 | Tabelle `house_configuration`, eine je Projekt (Migration 0025): festgehaltene Template- und Katalogversion, Auswahl, Lage in L93, Grenzschalter, Revision mit `If-Match`. Snapshot beim Speichern: Auswertung des Kerns exakt (Preis, Mengen, Ergebnisse, Hausbeschreibung), PLU-Prüfung mit Engine-Version und Eingangsteilen, Preisabgleich. Exakte Beträge nur im Snapshot für das Büro (E-HM-2) |
| E-HM-50 | Angeboten wird je Haustyp die aktuelle veröffentlichte Templateversion mit der neuesten Katalogversion, deren Befund freigegeben ist; nach einer neuen Katalogversion gilt die ältere freigegebene, bis das Büro neu freigibt, ohne Freigabe kein Angebot. Eine Konfiguration behält ihr Paar, auch zurückgezogen; `update_available`, sobald das angebotene Paar ein anderes ist. Die Übernahme folgt mit HM6 (E-HM-7) |
| E-HM-51 | Die Typwahl prüft D12 mit den Standards des Templates (`422 type_blocked` mit allen Gründen), setzt Auswahl, Lage und Grenzschalter zurück und beginnt mit der Schnellstellung `street_near`. Danach lehnt der Server nur ab: eine Auswahl, die der Kern nicht rechnet (`422 house_selection_invalid` mit dem Code des Kerns), eine Drehung außer den vier zur Straße (`rotation_not_allowed`), einen Grenzschalter an einer Kante ohne Erlaubnis (`boundary_not_allowed`). Eine Lage mit Verstoß wird gespeichert (E-HM-6) |
| E-HM-52 | PLU-Ergebnisse nach 3.7: bindend verletzt → `deviation`, auch wo P 19.6 „Warnung“ schreibt; nicht bindend verletzt oder nicht prüfbar → `warning`; Hinweis → `info`. Bei einer Abweichung der Lage schlägt der Server die nächste zulässige Lage vor, zuerst in der eigenen Drehung; übernommen wird sie nur auf Klick |
| E-HM-53 | Rundung kaufmännisch und symmetrisch zur Null (Betrag auf die Stufe, Vorzeichen zurück) in Python (`outcomes.round_amount`) und TypeScript (`haus/preis.ts`) gleich, Aufpreis = Nettodifferenz × (1 + MwSt.). Der Browser schickt seinen Nettopreis mit (`client_price`); weicht er um 0,005 € oder mehr ab, antwortet der Server `price_match: false` und protokolliert `house_price_mismatch`. Gespeichert und angezeigt wird danach der Serverpreis |
| E-HM-54 | `GET` der Konfiguration ruft `engine` nicht: Hausbeschreibung aus dem Snapshot, Lage und PLU-Prüfung mit aktuellem Grundstück und aktuellen Regeln; `site_changed`, wenn deren Eingangsteile vom Snapshot abweichen. `GET …/configuration/documents` liefert die festgehaltenen Dokumente für den Kern im Browser (E-HM-20) |
| E-HM-55 | Adapter Hausbeschreibung → `configuration/domain` (`facts.py`): Umrisse in Metern, Höhen über Gelände, Fassadenrollen; Firstachse `x` → `laengs`, `y` → `quer`, seit HM5 aus dem Azimut des längsten Firsts (E-HM-61). Materialklasse `other` zählt wie jede andere Klasse; ein Flachdach mit `other` verletzt deshalb eine Zone, die Dachmaterialien vorgibt (offen bis zur Auslegung, E-VA-5). Ein Fehler im Adapter ergibt `503 engine_unavailable` |
| E-HM-56 | **Nutzer (HM2 nicht nachholen):** HM4 mit schlanker Oberfläche vor HM2. Seite `/haus` als eigener Chunk: Haustypen, Ausstattung (ein Wert je Slot für alle Elemente), Lageplan (mit H2 geteilt: `configuration/Lageplan.tsx`), Ergebnis der Prüfung, Preisleiste. Jede Änderung wird sofort gespeichert, ein `PATCH` nach dem anderen. Der Kern rechnet im Hauptthread (Demohaus: Auswertung 0,5 ms, alle Kandidaten eines Slots unter 5 ms); Web Worker, 2D/3D, Wahl je Raum oder Element und Vorschau im Büro folgen mit HM2 |
| E-HM-57 | Gespeicherte Antworten des Kerns (`packages/domain/test/fixtures/demo-house/evaluations.json`, `pnpm run evaluations`) ersetzen `engine` in den Python-Tests; ein Test im Kern hält sie aktuell. Der Ende-zu-Ende-Seed `tests/e2e_seed_house.py` legt das Demohaus ohne IFC als veröffentlicht und freigegeben an, nur für Test und CI; im Betrieb entsteht ein Haustyp nur über das Büro (E-HM-40) |
| E-HM-58 | Vertrag Schema 2 (HM5): Dachentwurf im Template (`roof.design`: Form, Neigungen, Knick- bzw. Krüppelhöhe, Drehung); Dachformen, Linien, Terrassen- und Carporttypen und Zahl-Slots im Katalog; Kern 0.4.0. Gespeicherte Dokumente bleiben unverändert (L4), die Validierung hebt beim Lesen: Template und Katalog mit `schema_version` 1 (Flachdach als Entwurf; Katalog ohne Dachformen, Linien und Nebenbauten, Slots ohne `parameter`), Auswertungen vor 0.4.0 (`roof_form` → `roof_shape`, `ridge_direction` → `ridge_azimuth_deg`, ohne Nebenbauten und Zahlen) und Angaben im Entwurf ohne Dach (`roof: null`). `engine` nimmt nur Schema 2, die API schickt die gehobenen Dokumente |
| E-HM-59 | Geneigtes Dach im Kern (`src/roof/`, Ergänzung 11 mit den Folgerungen aus PLAN Kapitel 10): Kanten auf einer Geraden ganzzahlig zusammengefasst; Giebel nur an Flügelenden (Kante mit zwei ausspringenden Ecken), nie zwei nebeneinander; ohne Drehung First längs der längeren Seite jedes Flügels, beim quadratischen Flügel in x-Richtung. Neigung und Überstand je Kantenart (Traufe, Giebel), nicht je Kante: dann ist das Skelett der Traufkontur (Bezugskontur + Wanddicke + Überstand) genau das verlängerte Dach. Pultdach als eine Ebene. Unterseite auf der Bezugskontur in Auflagerhöhe, Aufbau senkrecht zur Fläche darüber. Krüppel- und Knickhöhe gelten auf der Bezugskontur; entsteht der obere Abschnitt nicht (`break_too_high`) oder beginnt der Krüppelwalm am Ortgang nicht über der Traufe (`break_too_low`), ist die Form gesperrt. Toleranzen als feste Bruchteile des Rasters von 0,1 mm, Gleichstand von Längen, Höhen und Linien 1 mm. Gründe als feste Liste `ROOF_REFUSALS` mit Texten in FR und DE; Fehler des Skeletts und eine Wand, die nicht ganz unter dem Dach liegt, heißen `skeleton_failed` |
| E-HM-60 | Lässt sich das Dach mit der Auswahl nicht erzeugen, nimmt der Kern die kleinste Teilmenge der gewählten Dach-Slots zurück: zuerst ohne die Form, klein vor groß, Drehung vor Neigung (höchstens vier Slots). Jede zurückgenommene Wahl erhält die Notiz `roof_not_constructible` mit Grund, die Auswahl bleibt gespeichert (P 2.1 Nr. 9); geht es auch mit den Standards nicht, lehnt der Kern ab (422 `roof_not_constructible`). Ein Wert, der zurückgenommen würde, ist in der Vorschau gesperrt. Ist der Standard eines Slots nicht verfügbar (z. B. Flachdachaufbau bei geneigter Form), gilt der erste verfügbare Wert mit Notiz `default_replaced` (nur ohne übersprungene Wahl, deren Notiz nennt den Ersatz schon); ein Dachaufbau der anderen Art (flach, geneigt) wird mit `roof_kind_mismatch` übersprungen |
| E-HM-61 | PLU-Begriffe der Dachform in Python (`facts.PLU_ROOF_FORMS`): Flach, Pult, Sattel, Walm gleichnamig; Mansarde und Mansardsattel → `mansard`; Krüppelwalm mit den Lesarten `gable`, `hip`, `other`. Die Formprüfung entscheidet nur, wenn alle Lesarten gleich ausgehen, sonst `roof_form_open`. Sind alle geneigten Flächen bis 0,1° gleich, gilt ihr Mittel als Neigung; sonst prüft der Server alle Neigungen und entscheidet, wenn alle die Grenzen einhalten oder keine, sonst `roof_pitch_open`. Offene Prüfungen sind nicht bindend und nicht prüfbar (`warning`, E-HM-52), bis die Auslegung festgelegt ist (E-VA-5). Firstachse aus dem Azimut des längsten Firsts so, dass die Prüfung dieselbe Achse sieht; die Haustypen nennen alle Neigungen (`pitches_deg`) |
| E-HM-62 | Wirksames Dach (`roof/effective.ts`): Form des Templates → Werte aus dem IFC; andere Form → Werte der Katalogform, Überstände bei gleicher Dachart (flach, geneigt) vom Template, sonst von der Form, Flachdach auf geneigtem Template mit Dachdecke und Attika der Form. Zahl-Slots (`value_type` `number`, `parameter` `roof_pitch` oder `roof_rotation`) gelten global am Dach, aufgelöst nach der Form und den übrigen Werten; Standard und Spanne leitet der Kern ab, nicht `defaults`. Neigung in der Spanne der wirksamen Form (bei der Form des Templates bis zu dessen Neigung erweitert), außerhalb der Standard mit Notiz `out_of_range`. Drehung 0/90/180/270° gegen den Uhrzeigersinn für Sattel, Krüppelwalm, Mansardsattel (First) und Pult (Traufseite); eine andere Form übernimmt die Drehung des Templates bei gleicher Drehsemantik. Gilt ein Slot für die Form nicht (Flachdach; Walm und Mansarde ohne Drehung), fehlt sein Wert. Kandidaten nur für die Drehung (vier Lagen mit Preis); die Neigung stellt ein Regler (`roofPitchRange`) und speichert beim Loslassen. Wie bei Werten entfernt der Standard die Wahl |
| E-HM-63 | Geschosse: Eine Ebene mit Wänden oder Räumen ist ein Geschoss mit genau einer Hülle; alle haben die Bezugskontur des Erdgeschosses (1 mm, gleiche Eckenfolge; sonst `storey_outlines_differ` im Kern, `storey_contour_differs` im Import). Ein Geschoss reicht bis zur Höhe des nächsten, die Decke darüber gehört zu ihm; der Import verlangt unter jedem Obergeschoss eine Decke (`floor_slab_missing`), eine Ebene nur mit dem Dach ist die Dachebene (`roof_level`). Für die Hausbeschreibung gilt die Fassade des Geschosses mit der dicksten Wand, die Fassadenrollen setzt das Büro am Erdgeschoss. Wandflächen je Segment bis zur Unterseite des Dachs, Giebelwände eingeschlossen (Ergänzung 5) |
| E-HM-64 | `engine /roof`: geneigtes Dach aus Bezugskontur, Wanddicke, Auflagerhöhe, Überständen, Form und Dicke (`HouseRoofRequest` → `HouseRoofGeometry`: Traufkontur, Kantenarten, Flächen mit Unterseite, Linien, Höhen, Firstazimut); eine nicht erzeugbare Form antwortet 422 `roof_not_constructible` mit Grund. Nur der IFC-Import ruft es; eine Ablehnung ist für ihn ein Ergebnis, ein Ausfall von `engine` ein Fehler des Jobs (E-HM-43, E-HM-45) |
| E-HM-65 | Dach im Import (`domain/roof.py`): Aus der Unterseite des `IfcRoof`-Körpers wird jede Kante der Bezugskontur Traufe (überall gleich hoch, Fläche steigt senkrecht nach innen) oder Giebel; Höhe der Traufen = Auflager. Krüppelwalm über der Mitte eines Giebels, oberer Mansardabschnitt nur dort, wo er an die Traufebene anschließt, je bis zu drei Kandidaten nach Häufigkeit; Überstände je Kantenart. Je Kandidat und Drehung erzeugt der Kern das Dach (`/roof`); erkannt ist die erste Form mit denselben Kantenarten und einer Unterseite gleich auf 1 mm plus dem Rundungsfehler der Neigung (0,01°). Sonst offen `roof_form_not_recognized` mit Grund. Das Büro kann im Entwurf ein geneigtes Dach setzen (`decisions.roof`, Startwerte je Form wie im Demo-Katalog), das das Dach aus dem IFC ersetzt (`roof_set_by_office`); ein Flachdach braucht die Dachdecke aus dem IFC. Der Standard von Dachform und Dachaufbau folgt dem Dach des Templates |
| E-HM-66 | Ausstattungslinien (`catalog.lines`: Slot → globaler Wert): Die Oberfläche setzt die Werte auf Klick, Werte gleich dem Standard des Templates entfallen wie bei jeder Wahl, Zahlen bleiben gesetzt, Überschreibungen je Raum oder Element bleiben. Gespeichert wird nur die Auswahl; aktiv ist die erste Linie nach `sort_order`, deren Werte alle gelten (`activeLine`), sonst „Eigene Zusammenstellung“. Der Aufpreis einer Linie ist die Preisdifferenz ihrer Werte (E-HM-14) |
| E-HM-67 | Terrasse und Carport (Slots am Element `site`; ein Wert ohne Typ heißt keiner): Maße rechnet der Kern (`facts.terrace`, `facts.carport`; die Terrasse so breit wie die längste Gartenkante, ohne sie keine). Lage, Zufahrt und Prüfungen (`annex`, `unsealed_min`, `parking`) rechnet Python mit `outbuildings.py` wie im heutigen Konfigurator: Terrasse vor der Gartenkante, Carport nah an der Straße ohne Haus und Terrasse zu berühren, Zufahrten von Carport und Garagentor. Die Kunden-API liefert die gesetzten Nebenbauten für den Lageplan (`outbuildings`) |

### 4.12 Regeldienst für die Massenstudie (E-RD)

Plan: [docs/PLAN_REGELDIENST.md](docs/PLAN_REGELDIENST.md); Format für die Gegenseite: [docs/API_REGELDIENST.md](docs/API_REGELDIENST.md). Auftrag des Nutzers vom 25.11.2026; die Empfehlungen des Plans gelten mit der Umsetzung als entschieden.

| Nr. | Entscheidung |
|---|---|
| E-RD-1 | Umfang der Auswertung `house` (ein Einfamilienhaus, wie bisher) oder `collectif` (Wohngebäude mit mehreren Wohnungen). `collectif` hat einen eigenen Systemprompt und eine eigene Nachsuche (Grund `single_house` statt `multi_dwelling`); Status, Zitat und Parameter sind dieselben. Prompt, Schemata und Eingabe-Hash von `house` bleiben bytegleich (Prüfsummen `a7ad548f037be25e`, `dc4e752f99503cef` im Test) |
| E-RD-2 | Pflichtarten `collectif`: `setback_street`, `setback_side`, `setback_rear`, `setback_between_buildings`, `max_footprint_ratio`, `max_height`, `unsealed_min`; Dach und Fassade werden gelesen, sind aber keine Pflicht. Schranken (`BOUNDS`) und `ENGINE_VERSION` bleiben; Werte darüber werden `unknown` (`out_of_bounds`) |
| E-RD-3 | Ablage: `rule_set.scope` mit Eindeutigkeit je Planstand, Zone und Umfang; `rule_extraction_run.scope`; Stand eines zusätzlichen Umfangs in `regulation_chapter_scope`, der von `house` bleibt in `regulation_chapter` (Migration 0026). Kundenweg, Analyse, Abdeckung im Büro und Referenzlisten lesen nur `house` |
| E-RD-4 | `collectif` wertet nur die CLI aus (`rules-extract --scope collectif --commune X --zone Z` oder `--chapter`): kein Job, kein Housekeeping, keine Auswertung über die API. Jeder Lauf ist bezahlt und braucht das Go des Nutzers |
| E-RD-5 | Leserouten `GET /service/rules/communes/{insee}` und `…/zones/{zone}?scope=` im Format `emprise-rules/1`; Regeln im Modell `RuleOut`. Nur der aktuelle Planstand der Gemeinde, kein Rückfall auf einen älteren; ohne Auswertung `not_extracted` |
| E-RD-6 | Prospect zur gegenüberliegenden Straßenseite und Werte nach Wohnungszahl bleiben `text_only` mit Zitat; ein Parameter dafür ändert das gemeinsame Ausgabeschema und damit den Hausprompt und braucht eine eigene Entscheidung |
| E-RD-7 | Referenzlisten tragen optional `"scope"`; `reference-check` misst dann die Versionen dieses Umfangs |
| E-RD-8 | Gegenprüfung und Zusammenführen vergleichen über `agreed_params`: Freitext nicht, ein Grenzwert nur eines Laufs nur, wenn dieselbe Zahl von beiden gelesen wurde, Angaben ohne Grenzwert nur eines Laufs entfallen; die Regel trägt die gemeinsamen Werte. Gilt für beide Umfänge, `ENGINE_VERSION` g2-1.3.0 (Messung Palaiseau, PLAN_REGELDIENST 9, Auftrag des Nutzers 26.11.2026) |
| E-RD-9 | Abstände vor Fassaden ohne Ansichten: `blind_min_m`, `blind_height_factor` bei `setback_side`, `setback_rear`, `setback_between_buildings`; nur im Umfang `collectif` gefragt (eigenes Schema, `COLLECTIF_ONLY_PARAMS`), das Haus bleibt bytegleich. Ergänzt E-RD-6 |
| E-RD-10 | `setback_between_buildings` nimmt optional `height_basis` wie die Grenzabstände; der Faktor 1 der Höhe gilt auch als Punkt „- la hauteur …“ einer Aufzählung nach „égale à :“. Prompt und Schemas unverändert, `ENGINE_VERSION` g2-1.3.1 (Messung Palaiseau, PLAN_REGELDIENST 9, Auftrag des Nutzers 26.11.2026) |

## 5. Wo die übrigen IDs stehen

Die folgenden Dateien liegen unverändert in `docs/archiv/` ([Übersicht](docs/archiv/README.md)); Verweise im Code (z. B. „Spez. 5.3.1“, „Plan H3 3.8“, „PLAN_AN5 7.4“, „ANNAHMEN PU12“) lassen sich dort nachschlagen.

| Präfix oder Verweis | Datei |
|---|---|
| „Spez.“, L1–L8, E1–E12, S1–S17, M… | [BACKEND_SPEZIFIKATION.md](docs/archiv/BACKEND_SPEZIFIKATION.md) |
| „Plan“, D1–D18, X… | [UMSETZUNGSPLAN.md](docs/archiv/UMSETZUNGSPLAN.md) |
| „Plan G3/H1/H2/H3/A/V“, „PLAN_AN…“, „PLAN_G2…“, E-… | `docs/archiv/PLAN_<Modul>.md` |
| A (R0), G (G1), RW (G2), BR (G3), H (H1), AF (A), HP (H2), HK (H3), VU (V), PS (AN0), UP (AN1), PU (AN2), EA (AN3), KR (AN4), VA (G2-Vollständigkeit), AU (AN5), SC (AN7), MA (AN6) | [ANNAHMEN.md](docs/archiv/ANNAHMEN.md), je Modul ein Abschnitt |
| B-…, R-…, REF-…, S1–S26 des Refactorings | `docs/archiv/REFACTORING_*.md` |
