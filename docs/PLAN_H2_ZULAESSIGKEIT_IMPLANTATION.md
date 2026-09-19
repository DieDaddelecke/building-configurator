# H2 Zulässigkeit und Implantation – Plan für die Umsetzung

> **Umsetzungsstand 19.09.2026:** Arbeitsschritte 1–4 umgesetzt (Backend `backend/app/configuration`, Migration 0009, Oberfläche `/konfigurator`, 38 Einheits- und 19 Integrationstests des Backends, 28 Tests der Oberfläche, im Browser auf dem Testgrundstück AD 65 geprüft); Festlegungen und Abweichungen in ANNAHMEN HP01–HP20. Offen: Playwright-Szenario, echte Typdateien (H1), Betrieb auf Unraid.
>
> Entwurf vom 19.09.2026 zum Auftrag „erstelle den Hauskonfigurator“ (R2 = H1, H2, H3, V, Umsetzungsplan 2.3). Dieser Plan deckt **H2** ab; H3 und V folgen in eigenen Plänen (Kapitel 9). Wie bei den Modulen davor gelten die Empfehlungen als entschieden ([[feedback-plan-dann-umsetzen]]); sie stehen in `docs/ANNAHMEN.md` (Abschnitt H2) und sind umkehrbar.

## 1. Ziel und Abgrenzung

**Ziel:** Aus dem Baurahmen (G3) und dem Hauskatalog (H1) wird der erste Kundenschritt des Konfigurators: Welche Typen passen auf das Grundstück (mit allen Gründen und Vorschlägen), und wo steht das gewählte Haus. Der Kunde wählt einen Typ, sieht auf dem Lageplan, wo das Haus stehen darf, verschiebt und dreht es, und der Server prüft jede gespeicherte Lage je Kante. Alle Regeln sind Simulation (D11); wie streng sie wirken, legt D12 fest (3.1).

**In H2:**
- `configuration` je Projekt: gewählter Typ (feste Typversion, L4), Lage, Bauen auf der Grenze je Kante, Revision mit `If-Match`.
- Zulässigkeit je veröffentlichtem Typ (Spez. 5.4.6): Dachform, Neigung, Höhen, Geschosse, Grundfläche, Firstrichtung, „passt überhaupt“; alle Gründe im Klartext; Vorschläge.
- Lage: Fläche aller zulässigen Hausursprünge je Drehung (Umsetzungsplan 3.8), Prüfung je Kante mit allen Verstößen (Spez. 5.3.4), Schnellstellungen (Spez. 5.3.5).
- Kundenoberfläche `/konfigurator`: Typkarten und Implantation.

**Nicht in H2:**
- Linie, Optionen, Kosten, RE2020, Freifläche mit Terrasse, Carport und Zufahrt: H3. **Abweichung vom Umsetzungsplan 3.8**, der Terrasse und Carport in H2 setzt: H1 kennt an einer Option weder Art noch Maße (`geometry_mode = none`, Plan H1 3.1), und ihre Fläche fließt erst in die Freiflächenrechnung von H3 (Spez. 5.9.3). Sie in H2 zu setzen hieße, die Optionen jetzt um Art und Maße zu erweitern und sie in H3 erneut anzufassen.
- Variantengruppen (Spez. 5.4.6): H1 hat keine (Plan H1 3.4). Die Zulässigkeit gilt je Typversion; die Schnittstelle bleibt so, dass Varianten später ergänzt werden.
- Freie Drehung, Gelände unter dem Haus (Höhen bleiben Annahme „eben“, G11), Gebäude auf Nachbargrundstücken.
- Der Endpunkt `/buildable?height_m=` (Spez. 6.3, G3-Plan 3.5 nennt ihn für H2): Die Fläche zulässiger Ursprünge je Typ und Drehung ersetzt ihn. Kein Kundenschritt braucht die Kontur für eine freie Höhe.

## 2. Ausgangslage

