# AN3 – Analyse für den Entwurf und Zusatzdokumente (Emprise Analyse)

> **Status:** geplant und umgesetzt am 26.09.2026 (Befunde beim Bau in 7.4) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN3, dazu die Zusatzdokumente aus AN4), 8.1 Nr. 8 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN3 (Präfix `EA`)
> **Voraussetzung:** AN0–AN2 (PS, UP, PU). Fachregeln: `BACKEND_SPEZIFIKATION.md` 5.2 (Regelarten), 5.3 (Baurahmen), 5.8 (Flächen, SDP nach R.111-22); Umsetzung G3 nach ANNAHMEN BR01–BR15.
> **Entscheidungen des Nutzers vom 25.09.2026:** AN3 mit dem RA1-Teil (bindende Grundfläche, Vollgeschosse, Nutzflächenspanne); **Zusatzdokumente aus AN4 vorgezogen** (E-AN2-5 anders entschieden als empfohlen): hochladen, auswerten, neben den PLU-Regeln zeigen – den Vergleich trifft der Architekt, die Übernahme als Projektkorrektur bleibt bei AN4.

---

## 1. Zweck und Umfang

Der Baurahmen aus G3 zeigt Konturen, Grenzwerte und Abstände – aber nicht die drei Zahlen, mit denen ein Architekt den Entwurf beginnt: **wie viel Grundfläche bindet**, **wie viele Geschosse** gehen und **wie viel Nutzfläche (surface de plancher, SDP)** daraus höchstens entsteht. AN3 bildet sie aus Baurahmen und Regeln, als Spanne mit offengelegten, je Projekt änderbaren Annahmen und mit Herkunft an jedem Eingangswert. Dazu kommen die Abstände je Grenze im Klartext.

Zweiter Teil: **Zusatzdokumente** – règlement de lotissement und cahier des charges – gelten neben dem PLU. Der Architekt lädt sie hoch, nennt das Lot, die Auswertung liest die Regeln mit eigenem Prompt, und die Analyse zeigt sie neben den PLU-Regeln mit einer Einordnung je Regel (strenger, weniger streng, gleich, abweichend).

**Enthalten:** Modul `analysis` (nur Analyse-Produkt) mit reiner Fachlogik; Annahmen je Projekt; neue Regelart `max_area` (Höchstflächen in m²) für PLU und Zusatzdokumente; Zusatzdokumente hochladen, lesen, Lot wählen, auswerten; Vergleich mit dem PLU; Oberfläche „Analyse“ und „Zusatzdokumente“ auf der Projektseite; Abstandsaussage je Grenze.

**Nicht enthalten:** Gabarit (Höhenstufen) und Schnitt – RA2, wie in PLAN_ANALYSE 5; Übernahme eines Werts aus einem Zusatzdokument als Projektkorrektur mit Zitat (AN4, zusammen mit dem Regelformular); Verrechnung der Zusatzdokumente in die Analysewerte (E-AN3-2); Bericht-PDF (AN5); SDP aus einem echten Grundriss (X3).

## 2. Befund

