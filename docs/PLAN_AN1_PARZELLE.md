# AN1 – Parzelle ohne Kataster (Emprise Analyse)

> **Status:** geplant und umgesetzt am 20./21.09.2026 · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN1), 8.1 Nr. 2–4 und 10 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN1 (Präfix `UP`)
> **Voraussetzung:** AN0 (Produktschnitt, ANNAHMEN PS01–PS09).

---

## 1. Zweck und Umfang

Der Architekt bringt die Parzelle selbst ein – als Datei oder gezeichnet – und ordnet ihre Kanten ein. Damit hat das Analyse-Produkt zum ersten Mal einen eigenen Eingang; bis hierher lief es nur auf Kataster-Parzellen des Einzugsgebiets (D17 kehrt das um).

**Enthalten:** Herkunft `upload`; Kanten für Grundstücke ohne Kataster; Datei-Upload DXF und GeoJSON mit Auswahl unter mehreren Konturen; Kanteneinordnung von Hand; Projekte am Architektenkonto mit Liste; Löschung eines Projekts im Kern; Oberfläche des Analyse-Produkts (Anmeldung, Projektliste, Parzelle, Kanten).

**Nicht enthalten:** PLU hochladen und Regeln (AN2), Baurahmen und Nutzfläche (AN3), Bericht, DXF-Ausgabe, Georeferenzierung und Projektnotizen (AN5), Mandanten (AN6). Gelände und Risiken bleiben `unavailable`, auch bei georeferenzierten Dateien – sie hängen an externen Diensten und kommen mit AN5.

## 2. Befund

| Baustein | Stand | Folge für AN1 |
|---|---|---|
| `site.origin ∈ {parcel, manual_sketch}` | Weg E legt **keine** `site_edge` an (G26) | ohne Kanten kein Abstand und kein Baurahmen (PLAN_ANALYSE 8.1 Nr. 2) |
| `split_edges` | rein geometrisch, fasst Segmente unter 5° Richtungsänderung zusammen | funktioniert für jeden Umriss, auch mit vielen Stützpunkten |
| `classify(..., neighbour_coverage="none")` | ohne Nachbarn bekommt keine Kante Straßenvertrauen → **jede Kante `other`, Vertrauen 0**, Warnungen `no_neighbour_data`, `no_street_edge`, `edges_need_review` | genau die gesuchte Ausgangslage: „unbekannt, bitte einordnen“ – keine Änderung an der Einordnungslogik nötig |
| Kante `other` im Baurahmen | `KIND_BY_EDGE["other"] = (setback_side, setback_rear)`, Markierung `kind_unclear` | eine nicht eingeordnete Kante ist nicht abstandsfrei, sondern wird eng ausgelegt – sicher in der richtigen Richtung |
| `PATCH /admin/projects/{id}/site/edges/{seq}` | Architekt setzt `street`, `side`, `rear`, `other`; `classify` leitet Hauptstraße und Azimute daraus ab | Einordnung von Hand braucht keinen neuen Endpunkt |
| `require_project_access` | nur das Projekt-Cookie | der angemeldete Architekt käme an keinen G1–G3-Endpunkt (8.1 Nr. 3) |
| `retention_cleanup` | löscht `status='draft'` nach 90 Tagen | Architektenprojekte wären nach drei Monaten weg (8.1 Nr. 4) |
| Löschung und Auskunft | `DELETE /projects/{id}` und `GET /projects/{id}/export` liegen in Modul A | fehlen dem Analyse-Produkt (8.1 Nr. 10, ANNAHMEN PS09) |
| Frontend | `FreiesZeichnen`, `SiteLageplan`, `KantenListe` (mit Rolle `architect`), `useSession` | wiederverwendbar; neu sind Rahmen, Projektliste und Upload |

## 3. Fachliche Festlegungen

### 3.1 Herkunft und Kanten