- G3 liefert Konturen (weit, eng), Bauband, Bauverbotsflächen und je Kante die Abstände aus `setbacks.py`. Das sind Aussagen für das Haus im Allgemeinen: die enge Kontur rechnet mit der Höchsthöhe der Zone. H2 rechnet mit den Höhen des gewählten Typs und mit einer konkreten Bezugskontur.
- H1 liefert je veröffentlichtem Typ Umriss (Fassade und Projektion), Höhen, Dachform, Neigung, Firstrichtung, Fassadenrollen, Eingang, Wohnfläche und Basispreis. `facade_roles` kann leer sein (die Veröffentlichung sperrt das nicht).
- `derive_envelope` und `setbacks_for_edge` sind rein und werden wiederverwendet, nicht kopiert.
- Alle fünf Platzhalter-Typen sind erfunden (H1 Kapitel 12). H2 ist gegen sie und gegen synthetische Fälle testbar; die Beta braucht echte Typen.

## 3. Fachliche Festlegungen

### 3.1 Wirkung der Regeln (D12, entschieden nach Empfehlung)

- Eine **wirksame** Regel (`effective`, das setzt in G2 ein bestätigtes Zitat und Gegenprüfung voraus) ist **bindend**: Ein Typ, der sie verletzt, ist gesperrt; eine Lage, die sie verletzt, wird nicht gespeichert (`422 placement_violation` mit allen Verstößen).
- Regeln mit `unknown`, `text_only` oder ohne Eintrag sind **Hinweise**: Sie sperren nichts und erscheinen mit Grund.
- Ein bindender Verstoß ist ein `fail`; ein Hinweis trägt `status = hint`. Ein nicht prüfbarer Wert (fehlende Höhe, Gelände über 5 % Neigung, Fassadenrolle fehlt) ist `unknown` und gilt nie als bestanden (Spez. 5.9.1).
- Die Anfrage an das Büro bleibt in jedem Fall möglich (D14), auch ohne Typ.

### 3.2 Drehung

Modellnorden ist die Y-Achse des Typs (Spez. 5.4.4). `rotation_deg` dreht im Uhrzeigersinn: Modellnorden zeigt danach nach Azimut `rotation_deg` (Lambert-93-Gitternorden; die Meridiankonvergenz von etwa 3° in Treillières gehört zu H3, wo Himmelsrichtungen von Optionen gebraucht werden).

Erlaubt sind **vier Drehungen** (Umsetzungsplan 3.8): Die Drehung, bei der die Fassade mit der Rolle `street` zur Hauptstraße zeigt, und je 90° weiter. Fehlt die Rolle, gilt die Richtung der längsten Grundstückskante als Ausrichtung (mit Hinweis). Ohne Hauptstraße (`corner`-Grundstücke ohne Zuordnung, Weg E) richtet sich alles nach der längsten Kante. Eine andere Drehung wird abgelehnt (`rotation_not_allowed`).

Bei einer bindenden Firstrichtung (`ridge_orientation` ≠ `any`) entfallen Drehungen, deren First mehr als 10° von der Vorgabe abweicht (Spez. 5.3.4). Übrig bleibt keine: der Typ ist gesperrt („passt nicht“).

### 3.3 Fläche zulässiger Ursprünge

Für eine feste Drehung ist die Menge aller zulässigen Ursprünge eine Fläche, keine Rastersuche (Umsetzungsplan 3.8). Mit `-C` = Bezugskontur, an der Ursprungsstelle gespiegelt, und `A ⊕ B` = Minkowski-Summe:

| Bedingung | Verbotene Ursprünge |
|---|---|
| Abstand `d` von der Kante `e` (Bezugskontur `C`) | `buffer(e ⊕ -C, d − 0,01)`; `e ⊕ -C` entsteht aus `-C`, entlang jedes Segments von `e` verschoben (die Endkopien und ein Parallelogramm je Umrisskante). Gilt, weil `buffer(e, d) ⊕ -C = buffer(e ⊕ -C, d)` (Rundung und Summe vertauschen) |
| Haus liegt in der Zonen-Teilfläche `Z` | Ursprünge, bei denen der Bezugspunkt außerhalb `Z` liegt oder die Projektion eine Kante von `Z` schneidet: `translate(Z, -p0)` bleibt erlaubt, `∪ (Kante von Z ⊕ -Projektion)` entfällt |
| Bauverbotsfläche `Q` (`no_build`) | `translate(Q, -p0) ∪ (Kante von Q ⊕ -Projektion)` |
| Bauband `building` | wie `Z` mit dem Streifen als Fläche |
| Bauband `facade` | Nur Ursprünge, bei denen ein Straßenfassadenabschnitt den Streifen berührt: Vereinigung der Streifen, entlang jedes Fassadenabschnitts verschoben |

