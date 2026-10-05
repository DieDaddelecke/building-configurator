# Hausmodell – Plan für die Umsetzung

> **Entwurf vom 03.10.2026.** Grundlage ist der Prompt des Nutzers „Parametrischer Hauskonfigurator mit IFC-Import (v3.1)“, abgelegt als [HAUSKONFIGURATOR_PROMPT_v3.1.md](HAUSKONFIGURATOR_PROMPT_v3.1.md) (im Folgenden „Prompt“, Kapitel als „P 8.2“). Was der Prompt festlegt, gilt, soweit dieser Plan nicht ausdrücklich abweicht (Kapitel 4) oder ergänzt (Kapitel 5); der Plan wiederholt ihn nicht.
>
> **Entscheidungen des Nutzers vom 03.10.2026** auf die Bewertung des Prompts: **1a** Rechenkern in TypeScript im Browser, Rechendienst in Node neben FastAPI, IFC-Import in Python · **2a** L1 bleibt: dem Kunden gerundet mit „ca.“, exakte Beträge nur im Dossier · **3a** Satteldach und R+1 vor der Ablösung; der heutige Konfigurator läuft bis dahin parallel. Nach den Probedateien: alle klassischen Dachformen in HM5, für den Kunden frei wählbar (E-HM-10, E-HM-25); Zonen immer richtig finden, Nummern ignorieren (E-HM-23). Die übrigen Punkte der Bewertung (Nr. 3, 4, 6–10) gelten nach Empfehlung. Die Festlegungen in Kapitel 7 tragen je eine Empfehlung und gelten mit dem Auftrag zur Umsetzung als entschieden; sie gehen dann nach DECISIONS (Präfix `E-HM`).
>
> **Stand:** HM0 und HM1 umgesetzt am 03.10.2026 (Aufträge „ersten Teil des Plans umsetzen“ und „mit dem nächsten Punkt fortfahren“), HM3 am 04.10.2026 vor HM2 (Auftrag „Stelle HM3 fertig“); E-HM-1 bis E-HM-47 stehen in [DECISIONS](../DECISIONS.md) 4.11, Ergebnisse von Spikes, HM1 und HM3 in Kapitel 10.

## 1. Ziel und Abgrenzung

**Ziel:** Das Haus im Konfigurator wird ein parametrisches Gebäudemodell. Haustypen kommen als IFC aus dem Archicad des Büros, der Kunde wählt Wandaufbau, Fenster, Dach und später mehr. Geometrie, Mengen, Preis und Prüfungen leiten sich daraus ab, live in 2D und 3D. Grundstück, Regeln und Baurahmen (G1–G3) liefern weiter den Rahmen.

**Ersetzt:** H1 (Katalog aus XLSX und DXF, Spannenpreise je Typ, Linie, Option), den Hausteil von H2/H3 (Typ, Linie, Optionen, Kosten, Energiebefund) und die Darstellung des Hauses in V.

**Bleibt:** G1, G2, G3, A, die Analyse, Anmeldung, Jobs. Die Prüfung des Hauses auf dem Grundstück (`configuration/domain`: Lage, Fläche zulässiger Ursprünge, Schnellstellungen, Typzulässigkeit, PLU-Prüfungen) bleibt in Python und bekommt das Haus künftig vom Rechenkern (3.1).

**Nicht in diesem Plan:** Deutschland als Markt (nur das Feld `market`), Dachgeschoss mit Schrägen (`R+1+C`), Gauben und Dachfenster, konfiguriertes IFC für den Rückweg nach Archicad (P 17.1 „später“, X4), Innenausbau und Haustechnik als Slots (Modell trägt sie, P 22), Kundenkonten.

## 2. Ausgangslage

- **Katalog (H1):** Typversion mit Umriss aus DXF, Kennwerten aus XLSX, Fassadenrollen von Hand, Spannen-Basispreis; Linien und Optionen (`plain`, `terrace`, `carport`) mit festen Aufpreisen je Typ; Preiskatalog je Region; RE2020-Befund je Typ und Linie ([catalog/models.py](../backend/app/catalog/models.py)). Im Katalog stehen nur `demo_*`-Typen; echte Typen und Preise gibt es nicht (ROADMAP 4.4).
- **Konfiguration (H2/H3):** eine je Projekt; Typ-, Linien- und Optionsversionen sind festgehalten, Preise und Regeln werden bei jedem Abruf neu gerechnet. `PATCH` lehnt neue bindende Verstöße ab (HP01, HK08). Kosten als Spanne, auf 1.000 € gerundet (HK10, [costs.py](../backend/app/configuration/domain/costs.py)).
- **Haus auf dem Grundstück:** Die Python-Fachlogik braucht vom Haus nur `HouseType` ([house.py](../backend/app/configuration/domain/house.py)): Fassaden- und Projektionsumriss, Geschosse, Dachform, Neigung, Firstrichtung, Trauf- und Firsthöhe, Fassadenrollen, Garagentor. Daraus entstehen Fläche zulässiger Ursprünge, Typzulässigkeit, Schnellstellungen und rund 30 Prüfungen mit Fundstelle.
- **Übergabe (V):** Fassung mit Snapshot, Prüfstempel über sechs Teile (Plan V 3.3), bindende Verstöße nur mit Bestätigung (Plan V 3.4), Dossier-PDF für das Büro, DXF.
- **Archiv:** IFC war als Ausbau X3 geplant (Spez. 5.4, Anhang A; UMSETZUNGSPLAN 3.11), TypeScript im Backend verworfen, „besser, wenn IFC nie kommt“ (UMSETZUNGSPLAN 10.2). Der Nutzer zieht X3 mit dem Prompt vor.

## 3. Zielbild im Projekt

```text
Archicad ─IFC─► Worker long: IfcOpenShell (Kindprozess) ─► Template-Entwurf ─Freigabe─► Templateversion
                                                                        │
Katalogversion je Markt (Dokument, Preise inklusive) ───────────────────┤
                                                                        ▼
 Browser: packages/domain (TS) ── Resolver → Geometrie → Mengen → Preis → Katalogregeln → 2D/3D
    │  live, ohne Server                     │
    │                                        └─ Hausbeschreibung (Umrisse, Höhen, Dach, Rollen, Materialien)
    ▼                                                          │
 api (FastAPI) ──► engine (Node, dasselbe Paket) ─────────────┘
    │                                                          ▼
    └──► configuration/domain (Python): Lage, Fläche zulässiger Ursprünge, PLU-Prüfungen ◄── G1–G3
                     │
                     ▼
         house_configuration: Auswahl, Lage, Snapshot (Ergebnis, Versionen, Prüfstempel)
```

### 3.1 Grenze zwischen TypeScript und Python

- **TypeScript (`packages/domain`)** rechnet alles, was nur vom Haus abhängt: Auflösung der Slots, Geometrie, Mengen, Preis, Katalogregeln (technisch, Verfügbarkeit), U-Wert, Kompatibilitätsprüfung, SVG für Grundriss, Ansichten und Axonometrie. Es läuft im Browser (live, Web Worker) und im Dienst `engine` (maßgeblich, L5).
- **Python** behält alles, was vom Grundstück abhängt: G1–G3, die Auslegung der Regeln und die Prüfung des Hauses auf dem Grundstück. Der Kern übergibt dafür eine **Hausbeschreibung** (`HouseFacts`), die `HouseType` ersetzt: Fassadenumriss (Außenkante der äußersten Schicht, alle oberirdischen Geschosse), Projektionsumriss (mit Dachüberstand), Geschosse, Dachform (Begriffe der PLU-Regeln, Ergänzung 11), Neigungen je Dachfläche, Firstrichtung, Traufe, First oder Attika, Erdgeschoss über Gelände, Fassadenrollen, Eingang, Garagentor, Materialklassen von Fassade und Dach.
- **Im Browser** misst der Kern Abstände und Überbauung zur Vorschau; ob eine Lage zulässig ist, sagt die Fläche zulässiger Ursprünge, die der Server zur gewählten Hausbeschreibung liefert (wie heute in H2). PLU-Ergebnisse kommen nach einem Serveraufruf; ändert sich die Hausbeschreibung (z. B. Ziegelfassade), holt der Browser Fläche und Prüfung neu.

### 3.2 Rechenkern `packages/domain`

- pnpm-Workspace im Wurzelverzeichnis: `frontend`, `packages/domain`, `engine`. Paketname `@emprise/domain`, Bezeichner englisch, ohne Abhängigkeit zu React, DOM, Three.js oder Datenbank (P 2, Prinzip 4).
- Polygon-Offset und boolesche Operationen mit `clipper2-ts`, ganzzahlig in 0,1 mm (P 4); jeder Ring wird vorher mit `polygonDefect` geprüft (Spike HM0, Kapitel 10, E-HM-26, E-HM-27).
- Tests mit Vitest und fast-check; Testdaten des Demohauses eingefroren, Demo-Seed getrennt (P 19).

### 3.3 Rechendienst `engine`

- Node 24, ein kleiner HTTP-Dienst ohne eigenen Zustand, nur im Compose-Netz erreichbar. Endpunkte: `/evaluate` (Auflösung bis Hausbeschreibung, mit `evaluateCandidates`), `/compatibility`, `/render` (SVG), `/health`.
- Die API ruft ihn beim Speichern, beim Prüfen vor der Übergabe, beim Veröffentlichen (Kompatibilität) und im Dossier-Job. Fällt er aus, antwortet die API `503 engine_unavailable`; der Browser rechnet die Vorschau weiter.
- Auf Unraid ein Container mehr (10 → 11). Trivy prüft das Image wie Backend und Web.

### 3.4 Vertrag und Typen

