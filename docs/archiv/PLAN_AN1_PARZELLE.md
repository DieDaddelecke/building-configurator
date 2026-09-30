# AN1 – Parzelle ohne Kataster (Emprise Analyse)

> **Status:** geplant und umgesetzt am 20./21.09.2026, Nachtrag PDF am 21.09.2026, Konturen von Hand zusammenstellen am 28.09.2026 (Kapitel 9), kurze Stücke zu Kanten zusammenführen am 28.09.2026 (Kapitel 10), Beschriftungen als Umrisse übergehen am 28.09.2026 (Kapitel 11) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN1), 8.1 Nr. 2–4 und 10 · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN1 (Präfix `UP`)
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

## 9. Nachtrag 28.09.2026: Konturen von Hand zusammenstellen

**Auftrag des Nutzers:** „Beim Auswählen der Parzellen nach dem Upload gibt es Parzellen, die falsch analysiert werden – die Konturen stimmen nicht unbedingt mit den tatsächlichen Parzellen überein. Füge eine Option zur händischen Korrektur hinzu – es sollten Konturen hinzu- und abgewählt werden können.“ Festlegung: ANNAHMEN UP17.

### 9.1 Befund an echten Auszügen

Zwei echte „plans cadastraux normalisés“ von cadastre.gouv.fr (1:500) durch `pdfplan` gelesen:

- **Fremde Linien zerschneiden Parzellen.** Über den Plan läuft eine Kreislinie; sie teilt Parzelle 144 in zwei Flächen (865 und 574 m²), ebenso 638, 840, 961 und andere. Keine Fläche ist dann die ganze Parzelle – mit einer einzigen Wahl lässt sie sich nicht übernehmen.
- **Parzellennummern sind Umrisse, kein Text.** Die Ziffern stehen als Zeichenpfade im PDF; `pdfminer` findet nur Einzelziffern der Randbeschriftung. Die Kandidaten tragen deshalb keine Nummer, und die Umrisse der Ziffern ergeben viele kleine Flächen (719 bzw. 2 132 unter 20 m²).
- Kopf und Legende des Blatts liefern große Rechtecke (600, 889, 1 200 m²) als Kandidaten.

Die zweite und dritte Beobachtung bleiben Grenzen (9.4); die erste behebt dieser Nachtrag.

### 9.2 Festlegungen

- **Mehrere Konturen wählen:** Ein Klick nimmt eine Fläche in die Auswahl, ein zweiter nimmt sie heraus; ohne Maus über eine Liste „Fläche hinzufügen“ und je gewählter Fläche „Entfernen“. Das Grundstück ist die **Vereinigung** der gewählten Flächen.
- **Vereinigen wie beim Kataster** (`outline.merge_parcels`, Spez. 5.1.3): Spalten bis 2 × 2 cm schließen, vereinfachen, ein zusammenhängendes Polygon (`422 site_not_contiguous`). **Löcher werden gefüllt** wie bei jedem Kandidaten (UP13): Liegt ein Gebäude auf der fremden Linie, fällt es in keine der Teilflächen und bliebe sonst als Loch zurück.
- **Enthaltene Flächen zählen mit:** Eine Fläche innerhalb einer gewählten (Gebäude in der Parzelle) ist schon Teil des Grundstücks; die Übersicht zeigt sie mit an, die Flächensumme zählt sie nicht doppelt.
- **Schranken:** höchstens 20 Flächen; Ergebnis 20–50 000 m² wie jeder Kandidat (G28); Flächen mit und ohne Lage lassen sich nicht mischen (`422 upload_outlines_incompatible`).
- **API:** Das Formularfeld `index` darf mehrfach stehen (Liste, jede Zahl ≥ 0). Mit einer Zahl verhält sich alles wie bisher.
- **Herkunft (L3):** `source_info.indices` nennt die vereinigten Flächen, `name` ihre Nummern mit „+“; die Projektseite zeigt „aus n Flächen zusammengesetzt“.
- **Fläche vor der Übernahme:** Die Oberfläche zeigt die Summe der gewählten Flächen ohne die enthaltenen, mit „≈“; maßgeblich ist die Fläche nach der Übernahme (Spalten geschlossen, vereinfacht).

### 9.3 Arbeitsschritte

