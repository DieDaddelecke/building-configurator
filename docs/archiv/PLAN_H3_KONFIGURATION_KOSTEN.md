# H3 Konfiguration und Kosten – Plan für die Umsetzung

> **Umsetzungsstand 19.09.2026:** Alle Arbeitsschritte umgesetzt (Backend `backend/app/configuration`, Migration 0010, Oberfläche `/konfigurator` mit den Schritten Linie, Optionen, Vorentwurf und der Kostenleiste, Felder der Katalogpflege); 58 Einheitstests und 24 Integrationstests des Backends, 41 neue Tests der Oberfläche, im Browser auf dem Testgrundstück AD 65 geprüft. Festlegungen und Abweichungen in ANNAHMEN HK01–HK17. Offen: Playwright-Szenario, echte Preise und Typdateien (H1), Betrieb auf Unraid, V.
>
> **Entwurf vom 19.09.2026** zu Umsetzungsplan 3.9, Spezifikation 5.5.4–5.5.6, 5.6.4–5.6.6, 5.9.2, 5.9.3, 5.9.6. Entscheidungen des Nutzers in dieser Session: Abweichung HP03 bleibt (Terrasse, Carport, Zufahrt kommen mit H3), D12 und D13 bestätigt, **Terrasse 3 m tief mit der Breite der Gartenfassade und Preis je m²**, **Carport in beiden Größen (einstellig 3 × 5 m, zweistellig 6 × 5 m)**. D8 und D10 blieben ungefragt und werden nach Empfehlung genommen ([[feedback-plan-dann-umsetzen]]); sie stehen in `docs/ANNAHMEN.md` (Abschnitt H3, Präfix `HK`) und sind umkehrbar.

## 1. Ziel und Abgrenzung

**Ziel:** Auf den gewählten Typ und seine Lage (H2) folgen Ausstattungslinie und Optionen; der Server prüft die Auswahl, setzt Terrasse und Carport selbst, rechnet Flächen, Regelprüfung, RE2020-Status und einen Kostenkorridor. Alles ist Simulation (D11, L7), Preise erscheinen nur als Spanne (L1).

**In H3:**
- Linie und Optionen je Konfiguration (feste Versionen, L4), Anwendbarkeit je Typ, Ausschlüsse (Spez. 5.5.4), in der Linie enthaltene Optionen (Spez. 5.5.6).
- Optionsarten `terrace` und `carport` mit Maßen; Terrasse an der Gartenfassade, Carport an der Straßenkante, automatisch gesetzt; Zufahrt (Spez. 5.9.3).
- Flächen (Grundfläche, versiegelt, unversiegelt) und Regelprüfung der Option: Nebengebäude, Grundflächenzahl mit Carport und Terrasse, unversiegelter Anteil, Stellplätze, Fassaden- und Dachmaterial (Spez. 5.9.2).
- RE2020-Status mit Konformitätsaufpreis aus dem Befund je Typ und Linie (Spez. 5.9.6, reduziert nach Plan H1 3.8).
- Kostenkorridor aus Basispreis, Linienaufpreis, Optionen, Konformitätsaufpreis (Spez. 5.6.5); Mehrwertsteuer (D10).
- Himmelsrichtung der Fassaden mit Meridiankonvergenz (HP05).
- Kundenoberfläche: Schritte Linie, Optionen, Vorentwurf in `/konfigurator`, Kostenleiste, Terrasse und Carport im Lageplan.
- Katalogpflege: Art und Maße einer Option, Material einer Option und einer Linie; Absicherung der Veröffentlichungsreihenfolge (HANDOFF 4.5 Punkt 3), weil H3 die jeweils jüngste veröffentlichte Version liest.

**Nicht in H3:**
- Übergabe, Snapshot, Neuprüfung beim Absenden, Dossier: V.
- Photovoltaik-Belegung, Keller, `requires`-Ausdrücke, Ausführungen je Oberflächenkategorie und Mengen (`finish_delta`, `tiered`, `formula`): ohne Modell nicht berechenbar (Umsetzungsplan Kapitel 7, „Optionspreise: feste Spanne statt Mengen“); Keller und Photovoltaik bleiben Optionen ohne Geometrie.
- Raumprogramm nach Dachraum (Stufe 8), Standortpositionen im Korridor, Preisindex BT01.
- Freie Platzierung von Terrasse und Carport durch den Kunden.

## 2. Ausgangslage