- Die Typen an der Grenze (Template, Katalogversion, Auswahl, Hausbeschreibung, Ergebnis) sind **Pydantic-Modelle** in `backend/app/house/contract.py` und gehen über `openapi.json` nach TypeScript (`packages/domain/src/contract.gen.ts`, dasselbe Werkzeug wie `pnpm run api:types`). Die CI prüft, dass beide generierten Dateien aktuell sind. Solange keine Route ein Modell verwendet (HM1), nimmt `main.py` die Vertragsmodelle ausdrücklich in `components.schemas` auf. So bleibt es bei einer Quelle (README „Änderungen an der API“), und Python schreibt Templates (IFC-Import) und Katalogversionen typgeprüft.
- Interne Typen des Kerns (Zwischengeometrie, `DerivedModel`) bleiben nur in TypeScript.
- Die API prüft jede Antwort von `engine` gegen die Pydantic-Modelle.

### 3.5 Daten

| Prompt (P 16) | Hier | Bemerkung |
|---|---|---|
| `HouseTemplate`, `HouseTemplateVersion`, `ImportedTemplateDraft`, `ImportJob`, `ImportReport` | `house_template` (Identität, `slug`), `house_template_version` (Dokument JSONB, Status `draft`/`reviewed`/`published`/`rejected`/`retired`, Importbericht, IFC-Schlüssel und sha256) | Entwurf und Version in einer Tabelle (E-HM-9); der Job läuft über die bestehende Warteschlange |
| Material … `PricingRule`, `PriceCatalog` | `house_catalog` (je Markt), `house_catalog_version` (ein Dokument mit Bauteilen, Slots, Werten, Regeln, Preisregeln und Preiseinträgen) | eine Veröffentlichungseinheit (E-HM-8) |
| `CatalogCompatibility` | `house_catalog_compatibility` | Prüfbefund aus `engine`, Freigabe durch `catalog_admin` |
| `SiteRuleSet`, `SiteRuleSetVersion`, `Site` | bestehend: `site`, `rule_set_version`, `rule`, Baurahmen | aktuelle Fassung mit Prüfstempel (E-HM-7) |
| `SavedConfiguration` | `house_configuration` (eine je Projekt: Template- und Katalogversion, Auswahl, Lage in Lambert-93, Snapshot, `engine_version`) | neben der heutigen `configuration` bis zur Ablösung |
| `Submission` | bestehend: `inquiry` + `submission` (Snapshot Schema 3) | Zustände des Prompts auf die des Vorgangs abgebildet wie in Plan V 3.1 (`returned` → `rueckfrage`, `offerIssued` → `beantwortet`, `withdrawn` → `zurueckgezogen`) |

Veröffentlichte Versionen sind per Trigger unveränderlich wie heute (L4). Dateien: `house/ifc/<sha256>.ifc` im Dateiverzeichnis.

### 3.6 IFC-Import

- Upload unter `/buero/katalog` (Rolle `catalog_admin`), Größen- und Typprüfung, Audit (P 12.1). Job `house_ifc_import` in der Warteschlange `long`. IfcOpenShell läuft in einem **Kindprozess** mit Speicher- und Zeitgrenze, damit eine fehlerhafte Datei den Worker nicht mitnimmt.
- Ergebnis: Template-Entwurf und Importbericht (P 12.4). Im Entwurf bestätigt das Büro, was der Import vorschlägt, und ergänzt, was er nicht erkennt: Raumtypen, Fassadenrollen, Eingang (Vorschlag: Außentür in eine Zone vom Typ Entrée), Garagentor (Vorschlag: Außentür in eine Garage) und, falls es nicht im IFC steht, die Höhe des Erdgeschosses über Gelände.
- **Platzhalter (Nutzer, 03.10.2026):** Außenwände und Dach im IFC sind Platzhalter, ihren Aufbau wählt der Konfigurator aus dem Katalog. Von den Außenwänden liest der Import nur die Innenseite als Bezugskontur (`innerPolygon`) und die Öffnungen, vom Dach nur Form, Neigung, Auflagerhöhe und Überstand. Dicken, Schichten und Materialien der Platzhalter liest er nicht. Die Innenseite gilt als Innenkante der innersten Profilschicht (E-HM-24).
- **Geschosse:** Ein `IfcBuildingStorey` zählt als Geschoss, wenn es Wände oder Räume enthält. Eines nur mit dem Dach (Probedatei 2: „R+1“) ist die Dachebene.
- **Dach:** Der Kern erzeugt es aus Kantenprofilen (Ergänzung 11), statt den IFC-Körper zu übernehmen, weil sich der Fassadenumriss mit dem Wandprofil ändert. Der Import leitet aus den Dachflächen des IFC-Körpers je Kante der Bezugskontur Neigungen, Knickhöhen, Auflagerhöhe und Überstand ab und erzeugt daraus das Dach. Deckt es sich mit dem IFC-Dach (Firste, Grate, Kehlen, Traufen, Toleranz wie beim Template), ist die Form erkannt. Sonst meldet er den Fehler „Dachform nicht erkannt“, und das Büro setzt die Kantenprofile im Entwurf.
- **Zonen erkennen (Nutzer, 03.10.2026: Zonen immer richtig finden, Nummerierung ignorieren; E-HM-23).** Jede `IfcSpace` landet in genau einer Gruppe: Raumzone mit Raumtyp, ignoriert oder nicht erkannt. Keine geht still verloren, der Bericht nennt je Zone Quelle, Rohwert und Ergebnis.
  1. *Quellen*, in dieser Reihenfolge: Name des `IfcSpaceType` (Archicad schreibt die Zonenkategorie in IFC4 so, weil `Pset_SpaceCommon.Category` nur in IFC2x3 existiert), `Pset_SpaceCommon.Category` an Zone oder Typ, `ObjectType`, `LongName` (Zonenname), `Name` (Zonennummer), Name und Kennung der Klassifizierung. Es gilt die erste Quelle, deren Wert in der Zuordnungstabelle steht. Treffen spätere Quellen einen anderen Raumtyp, gibt es eine Warnung.
  2. *Normalisierung*, für Werte und Tabelle gleich: Akzente weg, Großschreibung, Satzzeichen und Unterstriche zu Leerzeichen. `/`, `+`, `&` und „et“ trennen Teile, deren Reihenfolge nicht zählt („Cuisine + Séjour“ = „SEJOUR/CUISINE“). Nummern fallen weg („CHAMBRE 1“, „Chambre_02“, „chambre n°3“, „CHAMBRE1“ → „CHAMBRE“).
  3. *Zuordnungstabelle* im Katalog: Aliasse je Raumtyp, nach der Normalisierung eindeutig (Prüfung beim Veröffentlichen). Dazu kommt eine Liste von Kategorien ohne Raum (z. B. SDP, SHAB, Emprise au sol). Diese Liste gilt nur für die Quellen „Typ“ und „Category“, damit ein Zonenname wie „SDP“ (Probedateien) keine Raumzone verwirft. Der Import nimmt die letzte veröffentlichte Katalogversion des Markts; Lücken fallen zusätzlich bei der Kompatibilitätsprüfung auf (P 2.1 Nr. 5).
  4. *Geometrie aus den Wänden:* Räume sind die Flächen zwischen den Wänden eines Geschosses (Toleranz 1 mm). Eine Raumzone gehört zu dem Raum, der mehr als die Hälfte von ihr enthält; das ist immer eindeutig. Die Zone liefert nur den Typ, der Umriss kommt aus den Wänden. So bleibt die Zuordnung richtig, auch wenn Zonen nach dem Verschieben von Wänden nicht aktualisiert wurden (Probedatei 2). Weichen die Zonen eines Raums zusammen um mehr als 1 % seiner Fläche von ihm ab (symmetrische Differenz), gibt es die Warnung „Zone nicht aktualisiert“. Kein Raum mit mehr als der Hälfte → Fehler. Mehrere Zonen in einem Raum (offene Wohnküche) teilen ihn entlang ihrer Umrisse; das bestätigt das Büro im Entwurf. Ein Raum ohne Zone gilt als nicht erkannt.
  5. *Entwurf:* Nicht erkannte Zonen und Räume weist das Büro einem Raumtyp zu oder ignoriert sie; veröffentlicht wird erst, wenn keine offen ist. Nummern und Zonennamen werden nicht übernommen; Kennung ist die `GlobalId`.
- Der Importvertrag (P 12.2) wird ein eigenes Dokument `docs/IFC_IMPORTVERTRAG.md`, weil das Büro ihn beim Modellieren liest (E-HM-17).

### 3.7 Ergebnisarten und Status

| Herkunft | Ergebnis | Wirkung |
|---|---|---|
| Katalogregel (technisch, P 8.3) | `info`, `warning`, `block` | `block` sperrt die Übergabe (P 17.1) |
| PLU-Prüfung, wirksame Regel verletzt | `deviation` (neu) | Übergabe nur mit Bestätigung (Plan V 3.4); im Dossier ausgewiesen |
| PLU-Prüfung, Regel `unknown` oder nicht prüfbar | `warning` | offener Prüfpunkt, hindert nie |
| PLU-Hinweis | `info` | – |

Status der Konfiguration, abgeleitet, nie gespeichert: `blocked` vor `withDeviations` vor `validWithWarnings` vor `valid`. Eine unzulässige Auswahl oder Lage wird gespeichert; nichts verändert die Auswahl still (P 2.1 Nr. 9). Das hebt HP01 und HK08 auf (E-HM-6). Unverändert bleiben D12 (ein Template ohne zulässige Lage ist gesperrt, mit allen Gründen) und D14 (Anfrage ohne Konfiguration).

### 3.8 Preise und Anzeige (Entscheidung 2a)

- Der Kern rechnet exakt (P 9), sonst stimmen die Aufpreise nicht.
- Der Kunde sieht: Gesamt brutto auf 1.000 € gerundet, Aufpreise auf 100 € gerundet, jeweils mit „ca.“ und dem Hinweis „Richtpreis, Prüfung durch das Büro“. Keine Aufschlüsselung in Positionen beim Kunden, damit getrennt gerundete Zeilen nicht von der Summe abweichen (B-65).
- Die Kunden-API liefert nur gerundete Beträge (L1). Exakte Beträge stehen im Snapshot und im Dossier für das Büro.
- Folge von Prinzip 5: Die Einheitspreise des Katalogs gehen an den Browser und sind damit öffentlich lesbar (E-HM-20).

### 3.9 Versionen

