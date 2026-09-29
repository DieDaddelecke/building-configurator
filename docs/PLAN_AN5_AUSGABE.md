# AN5 – Ausgabe und Projektakte (Emprise Analyse)

> **Status:** geplant am 28.09.2026 (Auftrag: „AN5: Ausgabe der Analyse“ nach dem Startprompt), **umgesetzt am 28./29.09.2026** (Befunde beim Bau in 7.4; Abnahme 1–7 erfüllt bis auf die Prüfung im ArchiCAD des Büros) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN5), 5 (RA2), 6 (E-A3, E-A5); [PLAN_AN3_GABARIT.md](PLAN_AN3_GABARIT.md) E-AN3G-4 (Gelände im Schnitt) und E-AN3G-5 (Höhenstufen als 3D-DXF); ANNAHMEN UP04 und UP15 (Lage erst mit AN5) · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN5 (AU01 ff.)
> **Voraussetzung:** AN0–AN4. Fachregeln: `BACKEND_SPEZIFIKATION.md` 5.9.4 (Höhenbezug, Gelände), 5.10.5 (Lageplan), V 3.7 (DXF-Ebenen, `app/plan/`).

---

## 1. Zweck und Umfang

Bis AN4 sieht der Architekt alle Ergebnisse nur auf dem Bildschirm. Für die Arbeit am Entwurf braucht er sie **in seiner Projektakte und in seinem CAD**: einen Bericht, der jeden Wert mit Fundstelle belegt, und eine Zeichnung mit Grundstück, Konturen und Hüllkörper. Ein gezeichnetes oder ohne Koordinaten hochgeladenes Grundstück hat außerdem keine Lage. Deshalb fehlen Gelände und Risiken, und eine Datei in Lambert-93 ist nicht möglich (UP04, UP15).

**Enthalten:**
- **Projektliste** mit Name, Notiz und Archiv.
- **Georeferenzierung** eines gezeichneten oder ohne Koordinaten hochgeladenen Grundstücks. Der Architekt verschiebt und dreht es auf einer Karte mit Katasterebene; Maße und Fläche bleiben dabei unverändert. Danach werden **Gelände und Risiken** abgefragt, auch für Uploads mit erkannten Koordinaten.
- **Geländeprofil in den Schnitten** A–A und B–B (E-AN3G-4).
- **DXF** mit Umriss, Kanten nach Art, beiden Konturen, Bauband, Bauverbots- und Einschränkungsflächen, Schnittlinien und dem Gabarit in 3D: lokal und, bei Lage, in Lambert-93 (E-AN3G-5).
- **GeoJSON** (WGS84) für georeferenzierte Grundstücke.
- **Bericht-PDF** (de oder fr) für die Projektakte, mit folgendem Inhalt:
  - alle Werte mit Zitat und Seite, Korrekturen mit Begründung
  - Lageplan, Gabarit und Schnitte
  - Kennzahlen, Annahmen und Grenzen
  - offene Punkte
  - Unterlagen mit Stand, Datum und Prüfsumme

**Nicht enthalten:**
- Zonengrenze auf dem Grundstück einzeichnen (E-A3, siehe E-AN5-8).
- Frei gezogene Schnittlinie (E-AN3G-3).
- Gabarit, der dem geneigten Gelände folgt (E-AN5-4).
- Branding, Schriftfeld und Logo in PDF und DXF (AN6).
- Auskunftsbericht nach DSGVO (UP07).
- DWG und IFC (PLAN_ANALYSE 8.3).

## 2. Befund

| Baustein | Stand | Folge |
|---|---|---|
| `project` | Eigentümer, Organisation (nullable); die Liste zeigt die Adressbezeichnung des Grundstücks | Spalten `name`, `note`, `archived_at` (Migration 0018); `PATCH /projects/{id}` |
| Lage | `site.georeferenced`, `local_origin_*`; Zeichnung und Upload ohne Koordinaten liegen „technisch“ im SRID 2154 ohne Bedeutung (G27, UP04). `terrain_status`/`risks_status` stehen dort fest auf `unavailable`, es wird kein `site_enrich` eingeplant | neuer Anwendungsfall „Lage setzen“ mit starrer Transformation von Umriss und Kanten; danach `pending` und `site_enrich`. Dasselbe beim Upload mit erkannten Koordinaten |
| Gelände (`site/domain/terrain.py`) | 9 Stichproben, Ausgleichsebene (Neigung, mittlere Höhe) | Für ein Profil im Schnitt zu wenig: dichteres Raster für Grundstücke ohne Kataster (3.3). `geoplateforme.elevations` schickt alle Punkte in **einer** GET-Anfrage, bei 200 Punkten rund 5 KB Adresse → in Pakete zu 100 teilen |
| Schnitt (`analysis/domain/section.py`) | Gelände eben auf ±0,00 | `terrain` je Schnitt als Profil über der Bezugshöhe |
| DXF (`app/plan/dxf.py`, `geometry.Plan`) | Ebenen für Grundstück, Kanten, zwei Konturen, Haus (V); Lambert-93 = lokal + Ursprung | Ebenen für Bauband, Vorgaben, Schnitte und Gabarit (2D-Höhenlinien und 3D-Körper). V muss unverändert bleiben (Test) |
| Steckbrief (`envelope/sheet.py`) | PDF des Konfigurators mit dem Satz „vom Architekturbüro nicht geprüft“. **In der Analyse über den Baurahmen erreichbar** (`Baurahmen` mit `rolle="architect"` zeigt „Steckbrief“) | In der Analyse ersetzt der Bericht den Steckbrief (E-AN5-9); die Zeichenhilfen des Steckbriefs (Lageplan als SVG, Zeilen einer Regel) werden wiederverwendet |
| Analyse (`analysis/service.py`) | Prüfsumme `input_hash` ausdrücklich „für AN5“; enthält die Geländestichproben nicht | Stichproben und Risiken gehen in die Prüfsumme des Berichts ein (3.6) |
| Karte (`components/karte/Katasterkarte.tsx`) | MapLibre, Plan IGN oder Luftbild; Parzellen aus der eigenen API (nur mit Import) | neue Karte zum Einpassen mit der WMTS-Ebene `CADASTRALPARCELS.PARCELLAIRE_EXPRESS` (PCI, `PM_0_19`, am 28.09.2026 geprüft: Kachel mit Parzellen, Nummern und Gebäuden) – ohne Katasterimport |

