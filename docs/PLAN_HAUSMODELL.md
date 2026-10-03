# Hausmodell – Plan für die Umsetzung

> **Entwurf vom 03.10.2026.** Grundlage ist der Prompt des Nutzers „Parametrischer Hauskonfigurator mit IFC-Import (v3.1)“, abgelegt als [HAUSKONFIGURATOR_PROMPT_v3.1.md](HAUSKONFIGURATOR_PROMPT_v3.1.md) (im Folgenden „Prompt“, Kapitel als „P 8.2“). Was der Prompt festlegt, gilt, soweit dieser Plan nicht ausdrücklich abweicht (Kapitel 4) oder ergänzt (Kapitel 5); der Plan wiederholt ihn nicht.
>
> **Entscheidungen des Nutzers vom 03.10.2026** auf die Bewertung des Prompts: **1a** Rechenkern in TypeScript im Browser, Rechendienst in Node neben FastAPI, IFC-Import in Python · **2a** L1 bleibt: dem Kunden gerundet mit „ca.“, exakte Beträge nur im Dossier · **3a** Satteldach und R+1 vor der Ablösung; der heutige Konfigurator läuft bis dahin parallel. Die übrigen Punkte der Bewertung (Nr. 3, 4, 6–10) gelten nach Empfehlung. Die Festlegungen in Kapitel 7 tragen je eine Empfehlung und gelten mit dem Auftrag zur Umsetzung als entschieden; sie gehen dann nach DECISIONS (Präfix `E-HM`).

## 1. Ziel und Abgrenzung

**Ziel:** Das Haus im Konfigurator wird ein parametrisches Gebäudemodell. Haustypen kommen als IFC aus dem Archicad des Büros, der Kunde wählt Wandaufbau, Fenster, Dach und später mehr. Geometrie, Mengen, Preis und Prüfungen leiten sich daraus ab, live in 2D und 3D. Grundstück, Regeln und Baurahmen (G1–G3) liefern weiter den Rahmen.

**Ersetzt:** H1 (Katalog aus XLSX und DXF, Spannenpreise je Typ, Linie, Option), den Hausteil von H2/H3 (Typ, Linie, Optionen, Kosten, Energiebefund) und die Darstellung des Hauses in V.

**Bleibt:** G1, G2, G3, A, die Analyse, Anmeldung, Jobs. Die Prüfung des Hauses auf dem Grundstück (`configuration/domain`: Lage, Fläche zulässiger Ursprünge, Schnellstellungen, Typzulässigkeit, PLU-Prüfungen) bleibt in Python und bekommt das Haus künftig vom Rechenkern (3.1).

**Nicht in diesem Plan:** Deutschland als Markt (nur das Feld `market`), Walmdach und Dachgeschoss mit Schrägen (`R+1+C`), konfiguriertes IFC für den Rückweg nach Archicad (P 17.1 „später“, X4), Innenausbau und Haustechnik als Slots (Modell trägt sie, P 22), Kundenkonten.

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
- **Python** behält alles, was vom Grundstück abhängt: G1–G3, die Auslegung der Regeln und die Prüfung des Hauses auf dem Grundstück. Der Kern übergibt dafür eine **Hausbeschreibung** (`HouseFacts`), die `HouseType` ersetzt: Fassadenumriss (Außenkante der äußersten Schicht, alle oberirdischen Geschosse), Projektionsumriss (mit Dachüberstand), Geschosse, Dachform, Neigung, Firstrichtung, Traufe, First oder Attika, Erdgeschoss über Gelände, Fassadenrollen, Eingang, Garagentor, Materialklassen von Fassade und Dach.
- **Im Browser** misst der Kern Abstände und Überbauung zur Vorschau; ob eine Lage zulässig ist, sagt die Fläche zulässiger Ursprünge, die der Server zur gewählten Hausbeschreibung liefert (wie heute in H2). PLU-Ergebnisse kommen nach einem Serveraufruf; ändert sich die Hausbeschreibung (z. B. Ziegelfassade), holt der Browser Fläche und Prüfung neu.

### 3.2 Rechenkern `packages/domain`