`p0` ist ein Eckpunkt der Projektion. Die Abstandsregeln rechnen mit der Kontur, die die Regel nennt (`measured_from`: Fassade oder Projektion); die Zugehörigkeit zum Grundstück immer mit der Projektion, weil ein Dachüberstand nicht auf fremden Grund ragen soll.

Das Haus muss in **einer** Teilfläche liegen (Zonengrenzen sind keine Grundstücksgrenzen und tragen keinen Abstand). Zonen ohne Regeln (`in_progress`, `unavailable`) haben wie in G3 keine bebaubare Fläche.

**Toleranz und Schnellstellungen:** Die Prüfung lässt 0,01 m zu (Spez. 5.3.4). Die Fläche mit `d − 0,01` dient der Aussage „passt“ und der Serverprüfung; die Schnellstellungen und das Einrasten im Browser (`placement-area`) nutzen die Fläche mit `d`, damit ein Haus genau 5,00 m Abstand hält und nicht 4,99 m. Ist diese leer (ein Haus passt gerade eben), gilt die Fläche mit Toleranz.

### 3.4 Bauen auf der Grenze

`boundary_options` in der Konfiguration (Spez. 4.4): je seitlicher oder hinterer Kante ein Schalter, nur wo die Regel `allow_on_boundary` sagt. Standardmäßig aus: Das Haus hält dann den Abstand `max(min_m, faktor × H)` ein. Ist der Schalter an, ist der Abstand 0; verlangt die Regel eine Höchsthöhe an der Grenze (`on_boundary_max_height_m`), prüft H2 sie gegen die höchste Höhe des Typs. Der Schalter liegt bei der Konfiguration, nicht beim Typ.

### 3.5 Prüfungen des Typs (unabhängig von der Lage)

| Regel | Prüfung |
|---|---|
| `roof` | Dachform in `allowed_forms` (`complex` entspricht `other`); `flat_roof`: `forbidden` und `annex_only` sperren ein Flachdach am Hauptgebäude, `green_only` ist ein Hinweis; Neigung in `[pitch_min_deg, pitch_max_deg]` mit 0,1° Toleranz (angegebene Neigung des Typs, Plan H1 3.5) |
| `max_height` | First (bei Flachdach Attika) gegen `ridge_m` bzw. `parapet_m`, Traufe gegen `eave_m`, Geschosse gegen `storeys` (`R+1+C` erlaubt `R+1` und `R+1+C`, nicht `R+2`). Bezug Straßenniveau oder Gelände über 5 % Neigung: `unknown` mit Hinweis |
| `max_footprint_ratio` | Fläche der Fassade (`counts_overhangs = yes`: der Projektion) gegen `ratio × Fläche der Teilfläche`; je Teilfläche |
| Firstrichtung | 3.2 |

`facade` (Material, Farbe) gehört zur Linie und damit zu H3. Nebengebäude, Abstände zwischen Gebäuden, Stellplätze und Bepflanzung ebenfalls.

### 3.6 Vorschläge

Erst `alternatives` des gesperrten Typs, dann Typen derselben `family`, jeweils nur zulässige, nach Nähe der Wohnfläche sortiert (Spez. 5.4.6).

### 3.7 Weg E (freies Zeichnen, D13, entschieden nach Empfehlung)

Ohne Baurahmen und ohne Regeln: Der gezeichnete Umriss ist die Fläche, auf der das Haus frei verschoben und gedreht werden kann. Geprüft wird nur, dass die Projektion im Umriss liegt (`outside_outline`); keine Abstände, keine Höhen, keine Dachform. Drehungen sind die vier Ausrichtungen zur längsten Umrisskante. Der Hinweis aus G1 („nicht mit dem Bebauungsplan abgeglichen“) steht auf jeder Seite des Konfigurators. Ein Typ, der nicht in den Umriss passt, ist gesperrt (`no_valid_position`).