- H1 kennt Linien (`package_version`: Bezeichnungen, Umfang, enthaltene Optionen), Optionen (`module_version`: Bezeichnungen, Ausschlüsse, `geometry_mode`) und einen Preiskatalog (Basispreis je Typ, Linienaufpreis je Typ, Optionsaufpreis je Typ; ein Wert je Zeile), dazu RE2020-Befunde je Typ und Linie. Alle Preise binden an die Identität, nicht an die Version (Plan H1 3.7). Ein Import legt die Preise im **Entwurf** des Katalogs an; erst `POST …/price-catalog/publish` macht sie für Kunden lesbar.
- H2 liefert `configuration` mit Typversion, Lage, Grenzschaltern und die Maschinerie für Flächen zulässiger Ursprünge: `part_surface`, `edge_requirement`, `presets`, `check_placement`. Die Abstandsregeln lassen sich nach Art des Baukörpers auswählen (`setbacks_for_edge(..., building_kind)`); H2 hat immer `main` benutzt.
- `annex`, `unsealed_min`, `parking`, `facade`, `max_footprint_ratio.terrace_counts_above_m` sind Regelarten der Regelwerke (G2, `rules/domain/kinds.py`); H2 wertet nur `roof`, `max_height`, `max_footprint_ratio` (Haus allein) und die Abstände aus.
- Lokal ist der Preiskatalog ein Entwurf, es gibt eine Linie (`confort`), eine Option (`pv`), keine Terrasse, keinen Carport. Ohne veröffentlichten Katalog gibt es keine Preise, also auch keine wählbare Linie (3.1).

## 3. Fachliche Festlegungen

### 3.1 Auswahl

- Gespeichert werden `package_version_id` und `modules` (Liste `{module_version_id}`, Spez. 4.4) an der Konfiguration. Wer neu wählt, bekommt die jüngste veröffentlichte Version; was schon gespeichert ist, behält seine Version (L4), auch zurückgezogen.
- **Anwendbar** ist eine Linie oder Option für einen Typ, wenn der **veröffentlichte Preiskatalog** dafür eine Zeile hat (Plan H1 3.2: „nur die für diesen Typ gültigen“). Eine Option ohne Preis wäre sonst still gratis. Gibt es keinen veröffentlichten Katalog, ist nichts wählbar (`catalog_unavailable`).
- **Wirksam** sind die ausdrücklich gewählten Optionen und die der Linie. Eine in der Linie enthaltene Option kostet nichts und wirkt trotzdem (eine Terrasse in der Linie liegt auf dem Plan). Die Wahl des Kunden bleibt gespeichert; wechselt er zu einer Linie ohne die Option, wird sie wieder berechnet (Spez. 5.5.6, Verhalten des Mockups). Eine in der Linie enthaltene Option wirkt auch dann, wenn der Preiskatalog für den Typ keine Zeile dafür hat (sie kostet ohnehin nichts); ausdrücklich wählbar ist sie ohne Zeile nicht.
- **Ausschlüsse** (`excludes_slugs`) gelten zwischen zwei wirksamen Optionen, von denen mindestens eine ausdrücklich gewählt ist. Zwei Optionen, die die Linie beide enthält, ignoriert die Prüfung: das ist ein Datenfehler des Büros, kein Fehler des Kunden (im Mockup enthält Signature beide Holzverschalungen). Konflikte werden nie still aufgelöst: `422 invalid_selection` mit allen Gründen (`not_offered`, `excluded_by`, `unknown_option`, `unknown_package`, `catalog_unavailable`). Bei einem Ausschluss trägt die zuletzt gewählte Option den Grund; eine Option, die die Linie ohnehin enthält, zählt nicht als eigene Wahl. Ein im Katalog nicht angebotener Slug heißt `unknown_option`, auch wenn die Option zwar veröffentlicht, aber ohne Preiszeile für den Typ ist (sie steht nicht im Angebot).
- **Typwechsel:** Linie und Optionen, die für den neuen Typ nicht angeboten werden, entfallen; die Antwort nennt sie (`selection.dropped`).
- Bei jeder Änderung von Linie oder Optionen gilt für die Regelprüfung: abgelehnt wird nur, was **neu** bindend verletzt ist (3.9).

### 3.2 Optionsarten

`module_version` bekommt `kind` (`plain`, `terrace`, `carport`), `params` und `regulatory`. `geometry_mode` folgt aus der Art (`plain` → `none`, sonst `parametric`), kein zweiter Wert zum Pflegen. Parameter werden beim Anlegen geprüft (Grenzen, Standardwerte):

| Art | Parameter | Preis (`module_type_price.surcharge_cents`) |
|---|---|---|
| `plain` | – | fester Aufschlag |
| `terrace` | `depth_m` (0,5–6, Standard 3), `height_above_terrain_m` (Standard 0,3), `sealing_factor` (0–1, Standard 1) | **je m²**, Menge = Fläche der Terrasse |
| `carport` | `spaces` (1 oder 2), `width_m`, `depth_m`, `height_m` (Standard 2,7) | fester Aufschlag |

`regulatory`: `facade_material`, `roof_material` aus dem Vokabular der Regeln (`MATERIALS`, Spez. 4.1). Dieselben Felder trägt die Linie (`package_version.regulatory`), weil ihre Fassade und ihr Dach geprüft werden sollen (Umsetzungsplan 3.9 „Regelprüfung der Ausführungen“). Fehlt die Angabe, ist die Prüfung `unknown`-Hinweis, nie bestanden.