`site.origin` bekommt den dritten Wert `upload`. Für **beide** Herkünfte ohne Kataster (`manual_sketch`, `upload`) entstehen jetzt `site_edge`-Zeilen: `split_edges` auf den Umriss, leere Beobachtungen (`neighbour_share=0`, `adjacent=()`, `street_candidate="none"`, `probe_in_parcel=False`, `road_share=None`), `classify(..., neighbour_coverage="none")`. Das ändert G26 (dort blieb `site_edge` leer) und wirkt auch im Hauskonfigurator auf Weg E; das Verhalten dort bleibt sonst gleich, weil G2/G3 für `manual_sketch` weiterhin nicht laufen (G29) und die Oberfläche des Kunden die Kanten einer Skizze nicht zeigt.

Alle Kanten starten als `other` mit Vertrauen 0. Der Architekt setzt Straße, Seite, Hinten oder lässt `other` stehen; erst eine Straßenkante ergibt Hauptstraße, Straßen- und Gartenazimut.

### 3.2 Datei-Upload

Ein Endpunkt, ein Durchgang, kein Zwischenspeicher: `POST /projects/{id}/site/upload` mit der Datei. Die Antwort (`UploadResultOut`) enthält **entweder** das gebildete Grundstück **oder**, bei mehreren geschlossenen Konturen, alle Kandidaten (Ebene, Name, Fläche, Umriss in lokalen Metern zur Vorschau) – gespeichert wird dann nichts; der zweite Aufruf nennt `index`. Eine Auswahl ist kein Fehler, deshalb 200 statt eines Fehlercodes. Die Datei selbst wird **nicht** gespeichert, ihre Herkunft schon: Dateiname, SHA-256, Ebene, gewählter Index, erkanntes Koordinatensystem stehen in `site.source_info`.

| Format | Gelesen wird | Koordinatensystem |
|---|---|---|
| GeoJSON (`.geojson`, `.json`) | `Polygon` und `MultiPolygon` aus `Feature`, `FeatureCollection` oder blanker Geometrie; nur äußere Ringe | aus der Größenordnung erkannt: WGS84 (Lambert-93 nach Umrechnung) oder Lambert-93; sonst „ohne Bezug“ |
| DXF (`.dxf`) | geschlossene `LWPOLYLINE` und `POLYLINE`; je Kandidat die Ebene | Einheit aus `$INSUNITS` (mm, cm, m); Koordinaten im Lambert-93-Bereich gelten als georeferenziert, sonst „ohne Bezug“ |

Schranken wie bei Weg E (G28): Fläche 20–50 000 m², keine Selbstüberschneidung, mindestens drei Stützpunkte; dazu höchstens 2 000 Stützpunkte je Kontur und höchstens 8 MB Datei. Die Zahl der **Kanten** ist nicht beschränkt, weil `split_edges` zusammenfasst.

**Georeferenz:** Neue Spalte `site.georeferenced`. Sie ist wahr für Kataster-Grundstücke und für Uploads mit erkanntem Koordinatensystem; dann bleibt die echte Lambert-93-Lage erhalten und `outline_geojson` wird gefüllt. Sonst liegt der Umriss wie bei Weg E ab (0, 0) in einem technischen SRID 2154 ohne geografische Bedeutung (G26). Gelände, Risiken und Zonensuche bleiben in AN1 in **beiden** Fällen aus.

### 3.3 Projekte am Architektenkonto

- Neue Spalten `project.owner_staff_user_id` (→ `staff_user`) und `project.organisation_id` (nullable, ohne Tabelle – nur offengehalten, D15).
- `POST /projects`: Ist eine Mitarbeitersitzung mit Rolle `architect` vorhanden, wird das Projekt ihr zugeordnet und **kein** Projekt-Cookie gesetzt (sonst überschriebe jedes neue Projekt das vorige).
- `require_project_access` erlaubt zusätzlich: angemeldeter `architect`, Projekt hat einen Eigentümer und dieselbe Organisation (beides `NULL` = die eine Organisation des Büros, D15). Kundenprojekte ohne Eigentümer bleiben unerreichbar.
- `GET /projects` listet die Projekte mit Eigentümer (Rolle `architect`): Kennung, Bezeichnung des Grundstücks, Herkunft, Fläche, letzte Änderung. Benennung, Notiz und Archiv kommen mit AN5.
- `retention_cleanup` überspringt Projekte mit Eigentümer.

