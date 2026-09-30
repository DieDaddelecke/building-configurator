# AN4 – Korrigieren und begründen (Emprise Analyse)

> **Status:** geplant und umgesetzt am 28.09.2026 (Auftrag „Stelle AN4 fertig“; Befunde beim Bau in 7.4) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN4) und 5 (RA2); [PLAN_AN3_ANALYSE.md](PLAN_AN3_ANALYSE.md) 3.8, E-AN3-2, 7.2 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN4 (Präfix `KR`)
> **Voraussetzung:** AN0–AN3 (PS, UP, PU, EA). Regelarten und Schranken: `BACKEND_SPEZIFIKATION.md` 5.2.4, ANNAHMEN RW15 (Korrektur als JSON), RW19; Leitplanke L3 (Herkunft an jedem Wert).

---

## 1. Zweck und Umfang

Das Sprachmodell liest Regeln falsch oder gar nicht, und ein règlement de lotissement kann strenger sein als der PLU. Der Architekt muss beides im Projekt richtigstellen können – nachvollziehbar: mit Begründung und, wo möglich, mit Fundstelle. Heute geht das nur über die Büro-Endpunkte des Konfigurators mit einem JSON-Feld und ohne Quelle (RW15); das Analyse-Produkt hat gar keine Korrektur.

**Enthalten:**
- **Regelformular aus dem Schema:** Die Parameter jeder Regelart kommen als Formularbeschreibung aus `rules/domain/kinds.py` (eine Quelle für Prüfung, Modellausgabe und Formular); ein gemeinsames Formular ersetzt die JSON-Felder – im Analyse-Produkt und in beiden Büro-Formularen des Konfigurators.
- **Korrektur je Projekt** mit Pflichtbegründung und optionaler **Fundstelle** (Dokument, Seite, Zitat); das Zitat wird wie bei der Auswertung auf der Seite gesucht.
- **Regeln ergänzen**, die das Modell nicht gefunden hat.
- **Werte aus Zusatzdokumenten übernehmen:** aus dem Vergleich heraus, mit dem Strengeren je Parameter als Vorschlag und der Fundstelle des Zusatzdokuments; danach „übernommen“ statt „strenger“.
- **Zwei Stände vergleichen:** ohne ↔ mit den Korrekturen des Projekts, frühere ↔ aktuelle Auswertung – Kennzahlen und geänderte Regeln nebeneinander.

**Nicht enthalten:** Korrektur für die ganze Zone im Analyse-Produkt (E-AN4-8); gespeicherte Stände (E-AN4-5, mit AN5 bei Bedarf); Bericht-PDF, DXF (AN5); mehrere Fundstellen je Korrektur (E-AN4-2).

## 2. Befund

| Baustein | Stand | Folge |
|---|---|---|
| `project_rule_override` | Zone, Art, Baukörper, Status, Parameter, Notiz; keine Fundstelle; nur über `/admin/projects/{id}/rule-overrides` (Rollen `architect`, `rules_admin`, **ohne** Eigentümerprüfung) | Spalten für die Fundstelle; eigene Endpunkte mit `require_owned_project` fürs Analyse-Produkt |
| `apply_override` | ersetzt Regeln der Art (spezifischer Baukörper geht vor); Ausgabe mit `origin = project`, **Notiz als `notes`** | Die Notiz landet in der Kunden-API (`GET /projects/{id}/rules`, Baurahmen) – mit Pflichtbegründung nicht mehr tragbar (7.1 Nr. 7) |
| `supplement_rules` | ruft `_rules_for_zones` **mit** `project_id` → Korrekturen gelten auch für Zusatzdokumente, wenn der Zonencode passt | Zusatzdokumente immer ohne Korrekturen (7.1 Nr. 3) |
| Büro-Formulare | `Grundstuecke.tsx` (Projektkorrektur, Baukörper fest `main`) und `Regeln.tsx` (Zonenversion) mit JSON-Text | gemeinsames Formular |
| `kinds.py` | Pydantic-Modelle je Art, `PARAM_TYPES`, `BOUNDS`, Vokabulare | Formularbeschreibung daraus ableiten, nicht nachbauen |
| Vergleich (EA09) | gegen die **wirksamen** PLU-Regeln der größten Zone | nach einer Übernahme stünde „gleich“ – Herkunft der Gleichheit unklar (7.1 Nr. 2) |
| Regelwerksversionen | unveränderlich, alte als `retired` erhalten (L4) | frühere Auswertung ist ohne neue Datenhaltung vergleichbar |