Seed und Anleitung: Carport einstellig (3 × 5 m) und zweistellig (6 × 5 m) sind zwei Optionen, die sich gegenseitig ausschließen; Terrasse Holz mit 3 m Tiefe.

### 3.3 Terrasse

Rechteck an der **längsten Kante mit Rolle `garden`** (Fassade, nicht Projektion): Breite = Kantenlänge, Tiefe = `depth_m`, nach außen. Ohne Gartenrolle keine Terrasse (`no_garden_facade`, Option gesperrt, `facade_roles_missing` bleibt der Hinweis). Die Terrasse liegt ganz im Grundstück (`terrace_outside_site`, bindend, weil geometrisch sicher). Sie zählt zur Grundfläche, wenn `height_above_terrain_m` über `terrace_counts_above_m` der Regel liegt (Standard 0,6 m, Spez. 5.5.5); zur Versiegelung immer mit `sealing_factor`. Preis: Fläche × Wert je m².

### 3.4 Carport

Rechteck `width_m × depth_m`, die offene Seite zur Hauptstraße, so nah an der Straße wie die Regeln erlauben, sonst in der Mitte der Straßenkante. Er berührt weder Haus noch Terrasse (Abstand 0,5 m) und ist **erreichbar**: die Zufahrt (3 m breit, kürzeste Verbindung zur Straße) darf Haus und Terrasse nicht schneiden. Hinter dem Haus ist oft Platz, aber ohne Zugang wäre das keine Stelle. Ohne Hauptstraße (Weg E) gilt die längste Kante des Grundstücks als Straßenseite. Gesucht wird auf der Fläche zulässiger Ursprünge des Rechtecks (dieselbe Methode wie beim Haus, `part_surface`), mit Regeln für Nebengebäude:

- Abstände: die Regel der Art `annex` bzw. `any`. Gibt es sie nicht, ist der Abstand für den Nebenbau **nicht bekannt**. Dann sucht H3 zuerst mit den Abständen des Hauptbaus (damit der Vorschlag nicht auf der Grenze steht), findet es dort keine erreichbare Stelle, ohne Abstände; beides gilt als Hinweis (`carport_setback_assumed`, `carport_setback_relaxed`), nie als Sperre. Nur eine wirksame `annex`-Regel sperrt (D12).
- `annex.max_footprint_m2`, `annex.max_height_m`: Fläche und Höhe des Carports, bindend nur bei wirksamer Regel. Ein zweistelliger Carport von 30 m² überschreitet oft die 20 m² eines Nebengebäudes: dann ist die Option gesperrt, die einstellige nicht. Deshalb beide.
- Das Band der Straßenkante (Bauband) gilt nur dem Hauptbau und entfällt.
- Findet sich keine Stelle, ist die Option mit Grund `no_valid_position` nicht wählbar (Umsetzungsplan 3.8).

### 3.5 Zufahrt und Flächen (Spez. 5.9.3)

- **Zufahrt** 3,00 m breit: kürzeste Verbindung von der Mitte der offenen Carport-Seite zur Straßenkante; hat der Typ ein Garagentor (`garage_door = {edge, position}`), von dessen Punkt aus. Beides zugleich: beide Zufahrten zählen (sichere Seite). Ohne Carport und ohne Garagentor keine Zufahrt, aber der Hinweis `parking_not_shown` („Stellplätze nicht nachgewiesen“).
- **Wege:** Pauschale 10 m² (Spez. 5.9.3, Standard; der Preiskatalog trägt das Feld nicht, es ist eine benannte Konstante).
- **Grundfläche** (Emprise): Haus (Fassade, bei `counts_overhangs = yes` Projektion) + Carport + Terrasse über der Grenzhöhe, je Teilfläche mit ihr verschnitten; Grenze `ratio × Fläche der Teilfläche`. Die Prüfung des Hauses allein bleibt in H2; H3 rechnet die Summe.
- **Versiegelt:** Haus + Carport + Zufahrt + Terrasse × Faktor + Wege; **unversiegelt** = Fläche − versiegelt. `unsealed_min`: `ratio` (sonst `full_soil_ratio`) × Fläche der Teilfläche. Überlappungen (Zufahrt am Carport, Terrasse am Haus) zählen einmal.

### 3.6 Prüfungen der Auswahl

Alle als `Check` wie in H2 (Code, Messwert, Grenze, Zitat, bindend). Bindend nur bei wirksamer Regel oder geometrischer Gewissheit; sonst Hinweis (D12).