- Templateversion und Katalogversion werden mit der Konfiguration festgehalten; die Übernahme einer neueren ist eine ausdrückliche Aktion mit Vergleich (alter und neuer Preis, entfallene Werte, geänderte Ergebnisse, P 16).
- Grundstück und Regeln gelten immer im aktuellen Stand. Eine Änderung zeigt der bestehende Prüfstempel (Plan V 3.3) mit Vergleich an (E-HM-7).

### 3.10 Oberfläche

- Neue Komponenten in `frontend/src/haus/`: Konfigurationsleiste, Ansicht 2D | 3D | Grundstück, Preisleiste, Hinweise, Einzelkonfiguration (P 13–15). Zustand der Auswahl mit Zustand, Geometrie im Web Worker, 3D mit React Three Fiber als eigener Chunk.
- Zuerst als Vorschau im Büro (`/buero/katalog/vorschau`), dann für Kunden unter `/haus` hinter der neuen Fahne `house_model` (intern → Beta → alle, ADR-10). Einstieg aus `/grundstueck`, solange beide Konfiguratoren laufen.

### 3.11 Übergabe und Dossier

- Snapshot Schema 3 mit Versionen, Auswahl, exakten Beträgen, Mengen, Ergebnissen, Hausbeschreibung und SVGs.
- Dossier: Grundriss mit Bemaßung, Ansichten, Axonometrie (SVG aus dem Kern über `engine`, kein 3D-Rendering auf dem Server), Lageplan, Optionen, Mengen, Kosten exakt, Prüfergebnis mit Fundstellen, Versionen; dazu JSON (P 17.1) und DXF wie heute.

### 3.12 Parallelbetrieb und Ablösung (Entscheidung 3a)

- Bis zur Ablösung bleiben `/konfigurator`, H1-Katalog und Fahne `configurator` unverändert; das Hausmodell läuft unter `house_model`.
- Umgeschaltet wird in HM6: `/konfigurator` zeigt das Hausmodell; entfernt werden H1-Tabellen und -Pflege, XLSX/DXF-Import, Spannenpreise, `energy_assessment` und der Hausteil von `configuration` (Optionen, Kosten, Energie, `HouseType` aus dem Katalog). Die Fahne `house_model` entfällt.

## 4. Abweichungen vom Prompt

| Prompt | Hier | Grund |
|---|---|---|
| P 4: Node, tRPC, Zod, Drizzle als Backend | FastAPI, Alembic, OpenAPI bleiben; Node nur als Rechendienst | Entscheidung 1a; ein Backend, eine Datenbankmigration |
| P 3, 10.2: Bauvorschriften als Adapter im TS-Kern | PLU-Auslegung und -Prüfung bleiben in Python, der Kern liefert die Hausbeschreibung | 3.1; eine Auslegung der Regeln statt zweier, rund 2.350 getestete Zeilen in `configuration/domain` bleiben |
| P 4.1: Regel-Update unter 200 ms | gilt für Katalogregeln; PLU-Ergebnisse nach einem Serveraufruf | Folge der Zeile davor; gemessen in HM4 |
| P 4: ADRs in `docs/adr/`, `docs/ifc-spike.md` | DECISIONS (`E-HM`), Spike-Ergebnis in Kapitel 10 dieses Plans | ADR-08 |
| P 4: IFC-Bibliothek web-ifc oder IfcOpenShell | IfcOpenShell in Python | Entscheidung 1a; web-ifc bleibt Rückfall, falls der Spike scheitert |
| P 5.1.1: `ImportedTemplateDraft` getrennt | Entwurf als Status der Templateversion | E-HM-9 |
| P 5.2: `PriceCatalog` mit eigener Version | Preise in der Katalogversion | E-HM-8 |
| P 5.3, 8.3: Status `valid`/`validWithWarnings`/`blocked` | dazu `deviation`/`withDeviations` | 3.7; D11, Plan V 3.4 |
| P 9.3, 15: Beträge auf Cent und Euro beim Kunden | gerundet mit „ca.“ | Entscheidung 2a, L1 |
| P 16: `SiteRuleSetVersion` festgehalten | Grundstück und Regeln aktuell, Änderung über Prüfstempel | 3.9; Grundstücksrevisionen werden nicht aufbewahrt, und ein alter Regelstand wäre irreführend |
| P 17.2: Kundenkonten und Mandanten in Phase 4 | anonymes Projekt mit Zugangslink | L8, E-V5 |
| P 6.4, 21: nur Flachdach, ein Geschoss | alle klassischen Dachformen und R+1 vor der Ablösung | Entscheidung 3a, E-HM-25 |
| P 1: Märkte FR, dann DE | Feld `market`, nur FR | Kapitel 1 |
| P 6.1: Innenkante der tragenden Schicht ist die Referenz | Innenkante der innersten Profilschicht | Innendämmung (doublage) liegt vor der tragenden Schicht; so bleiben Räume bei jedem Profil gleich (E-HM-24) |
| P 12.3: Dach aus `IfcRoof`, Raum aus `IfcSpace` | Dach im Kern erzeugt, IFC liefert Parameter und Vergleich; Raumumriss aus den Wänden, Zone liefert den Typ | Platzhalter (3.6); Zonen werden in Archicad nicht immer aktualisiert |

## 5. Ergänzungen zum Prompt

1. **Höhenbezug:** Der Prompt misst ab Unterkante Bodenplatte, der PLU ab dem natürlichen Gelände. Das Template trägt die Höhe des Erdgeschosses über Gelände (IFC-Eigenschaft `Emprise.GroundFloorOffset` am Gebäude oder Eingabe im Entwurf, Standard 0,20 m, Spez. 5.4.3); das Gelände liefert G1, die Höhenprüfung bleibt in Python (E-HM-11).
2. **Zwei Umrisse:** Fassadenumriss (Außenkante der äußersten Schicht, P 6.2) und Projektionsumriss mit Dachüberstand. Welcher für eine Regel gilt, entscheidet die Python-Prüfung wie heute (E-HM-12).
3. **Fassadenrollen, Eingang, Garagentor:** werden im Entwurf zugewiesen und gehen in die Hausbeschreibung (Spez. 5.4.4). Sie richten Schnellstellungen, Terrasse und Zufahrt aus (E-HM-13).
4. **Dachform und Dachaufbau:** zwei Slots (E-HM-10).
    - „Dachform“ bietet für jeden Haustyp alle Formen der Ergänzung 11 an (Nutzer, 03.10.2026); voreingestellt ist die Form aus dem IFC.
    - Das Template trägt dafür nur Auflagerhöhe und Überstände (Traufe, Ortgang).
    - Neigung, Knick- und Krüppelhöhe kommen je Form aus dem Katalog als Voreinstellung mit Spanne; für die Form des IFC kommen sie aus dem IFC. Die Neigung ist innerhalb der Spanne einstellbar, damit sich PLU-Grenzen treffen lassen.
    - Bei Sattel-, Pult- und Krüppelwalmdach legt die Firstrichtung fest, welche Kanten Traufe und welche Giebel sind. Sie kommt aus dem IFC, sonst liegt der First längs der längeren Seite jedes Flügels. Sie lässt sich um 90° drehen (PLU-Regel `ridge_orientation`).
    - Kann der Kern eine Form für den Grundriss nicht erzeugen, ist sie mit Begründung gesperrt (`ResolutionNote`).
    - „Dachaufbau“ wählt Deckung, Dämmung und Gründach; `RoofType.kind` muss zur gewählten Form passen (`availableWhen`, z. B. Gründach nur bei flacher Neigung).
5. **Dachformen und R+1 (HM5):** Hülle je Geschoss, Fassadenumriss als Vereinigung der Geschosse, Dach nach Ergänzung 11, Giebelwände. Mengen über die Fassadenfläche je Segment; die Formel „Mittellinie × Fassadenhöhe“ (P 7) ist ihr Sonderfall bei konstanter Höhe, die Tests aus P 20 bleiben gültig. Dachfläche geneigt mit Überstand, je Dachfläche.
6. **Ausstattungslinie:** wird eine Voreinstellung, die mehrere Slots auf einmal setzt, auf ausdrückliche Wahl des Kunden. Es gibt keinen eigenen Linienaufpreis; der Preis ergibt sich aus den gesetzten Werten (E-HM-14).
7. **Nebenbauten:** Terrasse und Carport werden Slots mit Ziel `site`. Ihre Maße, Preise und Mengen rechnet der Kern; ihre Lage auf dem Grundstück, die Zufahrt und die Prüfungen (`annex`, `unsealed_min`, `parking`) bleiben in Python (`outbuildings.py`) (E-HM-14).
8. **Materialklassen:** Wandprofile und Dachtypen tragen eine Klasse für die PLU-Prüfung von Fassade und Dach (heute `package.regulatory`).
9. **Typzulässigkeit:** geprüft mit den Standardwerten des Templates (Spez. 5.4.6); eine Wahl, die die Lage unzulässig macht, wird `deviation` mit Vorschlag.
10. **Rollladenkasten:** Fenster mit Rollladen haben in Archicad eine Öffnung, die um den Kasten höher ist (Nutzer 03.10.2026; Probedateien: Öffnung 0,25 m über und 0,05 m unter dem Fenster). Der Import liest die Kastenhöhe als Abstand zwischen Oberkante Fenster und Oberkante Öffnung; der Wandabzug umfasst Fenster und Kasten. Ob der Kasten am Fenstertyp hängt (Option Rollladen) oder fest am Template, klärt HM1 mit dem Katalogmodell.
11. **Dachformen (Nutzer, 03.10.2026: Walmdächer sind üblich, alle klassischen Formen; E-HM-25):** Ein Dach wird je Kante der Bezugskontur beschrieben: Neigungsprofil (Neigung bis zu einer Höhe, darüber die nächste Neigung oder senkrecht) und Überstand. Dazu kommt die Auflagerhöhe auf der Bezugskontur (Probedatei 2: 3,77 m). Der Kern erzeugt daraus das Dach als gewichtetes gerades Skelett mit Profilwechseln in der Höhe („procedural extrusions“, Kelly und Wonka 2011). Ein Verfahren liefert so alle Formen, auch auf L-, T- und U-Grundrissen mit Kehlen und Graten:

    | Form | FR | Kantenprofil |
    |---|---|---|
    | Flachdach | toiture terrasse | keine Neigung, Attika |
    | Pultdach | monopente | eine Traufkante geneigt, die übrigen senkrecht |
    | Satteldach | deux pans | Traufkanten geneigt, Giebelkanten senkrecht |
    | Walmdach, Zeltdach | quatre pans, pavillon | alle Kanten geneigt (Zeltdach: quadratischer Grundriss) |
    | Krüppelwalmdach | demi-croupe | Giebelkanten bis zur Krüppelhöhe senkrecht, darüber geneigt |
    | Mansarddach | à la Mansart | steil bis zur Knickhöhe (brisis), darüber flach (terrasson), als Sattel- oder Walmform |

    Neigung und Überstand dürfen je Kante verschieden sein (Ortgang anders als Traufe). Mengen: Dachfläche je Fläche (geneigt, mit Überstand), Längen von First, Grat, Kehle, Traufe und Ortgang, Giebelwandflächen. Nicht enthalten: Gauben und Dachfenster (eigene Bauteile, später), versetzte Pultdächer und Dächer über Gebäudeteilen verschiedener Höhe (später, als Dachteile je Gebäudeteil).
    Für die PLU-Prüfung gibt der Kern die Dachform in den Begriffen der G2-Regeln an (`gable`, `hip`, `mono_pitch`, `flat`, `mansard`, `other`, `rules/domain/kinds.py`), dazu die Neigungen je Dachfläche. Die Zuordnung trifft Python. Krüppelwalm, Mischformen und die maßgebliche Neigung eines Mansarddachs sind im PLU nicht eindeutig: Sie bleiben offene Prüfpunkte (`warning`), bis die Auslegung festgelegt ist.