- pnpm-Workspace im Wurzelverzeichnis: `frontend`, `packages/domain`, `engine`. Paketname `@emprise/domain`, Bezeichner englisch, ohne Abhängigkeit zu React, DOM, Three.js oder Datenbank (P 2, Prinzip 4).
- Polygon-Offset und boolesche Operationen mit einem Clipper2-Port, ganzzahlig in 0,1 mm (P 4); welcher Port, entscheidet der Spike in HM0.
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
- Ergebnis: Template-Entwurf und Importbericht (P 12.4). Im Entwurf weist das Büro Raumtypen zu, die die Zuordnung nicht erkennt, außerdem Fassadenrollen, Eingang und Garagentor (wie heute in H1) und, falls es nicht im IFC steht, die Höhe des Erdgeschosses über Gelände.
- Die Zuordnung Archicad-Zonenkategorie → `roomTypeId` steht bei den Raumtypen im Katalog; der Import nimmt die letzte veröffentlichte Katalogversion des Markts. Lücken fallen bei der Kompatibilitätsprüfung auf (P 2.1 Nr. 5).
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
| P 6.4, 21: nur Flachdach, ein Geschoss | Satteldach und R+1 vor der Ablösung | Entscheidung 3a |
| P 1: Märkte FR, dann DE | Feld `market`, nur FR | Kapitel 1 |

## 5. Ergänzungen zum Prompt

1. **Höhenbezug:** Der Prompt misst ab Unterkante Bodenplatte, der PLU ab dem natürlichen Gelände. Das Template trägt die Höhe des Erdgeschosses über Gelände (IFC-Eigenschaft `Emprise.GroundFloorOffset` am Gebäude oder Eingabe im Entwurf, Standard 0,20 m, Spez. 5.4.3); das Gelände liefert G1, die Höhenprüfung bleibt in Python (E-HM-11).
2. **Zwei Umrisse:** Fassadenumriss (Außenkante der äußersten Schicht, P 6.2) und Projektionsumriss mit Dachüberstand. Welcher für eine Regel gilt, entscheidet die Python-Prüfung wie heute (E-HM-12).
3. **Fassadenrollen, Eingang, Garagentor:** werden im Entwurf zugewiesen und gehen in die Hausbeschreibung (Spez. 5.4.4). Sie richten Schnellstellungen, Terrasse und Zufahrt aus (E-HM-13).
4. **Dachform:** kommt aus dem Template; der Slot „Dach“ wählt nur den Aufbau (Deckung, Gründach). `RoofType.kind` muss zur Dachform des Templates passen (`availableWhen`) (E-HM-10).
5. **Satteldach und R+1 (HM5):** Hülle je Geschoss, Fassadenumriss als Vereinigung der Geschosse, Dach aus Traufe, Neigung, Firstrichtung und Überstand, Giebelwände. Mengen über die Fassadenfläche je Segment; die Formel „Mittellinie × Fassadenhöhe“ (P 7) ist ihr Sonderfall bei konstanter Höhe, die Tests aus P 20 bleiben gültig. Dachfläche geneigt mit Überstand.
6. **Ausstattungslinie:** wird eine Voreinstellung, die mehrere Slots auf einmal setzt, auf ausdrückliche Wahl des Kunden. Es gibt keinen eigenen Linienaufpreis; der Preis ergibt sich aus den gesetzten Werten (E-HM-14).
7. **Nebenbauten:** Terrasse und Carport werden Slots mit Ziel `site`. Ihre Maße, Preise und Mengen rechnet der Kern; ihre Lage auf dem Grundstück, die Zufahrt und die Prüfungen (`annex`, `unsealed_min`, `parking`) bleiben in Python (`outbuildings.py`) (E-HM-14).
8. **Materialklassen:** Wandprofile und Dachtypen tragen eine Klasse für die PLU-Prüfung von Fassade und Dach (heute `package.regulatory`).
9. **Typzulässigkeit:** geprüft mit den Standardwerten des Templates (Spez. 5.4.6); eine Wahl, die die Lage unzulässig macht, wird `deviation` mit Vorschlag.

## 6. Phasen