1. `site/domain/upload.py`: `MAX_SELECTED`, `merge_candidates` (über `merge_parcels`, Löcher füllen, Schranken, Lage prüfen).
2. `site/service.py` und `site/api.py`: `index` als Liste, Herkunft; Problemtexte de/fr.
3. `openapi.json`, `schema.d.ts`.
4. Frontend: `api/site.ts`, `KonturWahl` (Mehrfachwahl, enthaltene Flächen, Liste), `ParzelleHochladen` (Summe, „Auswahl übernehmen“), Herkunft auf der Projektseite; Texte de/fr.
5. Tests: Einheit (`merge_candidates`), Integration (Auszug mit einer Linie quer durch Parzelle und Haus → beide Teile ergeben 600 m² mit vier Kanten; nicht zusammenhängend; unbekannte Fläche), Komponente (hinzu- und abwählen, Liste, Summe ohne enthaltene Fläche).
6. Browser am echten Auszug: Parzelle 144 aus ihren zwei Teilen.

### 9.4 Grenzen

- Fehlt eine Grenzlinie oder schließt sie nicht, gibt es keine Fläche, die sich wählen ließe; zwei Parzellen ohne trennende Linie lassen sich nicht teilen. Dafür bleibt „Zeichnen und bemaßen“.
- Kleine Flächen unter 20 m² (Schuppen auf der Grenze) sind keine Kandidaten und lassen sich nicht hinzunehmen; Gebäude innerhalb der Parzelle gehören über das Füllen der Löcher ohnehin dazu.
- Eine eingeschlossene fremde Fläche (Enklave) lässt sich nicht ausschneiden, weil Löcher gefüllt werden.
- Nummern als Umrisse und Kandidaten aus Kopf und Legende: unverändert (9.1); die Nummer ließe sich nur mit Bilderkennung lesen (AN7).
- **Beschriftungen als Umrisse kerben die Flächen ein** (9.5, beim Bau Nr. 2): Wo Buchstaben einer Beschriftung eine Grenze kreuzen, entstehen kleine Einbuchtungen und damit viele kurze Kanten – das trifft jede Fläche aus einem solchen PDF, auch eine einzeln gewählte. Behoben in Kapitel 11 (UP19), mit anderer Regel als in 9.5 vorgeschlagen.

### 9.5 Prüfprotokoll

**Vor dem Bau:**

| Nr. | Befund | Folge | Festlegung |
|---|---|---|---|
| 1 | Die Vereinigung zweier Teilflächen lässt ein Loch, wo ein Gebäude auf der fremden Linie liegt (es ist in beiden nur eine Einbuchtung) | Grundstück mit falschem Loch, Fläche zu klein | Löcher füllen, wie beim einzelnen Kandidaten |
| 2 | Kandidaten sind Außenringe und können einander enthalten (Parzelle und ihr Gebäude) | Eine einfache Summe zählte das Gebäude doppelt | Enthaltene Flächen zählen nicht; die Übersicht zeigt sie als Teil der Auswahl |
| 3 | Die fremde Linie hinterlässt auf dem Umriss Stützpunkte ohne Knick | Zusätzliche, geteilte Kanten | `merge_parcels` vereinfacht (5 cm), wie beim Kataster |
| 4 | Aus DXF oder GeoJSON können Konturen mit und ohne Lage kommen | Vereinigung zweier Koordinatenräume ohne Sinn | `upload_outlines_incompatible` |
| 5 | Nach jedem Klick den Server rechnen lassen (Vorschau) hieße, die Datei jedes Mal neu zu senden und zu lesen (bis 20 MB, ein Plan mit 13 000 Linien) | Träge Bedienung | Summe im Browser, exakte Fläche nach der Übernahme |

**Geprüfte Alternativen:**

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Kleinste Flächen (Zellen der Zeichnung) statt Außenringen wählbar machen | Schraffuren und Ziffernumrisse zerlegen Gebäude und Nummern in Hunderte Splitter; jede Parzelle müsste man aus vielen Zellen zusammenklicken | Pläne ohne Schraffur und Textumrisse die Regel wären |
| Teilflächen selbst zusammenführen, wenn die trennende Linie keine Parzellengrenze ist | Im PDF unterscheidet nichts sicher eine Grenze von einer fremden Linie (Kreis, Maßkette, Straßenrand) | die Linienstile verlässlich wären |
| Eckpunkte des Umrisses von Hand verschieben | Deckt auch fehlende Linien ab, ist aber ein eigener Editor; die Aufgabe ist Hinzu- und Abwählen | Linien häufig fehlen – dann als Weiterentwicklung von „Zeichnen und bemaßen“ |