| Code | Prüft | bindend |
|---|---|---|
| `footprint_total` | Grundfläche der Summe gegen `max_footprint_ratio` | wirksame Regel |
| `unsealed_min` | unversiegelter Anteil | wirksame Regel |
| `annex_footprint`, `annex_height` | Carport gegen `annex` | wirksame Regel |
| `terrace_outside_site`, `no_valid_position` (Carport), `no_garden_facade` | Geometrie | ja |
| `carport_setback_assumed`, `carport_setback_relaxed`, `annex_unknown` | Abstand oder Regel für Nebenbauten unbekannt | nein |
| `parking` | angebotene Stellplätze (Carport `spaces`, Garagentor zählt 1) gegen `spaces_per_dwelling` | nein (Spez. 5.9.2: nur Warnung) |
| `parking_not_shown` | weder Carport noch Garagentor | nein |
| `facade_material`, `roof_material` | Material der Option/Linie gegen `facade.materials_allowed/forbidden` bzw. `roof.materials_allowed` | wirksame Regel |
| `material_unknown` | Option oder Linie ohne Materialangabe, Regel wirksam | nein |

Nicht geprüft: `spaces_per_m2_sdp` (SDP unbekannt; Hinweis `parking_not_checked`, nie `pass`), `setback_between_buildings` und `color_families_allowed` (ohne Hinweis).

### 3.7 Energie (RE2020)

Befund je (Typ, Linie) aus `energy_assessment`. Status `compliant`; `action` (nicht konform, Aufpreis und Maßnahmen); `not_assessed` (kein Befund, „Wärmeschutznachweis erforderlich“, L7). Bei `action` mit `compliance_surcharge_cents` geht der Betrag in beide Korridorgrenzen ein (Verhalten des Mockups bei Base). Kein Befund heißt kein Aufpreis. Kein Ersatz für die Berechnung (L7).

### 3.8 Kosten (Spez. 5.6.5)

```
K_min = Basis_min + Linienaufpreis + Σ Optionsaufpreise (nicht in der Linie enthalten) + Konformitätsaufpreis
K_max = Basis_max + dieselben Aufschläge
```

- Basis: `type_base_price` des veröffentlichten Katalogs; hat er für den Typ keine Zeile, der Basispreis der Typversion (H1 trägt ihn immer; die Quelle steht am Posten). Ohne veröffentlichten Katalog gibt es keine Kosten, auch keine Basis. Linie und Option: die Zeile des veröffentlichten Katalogs (Anwendbarkeit, 3.1). `terrace`: Wert × m².
- **Mehrwertsteuer (D10, nach Empfehlung):** gespeichert wird netto, angezeigt brutto mit `vat_rate_default` des Katalogs (Standard 20 %, Spez. 5.6.6). Die Antwort trägt `net`, `gross`, `vat_rate`, `display_basis = gross`; die Oberfläche zeigt brutto und kennzeichnet „TTC“. Das Büro trägt Preise netto (HT) ein.
- **Rundung:** Anzeige auf 1.000 € **kaufmännisch** (wie das Mockup und die Paritätsfälle in Spez. 11.2: 337.500 → 338.000), immer mit „ca.“. **Kein Feld `total`** (L1): nur `min_cents`, `max_cents`, `display_min_cents`, `display_max_cents`.
- **Menge der Terrasse** = Länge der Gartenkante × Tiefe. Sie hängt nur vom Typ ab, nicht von der Lage; die Kosten sind deshalb auch ohne gespeicherte Lage vollständig (Typteil). Nur die Position der Terrasse gehört zum Lageteil.
- Bedeutung der Spanne (D8, Honorar oder Bauleistung) berührt die Rechnung nicht, nur den Wortlaut; die Oberfläche sagt „Schätzung, unverbindlich“ wie das Mockup.
- Gibt es keinen veröffentlichten Katalog oder keinen Basispreis: `costs.available = false` mit Grund. Nie ein erfundener Wert.
- Jeder Posten trägt Code, Art (`base`, `package`, `option`, `energy`), Bezeichnung, min/max, `included`, bei Terrasse Menge und Einheit (L3).

### 3.9 Speichern und Sperren

D12: eine bindende Verletzung wird nicht gespeichert. Damit niemand in einem Zustand festhängt, den erst ein Katalog- oder Regelwechsel ungültig gemacht hat, gilt für die Prüfungen von H3: abgelehnt wird nur, was **neu** bindend verletzt ist im Vergleich zum gespeicherten Stand (`422 selection_blocked` mit den neuen Verstößen). Die Prüfung der Lage aus H2 bleibt streng. Eine Auswahl, die die Anwendbarkeit oder einen Ausschluss verletzt, wird immer abgelehnt (`invalid_selection`). `GET` liefert bestehende Verstöße weiter aus.

`GET …/catalog/options` liefert je Option, ob sie **wählbar** ist: Sie wird zur aktuellen Auswahl hinzugenommen und gerechnet; neue bindende Verstöße stehen als Gründe da. So muss der Kunde keinen Fehler auslösen, um ihn zu sehen.