### 3.8 Konfiguration und Revision

Eine Konfiguration je Projekt. `PATCH` ist ein Teil-Update; `If-Match: <revision>` schützt vor überschriebenen Änderungen (409 `revision_conflict`); ohne Header wird nicht geprüft. Der Typ wird auf eine **Typversion** festgelegt (L4); der Server prüft ihn bei jedem Abruf neu, weil Regeln, Grundstück und Katalog sich ändern (Umsetzungsplan 3.10 Neuprüfung). Ein Typ, der inzwischen gesperrt ist, bleibt gespeichert und erscheint mit seinen Verstößen; gespeichert wird nie eine Lage mit bindendem Verstoß.

Wählt der Kunde einen Typ ohne Lage, setzt der Server die Schnellstellung `street_near`. Wechselt er den Typ, entfällt die alte Lage.

## 4. Technik

### 4.1 Aufbau

`backend/app/configuration/` wie die übrigen Fachmodule (`domain/` rein, `models.py`, `schemas.py`, `service.py`, `api.py`). H3 und V erweitern dasselbe Modul.

```
domain/
  house.py       Typ als reine Datenklasse (Umrisse, Höhen, Dach, Rollen)
  geometry.py    Drehen und Verschieben, Überstreichen, Sperrflächen (3.3)
  rotations.py   erlaubte Drehungen (3.2)
  type_checks.py Prüfungen des Typs (3.5)
  surface.py     Fläche zulässiger Ursprünge je Drehung
  placement.py   Prüfung einer Lage je Kante (Spez. 5.3.4)
  presets.py     Schnellstellungen
  fit.py         Zulässigkeit und Vorschläge je Typ
```

`domain/` kennt weder Datenbank noch API. Eingabe ist `EnvelopeInput` aus G3, dazu `HouseType`. Der Dienst holt beides über `envelope.service.envelope_input` und `catalog.service` (Module rufen einander nur über `service` auf, Plan 3.2).

### 4.2 Datenmodell

Migration `0009`: `configuration(id, project_id unique, revision, building_type_version_id, placement jsonb, boundary_options jsonb, updated_at, updated_by, created_at, created_by)`. `placement = {origin_e, origin_n, rotation_deg}` in Lambert-93 wie Spez. 4.4; die API nimmt und liefert lokale Meter. Die Tabelle fällt mit dem Projekt (`ON DELETE CASCADE`). Keine neue Sequenz.

### 4.3 API (Feature-Flag `configurator`, Kunde; Rolle für das Büro)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/projects/{id}/catalog/types` | Veröffentlichte Typen mit Zulässigkeit, Gründen, Hinweisen, Vorschlägen |
| GET | `/projects/{id}/configuration` | Konfiguration mit Prüfung der Lage |
| PATCH | `/projects/{id}/configuration` | Typ, Lage, Grenzschalter; `If-Match` |
| GET | `/projects/{id}/configuration/placement-area` | Fläche zulässiger Ursprünge je erlaubter Drehung für den gewählten Typ |
| POST | `/projects/{id}/configuration/placement-presets` | `street_near`, `set_back`, `garden_max` |
| GET | `/admin/projects/{id}/configuration` | Wie GET, für das Büro (Anfrage, später V) |

Fehler: `type_not_found`, `type_blocked` (mit Gründen), `rotation_not_allowed`, `placement_violation` (mit allen Prüfungen), `boundary_not_allowed`, `revision_conflict`, `site_not_found`.

### 4.4 Frontend

Route `/konfigurator` mit den Schritten Haustyp und Implantation, französisch führend. Der Lageplan wiederverwendet `PlanSvg`, `Masskette` und die Kantenfarben. Beim Ziehen prüft der Browser lokal per Punkt-in-Fläche gegen die zulässigen Ursprünge (Spez. 8.2); beim Loslassen entscheidet der Server. Erreichbar über einen Knopf unter dem Baurahmen der Grundstücksseite.

## 5. Arbeitsschritte