**Beim Bau gefunden:**

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Die Summe vor der Übernahme mit einer Nachkommastelle („≈ 1.440,0 m²“) | Scheingenau neben „≈“ | Auf ganze m² gerundet; die Einzelflächen behalten eine Nachkommastelle |
| 2 | Im echten Auszug sind Beschriftungen („Sente rurale“, „DEVANT LA TUILERIE“) und Nummern als **gefüllte Umrisse ohne Strich** gezeichnet, die Grenzen als **Striche**. Die Buchstaben kerben die Flächen ein: Parzelle 144 aus zwei Teilen hat 32 Kanten, viele unter 1 m | Lange Kantenliste, jede Kante will eingeordnet sein | **Behoben in Kapitel 11** mit anderer Regel (Farbe und Größe, 11.1). Ursprünglicher Vorschlag: nur gestrichene Pfade zu Flächen schließen, gefüllte ohne Strich übergehen, mit Rückfall auf alle Pfade, wenn dann keine plausible Fläche bleibt. Probe am Auszug: 3 906 → 751 Linien, 849 → 251 Flächen, Buchstaben- und Ziffernflächen und Kerben verschwinden; auch die Gebäude fallen weg (ebenfalls nur gefüllt), was für die Parzelle nichts ändert, weil Kandidaten Außenringe sind. Vor dem Umbau am Original zu klären: In der Mitte des Blatts verschmelzen zwei Flächen zu einer (2 020 m²) – ob dort eine Grenze nur gefüllt gezeichnet ist, war am PDF nicht zu sehen |

**Prüflauf:** Backend 629 Tests mit `TEST_S3=1` (vorher 623), ruff, Format und mypy grün; neu 5 Einheitstests (`merge_candidates`) und ein Integrationstest (Auszug mit einer Linie quer durch Parzelle 65 und ihr Haus: kein Kandidat mit 600 m², die Teile 210 und 342 m² ergeben 600 m² mit vier Kanten; nicht zusammenhängend, unbekannte Fläche, 21 Flächen). Frontend 196 Tests (vorher 194; Mehrfachwahl mit enthaltener Fläche, Herkunft „aus 2 Flächen“), Lint, Typprüfung und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt (`index` als Liste).

**Browserprüfung am 28.09.2026** (Analyse-Stack mit neu gebauten Images, echter „plan cadastral normalisé“ 1:500): 130 Flächen; die zwei Teile von Parzelle 144 im Plan angeklickt (865,4 und 574,2 m²) → beide hervorgehoben, darunter als Auswahl, „2 Flächen zusammen, ≈ 1.440 m²“ → „Auswahl übernehmen“ → Grundstück 1.441,1 m², Herkunft „aus 2 Flächen der Datei zusammengesetzt“, Maßstab 1:500 angegeben. Das Testprojekt danach gelöscht.

## 10. Nachtrag 28.09.2026: Kurze Stücke zu Kanten zusammenführen

**Auftrag des Nutzers:** „Die Art und Weise, wie Katasterpläne aufgebaut sind, bedingt leider oft extrem viele Punkte auf sehr engem Raum. Gibt es eine Möglichkeit, Linien zusammenzuführen, wenn Punkte zu eng beieinander liegen?“ (mit Bildschirmfoto: Kantennummern 13–17 übereinander). Nach Probe und Vorschlag: „Ja, setze das so um.“ Festlegung: ANNAHMEN UP18.

### 10.1 Befund

Parzelle 144 aus dem echten Auszug (zwei Teile, 9.1) hat **32 Kanten, 10 davon unter 1 m und 17 unter 2 m**. Die kurzen Stücke kommen aus drei Quellen:

- **Kerben der Beschriftungen** (9.5, beim Bau Nr. 2): Wo Buchstaben eine Grenze kreuzen, springt der Umriss für Bruchteile eines Meters ein und wieder zurück (etwa 0,90 m hinein, 0,46 m quer, 0,94 m zurück).
- **Zickzack auf einer geraden Grenze:** fünf Stücke von 0,30–1,02 m, die kaum von der Geraden abweichen, aber je mehr als 5° knicken (`MERGE_ANGLE_DEG`).
- **Abgerundete Ecken:** drei Stücke von je etwa 1,5 m.