### 3.10 Himmelsrichtung (HP05)

Das Grundstück liegt in Lambert-93; „Norden“ der Lage ist Gitternorden. Die Meridiankonvergenz `γ = atan2(X − 700000, 12655612,05 − Y)` (Lambert-93, Konstanten der IGN) liegt in Treillières bei rund −3,3°. Wahrer Azimut einer Fassade = Gitterazimut + γ. Die Antwort trägt `convergence_deg` und den wahren Azimut der Gartenfassade und der Straßenfassade; die Oberfläche zeigt die Himmelsrichtung als Wort. Die Drehung der Lage bleibt am Gitternorden (H2).

### 3.11 Kein Cache des Typteils

Umsetzungsplan 3.9 sieht den Typteil (Kosten, Auswahl, Material) gecacht vor. Er besteht aus wenigen Nachschlagen und Additionen; die Geometrie (Lageteil) muss ohnehin bei jeder Änderung neu laufen. Ein Cache bräuchte Invalidierung bei jeder Katalog-, Preis- und Regeländerung. **Abweichung:** Typteil und Lageteil sind zwei getrennte reine Funktionen, aber ohne Cache. Messung in 6.

## 4. Technik

### 4.1 Aufbau

```
configuration/domain/
  options.py      Auswahl: Definitionen, Anwendbarkeit, Ausschlüsse, wirksame Optionen
  outbuildings.py Terrasse und Carport setzen, Zufahrt
  areas.py        Grundfläche, versiegelt, unversiegelt
  compliance.py   Prüfungen der Auswahl (3.6)
  costs.py        Korridor, Mehrwertsteuer, Rundung
  energy.py       RE2020-Status
  orientation.py  Meridiankonvergenz, wahre Azimute
  design.py       `evaluate_design`: Zusammenführung; Typteil und Lageteil getrennt
```

`domain/` bleibt rein. Der Dienst holt die Katalogsicht (`catalog.service.offer_for_type`: veröffentlichte Linien und Optionen mit Preisen für einen Typ, Preiskatalog, Befunde) und übergibt sie als Datenklassen. `surface.py` bekommt `building_kind` und `use_bands` (Standard wie bisher), damit der Carport dieselbe Fläche benutzt.

### 4.2 Datenmodell

Migration `0010`:
- `configuration`: `package_version_id` (FK, null), `modules` (JSONB, Standard `[]`).
- `module_version`: `kind` (Standard `plain`, Prüfung auf die drei Werte), `params` (JSONB, `{}`), `regulatory` (JSONB, `{}`).
- `package_version`: `regulatory` (JSONB, `{}`).

Veröffentlichte Versionen sind durch den Trigger `forbid_published_modification` geschützt; neue Spalten mit Standardwert lösen ihn nicht aus.

### 4.3 API (Flag `configurator`)

| Methode | Pfad | Zweck |
|---|---|---|
| PATCH | `/projects/{id}/configuration` | zusätzlich `package_slug` (null löscht) und `option_slugs` (vollständige Liste); `If-Match` wie in H2 |
| GET | `/projects/{id}/configuration` | zusätzlich `selection`, `outbuildings`, `areas`, `compliance`, `energy`, `costs`, `orientation` |
| GET | `/projects/{id}/catalog/options` | Linien und Optionen des gewählten Typs mit Preis, Zustand (`selected`, `included`, `available`, `blocked`), Gründen |
| GET | `/admin/projects/{id}/configuration` | wie GET, für das Büro |

Katalogpflege: `ModuleIn` um `kind`, `params`, `regulatory`; `PackageIn` um `regulatory`; Ausgaben entsprechend. `publish_package_version`/`publish_module_version` nur aus `draft` oder `review` (409 `version_not_publishable`).

Fehler: `invalid_selection` (mit `reasons`), `selection_blocked` (mit `checks`), dazu die von H2. Alle Antworten enthalten `simulation = true`.

### 4.4 Frontend

Die Schritte `type`, `placement` bekommen `package`, `options`, `design`. Kostenleiste (unten, ab Typwahl): Korridor „ca. 384.000 – 418.000 € TTC“, Posten aufklappbar, mit Hinweis „Schätzung, unverbindlich“. Linie: Tabelle wie im Mockup (Umfang je Linie), RE2020-Hinweis bei `action`. Optionen: Gruppen, Preis oder „in Linie enthalten“, gesperrte Optionen mit Grund, Ausschlusstext. Lageplan: Terrasse, Carport, Zufahrt neben dem Haus. Vorentwurf: Angaben, Prüfungen, Flächen, Himmelsrichtung, Korridor; **kein Absenden** (V). Katalogpflege: Felder Art, Maße, Material.

## 5. Arbeitsschritte

