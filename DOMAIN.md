# Fachdomäne

> Stand 30.09.2026. Was die Anwendung fachlich tut, welche Leitplanken gelten und wie die Begriffe im Code heißen. Technik: [ARCHITECTURE.md](ARCHITECTURE.md). Begründungen und IDs: [DECISIONS.md](DECISIONS.md).

## 1. Zweck

Emprise ist eine Plattform für Bauinteressenten in Frankreich und eine eigene Marke, getrennt vom Architekturbüro.

| Bereich | Wer | Ablauf |
|---|---|---|
| Konfigurator (`/`) | Kunden, anonym | Parzelle wählen (G1) → Regeln des Bebauungsplans (G2) → Baurahmen (G3) → Haustyp und Lage (H2) → Linie, Optionen, Kostenkorridor (H3) → unverbindlicher Vorentwurf an das Büro (V). Daneben jederzeit eine Anfrage ohne Konfiguration (A, D14) |
| Büro (`/buero`) | Mitarbeitende | Anfragen und Übergaben prüfen, Kanten und Regeln korrigieren, Katalog pflegen, Abdeckung der Regelwerke |
| Analyse (`/analyse`) | Architekten des eigenen Büros | Parzelle als Datei oder Zeichnung einbringen, règlement écrit hochladen, Zone wählen → Baurahmen, bindende Grundfläche, Geschosse, Nutzfläche, Gabarit und Schnitt; Regeln mit Begründung korrigieren; Bericht-PDF, DXF, GeoJSON |

Ergebnis ist nie ein Kauf und nie eine Rechtsauskunft, sondern eine Simulation, die das Büro nach Kontakt prüft (D11).

## 2. Leitplanken

Aus der Spezifikation (Kapitel 1.2), L2 und L6 angepasst an D11 und D12. Sie gelten für Backend und Frontend.

| Nr. | Leitplanke |
|---|---|
| L1 | **Kein Shop.** Keine Zahlung, kein Vertrag, keine Bestellung. Preise nur als Spanne oder mit „ca.“; die API liefert nie ein Feld, das als exakter Gesamtpreis gelesen werden kann. |
| L2 | **Simulierte Regeln begrenzen nur mit belegtem Zitat.** G2 wertet vollautomatisch aus, ohne Freigabe (D11). Bindend ist nur eine wirksame Regel (`effective`, Zitat und Werte geprüft); `unknown`, fehlende Pflichtarten und `text_only` erzeugen Hinweise (D12). Das Büro prüft nach Kontakt. |
| L3 | **Jede abgeleitete Zahl hat eine Herkunft**: Quelle, Methode, Version, Annahmen (`provenance`, Fundstelle mit Seite und Zitat). |
| L4 | **Veröffentlichte Stände sind unveränderlich**: Katalogversionen, Preiskataloge, Regelwerksversionen, Rechtstexte, Audit. Eine Änderung erzeugt eine neue Version; eine Übergabe friert die Versionen ein. |
| L5 | **Der Server ist maßgeblich** für Geometrie und Prüfung. Das Frontend rechnet nur zur Vorschau. |
| L6 | **Automatik schlägt vor, Menschen bestätigen.** Kanteneinordnung, Georeferenzierung, Scan-Erkennung und Regelauswertung liefern Vorschläge; Büro und Architekt korrigieren mit Begründung. Bei der Regelauswertung ersetzt die Prüfung nach Kontakt die Freigabe (D11). |
| L7 | **Grenzen der Aussage sind sichtbar**: Katasterplan ist keine Vermessung, Regelprüfung keine Bauantragsprüfung, RE2020-Status keine Wärmeschutzberechnung; maßgeblich ist das Certificat d'urbanisme. |
| L8 | **Datenschutz**: Hosting in der EU (bis zur Beta auf eigenem Server, D3), Datenminimierung, Einwilligung vor Übermittlung an das Büro, keine Kundendaten an Sprachmodelle – nur öffentliche Planunterlagen. |

Arbeitsprinzip der Regelkette: **Das Sprachmodell liest, Python rechnet, der Mensch prüft** (DECISIONS ADR-01).

## 3. Glossar