## 6. Phasen

Jede Phase wird einzeln beauftragt („weiter mit HM1“), endet mit grünen Prüfungen, einem Bericht und den Festlegungen in DECISIONS. Umfang grob: S klein, M mittel, L groß.

| Phase | Inhalt | Abnahme | Braucht vom Büro | Umfang |
|---|---|---|---|---|
| **HM0** Einrichtung und Spike | pnpm-Workspace im Wurzelverzeichnis (die Wurzel-`.gitignore` schließt `/package.json` für die Werkzeuge des Mockups aus; das entfällt), Build-Kontext des Web-Images auf die Wurzel mit `.dockerignore` (u. a. `ifc-proben/`), CI-Job für `packages/domain`. `engine` mit `/health` und einem `/evaluate`-Gerüst in Compose (lokal, E2E, Unraid) und Trivy. Spike IFC: IfcOpenShell-Wheel für Python 3.12 im Backend-Image (Größe, Kindprozess), eine echte Archicad-Datei auslesen nach P 12.3. Spike Clipper2: Ports vergleichen (Offset, Boolesch, Minkowski, 0,1 mm, Größe im Bundle). Spike Dach: gewichtetes Skelett mit Profilwechseln in TypeScript (Bibliothek, z. B. CGAL 6 als WebAssembly, gegen eigene Umsetzung), Walmdach der Probedatei 2 nachbauen und vergleichen. Entwurf `docs/IFC_IMPORTVERTRAG.md` | CI grün mit den neuen Jobs, Spike-Ergebnis in Kapitel 10, Bibliotheken entschieden | eine IFC aus Archicad (beliebiges Haus) | M |
| **HM1** Rechenkern | Vertrag in Pydantic, Typen generiert; das Datenmodell trägt schon Geschosse und das Dach als Kantenprofile (Ergänzung 11). Resolver mit `ResolutionNote`, `evaluateCandidates`, Ausdrücke (P 8.4), Geometrie (zunächst Flachdach, ein Geschoss), Mengen, Preis, Katalogregeln, U-Wert, Kompatibilitätsprüfung, Status. Testdaten und Demo-Seed getrennt; Node-Skript für die Szenarien P 19.7 | Tests P 20.1, 20.1.1, 20.2 grün; Ausgabe des Skripts gleich P 19.7 | – | L |
| **HM2** Oberfläche | 2D, 3D, Konfigurations- und Preisleiste, Hinweise, Einzelkonfiguration, FR/DE, Web Worker; als Vorschau im Büro mit Demo-Seed, noch ohne Grundstück. Referenzgeräte festlegen (DECISIONS), Zielwerte P 4.1 messen | Szenarien P 19.7 in 2D, 3D und Preis sichtbar; Kamera bleibt stehen; Messwerte in Kapitel 10 | – | L |
| **HM3** IFC-Import | Upload, Job im Kindprozess, Importbericht mit Vorschau, Entwurf (Raumtypen, Rollen, Höhe über Gelände), Veröffentlichung mit Kompatibilitätsprüfung über `engine` und Freigabe; Tabellen für Template und Katalogversion; Demo-Katalog per CLI | Referenz-IFC → Template gleich den Testdaten (1 mm, P 20.3); fehlerhafte Dateien → erwartete Meldungen; Zonenerkennung (3.6) mit Tabellentest der Schreibweisen und Quellen, Probedateien 1 und 2 vollständig erkannt | Referenz-IFC des Demohauses nach Importvertrag; Zonenkategorien des Büros | M–L |
| **HM4** Kundenweg | `house_configuration`, API für Kunde und Büro, Speichern über `engine` mit Snapshot. Hausbeschreibung → `configuration/domain` (Fläche, Lage, Schnellstellungen, Zulässigkeit, PLU-Prüfung); Ergebnisarten 3.7; Versionen 3.9; Seite `/haus` hinter `house_model`. Grundstücksszenarien P 19.6/19.7 als Python-Tests | Konfiguration lädt nach Katalogänderung unverändert; Server- gleich Browserpreis (Chromium); Playwright Kunde bis Speichern auf AD 65 | – | M–L |
| **HM5** Dachformen, R+1, Linien, Nebenbauten | Ergänzungen 5.3–5.8 und 5.11 in Kern, Import und Oberfläche | jede Form der Ergänzung 11 aus einer Archicad-Probe erkannt und gleich erzeugt (L-Grundriss eingeschlossen); ein echter Typ des Büros (R+1) aus IFC, auf AD 65 konfiguriert, Prüfungen wie im heutigen Konfigurator | echte Typen als IFC; je Dachform eine Probe | L |
| **HM6** Übergabe, Katalogpflege, Ablösung | Snapshot Schema 3, Übergabe mit 3.7, Dossier und JSON (3.11); Pflege der Katalogversion (Arbeitsmappe mit einem Blatt je Art importieren, prüfen, veröffentlichen), Kompatibilitätsfreigabe, Übernahme neuer Versionen in gespeicherte Konfigurationen; Umschalten und Entfernen nach 3.12 | Ende-zu-Ende P 20.3 mit Playwright bis zur Übergabe; Büro sieht Fassung und Dossier | echte Katalogwerte (Profile, Fenster, Dächer, Preise) | M–L |

Kosten: keine Aufrufe des Sprachmodells (der Import kommt ohne KI aus, P 12.1). Recht: keine neue Frage, L1 bleibt (2a). Betrieb: ein Container mehr, ein größeres Backend-Image (IfcOpenShell).

## 7. Festlegungen mit Empfehlung

| Nr. | Festlegung | Empfehlung und Grund |
|---|---|---|
| E-HM-1 | Technik | **Entschieden 03.10.2026 (Nutzer, 1a):** TS-Kern im Browser und in `engine`, FastAPI bleibt, IFC in Python |
| E-HM-2 | Preisanzeige | **Entschieden 03.10.2026 (Nutzer, 2a):** wie 3.8 |
| E-HM-3 | Umfang vor der Ablösung | **Entschieden 03.10.2026 (Nutzer, 3a):** Satteldach und R+1 vorher, Parallelbetrieb (3.12); erweitert um alle klassischen Dachformen (E-HM-25) |
| E-HM-4 | Grenze TS ↔ Python | Hausbeschreibung als Schnittstelle, PLU-Prüfung bleibt in Python (3.1) |
| E-HM-5 | Quelle der Typen | Pydantic, generiert nach TS (3.4) |
| E-HM-6 | Ergebnisarten und Status | wie 3.7; HP01 und HK08 aufgehoben, D12 und D14 bleiben |
| E-HM-7 | Versionen | Template und Katalog festgehalten, Grundstück und Regeln aktuell mit Prüfstempel (3.9) |
| E-HM-8 | Katalogversion | ein Dokument je Markt mit Preisen; eigene Preisversion erst, wenn Preise häufiger wechseln als Bauteile |
| E-HM-9 | Template-Entwurf | Status der Templateversion statt eigener Tabelle |
| E-HM-10 | Dachform | **Entschieden 03.10.2026 (Nutzer):** jede Form der Ergänzung 11 für jeden Haustyp wählbar, voreingestellt die Form aus dem IFC; Aufbau als eigener Slot. Empfehlung dazu: Neigung mit Spanne aus dem Katalog einstellbar, Firstrichtung drehbar, nicht erzeugbare Formen gesperrt mit Begründung (Ergänzung 4) |
| E-HM-11 | Höhenbezug | Erdgeschoss über Gelände im Template, Standard 0,20 m |
| E-HM-12 | Umrisse | Fassade und Projektion wie heute |
| E-HM-13 | Rollen, Eingang, Garagentor | im Entwurf bestätigt; Vorschlag aus dem IFC (Außentür in die Entrée bzw. Garage, 3.6) |
| E-HM-14 | Linie, Nebenbauten | Linie als Voreinstellung, Nebenbauten als Slots `site` mit Lage und Prüfung in Python |
| E-HM-15 | Kundenkonten | keine |
| E-HM-16 | Markt | Feld `market`, nur FR, eine Region |
| E-HM-17 | Dokumente | Festlegungen in DECISIONS; `docs/IFC_IMPORTVERTRAG.md` als einzige Ausnahme zu ADR-08 (Leser ist das Büro, nicht der Code) |
| E-HM-18 | Bilder im Dossier | SVG aus dem Kern, kein Rendering auf dem Server |
| E-HM-19 | IFC sicher verarbeiten | Kindprozess mit Grenzen, Datei nur über die API, Audit |
| E-HM-20 | Einheitspreise im Browser | annehmen: der Konfigurator zeigt Richtpreise ohnehin öffentlich; sonst käme jeder Preis erst vom Server (P 4.1 verfehlt) |
| E-HM-21 | Fahne | neue Fahne `house_model`, entfällt mit der Ablösung |
| E-HM-22 | Alte Daten bei der Ablösung | keine Übernahme (nur `demo_*`-Typen und Testvorgänge); vorher auf Unraid prüfen, ob echte Vorgänge bestehen |
| E-HM-23 | Zonenerkennung | **Entschieden 03.10.2026 (Nutzer):** Zonen immer richtig finden, Nummerierung ignorieren; Regel 3.6 (Quellen, Normalisierung, Aliasse im Katalog, Umriss aus den Wänden) |
| E-HM-24 | Bezugskante der Außenwand | Innenseite der Platzhalterwand = Innenkante der innersten Profilschicht: Räume bleiben bei jedem Profil gleich, Profile mit Innendämmung möglich; Zonen in Archicad bis zu dieser Kante |
| E-HM-25 | Dachformen | **Entschieden 03.10.2026 (Nutzer):** Walmdächer sind üblich; alle klassischen Formen in HM5, vor der Ablösung. Umsetzung über Kantenprofile und ein Skelettverfahren (Ergänzung 11) |