1. Reine Fachlogik und Einheitstests: Auswahl, Terrasse, Carport, Flächen, Prüfungen, Kosten, Energie, Konvergenz.
2. Migration, Modelle, Katalogdienst (Angebot, Veröffentlichungsreihenfolge), Dienst, API, Integrationstests; `openapi.json` und Typen.
3. Frontend: Schnittstelle, Kostenleiste, Schritte, Lageplan, Katalogpflege-Felder, Tests.
4. Im Browser prüfen (lokaler Stack mit Linien, Optionen, veröffentlichtem Katalog).
5. Dokumentation: ANNAHMEN, BETRIEB, README, Plan 3.9 und AGENTS; HANDOFF und AENDERUNGEN über `/handoff`.

## 6. Abnahme

- Korridorfälle der Parität (Spez. 11.2, `vat_rate = 0`, Optionen als feste Spannen wie im Mockup, Lärche 12.400 €, Terrasse 9.800 € als Art `plain`): Ligne Base ca. 338.000 – 372.000 € (328.000 – 362.000 € + 9.500 € Konformität), Confort ca. 362.000 – 396.000 €, Confort mit Lärche und Terrasse ca. 384.000 – 418.000 €, Signature mit enthaltenen Optionen ohne Aufschlag. Die Rechnung mit `finish_delta` (Spez. 6.5, Lärche je m²) gehört nicht zu H3 (keine Ausführungen, Umsetzungsplan Kapitel 7); die Kostenfunktion prüft je m² an der Terrasse.
- Eine in der Linie enthaltene Option erhöht den Korridor nicht; wählt der Kunde eine andere Linie, wird sie wieder berechnet.
- Freiflächenrechnung mit Zufahrt: Rechenfall mit Grundstück 20 × 31 m, Haus, Carport, Terrasse, Zufahrt, Wege 10 m².
- Ausschlüsse; nicht angebotene Option → `invalid_selection`; Typwechsel entfernt Nicht-Angebotenes.
- Carport: zweistelliger Carport bei `annex.max_footprint_m2 = 20` gesperrt, einstelliger wählbar; ohne `annex`-Regel Hinweis, keine Sperre; kein Platz → `no_valid_position`.
- Terrasse: Maße = Kantenlänge × Tiefe; ohne Gartenrolle gesperrt; Terrasse über der Grenzhöhe zählt zur Grundfläche.
- Konvergenz in Treillières −3,3° (Gegenprobe gegen die Formel des Anbieters, ±0,05°).
- Eigenschaftstest: Für zufällige Haus- und Nebenbaulagen liegt der Carport nie im Haus und stets im Grundstück; versiegelt + unversiegelt = Grundstücksfläche.
- Auswertung einer Konfiguration mit allen Optionen unter 800 ms (Spez. 11.5), `GET …/catalog/options` unter 2 s.
- Kein Antwortfeld, das als Gesamtpreis lesbar ist (Test über das Schema).

**Ergebnis der Abnahme (19.09.2026):** alle Punkte durch Tests belegt (58 Einheits-, 24 Integrationstests, dazu die Paritätsfälle 11.2 mit `vat_rate = 0`). Gemessen im lokalen Stack auf AD 65 mit Terrasse und Carport: `GET …/configuration` 13–79 ms, `GET …/catalog/options` 14–36 ms, `PATCH` in den Integrationstests 260–410 ms. Die Tests prüfen die grobe Schranke (2 s und 4 s), nicht die Zielwerte.

## 7. Risiken

- **Preise sind Platzhalter**, solange das Büro keine echten Typdateien liefert; der Korridor ist nur so gut wie der Katalog. Ohne veröffentlichten Katalog gibt es keine Kosten.
- **Carport-Position ist ein Vorschlag**, keine Planung. Im Vorentwurf steht das so; das Büro prüft.
- **Nebenbau-Regeln sind selten sauber extrahiert.** Deshalb sperren nur wirksame `annex`-Regeln; alles andere ist Hinweis.
- **Mehrwertsteuer:** liefert das Büro Preise brutto statt netto, stehen 20 % zu viel im Korridor. Die Pflegeoberfläche und BETRIEB sagen „netto (HT)“.

## 8. Offene Punkte für den Nutzer

- D8 (Honorar oder Bauleistung) und D10 (brutto) sind nach Empfehlung genommen; D8 bestimmt nur den Wortlaut der Spanne.
- Maße der Terrasse (3 m tief, Breite der Fassade) und des Carports (3 × 5 und 6 × 5 m) sind Vorgaben des Nutzers; das Büro kann sie in der Katalogpflege ändern, weil sie Parameter der Option sind.

## 9. Ausblick V

V übernimmt `configuration` samt Auswahl und Auswertung in den Snapshot der Anfrage, rechnet beim Absenden mit dem dann jüngsten Preiskatalog und den Regeln neu und zeigt die Änderung; `costs.price_catalog_version` und die Versionen der Auswahl sind dafür schon Teil der Antwort.

## 10. Prüfprotokoll