1. Reine Geometrie und Prüfungen mit Einheitstests (Parität Spez. 11.2, Eigenschaftstests).
2. Migration, Modell, Dienst, API, Integrationstests; `openapi.json` und Typen.
3. Frontend: Schnittstelle, Typkarten, Implantation, Tests.
4. Im Browser prüfen (lokaler Stack, Testprojekt).
5. Dokumentation: ANNAHMEN, BETRIEB (Flag), HANDOFF/AENDERUNGEN über `/handoff`.

## 6. Abnahme

- Parität 11.2: Fläche 14,0 × 21,0 m; Plateau gesperrt wegen Dachform ohne den Grund „passt nicht“; Vorschlag `plateau_adapte`; Plateau mit `parallel_to_street` zusätzlich „passt nicht“; Ligne straßennah 5,00 · 4,00 · 4,00 · 18,00 m; Zug über die Nordgrenze `placement_violation` mit `setback_street`; Nordwestecke zwei Verstöße.
- Eigenschaft: Jeder Punkt der Fläche zulässiger Ursprünge besteht die Prüfung je Kante; Punkte knapp außerhalb nicht.
- Zulässigkeit von 20 Typen unter 3 s; `PATCH` unter 800 ms (Messung im Test, Spez. 11.5).
- Weg E: freie Lage im Umriss, kein Baurahmen nötig.

## 7. Risiken

- **Sperren aus falsch ausgewerteten Regeln.** Ein Lesefehler in G2 sperrt dann zu Unrecht einen Typ. Gegen das Risiko: nur `effective` sperrt; der Grund zeigt Wert und Zitat mit Seite; das Büro kann die Regel bei einer Anfrage korrigieren. Ohne Schlüssel der Claude API ist die Menge der wirksamen Regeln klein, dann sperrt H2 wenig.
- **Feinheiten der Fläche** (Splitter, punktförmige Passung): Toleranz 0,01 m, Splitter unter 1 cm² entfallen.
- **Höhen der Fassade einzeln** (`facade_point`): H1 kennt nur eine Traufe und einen First; H2 rechnet mit der größten Höhe (sichere Seite, G3 3.5).

## 8. Offene Punkte für den Nutzer

- Keine neuen; D12 und D13 sind nach Empfehlung genommen (ANNAHMEN). Zu klären bleiben die Datenfragen aus HANDOFF (Schlüssel der Claude API, echte Typdateien).

## 9. Ausblick H3 und V

- **H3** (Konfiguration und Kosten): Tabelle `configuration` um Linie und Optionen erweitern (Spalten in Migration `0010`), Optionen um Art und Maße (Terrasse, Carport), Auswertung `evaluate()` in zwei Teilen (Typteil gecacht, Lageteil), Freifläche mit Zufahrt, Kostenkorridor, RE2020-Status. Schritte Linie, Optionen, Vorentwurf im Frontend. Terrasse und Carport werden dort automatisch gesetzt.
- **V** (Übergabe): Anfrage um Konfiguration und Auswertung erweitern (Snapshot 5.10.4), Neuprüfung beim Absenden, Dossier-PDF und DXF-Lageplan, Zustände und Nachrichten.

## 10. Prüfprotokoll

### 10.1 Befunde beim Entwurf und beim Bau