| Baustein | Stand | Folge für AN3 |
|---|---|---|
| `derive_envelope` | liefert je Auslegung eine Kontur (Geometrie, Fläche) und je Zonen-Teilfläche Grenzwerte, darunter `footprint_max_m2 = ratio × Teilfläche` | Bindende Grundfläche = Minimum aus Kontur ∩ Teilfläche, `footprint_max_m2` und einer absoluten Obergrenze – je Teilfläche, dann Summe |
| `heights.from_rule` | rechnet `R+1+C` mit 3,00 m in Traufe und First um (nur für die engste Kontur) | Für die Geschosszahl **nicht** verwenden, sondern die Regel selbst: sonst stünde „aus der Traufhöhe“, wo der Plan Geschosse nennt |
| Regelarten (`kinds.py`) | keine Art für eine SDP-Obergrenze oder eine absolute Grundfläche; `max_footprint_ratio.ratio` ist Pflicht und wird in H2/H3 an vier Stellen vorausgesetzt | neue Art `max_area` statt `max_footprint_ratio` aufzuweichen (3.6) |
| `create_full_app` | baut `openapi.json` aus dem Profil `configurator` | Routen, die nur das Analyse-Produkt hat, fehlten in `openapi.json` und `schema.d.ts` → das volle Profil wird die Vereinigung aller Produkte |
| `project_regulation` | Rolle nur `plu`, höchstens eines je Projekt | Rolle `supplement` dazu |
| `read_document` | legt je erkanntem Zonenkapitel eine Zeile an | Zusatzdokumente haben keine Zonenkapitel → ein Kapitel `DOC` über das ganze Dokument |
| `extract_chapter` | PLU-Prompt, Pflichtarten werden als `unknown` ergänzt (`complete`) | zweiter Prompt; ohne Pflichtarten |
| `assess.foreign_sector` | ordnet Werte über Nennungen der Sektoren im Zitat zu | Lotnummern („12“) wären überall Zahlen im Zitat („12 m“) → falsche `sector_mismatch` → Sektor `Lot-12` (3.7) |
| Oberfläche | `Bebauungsplan` und `ProjektSeite` nehmen `regulations[0]` als PLU | mit Zusatzdokumenten nach Rolle filtern |

## 3. Fachliche Festlegungen

### 3.1 Bindende Grundfläche

Je Zonen-Teilfläche und Auslegung (`lenient`, `strict`) drei Kandidaten:

| Kandidat | Wert | Herkunft |
|---|---|---|
| `contour` | Fläche der Kontur innerhalb der Teilfläche | Baurahmen (G3) |
| `ratio` | `ratio × Teilfläche` aus `max_footprint_ratio` | Zitat der Regel |
| `absolute` | `footprint_m2` aus `max_area` | Zitat der Regel |

Bindend ist das Minimum der ermittelten Kandidaten; die Ausgabe nennt ihn. `not_regulated` heißt: kein Kandidat. Ist `ratio` nicht ermittelt (`unknown`, `missing`), bleibt der Wert eine **Obergrenze** (`complete: false`, Grund `footprint_ratio_unknown`) – nie geschätzt (D11). Teilflächen, die der Baurahmen ausschließt (`excluded`), tragen 0 bei. Summe über alle Teilflächen je Auslegung.

*Beispiel* (Testparzelle 20 × 30 m, Zone Uh): Kontur 300 m² (weit) und 210 m² (eng), Grundflächenzahl 25 % → 150 m²; bindend in beiden Auslegungen 150 m² (`ratio`).

### 3.2 Vollgeschosse

Aus der Regel `max_height` der Teilfläche (Parameter, nicht `Heights`):

| Lage | Vollgeschosse | Oberstes Geschoss | Quelle |
|---|---|---|---|
| `storeys` (`R+1+C`) | 1 + Obergeschosse, exakt | `C` → Dachgeschoss, `A` → Attika, sonst keines | `storeys` |
| `eave_m` | ⌊Traufe / h_max⌋ … ⌊Traufe / h_min⌋ | Dachgeschoss **möglich**, wenn `ridge_m − n_max × h_min ≥ 2,20 m` (Streifen über 1,80 m) | `eave` |
| nur `parapet_m` | ⌊Attika / h⌋ | keines (Flachdach) | `parapet` |
| nur `ridge_m` | ⌊(First − 5,00) / h_max⌋ … ⌊First / h_min⌋ (Dachform offen) | Dachgeschoss möglich | `ridge` |
| keine Höhe | nicht ermittelt | – | `unknown` |

`h` ist die Geschosshöhe (Boden bis Boden) aus den Annahmen (3.4). Nennt der Plan Geschosse **und** eine Traufhöhe, gilt die Geschosszahl; ist sie mit `h_min` unter der Traufe nicht erreichbar, erscheint `storeys_exceed_eave`. Ein nur *mögliches* Dachgeschoss zählt am unteren Ende der Spanne nicht mit (E-AN3-5).