### 10.1 Befunde beim Entwurf

| Nr. | Befund | Folge |
|---|---|---|
| 1 | Der erste Entwurf der Abnahme nannte das Rechenbeispiel aus Spez. 6.5 mit `72,4 × (225 − 60)` (Lärche je m² als `finish_delta`). H3 hat keine Ausführungen und keine Mengen; das Umsetzungsplan-Kriterium („Lärche als feste Spanne je Typ“) meint die Option des Mockups mit 12.400 € | Abnahme 6 auf die Paritätsfälle 11.2 mit festen Spannen umgestellt; je m² prüft nur die Terrasse |
| 2 | Rundung „untere ab, obere auf“ hätte 337.500 € als 337.000 € gezeigt; die Paritätstabelle (11.2) und das Mockup erwarten 338.000 € | Kaufmännisch runden (3.8) |
| 3 | Preise je Option sind ein einzelner Wert je Typ (`module_type_price.surcharge_cents`), die Terrasse braucht „je m²“ | Die Art der Option legt die Einheit fest (3.2); kein zweites Preisfeld |
| 4 | Eine Option ohne Preiszeile hätte still nichts gekostet | Anwendbarkeit folgt aus der Preiszeile (3.1, Plan H1 3.2) |
| 5 | Im Mockup enthält Signature `holz_sued` und `holz_voll`, die sich ausschließen: die Ausschlussprüfung über alle wirksamen Optionen hätte jede Signature-Konfiguration verworfen | Ausschluss nur, wenn eine der beiden Optionen ausdrücklich gewählt ist (3.1) |
| 6 | D12 „bindende Verletzung wird nicht gespeichert“ kann festklemmen, wenn ein Katalog- oder Regelwechsel die gespeicherte Auswahl ungültig gemacht hat: dann ließe sich weder Linie noch Lage ändern | Für H3 nur **neue** bindende Verstöße ablehnen (3.9) |
| 7 | Ohne Regel für Nebengebäude hätte der Carport auf der Grenze und der Straßenlinie gestanden (Abstand `unknown` = kein Abzug) | Zweistufige Suche: erst mit den Abständen des Hauptbaus, dann ohne; nur ein Hinweis (3.4) |
| 8 | Die Terrassenmenge hing im ersten Entwurf an der platzierten Fassade; ohne Lage wären die Kosten unvollständig gewesen | Menge nur aus Typ und Rolle, Position getrennt (3.8) |
| 9 | H3 liest die jeweils jüngste veröffentlichte Version (`current_version_id`), doch `publish_*_version` prüft weder Status noch Reihenfolge (HANDOFF 4.5): eine ältere Version könnte die neuere verdrängen | Veröffentlichung nur aus `draft`/`review` (4.3) |
| 10 | Vorzeichen der Meridiankonvergenz: „wahr = Gitter − γ“ (aus der Definition der IGN falsch gelesen) hätte die Himmelsrichtung um 6,6° verfehlt. Herleitung aus der Geometrie (Meridian westlich des Mittelmeridians neigt sich nach Osten zum Kegelscheitel): wahrer Azimut = Gitterazimut + γ, mit γ = atan2(X − 700000, 12655612,05 − Y) negativ westlich von 3° O | 3.10 auf „+ γ“ mit dem Zahlenbeispiel Nantes (γ ≈ −3,3°) gestellt |
| 11 | `evaluate_design` als reine Funktion braucht den Katalog als Eingabe; wäre er im Dienst gemischt, ließe sich Kosten und Auswahl nicht ohne Datenbank testen | Katalogsicht als Datenklassen (4.1) |

### 10.1a Befunde beim Bau