## 3. Fachliche Festlegungen

### 3.1 Formularbeschreibung

`GET /admin/rule-kinds` (Rollen wie das Lesen der Regeln) liefert je Regelart: `kind`, `building_specific` (aus `BUILDING_SPECIFIC_KINDS`), `mandatory`, und je Parameter `name`, `type` (`number`, `flag`, `choice`, `items`, `text`), `required`, `default`, `options` (aus `Literal` bzw. den Vokabularen), `min`/`max` (aus `BOUNDS`) und `unit`. Abgeleitet in `rules/domain/form.py` aus den Pydantic-Modellen; ein Einheitstest hält Modelle, `PARAM_TYPES` und Formular deckungsgleich.

Einheiten sind je Parameter festgelegt, nicht aus `PERCENT_PARAMS` abgeleitet (7.1 Nr. 5):

| Einheit | Parameter | Eingabe im Formular |
|---|---|---|
| `m` | `*_m` | Meter |
| `m2` | `*_m2` | m² |
| `deg` | `pitch_*_deg` | Grad |
| `share` | `ratio`, `full_soil_ratio`, `min_green_ratio` | Prozent (gespeichert 0–1) |
| `factor` | `height_factor` | Faktor (0,5 = H/2) |
| `per_area` | `spaces_per_m2_sdp`, `trees_per_m2` | Kehrwert „1 je … m²“ (7.1 Nr. 6) |
| `count` | `spaces_per_dwelling` | Anzahl |

Die Zusammenhänge zwischen Parametern („`min_m` oder `height_factor`“) prüft weiter nur der Server (`validate_params`); seine Gründe (`min_m_or_height_factor_required`, `implausible`, …) übersetzt die Oberfläche.

### 3.2 Korrektur je Projekt

- **Schlüssel** wie bisher: Zone, Art, Baukörper. Der Zonencode muss eine Zone der aktuellen Regeln des Projekts sein (`422 zone_unknown`), sonst träfe eine Korrektur `Lot-12` das Zusatzdokument (7.1 Nr. 3).
- **Baukörper:** beim Korrigieren der der Regel; beim Ergänzen wählbar für baukörperbezogene Arten (Abstände, Höhe, Dach, Fassade; Vorgabe `main`), sonst `any`.
- **Status:** wirksam, nicht geregelt, nicht ermittelt (letzteres mit Grund `correction`: Der Architekt nimmt einen falsch gelesenen Wert aus der Rechnung).
- **Begründung** Pflicht (3–2000 Zeichen), **nur für das Büro sichtbar**: Sie erscheint in der Liste der Korrekturen, nicht mehr in `RuleOut.notes` (7.1 Nr. 7).
- **Fundstelle** (optional): Dokument (das PLU des Projekts, eines seiner Zusatzdokumente oder – im Konfigurator – der Planstand der Regeln), Seite (1 bis Seitenzahl), Zitat (optional, bis 4000 Zeichen). Das Zitat wird mit `verify_quote` auf der Seite und den Nachbarseiten gesucht; gefunden → `quote_verified`, die Seite wird berichtigt; nicht gefunden → gespeichert, im Baurahmen mit `*` wie ein unbestätigtes Zitat. Ohne Dokument keine Seite (`422 source_invalid`).
- **Vorschlag beim Korrigieren einer gelesenen Regel:** Dokument, Seite und Zitat der Auswertung; sonst verlöre der unveränderte Teil der Regel seine Herkunft (7.1 Nr. 8).
- **Anzeige:** Regeln und Baurahmen zeigen die Seite als Verweis und dahinter „Korrektur“; ohne Fundstelle wie bisher „Büro, nur dieses Projekt“. Herkunft bleibt `project` (E-AN4-7).
- **Wechsel von Zone oder PLU:** Korrekturen hängen am Zonencode. Eine Korrektur einer Zone, die das Projekt nicht mehr hat, wirkt nicht und steht in der Liste als „nicht wirksam“; eine Fundstelle in einem Dokument, das nicht mehr am Projekt hängt, wird so gekennzeichnet.
- **Audit** wie bisher (`project_rule_override.put`/`.delete`), mit Fundstelle.