## 8. Auswirkungen auf Dokumente und Betrieb

Bei der Umsetzung, je Phase: ARCHITECTURE (Dienst `engine`, `packages/domain`, Modul `app/house`, Abhängigkeiten), DOMAIN (Glossar: Template, Slot, Wert, Profil, Schicht; Fachregeln 4.5 neu), DECISIONS (`E-HM`), README (Workspace, Befehle, Stolperstellen), `deploy/unraid/README.md` (Container `engine`, Image-Größe). Nach HM6 kommen dieser Plan und der Prompt ins Archiv.

## 9. Risiken

| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| Archicad-Export liefert die Semantik nicht (`IsExternal`, Raumbegrenzungen, Schichten) | Import unvollständig | Spike HM0 mit echter Datei vor HM1; Rückfälle aus P 12.3; Importvertrag |
| Dachformen und R+1 aufwendiger als das Flachdach | HM5 groß, Ablösung später | Modell von Anfang an mehrgeschossig und mit Kantenprofilen (HM1); alle Formen über ein Verfahren (Ergänzung 11) |
| Gewichtetes Skelett mit Profilwechseln hat viele Sonderfälle (gleichzeitige Ereignisse, Rundung); keine bewährte TS-Bibliothek bekannt | Dächer falsch oder Abbruch bei ungewöhnlichen Grundrissen | Spike HM0 bestanden (Kapitel 10); feste Toleranzen; Vergleich gegen Archicad-Dächer je Form; Import lehnt nicht erkannte Formen sichtbar ab |
| `clipper2-ts` hängt bei nicht einfachen Ringen (Kapitel 10) | Browser-Tab oder `engine` blockiert | `polygonDefect` vor jedem Aufruf (E-HM-27); Fehlerbericht; Rückfall `clipper2-wasm` |
| Zwei Laufzeiten (Python, Node) | mehr Betrieb und Abhängigkeiten | `engine` ohne Zustand und ohne Port nach außen; Trivy; Gesundheitsprüfung |
| Browser rechnen trigonometrische Funktionen nicht gleich | Browserpreis weicht im Cent ab | Geometrie ganzzahlig (0,1 mm), Beträge mit einer Rundungsregel; Server maßgeblich (L5); Gleichheit in Chromium geprüft |
| 3D auf Mittelklasse-Telefonen zu langsam | Ziele P 4.1 verfehlt | messen in HM2, 3D als eigener Chunk, Neuaufbau nur geänderter Elemente |
| Katalogdaten (Profile, Preise je m²) fehlen | kein echter Betrieb | Demo-Seed bis HM6; Katalogpflege per Arbeitsmappe wie heute |

## 10. Ergebnisse von Spike und Messungen

Wird je Phase ausgefüllt: IFC-Datei, gefundene Eigenschaften und Beziehungen je Zeile von P 12.3, Abweichungen, gewählter Clipper2-Port mit Messwerten, Image-Größen; Messwerte zu P 4.1 auf den Referenzgeräten.

**Probedatei 1 (03.10.2026):** `ifc-proben/test_building_1_ifc.ifc` (nicht in Git), Archicad 28, Übersetzer „03 - Paramétrique (IFC4)“ = IFC4 Design Transfer View, Meter. Ein Geschoss, 10 Wände, 4 Fenster, 5 Türen, 5 Zonen, Bodenplatte; kein Dach, keine Decke. Gelesen mit IfcOpenShell 0.9.0 unter Python 3.12 (Linux-Wheel, installiert rund 233 MB).

| P 12.3 | Befund |
|---|---|
| Wand außen/innen | `Pset_WallCommon.IsExternal` kommt an, ist aber bei allen 10 Wänden `true`, auch bei den 4 Innenwänden (0,10 m); ebenso `LoadBearing`. Rückfall über die Vereinigung der Räume trennt richtig |
| Innenkante der Hülle | ohne Raumbegrenzungen (Option aus). Achsen der Außenwände liegen auf der Innenseite (`IfcMaterialLayerSetUsage`, Versatz 0); Innenkontur daraus geschlossen, L-Form 55,00 m² = Fläche der Bodenplatte. Wände berühren sich nur Kante an Kante mit Rundungsrauschen; mit 1 mm Toleranz geschlossen |
| Schichten | Außenwand einschichtig („0_GEN - Structurel“ 0,30 m): gewollt, Platzhalter (Nutzer, 03.10.2026; 3.6). Schichten im IFC werden nicht gelesen |
| Öffnung → Wand | alle 9 über `IfcRelFillsElement`/`IfcRelVoidsElement`. Öffnungskörper größer als Nennmaß: Fenster +0,30 m in der Höhe, davon 0,25 m oben = Rollladenkasten (Nutzer; Sturz der Öffnung einheitlich 2,50 m, Fenster bis 2,25 m; Ergänzung 10) und 0,05 m unten, Türen +7 cm Breite, +4 cm Höhe. Wandabzug aus `IfcOpeningElement`, Typmaße aus `OverallWidth`/`OverallHeight` |
| Öffnung → Raum | geometrisch eindeutig: jedes Fenster ein Raum, jede Innentür zwei Räume. Einzige Außentür PP106 (2,10 × 2,40 m) ist die Haustür (Nutzer) und führt in die Zone ENTREE: Eingang ließe sich vorschlagen (E-HM-13) |
| Geschosse | `IfcBuildingStorey` „RDC“, Höhe 0,00 |
| Dach | fehlt im Modell |
| Räume | 5 `IfcSpace`, Flächen gleich den Räumen zwischen den Wänden. Zonenkategorie (in Archicad `Category` aus `Pset_SpaceCommon`) kommt als Name des `IfcSpaceType` über `IfcRelDefinesByType`, alle 5 zugeordnet: CHAMBRE 1 (13,72 m²), CHAMBRE 2 (10,18), ENTREE (8,70), SEJOUR/CUISINE (15,60), SALLE DE BAIN/WC (5,16). `Pset_SpaceCommon.Category` gibt es in IFC4 nicht mehr, deshalb fehlt das Pset. `Name` (Zonennummer) leer, `LongName` (Zonenname) „SDP“, Typ `GFA`, Klassifizierung „Surface de plancher SP“. Erkennung nach 3.6 (Probe im Spike): alle 5 aus dem Typ erkannt, „CHAMBRE 1/2“ → Chambre; keine Überlappung, jeder Raum zwischen den Wänden zu 100 % bedeckt |
| sonst | keine Proxys, keine Teile; Basismengen und Raumbegrenzungen aus; Bodenplatte `FLOOR` statt `BASESLAB`; Gebäude nicht am Projektnullpunkt (x ≈ 10–21, y ≈ 13–20); Fenster heißen nach Typ (F-02, F-03, PF-02), Namen doppelt |

**Probedatei 2 (03.10.2026):** `ifc-proben/test_building_2_ifc.ifc`, gleiche Export-Optionen. Gegenüber Datei 1:

| Thema | Befund |
|---|---|
| Wand außen/innen | behoben: 6 `MUR_EXT` mit `IsExternal`/`LoadBearing` = `true`, 4 `CLOISON` mit `false`, Typ `PARTITIONING`, UniFormat „Interior Fixed Partitions“ |
| Trennwände | 3 von 4 um 5 cm verschoben; Zimmer jetzt 3,00 m breit. Wandhöhe unverändert 3,77 m, Decke fehlt weiter |
| Zonen | nach dem Verschieben **nicht aktualisiert** (Umrisse wie in Datei 1): Chambre 2 ragt 0,32 m² in Wände, Chambre 1 und Entrée je 0,15 m²; in Bad/WC 0,24 m², Chambre 1 0,23 m² und Entrée 0,15 m² ohne Zone. Regel 3.6 Nr. 4 ordnet trotzdem richtig zu (jede Zone liegt zu 96,9–100 % in ihrem Raum) und warnt |
| Dach | `IfcRoof` „TOITURE“, Typ „0_GEN - Membrane ext. 300“ (Platzhalter), Körper als Dreiecksnetz (`Tessellation`), keine aggregierten Platten, `Pset_RoofCommon`. Form: **Walmdach** auf dem L-Grundriss, 20° auf allen Seiten, Überstand 0,50 m ab Außenseite der Platzhalterwand, Dicke 0,30 m. Firste und Grate sind genau das gerade Skelett der Bezugskontur (First y = 15,272 über dem 4,00 m tiefen Flügel, x = 13,641 über dem 6,00 m breiten), Dachunterseite auf der Bezugskontur bei 3,77 m. Oberkante First 5,18 m; Traufkante unten 3,48 m, oben 3,80 m |
| Geschosse | neues `IfcBuildingStorey` „R+1“ auf 3,77 m enthält nur das Dach: Dachebene, kein Geschoss (3.6) |