| Nr. | Befund | Folge |
|---|---|---|
| 12 | Ein neuer Entwurf des Preiskatalogs begann leer (`_draft_price_catalog`, H1). Nach der ersten Veröffentlichung hätte jeder weitere Typimport den Katalog auf die Zeilen dieses einen Typs reduziert und allen anderen Typen Linien, Optionen und Basispreis genommen | Der neue Entwurf übernimmt die Zeilen der veröffentlichten Version und den Mehrwertsteuersatz (Test `test_new_price_draft_starts_from_the_published_prices`) |
| 13 | Beim Ausschluss zweier Optionen kam in Signature ein Widerspruch heraus: Wählt der Kunde `holz_voll` unter Confort und wechselt dann zu Signature, das beide Holzverschalungen enthält, galt seine Wahl als Konflikt zur enthaltenen `holz_sued` und blockierte den Wechsel | Was die Linie enthält, zählt nicht mehr als eigene Wahl (3.1); den Grund trägt die zuletzt gewählte Option, damit „Carport zweistellig schließt Carport einstellig aus“ beim zweistelligen steht |
| 14 | Die Reihenfolge der gewählten Optionen ging beim Speichern verloren (Sortierung nach Slug beim Zurücklesen) | `_selection` liest in der gespeicherten Reihenfolge |
| 15 | **Im Browser:** Der Carport stand hinter dem Haus, seine Zufahrt lief 18 m durch das Haus. Mit den Abständen des Hauptbaus (Straße 5 m, Seiten 3 m) war neben dem Haus kein Platz, hinter ihm schon, und die erste Fassung wählte die Stelle nur nach dem Straßenabstand | Erreichbarkeit als Bedingung (3.4): die Zufahrt darf das Haus nicht schneiden; ohne erreichbare Stelle mit den Abständen des Hauptbaus gilt die Suche ohne sie (`carport_setback_relaxed`) |
| 16 | **Im Browser:** Carport und Terrasse überlappten sich (die Terrasse folgt der Gartenfassade, der Carport suchte nur Platz neben dem Haus) | Die Terrasse ist ein Hindernis für den Carport und seine Zufahrt; Eigenschaftstest über Lage und Drehung (`test_property_carport_and_driveway_avoid_house_and_terrace`) |
| 17 | Der Carport berührte das Haus, weil die Fläche zulässiger Ursprünge geschlossen ist und die Kandidaten auf ihrem Rand liegen | Abstand 0,5 m zu Haus und Terrasse (`OUTBUILDING_CLEARANCE_M`) |
| 18 | Ein veröffentlichtes Modul ohne Preiszeile für den Typ steht nicht im Angebot; die erste Fassung der Tests erwartete dafür `not_offered`, das Angebot lieferte `unknown_option` | Festgelegt (3.1); `not_offered` bleibt für eine gespeicherte Wahl, deren Preiszeile später entfällt |
| 19 | Nach der Erreichbarkeitsregel findet der zweistellige Carport (6 m) neben einem mittig stehenden Haus auf AD 65 keine Stelle mehr (früher hinter dem Haus, ohne Zugang) | Richtig so: die Option ist `blocked` mit `no_valid_position`; verschiebt der Kunde das Haus, geht sie auf. Tests entsprechend |

### 10.2 Geprüfte Alternativen

- **Typteil cachen** (Umsetzungsplan 3.9): verworfen (3.11). Besser, wenn die Auswertung eines Tages über 800 ms liegt.
- **Eigene Ausführungstabellen (`finish`, `finish_version`) für Material und Regelprüfung** (Spez. 4.3): verworfen; ohne Mengen und ohne Modell tragen sie nichts außer der Materialklasse. `regulatory` an Option und Linie reicht. Besser mit X3.
- **`GET /evaluation` als eigener Endpunkt** (Spez. 6.3): verworfen; die Oberfläche braucht Konfiguration und Auswertung zugleich, ein Aufruf spart einen Rundlauf und die Revisionen laufen nicht auseinander. Besser, wenn V die Auswertung ohne Konfiguration braucht.
- **Auswahl als Slugs speichern** statt Versions-IDs: verworfen (L4).
- **Terrasse und Carport vom Kunden frei platzieren:** verworfen (Umsetzungsplan 3.8: automatisch gesetzt); Vorschlag später.
- **Meridiankonvergenz mit PostGIS oder einer neuen Bibliothek:** verworfen, die Formel hat zwei Konstanten und keine Abhängigkeit.
- **Preise brutto im Katalog:** verworfen (Spez. 5.6.6 „gespeichert wird netto“); die Pflegeoberfläche sagt HT.

### 10.3 Grenzen

- Keine Ausführungen je Oberfläche, keine Mengenrechnung, kein Keller und keine Photovoltaik-Belegung (Umsetzungsplan Kapitel 7); ihre Optionen sind feste Aufschläge.
- Der Stellplatzrichtwert nach `spaces_per_m2_sdp` steht als Hinweis „nicht geprüft“ da; Abstand zwischen Gebäuden und Farbfamilien der Fassade werden nicht geprüft und nicht ausgewiesen.
- Die Oberfläche lief nur im Kundenpfad auf dem Testgrundstück AD 65 (Zone Uh: ohne Nebengebäuderegel, `unsealed_min` unbekannt); ein Nebenbauverstoß mit echten Regeln ist nur in den Tests, nicht im Browser gesehen. Kein Playwright-Szenario. Alle Preise der Demo sind erfunden.
- Carport und Terrasse nehmen keine Rücksicht auf Baumbestand, Leitungen oder Gelände.
- Der Carport sucht nur eine Stelle **neben** dem Haus; er verschiebt das Haus nicht und führt die Zufahrt nicht um Hindernisse (nur gerade). Steht das Haus mittig auf einem schmalen Grundstück, ist der zweistellige Carport `blocked`, bis der Kunde das Haus zur Seite zieht.
- Die Schnellstellung des Hauses (H2) und die Carport-Suche kennen einander nicht: Eine Lage, die den Carport zulässt, wird nicht gesucht (Vorschlag für später).