## 3. Fachliche Festlegungen

### 3.1 Projektliste

- `project.name` (bis 120 Zeichen), `project.note` (bis 2000 Zeichen), `project.archived_at`.
- `PATCH /projects/{id}` mit `name`, `note`, `archived` (Architekt, eigenes Projekt; Audit `project.update` ohne Inhalt der Notiz).
- `GET /projects?archived=false|true` (Vorgabe `false`); die Antwort nennt `name`, `note` (gekürzt auf 200 Zeichen) und `archived_at`.
- Oberfläche:
  - **Liste:** Name, sonst die Adressbezeichnung; Filter „Aktiv/Archiv“ und eine Suche über Name und Adresse im Browser.
  - **Projektseite:** Name und Notiz bearbeiten, archivieren und zurückholen.
- Archivieren blendet nur aus. Ein archiviertes Projekt bleibt bearbeitbar und löschbar (E-AN5-7).
- **Datenschutz:** Name und Notiz können den Namen eines Bauherrn enthalten. Sie verlassen das System nicht: Sie gehen weder an OpenRouter noch an die Géoplateforme. Sie stehen nur im Bericht, und dieser landet im Objektspeicher der Instanz. Das gehört ins Verarbeitungsverzeichnis (HANDOFF 4.5 Punkt 6).

### 3.2 Georeferenzierung

**Weg in der Oberfläche** (E-AN5-1):
1. Adresse suchen; die Karte springt dorthin.
2. Der Umriss liegt mittig darüber: im Maßstab der Karte, zunächst ungedreht (Blattoben = Norden).
3. Der Architekt schiebt den Umriss mit der Maus oder den Pfeiltasten (0,1 m, mit Umschalttaste 1 m) auf die Parzelle der Katasterebene.
4. Er dreht ihn mit Regler und Feinknöpfen (±0,1°, ±1°).
5. Luftbild und Plan IGN lassen sich als Hintergrund wählen.
6. „Lage übernehmen“.

**Was die Karte zeigt:** `SiteOut` bekommt `placement` mit folgenden Angaben:
- `pivot_local`: Schwerpunkt des Umrisses in lokalen Metern
- `pivot_wgs84`: nur mit Lage
- `map_rotation_deg`: Drehung im Uhrzeigersinn, mit der die lokalen Koordinaten auf der Karte (geografisch Nord oben) erscheinen:
  - ohne Lage `0`, Blattoben gilt als Norden
  - mit Lage `−γ`, weil die lokalen Achsen dann Gitternord von Lambert-93 folgen

Die Karte zeichnet jeden Punkt als Versatz `R(map_rotation_deg + Δ) · (p − pivot)` in Metern Ost/Nord um den Drehpunkt. `Δ` ist die Drehung, die der Architekt einstellt; der Regler beginnt immer bei 0 („gegenüber der jetzigen Lage“).

**API:** `PUT /projects/{id}/site/position` mit folgendem Inhalt:
- `lon`, `lat`: neue WGS84-Lage des Drehpunkts
- `rotation_deg` = `Δ`
- `expected_revision`

Zugelassen sind nur der Architekt und eigene Projekte (`require_owned_project` wie AN2). Im Konfigurator kann ein Kunde seine Zeichnung damit nicht verorten. Erlaubt ist das für Grundstücke der Herkunft `manual_sketch` und `upload`, auch wenn sie schon eine Lage haben (Korrektur). Für `parcel` antwortet die API mit `409 site_position_parcel`.

**Transformation (starr, Maße unverändert):**
- **Gitterkonvergenz** `γ` = Gitterazimut der geografischen Nordrichtung am neuen Drehpunkt, im Uhrzeigersinn. PostGIS transformiert den Punkt und einen Punkt 100 m geografisch nördlich davon (`ST_Project`) nach Lambert-93; `γ` ist der Azimut dieser Strecke im Gitter. Bei Nantes sind das etwa 3° – ohne Korrektur läge das Grundstück in Lambert-93 um diesen Winkel verdreht.
- **Rechnung für jeden Punkt** `p` von Umriss und Kanten: `p' = P93 + R(θ) · (p − pivot)` mit `θ = map_rotation_deg + Δ + γ`. Dabei ist `P93` der Drehpunkt in Lambert-93, und `R(θ)` dreht im Uhrzeigersinn. Daraus folgt:
  - ohne Lage: `θ = Δ + γ`
  - bei einer Korrektur: `θ = Δ − γ_alt + γ_neu ≈ Δ`, denn die Konvergenz ändert sich auf wenigen Metern um weniger als 0,001°
  - Test: Eine lokale Strecke nach Blattoben hat nach `Δ = 30°` den geografischen Azimut 30° und den Gitterazimut `30° + γ`.