`split_edges` beendet eine Kante bei jedem Knick über 5°, gleich wie kurz das Stück ist. Jede Kante erhält eine Nummer in der Mitte; bei Stücken unter 1 m liegen die Nummern übereinander (Bildschirmfoto), und jede Kante will eingeordnet sein.

### 10.2 Festlegungen

- **Stücke sammeln, dann die Richtung prüfen:** Beim Bilden der Kanten werden die Stücke ab dem Ende der laufenden Kante gesammelt, bis ihr Endpunkt mindestens die **Schwelle** entfernt liegt. Erst dieser gesammelte Schritt wird wie bisher geprüft: Weicht seine Richtung um weniger als 5° von der Sehne der laufenden Kante ab, gehört er dazu, sonst beginnt mit ihm eine neue Kante. Ein kürzerer Rest am Ende des Rings gehört zur laufenden Kante.
- **Folgen:** Kerben und Zickzack auf einer Geraden verschwinden in der Kante, zu der die Gerade gehört; zwei Kanten, die nur eine Kerbe trennt, werden eine. Eine abgerundete Ecke aus kurzen Stücken wird eine eigene Kante von mindestens der Schwelle; ein Rest unter der Schwelle gehört zur folgenden Kante. Eine Kante mit einer Sehne unter der Schwelle bleibt nur, wo ein Ring zu klein für drei solche Kanten ist (Rückfall) oder der Rest am Ende des Rings zurückbiegt (10.5, beim Bau Nr. 2).
- **Kein Punkt wird verschoben oder gelöscht.** Umriss, Fläche und Stützpunkte bleiben, wie die Datei sie liefert; die Kante ist ein Linienzug über alle Punkte (Länge entlang des Zugs, Richtung und Normale aus der Sehne, wie bei jeder Kante mit mehreren Punkten).
- **Ecke als Anfang:** Der Ring beginnt wie bisher an der Ecke mit der stärksten Richtungsänderung; die Richtungen werden dafür zu den Punkten gemessen, die mindestens die Schwelle entfernt liegen, damit eine Kerbe nicht als Ecke zählt.
- **Schwelle:** 2 m (`UPLOAD_SHORT_PIECE_M`); bei PDF mindestens 1 mm auf dem Papier (`UPLOAD_SHORT_PIECE_PAPER_M` × Maßstab), weil Beschriftungen mit dem Maßstab wachsen: 1:500 und 1:1000 → 2 m, 1:2500 → 2,5 m, 1:5000 → 5 m.
- **Rückfall:** Bleiben auf einem Ring weniger als drei Kanten, wird er wie bisher zerlegt.
- **Geltung:** nur für hochgeladene Grundstücke (`origin = upload`), nur beim Bilden. Frei gezeichnete Grundstücke (Kanten ab 1 m gewollt) und Grundstücke aus dem Kataster (Hauskonfigurator) bleiben unverändert (Schwelle 0 ergibt genau die bisherige Zerlegung). Bestehende Projekte behalten ihre Kanten und Einordnungen.
- **Herkunft (L3):** `source_info.short_piece_m` hält die Schwelle fest; die Projektseite nennt „Stücke unter n m zusammengefasst“.

### 10.3 Arbeitsschritte

1. `site/domain/tolerances.py`: `UPLOAD_SHORT_PIECE_M`, `UPLOAD_SHORT_PIECE_PAPER_M`.
2. `site/domain/edges.py`: `split_edges(polygon, short_piece_m=0.0)`; Sammeln, Ecke als Anfang, Rückfall.
3. `site/domain/upload.py`: `short_piece_m_for(scale)`.
4. `site/service.py`: Schwelle beim Hochladen durchreichen und in die Herkunft schreiben.
5. Frontend: Herkunft auf der Projektseite; Texte de/fr.
6. Tests: Einheit (Schwelle 0 wie bisher; Kerbe und Zickzack → vier Kanten mit allen Punkten; abgerundete Ecke → eigene Kante; fein abgetasteter Kreis → mehrere Kanten; Rückfall; Schwelle je Maßstab), Integration (Upload mit Kerbe → vier Kanten, Herkunft), Komponente (Herkunft).
7. Browser am echten Auszug: Parzelle 144.

### 10.4 Grenzen

