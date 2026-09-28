# AN3 (Rest) – Gabarit und Schnitt (Emprise Analyse)

> **Status:** geplant und umgesetzt am 28.09.2026 (Auftrag „beginne mit dem Modulplan für Gabarit und Schnitt – beende AN3“; Befunde beim Bau in 7.4) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN3: Gabarit, Schnitt) und 5 (RA2); [PLAN_AN3_ANALYSE.md](PLAN_AN3_ANALYSE.md) 1 („Nicht enthalten“), 3.3 und 7.1 Nr. 9 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN3 (EA13 ff.)
> **Voraussetzung:** AN3 erster Teil (EA01–EA12). Fachregeln: `BACKEND_SPEZIFIKATION.md` 5.2.4 (Regelarten `setback_*`, `max_height`), 5.3.1–5.3.2 (bebaubare Fläche als Funktion der Höhe), 5.9.4 (Höhenbezug); G3 nach ANNAHMEN BR01–BR15.

---

## 1. Zweck und Umfang

In französischen PLU hängt der Abstand zur Grenze oft von der Höhe ab („L ≥ H/2, mindestens 3 m“). Bauen auf der Grenze ist häufig nur bis zu einer Höhe erlaubt („en limite jusqu'à 3,50 m“). Der Baurahmen aus G3 zeigt deshalb zwei Konturen: die weiteste mit der Höhe 0, die engste mit der Höchsthöhe (BR01). Was dazwischen liegt, sieht der Architekt nicht: **wo er wie hoch bauen darf**. Das ist der *gabarit* – der gestufte Hüllkörper aus Konturen je Höhenstufe – und sein Schnitt quer über das Grundstück.

Der Gabarit behebt zugleich einen benannten Fehler der Nutzflächenspanne (PLAN_AN3 7.1 Nr. 9): Das obere Ende rechnet die weiteste Kontur auf **allen** Geschossen, obwohl obere Geschosse Abstand halten müssen.

**Enthalten:**
- Kontur je Höhenstufe in beiden Auslegungen (Gabarit), ausgegeben mit der Analyse.
- Nutzfläche je Geschoss aus dem Gabarit, beide Enden der Spanne.
- Zwei Schnitte (A–A quer zur Hauptstraße, B–B längs) mit Grundstücksgrenzen, Stufen des Gabarits, Abstandslinien („Abstandsdreiecke“), Trauf- und Firsthöhe und Geländelinie.
- Oberfläche „Gabarit und Schnitt“ auf der Projektseite: Lageplan mit Höhenlinien, Schnitt, Wechsel der Auslegung.

**Nicht enthalten:** DXF der Höhenstufen in 3D und Bericht-PDF (AN5, E-AN3G-5); Geländeprofil (AN5 mit der Georeferenzierung, E-AN3G-4); frei gezogene Schnittlinie (E-AN3G-3); Dachneigung als schräge Fläche im Hüllkörper (E-AN3G-7); Abstand zwischen Gebäuden (`setback_between_buildings`, ohne zweites Gebäude gegenstandslos).

## 2. Befund

| Baustein | Stand | Folge |
|---|---|---|
| `setbacks._boundary` | rechnet `max(min_m, faktor × H)`, H aus `Heights.for_basis`; weit ausgelegt immer mit H = 0 oder 0 m bei `allow_on_boundary`; **`on_boundary_max_height_m` wird nicht ausgewertet** (G3 kennt nur die Höhe 0 und die Höchsthöhe) | neue Funktion `at_height` je Stufe: Höhe der Stufe, oberhalb der Bezugshöhe gedeckelt, Grenzbebauung nur bis zur erlaubten Höhe (3.1) |
| `derive._contour` | Kontur aus Teilflächen, Kanten, Bauband und Vorgaben; privat | öffentliche `contour_at_height` im selben Modul, die `_contour` mit Abständen je Stufe aufruft – keine zweite Ableitung |
| `Heights` bei reiner Geschossangabe | `R+1+C` mit fest 3,00 m umgerechnet (Annahme `storey_height_3.00`) | Mit anderer Geschosshöhe aus den Annahmen (EA04) läge die dritte Stufe über der „Höchsthöhe“ und fiele weg → Höhen im Gabarit mit der Geschosshöhe der Annahmen neu umrechnen (`from_storeys` mit Parameter) |
| Nutzfläche (EA05) | `F × (n + s) × (1 − w)` | je Geschoss `min(F, Fläche der Stufe)` (3.4) |
| Gelände | im Analyse-Produkt immer `unavailable` (Upload und Zeichnung, UP04) | Schnitt eben mit Hinweis; Profil erst mit AN5 |
| Planbausteine `components/plan/` | `PlanSvg` (Lageplan, N oben), `MassH`, `Massstab`, `Schraffur` | Lageplan des Gabarits wie `BaurahmenPlan`; der Schnitt bekommt eine eigene Zeichenfläche (x = Lage, y = Höhe) |

## 3. Fachliche Festlegungen

### 3.1 Abstand für eine Höhenstufe

Für einen Baukörperteil, der bis zur Höhe `h` reicht, gilt je Kante und Regel:

| Regel | weiteste Auslegung | engste Auslegung |
|---|---|---|
| `setback_side`/`setback_rear`, wirksam | `0`, wenn `allow_on_boundary` und (`on_boundary_max_height_m` fehlt oder `h ≤` diese Höhe); sonst `max(min_m, faktor × H(h))` | `max(min_m, faktor × H(h))` |
| `setback_street`, `not_regulated`, `unknown`, `missing` | wie im Baurahmen | wie im Baurahmen |

`H(h) = min(h, Bezugshöhe der Regel)`, Bezugshöhe = `Heights.for_basis(height_basis)` (Traufe bei `eave`, sonst die größte Höhe). Über der Traufe wächst ein an der Traufe gemessener Abstand nicht weiter: Das Dach liegt über dem obersten Geschoss. Ohne Faktor ist der Abstand `min_m`. Kante `other` und mehrere Regeln: wie bisher über `distances` (weit das Minimum, eng das Maximum).

Kontrolle: Mit `h` = Bezugshöhe ergibt die engste Auslegung genau die engste Kontur von G3, mit `h = 0` die weiteste Auslegung genau die weiteste Kontur (auch mit Höhengrenze der Grenzbebauung, denn 0 liegt darunter). Beides wird getestet.

### 3.2 Gabarit

- **Kontur je Stufe:** `contour_at_height(data, envelope, h, reading, heights)` – dieselbe Ableitung wie der Baurahmen (Teilflächen, Bauband, Bauverbots- und Einschränkungsflächen, Splitter unter 4 m² und schmaler als 2 m entfallen), mit den Abständen aus 3.1. Teilflächen, deren Höchsthöhe unter `h` liegt, tragen nichts bei.
- **Stufen:** Die Stufe `(von, bis]` hat die Kontur bei `bis` – für die ganze Stufe die kleinste Fläche, also auf der sicheren Seite. Obergrenzen der Stufen: alle 3,00 m, dazu die kennzeichnenden Höhen: jede `on_boundary_max_height_m`, jede Traufe und die Höchsthöhe jeder Teilfläche. Aufeinanderfolgende Stufen mit gleichen Abständen werden zusammengelegt, außer an einer Traufe (Wand- und Dachbereich bleiben getrennt).
- **Höhen der Teilfläche:** Nennt der Plan Meter, gelten sie. Nennt er nur Geschosse, wird mit der **oberen** Geschosshöhe der Annahmen umgerechnet (Vorgabe 3,00 m wie in G3) und die Annahme benannt.
- **Ohne Höchsthöhe** gibt es keine Stufen: Eine Teilfläche ohne ermittelte Höhe fehlt im Gabarit (`height_unknown:<Zone>`); fehlt sie überall, ist der Gabarit `unavailable`.
- **Vollständigkeit:** Die engste Auslegung ist vollständig, wenn die engste Kontur von G3 es ist (dieselben Gründe); dazu kommt `height_unknown`.
- Keine eigene Datenhaltung: Der Gabarit wird mit der Analyse bei jedem Abruf gerechnet (wie EA11). Konturen mit gleichen Abständen werden innerhalb eines Abrufs nur einmal gerechnet.

*Beispiel* (Testgrundstück 20 × 31 m, Straße im Norden 5 m, hinten 5 m, Seiten „H/2 an der Traufe, mindestens 3 m, auf der Grenze bis 3,50 m“, Traufe 7 m, First 10 m):

| Stufe | Seitenabstand weit / eng | Fläche weit | Fläche eng |
|---|---|---|---|
| 0 – 3,50 m | 0 / 3,00 m | 20 × 21 = 420 m² | 14 × 21 = 294 m² |
| 3,50 – 6,00 m | 3,00 / 3,00 m | 294 m² | 294 m² |
| 6,00 – 7,00 m | 3,50 / 3,50 m | 13 × 21 = 273 m² | 273 m² |
| 7,00 – 10,00 m (Dach) | 3,50 / 3,50 m | 273 m² | 273 m² |

Zone Uh des Testreglements (Seiten 3 m oder auf der Grenze ohne Höhengrenze, keine Höhenabhängigkeit): zwei Stufen 0–7 m und 7–10 m mit je 300/210 m² – der Gabarit bestätigt den Baurahmen.

### 3.3 Schnitte

- **Zwei Schnitte:** **A–A** in Richtung der Innennormalen der Hauptstraßenkante (von der Straße nach hinten), **B–B** rechtwinklig dazu (von der Straße aus gesehen von links nach rechts). Ohne Hauptstraße: A–A entlang der langen Seite des kleinsten umschließenden Rechtecks. Beide gehen durch den Schwerpunkt der engsten Kontur (sonst der weitesten, sonst durch einen Punkt im Grundstück); liegt der Schwerpunkt außerhalb der Fläche (L-Form), wird ein innerer Punkt genommen.
- **Inhalt je Schnitt** (Lage `s` in Metern ab der ersten Grenze): Abschnitte des Grundstücks; Grenzübergänge mit Kante, Art und Seite des Grundstücks; je Stufe und Auslegung die Abschnitte der Kontur; Traufe, First oder Attika je Teilfläche über ihrem Abschnitt (umgerechnete Höhen gekennzeichnet); je Grenzübergang und Auslegung die **Abstandslinie** `x = d(h)` für `h` von 0 bis zur Höchsthöhe, auf die Schnittlinie umgerechnet (`s = s₀ ± x / sin θ`, θ Winkel zwischen Schnitt und Kante; unter 15° keine Linie, weil der Schnitt dort fast längs der Grenze läuft).
- **Gelände:** eben auf ±0,00 (Höhen über der Bezugshöhe der Regel). Status und Neigung stehen daneben; ein Profil kommt mit AN5 (E-AN3G-4).

### 3.4 Nutzfläche je Geschoss

Je Teilfläche und Ende der Spanne, `F` die bindende Grundfläche dieser Auslegung (EA02), `A(h)` die Fläche der Gabarit-Kontur bei `h` innerhalb der Teilfläche:

- **oben** (weiteste Auslegung, Geschosshöhe `h_min`): `[Σ_{k=1..n_max} min(F, A(k · h_min)) + s_max · min(F, A(h_D))] × (1 − w_min)`
- **unten** (engste Auslegung, `h_max`): `[Σ_{k=1..n_min} min(F, A(k · h_max)) + s_min · min(F, A(h_D))] × (1 − w_max)`
- `h_D` (oberstes Geschoss): Dachgeschoss auf der Höhe des Geschosses darunter (`n · h`), Attikageschoss eine Geschosshöhe höher (`(n + 1) · h`).
- `max_area.sdp_m2` begrenzt beide Enden wie bisher.

Das untere Ende ändert sich in zwei Fällen: wenn ein Geschoss über der Höchsthöhe läge (dann 0), und bei reiner Geschossangabe mit einer oberen Geschosshöhe über 3,00 m (dann reichen die Geschosse höher als die Umrechnung von G3, und ein höhenabhängiger Abstand wird größer). Sonst ist die engste Kontur mit der Höchsthöhe gerechnet und liegt in jeder Stufe darunter, `min(F, A)` ist dort immer `F`. Unten ≤ oben gilt immer: Die engste Auslegung liegt in jeder Stufe innerhalb der weitesten, höhere Stufen innerhalb niedrigerer, und ein oberstes Geschoss zählt unten nur, wenn der Plan es nennt – dann ist die Geschosszahl an beiden Enden gleich. Das gilt auch, wenn Geschossangabe und Höhe einander widersprechen (`storeys_exceed_eave`). Die Antwort nennt die Fläche je Geschoss und `gabarit_limits_storeys`, wenn der Gabarit das obere Ende kleiner macht als `F × (n + s) × (1 − w)`. Aus `NOT_COUNTED` entfallen `boundary_height` und `upper_setbacks`.

*Beispiel* (wie 3.2, Grundflächenzahl 60 % → 372 m²): oben n = 2, Dachgeschoss möglich (10 − 2 × 2,70 = 4,60 m) → `[min(372; 420) + min(372; 294) + 0,75 × min(372; 294)] × 0,92 = (372 + 294 + 220,5) × 0,92 = 815,6` → **816 m²** statt bisher 372 × 2,75 × 0,92 = 941 m². Unten bindet die engste Kontur von G3 (Seiten 3,50 m bei 7 m Traufe: 13 × 21 = 273 m²): `(min(273; 294) + min(273; 294)) × 0,85 = 464,1` → **464 m²**, unverändert. Zone Uh: 255–380 m², unverändert.

### 3.5 API

`AnalysisOut` bekommt:

- `gabarit`: Status, Grund, Höchsthöhe, benutzte Geschosshöhe bei reiner Geschossangabe, Hinweise, Stufen mit `from_m`, `to_m` und je Auslegung Ringe in lokalen Metern, Fläche, Vollständigkeit.
- `sections`: je Schnitt Schlüssel (`A`, `B`), Anfang und Ende in lokalen Metern, Länge, Grundstücksabschnitte, Grenzübergänge, Stufen mit Abschnitten, Höhenlinien, Abstandslinien.
- in `AnalysisFloorAreaOut`: `storeys_low`/`storeys_high` (Höhe, Fläche, Anteil je Geschoss) und `notes`.

`ENGINE_VERSION` → `an3-1.1.0` (neue Werte, neue Prüfsumme). Kein neuer Endpunkt, keine Migration.

### 3.6 Oberfläche

Neuer Abschnitt **„Gabarit und Schnitt“** zwischen „Analyse“ und „Baurahmen“ (`products/analyse/GabaritSchnitt.tsx`):
- Lageplan: Grundstück, Konturen aller Stufen als Höhenlinien mit Beschriftung (`+3,50`), Schnittlinien A–A und B–B mit Endmarken.
- Wechsel „weiteste / engste Auslegung“ nur, wenn sich die beiden unterscheiden; vorgewählt die weiteste (der Gestaltungsraum), die engste ist die sichere Seite.
- Tabelle der Stufen (von–bis, Fläche weit/eng).
- Schnitt mit Wechsel A–A/B–B: Geländelinie, Grenzen mit Art, Stufen (eng gefüllt, weit hell), Abstandslinien, Traufe/First mit Kote, Höhenmaßstab links; Hinweis zum ebenen Gelände.
- In der Herleitung der Nutzfläche die Geschossflächen („372 · 294 · DG 75 % von 294 m²“) und der Hinweis, wenn der Gabarit das obere Ende begrenzt.

## 4. Arbeitsschritte

1. `envelope/domain/setbacks.py`: `at_height`; `envelope/domain/heights.py`: `from_storeys` mit optionaler Geschosshöhe; `envelope/domain/derive.py`: `contour_at_height`. Verhalten von G3 unverändert.
2. `analysis/domain/gabarit.py`: Höhen je Teilfläche, Stufen, Zusammenlegen, Zwischenspeicher je Abstandssatz, Flächen je Teilfläche.
3. `analysis/domain/section.py`: Schnittlinien, Abschnitte, Grenzübergänge, Höhen- und Abstandslinien.
4. `analysis/domain/floor_area.py` und `analyse.py`: Geschossflächen aus dem Gabarit, `notes`; `NOT_COUNTED` gekürzt; `ENGINE_VERSION`.
5. `analysis/schemas.py`, `service.py`; `openapi.json`, `schema.d.ts`.
6. Frontend: `GabaritSchnitt.tsx` (Lageplan, Tabelle, Schnitt), Herleitung in `Analyse.tsx`, `ProjektSeite.tsx`, Übersetzungen de/fr.
7. Tests: Einheit (`at_height`, Kontrollen aus 3.1, Stufen des Beispiels, Geschossangabe mit anderer Geschosshöhe, ohne Höhe, Nutzfläche des Beispiels, unten ≤ oben, Schnitt mit Übergängen und Abstandslinie), Integration (Uh über die API), Komponenten (Gabarit, Schnitt).
8. Dokumente: ANNAHMEN (EA13 ff.), PLAN_ANALYSE (AN3 vollständig), PLAN_AN3 (Verweise), AGENTS, UMSETZUNGSPLAN D18.

## 5. Abnahme

1. Beispiel 3.2 als Einheitstest: vier Stufen mit 420/294, 294/294, 273/273, 273/273 m²; Nutzfläche 464–816 m², `gabarit_limits_storeys`.
2. `at_height` mit der Bezugshöhe ergibt die engste Kontur von G3 (Testgrundstück, Zone UB und Beispiel), mit 0 die weiteste; alle bisherigen Tests von G3, H2 und H3 grün.
3. `R+1+C` mit Geschosshöhe 3,50 m: Stufen bis 7,00/12,00 m, kein Geschoss fällt weg; ohne Höhenregel `unavailable`, die übrigen Kennzahlen wie bisher.
4. Schnitt des Beispiels: A–A von der Straße (s = 0) nach hinten, Kontur 5–26 m; B–B mit zwei seitlichen Grenzen, Stufe 0–3,50 m weit über die ganze Breite, 6–7 m 3,50–16,50 m; Abstandslinie der Seite weit (0; 0) → (0; 3,50) → (3; 3,50) → (3; 6) → (3,50; 7) → (3,50; 10).
5. API mit Zone Uh (aufgezeichnete Auswertung): Gabarit mit zwei Stufen 300/210 m², zwei Schnitte, Nutzfläche 255–380 m²; `openapi.json` aktuell.
6. Browser (Analyse-Stack, de/fr, Telefonbreite ohne waagerechtes Verschieben der Seite): Lageplan mit Höhenlinien, Wechsel der Auslegung, Schnitt A–A/B–B.
7. Laufzeit der Analyse für das Testprojekt gemessen und in BETRIEB 15 eingetragen.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN3G-1 | Gabarit in einer oder in beiden Auslegungen? | **Beide**, wie die Konturen (BR01): Bauband ohne Bedeutung, Kante `other`, einschränkende Vorgaben und nicht ermittelte Abstände bleiben mehrdeutig. Lageplan mit Wechsel, Schnitt beide übereinander |
| E-AN3G-2 | Stufenhöhe | **3,00 m plus kennzeichnende Höhen**, gleiche Stufen zusammengelegt. Feinere Stufen zeichnen bei `H/2` kaum anders, machen den Lageplan aber unlesbar; die Nutzfläche rechnet ohnehin mit den genauen Geschosshöhen |
| E-AN3G-3 | Schnittlinie frei wählbar? | **Nein, zwei feste Schnitte** A–A und B–B. Sie zeigen Straße, hintere und seitliche Grenzen – die Abstände, um die es geht. Freie Linie, wenn Architekten sie vermissen (Rückmeldung nach dem ersten Einsatz) |
| E-AN3G-4 | Gelände im Schnitt | **Eben mit Hinweis bis AN5.** Im Analyse-Produkt hat kein Grundstück Geländedaten (UP04); die Georeferenzierung in AN5 bringt sie |
| E-AN3G-5 | Höhenstufen als 3D-DXF jetzt? | **Nein, mit AN5** (Ausgabe: DXF, Bericht). Die Stufen liegen dann schon als Geometrie vor |
| E-AN3G-6 | Nutzfläche aus dem Gabarit rechnen? | **Ja, beide Enden mit derselben Formel** (3.4). Behebt PLAN_AN3 7.1 Nr. 9; unten ändert sich nur der Widerspruchsfall |
| E-AN3G-7 | Dachneigung im Hüllkörper | **Nein:** über der Traufe senkrecht bis zum First („Dachzone“). Ohne Firstrichtung ist die schräge Fläche nicht bestimmt; das Dachgeschoss ist über seinen Anteil angenähert (EA05) |
| E-AN3G-8 | Rechnen im Backend oder im Browser? | **Backend**, mit der Analyse in einer Antwort: shapely ist da, eine Geometriebibliothek im Browser käme dazu, und Bericht und DXF (AN5) brauchen dieselben Stufen |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | PLAN_ANALYSE schlug vor, die Ableitung je Stufe „mit fixiertem `Heights`“ aufzurufen | `on_boundary_max_height_m` bliebe unbeachtet (G3 kennt sie nicht), der Abstand wüchse über der Traufe weiter, und über der Höchsthöhe gäbe es weiter eine Kontur | 3.1: eigene Abstandsfunktion je Stufe; 3.2: über der Höchsthöhe nichts |
| 2 | Stufe mit der Kontur an ihrer Unterkante | Die Stufe wäre größer als erlaubt, sobald der Abstand mit der Höhe wächst | 3.2: Kontur an der Oberkante (sichere Seite) |
| 3 | Reine Geschossangabe mit den 3,00 m aus G3 | Mit Geschosshöhe 3,50 m läge das zweite Geschoss (7,00 m) über der umgerechneten Traufe (6,00 m) und fiele weg | 3.2: Umrechnung mit der Geschosshöhe der Annahmen |
| 4 | Nur das obere Ende aus dem Gabarit | Widersprechen Geschosszahl und Höhe (`R+2`, Traufe 7 m), zählte unten ein drittes Geschoss, oben nicht → unten > oben | 3.4: dieselbe Formel für beide Enden |
| 5 | Zusammenlegen gleicher Stufen | Die Traufe verschwände, wenn die Abstände oberhalb gleich bleiben (Zone Uh) – der Schnitt zeigte keine Dachzone | 3.2: an der Traufe nie zusammenlegen |
| 6 | Schnitt durch den Schwerpunkt des Grundstücks | Bei L-Form liegt er außerhalb, der Schnitt träfe die bebaubare Fläche nicht | 3.3: Schwerpunkt der Kontur, sonst innerer Punkt |
| 7 | Abstandslinie im Schnitt unmittelbar in Metern aufgetragen | Schneidet der Schnitt die Grenze schräg, stimmt der Abstand längs des Schnitts nicht | 3.3: Umrechnung über `1 / sin θ`, unter 15° keine Linie |
| 8 | Zwei Regeln an Kante `other` | Minimum und Maximum zweier stückweise linearer Abstände haben Knicke zwischen den Stützstellen | Abstandslinie aus Stützstellen (Knickhöhen) und einem Raster von 0,25 m |
| 9 | Rechenaufwand: zwei Auslegungen × Stufen × Geschosse | bis 20 Konturen je Abruf; bei Grundstücken mit vielen Kanten spürbar | 3.2: gleiche Abstandssätze nur einmal rechnen; Messung in der Abnahme |
| 10 | „soit en limite, soit en retrait de 3 m“ | Weit ausgelegt ist der Streifen zwischen 0 und 3 m bebaubar – aber nur mit einem Baukörper an der Grenze | bewusst: dieselbe Lesart wie die weiteste Kontur von G3 (BR01); in 7.3 benannt |
| 11 | `height_basis = facade_point` | Die Höhe der zugewandten Fassade ist je Stufe die Stufenhöhe selbst | 3.1: Bezugshöhe = größte Höhe, gedeckelt nur durch sie |
| 12 | Erste Fassung von 3.4: „unten ändert sich nur im Widerspruchsfall“ | Bei reiner Geschossangabe und Geschosshöhe über 3,00 m wird auch das untere Ende kleiner (richtig so, aber anders als behauptet) | 3.4: beide Fälle genannt, Beweis für unten ≤ oben ergänzt |
| 13 | Oberstes Geschoss: oben `n_max · h_min`, unten `n_min · h_max` – welches höher liegt, hängt von der Traufe ab (Traufe 8,50 m: 8,10 gegen 6,00 m) | Ließe unten > oben zu, wenn unten ein Dachgeschoss zählt | kein Fehler: unten zählt es nur mit Geschossangabe im Plan, dann ist `n` an beiden Enden gleich (3.4) |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Exakter Hüllkörper als geneigte Flächen (Offset je Höhe, gerades Skelett) | eigene Geometrie, für `max(min, f × h)` und die Grenzbebauung weitgehend gleichwertig mit Stufen; der Schnitt zeigt die genaue Linie ohnehin | ein Nutzer das 3D-Modell in CAD weiterbaut (AN5-DXF kann Stufen liefern) |
| 3D im Browser (three.js) | große Abhängigkeit für eine Ansicht; Lageplan mit Höhenlinien und zwei Schnitte sind die übliche Darstellung im Bauantrag | Abo für fremde Büros (AN6) |
| Gabarit als eigener Endpunkt | eine zweite Anfrage mit gleicher Eingabe; die Nutzfläche braucht ihn ohnehin | die Antwort zu groß oder zu langsam wird (Messung 5 Nr. 7) |
| Geländeprofil aus den Stichproben der Ausgleichsebene | im Analyse-Produkt gibt es keine; im Konfigurator gibt es keinen Schnitt | AN5 bringt Gelände |

### 7.3 Bewusste Grenzen

Stufen statt geneigter Flächen; Kontur an der Oberkante jeder Stufe. Gelände eben. Weit ausgelegt gilt der Streifen zwischen Grenze und Mindestabstand als bebaubar, wo auf der Grenze gebaut werden darf. Dachneigung und Firstrichtung begrenzen den Hüllkörper nicht. Die Nutzfläche bleibt eine Spanne ohne Grundriss.

### 7.4 Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Rechenfehler im Beispiel 3.4: unten mit der Kontur bei 3,00 m (294 m²) statt mit der engsten Kontur von G3 (Traufe 7 m, 273 m²) gerechnet | Abnahme 1 hätte 500 statt 464 m² verlangt | 3.4 und 5 Nr. 1 berichtigt; der Test rechnet 464,1 m² |
| 2 | Die Höhengrenze der Grenzbebauung wurde mit der Rechentoleranz der Abstände (1 cm) verglichen | Die Abstandslinie sprang erst bei 3,51 statt bei 3,50 m vom Grenzabstand 0 auf 3 m | Eigene Toleranz `HEIGHT_EPSILON_M` (nur Gleitkommafehler) in `setbacks.at_height` |
| 3 | Beschriftung „First 10,00“ rechts neben der Linie | In der Zeichnung abgeschnitten | über der Linie, rechtsbündig am Ende |
| 4 | In Telefonbreite war die **Projektseite** 13–55 px zu breit – nicht durch den neuen Abschnitt, sondern durch die Kantentabelle des Abschnitts „Grundstück“ (seit AN1): das Rasterfeld wuchs auf die Tabellenbreite, und die `sr-only`-Beschriftungen der Auswahlfelder lagen außerhalb des nicht positionierten Rahmens | Die ganze Seite verschob sich waagerecht | `[&>*]:min-w-0` an den Rastern der Projektseite und des Gabarits, `relative` am Rahmen von `KantenListe`; Stolperstelle im README |

**Prüflauf:** Backend 606 Tests mit `TEST_S3=1` (neu `tests/unit/test_analysis_gabarit.py` mit 19 Tests, Integrationstest der Analyse um Gabarit, Schnitte und Geschossflächen erweitert), Frontend 178 (vorher 172; neu `gabarit-schnitt.test.tsx` mit 5 Tests, dazu einer in `analyse-kennzahlen.test.tsx`), ruff, Format, mypy, Typprüfung und Lint grün; `openapi.json` und `schema.d.ts` neu erzeugt. Keine Migration.

**Browserprüfung am 28.09.2026** (Analyse-Stack mit neu gebauten Images, Deutsch und Französisch, Telefonbreite): Testprojekt „Testparzelle Zone Uh“ → zwei Stufen 0–7 m und Dachzone 7–10 m mit 300/210 m², Schnitt A–A' (Straße 3 bis hinten 1, Band 5–20 m, Traufe 7,00, First 10,00), B–B' (weit von Grenze zu Grenze, eng 3 m Abstand, Abstandslinien an beiden Seiten). Mit vorübergehender Büro-Korrektur „Seiten H/2 an der Traufe, mindestens 3 m, auf der Grenze bis 3,50 m“: vier Stufen 300/210, 210/210, 195/195, 195/195 m² (13 × 15 m ab 6 m), im Schnitt B–B' die typische Stufe mit Schräge zwischen 6 und 7 m; Nutzfläche unverändert 255–380 m², weil die Grundflächenzahl (150 m²) in jeder Stufe bindet. Korrektur danach entfernt. `GET /analysis` Median 59 ms (zehn Abrufe, 9 KB).