Jede Phase wird einzeln beauftragt („weiter mit HM1“), endet mit grünen Prüfungen, einem Bericht und den Festlegungen in DECISIONS. Umfang grob: S klein, M mittel, L groß.

| Phase | Inhalt | Abnahme | Braucht vom Büro | Umfang |
|---|---|---|---|---|
| **HM0** Einrichtung und Spike | pnpm-Workspace im Wurzelverzeichnis, Build-Kontext des Web-Images auf die Wurzel, CI-Job für `packages/domain`. `engine` mit `/health` und einem `/evaluate`-Gerüst in Compose (lokal, E2E, Unraid) und Trivy. Spike IFC: IfcOpenShell-Wheel für Python 3.12 im Backend-Image (Größe, Kindprozess), eine echte Archicad-Datei auslesen nach P 12.3. Spike Clipper2: Ports vergleichen (Offset, Boolesch, Minkowski, 0,1 mm, Größe im Bundle). Entwurf `docs/IFC_IMPORTVERTRAG.md` | CI grün mit den neuen Jobs, Spike-Ergebnis in Kapitel 10, Bibliotheken entschieden | eine IFC aus Archicad (beliebiges Haus) | M |
| **HM1** Rechenkern | Vertrag in Pydantic, Typen generiert; das Datenmodell trägt schon Geschosse und Dachform. Resolver mit `ResolutionNote`, `evaluateCandidates`, Ausdrücke (P 8.4), Geometrie (zunächst Flachdach, ein Geschoss), Mengen, Preis, Katalogregeln, U-Wert, Kompatibilitätsprüfung, Status. Testdaten und Demo-Seed getrennt; Node-Skript für die Szenarien P 19.7 | Tests P 20.1, 20.1.1, 20.2 grün; Ausgabe des Skripts gleich P 19.7 | – | L |
| **HM2** Oberfläche | 2D, 3D, Konfigurations- und Preisleiste, Hinweise, Einzelkonfiguration, FR/DE, Web Worker; als Vorschau im Büro mit Demo-Seed, noch ohne Grundstück. Referenzgeräte festlegen (DECISIONS), Zielwerte P 4.1 messen | Szenarien P 19.7 in 2D, 3D und Preis sichtbar; Kamera bleibt stehen; Messwerte in Kapitel 10 | – | L |
| **HM3** IFC-Import | Upload, Job im Kindprozess, Importbericht mit Vorschau, Entwurf (Raumtypen, Rollen, Höhe über Gelände), Veröffentlichung mit Kompatibilitätsprüfung über `engine` und Freigabe; Tabellen für Template und Katalogversion; Demo-Katalog per CLI | Referenz-IFC → Template gleich den Testdaten (1 mm, P 20.3); fehlerhafte Dateien → erwartete Meldungen | Referenz-IFC des Demohauses nach Importvertrag; Zonenkategorien des Büros | M–L |
| **HM4** Kundenweg | `house_configuration`, API für Kunde und Büro, Speichern über `engine` mit Snapshot. Hausbeschreibung → `configuration/domain` (Fläche, Lage, Schnellstellungen, Zulässigkeit, PLU-Prüfung); Ergebnisarten 3.7; Versionen 3.9; Seite `/haus` hinter `house_model`. Grundstücksszenarien P 19.6/19.7 als Python-Tests | Konfiguration lädt nach Katalogänderung unverändert; Server- gleich Browserpreis (Chromium); Playwright Kunde bis Speichern auf AD 65 | – | M–L |
| **HM5** Satteldach, R+1, Linien, Nebenbauten | Ergänzungen 5.3–5.8 in Kern, Import und Oberfläche | ein echter Typ des Büros (R+1, Satteldach) aus IFC, auf AD 65 konfiguriert, Prüfungen wie im heutigen Konfigurator | echte Typen als IFC | L |
| **HM6** Übergabe, Katalogpflege, Ablösung | Snapshot Schema 3, Übergabe mit 3.7, Dossier und JSON (3.11); Pflege der Katalogversion (Arbeitsmappe mit einem Blatt je Art importieren, prüfen, veröffentlichen), Kompatibilitätsfreigabe, Übernahme neuer Versionen in gespeicherte Konfigurationen; Umschalten und Entfernen nach 3.12 | Ende-zu-Ende P 20.3 mit Playwright bis zur Übergabe; Büro sieht Fassung und Dossier | echte Katalogwerte (Profile, Fenster, Dächer, Preise) | M–L |