### 3.3 Regeln ergänzen

„Nicht ermittelt“ gelesene Pflichtarten stehen schon als Zeile in der Regelliste und werden dort korrigiert. Arten ohne Zeile (Stellplätze, Nebengebäude, Höchstflächen, Bepflanzung, Einfriedung, Abstand zwischen Gebäuden) ergänzt „Regel ergänzen“ mit Wahl der Art. Ergänzte Regeln wirken wie gelesene: `max_area` in der Analyse, Abstände im Baurahmen, die übrigen in Liste und Steckbrief.

### 3.4 Übernahme aus einem Zusatzdokument

Aus dem Vergleich (EA09) bei den Ergebnissen `stricter`, `mixed`, `different` und `only_supplement`: „Übernehmen“ öffnet das Regelformular für die verglichene PLU-Zone mit

- **Parametern:** dem Strengeren je Parameter (`merge_stricter`): Ausgangspunkt die wirksame PLU-Regel, darüber jeder Parameter des Zusatzdokuments – Höchstwert das Minimum, Mindestwert das Maximum, erlaubte Mengen die Schnittmenge (leer → Wert des Zusatzdokuments), verbotene Mengen die Vereinigung, Erlaubnis nur, wenn beide sie geben, Geschosse die kleinere Zahl, Stufen (`flat_roof`, `ridge_orientation`) die strengere, Parameter ohne Richtung der Wert des Zusatzdokuments. Parameter nur im PLU bleiben. Ergibt das keine gültige Regel, die Parameter des Zusatzdokuments. Beispiel: PLU Traufe 7 m, First 10 m; Lotissement First 8 m → **Traufe 7 m, First 8 m**, nicht nur First 8 m (7.1 Nr. 1).
- **Fundstelle:** Dokument, Seite und Zitat der Regel des Zusatzdokuments (dort schon geprüft).
- **Begründung:** leer, Pflicht – ob das Zusatzdokument gilt (L.442-9, Privatrecht des cahier des charges), entscheidet der Architekt (E-AN3-2).

Der Vorschlag kommt vom Server mit dem Vergleich (`RuleComparisonOut.proposal`), weil dort die Richtungen je Parameter stehen.

**Danach:** Der Vergleich rechnet weiter gegen die wirksamen Regeln. Stammt die wirksame Regel aus einer Korrektur mit Fundstelle in **diesem** Zusatzdokument, heißt das Ergebnis `adopted` („übernommen“) statt `equal`; `supplement_stricter` zählt es nicht mehr. Dafür trägt die Herkunft eines Werts (`Citation`, `RuleOut`) die Kennung des Dokuments.

### 3.5 Zwei Stände vergleichen

Ein **Stand** ist gerechnet, nicht gespeichert: Regelwerksversion je Zone und mit oder ohne Korrekturen des Projekts. Zwei feste Gegenüberstellungen (E-AN4-5):

| Vergleich | links | rechts | angeboten, wenn … |
|---|---|---|---|
| **Korrekturen** | aktuelle Auswertung ohne Korrekturen | aktuelle Auswertung mit Korrekturen (Arbeitsstand) | das Projekt wirksame Korrekturen hat |
| **Auswertungen** | frühere Version ohne Korrekturen | aktuelle Version ohne Korrekturen | eine Zone mehr als eine Version hat |