*Beispiel* Uh: Traufe 7 m, First 10 m → ⌊7/3,00⌋ = ⌊7/2,70⌋ = 2 Vollgeschosse (R+1); 10 − 2 × 2,70 = 4,60 m ≥ 2,20 m → Dachgeschoss möglich. Nur First 10 m: ⌊5/3,00⌋ = 1 bis ⌊10/2,70⌋ = 3 Vollgeschosse; über drei Geschossen bleiben 1,90 m → oben kein Dachgeschoss.

### 3.3 Nutzfläche (SDP) als Spanne

Je Teilfläche: **SDP = F × (n + s) × (1 − w)** mit F bindender Grundfläche, n Vollgeschossen, s anrechenbarem Anteil des obersten Geschosses, w Außenwandabzug (SDP wird innen gemessen, die Grundfläche außen).

- **unten:** F aus der engsten Auslegung, n_min, s_min (0, wenn das Dachgeschoss nur möglich ist), w_max
- **oben:** F aus der weitesten Auslegung, n_max, s_max, w_min
- Obergrenze `max_area.sdp_m2` der Zone → beide Enden höchstens so groß; die Ausgabe nennt, dass sie bindet.
- Summe über die Teilflächen, gerundet auf 1 m².
- **Nicht gerechnet und benannt** (R.111-22 und Entwurf): Treppen- und Aufzugsöffnungen, Flächen unter 1,80 m (nur über den Anteil s angenähert), Stellplätze und Rampen, nicht ausbaufähige Dachräume, Technik- und Kellerräume, Abzug von 10 % bei Sammelerschließung, Laibungen; außerdem Höhenbegrenzung auf der Grenze (`on_boundary_max_height_m`) und höhenabhängige Abstände oberer Geschosse in der weitesten Auslegung (Gabarit, RA2).

*Beispiel* Uh mit Vorgaben: unten 150 × (2 + 0) × 0,85 = **255 m²**, oben 150 × (2 + 0,75) × 0,92 = **380 m²** (379,5).

### 3.4 Annahmen je Projekt

| Annahme | Vorgabe | Grenzen |
|---|---|---|
| Geschosshöhe `storey_height_m` (Boden bis Boden) | 2,70 – 3,00 m | 2,40 – 4,00 |
| Außenwandabzug `wall_share` | 8 – 15 % | 0 – 30 % |
| Anteil Dachgeschoss `attic_share` (> 1,80 m) | 50 – 75 % | 0 – 100 % |
| Anteil Attikageschoss `attique_share` | 60 – 80 % | 0 – 100 % |

Gespeichert je Projekt (Tabelle `analysis_parameters`, Migration 0014), weil der Bericht (AN5) sie nennen muss; ohne Eintrag gelten die Vorgaben. Jede Annahme ist ein Bereich (min ≤ max). Die Antwort nennt benutzte Werte und Vorgaben.

### 3.5 Abstand je Grenze im Klartext

Aus dem vorhandenen Baurahmen (`EnvelopeOut.edges[].setbacks` mit Parametern, Höhen der Teilfläche) – reine Formatierung in der Oberfläche, kein neuer Endpunkt: „auf der Grenze zulässig (bis 3,50 m Höhe), sonst mindestens 3,00 m“, „H/2 an der Traufe, mindestens 3,00 m – bei 7,00 m also 3,50 m“, „zwischen 5 und 20 m (ganzer Baukörper)“, „nicht geregelt“, „nicht ermittelt“, jeweils mit Seite. Kanten `other` nennen beide Regeln.

### 3.6 Neue Regelart `max_area`

Parameter `sdp_m2` (surface de plancher maximale) und `footprint_m2` (emprise au sol maximale in m²), mindestens einer; Plausibilität 10–5000 m²; gilt für das Grundstück (nicht je Baukörper). Beide Prompts kennen sie. Warum eine neue Art statt eines optionalen `max_m2` an `max_footprint_ratio`: H2/H3 setzen `ratio` an vier Stellen voraus, und `derive._part` schlösse eine Teilfläche ohne `ratio` als `footprint_zero` aus.

Folge: Der PLU-Prompt ändert sich (`g2-prompt-4`); mit dem Schlüssel wird ohnehin jedes Kapitel neu ausgewertet (HANDOFF 4.6), zusätzliche Kosten entstehen dadurch nicht. Der Hauskonfigurator zeigt die neue Art in der Regelliste, prüft sie aber nicht (wie `spaces_per_m2_sdp`, Plan H3).