### 3.4 Löschung und Auskunft in den Kern

**Die Löschung** `DELETE /projects/{id}` wandert aus `app/inquiry/api.py` nach `app/platform/projects.py`. Modul A hängt dort seine Sperre ein (`register_delete_guard`: nach einer Anfrage löscht nur das Büro, D6), damit die Grenze aus AN0 hält. Pfad und Antworten bleiben gleich – für den Hauskonfigurator ändert sich nichts.

**Die Auskunft** `GET /projects/{id}/export` bleibt dagegen in Modul A (Abweichung vom Entwurf, UP07): Ihr Inhalt – Kontakt, Einwilligungen, Anfrage, Fassungen – stammt vollständig aus A; ein Architektenprojekt hat davon nichts. Sobald fremde Büros Daten einstellen (AN6), ist das neu zu bewerten.

### 3.5 Oberfläche des Analyse-Produkts

`/` Anmeldung (Mitarbeitersitzung, Rolle `architect`) und Projektliste mit „Neues Projekt“ · `/projekt/:id` Parzelle einbringen (Datei oder zeichnen), danach Lageplan mit Kantenliste zum Einordnen. Wiederverwendet werden `FreiesZeichnen`, `SiteLageplan`, `KantenListe` (Rolle `architect`) und `useSession`; neu sind `AnalyseLayout`, `Projekte`, `ProjektSeite` und `ParzelleHochladen`.

## 4. Arbeitsschritte

1. Migration `0012`: `site.origin` um `upload`, `site.georeferenced`, `site.source_info`, `project.owner_staff_user_id`, `project.organisation_id`.
2. `app/site/domain/upload.py` (rein): DXF und GeoJSON lesen, Kandidaten bilden, Koordinatensystem erkennen, Schranken prüfen.
3. `site/service.py`: `_store_sketch_site` (Zeichnung und Upload gemeinsam) mit Kanten; `load_site` für Grundstücke ohne Kataster mit Kanten und Warnungen.
4. `site/api.py`: `POST …/site/upload`; `PATCH …/site/edges/{seq}` für den Architekten bleibt.
5. Plattform: Eigentümer beim Anlegen, `require_project_access`, `GET /projects`, `retention_cleanup`, Löschung und Auskunft in den Kern.
6. Frontend: Rahmen, Projektliste, Projektseite mit Upload, Zeichnen und Kanteneinordnung; Übersetzungen.
7. Tests: Einheitstests für das Lesen der Dateien, Integrationstests für Upload, Kanten, Eigentum und Zugriff; Komponententest der Projektseite.
8. Dokumente: ANNAHMEN (Abschnitt AN1), BETRIEB 15, PLAN_ANALYSE (AN1 umgesetzt), README.

## 5. Abnahme