- **Kanten** behalten Nummer, Art, Quelle und Beobachtungen. `normal_azimuth_deg`, `street_azimuth_deg` und `garden_azimuth_deg` werden aus der neuen Lage gerechnet. `length_m` und `area_m2` bleiben (Test: gleich auf 1 mm bzw. 0,01 m²).
- **Gespeichert** werden:
  - `georeferenced = true`
  - neuer `local_origin` (untere linke Ecke, abgerundet wie bei Upload)
  - `outline_hash`, `revision + 1`
  - `source_info.position` mit folgenden Angaben:
    - `lon`, `lat`
    - `rotation_deg`: Summe aller `Δ` seit der Zeichnung bzw. der Datei
    - `convergence_deg`
    - `method: "map"`
    - Zeitpunkt und Bearbeiter

    Ein Upload mit Koordinaten hat bis zu einer Korrektur `method: "file"`.
- **Danach:** alte Gelände- und Risikozeilen löschen, `terrain_status`/`risks_status = pending`, `site_enrich` einplanen. Das gilt auch beim Speichern eines Uploads mit erkannten Koordinaten. Der Kommentar „nie `pending`“ in `_store_sketch_site` gilt dann nur noch für Grundstücke ohne Lage.
- **Die Einordnung der Kanten bleibt.** Ein Dreh ändert, wo „vorn“ ist, nicht welche Kante zur Straße liegt. Die Auswertung (Regeln) bleibt gültig; der Baurahmen wird neu gerechnet (neue Prüfsumme).

**Genauigkeit:** so gut wie das Einpassen auf dem Kataster, in Zoomstufe 19 etwa 0,3 m je Bildpunkt. Der Kataster selbst weicht in Frankreich bis zu einigen Metern ab. Bericht und DXF nennen die Lage deshalb „von Hand eingepasst“; bei Uploads mit Koordinaten steht „aus der Datei“. Die Verzerrung von Lambert-93 (höchstens etwa 1 ‰) bleibt unberücksichtigt: bei 50 m höchstens 5 cm.

### 3.3 Gelände

- **Dichtes Raster für Grundstücke ohne Kataster** (`site/domain/terrain.py::grid_points`):
  - Rasterweite `max(2 m, √(Fläche / 200))`, also höchstens etwa 200 Punkte im Grundstück. Beispiele: 600 m² ergeben 2 m und etwa 150 Punkte; 5 000 m² ergeben 5 m; 50 000 m² ergeben 15,8 m.
  - Die 9 Stichproben des Konfigurators für `parcel` bleiben unverändert.
  - Die Ausgleichsebene (Neigung, mittlere Höhe) wird aus allen Punkten gerechnet.
  - Anfragen an den Höhendienst in Paketen zu 100 Punkten.
- **Profil im Schnitt** (`analysis/domain/terrain_profile.py`):
  - Aus den Stichproben entsteht ein Dreiecksnetz (Delaunay).
  - Entlang der Schnittlinie werden alle 0,5 m und an den Grundstücksgrenzen die Höhen linear im Dreieck interpoliert.
  - Die Stichproben liegen in Zellmitten, das Netz endet deshalb bis zu einer halben Rasterweite vor der Grenze. Dort wird vom letzten Punkt im Netz mit der Neigung der Ausgleichsebene längs des Schnitts weitergeführt (7.4 Nr. 2); eine Ebene bleibt damit genau.
  - Die Ausgabe `terrain` ist eine Liste `[s, dz]` mit `dz` = Höhe − `reference_altitude_ngf`; dazu kommt `reference_altitude_ngf` im Gabarit.
  - Ohne Gelände bleibt die Liste leer, und der Schnitt zeigt wie bisher die Linie ±0,00.
- **Höhenbezug (E-AN5-4):** Die Stufen bleiben über ±0,00 = mittlere Geländehöhe der Stichproben. Das Profil zeigt, wo das Gelände darüber oder darunter liegt. Bei Neigung über 5 % lautet der Hinweis: „Höhenbezug nach PLU prüfen (Messpunkt der Höhe)“. Das PLU entscheidet, ob die Höhe am tiefsten Punkt, im Mittel oder Punkt für Punkt gemessen wird; das Werkzeug kennt diese Angabe nicht verlässlich (`Heights.reference`).
- Die Prüfsumme der Analyse nimmt die Stichproben auf (Hash über `samples`), weil sie das Profil bestimmen. `ENGINE_VERSION` der Analyse wird `an5-1.0.0`. Das kostet nichts: Die Analyse speichert keine Ergebnisse, und `rules_housekeeping` reagiert nur auf die Version von G2 (BETRIEB 9).

### 3.4 DXF

Aus Baurahmen und Analyse entsteht ein erweiterter `Plan` (`analysis/export.py::plan_for`). `app/plan/dxf.py` bekommt neue Ebenen, die nur angelegt und gezeichnet werden, wenn sie belegt sind. Für V bleibt der Inhalt gleich: gleiche Ebenen und gleiche Objekte je Ebene. Byte-gleich ist eine DXF von ezdxf ohnehin nie, weil sie Zeitstempel und GUIDs im Kopf trägt.

| Ebene | Inhalt |
|---|---|
| `PARCELLE`, `LIMITE_*` | Umriss, Kanten nach Art (wie V) |
| `ZONE_CONSTRUCTIBLE_LARGE` / `_STRICTE` | beide Konturen (wie V) |
| `BANDE_CONSTRUCTIBLE` | Bauband |
| `ZONE_NON_AEDIFICANDI`, `ZONE_CONTRAINTE` | Vorgaben `no_build` / `restricts` (Flächen und Linien) |
| `COUPE` | Schnittlinien A–A, B–B mit Beschriftung |
| `GABARIT_LARGE_COURBES` / `GABARIT_STRICT_COURBES` | Kontur jeder Stufe als geschlossene Polylinie mit Erhebung = Oberkante der Stufe |
| `GABARIT_LARGE_VOLUME` / `GABARIT_STRICT_VOLUME` | je Stufe ein geschlossener Körper als Polyface-Netz: Seitenflächen je Kante, Deckel und Boden trianguliert (`ezdxf.math.triangulation.mapbox_earcut_2d`, mit Löchern) |
| `TEXTE`, `ORIGINE` | Projekt, Datum, Prüfsumme, Ursprung, Höhenbezug, Hinweis nach E-A5 |