Kosten: keine Aufrufe des Sprachmodells (der Import kommt ohne KI aus, P 12.1). Recht: keine neue Frage, L1 bleibt (2a). Betrieb: ein Container mehr, ein größeres Backend-Image (IfcOpenShell).

## 7. Festlegungen mit Empfehlung

| Nr. | Festlegung | Empfehlung und Grund |
|---|---|---|
| E-HM-1 | Technik | **Entschieden 03.10.2026 (Nutzer, 1a):** TS-Kern im Browser und in `engine`, FastAPI bleibt, IFC in Python |
| E-HM-2 | Preisanzeige | **Entschieden 03.10.2026 (Nutzer, 2a):** wie 3.8 |
| E-HM-3 | Umfang vor der Ablösung | **Entschieden 03.10.2026 (Nutzer, 3a):** Satteldach und R+1 vorher, Parallelbetrieb (3.12) |
| E-HM-4 | Grenze TS ↔ Python | Hausbeschreibung als Schnittstelle, PLU-Prüfung bleibt in Python (3.1) |
| E-HM-5 | Quelle der Typen | Pydantic, generiert nach TS (3.4) |
| E-HM-6 | Ergebnisarten und Status | wie 3.7; HP01 und HK08 aufgehoben, D12 und D14 bleiben |
| E-HM-7 | Versionen | Template und Katalog festgehalten, Grundstück und Regeln aktuell mit Prüfstempel (3.9) |
| E-HM-8 | Katalogversion | ein Dokument je Markt mit Preisen; eigene Preisversion erst, wenn Preise häufiger wechseln als Bauteile |
| E-HM-9 | Template-Entwurf | Status der Templateversion statt eigener Tabelle |
| E-HM-10 | Dachform | aus dem Template, Slot nur für den Aufbau |
| E-HM-11 | Höhenbezug | Erdgeschoss über Gelände im Template, Standard 0,20 m |
| E-HM-12 | Umrisse | Fassade und Projektion wie heute |
| E-HM-13 | Rollen, Eingang, Garagentor | im Entwurf zugewiesen, optional aus IFC-Eigenschaften |
| E-HM-14 | Linie, Nebenbauten | Linie als Voreinstellung, Nebenbauten als Slots `site` mit Lage und Prüfung in Python |
| E-HM-15 | Kundenkonten | keine |
| E-HM-16 | Markt | Feld `market`, nur FR, eine Region |
| E-HM-17 | Dokumente | Festlegungen in DECISIONS; `docs/IFC_IMPORTVERTRAG.md` als einzige Ausnahme zu ADR-08 (Leser ist das Büro, nicht der Code) |
| E-HM-18 | Bilder im Dossier | SVG aus dem Kern, kein Rendering auf dem Server |
| E-HM-19 | IFC sicher verarbeiten | Kindprozess mit Grenzen, Datei nur über die API, Audit |
| E-HM-20 | Einheitspreise im Browser | annehmen: der Konfigurator zeigt Richtpreise ohnehin öffentlich; sonst käme jeder Preis erst vom Server (P 4.1 verfehlt) |
| E-HM-21 | Fahne | neue Fahne `house_model`, entfällt mit der Ablösung |
| E-HM-22 | Alte Daten bei der Ablösung | keine Übernahme (nur `demo_*`-Typen und Testvorgänge); vorher auf Unraid prüfen, ob echte Vorgänge bestehen |

## 8. Auswirkungen auf Dokumente und Betrieb

Bei der Umsetzung, je Phase: ARCHITECTURE (Dienst `engine`, `packages/domain`, Modul `app/house`, Abhängigkeiten), DOMAIN (Glossar: Template, Slot, Wert, Profil, Schicht; Fachregeln 4.5 neu), DECISIONS (`E-HM`), README (Workspace, Befehle, Stolperstellen), `deploy/unraid/README.md` (Container `engine`, Image-Größe). Nach HM6 kommen dieser Plan und der Prompt ins Archiv.