- Die Kerben bleiben als Knicke innerhalb einer Kante sichtbar und gehen in Länge und Fläche ein; Kerben aus Beschriftungen beseitigt Kapitel 11 (UP19), andere bleiben.
- Ein echter Versprung unter der Schwelle (etwa eine um 1,5 m versetzte Grenze in einem Geometerplan) wird Teil einer Kante und bekommt deren Einordnung; die Geometrie bleibt erhalten.
- Eine abgerundete Ecke zwischen Straße und Nachbar ist eine eigene Kante und will eingeordnet sein.

### 10.5 Prüfprotokoll

**Vor dem Bau:**

| Nr. | Befund | Folge | Festlegung |
|---|---|---|---|
| 1 | Die im Chat beschriebene einfachste Regel („ein Stück unter 2 m beendet keine Kante, es gehört zur Kante davor“) hängt jedes kurze Stück an, auch eine ganze Kurve aus 1-m-Sehnen | Eine fein gezeichnete Kurve (Geometerplan, DXF) ginge vollständig in der Kante davor auf; ein Umriss nur aus kurzen Stücken (Rundung) würde **eine** Kante | Stücke bis zur Schwelle sammeln, dann die Richtung prüfen (10.2). Für Kerben und Zickzack gleiches Ergebnis; eine Rundung wird eigene Kante statt Teil der Kante davor – so dem Nutzer berichtet |
| 2 | Die bisherige Wahl des Anfangs (stärkster Knick) kann in einer Kerbe liegen (Knicke bis 180°) | Die erste Kante begänne mitten in einer Kerbe; die Kerbe teilte die Gerade in zwei Kanten | Richtung zum Punkt in Schwellenabstand messen (10.2) |
| 3 | Bei 1:5000 ist die Schwelle 5 m; ein kleines Grundstück könnte weniger als drei Kanten behalten | Einordnung ohne Ecken | Rückfall auf die bisherige Zerlegung |
| 4 | Die Schwelle später zu ändern, änderte die Kanten neuer Uploads, nicht der bestehenden | Zwei Projekte aus derselben Datei mit verschiedenen Kanten | Schwelle in der Herkunft (`source_info.short_piece_m`) |
| 5 | `_store_sketch_site` gibt bei gleichem Umriss, gleicher Herkunft und Anschrift das vorhandene Grundstück zurück | Eine erneut hochgeladene Datei eines Altprojekts bekommt die neuen Kanten nicht | Gewollt: Kanten und Einordnungen bestehender Projekte bleiben (10.2) |

**Geprüfte Alternativen:**

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Punkte ausdünnen (Douglas-Peucker) | Probe an Parzelle 144: bei 0,2 m noch 26 Kanten, erst bei 1 m keine Kurzkante mehr – dann weicht die Fläche um 35 m² ab | die kurzen Stücke Messrauschen wären statt Kerben |
| Einkerbungen morphologisch schließen (Puffer hin und zurück) | Bei 0,25 m nur die schmalsten Kerben (27 Kanten), bei 0,5 m noch 24 Kanten, Fläche +1 m²; ändert den Umriss | es nur um Spalten ginge |
| Kanten von Hand zusammenlegen und teilen | Eigener Editor; die Mehrzahl der Fälle löst die Regel ohne Zutun | die Schwelle in der Praxis oft falsch greift – dann als Ergänzung |
| Auch für den Hauskonfigurator (Kataster) | Kataster-Grundstücke kommen aus Etalab ohne Beschriftungskerben; die Einordnung dort nutzt Nachbarn je Kante und ist getestet | dort ähnliche Kurzkanten auffallen |

**Beim Bau gefunden:**

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Eine abgerundete Ecke aus drei Stücken von rund 1,5 m wird nicht ganz eine Kante: Die ersten zwei Stücke erreichen die Schwelle und bilden sie, das dritte bleibt als Rest unter der Schwelle und geht in die folgende Kante (Parzelle 144 oben links: Kante 11 aus zwei Stücken, das dritte beginnt Kante 12) | Die Rundung verteilt sich auf zwei Kanten; die Nummern liegen trotzdem mindestens 2 m auseinander | Hingenommen und in 10.2 benannt; ein Einheitstest hält das Verhalten fest |
| 2 | Auf beiden echten Blättern (280 Flächen) bleiben 34 Kanten mit einer Sehne unter der Schwelle; 33 davon in Flächen, die zu klein für drei Kanten ab 2 m sind (Rückfall), eine in einer Fläche von 42 m², deren Rest am Ringende zurückbiegt | Nur Kleinflächen (Gebäude, Ziffern), keine Parzelle | Hingenommen; 10.2 genauer gefasst |