### 3.7 Zusatzdokumente

- **Hochladen:** derselbe Endpunkt `POST /projects/{id}/regulations` mit Art `lotissement` oder `cahier_des_charges` → Rolle `supplement`. Höchstens drei je Projekt (`422 too_many_supplements`); ein PLU wird dadurch nicht ersetzt. Dasselbe PDF bleibt dasselbe Dokument (PU01); war es schon mit der anderen Kategorie (PLU ↔ Zusatzdokument) hochgeladen, `409 document_type_conflict` – sonst liefe es mit dem falschen Prompt.
- **Lesen:** Job `rules_document_read` wie bisher, aber statt Zonenkapiteln ein Kapitel **`DOC`** über das ganze Dokument, ohne allgemeine Seiten, ohne Vorschläge (`detection = 'document'`).
- **Lot wählen:** `PUT /projects/{id}/regulations/{document_id}/lot` mit `lot` (optional, z. B. `12`) und optional Seitenbereich. Der Sektor heißt `Lot-12`, ohne Lot `Ensemble`; er kommt zu den Sektoren von `DOC`. Wie bei der Zonenwahl: geänderte Eingabe → `pending` und Job, **Kosten hier**; über 150 Seiten → `422 chapter_too_long`, dann Seitenbereich angeben.
- **Auswertung:** `rules_extract` mit **eigenem Prompt**: Regeln für ein neues Einfamilienhaus auf dem angefragten Lot, Tabellen je Lot nur für dieses Lot, keine Regeln, die nur auf den PLU verweisen; dieselben Regelarten und Schranken, Gegenprüfung wie beim PLU, **keine Pflichtarten** (`complete` entfällt). Budget und Kostenzählung gemeinsam mit dem PLU.
- **Zuordnung der Sektoren:** `match_sector` vergleicht zuletzt ohne Satz- und Leerzeichen (`Lot 12` ↔ `Lot-12`), nur wenn eindeutig.

### 3.8 Vergleich mit dem PLU

Je Regel des Zusatzdokuments (Art, Baukörper) gegen die PLU-Regel derselben Art der größten Zonen-Teilfläche (mit Rückfall auf `any`), Parameter für Parameter mit Richtung:

| Richtung | Parameter (Auswahl) | strenger, wenn … |
|---|---|---|
| Höchstwert | `ratio` (Grundfläche), `ridge_m`, `eave_m`, `parapet_m`, `max_m`, `sdp_m2`, `footprint_m2`, `max_height_m`, `max_footprint_m2`, `pitch_max_deg`, `on_boundary_max_height_m` | kleiner |
| Mindestwert | `min_m`, `height_factor`, `ratio`/`full_soil_ratio` (Freifläche), `spaces_*`, `trees_per_m2`, `min_green_ratio`, `pitch_min_deg` | größer |
| Erlaubnis | `allow_on_boundary` | `false` |
| Erlaubte Menge | `allowed_forms`, `materials_allowed`, `color_families_allowed`, `materials` | echte Teilmenge |
| Verbotene Menge | `materials_forbidden` | echte Obermenge |
| Geschosse | `storeys` | weniger Geschosse |
| genau | `mode`, `band`, `measured_from`, `height_basis`, `reference`, … | – (verschieden → `different`) |

Ein Parameter nur im Zusatzdokument schränkt zusätzlich ein (strenger); einer nur im PLU gilt weiter (neutral). Ergebnis je Regel: `stricter`, `looser` (der PLU bindet), `equal`, `mixed`, `different`, `only_supplement` (der PLU hat keinen ermittelten Wert dieser Art – das Zusatzdokument schränkt zusätzlich ein), `no_own_rule` (Zusatzdokument „nicht geregelt“ – der PLU gilt, **nicht** Abstand 0), `unknown` (Regel des Zusatzdokuments nicht belegt). Hinweise (`text_only`) erscheinen als Liste. Die Analyse meldet `supplement_stricter` mit den Arten, die sie betreffen (Grundfläche, Höchstflächen, Höhe, Abstände) – **in ihren Werten nicht verrechnet** (E-AN3-2).