Der Versionsvergleich rechnet beide Seiten **ohne** Korrekturen, weil diese sonst genau die Änderungen der Auswertung überdeckten, die der Architekt sehen will (7.1 Nr. 5).

`GET /projects/{id}/analysis/comparison?base=automatic` bzw. `?base=<Versions-ID>` liefert: beide Stände (Beschreibung, Status), angebotene Vergleiche, **Kennzahlen** (bindende Grundfläche weit/eng, Konturfläche weit/eng, Vollgeschosse von–bis, Nutzfläche von–bis, Höchsthöhe des Gabarits) je Seite und **Regeln** je Zone, Art und Baukörper mit beiden Werten und `changed`. Eine frühere Version bekommt für die Rechnung den Status ihrer Herkunft (`simulated`/`office_reviewed`), nicht `retired` (7.1 Nr. 4). Eine Version, die nicht zu einer Zone des Projekts gehört → `404 version_not_found`.

### 3.6 API und Zugriff

- `GET /admin/rule-kinds` – Formularbeschreibung (3.1).
- `GET`, `PUT /projects/{id}/rule-overrides`, `DELETE …/{override_id}` – Korrekturen im Analyse-Produkt, `require_owned_project`; dieselben Funktionen wie die Büro-Endpunkte, die ebenfalls die Fundstelle annehmen.
- `ProjectOverrideIn.source` (`document_id`, `page`, `quote`), `ProjectOverrideOut.source` (dazu Titel, `quote_verified`, `source_url`, `attached`), `RuleOut.source_document_id`, `RuleComparisonOut.proposal`, Ergebnis `adopted`.
- `GET /projects/{id}/analysis/comparison` (3.5).
- Migration **0015**: `project_rule_override.source_file_id` (→ `source_file`, `ON DELETE SET NULL`), `page`, `quote`, `quote_verified`.
- `ENGINE_VERSION` der Analyse → `an4-1.0.0` (neues Ergebnis `adopted`, Vorschläge).

### 3.7 Oberfläche

- **Analyse-Produkt:** neuer Abschnitt **„Regeln und Korrekturen“** nach den Zusatzdokumenten statt der zugeklappten Regeln am Ende (E-AN4-6): die Regelliste mit „Korrigieren“ je Zeile, bei Korrekturen „Ändern“ und „Zurücknehmen“ und die Begründung unter dem Wert; „Regel ergänzen“; Liste nicht wirksamer Korrekturen; darunter **„Stände vergleichen“** mit Auswahl und Tabelle (Kennzahl · links · rechts, Unterschiede hervorgehoben; geänderte Regeln).
- **Zusatzdokumente:** „Übernehmen“ in der Vergleichstabelle öffnet das Formular mit dem Vorschlag; Ergebnis „übernommen“.
- **Regelformular** (`src/rules/RegelFormular.tsx`, gemeinsam): Art, Baukörper, Status, Felder aus der Beschreibung (Zahlen mit Komma, Prozent, Kehrwert, Auswahl, Mehrfachauswahl als Kästchen, Text), Fundstelle (Dokument, Seite, Zitat), Begründung. `RegelFelder` allein für die Zonenversion im Büro.
- **Konfigurator (Büro):** Projektkorrektur und Zonenversion ohne JSON (RW15 erledigt).

## 4. Arbeitsschritte