- **Höhen (E-AN5-2):**
  - Lokale Datei: Z relativ, ±0,00 = Bezugshöhe.
  - Lambert-93: Z in m NGF (`reference_altitude_ngf + h`), wenn Gelände vorliegt, sonst relativ.
  - Der Text in der Datei nennt jeweils, welcher Bezug gilt.
- **Ein Körper je Stufe:** vom Boden der Stufe bis zu ihrer Oberkante. Auf die Stufe darüber wird nicht geschnitten, damit jeder Körper für sich geschlossen bleibt. Dachstufen stehen auf eigenen Ebenen mit Suffix `_TOIT`, damit sie sich ausblenden lassen.
- **Endpunkt:** `GET /projects/{id}/analysis/export/dxf?variant=local|L93` antwortet sofort im Request, ohne Ablage. Erwartet sind unter 0,5 s; gemessen wird in Abnahme 7. `L93` ohne Lage ergibt `409 export_not_georeferenced`. Der Dateiname ist `<Name oder Adresse>_<Datum>_<local|L93>.dxf`, auf ASCII vereinfacht.

### 3.5 GeoJSON

- `GET /projects/{id}/analysis/export/geojson` liefert eine FeatureCollection in WGS84 (RFC 7946), nur mit Lage (sonst `409 export_not_georeferenced`, E-AN5-6).
- Die Merkmale tragen `layer` wie die DXF-Ebenen.
- Eigenschaften:
  - Kante: `seq`, `kind`, `lenient_m`, `strict_m`
  - Kontur: `reading`, `area_m2`, `complete`
  - Gabarit: `reading`, `from_m`, `to_m`, `roof`, `z_ngf_top` (wenn bekannt)
  - Vorgabe: `effect`, `label`
- Umgerechnet wird in **einer** PostGIS-Abfrage über eine GeometryCollection, Koordinaten auf 7 Nachkommastellen.

### 3.6 Bericht-PDF

- **Erzeugen wie der Steckbrief:**
  - Job `analysis_report` im Worker (WeasyPrint).
  - Ablage im Objektspeicher unter `analysis/<Projekt>/<Prüfsumme>_<Sprache>.pdf`, Tabelle `analysis_report` (Migration 0018).
  - `POST /projects/{id}/analysis/report` mit `locale` liefert `ready` oder `pending` samt `job_id`.
  - `GET …/analysis/report?locale=` liefert das PDF oder `409 report_not_ready`.
  - Aufrufe sind begrenzt wie beim Steckbrief (`envelope_sheet_limit_per_hour`, eigener Zähler `analysis_report`).
- **Prüfsumme des Berichts:** über alles, was der Bericht zeigt – Name, Notiz, Adresse, die Ausgaben von Grundstück (mit Stichproben und Risiken), Baurahmen, Analyse und Regeln, Korrekturen, Unterlagen mit Prüfsumme der Datei – dazu `REPORT_VERSION`; die Sprache steht im Schlüssel. Ausgenommen sind Felder ohne Einfluss auf den Inhalt (Läufe, Kosten, Adressen, `job_id`, `updated_at`; 7.4 Nr. 1). Ändert sich etwas davon, entsteht ein neuer Bericht; derselbe Stand wird nur einmal erzeugt.
- **Inhalt** (A4, Fußzeile auf jeder Seite mit dem Hinweis nach E-A5, Seitenzahl, Prüfsumme):
  1. **Kopf:** Name, Adresse, Datum der Erzeugung, Status der Analyse, Stand (`ENGINE_VERSION`). Ein Bearbeiter wird nicht genannt, weil derselbe Stand für alle nur einmal erzeugt wird.
  2. **Kennzahlen:**
     - bindende Grundfläche weit/eng, mit bindendem Wert
     - Vollgeschosse
     - Nutzfläche als Spanne
     - Höchsthöhe
     - Abstand je Grenze im Klartext (EA10)
  3. **Lageplan** mit Grundstück, Kanten mit Nummer und Art, Konturen, Bauband, Vorgaben, Nordpfeil und Maßstab. Neu gezeichnet in `analysis/drawing.py`; die Farben kommen vom Steckbrief.
  4. **Gabarit:** Lageplan der Stufen, Tabelle der Stufen, **Schnitte A–A und B–B** mit Geländeprofil. Das ist der Schnitt der Oberfläche, serverseitig als SVG.
  5. **Regeln je Zone:**
     - Wert, Status, Seite und Zitat
     - Herkunft: Auswertung, Büro oder Projekt
     - Korrekturen mit **Begründung** und Fundstelle (E-AN5-5)
     - „nicht ermittelt“ und „nicht abbildbar“ ausdrücklich als **offene Punkte**
  6. **Zusatzdokumente:** strengere Werte und Übernahmen.
  7. **Annahmen und Grenzen:** Parameter der Nutzfläche, nicht Gerechnetes (`not_counted`), Hinweise des Gabarits, Warnungen.
  8. **Grundstück und Lage:** Herkunft, Datei, Maßstab, Lage (Methode, Ursprung in Lambert-93), Gelände (Höhe, Neigung, Quelle IGN RGE ALTI), Risiken (Géorisques, informativ).
  9. **Unterlagen und Stand:**
     - Reglement: Titel, Datei, SHA-256 gekürzt, Kapitel und Seiten, Version der Auswertung, Modell, Datum
     - Zusatzdokumente
     - Prüfsummen