**Spike HM0 (03.10.2026), Clipper2-Port.** Bezugskontur der Probedatei 2 in 0,1 mm, Wand 0,30 m; Laufzeit für 2000-mal Offset und Vereinigung eines Polygons mit 24 Ecken; Bündel minimiert, gzip.

| Port | Offset (soll 65,26 m², 6 Ecken) | Boolesch, Minkowski | Laufzeit | Bündel | Befund |
|---|---|---|---|---|---|
| `clipper2-ts` 2.0.1-18 (countertype, BSL-1.0, ohne Abhängigkeiten) | richtig, ganzzahlig | richtig | 128 ms | 17 kB | **gewählt** (E-HM-26); hängt bei Rücklauf, siehe unten |
| `clipper2-js` 1.2.4 | 58,86 m², 11 Ecken | Minkowski-Hülle 2,02 statt 1,21 m² | 413 ms | 19 kB | rechnet falsch, ausgeschieden |
| `clipper2-wasm` 0.4.0 (C++-Original) | richtig | richtig | 74 ms | 10 kB JS und 82 kB WebAssembly | Rückfall: asynchroner Start, Speicher von Hand freigeben, die CSP bräuchte `'wasm-unsafe-eval'` |

Befund aus dem Dach-Spike: `union` von `clipper2-ts` läuft bei einem Ring, der auf einer Linie zurückläuft (Minimalbeispiel `(0,0) (100,0) (90,0) (89,5) (11,5) (10,0) (5,0)`), endlos und belegt Speicher bis zum Abbruch; Version 2.0.1 ebenso. `clipper2-js` und das C++-Original liefern das Trapez. Einfache Polygone, auch mehrere überlappende, sind nicht betroffen (20 000 Zufallsfälle). Gegenmaßnahme im Kern: `polygonDefect` prüft jeden Ring vor Clipper2 exakt in Ganzzahlen (höchstens 1 km, keine doppelten Punkte, keine Berührung außer der gemeinsamen Ecke von Nachbarn, kein Rücklauf) und wirft `GeometryError`; `engine` antwortet 422 (E-HM-27). Ein Fehlerbericht mit dem Minimalbeispiel an countertype/clipper2-ts steht aus.

**Spike HM0, Dach.** Bibliotheken: Keine bietet ein gewichtetes Skelett in JavaScript oder TypeScript. `straight-skeleton` 3.0 und `@matthewjacobson/str8` 0.5 binden CGAL `Straight_skeleton_2` als WebAssembly ein; sie sind ungewichtet, und das CGAL-Paket steht unter GPL, was im Browser-Bündel den Konfigurator unter die GPL zöge. `@proc-geo/core`, `@dvanauken/straight-skeleton` und `straight-skeleton-geojson` sind ungewichtet oder Alpha. Daher eigene Umsetzung (E-HM-28).

Prototyp `packages/domain/spike/roof/skeleton.ts` (rund 360 Zeilen, Gleitkomma in Metern, nicht aus dem Paket exportiert): Wellenfront mit der Höhe als Zeit; Kantenereignis, Teilungsereignis und Profilwechsel als Ereignis in fester Höhe, gleichzeitige Ereignisse gemeinsam. Werden nach einem Ereignis parallele Kanten Nachbarn, endet bei gleicher Richtung die steilere Fläche waagerecht, bei Gegenrichtung fällt der Sporn auf der Länge der kürzeren Kante zu einem First zusammen. Die Flächen entstehen aus den Bahnen der Ecken.

| Prüfung | Ergebnis |
|---|---|
| Walmdach der Probedatei 2 | alle 20 Knoten des Archicad-Dachs (Unter- und Oberseite, Firste, Traufen) innerhalb 1 mm: Skelett der Traufkontur (Bezugskontur + 0,80 m), Auflager 3,77 m auf der Bezugskontur, 20°, Dicke 0,30 m (lotrecht 0,3193 m) |
| Formen mit erwarteten Knoten | Satteldach, Pultdach, Walmdach mit steileren Walmen, Krüppelwalm (Giebel bis 2 m), Mansardwalm (Knick bei 2,2 m) auf dem Rechteck |
| Formen auf Grundrissen | Walm, Sattel, Krüppelwalm, Mansarde, Mansardsattel auf Rechteck, L, T, U |
| Invarianten, in jedem Fall | jeder Punkt einer Fläche liegt auf ihrem Neigungsprofil (1 µm); die Grundrisse der Flächen decken die Kontur ohne Lücke und Überlappung |
| Zufallsgrundrisse | 20 000 Fälle (Vereinigung bis vier Rechtecke im 0,5-m-Raster, geschert), davon 11 277 einfache Konturen gerechnet; gleiche und verschiedene Neigungen, Mansarde mit verschiedenen Knickhöhen, Giebel an beliebigen Kanten, Krüppelwalm: keine Abweichung. Rund 260 Ecken je ms. Ein Eigenschaftstest mit 300 Fällen läuft in der CI |

Für HM5 folgt daraus: (1) Kanten auf einer Geraden vorher zusammenfassen; der Prototyp lehnt sie ab. (2) Ein Giebel an einer Kante neben einer einspringenden Ecke wird im Skelett eine senkrechte Wand ins Hausinnere (zulässig, als Dach unsinnig): Giebel nur an Kanten mit zwei ausspringenden Ecken (Flügelenden), sonst ist die Form gesperrt (E-HM-10). (3) Toleranzen fest in 0,1 mm statt Gleitkomma-Schwellen. (4) Überstand: Das Skelett der Traufkontur stimmt nur bei gleicher Neigung und gleichem Überstand an allen Kanten; sonst die Flächen über die Bezugskontur hinaus als Ebenen bis zur Traufe verlängern.

**Spike HM0, IFC im Backend-Image.** IfcOpenShell 0.9.0 (Wheel für Python 3.12, `numpy` und `shapely` sind schon im Image): Backend-Image unkomprimiert 1,25 → 1,56 GB, komprimiert +67 MB; das Paket selbst 234 MB. Kindprozess mit `RLIMIT_AS` und Zeitlimit:

| Fall | Ergebnis |
|---|---|
| Probedatei 1 und 2 (192 kB) | 1,1 s: Start 0,4 s, Öffnen 0,02 s, Geometrie von 36 Bauteilen 0,5 s; Spitzenspeicher 81 MB |
| Adressraum 512 MB, 256 MB | läuft |
| Adressraum 160 MB und weniger | Abbruch beim Laden von numpy/OpenBLAS, Rückgabewert 1 mit Meldung; der Elternprozess läuft weiter |
| halbe Datei | `RuntimeError` bei der Geometrie der ersten Wand |
| Zufallsbytes | `ifcopenshell.Error: Unable to parse IFC SPF header` |
| nur Kopf, ohne Daten | öffnet, alles leer: der Import muss „kein Geschoss“ als Fehler melden |
| Zeitlimit 0,3 s | Kindprozess beendet |

Anfangswerte für HM3: 1 GB Adressraum, 120 s, `OPENBLAS_NUM_THREADS=1` (E-HM-19); an einer großen Büro-Datei nachmessen.

**HM1 (03.10.2026), Rechenkern.** Ausgabe von `pnpm run scenarios` mit den Testdaten; gleich P 19.7. Die Grundstückszeilen rechnet Python ab HM4, den Dachaufbau in 3D zeigt HM2; Holz nennt zusätzlich Innenmaß und Wanddicke.

| Szenario | Ergebnis |
|---|---|
| Ausgangszustand | Innen 8,00 × 12,00; außen 8,72 × 12,72 m; Netto 429.328,51 € |
| Ziegelfassade | Innen unverändert; außen 8,96 × 12,96 m; Wand 48 cm; Fassadenschichten +5.002,72 €, Auflager 43,52 m × 45 € = +1.958,40 €, gesamt +6.961,12 €; Laibungsfläche 3,792 m² |
| Holzfassade | Innen unverändert; außen 8,88 × 12,88 m; Wand 44 cm; +8.118,22 €; kein Auflager; Laibungsfläche 2,528 m² |
| Bodentief global (Standardfassade) | Auswahl bleibt global „Bodentief“; effektiv 5 Fenster bodentief, Bad-Fenster Standard mit `ResolutionNote`; Status `valid`; Fensterpositionen unverändert; Fenster +2.000 €, Wand −648 €, gesamt +1.352 € |
| Gründach | Dachaufbau 0,28 m; Dachfläche 110,92 m²; +8.873,47 € |

Tests: Kern 134 (P 20.1 mit 28, P 20.1.1 mit 8, P 20.2 mit 6 Eigenschaften, Ausdrücke 20, Kompatibilität 22, Szenarien, Geometrie aus HM0), `engine` 13, Vertrag in Python 12. Laufzeit von `evaluate` für das Demohaus (Node 24.18 auf dem Entwicklungsrechner, Median und p95 aus 200 Läufen): Standard 0,16 / 0,51 ms; drei gewählte Slots mit Aufpreisen 0,49 / 1,10 ms; dazu die Kandidaten des Fenster-Slots 0,67 / 1,45 ms. Die Ziele aus P 4.1 (Preis 200 ms, Kandidaten 300 ms, Server 1 s) sind weit unterschritten; gemessen wird im Browser auf den Referenzgeräten in HM2. Bündel von `engine` 183 kB (nicht minimiert, mit `clipper2-ts`).

**HM3 (04.10.2026), IFC-Import.** Umgesetzt vor HM2; Festlegungen E-HM-37 bis E-HM-46. Die Referenz-IFC und die Zonenkategorien des Büros fehlen noch: Für die Referenz steht ein synthetisches Demohaus, für die Kategorien die Aliasse des Demo-Katalogs.