1. DXF mit zwei geschlossenen Polylinien → Auswahl, danach Grundstück mit Kanten; GeoJSON in WGS84 und in Lambert-93 → georeferenziert; gezeichnete Parzelle → nicht georeferenziert, ebenfalls mit Kanten.
2. Jede Kante beginnt als `other` mit Vertrauen 0; nach dem Setzen einer Straßenkante stehen Hauptstraße und Azimute.
3. Ein Architekt erreicht nur Projekte mit Eigentümer; ein fremdes Kundenprojekt bleibt `404`; ohne Anmeldung `404`.
4. `retention_cleanup` löscht ein altes Projekt ohne Eigentümer und lässt das mit Eigentümer stehen.
5. Löschung und Auskunft verhalten sich im Hauskonfigurator unverändert (Sperre nach einer Anfrage, Inhalt der Auskunft).
6. Voller Prüflauf grün, `openapi.json` neu erzeugt, Grenz-Test aus AN0 hält.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN1-1 | Datei aufbewahren? | **Nein**, nur Herkunftsangaben (Name, SHA-256, Ebene, Index). Die Parzelle steckt danach in der Geometrie; eine Ablage bräuchte Aufbewahrungsfrist und Löschweg. Mit AN5 (Projektakte) neu bewerten |
| E-AN1-2 | DWG | **Nicht** in RA1 (E-A2); ein Konverter wäre ein eigener Baustein |
| E-AN1-3 | Koordinatensystem erkennen oder abfragen | **Erkennen** an der Größenordnung, Ergebnis anzeigen und im Grundstück festhalten. Eine Auswahl im Formular wäre eine Fehlerquelle mehr; falsch erkannt heißt „ohne Bezug“, und das schadet in AN1 nicht |
| E-AN1-4 | Zugriff des Architekten | Jeder angemeldete `architect` sieht **alle** Projekte mit Eigentümer (ein Büro, D15). Erst AN6 trennt nach Organisation und Person |
| E-AN1-5 | Gelände und Risiken bei georeferenziertem Upload | **Aus** in AN1. Sie kosten externe Aufrufe und hängen an einer geprüften Lage; AN5 schaltet sie mit der Georeferenzierung frei |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Erster Entwurf wollte die Kanteneinordnung neu bauen | Doppelte Fachlogik neben `classify` | 3.1: `classify` beherrscht `neighbour_coverage="none"` bereits; keine Änderung an der Einordnung |
| 2 | Zweistufiger Upload (erst hochladen, dann auswählen) braucht einen Zwischenspeicher mit Aufräumjob | Mehr Zustand, mehr Löschpflichten | 3.2: zustandslos, bei mehreren Konturen `422` mit Kandidaten und zweitem Aufruf mit `index` |
| 3 | „Client schickt die gewählten Koordinaten zurück“ wäre einfacher, aber die Herkunftsangabe (SHA-256) passte dann nicht mehr zur Geometrie | Falsche Nachvollziehbarkeit | 3.2: die Geometrie entsteht immer aus der Datei |
| 4 | Kanten ohne Einordnung als `street` zu setzen (wie am Rand des Einzugsgebiets) wäre „sicher“, verschöbe aber die Abstände an allen Seiten und erfände eine Straße | Baurahmen wäre falsch, nicht nur vorsichtig | 3.1: `other`, im Baurahmen eng ausgelegt und als `kind_unclear` markiert |
| 5 | Löschung und Auskunft einfach nach `platform` zu kopieren, hätte die Anfragedaten im Kern gebraucht | Grenzverstoß gegen AN0 | 3.4: Erweiterungsliste, Modul A meldet sich an |
| 6 | Ein Projekt-Cookie zusätzlich zur Mitarbeitersitzung zu setzen, hätte bei jedem neuen Projekt das vorige aus dem Cookie verdrängt | Verwirrender Zugriff, Projekte „verschwinden“ | 3.3: für Architekten kein Cookie |
| 7 | Die Schranke „3–40 Kanten“ aus Weg E auf Uploads anzuwenden, hätte jede Katasterausleitung mit Rundungen abgelehnt | Brauchbare Dateien abgewiesen | 3.2: Grenze auf Stützpunkte (2 000), Kanten entstehen aus `split_edges` |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Parzelle als Bilddatei mit Maßstabskalibrierung | Ohne Georeferenz und ohne Vektor bliebe jede Länge geschätzt | mit AN5 eine Kalibrierung samt Georeferenz kommt |
| Upload über den vorhandenen `PUT …/site` mit Koordinatenliste | Der Client bestimmte die Geometrie; Format-Fehler fielen erst im Browser auf | ein zweiter Client ohne Dateizugriff dazukäme |
| Eigene Tabelle `analysis_project` statt Eigentümer an `project` | Zwei Projektbegriffe, doppelte Zugriffsregel, G1–G3 müssten beide kennen | die Produkte fachlich auseinanderlaufen (dann mit AN6) |
| Organisation sofort als Tabelle | Kosten ohne Nutzen, solange ein Büro arbeitet (D15) | ein zweites Büro konkret bevorsteht (AN6) |