**Probe mit dem eingebauten Code** (beide echten Auszüge, alle Flächen): 1:500, Schwelle 2 m, 130 Flächen: 1 520 → 833 Kanten, Kanten mit Sehne unter 2 m 698 → 5. 1:1000, Schwelle 2 m, 150 Flächen: 2 597 → 1 187 Kanten, 1 413 → 29. In jeder Fläche bleibt jeder Stützpunkt Teil genau einer Kante. Parzelle 144: 32 → 13 Kanten, 1 441,1 m² unverändert.

**Prüflauf:** Backend 636 Tests mit `TEST_S3=1` (vorher 629), ruff, Format und mypy grün; neu 5 Einheitstests zu `split_edges` (ohne Schwelle wie bisher; Kerbe und Zickzack → vier Kanten mit allen Punkten und derselben Länge; abgerundete Ecke; Kreis aus 60 Sehnen → 30 Kanten statt 60; Rückfall), einer zu `short_piece_m_for` und ein Integrationstest (GeoJSON mit Kerbe → vier Kanten, Herkunft; die Herkunft der Vereinigung nennt die Schwelle ebenfalls). Frontend 197 Tests (vorher 196; Herkunft nennt die Schwelle), Lint, Typprüfung und Build grün. `openapi.json` unverändert (`source_info` ist ein freies Objekt).

**Browserprüfung am 28.09.2026** (neu gebaute Images, echter Auszug 1:500): Parzelle 144 aus ihren zwei Teilen übernommen → 13 Kanten, keine Nummern mehr übereinander, 1.441,1 m²; Herkunft „Kanten: Stücke unter 2 m zu einer Kante zusammengefasst“. Bei schmalem Fenster berühren sich die Nummern der Kanten 4 und 5 (4,2 und 3,5 m) knapp, bleiben aber lesbar. Das Testprojekt danach gelöscht.

## 11. Nachtrag 28.09.2026: Beschriftungen als Umrisse übergehen

**Auftrag des Nutzers:** „Kerben der Beschriftung kannst du gerne bearbeiten“ (zu 9.5, beim Bau Nr. 2, und 10.4). Festlegung: ANNAHMEN UP19.

### 11.1 Befund

- **Der Vorschlag aus 9.5 verliert Grenzen.** Nur gestrichene Pfade zu Flächen zu schließen, lässt in der Blattmitte des Auszugs Parzelle 1115 und ihre Nachbarin zu einer Fläche von 2 020 m² verschmelzen: Die Grenze zwischen beiden ist dort nur die Kante eines gefüllten Gebäudes.
- **Farbe und Größe trennen sauber.** Auf beiden echten Auszügen sind alle nur gefüllten Pfade in Schwarz kleiner als 10 mm auf dem Papier (258 bzw. 870 Pfade – Buchstaben und Ziffern, die größten sind die Großbuchstaben des Flurnamens). Gebäude sind orange oder hellgelb gefüllt (3–64 mm), Wasser blau, Masken weiß. Grenzen sind gestrichen.

### 11.2 Festlegungen

- **Beschriftung:** Ein Pfad gilt als Beschriftung, wenn er nur gefüllt ist (ohne Strich), dunkel (Grau, RGB oder CMYK mit höchstens 25 % Helligkeit; ohne Farbangabe schwarz wie im PDF vorgegeben) und höchstens 10 mm auf dem Papier misst (längere Seite des umschließenden Rechtecks). Seine Strecken gehen nicht in die Flächen ein.
- **Rückfall:** Ergibt sich ohne die Beschriftungen keine plausible Fläche, zählen alle Pfade wie bisher.
- Texte mit Textschicht (Parzellennummern als Text) bleiben unberührt; Nummern als Umrisse bleiben unlesbar (9.4).
- Gilt für jedes PDF, nicht nur für Auszüge von cadastre.gouv.fr. Bestehende Projekte behalten ihren gespeicherten Umriss.

### 11.3 Arbeitsschritte

1. `site/domain/pdfplan.py`: `_is_glyph`, `_is_dark`, `PdfPage.glyph_segments`; `read_plan` mit Rückfall.
2. Tests: Einheit (Helligkeit in Grau, RGB und CMYK; Auszug mit einer kleinen schwarzen, einer großen schwarzen und einer kleinen farbigen Form auf der Grenze; Rückfall), Integration (Kandidat und Grundstück ohne Kerbe).
3. Probe an beiden echten Auszügen, Browser an Parzelle 144.