| Abnahme | Ergebnis |
|---|---|
| Referenz-IFC → Template gleich den Testdaten (1 mm) | `tests/house_support.py` schreibt das Demohaus der Testdaten mit IfcOpenShell als IFC4 wie Archicad (Zonenkategorie als `IfcSpaceType`, Öffnung mit Rollladenkasten, Bodenplatte, Flachdach). Import und Fassadenrollen → Template gleich `template.json`; über die API mit Upload, Job, Prüfung in `engine` und Freigabe ebenso. Liegt `ifc-proben/demohaus_referenz.ifc` vor, läuft derselbe Vergleich mit ihr (bis dahin übersprungen) |
| Fehlerhafte Dateien → erwartete Meldungen | Zufallsbytes, fremdes Schema, nur Kopf, abgeschnittene Datei, Speicher- und Zeitgrenze im Kindprozess, fehlende Bodenplatte, fehlendes oder geneigtes Dach, offene Hülle, Zone außerhalb der Räume, nicht aktualisierte Zone, Fenster ohne Typ im Katalog: je der erwartete Code und Schweregrad. Jeder Code hat einen Text in FR und DE (E-HM-46) |
| Zonenerkennung | Tabellentests der Schreibweisen (Akzente, Nummern, Unterstriche, Teile in anderer Reihenfolge) und der Quellen (Reihenfolge, Widerspruch, Kategorien ohne Raum, Eindeutigkeit der Tabelle). Probedateien 1 und 2: je 5 von 5 Zonen aus dem Typ erkannt (Wohnen, Flur, Bad, zweimal Schlafzimmer), in Datei 2 trotz der nicht aktualisierten Zonen (vier Warnungen „Zone nicht aktualisiert“) |

Probedateien mit dem Demo-Katalog: Datei 1 meldet den Fehler „Kein Dach gefunden“, Datei 2 „Dachform nicht erkannt“ (Walmdach 20°, ab HM5), Datei 1 dazu viermal `IsExternal` an Innenwänden. In beiden bleiben 4 Fenster (1,80 × 1,25 bzw. 2,15 m, Sturz 2,25 m, Rollladenkasten 0,25 m) und die Haustür (2,10 × 2,40 m) offen, weil der Demo-Katalog solche Typen nicht hat; der Eingang wird erkannt. Veröffentlichen lässt sich keine Probedatei, bis echte Katalogtypen (HM6) und Dächer (HM5) da sind.

Laufzeit des Jobs im lokalen Stack, mit Start des Kindprozesses: Demohaus (39 kB) 1,3–1,9 s, Probedatei 1 (193 kB) 1,1 s. Tests: Backend zum Hausmodell 116 (dazu 1 übersprungen, die Referenz-IFC; ganzes Backend 943), Frontend 25 (Seiten und Texte), Kern 140, `engine` 13. Von Hand im lokalen Stack geprüft: Upload, Import, Entwurf mit Namen und Fassadenrollen, Prüfung im echten `engine`, Freigabe, Verwerfen, Sperre nach dem Veröffentlichen, Französisch und Deutsch. Ein Playwright-Test für diesen Weg fehlt noch.

**HM4 (04.10.2026), Kundenweg.** Umgesetzt vor HM2 mit schlanker Oberfläche (E-HM-56); Festlegungen E-HM-48 bis E-HM-57. Die Templates kommen bis zur Referenz-IFC aus dem Demohaus (HM3).

| Abnahme | Ergebnis |
|---|---|
| Konfiguration lädt nach Katalogänderung unverändert | Integrationstest: Preise ×1,1 als Katalogversion 2 mit Templateversion 2, Version 1 zurückgezogen. Die gespeicherte Konfiguration lädt mit Version 1 und Katalog 1, Preis und Ergebnisse unverändert, `update_available`; `engine` erhält die alten Preise. Ein neues Projekt bekommt Version 2 mit Katalog 2 |
| Server- gleich Browserpreis (Chromium) | Playwright: Chromium rechnet die Ziegelfassade und schickt den Nettopreis mit, der Server antwortet `price_match: true` und zeigt denselben gerundeten Betrag. Vitest: Kern im Browser gleich den gespeicherten Antworten von `engine` (vier Fälle), Rundungstabelle gleich der in Python |
| Playwright Kunde bis Speichern auf AD 65 | `e2e/haus.spec.ts`: Parzelle AD 65, Demohaus zulässig mit „ab ca. 515.000 €“, Typwahl mit Lage `street_near`, Fassade gewählt und gespeichert, nach Neuladen derselbe Stand |

Grundstücksszenarien P 19.6/19.7 in Python (`tests/unit/test_house_site_check.py`): Grundstück 18 × 12 m, Abstände 1,5 m, Haus mittig.

| Fall | Abstand zu den Längs- / Schmalseiten des Grundstücks | Überbauung | mit 55 % (P 19.6) | mit 52 % (P 20.1) |
|---|---|---|---|---|
| Standard | 1,64 / 2,64 m | 51,35 % | zulässig | zulässig |
| Ziegel | 1,52 / 2,52 m | 53,76 % | zulässig | Abweichung, kein Vorschlag (keine Lage behebt sie) |
| Holz | 1,56 / 2,56 m | 52,95 % | zulässig | Abweichung, kein Vorschlag |

Dazu: Ziegel bei 1,60 m Straßenabstand ist an der Lage des Standardhauses eine Abweichung mit Vorschlag weniger als 0,2 m daneben (Ergänzung 9); Material der Fassade aus dem Wandprofil geprüft; ohne Lage nur der Typ.

Laufzeiten im lokalen Stack (Docker auf dem Entwicklungsrechner, AD 65, Zone Uh, je 6 bis 9 Aufrufe aus den Ende-zu-Ende-Läufen): `PATCH` mit `engine` und PLU-Prüfung 160–341 ms (Median 249), `GET` der Konfiguration ohne `engine` 172–375 ms, Haustypen mit Zulässigkeit 243–481 ms, Fläche der Ursprünge 118–258 ms, Dokumente 32–50 ms. Das Ziel aus P 4.1 für den Server (1 s) ist eingehalten; die Ziele im Browser misst HM2 auf den Referenzgeräten. Seite `/haus` als eigener Chunk 106 kB (gzip 31 kB) mit Kern und `clipper2-ts`.

Tests: Backend zum Kundenweg 60 (Einheiten 45, Integration 15), Frontend 30 (Rundung, Kern, Seite), Kern 141 (dazu die Aktualität von `evaluations.json`), Ende-zu-Ende 2.

Offen aus HM2 (nicht nachgeholt, E-HM-56): 2D und 3D, Web Worker, Wahl je Raum oder Element, Vorschau im Büro, Messung P 4.1 auf den Referenzgeräten.

## 11. Selbstprüfung

### 11.1 Prüfprotokoll