- Sprache wählbar: Deutsch oder Französisch, vorgewählt die Sprache der Oberfläche. Die Texte stehen in `platform/locales` unter `report.*`; Regelwerte, Risiken und Lose lesen sich wie in der Oberfläche (`app/rules/format.py`, Texte aus dem Frontend abgeglichen, 7.4 Nr. 6–7).

### 3.7 Oberfläche

- **Projektliste** (3.1): Name, Adresse, Herkunft, Fläche, letzte Änderung; Filter Aktiv/Archiv; Suchfeld.
- **Projektseite:**
  - Kopf mit Name (bearbeitbar), Notiz und „Archivieren“ bzw. „Zurückholen“.
  - Im Abschnitt Grundstück „Lage festlegen“ bzw. „Lage korrigieren“ mit der Karte zum Einpassen (`products/analyse/LageEinpassen.tsx`, MapLibre nur per `React.lazy` wie `Katasterkarte`).
  - Nach der Lage stehen Gelände (Höhe, Neigung) und Risiken im Abschnitt Grundstück.
- **Neuer Abschnitt „Bericht und Ausgabe“** unter dem Gabarit:
  - Bericht (Sprache, erzeugen, herunterladen; Abfrage wie beim Steckbrief)
  - DXF lokal
  - DXF Lambert-93 und GeoJSON: ohne Lage ausgegraut, mit dem Hinweis „erst mit Lage“
- Der Steckbrief des Konfigurators verschwindet aus der Analyse (`Baurahmen` bekommt `steckbrief={false}`).
- Im Schnitt zeichnet die Oberfläche das Geländeprofil (gestrichelte Linie mit Schraffur darunter) statt der Linie ±0,00, wenn es vorliegt.

## 4. Arbeitsschritte

1. **Migration 0018:**
   - `project.name`, `note`, `archived_at`
   - Tabelle `analysis_report` (Projekt mit `ON DELETE CASCADE`, Prüfsumme, Sprache, Schlüssel, Größe, Zeitpunkt; eindeutig je Projekt, Prüfsumme und Sprache)
   - Löschen eines Projekts entfernt auch die Berichtsdateien (wie beim Steckbrief)
2. **Projektliste:** `platform/projects.py` (`PATCH`, Filter, Felder); Oberfläche `Projekte.tsx`, Kopf der `ProjektSeite`.
3. **Lage:**
   - `site/domain/position.py`, rein: Drehpunkt, Transformation, Azimute
   - `site/service.py::position_site`: Konvergenz, Speichern, Anreicherung
   - `site/api.py`: `PUT …/site/position`
   - Upload mit Koordinaten plant `site_enrich` ein
4. **Gelände:**
   - `terrain.grid_points`
   - `geoplateforme.elevations` in Paketen
   - `site_enrich` wählt das Raster nach Herkunft
   - `TerrainInput.samples`
   - `analysis/domain/terrain_profile.py`
   - `SectionOut.terrain`, `GabaritOut.reference_altitude_ngf`
   - `ENGINE_VERSION an5-1.0.0`
5. **DXF:** `app/plan/geometry.Plan` um Bänder, Vorgaben, Schnitte, Stufen und Z-Bezug erweitern; `app/plan/dxf.py` mit Ebenen und Polyface; `analysis/export.py::plan_for`, Endpunkt.
6. **GeoJSON:** `analysis/export.py::geojson`, Endpunkt.
7. **Bericht:**
   - `analysis/drawing.py`: Lageplan, Gabarit und Schnitt als SVG
   - `analysis/report.py`: HTML
   - `analysis/jobs.py`: Job `analysis_report`
   - Modell, Service und Endpunkte
   - Texte de/fr
   - Job im Produktprofil `analyse` registrieren
8. **Oberfläche:** `LageEinpassen.tsx` mit reiner Hilfe `einpassen.ts` (Umriss drehen und in Länge/Breite setzen, Tastatur), `Ausgabe.tsx`, Geländeprofil in `GabaritSchnitt.tsx`, Gelände und Risiken in `ProjektSeite`, `Baurahmen` ohne Steckbrief, Übersetzungen de/fr.
9. `openapi.json`, `schema.d.ts`.
10. **Tests:**
    - Einheit:
      - Transformation: Drehpunkt, Konvergenz-Vorzeichen, Längen und Fläche gleich, Azimute
      - Raster und Profil: Ebene exakt nachgebildet, außerhalb leer
      - DXF: Ebenen, Körper geschlossen, L93 verschoben, Z in NGF; V unverändert
      - GeoJSON-Aufbau
      - Bericht-HTML: Abschnitte, offene Punkte, Korrektur mit Begründung
    - Integration:
      - Liste mit Name, Archiv und Filter
      - Lage setzen → Anreicherung eingeplant, Kanten behalten ihre Art
      - `parcel` → 409
      - DXF/GeoJSON-Endpunkte, 409 ohne Lage
      - Bericht: Auftrag, Job, Download, gleicher Stand nur einmal
      - Löschen entfernt den Bericht
    - Komponenten: Liste, Einpassen-Hilfe, Ausgabe, Schnitt mit Profil
11. **Dokumente:** ANNAHMEN (AU01 ff.), PLAN_ANALYSE (AN5 umgesetzt), BETRIEB 15 (Ausgabe, Lage, Gelände, Job, ausgehender Zugang), AGENTS, UMSETZUNGSPLAN D18/R1.

## 5. Abnahme

1. Ein gezeichnetes Rechteck 20 × 30 m, auf Treillières gesetzt und um 30° gedreht:
   - Fläche 600,00 m², Kantenlängen unverändert
   - die Kante, die vorher nach Norden zeigte, zeigt geografisch nach 30° (Nordost), in Lambert-93 um `γ` versetzt
   - `site_enrich` eingeplant