1. `rules/domain/form.py` (Formularbeschreibung), Endpunkt, Einheitstest gegen `kinds.py`.
2. Migration 0015, Modell; `rules/service.py`: Fundstelle prüfen und ausgeben, Zonenprüfung, Notiz nicht mehr in `RuleOut`, `resolve_rules(overrides=…, versions=…)`, Zusatzdokumente ohne Korrekturen; `rules/api.py`: Endpunkte je Projekt; Schemas.
3. `envelope/domain/inputs.Citation.document_id`, `envelope/service` reicht Optionen an `resolve_rules` weiter.
4. `analysis/domain/compare.py`: `merge_stricter`, `adopted`; `analysis/service.py`, `schemas.py`, `api.py`: Vergleich der Stände.
5. `openapi.json`, `schema.d.ts`.
6. Frontend: `api/rules.ts` (Arten, Korrekturen je Projekt), `api/analysis.ts` (Vergleich); `rules/RegelFormular.tsx`, `rules/felder.ts` (Umrechnung); `RegelnSimulation` mit Aktion je Zeile; `products/analyse/RegelnKorrekturen.tsx`, `StaendeVergleich.tsx`; Übernahme in `Zusatzdokumente.tsx`; Büro-Formulare umstellen; Quelle „Korrektur“ in Regeln und Baurahmen; Übersetzungen de/fr.
7. Tests: Einheit (Formular, Zusammenführen, `adopted`), Integration (Korrektur mit Fundstelle, Zitatprüfung, Zugriff, Zonenprüfung, Übernahme bis zur Analyse, Stände, Kunden-API ohne Begründung), Komponenten (Formular, Korrekturen, Stände, Übernahme, Büro).
8. Dokumente: ANNAHMEN (Abschnitt AN4, RW15), BETRIEB 15, PLAN_ANALYSE, AGENTS, UMSETZUNGSPLAN D18.

## 5. Abnahme