### 7.3 Bewusste Grenzen

Der Hinweisschlüssel `notice.upload` entsteht am Grundstück, wird aber in AN1 nirgends angezeigt: Die Analyse-Oberfläche trägt den Hinweis nach E-A5 dauerhaft im Fuß. Sonst: kein DWG, kein Bild, kein Shapefile; keine Löcher im Umriss (nur äußere Ringe); keine Zusammenführung mehrerer Konturen zu einem Grundstück (eine Kontur je Grundstück, E-A3); keine Georeferenzierung von Hand, kein Gelände, keine Risiken (AN5); keine Benennung, Notiz oder Archivierung von Projekten (AN5); keine Rechteverwaltung je Person oder Organisation (AN6).

### 7.1a Beim Bau gefunden

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | **Beide Stacks lokal im selben Netz, Dienste gleich benannt**: Docker legt je Dienstnamen einen Netz-Alias an, `api` zeigte damit auf **zwei** Container. Die Weiterleitung `/api` des Analyse-Web-Containers landete abwechselnd beim Hauskonfigurator – die Anmeldung „verschwand“, Flags und Projekte kamen aus der falschen Datenbank | Ein Produkt beantwortete Anfragen des anderen; die Anmeldung legte die Sitzung in der falschen Datenbank an | `compose.analyse.yaml`: Dienste heißen `api-analyse`, `worker-analyse`, `web-analyse`, `migrate-analyse`, `db-init-analyse`; `API_UPSTREAM` zeigt auf `api-analyse`. Auf Unraid gab es das Problem nie (eigene Netze je Stack) |
| 2 | `safe_next` ließ nur Ziele unter `/buero` zu und fiel sonst auf `/buero` zurück – im Analyse-Produkt gibt es das nicht: Nach der Anmeldung stand „Seite nicht gefunden“ | Das zweite Produkt war nach der Anmeldung unbenutzbar | `staff_home` und `staff_denied` je Produkt in `app/products.py`; `safe_next` prüft jetzt nur noch „relativ, kein Host“ (offene Weiterleitung bleibt ausgeschlossen). Die abgelehnte Anmeldung zeigt ihren Grund auch im Analyse-Rahmen |
| 3 | Der Baurahmen war nur für `manual_sketch` gesperrt; ein Grundstück aus einer Datei wäre in `resolve_rules` gelaufen – ohne Gemeinde, ohne Zone | Unklares Verhalten statt klarer Aussage „keine Regeln“ | `NO_RULES_ORIGINS` in `envelope/service.py`; Grund und Hinweis heißen wie die Herkunft (`upload`), `FREE_REASONS` in H2 ergänzt |
| 4 | Der Abbrechen-Knopf des Uploads nutzte den Schlüssel `cancel`, den es nur unter `site.selection.cancel` gibt | „cancel“ stand wörtlich in der Oberfläche | eigener Schlüssel `analyse.upload.cancel` |
| 5 | Lokal teilen sich beide Produkte den Cookie-Vorrat (`localhost`, nur andere Ports): Eine Anmeldung im einen Produkt verdrängt die im anderen | Nur störend beim Entwickeln; auf Unraid haben die Produkte eigene Hostnamen | in README (Stolperstellen) festgehalten, nicht behoben |
| 6 | `form_site` wies nur `manual_sketch` ab: Ein Grundstück aus einer **Datei** hätte sich durch ein Katastergrundstück ersetzen lassen | Herkunftswechsel nur in eine Richtung gesperrt (Widerspruch zu G28) | `SKETCH_ORIGINS` auch dort; neuer Test `test_cadastre_site_cannot_replace_an_upload`. Die Prüfung greift **nach** `parcel_not_found` – der Test setzt die Parzelle deshalb selbst ein |