2. Profil über einer schiefen Ebene `z = 40 + 0,1·x`: Das Profil entlang A–A gibt die Ebene auf 1 cm genau wieder, die Neigung ist 10 %, der Hinweis „Höhenbezug prüfen“ erscheint.
3. DXF des Testprojekts (Zone Uh):
   - `ezdxf` liest die Datei wieder ein
   - Stufen-Körper geschlossen (jede Kante gehört zu zwei Flächen)
   - L93 = lokal + Ursprung
   - Z in NGF mit Gelände, sonst relativ
   - Dossier-DXF aus V inhaltlich gleich mit vorher (Ebenen und Objekte je Ebene)
4. GeoJSON: gültig nach RFC 7946 (Ring-Orientierung, WGS84); ohne Lage 409.
5. Bericht (de und fr):
   - alle Abschnitte
   - jede wirksame Regel mit Seite
   - Korrektur mit Begründung
   - offene Punkte gelistet
   - Fußzeile mit Hinweis
   - zweiter Auftrag mit gleichem Stand → `ready` ohne neuen Job
   - nach einer Korrektur neue Prüfsumme
6. Browser (Analyse-Stack, de/fr, Telefonbreite ohne waagerechtes Verschieben):
   - Liste mit Name und Archiv
   - Lage auf der Katasterebene einpassen
   - Gelände und Risiken erscheinen
   - Schnitt mit Profil
   - Bericht und DXF herunterladen
   - DXF im ArchiCAD des Büros prüfen, sobald möglich (BETRIEB 14)
7. Dauer von Bericht und DXF gemessen und in BETRIEB 15 eingetragen.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN5-1 | Wie wird ein Grundstück verortet? | **Auf einer Karte mit Katasterebene verschieben und drehen**, die Adresssuche setzt nur den Startpunkt. Der Plan nannte „Punkt aus der Adresssuche und Drehwinkel“. Der Adresspunkt liegt aber oft 5–20 m neben dem Schwerpunkt der Parzelle, und ein so ungenaues DXF in Lambert-93 wäre im CAD sofort als falsch sichtbar. Mit der Katasterebene genügt ein Blick zur Kontrolle |
| E-AN5-2 | Höhenbezug im DXF | **Lokal relativ, Lambert-93 in m NGF** (mit Gelände), jeweils mit Text in der Datei. So lässt sich die L93-Datei mit einem Geländemodell des Büros zusammensetzen, die lokale bleibt einfach |
| E-AN5-3 | Form des 3D-Gabarits | **Höhenlinien und geschlossene Körper je Stufe** (Polyface) auf getrennten Ebenen. Die Höhenlinien liest jedes CAD; die Körper zeigen den Hüllkörper in 3D. Ob ArchiCAD die Körper als Morph übernimmt, ist nicht belegt und wird mit dem Büro geprüft (BETRIEB 14) |
| E-AN5-4 | Folgt der Gabarit dem Gelände? | **Nein**, Stufen über der mittleren Geländehöhe. Dazu das Profil und bei Neigung über 5 % ein Hinweis. Wie die Höhe gemessen wird (tiefster Punkt, Mittel, Punkt für Punkt), steht im PLU und ist nicht verlässlich ausgewertet; eine stille Annahme wäre gefährlicher als ein sichtbarer Hinweis |
| E-AN5-5 | Begründungen der Korrekturen im Bericht? | **Ja.** Der Bericht ist die Projektakte des Büros, und KR03 schützt die Begründung vor Kunden, nicht vor dem Büro. Wer ihn weitergibt, sieht das im Bericht: Die Überschrift nennt „Korrekturen des Büros“ |
| E-AN5-6 | GeoJSON ohne Lage? | **Nein.** RFC 7946 kennt nur WGS84; lokale Koordinaten darin wären eine Fehlerquelle. Ohne Lage gibt es das lokale DXF |
| E-AN5-7 | Was bewirkt „archivieren“? | **Nur ausblenden.** Sperren oder automatisches Löschen bräuchte eine Frist, die niemand verlangt hat; Löschen bleibt ein eigener Schritt |
| E-AN5-8 | Zonengrenze einzeichnen (E-A3: „erst in AN5“) | **Nicht in AN5**, sondern nach Auslöser. Das bräuchte Teilflächen je Zone im zweiten Einstieg von `resolve_rules` (AN2) und eine Zone je Teilfläche in der Auswahl – ein eigenes Modul. Bis dahin bleibt eine Zone je Grundstück wie bisher und in der Oberfläche benannt |
| E-AN5-9 | Steckbrief des Konfigurators in der Analyse | **Ausblenden**, der Bericht ersetzt ihn. Sein Satz „vom Architekturbüro nicht geprüft“ ist im Werkzeug des Büros falsch |
| E-AN5-10 | Bericht und Dateien erzeugen | **Bericht im Worker mit Ablage je Prüfsumme und Sprache** (WeasyPrint braucht Sekunden, wie beim Steckbrief). **DXF und GeoJSON sofort im Request**, ohne Ablage – sie entstehen in Millisekunden, und eine Ablage bräuchte Aufräumen |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Der Plan nannte „Punkt aus der Adresssuche und Drehwinkel“. Welcher Punkt des Umrisses auf den Adresspunkt fällt, war offen, ebenso die Genauigkeit | Ein um 5–20 m versetztes Grundstück in Lambert-93, im CAD sofort falsch | 3.2, E-AN5-1: Drehpunkt = Schwerpunkt, Lage auf der Katasterebene eingepasst |
| 2 | Die Karte zeigt geografisch Nord, Lambert-93 hat Gitternord. Die Konvergenz beträgt bei Nantes etwa 3° | Grundstück in Lambert-93 um 3° verdreht, Konturen und Nachbarbezug falsch | 3.2: Konvergenz am Drehpunkt über PostGIS, Vorzeichen per Test |
| 3 | Eine Transformation über geodätische Strecken (`ST_Project` je Punkt) hätte Längen und Fläche um bis zu 1 ‰ verändert | „Meine Fläche hat sich geändert“ – ohne fachlichen Grund | 3.2: starre Transformation in Lambert-93, Maße gleich |
| 4 | Neun Stichproben ergeben im Schnitt nur eine Gerade (Ausgleichsebene) | Ein „Profil“ ohne Aussage | 3.3: dichtes Raster bis 200 Punkte für Grundstücke ohne Kataster |
| 5 | `elevations` schickt alle Punkte in einer GET-Adresse | Bei 200 Punkten rund 5 KB Adresse; manche Server lehnen über 4–8 KB ab | 3.3: Pakete zu 100 |
| 6 | Die Prüfsumme der Analyse enthält die Stichproben nicht, das Profil hängt aber daran | Ein Bericht mit veraltetem Profil würde wiederverwendet | 3.3, 3.6: Hash der Stichproben in Analyse und Bericht |
| 7 | Nach dem Drehen stimmen `normal_azimuth_deg` und die Azimute von Straße und Garten nicht mehr | Nordpfeil und Einordnungshilfen falsch | 3.2: aus der neuen Lage neu gerechnet |
| 8 | Die Analyse zeigt heute den Steckbrief des Konfigurators mit „vom Architekturbüro nicht geprüft“ | Falsche Aussage im Werkzeug des Büros | E-AN5-9 |
| 9 | Neue DXF-Ebenen in `app/plan/dxf.py` könnten die Dateien von V ändern | Stiller Unterschied im Dossier einer eingereichten Fassung | 3.4: nur belegte Ebenen anlegen und zeichnen; Abnahme 3 vergleicht den Inhalt von V |
| 10 | E-A3 legte die Zonengrenze auf AN5, die Modulliste von AN5 nennt sie nicht | Widerspruch im Gesamtplan | E-AN5-8: nicht in AN5, eigener Auslöser; PLAN_ANALYSE E-A3 wird nachgezogen |
| 11 | Name und Notiz können personenbezogen sein (Bauherr) | Fehlt im Verarbeitungsverzeichnis, würde ungeprüft weitergegeben | 3.1: bleibt im System, nur im Bericht; Verzeichnis in HANDOFF |
| 12 | Ein Körper je Stufe, auf die nächste Stufe beschnitten, ergäbe offene Flächen, wo die obere Kontur kleiner ist | Netz nicht geschlossen, manche CAD zeigen Löcher | 3.4: jeder Körper geschlossen von Unter- bis Oberkante |
| 13 | Das Löschen eines Projekts entfernt Zeilen per `CASCADE`, nicht aber Dateien im Objektspeicher | Berichte blieben liegen, mit Name des Projekts | 4 Schritt 1: wie beim Steckbrief mitlöschen (Umsetzung prüfen: 7.4) |