1. Formularbeschreibung: alle 15 Arten; `max_footprint_ratio.ratio` Pflicht, Einheit `share`, 0–1; `setback_street.mode` Auswahl mit Vorgabe `min`; `roof.allowed_forms` Mehrfachauswahl der Dachformen; jeder Parameter der Modelle kommt vor.
2. Testparzelle Zone Uh: Grundflächenzahl 25 % → 20 % mit Begründung und Seite des Reglements (Zitat gefunden) → bindende Grundfläche 120/120 m², Nutzfläche 204–304 m²; Baurahmen zeigt die Seite mit „Korrektur“; Vergleich „Korrekturen“: 150 → 120 m², 255–380 → 204–304 m², eine geänderte Regel. Zurücknehmen → wieder 150 m².
3. Ergänzen: Stellplätze 2 je Wohnung → Regel mit Herkunft Projekt; Zonencode eines Lots → 422; fremdes Projekt, Kunde → 404; unbekanntes Dokument, Seite über der Seitenzahl → 422; ungültige Parameter → 422 mit Grund.
4. Zusatzdokument Lot 12 (aufgezeichnete Antwort wie AN3): Vorschlag für die Höhe = Traufe 7 m, First 8 m; nach der Übernahme `adopted`, Gabarit bis 8 m; Höchstflächen übernehmen → Grundfläche 120 m² (`absolute`), Nutzfläche 180 m² (Obergrenze); `supplement_stricter` leer.
5. Zweite Version des Regelwerks (im Test eine Büro-Version mit GRZ 30 %; eine zweite aufgezeichnete Modellantwort mit 30 % scheiterte an der Zitatprüfung, weil das Zitat „25 %“ nennt) → Vergleich „Auswertungen“ Version 1 ↔ 2: 25 % → 30 %, 150 → 180 m², sonst keine geänderte Regel.
6. Kunden-API (`GET /projects/{id}/rules`, Baurahmen) enthält keine Begründung einer Büro-Korrektur.
7. Hauskonfigurator: Büro korrigiert ohne JSON; alle bisherigen Tests grün, Grenz-Test hält.
8. Browser (Analyse-Stack, de/fr, Telefonbreite ohne waagerechtes Verschieben der Seite): korrigieren, ergänzen, übernehmen, vergleichen, zurücknehmen.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN4-1 | Formularbeschreibung vom Server oder im Frontend nachgebaut? | **Server**, aus den Pydantic-Modellen: eine Quelle, ein Test hält sie gleich; eine neue Regelart erscheint ohne Frontend-Arbeit im Formular |
| E-AN4-2 | Eine oder mehrere Fundstellen je Korrektur? | **Eine** (Dokument, Seite, Zitat). Bei einer Übernahme bleiben die Parameter nur des PLU unverändert; ihre Seite steht weiter im Vergleich „Korrekturen“ (links) |
| E-AN4-3 | Übernahme: Regel des Zusatzdokuments unverändert oder das Strengere je Parameter? | **Das Strengere je Parameter** als Vorschlag im Formular – sonst lockert die Übernahme Werte, die nur im PLU stehen (7.1 Nr. 1). Der Architekt kann ändern |
| E-AN4-4 | Vergleich nach der Übernahme gegen die gelesenen oder die wirksamen PLU-Werte? | **Wirksame** (wie EA09) mit Ergebnis `adopted`; der Vorher-Wert steht im Vergleich der Stände |
| E-AN4-5 | Stände gespeichert oder gerechnet? | **Gerechnet**, zwei feste Gegenüberstellungen. Regelwerksversionen sind unveränderlich, Korrekturen abschaltbar – ein gespeicherter Stand brächte nur Dubletten. Festgehaltene Stände erst mit der Projektakte (AN5), falls der Bericht sie braucht |
| E-AN4-6 | Wo stehen Regeln und Korrekturen im Analyse-Produkt? | **Eigener Abschnitt nach den Zusatzdokumenten**, offen: Die Regeln sind die Eingabe aller Ergebnisse darunter; zugeklappt am Ende fänden sich Korrekturen nicht |
| E-AN4-7 | Herkunft `architect` (PLAN_ANALYSE) als neuer Wert? | **Nein, `project` bleibt.** Die Tabelle unterscheidet Zone (Büro) und Projekt, nicht Rollen; im Analyse-Produkt ist der Architekt das Büro. Autor und Zeit stehen an der Korrektur |
| E-AN4-8 | Korrektur für die ganze Zone (neue Regelwerksversion) im Analyse-Produkt? | **Nein.** Dasselbe PDF ist dasselbe Dokument für alle Projekte des Büros (PU01) – eine Zonenkorrektur änderte still andere Projekte. Bei Bedarf später als eigene Aktion mit Hinweis |
| E-AN4-9 | Büro-Formulare des Konfigurators mit umstellen? | **Ja** (RW15): dieselbe Komponente, kleiner Aufwand |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Übernahme der Regel des Zusatzdokuments „wie gelesen“ | Die Korrektur ersetzt die ganze PLU-Regel: Lotissement „First 8 m“ ließe die Traufe 7 m des PLU fallen – die Übernahme des strengeren Werts machte die Analyse lockerer | 3.4: `merge_stricter` je Parameter, E-AN4-3 |
| 2 | Vergleich nach Übernahme gegen die wirksamen Werte | „gleich“ und die Warnung verschwindet, ohne dass sichtbar ist, warum | 3.4: Ergebnis `adopted` über die Kennung des Dokuments |
| 3 | `supplement_rules` wendet Korrekturen des Projekts an; die Büro-Endpunkte prüfen den Zonencode nicht | Eine Korrektur mit Zonencode `Lot-12` veränderte das Zusatzdokument und damit den Vergleich | 3.2: Zonenprüfung; Zusatzdokumente ohne Korrekturen |
| 4 | Frühere Version in `_rules_for_zones` hätte den Status `retired` | nicht in `ZoneStatus`: Fehler in der Ausgabe, Zone „nicht verfügbar“ | 3.5: Status aus der Herkunft der Version |
| 5 | Versionsvergleich mit Korrekturen auf beiden Seiten | Genau die korrigierten Arten zeigten keine Änderung der Auswertung – etwa, ob die neue Auswertung die eigene Korrektur überflüssig macht | 3.5: beide Seiten ohne Korrekturen |
| 6 | Anteile aus `PERCENT_PARAMS` als Prozent eingeben | `height_factor` steht dort (der Text darf Prozent nennen), ist aber ein Faktor (H/2 = 0,5) – als „50 %“ missverständlich | 3.1: Einheit je Parameter festgelegt |
| 7 | Dichten `spaces_per_m2_sdp`, `trees_per_m2` direkt eingeben | 0,02 statt „1 je 50 m²“ – fehleranfällig | 3.1: Kehrwert |
| 8 | Die Notiz der Korrektur steht in `RuleOut.notes` | Mit Pflichtbegründung gelangten interne Begründungen in die Kunden-API (Regeln, Baurahmen) des Konfigurators | 3.2: Begründung nur in der Liste der Korrekturen |
| 9 | Beim Korrigieren einer gelesenen Regel ohne Fundstelle | Der unveränderte Teil der Regel verlöre seine Seite (L3) | 3.2: Fundstelle der Auswertung als Vorschlag |
| 10 | Leere Liste bei erlaubten Mengen heißt „keine Einschränkung“ | Die Schnittmenge mit einer leeren PLU-Liste ergäbe „nichts erlaubt“ | 3.4: Schnittmenge nur, wenn beide Seiten eine Liste haben; leere Schnittmenge = Widerspruch → Wert des Zusatzdokuments |
| 11 | Zone oder PLU wechseln | Korrekturen der alten Zone wirkten still nicht mehr; eine Korrektur mit gleichem Zonencode in einem neuen PLU wirkte still weiter | 3.2: Liste zeigt „nicht wirksam“ und Fundstellen außerhalb des Projekts; Grenze in 7.3 |
| 12 | Kurze Zitate („3 m“) | `verify_quote` verlangt eine Mindestlänge und meldet sie als nicht gefunden | gewollt: kurze Zitate belegen nichts; Hinweis im Formular |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Formular aus `openapi.json` (JSON-Schema der Parameter) | Das Frontend bräuchte einen JSON-Schema-Interpreter; Einheiten, Vokabulare und Grenzen stünden trotzdem nicht darin | ein generischer Formulargenerator ohnehin käme |
| Gespeicherte Stände („Stand festhalten“) | Dubletten unveränderlicher Daten; die zwei nützlichen Vergleiche sind rechenbar | der Bericht (AN5) einen Stand mit Datum festhalten muss |
| Frei wählbare Stände links und rechts | vier Kombinationen je Version, wenig Nutzen über die zwei festen Vergleiche hinaus | Architekten viele Versionen haben (mehrere Neuauswertungen) |
| Zusatzdokumente in die Regeln einrechnen (Strengeres automatisch) | Geltung ist Rechtsfrage des Einzelfalls (E-AN3-2) | nie ohne Entscheidung des Architekten |
| Neue Herkunft `architect` | eine Unterscheidung ohne fachliche Wirkung; alle Anzeigen, H2/H3 und V kennen `project` | fremde Büros (AN6) Korrekturen je Person unterscheiden müssen |