### 3.9 API, Zugriff, Produktschnitt

- Neues Modul `backend/app/analysis/` (`domain/`, `models.py`, `schemas.py`, `service.py`, `api.py`), nur im Analyse-Produkt; `test_module_boundaries` zählt es zu den Produktmodulen (der Kern importiert es nicht).
- `GET /projects/{id}/analysis` → `AnalysisOut` (Simulation, Status wie der Baurahmen, Prüfsumme über Baurahmen-Eingaben, Annahmen und Regelstände der Zusatzdokumente; Grundfläche, Geschosse und SDP je Teilfläche und gesamt; nicht gerechnete Abzüge; Zusatzdokumente mit Regeln und Vergleich; Hinweise).
- `PUT /projects/{id}/analysis/parameters`, `DELETE …/parameters` (zurück auf Vorgaben).
- Zugriff überall `require_owned_project` (Architekt, Projekt mit Eigentümer).
- Ohne Baurahmen (kein PLU und kein Kataster; Baurahmen `unavailable` oder `in_progress`) gibt es keine Kennzahlen, sondern Status und Grund des Baurahmens; Zusatzdokumente und ihr Vergleich erscheinen trotzdem, soweit PLU-Regeln vorliegen.
- `create_full_app` baut die Vereinigung aller Produktprofile; so bleibt `openapi.json` eine Datei (PLAN_ANALYSE 8.1 Nr. 5).

### 3.10 Oberfläche

Projektseite in der Reihenfolge Grundstück → Bebauungsplan → **Zusatzdokumente** → **Analyse** → Baurahmen → Regeln (aufklappbar). „Analyse“: drei Kennzahlen (bindende Grundfläche eng/weit mit bindendem Kandidaten, Vollgeschosse mit Quelle, SDP-Spanne mit Obergrenze), darunter die Kandidaten mit Seite, „Abstände je Grenze“ im Klartext, „nicht gerechnet“, Annahmen zum Aufklappen und Ändern, Hinweis auf strengere Zusatzdokumente. „Zusatzdokumente“: Liste, Hochladen (Datei, Titel, Art), Lot und „Auswerten“, Stand mit Kosten, Vergleichstabelle (Regel · PLU · Zusatzdokument mit Seite · Einordnung).

## 4. Arbeitsschritte

1. `rules/domain/kinds.py`: `max_area`; Prompt `g2-prompt-4` mit `max_area`; Prompt für Zusatzdokumente, Fingerabdruck je Art (`extraction.py`); `ExtractionRequest.document_kind` (`integrations/claude.py`); `extract.py` ohne `complete` für Zusatzdokumente; `match_sector` mit Rückfall.
2. Migration `0014`: Rolle `supplement`, Tabelle `analysis_parameters`.
3. `rules/documents.py`: Upload nach Kategorie, Lesen mit Kapitel `DOC`, `choose_lot`, Grenzen; `rules/service.py`: Regeln der Zusatzdokumente (`supplement_rules`); Endpunkt in `rules/api.py`.
4. `analysis/domain`: `parameters`, `footprint`, `storeys`, `floor_area`, `compare`, `analyse` (rein, mit Einheitstests).
5. `analysis/service.py`, `api.py`, `products.py`, `main.create_full_app`; `openapi.json`, `schema.d.ts`.
6. Frontend: `api/analysis.ts`, `products/analyse/Analyse.tsx`, `Zusatzdokumente.tsx`, `abstand.ts`; `Bebauungsplan`/`ProjektSeite` nach Rolle; Regelart `max_area` in `rules/format.ts`, `envelope/format.ts`, Übersetzungen de/fr (Frontend und Backend).
7. Tests: Einheit (Domäne, Regelart, Prompt, Zuordnung), Integration (Zusatzdokument von Upload bis Vergleich, Annahmen, Zugriff, Profile), Komponenten (Analyse, Zusatzdokumente, Abstandstexte).
8. Dokumente: ANNAHMEN (Abschnitt AN3), BETRIEB 15, PLAN_ANALYSE (AN3, AN4), README, AGENTS.