| Deutsch | Französisch | Im Code |
|---|---|---|
| Parzelle | parcelle | `parcel`, Kataster in `ref_parcel` |
| Grundstück (eine oder mehrere Parzellen, Skizze oder Upload) | unité foncière | `site`, Herkunft `origin` ∈ `parcel`, `manual_sketch`, `upload` |
| Grundstückskante | limite | `site_edge`, Art `street`, `side`, `rear`, `other` |
| Bebauungsplan | PLU / PLUi | `land_use_plan` (GPU-Import oder `origin = 'upload'`) |
| Zone | zone (z. B. UB) | `zone`; Überlagerungen `overlay_constraint` |
| Schriftliche Festsetzungen | règlement écrit | `source_file`, `source_page`, `regulation_chapter` |
| Zusatzdokument | règlement de lotissement, cahier des charges | `project_regulation` |
| Regelwerk | règles applicables à la zone | `rule_set`, `rule_set_version`, `rule` (unveränderlich) |
| Auswertungslauf | – | `rule_extraction_run` |
| Projektkorrektur | – | `project_rule_override` |
| Abstand zur Straße / seitlich / hinten / zwischen Gebäuden | recul / retrait | `setback_street`, `setback_side`, `setback_rear`, `setback_between_buildings` |
| Grundflächenzahl | coefficient d'emprise au sol (CES) | `max_footprint_ratio` |
| Absolute Obergrenze Fläche | – | `max_area` (`footprint_m2`, `sdp_m2`) |
| Höhe (Traufe, First, Attika) | hauteur à l'égout, au faîtage, à l'acrotère | `max_height`; `eave_m`, `ridge_m`, `parapet_m` |
| Unversiegelte Fläche | pleine terre | `unsealed_min` |
| Baurahmen | zone d'implantation possible | Ergebnis von `derive_envelope`: Konturen `lenient` (weiteste) und `strict` (engste Auslegung) |
| Steckbrief | fiche | `envelope_sheet` (PDF) |
| Bindende Grundfläche | emprise au sol | `analysis/domain/footprint.py` |
| Nutzfläche | surface de plancher (SDP) | `analysis/domain/floor_area.py` (Spanne) |
| Gabarit | gabarit | Hüllkörper in Höhenstufen, `analysis/domain/gabarit.py` |
| Haustyp | modèle | `building_type`, `building_type_version` |
| Ausstattungslinie | gamme | `package`, `package_version` |
| Option | module / option | `module`, `module_version` |
| Preiskatalog | – | `price_catalog`, `price_catalog_version` |
| Implantation (Lage des Hauses) | implantation | `configuration.placement` (Lambert-93 gespeichert, lokale Meter in der API) |
| Anfrage | demande | `inquiry` (Vorgang), `customer`, `consent` |
| Übergabe, Vorentwurf | transmission, esquisse | `submission` je Fassung, Dossier-PDF |
| Energiebewertung | étude thermique RE2020 | `energy_assessment` |
| Organisation, Mitglied | – | `organisation` (Art `operator` oder `customer`), `organisation_member` |

## 4. Fachregeln

### 4.1 Grundstück (G1)

- Geometrie in der Datenbank in Lambert-93 (SRID 2154); gerechnet wird mit Shapely, im Baurahmen in lokalen Metern.
- Kanten werden automatisch eingeordnet (`site/domain/edges.py`); Kunde und Büro korrigieren. Unbestätigte Einordnung hindert keine Anfrage; das Büro prüft beim Eingang.
- Weg E (Skizze ohne Kataster): Geometrie ohne geografischen Bezug, nie als echte Lage behandeln; die letzte Kante schließt den Umriss.
- Upload (DXF, GeoJSON, vektorielles PDF, Scan zum Nachzeichnen): Koordinatensystem an der Größenordnung erkannt; kurze Stücke bilden keine eigene Kante; Beschriftungen gehen nicht in die Flächen ein. Die Datei wird nicht aufbewahrt, nur ihre Herkunft.
- Lage eines hochgeladenen Grundstücks: auf der Karte mit Katasterebene verschieben und drehen; erst dann Gelände und Risiken.

### 4.2 Regeln (G2)