### 7.3 Bewusste Grenzen

Eine Fundstelle je Korrektur; bei einer Übernahme tragen die unveränderten PLU-Parameter die Seite des Zusatzdokuments. Korrekturen hängen am Zonencode, nicht am Dokument: Ein neues PLU mit gleichem Zonencode erbt sie (sichtbar an der Fundstelle im alten Dokument). Stände werden gerechnet, nicht festgehalten. Keine Zonenkorrektur im Analyse-Produkt.

### 7.4 Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Eine Büro-Version kennt keinen Grund für „nicht ermittelt“ (`RuleIn` ohne `reason`), die Auswertung schon (`missing`) | Der Versionsvergleich meldete drei Regeln als geändert, die links und rechts gleich „nicht ermittelt“ lesen | `_reason` in `analysis/service.py`: ohne Grund gilt `missing`, wie in der Oberfläche |
| 2 | Das Zahlenfeld „Anteil“ trug `required`; die Prüfung des Browsers verhinderte das Absenden | Die eigenen Meldungen („Pflichtangabe“, Grenzen) erschienen nie | `noValidate` am Formular; Pflicht und Grenzen prüft das Formular selbst |
| 3 | Die unsichtbare Spaltenüberschrift „Aktion“ (`sr-only`) in den verschiebbaren Tabellen von Regeln und Zusatzdokumenten | In Telefonbreite war die Projektseite 122 px zu breit (Stolperstelle aus AN3, README) | `relative` an den Tabellenrahmen von `RegelnSimulation`, `Zusatzdokumente`, `StaendeVergleich` |
| 4 | Rückfalltext `rules.notices.upload`: Zusatzdokumente „nur im Vergleich, nicht in Regeln und Baurahmen“ | Nach einer Übernahme falsch | Text de/fr, EA12 |
| 5 | Nach einer Übernahme zeigt die Spalte „Bebauungsplan“ im Vergleich der Zusatzdokumente den wirksamen Wert mit der Seite des Zusatzdokuments | Las sich wie eine Seite des PLU | Kennzeichen „Korrektur“ hinter der Seite |
| 6 | Den ersten angebotenen Vergleich per `useEffect` vorwählen | Lint-Regel `set-state-in-effect` (doppeltes Rendern) | Auswahl abgeleitet: Der Vergleich `automatic` liefert die Liste, ein zweiter Abruf nur für eine Version |
| 7 | Listenfelder und Kennzeichen in Antwortmodellen mit Standardwert (`options`, `active`) | Im Frontend-Typ optional (README, Änderungen an der API) | Ohne Standardwert |