| Nr. | Befund | Folge |
|---|---|---|
| 1 | Der Paritätsfall „Plateau mit `parallel_to_street` … zusätzlich ‚passt nicht‘“ (Spez. 11.2) setzt voraus, dass die Lage auch dort geprüft wird, wo der Typ schon aus anderem Grund scheitert. Die erste Fassung von `evaluate_type` brach nach dem ersten Typgrund ab | Lage und Typprüfung getrennt gerechnet; beide Gründe stehen nebeneinander (Test `test_gable_wide_house_with_ridge_parallel_to_street_does_not_fit`) |
| 2 | Die Bedingung „Straßenfassade im Band“ (`band = facade`) ist keine Erosion wie das Bauband für den ganzen Baukörper, sondern eine Berührung: erlaubt sind Ursprünge, bei denen ein Fassadenabschnitt den Streifen trifft (Streifen entlang der Fassade verschoben) | Eigene Herleitung in 3.3; Tests für beide Bandarten |
| 3 | Die Schnellstellung lieferte 4,99 m statt 5,00 m Abstand, weil die Fläche mit der Toleranz von 0,01 m gerechnet war; im Browser zeigte dasselbe „2,99 m von 3,00 m“ | Zwei Flächen: exakt für Schnellstellungen und den Browser, mit Toleranz für „passt“ und die Serverprüfung (ANNAHMEN HP11) |
| 4 | Ein `hypothesis`-Test über zufällige Ursprünge (Fläche gegen Prüfung je Kante) fand keinen Widerspruch; die Eigenschaft „jeder Punkt der Fläche besteht die Prüfung, jeder Punkt deutlich außerhalb nicht“ gilt für drei Hausgrößen und alle vier Drehungen | Bleibt als Regressionstest |
| 5 | Die Typprüfung des Frontends fand eine Namenskollision im OpenAPI-Schema: `PlacementIn` existiert schon im Katalog (Entrance/Garagentor) und wurde dort in `app__configuration__schemas__PlacementIn` umbenannt, sodass die Oberfläche der Katalogpflege nicht mehr baute | H2-Modell in `PlacementRequest` umbenannt |
| 6 | Im Browser schwenkte das Haus beim Drehen um die Ecke des Modellursprungs statt um seine Mitte und sprang damit über den Plan | Drehung um die Hausmitte, danach in die Fläche geklemmt (HP19) |
| 7 | Auf jeder Typkarte stand derselbe Hinweis („Toiture : règle non déterminée“) | Was für jeden Typ gleich lautet, steht einmal über den Karten |
| 8 | Testfehler, nicht Codefehler: Ein „winziges Haus“ muss um den Ursprung liegen, sonst schrumpft die Fläche um seine Maße; die Tabelle `rule` ist unveränderlich, eine Korrektur der Regeln im Test läuft über die Projektkorrektur | Tests angepasst |

### 10.2 Geprüfte Alternativen

- **Rastersuche über Ursprünge** (Spez. 5.3.6) statt der Fläche: ungenau an den Rändern, bei 0,25 m rund 10 000 Punkte je Drehung und Typ. Verworfen; Kandidaten gibt es nur noch für die Schnellstellungen.
- **`pyclipper` für die Minkowski-Summe** (Umsetzungsplan 3.8 nennt sie): nicht nötig. Die Überstreichung eines Umrisses entlang einer Strecke (Endlagen und Parallelogramme) ergibt mit `shapely` dieselbe Fläche; keine neue Abhängigkeit, kein neues Image.
- **Lage in lokalen Metern speichern:** Der Ursprung des lokalen Systems hängt am Grundstück und kann sich mit ihm ändern. Gespeichert wird in Lambert-93 (Spez. 4.4), die API rechnet um.
- **Sperren auch bei nicht bestätigtem Zitat:** Nicht nötig, weil `effective` in G2 ein bestätigtes Zitat und die Gegenprüfung voraussetzt.
- **Alle Drehungen frei:** Verworfen wie im Umsetzungsplan (Voraussetzung der Flächenmethode).

### 10.3 Grenzen und offene Punkte

- Die Höhenprüfung ist ohne Gelände `unknown`; lokal liefert der Höhendienst derzeit kein Gelände, deshalb steht auf jeder Karte „Hauteurs non vérifiables“. Das ist gewollt, beschreibt aber nicht den Betrieb mit Gelände.
- Auf dem Testgrundstück AD 65 ist mit den aufgezeichneten Regeln nur Zone Uh ausgewertet; sie kennt keine Dachregel. Ein gesperrter Typ mit echten Regeln ist nur in den Tests, nicht im Browser gesehen worden (die Karten der Demo-Typen sind alle zulässig).
- Ziehen per Zeiger wurde mit dem Ziehen des Browserwerkzeugs geprüft (funktioniert), Berührung (Touch) nicht; Tastatur und Knöpfe sind in Komponententests abgedeckt.
- Kein Playwright-Szenario und keine Komponententests mit einem Zeiger-Ziehen.
- Mehrere Grundstücke mit mehreren Zonen: nur im Einheitstest (`test_house_must_stay_in_one_zone`), nicht am echten Grundstück.