**Prüflauf:** Backend 509 Tests (vorher 479), Frontend 147 (vorher 145), ruff, Format, mypy, Typprüfung, Lint und Build grün. Der vorhandene Test zu `safe_next` schrieb die alte Regel „nur `/buero`“ fest und wurde auf „jedes relative Ziel, kein Host“ umgestellt (UP11).

**Browserprüfung am 21.09.2026** (Analyse-Stack, Deutsch und Französisch, auch Telefonbreite): Anmeldung → Projekt anlegen → GeoJSON mit zwei Konturen in Lambert-93 hochladen → Auswahl mit Vorschau, Fläche und „mit Lage“ → größere Kontur übernommen (682 m², georeferenziert, Herkunftsangaben sichtbar) → vier Kanten als „Sonstige Grenze“ mit Warnung → Kante 1 als Straße gesetzt → Hauptstraße steht, die übrigen Kanten werden zu Seite und Hinten, Warnung verschwindet. Projektliste zeigt Bezeichnung, Herkunft, Fläche und Datum. Die Anmeldung im Hauskonfigurator landet unverändert auf `/buero`.

---

## 8. Nachtrag 21.09.2026: Parzelle aus einem PDF

**Auftrag des Nutzers:** „Es sollte auch möglich sein, PDF-Dateien hochzuladen, aus denen dann die Parzelle gelesen wird.“ Das hebt E-A2 auf („kein PDF-Plan mit Maßstabskalibrierung, erst mit AN5“). Festlegungen: ANNAHMEN UP13–UP16.

### 8.1 Vorgehen

Die Pläne, die ein Büro als PDF bekommt, sind fast immer **vektoriell**: der Auszug aus cadastre.gouv.fr („Extrait du plan cadastral“) und der aus dem CAD gedruckte Plan des Geometers. Darin stehen die Grenzen als Zeichenpfade. Daraus folgt der Weg:

1. Linien und Texte lesen (`pdfminer.six`, MIT; PyMuPDF scheidet wegen AGPL aus).
2. Alle Linien der ersten Seite mit Linien zu Flächen schließen (`unary_union` + `polygonize`); Kandidat ist der Außenring jeder Fläche.
3. Maßstab aus dem Text, sonst von Hand; Punkte → Meter mit `0,0254 / 72 × Maßstab`.
4. Blattrahmen verwerfen (enthält mehr als 12 Flächen), Parzellennummern zuordnen, benannte Flächen zuerst.
5. Wie bei DXF: mehrere Kandidaten → Auswahl, jetzt in einer **Übersicht**, in der die Parzelle zwischen ihren Nachbarn angeklickt wird (`outline_overview`, gemeinsamer Ursprung), mit Liste als Weg ohne Maus.

Gescannte PDFs enthalten keine Linien; sie werden mit `upload_pdf_no_vector` abgewiesen. Sie ließen sich nur über Bilderkennung lesen (Claude API) – das ist eine Kostenentscheidung und braucht den Schlüssel (8.3).

### 8.2 Prüfung