Bei der Selbstprüfung des Plans gefunden und im Text behoben:

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 14 | Die erste Formel `R(rotation − γ)` ließ offen, wie `γ` definiert ist, und nannte das Vorzeichen „per Test“ | Je nach Lesart um 2γ (bei Nantes etwa 6°) verdreht | 3.2: `γ` = Gitterazimut der geografischen Nordrichtung, `θ = map_rotation_deg + Δ + γ`, Test mit Strecke nach Blattoben |
| 15 | Eine Korrektur eines schon verorteten Grundstücks war nicht beschrieben: Die lokalen Achsen folgen dann Gitternord, die Karte zeigt geografisch Nord | Die Karte hätte das Grundstück um `γ` verdreht gezeigt, „Übernehmen“ ohne Änderung hätte es um `γ` weitergedreht | 3.2: `placement.map_rotation_deg` (0 bzw. `−γ`), Regler relativ zur jetzigen Lage |
| 16 | Der neue Endpunkt liegt im Kern (`site/api.py`) und wäre mit `require_project_access` auch im Konfigurator für Kunden offen | Kunden könnten gezeichnete Grundstücke verorten und damit Anfragen an externe Dienste auslösen, was G27 ausschließt | 3.2: `require_owned_project` |
| 17 | Rasterweite „mindestens 1 m, höchstens 10 m“ und „höchstens 200 Punkte“ widersprechen sich ab etwa 20 000 m² | Unklare Regel, entweder zu viele Anfragen oder die Grenze verletzt | 3.3: `max(2 m, √(A/200))` mit Beispielen |
| 18 | „V bleibt byte-gleich“ ist mit ezdxf nicht erreichbar: Der Kopf trägt Zeitstempel und GUIDs | Ein Test auf Bytegleichheit wäre immer rot | 3.4, Abnahme 3: gleiche Ebenen und Objekte |
| 19 | Der Kopf des Berichts nannte den Bearbeiter, die Prüfsumme nicht | Ein zweiter Architekt hätte einen Bericht mit dem Namen des ersten bekommen | 3.6: kein Bearbeiter im Kopf |
| 20 | „ArchiCAD liest Polyface als Morph“ war eine unbelegte Behauptung | Falsche Sicherheit bei E-AN5-3 | E-AN5-3: als offene Prüfung mit dem Büro |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Automatisch auf die Katasterparzelle einpassen (Parzelle über API Carto holen, Umriss per Ausgleich drehen und schieben) | Braucht die Parzellennummer oder einen Klick, eine Ausgleichsrechnung mit Spiegelungs- und Mehrdeutigkeitsfällen und bleibt bei abweichendem Plan (Teilung, Geometer) unsicher; das Auge auf der Katasterebene leistet dasselbe | viele Grundstücke eingepasst werden müssen – dann als Vorschlag, den der Architekt bestätigt |
| Nur Adresspunkt und Winkel (Plan-Text) | 5–20 m Versatz (7.1 Nr. 1) | Gelände und Risiken allein gebraucht würden, ohne L93-Datei |
| Geländeprofil beim Rechnen der Analyse live abfragen | Externer Aufruf bei jedem Abruf der Analyse, Kosten und Ausfälle im Request | die Schnittlinie frei wird (E-AN3G-3) – dann ein Job je Linie |
| Gabarit dem Gelände folgen lassen | Messregel der Höhe im PLU nicht verlässlich bekannt (E-AN5-4) | die Regelart `max_height` den Messpunkt ausgewertet trägt |
| Bericht im Browser drucken | Server ist maßgeblich (L5); gleicher Stand, gleiche Datei, archivierbar | nie |
| Ein Bericht-Service mit HTML-Vorlagen (Jinja) | Der Steckbrief kommt ohne Vorlagenbibliothek aus; eine zweite Art, HTML zu erzeugen, wäre mehr Pflege | die Vorlagen von Nicht-Entwicklern gepflegt werden sollen (Branding in AN6) |
| IFC statt DXF-Polyface für den Hüllkörper | Neue Abhängigkeit, im Büro ist DXF der Austausch (PLAN_ANALYSE 8.3) | ein BIM-Werkzeug des Büros den Hüllkörper als Raumkörper braucht |