## 9. Risiken

| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| Archicad-Export liefert die Semantik nicht (`IsExternal`, Raumbegrenzungen, Schichten) | Import unvollständig | Spike HM0 mit echter Datei vor HM1; Rückfälle aus P 12.3; Importvertrag |
| Satteldach und R+1 aufwendiger als das Flachdach | HM5 groß, Ablösung später | Modell von Anfang an mehrgeschossig und mit Dachform (HM1); Walmdach erst danach |
| Zwei Laufzeiten (Python, Node) | mehr Betrieb und Abhängigkeiten | `engine` ohne Zustand und ohne Port nach außen; Trivy; Gesundheitsprüfung |
| Browser rechnen trigonometrische Funktionen nicht gleich | Browserpreis weicht im Cent ab | Geometrie ganzzahlig (0,1 mm), Beträge mit einer Rundungsregel; Server maßgeblich (L5); Gleichheit in Chromium geprüft |
| 3D auf Mittelklasse-Telefonen zu langsam | Ziele P 4.1 verfehlt | messen in HM2, 3D als eigener Chunk, Neuaufbau nur geänderter Elemente |
| Katalogdaten (Profile, Preise je m²) fehlen | kein echter Betrieb | Demo-Seed bis HM6; Katalogpflege per Arbeitsmappe wie heute |

## 10. Ergebnisse von Spike und Messungen

Wird in HM0 und HM2 ausgefüllt: IFC-Datei, gefundene Eigenschaften und Beziehungen je Zeile von P 12.3, Abweichungen, gewählter Clipper2-Port mit Messwerten, Image-Größen; Messwerte zu P 4.1 auf den Referenzgeräten.

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
| 8 | Dachform als Slot (`RoofType.kind`, P 5.2) | Wechsel Flach ↔ Satteldach würde Höhe und Geometrie tauschen, die das Template nicht trägt | Dachform aus dem Template (5.4) |
| 9 | Grundstücksszenarien P 19.6/19.7 im TS-Kern getestet | doppelte PLU-Prüfung nur für Tests | als Python-Tests in HM4 (6) |
| 10 | Raumtypen gehören zum Katalog, der Import kennt aber keinen Katalog | Template ohne gültige `roomTypeId` | Zuordnung im Katalog, Import nimmt die letzte veröffentlichte Version, Lücken über die Kompatibilitätsprüfung (3.6) |
| 11 | IfcOpenShell (C++) im Worker-Prozess | Absturz bei fehlerhafter Datei beendet den Worker und andere Jobs | Kindprozess mit Grenzen (3.6, E-HM-19) |
| 12 | Gleichheit Server- und Browserpreis (P 20.3) für alle Browser zugesagt | Unterschiede in `Math.sin`/`cos` je JavaScript-Engine | ganzzahlige Geometrie, Prüfung in Chromium, Server maßgeblich (9) |
| 13 | Vertragsmodelle „über `openapi.json`“ ab HM1, aber FastAPI nimmt nur Modelle auf, die eine Route verwendet; Routen gibt es erst ab HM3 | keine TS-Typen in HM1 | Modelle ausdrücklich in `components.schemas` (3.4) |
| 14 | HM1 nur mit Flachdach und einem Geschoss, die Risikotabelle verlangt aber ein mehrgeschossiges Modell von Anfang an | Umbau des Vertrags in HM5 | Datenmodell in HM1 mit Geschossen und Dachform, Geometrie zunächst nur Flachdach (6) |

Nachgerechnet: alle Erwartungswerte aus P 19.7 und 20.1 (Außenmaße, Umfänge, Öffnungs- und Schichtflächen, Laibungen, Auflager, Netto 429.328,51 €, Aufpreise, Dachfläche, Überbauung, Abstände, U-Werte). Sie stimmen. P 19.6 nennt 55 % Überbauung, P 20.1 prüft mit 52 %; beide gehören in die Testdaten.

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