**Prüflauf:** Backend 623 Tests mit `TEST_S3=1` (vorher 606; neu `tests/unit/test_rule_correction.py` mit 10 und `tests/integration/test_rule_correction.py` mit 7 Tests), Frontend 194 (vorher 178; neu `rules/regel-formular.test.tsx` mit 7, `products/analyse/regeln-korrekturen.test.tsx` mit 5, `pages/buero/buero-korrektur.test.tsx` mit 2 Tests, dazu 2 in `zusatzdokumente.test.tsx`), ruff, Format, mypy, Typprüfung, Lint und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt (Konfigurator 99, Analyse 63 Operationen). Die Formularbeschreibung liegt als Testdatei `frontend/src/rules/__fixtures__/rule-kinds.json` vor, erzeugt aus `rule_kind_forms()` – nach einer Änderung an `kinds.py` neu erzeugen (README).

**Browserprüfung am 28.09.2026** (Analyse-Stack mit neu gebauten Images und Migration 0015, Deutsch und Französisch, Telefonbreite): Testprojekt „Testparzelle Zone Uh“ → „Regeln und Korrekturen“ mit „Korrigieren“ je Zeile; Grundfläche korrigiert: Formular mit Dokument, Seite 11 und Zitat der Auswertung vorbelegt, 25 → 20 %, Begründung → Regel „≤ 20 %“, „S. 11 · Korrektur“ (Zitat bestätigt), Begründung darunter, „Ändern“/„Zurücknehmen“; Analyse 120 m² und 204–304 m², Herkunft „p. 11 · correction“. „Stände vergleichen“: 150 → 120 m², 255–380 → 204–304 m², eine geänderte Regel. Lotissement Lot 12: „Übernehmen“ bei der Höhe → Vorschlag Traufe 7 m, First 8 m, Fundstelle S. 2 des Lotissement (Zitat bestätigt) → „übernommen“, Gabarit bis 8 m, Warnung nur noch für die Höchstflächen. „Regel ergänzen“ bietet nur fehlende Arten. In Telefonbreite nach Befund 3 ohne waagerechtes Verschieben. Laufzeit lokal (zehn Abrufe): `GET /analysis` Median 53 ms, `GET /analysis/comparison` Median 82 ms, höchstens 92 ms. Beide Testkorrekturen danach zurückgenommen (im Audit-Log sichtbar); das Projekt steht wieder auf 150 m², 10 m, 255–380 m².