### 7.3 Bewusste Grenzen

- **Lage:** von Hand eingepasst, so genau wie der Kataster. Die Verzerrung von Lambert-93 bleibt unberücksichtigt.
- **Gelände:**
  - Profil aus höchstens 200 Punkten.
  - Der Gabarit steht über der mittleren Höhe.
  - Risiken sind nur informativ und an einem Punkt abgefragt.
- **Bericht und Dateien:**
  - Der Bericht ist ohne Branding.
  - DXF gibt es nur als R2010 ohne Schriftfeld.
  - GeoJSON gibt es nur mit Lage.
  - Frühere Berichtsstände bleiben im Objektspeicher, bis das Projekt gelöscht wird (je Bericht rund 50 KB, nur auf Anforderung und begrenzt je Stunde).
- **Archiv:** Es blendet nur aus.

### 7.4 Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | `EnvelopeOut.updated_at` ist bei jeder Berechnung die aktuelle Zeit und ging in die Prüfsumme des Berichts ein | Jede Anfrage hätte einen neuen Bericht erzeugt, „derselbe Stand nur einmal“ wäre nie eingetreten | `updated_at` unter den Feldern ohne Einfluss (AU08); Test „einmal je Stand und Sprache“ |
| 2 | Die Stichproben liegen in Zellmitten; „außerhalb des Netzes kein Punkt“ ließ das Profil bis zu einer halben Rasterweite vor jeder Grenze enden | Lücke genau dort, wo die Abstände liegen | 3.3: Fortsetzung mit der Neigung der Ausgleichsebene (AU04) |
| 3 | Nach „Lage übernehmen“ holte die Seite die Analyse sofort neu, das Gelände kam aber erst Sekunden später (`site_enrich`) | Gabarit und Schnitt zeigten „Gelände unbekannt“, bis die Seite neu geladen wurde (Browserabnahme) | `useRefreshAnalysisOnTerrain`: Wechsel des Geländes von `pending` auf ein Ergebnis holt die Analyse neu (AU03) |
| 4 | Die Sprache des Berichts war fest Französisch | Widerspruch zu 3.6 („vorgewählt die Sprache der Oberfläche“) | `Ausgabe.tsx`, Test |
| 5 | Ausgegraute Knöpfe (`btn-ghost`, `chip`) sahen wie aktive aus | DXF Lambert-93 und GeoJSON ohne Lage wirkten anklickbar | `styles/index.css`: `:disabled` mit Linienfarbe und Sperrzeiger |
| 6 | Der Bericht gab Regelwerte als Parameterliste aus („mode range · maximum 20,00“); der Steckbrief des Konfigurators ebenso für Regeln ohne festen Betrag | In Projektakte und Kunden-PDF unlesbar, anders als auf dem Bildschirm | `app/rules/format.py` als Gegenstück zu `rules/format.ts`, Texte über `tools/sync-check-texts.cjs`; `envelope.param.*` entfällt (AU09, AU10) |
| 7 | Risiken standen mit dem Rohtext von Géorisques („Risque Existant“), Lose als „Lot Lot-12“; die Legende nannte Kategorien, die der Plan nicht zeigte, und das Geländeprofil ohne Profil | Bericht widersprach der Oberfläche | Risiken mit `risk.kind.*`, Lose wie `lotLabel`, Legenden nur für Gezeigtes (AU09) |
| 8 | Tests mit PLU und `run_one`: Der Hilfsaufruf nimmt den ältesten wartenden Job, das ist dort die Regel-Auswertung | Ein Test hätte eine bezahlte Auswertung ausgelöst (mit Testschlüssel scheitert sie nur) | Tests rufen `site_enrich` direkt mit `JobContext` auf; README „Stolperstellen“ |
| 9 | `retention_cleanup` löscht Kundenentwürfe per SQL, ohne ihre Steckbrief-Dateien; die Dossier-Dateien von V sind beim Löschen nicht angemeldet | Verwaiste Dateien im Objektspeicher (kein Zugriff, aber Datensparsamkeit) | Nicht in AN5: eigene Aufgabe (HANDOFF); AN5 selbst meldet Bericht und Steckbrief an (AU11) |

Gemessen in der Browserabnahme (lokal, Testparzelle Zone Uh, 600 m²): Gelände 148 Punkte, `site_enrich` 5,3 s; Bericht-Job 1,0–2,5 s, 7–8 Seiten, rund 50 KB; DXF beim ersten Abruf nach dem Start 0,5 s, danach unter 0,1 s (lokal und Lambert-93); GeoJSON unter 0,1 s.