| Nr. | Fehler im ersten Entwurf | Folge | Behoben in |
|---|---|---|---|
| 1 | `engine` erst mit dem Kundenweg geplant; die Kompatibilitätsprüfung (P 2.1 Nr. 5) ist aber Teil des TS-Kerns, und das Veröffentlichen löst sie in Python aus | HM3 nicht umsetzbar | `engine` in HM0 (3.3, 6) |
| 2 | PLU-Prüfung als Adapter im TS-Kern (wie P 10.2) geplant; G3 legt dieselben Regeln (z. B. Abstand H/2) in Python aus | zwei Auslegungen derselben Regel, Fläche zulässiger Ursprünge und Prüfung könnten auseinanderlaufen (heute per Eigenschaftstest gesichert) | Hausbeschreibung als Grenze, Prüfung bleibt in Python (3.1, E-HM-4) |
| 3 | `SiteRuleSetVersion` festhalten wie P 16 | Grundstücksrevisionen werden nicht aufbewahrt, ein alter Stand ließe sich nicht nachrechnen; ein veralteter Regelstand wäre zudem irreführend | aktuell mit Prüfstempel (3.9, E-HM-7) |
| 4 | Verletzte PLU-Regel als `block` (P 8.3) | eine falsch gelesene Regel (Simulation, D11) sperrt echte Kunden von der Übergabe aus | Ergebnisart `deviation` (3.7) |
| 5 | Wandfläche „Mittellinie × Fassadenhöhe“ (P 7) auch für Satteldach | Giebelflächen fehlen, Wandpreis zu niedrig | Fassadenfläche je Segment, Formel als Sonderfall (5.5) |
| 6 | Positionen und Summe beim Kunden je für sich gerundet | Zeilen ergeben nicht die Summe (B-65) | nur Summe und Aufpreise beim Kunden (3.8) |
| 7 | Web-Image baut mit Kontext `frontend/` | `packages/domain` fehlt im Build | Build-Kontext auf die Wurzel in HM0 |
| 8 | Dachform als Slot (`RoofType.kind`, P 5.2) | Wechsel Flach ↔ Satteldach würde Höhe und Geometrie tauschen, die das Template nicht trägt | Dachform aus dem Template (5.4); überholt: das Dach wird aus der Bezugskontur erzeugt, das Template trägt nur Auflagerhöhe und Überstände, die Form ist frei wählbar (E-HM-10) |
| 9 | Grundstücksszenarien P 19.6/19.7 im TS-Kern getestet | doppelte PLU-Prüfung nur für Tests | als Python-Tests in HM4 (6) |
| 10 | Raumtypen gehören zum Katalog, der Import kennt aber keinen Katalog | Template ohne gültige `roomTypeId` | Zuordnung im Katalog, Import nimmt die letzte veröffentlichte Version, Lücken über die Kompatibilitätsprüfung (3.6) |
| 11 | IfcOpenShell (C++) im Worker-Prozess | Absturz bei fehlerhafter Datei beendet den Worker und andere Jobs | Kindprozess mit Grenzen (3.6, E-HM-19) |
| 12 | Gleichheit Server- und Browserpreis (P 20.3) für alle Browser zugesagt | Unterschiede in `Math.sin`/`cos` je JavaScript-Engine | ganzzahlige Geometrie, Prüfung in Chromium, Server maßgeblich (9) |
| 13 | Vertragsmodelle „über `openapi.json`“ ab HM1, aber FastAPI nimmt nur Modelle auf, die eine Route verwendet; Routen gibt es erst ab HM3 | keine TS-Typen in HM1 | Modelle ausdrücklich in `components.schemas` (3.4) |
| 14 | HM1 nur mit Flachdach und einem Geschoss, die Risikotabelle verlangt aber ein mehrgeschossiges Modell von Anfang an | Umbau des Vertrags in HM5 | Datenmodell in HM1 mit Geschossen und Dachform, Geometrie zunächst nur Flachdach (6) |
| 15 | Liste der Kategorien ohne Raum auf alle Quellen angewandt | Zonenname „SDP“ (beide Probedateien) hätte jede Raumzone verworfen | Liste nur für die Quellen „Typ“ und „Category“ (3.6 Nr. 3) |
| 16 | Raumumriss aus `IfcSpace` (P 12.3) | nicht aktualisierte Zonen (Probedatei 2) ergeben falsche Flächen, Räume mit Lücken oder in Wänden | Umriss aus den Wänden, Zone nur Typ; Zuordnung über „mehr als die Hälfte“ (3.6 Nr. 4) |
| 17 | Abweichung je Zone gegen ihren Raum gemessen | offene Wohnküche mit zwei Zonen in einem Raum würde immer warnen | Zonen eines Raums zusammen gegen den Raum (3.6 Nr. 4) |
| 18 | Bezug „Innenkante der tragenden Schicht“ (P 6.1) | Profile mit Innendämmung würden die Räume verkleinern, die Invariante P 2.1 Nr. 1 (Innenkante unverändert) gälte nur noch für die tragende Schicht, nicht für die Räume | innerste Profilschicht (E-HM-24) |
| 19 | Dach aus dem IFC-Körper übernehmen | Überstand und Traufe folgen nicht der Fassade, wenn das Profil sie verschiebt | Dach im Kern aus Parametern, IFC nur Vergleich (3.6) |
| 20 | Jedes `IfcBuildingStorey` als Geschoss | Dachebene „R+1“ (Probedatei 2) als Geschoss gezählt, PLU-Prüfung von Geschosszahl und Höhe falsch | Geschoss nur mit Wänden oder Räumen (3.6) |
| 21 | Dachform-Begriffe des heutigen Hausmodells (`gable`, `hip`, `flat`, `complex`, H1) | Pult- und Mansarddach, die die PLU-Regeln kennen (`mono_pitch`, `mansard`), wären nicht prüfbar | Begriffe der G2-Regeln in der Hausbeschreibung (Ergänzung 11) |
| 22 | Eine Neigung je Haus in der Hausbeschreibung | Mansarde und Ortgang mit anderer Neigung nicht abbildbar, PLU-Neigung falsch geprüft | Neigungen je Dachfläche; welche maßgeblich ist, legt die Auslegung fest (Ergänzung 11) |
| 23 | Freie Formwahl ohne Regel, welche Kanten Giebel sind | Satteldach auf einem Typ mit Walmdach im IFC wäre unbestimmt | Firstrichtung als Parameter mit Voreinstellung, drehbar (Ergänzung 4) |
| 24 | Freie Formwahl auch dort, wo die Form nicht zum Grundriss passt | Abbruch oder unsinnige Dächer beim Kunden | nicht erzeugbare Formen gesperrt mit Begründung (Ergänzung 4) |
| 25 | Feste Neigung je Form | eine PLU-Spanne (z. B. 35–45°) wäre mit der Voreinstellung oft verfehlt, die freie Formwahl liefe ins Leere | Neigung einstellbar innerhalb der Katalogspanne (Ergänzung 4) |
| 26 | Clipper2-Port nur an gültigen Eingaben verglichen (HM0) | `clipper2-ts` hängt bei einem Rücklauf; eine einzige Anfrage hätte `engine` blockiert | Polygonprüfung vor jedem Aufruf, Ablehnung mit 422 (E-HM-27) |
| 27 | Überstand über das Skelett der Traufkontur (Spike HM0) | stimmt nur bei gleicher Neigung und gleichem Überstand an allen Kanten | Flächen über die Bezugskontur hinaus als Ebenen verlängern (Kapitel 10) |
| 28 | Giebel an jeder Kante wählbar | neben einer einspringenden Ecke wird der Giebel eine senkrechte Wand ins Hausinnere | Giebel nur an Flügelenden, sonst Form gesperrt (Kapitel 10) |
| 29 | Höhen des Demohauses aus P 19.1 übernommen (HM1) | lichte Höhe 2,70 m, Bodenplatte 0,20 m und Fassade 3,20 m lassen 0,30 m für Dachdecke und Attika; die Attika muss den Aufbau (0,16 bzw. 0,28 m) um 0,10 m überragen, bräuchte also 0,26 bzw. 0,38 m. Testdaten so nicht bildbar | Höhenkette E-HM-35: lichte Höhe 2,50 m, Dachdecke 0,10 m, Attika 0,40 m; Fassadenhöhe und alle Erwartungswerte bleiben |
| 30 | Listen in Ausdrücken beliebig verschachtelt (P 8.4) | generierter TypeScript-Typ verweist über Listen auf sich selbst (TS2502), `contract.gen.ts` übersetzt nicht | Listen enthalten nur Werte (E-HM-34) |
| 31 | Kantenlängen mit `Math.hypot` | ECMAScript legt die Genauigkeit von `hypot` nicht fest, `sqrt` ist genau gerundet; Browser- und Serverpreis könnten abweichen | `Math.sqrt` in Kern und Prüfung |
| 32 | Gleichstand der Raumüberschreibung über alle angrenzenden Räume (P 8.2 wörtlich) | „breite Tür im Schlafzimmer“ greift an der Schlafzimmertür nie, weil der Flur dieselbe Priorität hat | nur Räume mit Überschreibung zählen (E-HM-32) |
| 33 | Kennung des Haustyps mit Bindestrichen (HM3) | `demo_house` aus Testdaten und Katalog ließ sich nicht hochladen; unter einer anderen Kennung fehlt der Grundpreis (`price_entry_missing`) | Muster der H1-Haustypen (E-HM-42) |
| 34 | Befundcodes frei im Code gebildet (`f"{code}_ambiguous"`, HM3) | ein neuer Code bliebe ohne Text, die Oberfläche zeigte nur den Code | feste Liste mit Test über alle Meldestellen (E-HM-46) |
| 35 | Befunde der Kompatibilitätsprüfung als Code in der Oberfläche (HM3) | widerspricht E-HM-33; das Büro liest `price_entry_missing` statt eines Satzes, und ein neuer Code des Kerns fiele niemandem auf | typisierte Codeliste im Kern, Texte in FR und DE mit Test (E-HM-47) |

Nachgerechnet: alle Erwartungswerte aus P 19.7 und 20.1 (Außenmaße, Umfänge, Öffnungs- und Schichtflächen, Laibungen, Auflager, Netto 429.328,51 €, Aufpreise, Dachfläche, Überbauung, Abstände, U-Werte). Sie stimmen; nicht nachgerechnet war die Höhenkette aus P 19.1 (Nr. 29). P 19.6 nennt 55 % Überbauung, P 20.1 prüft mit 52 %; beide gehören in die Testdaten.

### 11.2 Geprüfte Alternativen

| Alternative | Besser, wenn … |
|---|---|
| Alles in Python, Vorschau über den Server (Bewertung 1b) | Live-2D/3D bei jeder Änderung verzichtbar wäre |
| PLU-Prüfung nach TypeScript portieren (P 10.2 wörtlich) | Prüfungen ohne Server laufen müssen (offline) oder beim Ziehen mehr als die Fläche zulässiger Ursprünge gebraucht wird |
| V8 eingebettet in Python statt Dienst `engine` | ein weiterer Container stört; dafür native Abhängigkeit im Backend-Image |
| Zod als Quelle des Vertrags | Python den Vertrag nur durchreichte; es schreibt aber Templates und Katalogversionen |
| Eigene Version für den Preiskatalog (P 5.2) | Preise deutlich häufiger wechseln als Bauteile |
| Variantengruppen im IFC (Spez. 5.4.2) statt parametrischer Profile | Varianten sich nicht als Schichtwechsel ausdrücken lassen (andere Grundrisse, Anbauten) |
| 3D-Bilder auf dem Server rendern | das Büro fotorealistische Darstellungen im Dossier verlangt |
| web-ifc in Node statt IfcOpenShell | der Spike zeigt, dass IfcOpenShell die Archicad-Dateien schlechter liest |
| Prompt-Phasen ohne HM5 bis zur Ablösung | Flachdach und ein Geschoss genügen; sonst Rückschritt gegenüber den heutigen Typen (3a) |
| Zonenkategorie nur aus einer Quelle (`IfcSpaceType`) | nur ein Archicad-Übersetzer im Einsatz bliebe; die Reihenfolge der Quellen kostet wenig und deckt IFC2x3 und andere Programme ab |
| Unscharfer Abgleich (Ähnlichkeit) statt Aliasse | Schreibweisen unvorhersehbar wären; Fehlzuordnungen blieben aber still, Aliasse plus Entwurf machen jede Zuordnung sichtbar |
| Raum aus der Zone, Wände nur zur Prüfung | Zonen in Archicad verlässlich aktualisiert würden; Probedatei 2 zeigt das Gegenteil |
| Dach aus dem IFC übernehmen | Außenwände kein Platzhalter wären; Formen außerhalb der Ergänzung 11 (Gauben, versetzte Pultdächer) bräuchten es dennoch (dann Dachkörper verschieben statt erzeugen) |
| Dachformen je Haustyp vom Büro freigeben | das Büro Formen ausschließen will, die gestalterisch nicht zum Typ passen; lässt sich später als Katalogregel nachrüsten, ohne das Modell zu ändern |
| Eigene Formeln je Dachform statt Skelett | nur Rechteckgrundrisse vorkämen; L-, T- und U-Grundrisse mit Kehlen bräuchten je Form und Grundriss eigene Sonderfälle |