## 5. Abnahme

1. Testparzelle 20 × 30 m mit Zone Uh (aufgezeichnete Auswertung): bindende Grundfläche 150/150 m² (`ratio`), Kandidaten 300/210 m² (`contour`), R+1 mit möglichem Dachgeschoss, SDP 255–380 m²; mit geänderten Annahmen andere Spanne, Vorgaben wiederherstellbar.
2. `R+1+C` im Plan → 2 Vollgeschosse, Dachgeschoss 50–75 %, Quelle `storeys`; nur First → Spanne mit Hinweis; keine Höhe → SDP nicht ermittelt.
3. `max_area.sdp_m2 = 200` → SDP höchstens 200 m² mit Hinweis, dass die Obergrenze bindet.
4. Zusatzdokument (Test-PDF mit Tabelle je Lot) hochladen → Kapitel `DOC`, noch kein Job; Lot 12 wählen → ein Job; mit aufgezeichneter Antwort: `max_area` 180 m² (`only_supplement`), Firsthöhe 8 m (`stricter` gegen 10 m), Abstand „non réglementé“ (`no_own_rule`); Analyse meldet `supplement_stricter`, ihre Werte bleiben die des PLU.
5. Zweites Lot desselben Dokuments in einem anderen Projekt → dasselbe Dokument, Kapitel neu eingeplant; viertes Zusatzdokument → 422; PLU-PDF als Zusatzdokument → 409.
6. Zugriff: Kunde mit Cookie und Architekt auf Kundenprojekt → 404; Konfigurator-Profil ohne `/analysis`, Analyse-Profil ohne Katalog; `openapi.json` enthält beide.
7. Hauskonfigurator unverändert; alle bisherigen Tests grün, Grenz-Test hält.
8. Browser (Analyse-Stack, de/fr, Telefonbreite): Analyse mit Werten und Annahmen; Zusatzdokument bis zum Vergleich.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN3-1 | Annahmen je Anfrage oder je Projekt? | **Je Projekt gespeichert.** Der Bericht (AN5) muss nennen, womit gerechnet wurde; im Browser gespeicherte Werte gingen auf einem zweiten Gerät verloren |
| E-AN3-2 | Zusatzdokumente in die Analysewerte einrechnen („das Strengere bindet“)? | **Nein, nur vergleichen und melden.** Ob ein règlement de lotissement nach zehn Jahren noch gilt (L.442-9) und wie weit ein cahier des charges als Privatrecht bindet, entscheidet der Architekt; entspricht der Wahl vom 25.09.2026. Mit AN4 übernimmt er einzelne Werte mit Zitat als Projektkorrektur, dann wirken sie auch in Baurahmen und Analyse |
| E-AN3-3 | `max_area` auch im PLU-Prompt? | **Ja.** Ein Schema für beide Prompts; absolute Obergrenzen kommen auch in PLU vor. Die Neuauswertung kostet jetzt nichts extra (bisher keine echte Auswertung) |
| E-AN3-4 | Lot als Sektor eines Kapitels oder ein Kapitel je Lot? | **Sektor.** Ein Dokument, ein Kapitel; ein neues Lot wertet das Kapitel neu aus (Kosten wie E-AN2-2), Tabellen je Lot liest das Modell in einem Durchgang |
| E-AN3-5 | Nur mögliches Dachgeschoss (aus Höhen abgeleitet) am unteren Ende mitzählen? | **Nein.** Unten steht, was der Plan sicher trägt; oben das Mögliche |
| E-AN3-6 | Wie viele Zusatzdokumente je Projekt? | **Drei** (lotissement, cahier des charges, ein Änderungsstand); mehr deutet auf falsch zugeordnete Dateien |
| E-AN3-7 | Gabarit und Schnitt jetzt? | **Nein, RA2** wie geplant; die Analyse braucht sie für die drei Zahlen nicht |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | `openapi.json` entsteht aus dem Profil `configurator`; Routen nur des Analyse-Produkts fehlten | keine Typen im Frontend, CI-Schritt `api:types` ohne Wirkung | 3.9: volles Profil = Vereinigung |
| 2 | Geschosse aus `heights.from_rule` abgeleitet | `R+1+C` würde über 3,00 m in eine Traufe umgerechnet und wieder zurück; Quelle falsch benannt, bei anderer Geschosshöhe andere Zahl | 3.2: Parameter der Regel |
| 3 | Lotnummern als Sektor („12“) | `foreign_sector` hält jede 12 im Zitat für eine Nennung des Sektors → `sector_mismatch` bei zwei Lots | 3.7: `Lot-12`, Rückfall in `match_sector` |
| 4 | `complete` ergänzt fehlende Pflichtarten | jedes Zusatzdokument hätte acht `unknown`-Regeln → Vergleich voller „nicht ermittelt“ | 3.7: ohne Pflichtarten |
| 5 | „non réglementé“ im Zusatzdokument wie im PLU als Abstand 0 m gelesen | Vergleich meldete „weniger streng“, obwohl der PLU weiter gilt | 3.8: `no_own_rule` |
| 6 | Dasselbe PDF einmal als PLU, einmal als Zusatzdokument | Auswertung mit falschem Prompt, Regeln eines PLU als Lotregeln | 3.7: `409 document_type_conflict` |
| 7 | Kapitel `DOC` über das ganze Dokument | über 150 Seiten scheitert jede Auswertung | 3.7: Seitenbereich beim Lot |
| 8 | `ProjektSeite`/`Bebauungsplan` nehmen den ersten Eintrag als PLU | mit Zusatzdokumenten falsches Dokument, Ergebnis auch ohne gewählte PLU-Zone | 3.10, Schritt 6 |
| 9 | SDP oben mit weitester Kontur auf allen Geschossen | Bauen auf der Grenze ist oft nur bis zu einer Höhe erlaubt, obere Geschosse brauchen dann Abstand – die Spanne ist oben zu hoch | 3.3: als nicht gerechnet benannt; Gabarit (RA2) löst es |
| 10 | Grundflächenzahl nicht ermittelt | Minimum nur aus der Kontur wäre eine Scheinzahl | 3.1: Obergrenze, `complete: false` |
| 11 | `max_footprint_ratio` um `max_m2` erweitern lag nahe | H2/H3 setzen `ratio` voraus; `derive._part` schlösse die Teilfläche als `footprint_zero` aus | 3.6: eigene Art |
| 12 | Rückfalltext von `notice.rules_upload` sagt „Zusatzdokumente … nicht berücksichtigt“ | stünde über einer Seite, die sie vergleicht | Text: Zusatzdokumente nur im Vergleich der Analyse, nicht in Regeln und Baurahmen |
| 13 | Dachgeschoss bei einer Spanne von Geschossen mit `n` geprüft | oben ein Dachgeschoss über `n_max` Geschossen, das dort keinen Platz hat | 3.2: Prüfung mit `n_max` und `h_min` |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Zusatzdokumente sofort verrechnen („mit Zusatzdokument“ als zweite Zeile) | Geltung ist eine Rechtsfrage des Einzelfalls; Entscheidung des Nutzers | AN4 die Übernahme je Wert bringt – dann über Projektkorrekturen |
| Übernahme per Klick als `project_rule_override` schon jetzt | Korrekturen tragen kein Zitat (Seite, Quelle) – L3 verlangt Herkunft an jedem Wert | AN4 die Korrektur um die Quelle erweitert |
| Abstandsaussage im Backend als Text | Alle Daten stehen im Baurahmen; Texte gehören zu den Übersetzungen der Oberfläche | ein Bericht (AN5) dieselben Sätze braucht – dann dort über Übersetzungsschlüssel |
| Annahmen nur im Browser | zweites Gerät, Bericht | nie |
| SDP aus einem Grundriss | kein Grundriss im Analyse-Produkt | X3 (Modelle) |
| Kapitel je Lot | Kosten fallen ohnehin je neuem Lot an; eine Tabelle je Lot liest sich in einem Durchgang besser | Dokumente mit Hunderten Seiten je Lot |