- Regelarten: `setback_street`, `setback_side`, `setback_rear`, `setback_between_buildings`, `max_footprint_ratio`, `max_height`, `roof`, `facade`, `unsealed_min`, `parking`, `annex`, `planting`, `fence`, `text_only`, `max_area` (`rules/domain/kinds.py`).
- Status: `effective` (bindend), `unknown`, `not_regulated` (belegt nicht geregelt), `text_only`.
- Pflichtarten für das Hauptgebäude: die drei Abstände, Grundflächenzahl, Höhe, Dach, Fassade, unversiegelte Fläche. Fehlt eine, ist sie `unknown` – nie ein Standardwert.
- Eine Regel wirkt nur, wenn ihr Zitat auf der genannten Seite steht, ihre Zahlen im Zitat vorkommen, der Sektor passt und die Gegenprüfung dieselben Werte liest. Mehrdeutiges bleibt sichtbar offen, bis der Nutzer die Auslegung festlegt (E-VA-5).
- Korrekturen: Das Büro legt je Zone eine Bürofassung an (Konfigurator); Büro und Architekten korrigieren je Projekt mit Begründung und Fundstelle (`project_rule_override`). Dasselbe PDF ist dasselbe Dokument für alle Projekte (erkannt am sha256); eine Zonenkorrektur gibt es in der Analyse deshalb nicht.
- Zusatzdokumente werden mit dem PLU verglichen, nicht verrechnet; ein Wert gilt erst, wenn der Architekt ihn übernimmt (Vorschlag: das Strengere je Parameter).
- Ein hochgeladenes PLU geht dem GPU-Stand vor. Gescannte Reglements werden nach Bestätigung lokal erkannt (Tesseract); im GPU-Weg gibt es keine Texterkennung.

### 4.3 Baurahmen (G3)

- `derive_envelope` ist rein und deterministisch; der Baurahmen wird nicht gespeichert, sondern bei Bedarf gerechnet (`input_hash`, Fingerabdruck).
- Zwei Konturen: `lenient` legt jede Regel am günstigsten aus, `strict` am strengsten; ein nicht ermittelter Abstand wird nicht geschätzt.
- Teilflächen einer Zone ohne ausgewertete Regeln gelten als nicht bebaubar. Emplacement réservé und Espace boisé classé sind Bauverbot; Risiko- und Schutzflächen wirken nur in der engsten Auslegung.

### 4.4 Analyse (AN3–AN5)

- Bindende Grundfläche je Teilfläche und Auslegung: Minimum aus Kontur, Anteil aus `max_footprint_ratio` und `max_area.footprint_m2`; fehlt der Anteil, bleibt der Wert eine Obergrenze.
- Nutzfläche als Spanne: beide Enden mit derselben Formel aus Gabarit, Geschossen und Außenwandabzug; unten sicher Tragbares, oben das Mögliche.
- Gabarit in Stufen von 3,00 m plus kennzeichnende Höhen, über der Traufe senkrecht bis zum First; über der mittleren Geländehöhe mit Hinweis bei Neigung über 5 %. Zwei feste Schnitte A–A und B–B.
- Eine Zone je Grundstück; Zonengrenzen einzeichnen erst nach Auslöser.

### 4.5 Konfiguration und Kosten (H1–H3)

- Nur wirksame Regeln sperren Typen und Lagen; eine unzulässige Lage wird nicht gespeichert (`422 placement_violation`). Ohne Baurahmen (Weg E, keine Regeln) gilt ein freier Modus im Umriss (D12, D13).
- Kosten: `Basis + Linie + Optionen (nicht in der Linie) + Konformität`, als Spanne in Cent, netto gerechnet, brutto mit dem Satz des Katalogs angezeigt, auf 1.000 € gerundet mit „ca.“ (D10, L1).
- Ein veröffentlichter Preiskatalog gilt je Region als Ganzes; ein Posten ohne Preiszeile ist nicht wählbar.

### 4.6 Anfrage und Übergabe (A, V)

- Einwilligung vor jeder Übermittlung an das Büro, bezogen auf eine unveränderliche Textversion. Bestätigungscode per Mail, 10 Minuten gültig.
- Übergabe je Fassung (`submission`); vor dem Absenden wird die Konfiguration neu geprüft. Das Dossier entsteht auf Französisch und Deutsch.
- Die Anfrage ohne Konfiguration bleibt dauerhaft möglich (D14).
- Entwürfe ohne Anfrage werden 90 Tage nach der letzten Aktivität gelöscht (`retention_cleanup`); nach einer Anfrage löscht nur das Büro (`409 deletion_requires_office`, D6 offen).