### 11.4 Grenzen

- Zeichnet ein Plan kurze Grenzstücke als kleine schwarze Flächen statt als Linien, fehlen diese Stücke; bleibt trotzdem eine plausible Fläche, greift der Rückfall nicht. Auf den echten Auszügen nicht beobachtet.
- Kleine schwarz gefüllte Gebäude (unter 10 mm, bei 1:500 unter 5 m) sind keine eigene Fläche mehr; für die Parzelle ohne Belang, weil Kandidaten Außenringe sind.
- Einbuchtungen aus anderen Ursachen (Gebäudekanten auf der Grenze, fremde Linien) bleiben; dafür bleiben die Konturwahl (UP17) und das Zusammenführen kurzer Stücke (UP18).

### 11.5 Prüfprotokoll

**Vor dem Bau:**

| Nr. | Befund | Folge | Festlegung |
|---|---|---|---|
| 1 | Nur gestrichene Pfade (Vorschlag 9.5) | Eine echte Grenze geht verloren (11.1) | Verworfen; Farbe und Größe entscheiden |
| 2 | Die Großbuchstaben des Flurnamens messen bis rund 9 mm, die kleinsten Gebäude ab 3 mm | Allein mit der Größe wären kleine Gebäude Schrift | 10 mm **und** dunkel; Gebäude sind farbig |
| 3 | Andere PDFs geben Farben in Grau oder CMYK an, manche gar nicht | RGB allein erkennte dort keine Schrift | Helligkeit aus allen drei Farbräumen; ohne Angabe schwarz |
| 4 | Die Kerben fallen weg, die Fläche ändert sich (Parzelle 144 +1,1 m², auf Blatt 2 bis +24 m²) | Andere Fläche als bisher | Gewollt: Das ist die Fläche ohne Schrift; bestehende Projekte behalten ihren Umriss |

**Geprüfte Alternativen:**

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Nur gestrichene Pfade | Verliert Grenzen, die nur als Gebäudekante gezeichnet sind (11.1) | Grenzen immer gestrichen wären |
| Kerben geometrisch schließen (Puffer hin und zurück) | Schließt auch echte Einbuchtungen, breite Buchstaben nicht (10.5) | es nur um Spalten ginge |
| Buchstaben an ihrer Form erkennen (Kurven, Innenringe) | Aufwendig; Farbe und Größe genügen auf den echten Auszügen | Pläne Schrift in Gebäudefarben setzten |

**Probe mit dem eingebauten Code** (beide echten Auszüge):

| | Blatt 1 (1:500) | Blatt 2 (1:1000) |
|---|---|---|
| Strecken | 3 906 → 1 010 | 13 120 → 2 561 |
| Flächen | 849 → 484 | 2 333 → 1 060 |
| Kandidaten (vor der Kappung auf 150) | 130 → 130, keine verschmolzen | 332 → 331, keine verschmolzen: 320 gleich, 8 größer (Kerben gefüllt, bis +24 m²), 4 schmale Streifen (1–2 m breit) zwischen einer Linie und einem Schriftzug fallen weg |
| Kanten aller Kandidaten mit Schwelle (UP18) | 833 → 783 | 1 187 → 1 081 |

Parzelle 144: Teile 866,5 und 575,7 m² (vorher 865,4 und 574,2), zusammen 1 442,2 m² (+1,1 m²); 18 statt 32 Kanten ohne Schwelle, 12 statt 13 mit. Der verbliebene Knick an Kante 11 kommt von der Kreislinie, nicht von Schrift.

**Prüflauf:** Backend 649 Tests mit `TEST_S3=1` (vorher 636), ruff, Format und mypy grün; neu die Einheitstests zur Helligkeit (10 Fälle), zu kleinen, großen und farbigen Formen auf der Grenze und zum Rückfall sowie ein Integrationstest (Buchstabe auf der Grenze von 65: Kandidat 600 m², vier Kanten). Frontend unverändert.

**Browserprüfung am 28.09.2026** (neu gebaute Images, echter Auszug 1:500): die Teile von Parzelle 144 mit 866,5 und 575,7 m² gewählt, „2 Flächen zusammen, ≈ 1.442 m²“ → Grundstück 1.442,2 m² mit 12 Kanten, ohne Kerben an den Kanten 3 und 6. Das Testprojekt danach gelöscht.