### 7.3 Bewusste Grenzen

Die SDP ist eine Spanne aus Grundfläche und Geschossen, kein Aufmaß. Keine Verrechnung der Zusatzdokumente, kein Gabarit, kein Schnitt. Tabellen je Lot als Bild (gescannt) sind nicht lesbar (RW03). Mehrzonen-Grundstücke vergleichen Zusatzdokumente gegen die größte Zone.

### 7.4 Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Der Idempotenzschlüssel des Auswertungsauftrags (`plan_import.enqueue_extraction`) rechnete die Eingabe mit dem Prompt des PLU | Eine Änderung am Prompt der Zusatzdokumente hätte keinen neuen Auftrag ausgelöst | Dokumentart durch `ensure_chapter` bis in `input_hash` gereicht (EA08) |
| 2 | Die Zonenwahl nahm jedes Dokument des Projekts an | Auf einem Zusatzdokument entstünde ein Zonenkapitel neben `DOC` | `409 not_a_plu`, spiegelbildlich `409 not_a_supplement` (EA07) |
| 3 | `round` rundet 379,5 zur geraden Zahl, und 150 × 2,75 × (1 − 0,08) ergibt im Gleitkomma 379,49999… | Die Spanne des Beispiels endete je nach Rechenweg bei 379 oder 380 | `round_m2`: auf sechs Stellen runden, dann halbe aufrunden (EA05) |
| 4 | Die Oberfläche lud Regeln und Baurahmen nur neu, wenn sich der Stand des **ersten** Dokuments änderte | Ein fertig ausgewertetes Zusatzdokument erschiene erst nach Neuladen im Vergleich | `useRefreshWhenStateChanges` über alle Dokumente, dazu die Analyse |
| 5 | `ruleValue` kannte `max_area` nicht, Steckbrief und Büro-Korrektur ebenso | leere Werte in Regelliste und Steckbrief, Art in der Korrektur nicht wählbar | Formatierung, Reihenfolge, Übersetzungen (Frontend und Backend), Liste der Korrekturarten |
| 6 | Die Startseite des Analyse-Produkts kündigte die Nutzfläche als „folgt“ an und nannte das PDF als Parzellenformat nicht (seit AN1 falsch) | Falsche Aussage gegenüber dem Büro | Texte in de/fr |