- **Einheitstests** (`test_site_pdf_domain.py`, PDFs mit WeasyPrint im Test gesetzt): Ausgabemaßstab vor Erfassungsmaßstab, Maßstab von Hand, kein und zwei Maßstäbe, Scan, Blattrahmen mit 16 Parzellen, schiefes Viereck bei 1:200 gegen die Trapezformel, Maßstabstexte (auch Datum „21/09/2026“ ist keiner).
- **Integration** (`test_site_upload.py`): Auswahl und Übernahme mit Herkunft (`format`, `scale`, `scale_source`, `page`), Maßstab fehlt/zweideutig, Scan.
- **Realistischer Auszug aus echten Daten**: AD 65 mit Umgebung aus dem Kataster von Treillières bei 1:500 gesetzt – 22 Parzellen, 23 Gebäude mit **458 Schraffurlinien**, Rahmen, Kopf mit „Échelle d'origine : 1/1000 — Échelle d'édition : 1/500“, Karte auf Seite 2. Gelesen in **0,33 s**, Maßstab 1:500 aus dem Text, 39 Kandidaten, davon 14 mit Nummer; AD 65 mit **926,1 m² – gleich der Katasterfläche** (Abweichung 0,00 %).
- **Browser** (Analyse-Stack, Französisch): PDF gewählt → Maßstabsfeld erscheint → 39 Flächen, „Échelle 1:500 lue dans le plan“ → Parzelle 65 im Plan angeklickt → Grundstück 926,1 m² mit vier Kanten (46,2 / 20,0 / 46,2 / 20,1 m), Herkunft zeigt Datei und Maßstab.

### 8.3 Grenzen

- **Scans**: nicht lesbar (UP16). Nächster Ausbau wäre Bilderkennung über die Claude API; vorher zu klären: Budget je Aufruf und der Schlüssel (HANDOFF Priorität 1).
- **Nicht maßstäblich gedruckte PDFs** („an Seite anpassen“) ergeben falsche Maße und lassen sich nicht erkennen; die Oberfläche bittet um den Vergleich mit der Katasterfläche.
- **Keine Lage, Norden oben**: Rahmenkoordinaten in Lambert-93 werden nicht ausgewertet (AN5).
- **Eine Seite**: Geometrie nur von der ersten Seite mit Linien; Pläne mit mehreren Blättern in verschiedenen Maßstäben werden nicht zusammengesetzt.
- **Kurven** werden durch ihre Endpunkte ersetzt – für Flurstücksgrenzen unerheblich, für runde Grenzen (selten) ungenau.
- Echte Auszüge von cadastre.gouv.fr lagen nicht vor; geprüft wurde an einem nachgebauten Auszug aus den echten Katasterdaten. Der erste echte Auszug aus dem Büro ist die nächste Gegenprobe.

### 8.4 Prüfprotokoll

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Katasterauszüge nennen **zwei** Maßstäbe (Erfassung und Ausgabe) | Ohne Unterscheidung wäre jeder echte Auszug „zweideutig“ – oder bei 1:1000 statt 1:500 viermal zu groß | Das letzte Stichwort vor der Zahl entscheidet („édition“ gegen „origine“) |
| 2 | Das Muster `1/…` traf auch Datumsangaben („21/09/2026“ enthält „1/09“) | Falscher Maßstab 1:2026 möglich | keine Ziffer oder `/` direkt davor oder danach |
| 3 | Gebäude liegen als Loch in der Parzellenfläche | Die Parzelle wäre um die Gebäude zu klein | Kandidat ist der **Außenring** jeder Fläche |
| 4 | Texte in Form-XObjects fasst `pdfminer` ohne `all_texts` nicht zu Zeilen zusammen | Parzellennummern fehlten bei manchen Erzeugern | `LAParams(all_texts=True)` |
| 5 | Beim zweiten Aufruf (Übernahme) hätte die Oberfläche den gelesenen Maßstab als „angegeben“ mitgeschickt | Herkunft falsch: `scale_source = input` statt `file` | Nur ein von Hand eingegebener Maßstab geht mit |
| 6 | Die Fehlercodes aus AN1 (`upload_invalid` usw.) hatten keine Übersetzung im Backend | Der Titel der Fehlermeldung war der rohe Schlüssel | Texte in `app/platform/locales/*.json`, zusammen mit den drei neuen Codes |