**Prüflauf:** Backend 588 Tests (vorher 541; neu `tests/unit/test_analysis_domain.py` mit 34 und `tests/integration/test_analysis.py` mit 9 Tests, dazu Einheitstests für `max_area`, den Zusatz-Prompt, die Zuordnung der Lots und den Produktschnitt), Frontend 172 (vorher 157; neu `abstand.test.ts`, `zusatzdokumente.test.tsx`, `analyse-kennzahlen.test.tsx`), dazu ruff, Format, mypy, Typprüfung, Lint und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt. Beide lokalen Stacks laufen auf Migration **0014**.

**Browserprüfung am 26.09.2026** (Analyse-Stack, Französisch und Deutsch, Telefonbreite ohne waagerechtes Verschieben der Seite): Testprojekt „Testparzelle Zone Uh“ → Analyse: 150 m² (Grundflächenzahl bindet; Kontur 210/300 m²), „2 + combles possibles“ aus der Traufhöhe, SDP 255–380 m², Abstände je Grenze im Klartext mit Seite. Außenwandabzug unten 10 % → 255–371 m², „modifiées“; Vorgaben wiederhergestellt → 255–380 m². Zusatzdokument (3 Seiten) hochgeladen → gelesen → Lot 12 → ohne Schlüssel „nicht eingerichtet“ → mit aufgezeichneter Antwort „analysé · 2 appels · 0,16 $“, Vergleich: Surfaces maximales „uniquement dans le document“, Hauteur „plus strict que le PLU“ (8 m gegen 10 m), Retrait latéral „pas de règle propre – le PLU s'applique“, Hinweis zu den Clôtures; Analyse meldet „plus strict pour : Surfaces maximales, Hauteur“, ihre Werte bleiben die des PLU. In Telefonbreite scrollt die Vergleichstabelle in ihrem Rahmen.
