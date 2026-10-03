# Projekt: Parametrischer Hauskonfigurator mit IFC-Import (v3.1)

## 0. Kontext

Wir entwickeln eine Webanwendung, in der Bauherren ein Haus auf Basis eines vordefinierten Haustyps selbst konfigurieren: Außenwandaufbau, Fenster, Dach und später Innenausbau, Haustechnik usw. Ein Grundriss besteht dabei aus semantischen Räumen/Nutzungsbereichen, physischen Wänden, Öffnungen und der Gebäudehülle. Das geschieht innerhalb der geltenden Bauvorschriften des Grundstücks.

Das Ergebnis ist **kein Kaufabschluss**. Es ist eine Skizze mit Kostenschätzung, die an ein Architekturbüro übergeben wird. Das Büro prüft sie und erstellt ein verbindliches Angebot. Alle Preise in der Anwendung sind deshalb **Richtpreise**.

Märkte: **Frankreich zuerst**, danach Deutschland. Sprache, Bauvorschriften, Mehrwertsteuer und Preiskataloge sind deshalb von Anfang an marktabhängig.

Basisgebäude werden in Archicad modelliert und nach einem kontrollierten Workflow als IFC exportiert. IFC ist ausschließlich ein **Importweg für Templates**. Kunden laden nie IFC.

---

## 1. Arbeitsweise

Dieses Dokument beschreibt das Gesamtsystem. Umgesetzt wird es in **Phasen** (Abschnitt 18).

- Bearbeite immer nur die aktuelle Phase. Beginne jede Phase mit einem kurzen Plan, beende sie mit lauffähigem Code, grünen Tests und einem kurzen Bericht (was umgesetzt, was offen, welche Entscheidungen).
- Falls bereits ein Repository existiert, analysiere es zuerst. Andernfalls lege es gemäß Abschnitt 4 neu an.
- Architekturentscheidungen, die von diesem Dokument abweichen oder es konkretisieren, werden als kurze ADR in `docs/adr/` festgehalten.
- Alle Zahlenwerte in diesem Dokument sind **Beispieldaten**. Sie liegen im Katalog bzw. Seed, nie im Code.
- Wenn eine Anforderung unklar oder widersprüchlich ist: nachfragen bzw. die Annahme im Bericht dokumentieren, nicht stillschweigend entscheiden.

---

## 2. Architekturprinzipien

1. **Template ist unveränderlich.** Ein importiertes und veröffentlichtes Haus-Template (`HouseTemplate` in einer Version) wird nie durch Konfiguration verändert.
2. **Konfiguration ist nur Auswahl.** Eine Konfiguration speichert ausschließlich, welcher Wert in welchem Slot gewählt wurde (Abschnitt 8). Sie enthält keine Geometrie, keine Mengen und keine Preise.
3. **Alles Weitere wird abgeleitet.** Geometrie, Mengen, Preis und Regelprüfung sind reine, deterministische Funktionen von `(TemplateVersion, CatalogVersion, Configuration, Site, SiteRuleSetVersion)`.
4. **Domänenkern ohne Framework.** Die gesamte Logik liegt in einem eigenen TypeScript-Paket ohne Abhängigkeit zu React, DOM, Three.js oder Datenbank.
5. **Gleicher Code in Client und Server.** Der Client rechnet live für die Vorschau. Beim Speichern rechnet der Server mit demselben Paket erneut. Nur das serverseitige Ergebnis wird gespeichert.
6. **Keine Produkte im Code.** Kein `if (wall === "brick")`. Ein neuer Wandaufbau, Fenstertyp oder Dachtyp entsteht durch einen neuen Katalogdatensatz.
7. **Klare Zuständigkeiten:**

| Bereich | Beantwortet |
|---|---|
| Template (aus IFC) | Wo befindet sich was? |
| Katalog | Welche Varianten gibt es, mit welchen Eigenschaften und Preisen? |
| Resolver | Welche Variante gilt konkret für welches Bauteil? |
| Geometry Engine | Wie sieht das Gebäude mit diesen Varianten aus? |
| Quantity Takeoff | Wie viel von was steckt im Gebäude? |
| Pricing Engine | Was kostet das? |
| Rule Engine | Ist die Kombination zulässig – technisch und baurechtlich? |
| UI | Wie wählt der Kunde aus und versteht die Auswirkungen? |

Keiner dieser Bereiche greift auf die Interna eines anderen zu. Insbesondere: 2D, 3D und Preis haben **keine eigene Geometrielogik**, und die Pricing Engine berechnet **keine Mengen**.

### 2.1 Domain-Invarianten

Diese Invarianten gelten unabhängig von UI oder Persistenz und müssen durch Tests abgesichert sein:

1. Die Innenkante der Referenzhülle bleibt bei einer Änderung des Außenwandprofils unverändert.
2. Jedes `Opening` gehört genau zu einem Host.
3. Jedes `Opening` liegt vollständig innerhalb seines Hosts und darf keine andere Öffnung überlappen.
4. Für jedes aufgelöste Slot-Ziel existiert genau ein effektiver Wert: Element-Override → Raum-Override → globaler Wert → Template-Default, wobei jede Stufe nur greift, wenn ihr Wert für das Element **verfügbar** ist (`availableWhen`). Jede übersprungene Stufe erzeugt eine `ResolutionNote`.
5. Eine Kombination aus Template- und Katalogversion ist nur nutzbar, wenn ein freigegebener `CatalogCompatibility`-Eintrag existiert. Freigegeben wird nur, wenn alle Defaults und Slot-Ziele des Templates im Katalog auflösbar und verfügbar sind und jedes bepreiste Bauteil genau eine Preisquelle hat.
6. Eine gespeicherte Konfiguration verändert niemals Template-, Katalog- oder SiteRuleSet-Versionen.
7. Mengen, Preise, Geometrie und Regeln sind bei identischen Eingaben deterministisch.
8. Abgeleitete Ergebnisse sind nie die fachliche Quelle der Wahrheit; Quelle der Wahrheit sind nur versionierte Eingaben.
9. Regelprüfung darf keine Benutzerentscheidung stillschweigend verändern. Korrekturvorschläge sind Ergebnisse der Rule Engine, keine impliziten Mutationen.
10. Farben, Schraffuren und sonstige Darstellungsmerkmale sind reine Präsentationsdaten und werden niemals zur geometrischen oder semantischen Erkennung verwendet.
11. Jeder Betrag im `PriceResult` stammt aus genau einem `PriceEntry`. Bauteildefinitionen und `PricingRule`s enthalten keine Beträge.
12. Ein inkrementell (memoisiert) berechnetes Ergebnis ist identisch mit einer vollständigen Neuberechnung aus denselben Eingaben.

---

## 3. Pipeline

```text
ADMIN-ZEIT (selten, serverseitig)
Archicad → IFC-Export → Importer → Validierung + Importbericht → HouseTemplate vN

KATALOG (versioniert, pro Markt)
Materials · WallProfiles · WindowTypes · DoorTypes · RoofTypes
ConfigSlots · OptionValues · Rules · PricingRules · PriceCatalog

LAUFZEIT (reine Funktionen, Client = Server)
TemplateVersion + CatalogVersion + Configuration + Site + SiteRuleSetVersion
   │
   ▼ Resolver
ResolvedModel        jedes Bauteil hat einen konkreten Typ (Profil, Fenstertyp, Dachtyp …)
                     + ResolutionNote[] (wo und warum ein Wert nicht gegriffen hat)
   │
   ▼ Geometry Engine
DerivedModel         Konturen, Schichten, Öffnungen, Platten, Dach, Platzierung auf dem Grundstück
   │
   ├──▶ Quantity Takeoff ──▶ Pricing Engine ──▶ PriceResult
   ├──▶ Rule Engine ───────────────────────▶ RuleResult[] (mit Erklärungen)
   ├──▶ 2D-Viewer
   └──▶ 3D-Viewer
```

Jede Stufe ist einzeln testbar und wird bei Änderungen nur für betroffene Bauteile neu berechnet (Memoisierung über stabile Element-IDs und Hashes der Eingaben).

Herkunft der Regeln:

- **Technische Regeln und Verfügbarkeiten** liegen als Daten im Katalog (`Rule`, `OptionValue.availableWhen`).
- **Bauvorschriften** sind Adapter-Code pro Rechtsraum (FR, DE) im Domänenkern. Ihre Parameter (z. B. maximaler Überbauungsanteil, Mindestabstand) kommen aus der `SiteRuleSetVersion` des Grundstücks. Die Adapter erzeugen `RuleResult`s im selben Format wie Katalogregeln.

---

## 4. Technologie (Vorgabe)

Abweichungen nur mit ADR.

| Bereich | Wahl |
|---|---|
| Repository | pnpm-Monorepo |
| Domänenkern | `packages/domain` – TypeScript, keine Framework-Abhängigkeiten |
| Polygon-Offset / Boolesche Operationen | Clipper2 (JS/WASM-Port – Verfügbarkeit und Präzision in Phase 0 prüfen). Clipper rechnet mit Ganzzahlen: Koordinaten werden mit 1 Einheit = 0,1 mm skaliert, Rückumrechnung nur an der Schnittstelle des Geometriemoduls. |
| Frontend | `apps/web` – React, TypeScript, Vite |
| State | Zustand (nur Auswahl- und UI-State; abgeleitete Daten über Selektoren/Memoisierung) |
| 2D | SVG |
| 3D | Three.js mit React Three Fiber |
| Backend | `apps/api` – Node.js, TypeScript, tRPC mit Zod-Validierung |
| Datenbank | PostgreSQL mit Drizzle ORM |
| IFC | serverseitig in `packages/ifc-import`; Kandidat web-ifc (ThatOpen) in Node, Fallback IfcOpenShell als Python-Service – Entscheidung nach dem Spike in Phase 0 |
| Tests | Vitest, fast-check (property-based), später Playwright |
| i18n | `LocalizedText = Record<Locale, string>`; mindestens `fr`, `de`; UI-Strings über eine i18n-Bibliothek |

Einheiten intern: **Meter, Quadratmeter, Kubikmeter, Euro netto**. Umrechnung nur an den Rändern (Import, Anzeige).

Geometrische Toleranz: 1 mm. Vergleiche in Tests mit dieser Toleranz.

### 4.1 Performance- und Betriebsziele

Für das Demohaus und typische Konfigurationen gelten zunächst diese Zielwerte:

- Auswahländerung → sichtbares 2D-Update: Ziel < 100 ms
- Auswahländerung → sichtbares 3D-Update: Ziel < 150 ms
- Auswahländerung → Preis-/Regel-Update: Ziel < 200 ms
- Vorschau aller Werte eines Slots (`evaluateCandidates`, Abschnitt 8.2): Ziel < 300 ms
- vollständige serverseitige Neuberechnung des Demohauses: Ziel < 1 s

Referenzumgebung: Produktions-Build, aktueller Mittelklasse-Laptop und Mittelklasse-Smartphone; die konkreten Geräte werden in einer ADR festgelegt.

Diese Werte sind Entwicklungsziele, keine fachlichen Zusagen. Werden sie verfehlt, ist die Ursache zu messen und zu dokumentieren, bevor weitere Optimierungen eingeführt werden.

---

## 5. Domänenmodell

### 5.1 Template (aus IFC, unveränderlich)

```ts
HouseTemplate {
  id; version; name: LocalizedText
  sourceIfc: { fileName; hash; ifcSchema; importedAt }
  levels: Level[]
  envelope: EnvelopeLoop[]        // ein geschlossener Ring pro Geschoss
  interiorWalls: InteriorWall[]
  openings: Opening[]             // Fenster und Türen
  slabs: Slab[]
  roof: RoofPlacement
  rooms: Room[]
  defaults: Record<SlotId, OptionValueId>
  // Keine Preiswerte im Template. Preise liegen ausschließlich im versionierten Katalog.
}

Level { id; name; elevation; clearHeight }

// Referenzgeometrie: Innenkante der tragenden Außenwand, gegen den Uhrzeigersinn
EnvelopeLoop {
  levelId
  innerPolygon: Point2[]
  segments: EnvelopeSegment[]     // abgeleitet aus innerPolygon, stabile IDs
}

EnvelopeSegment {
  id; sourceIfcGlobalId
  start: Point2; end: Point2      // auf der Innenkante
  height
  wallProfileSlot: SlotId         // welcher Slot das Profil bestimmt
}

InteriorWall {
  id; sourceIfcGlobalId; levelId
  axis: [Point2, Point2]
  thickness; height
  profileSlot?
  adjacentRoomIds: RoomId[]       // 0–2 angrenzende Räume
}

Opening {
  id; sourceIfcGlobalId
  kind: "window" | "door"
  hostKind: "envelopeSegment" | "interiorWall"
  hostId
  offsetAlongHost                 // ab Host-Anfang bis Öffnungsmitte; bei Hüllensegmenten entlang
                                  // der Innenkante, bei Innenwänden entlang der Achse
  adjacentRoomIds: RoomId[]       // 1–2 angrenzende Räume
  typeSlot: SlotId
}

Slab { id; sourceIfcGlobalId; levelId; kind: "ground" | "floor" | "roof"; thickness; edgeRule: "followEnvelope" }

RoofPlacement { levelId; parapetHeight; overhang }

Room {
  id; sourceIfcGlobalId; levelId
  name: LocalizedText
  roomTypeId: RoomTypeId          // Referenz auf RoomTypeDefinition, z. B. bedroom, living, kitchen, bathroom, corridor
  polygon: Point2[]
  // Fläche wird aus polygon abgeleitet; keine frei gepflegte room.area-Quelle.
}
```

Jedes aus IFC stammende Element behält seine IFC-`GlobalId`. Interne IDs erzeugt der Importer. Sie müssen bei erneutem Import derselben Datei stabil sein (z. B. aus GlobalId abgeleitet).

### 5.1.1 IFC-Importzustand

```ts
ImportedTemplateDraft {
  id
  sourceIfc: { fileName; hash; ifcSchema; importedAt }
  candidateTemplate: HouseTemplate
  importReportId
  status: "draft" | "reviewed" | "approved" | "rejected"
}
```

Ein Draft darf nicht im Kunden-Konfigurator verwendet werden. Nur veröffentlichte `HouseTemplateVersion` sind kundenwirksam.

### 5.2 Katalog (versioniert, pro Markt)

```ts
Material {
  id; name: LocalizedText
  lambda?: number                 // W/(m·K)
  density?: number                // kg/m³
  carbonPerM3?: number            // kg CO2e/m³ – Vorbereitung RE2020
  renderKey                       // Verweis auf 3D-Material/Textur und 2D-Schraffur
}

WallProfile {
  id; name: LocalizedText
  layerIds: WallLayerId[]         // geordnet von INNEN nach AUSSEN; Schichten sind profilübergreifend wiederverwendbar
  openingAnchorLayerId            // Schicht, an deren Außenkante Fenster/Türen sitzen
  bearing?: {                     // Auflager nicht selbsttragender Außenschichten, z. B. Ziegelvorsatzschale
    supportedLayerIds: WallLayerId[]
    kind: "foundationLedge" | "brackets"
  }
  revealFinish?: { materialId }   // Bekleidung der äußeren Laibung vor der Ankerschicht
}

WallLayer {                       // Katalogobjekt: Material + Dicke, z. B. "Beton 20 cm"
  id; materialId; thickness
  structural: boolean
  thermal: boolean                // false für Schichten außerhalb einer Hinterlüftung
}

WindowType {
  id; name: LocalizedText
  width; height
  headHeight                      // Sturzhöhe über OKFF, Brüstung = headHeight − height
  uw?: number; g?: number
  renderKey
}

DoorType {
  id; name: LocalizedText
  width; height
  renderKey
}

RoofType {
  id; name: LocalizedText
  kind: "flat" | "gable" | "hip" | "shed" | …
  buildUp: RoofLayer[]            // Aufbau über der Dachdecke
  green: boolean
  renderKey
}

RoomTypeDefinition {
  id
  name: LocalizedText
  description?: LocalizedText
  overridePriority: number         // entscheidet bei Bauteilen zwischen zwei Räumen, welcher Raum-Override gilt
  displayKey                       // reine Darstellung; niemals Logikquelle
}

PriceEntry {                       // sagt nur, WAS WIE VIEL kostet
  id
  targetKind: "wallLayer" | "windowType" | "doorType" | "roofType" | "template" | "slotOption" | "service"
  targetId                         // bei "service" ein Leistungsschlüssel, z. B. "bearing.foundationLedge"
  unit: "m" | "m2" | "m3" | "pcs" | "lumpSum" | "percent"
  value: number                    // €/Einheit, € pauschal oder % – je nach unit
}

PriceCatalog {
  id
  version
  market: "FR" | "DE"
  currency: "EUR"
  vatRate
  entries: PriceEntry[]
  validFrom
  status: "draft" | "published"
}
```

Veröffentlichte Katalog- und Templateversionen sind unveränderlich. Änderungen erzeugen eine neue Version. Bauteildefinitionen enthalten keine Marktpreise; alle Preise, auch Fixkosten und Pauschalen, werden über `PriceEntry` und den `PriceCatalog` geführt. Wandschichten werden ausschließlich über `wallLayer` bepreist; Materialien tragen keine Preise. Die Gültigkeit eines Preises ergibt sich allein aus der Katalogversion.

`CatalogCompatibility` wird verwendet, um ausdrücklich freigegebene Kombinationen aus Template- und Katalogversion zu kennzeichnen:

```ts
CatalogCompatibility {
  templateVersionId
  catalogVersionId
  supported: boolean
  reason?: LocalizedText
}
```

Kompatibilitätseinträge entstehen beim Veröffentlichen einer Template- oder Katalogversion: Das System prüft automatisch alle betroffenen Kombinationen gemäß Invariante 5 und legt Einträge mit Prüfergebnis an. Ein Admin gibt sie frei oder lehnt sie mit Begründung ab.

Eine Konfiguration kann nur mit einer freigegebenen Kombination aus Template- und Katalogversion gespeichert werden.

### 5.3 Konfiguration

```ts
Configuration {
  templateVersionId
  catalogVersionId
  siteRuleSetVersionId?
  selections: Record<SlotId, SlotSelection>
  site?: SitePlacement
}

SlotSelection {
  value: SlotValue
  roomOverrides?: Record<RoomId, SlotValue>
  elementOverrides?: Record<ElementId, SlotValue>
}

SlotValue =
  | { type: "option"; optionValueId: OptionValueId }
  | { type: "options"; optionValueIds: OptionValueId[] }
  | { type: "number"; value: number; unit?: string }
  | { type: "dimension"; value: number; unit: "mm" | "cm" | "m" }
  | { type: "quantity"; value: number; unit?: string }
  | { type: "boolean"; value: boolean }
  | { type: "product"; productId: string }
```

Der Status einer Konfiguration wird immer abgeleitet, nie gespeichert oder gesetzt:

| Status | Bedeutung | Speichern | Übergabe an Architekturbüro |
|---|---|---|---|
| `valid` | keine Warnungen, keine Blockaden | ja | ja |
| `validWithWarnings` | mindestens ein `warning` | ja | ja, Warnungen werden im Dossier ausgewiesen |
| `blocked` | mindestens ein `block` | ja | nein |

---

## 6. Geometrieregeln

### 6.1 Außenwände

- Die **Innenkante der tragenden Schicht** (`innerPolygon`) ist die Referenz und bleibt bei jeder Konfiguration identisch. Damit bleiben alle Innenmaße, Räume und Innenwände unverändert.
- Die Außenkontur jeder Schicht entsteht durch **Polygon-Offset nach außen** um die kumulierte Dicke der Schichten. Ecken ergeben sich daraus automatisch korrekt. Keine Einzelwand-Gehrungslogik.
- Für Darstellung und Mengen werden die Schichten danach wieder in Segmente zerlegt (gleiche Segment-IDs wie die Referenz).
- Bei Segmenten mit unterschiedlichen Profilen (später) wird pro Segment versetzt und an den Stößen geschnitten. Für das MVP gilt ein Profil pro Geschoss.

### 6.2 Abhängige Bauteile

Folgende Bauteile folgen der berechneten Kontur und werden mit ihr neu berechnet:

- Bodenplatte und Deckenränder: bis Außenkante der letzten **strukturellen oder thermischen** Schicht (nicht der Bekleidung).
- Attika und Dachrand: ebenso; Fassadenbekleidung läuft bis Oberkante Attika.
- Gebäude-Footprint für Grundstück und Bauvorschriften: Außenkante der **äußersten** Schicht.
- Auflager (`WallProfile.bearing`): Bei `foundationLedge` wird die Gründung bzw. Bodenplatte unter den getragenen Schichten bis zu deren Außenkante verbreitert. Bei `brackets` bleibt die Gründung unverändert. In beiden Fällen entsteht die Menge `bearing.length` (Abschnitt 7).

### 6.3 Öffnungen

- Position entlang der Wand: `offsetAlongHost` auf der Innenkante. Sie ändert sich durch Profilwechsel nicht.
- Lage in der Wandtiefe: das Fenster sitzt an der Außenkante von `openingAnchorLayerId`. Eine dickere Fassade vertieft nur die äußere Laibung. Die Laibungstiefe ist die Summe der Schichtdicken außerhalb der Ankerschicht; ist `revealFinish` gesetzt, wird die Laibung damit bekleidet (3D sichtbar, Menge `reveal.area`).
- Höhe: Die **Sturzhöhe bleibt konstant**, die Brüstung ergibt sich als `headHeight − height`. So bleiben Fensteroberkanten in der Fassade auf einer Linie.
- Öffnungen werden in 3D nicht per CSG ausgeschnitten. Wandsegmente werden um Öffnungen herum in Teilkörper zerlegt (Brüstung, Sturz, Pfeiler).

### 6.4 Dach

- Flachdach: Dachdecke + Aufbau aus `RoofType.buildUp`, umlaufende Attika.
- Gründach: zusätzlicher Aufbau (Substrat, Vegetation) innerhalb der Attika, in 3D sichtbar.
- Gebäudehöhe = Maximum aus Oberkante Attika und Oberkante Dachaufbau. Sie geht in die Bauvorschriften ein.
- Die Attika muss den Dachaufbau um mindestens `parapetMinUpstand` (Katalogparameter, Demo 0,10 m) überragen. Andernfalls erzeugt eine Katalogregel ein `block` mit Erklärung. Im Demohaus erfüllen beide Dachtypen diese Bedingung.
- Das Datenmodell ist so angelegt, dass geneigte Dachformen später als weitere `kind`-Werte mit eigener Geometriefunktion hinzukommen.

### 6.5 Grundriss-Semantik

Ein Grundriss besteht aus drei logisch getrennten Ebenen:

1. **Räume / Nutzungsbereiche** – semantische Flächen wie Schlafzimmer, Wohnen/Küche, Bad oder Erschließung.
2. **Wände / Bauteile** – physische Innenwände und Außenwandsegmente.
3. **Gebäudehülle** – die parametrisch aus dem Außenwandprofil abgeleitete Hülle.

Wie Räume und Wände im 2D-Plan eingefärbt werden, legt das UI-Theme über `RoomTypeDefinition.displayKey` fest (Abschnitt 13). Farben sind nicht Teil der Domänenspezifikation und niemals eine Datenquelle für Erkennung oder Geometrieberechnung.

**Wichtige Invariante:** Ein Wechsel des `WallProfile` verändert ausschließlich die Außenkontur und die davon abhängigen Bauteile. Raum-Polygone, Innenwandachsen und Innenmaße bleiben unverändert.

Räume und Wände werden nicht als dasselbe geometrische Objekt modelliert. Eine Innenwand kann 0–2 Räume begrenzen. Eine Tür kann 1–2 Räume verbinden; ein Außenfenster grenzt typischerweise an einen Raum und die Außenwelt.

### 6.6 Geometrievalidierung

Vor der Erzeugung des finalen `DerivedModel` werden mindestens folgende Invarianten geprüft:

- Öffnungen liegen vollständig innerhalb ihres Hosts.
- Öffnungen überlappen nicht.
- Fenster/Türen überschreiten weder Wandlänge noch Geschosshöhe.
- Raumgrenzen und Innenwände sind geometrisch konsistent.
- Ungültige Geometrie führt zu einem strukturierten Fehler oder einer Warnung, niemals zu stillschweigend falscher Geometrie.

---

## 7. Mengenermittlung (Quantity Takeoff)

Die Mengenermittlung erzeugt aus dem `DerivedModel` eine flache Liste benannter Mengen mit Herkunft:

```ts
Quantity {
  key                       // z. B. "wall.layer.area", "window.count", "roof.area"
  elementIds: ElementId[]   // Herkunft
  refId?                    // z. B. Layer-ID, WindowType-ID
  value; unit: "m" | "m2" | "m3" | "pcs"
}
```

Aufmaßregeln (Katalogparameter, pro Markt änderbar):

| Menge | Regel (Default) |
|---|---|
| Fläche einer Wandschicht | Länge der **Schicht-Mittellinie** × Fassadenhöhe − Öffnungsflächen |
| Öffnungsabzug | alle Öffnungen größer `openingDeductionThreshold` (Default 0 m²) |
| Fassadenhöhe | UK Bodenplatte bis OK Attika (aus Template und Dachtyp abgeleitet) |
| Dachfläche | Fläche innerhalb der Außenkante der letzten thermischen Schicht |
| Footprint | Fläche der Außenkontur der äußersten Schicht |
| Fenster/Türen | Stück pro Typ |
| Auflager (`bearing.length`) | Länge der Mittellinie der getragenen Schichten, ohne Abzüge |
| Laibung (`reveal.area`) | Σ über Öffnungen in Hüllensegmenten: (2 · Höhe + Breite) × Laibungstiefe |

Für eine einfache, rechtwinklige Hülle (Rechteck, L-, T- oder U-Form) gilt: Länge der Mittellinie einer Schicht mit Abstand d von der Innenkante = Innenumfang + 8·d. Für das Rechteck a × b also 2·(a + b) + 8·d.

---

## 8. Optionssystem

### 8.1 Slots und Werte

Konfigurierbar ist alles, was als **Slot** definiert ist. Ein Slot ist eine Entscheidung, ein `OptionValue` eine mögliche Antwort.

```ts
ConfigSlot {
  id
  category; subcategory?; group?          // Navigation, beliebig tief erweiterbar
  name: LocalizedText; description?: LocalizedText
  target: Selector                        // auf welche Elemente der Slot wirkt
  granularity: "global" | "perElement" | "perRoom"
  valueType: "single" | "multi" | "numeric" | "dimension" | "quantity" | "boolean" | "product"
  parentSlotId?                           // abhängige Slots, z. B. Hersteller → Produktlinie → Typ
  effects: {
    geometry: boolean
    quantity: boolean
    pricing: boolean
    rules: boolean
    appearance: boolean
  }
  sortOrder
}

Selector {
  elementKind: "envelopeSegment" | "interiorWall" | "opening" | "roof" | "room" | "building" | "site" | …
  where?: Expr
}

OptionValue {
  id; slotId
  name: LocalizedText; description?: LocalizedText
  assigns: {
    wallProfileId?; windowTypeId?; doorTypeId?; roofTypeId?
    params?: Record<string, number | string | boolean>
  }
  availableWhen?: Expr                     // Verfügbarkeit pro Element bzw. abhängig vom Elternslot;
                                           // ausgewertet vom Resolver (Abschnitt 8.2)
  sortOrder
}
```

Es gibt **keine additiven Effekte** („Schicht hinzufügen“). Ein Wert weist immer einen vollständigen Typ zu. Dadurch ist das Ergebnis unabhängig von der Reihenfolge der Auswahl.

`effects` beschreibt, welche Engines durch eine Slot-Änderung betroffen sein können. Es ist ausschließlich ein Optimierungshinweis für Invalidierung und Memoisierung, keine Geschäftslogik. Korrektheit darf nie davon abhängen: Ein Testmodus berechnet jede Änderung zusätzlich vollständig neu und vergleicht (Invariante 12). Ein Slot, für dessen `effects` im Zweifel nichts feststeht, setzt alle Flags auf `true`.

### 8.2 Auflösung (Resolver)

Es gibt zwei getrennte Konzepte:

- **Verfügbarkeit** (`OptionValue.availableWhen`, Resolver): Wird dieser Wert für dieses Element überhaupt angeboten? Das ist eine Produktentscheidung, z. B. „bodentiefe Fenster gibt es nicht im Bad“.
- **Zulässigkeit** (Rule Engine, Abschnitt 8.3): Ist die entstandene Kombination technisch oder baurechtlich in Ordnung? Z. B. „Grenzabstand unterschritten“.

Der Resolver ermittelt für jedes Element, das ein Slot über `target` erfasst, den effektiven Wert. Priorität:

1. Element-Override
2. Raum-Override
3. globaler Slot-Wert
4. Template-Default

Jede Stufe greift nur, wenn ihr Wert für das Element verfügbar ist. Sonst geht der Resolver zur nächsten Stufe und erzeugt eine `ResolutionNote`:

```ts
ResolutionNote {
  slotId; elementId
  skippedLevel: "element" | "room" | "global"
  skippedValueId
  appliedValueId
  reason: LocalizedText            // z. B. "Bodentiefe Fenster sind im Bad nicht verfügbar."
}
```

Die gespeicherte Auswahl bleibt dabei unverändert. Wählt der Kunde „Bodentief“ global, bleibt dies seine Auswahl; das Bad-Fenster erhält effektiv den Default, und die UI zeigt die Notiz am Element. Ist der Template-Default selbst nicht verfügbar, ist das ein Konfigurationsfehler des Katalogs, der bereits bei der Kompatibilitätsprüfung (Invariante 5) auffällt.

Raum-Overrides bei Bauteilen zwischen zwei Räumen (z. B. Innentür Bad/Flur): Es gilt der Override des Raums mit der höheren `RoomTypeDefinition.overridePriority`. Bei Gleichstand greift kein Raum-Override, und es entsteht eine `ResolutionNote`.

Für die UI stellt der Domänenkern zusätzlich bereit:

```ts
evaluateCandidates(model, configuration, slotId, elementId?) → {
  optionValueId
  available: boolean; unavailableReason?: LocalizedText
  ruleResults: RuleResult[]        // hypothetisch, als wäre der Wert gewählt
  priceDelta: number
}[]
```

Damit zeigt die Optionsliste vor der Auswahl, welche Werte nicht verfügbar, gesperrt oder mit Warnung verbunden sind.

### 8.3 Regeln

```ts
Rule {
  id
  scope: "selection" | "element" | "building" | "site"
  when: Expr                       // true = Regel ist verletzt bzw. Hinweis trifft zu
  outcome: "info" | "warning" | "block"
  message: LocalizedText
  suggestion?: { slotId; optionValueId; elementIds?: ElementId[]; label: LocalizedText }
  source?: RuleSource
}

RuleSource {
  jurisdiction?
  document?
  section?
  reference?
  retrievedAt?
}
```

| `outcome` | Bedeutung | Wirkung auf Konfigurationsstatus |
|---|---|---|
| `info` | Hinweis ohne Prüfbedarf | keine |
| `warning` | zulässig, aber prüfbedürftig | `validWithWarnings` |
| `block` | unzulässig | `blocked` |

- Eine `suggestion` ist bei jedem `outcome` möglich. Sie wird in der UI als Aktion angeboten („Für dieses Fenster Standard wählen“) und erst durch den Kunden ausgeführt.
- Die Engine ändert die Konfiguration nie selbst (Invariante 9).
- Wird eine bestehende Auswahl durch eine spätere Wahl unzulässig, bleibt sie bestehen; die Konfiguration wird `blocked`, und die UI zeigt den Konflikt mit Vorschlag.
- Rechtliche oder technische Regelergebnisse sind Systemhinweise bzw. Prüfergebnisse und kein verbindlicher Nachweis.

### 8.4 Expr-Vertrag

Die Ausdruckssprache wird zunächst auf folgende Operatoren begrenzt:

- Vergleich: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`
- Logik: `and`, `or`, `not`
- Mengen: `in`, `notIn`, `contains`
- Existenz: `exists`
- Arithmetik: `add`, `sub`, `mul`, `div`
- Pfadzugriff: `{ "path": "room.roomTypeId" }`
- Literale: string, number, boolean, null, array

Beispiel – `availableWhen` des Werts „Bodentief“ (verfügbar, wenn kein angrenzender Raum ein Bad ist):

```json
{
  "op": "not",
  "args": [
    { "op": "contains", "left": { "path": "element.adjacentRooms.roomTypeId" }, "right": "bathroom" }
  ]
}
```

Verfügbare Pfade sind pro Auswertungskontext dokumentiert (`element.*`, `room.*`, `building.*`, `site.*`, `selection.*`, `quantity.*`). Ein Pfad auf eine Liste liefert eine Liste.

Die Engine definiert explizit das Verhalten bei `null`, fehlenden Pfaden, Typfehlern und Division durch null. Expressions enthalten niemals JavaScript oder sonstigen ausführbaren Code.

**Keine stille Mutation:** Die Rule Engine darf weder `Configuration.selections` noch gespeicherte Daten selbst ändern. Sie liefert nur strukturierte Ergebnisse und optionale Vorschläge.

## 9. Preisberechnung

### 9.1 Modell

Gerechnet wird **bottom-up**. Es gibt keine versteckten Produktpreise im Bauteilmodell.

```text
Nettopreis = Σ lumpSum-Regeln    PriceEntry.value
           + Σ perUnit-Regeln    Menge(quantityKey) × PriceEntry.value
           ± Σ percent-Regeln    Basis × PriceEntry.value / 100   (in Reihenfolge `order`)
Brutto     = Netto × (1 + vatRate des Marktes)
```

Ein `PriceEntry` geht nur über eine `PricingRule` in den Preis ein. Die gesamte Basisleistung eines Templates ist ein `PriceEntry` mit `targetKind: "template"` und wird über eine `lumpSum`-Regel angewendet. Das Template selbst enthält keine Preise.

Aufpreise in der UI („+40 €/m²“, „+5.003 €“) sind **abgeleitet**: Differenz zwischen dem Ergebnis mit der aktuellen Auswahl und dem Ergebnis mit dem Default-Wert dieses Slots. Dazu rechnet die Engine bei Bedarf eine zweite Variante. Deltas werden lazy berechnet und anhand von `(templateVersionId, catalogVersionId, configurationHash, slotId)` memoisiert.

Dadurch sind auch Wechselwirkungen korrekt erfasst. Beispiel: Größere Fenster erhöhen den Fensterpreis, verringern aber die Wandfläche und damit den Wandpreis.

### 9.2 Preisregeln

```ts
PricingRule {                       // sagt nur, WELCHE MENGE mit WELCHEM PriceEntry verrechnet wird
  id; label: LocalizedText
  appliesTo: Selector | { slotId; optionValueId }
  method: "perUnit" | "lumpSum" | "percent"
  quantityKey?                       // Pflicht bei perUnit (Abschnitt 7)
  price:
    | { entryId: PriceEntryId }      // fester Eintrag, z. B. Basisleistung, Auflager
    | { byTarget: PriceEntry["targetKind"] }
                                     // Eintrag wird über die refId der Menge gefunden,
                                     // z. B. eine Regel für ALLE Wandschichten
  percentBase?: "subtotal" | QuantityKey   // nur bei percent
  order
}
```

`PricingRule` enthält keine Beträge. Fehlt bei `byTarget` für eine Menge der passende `PriceEntry`, ist das ein Fehler, der bereits bei der Kompatibilitätsprüfung auffällt, nicht erst beim Kunden.

Einheiten: €/m², €/m, €/m³, €/Stück, pauschal, %.

### 9.3 Ergebnis

```ts
PriceResult {
  catalogVersionId; market
  baseAmount                        // Summe der PriceEntries mit targetKind "template"
  items: { label; quantity; unit; unitPrice; total; slotId?; elementIds }[]
  netTotal; vatRate; vatAmount; grossTotal
  deltas: Record<SlotId, number>    // Differenz zum Default pro Slot, für die UI
  isEstimate: true
}
```

Rundung: intern ungerundet, Anzeige auf ganze Euro, Positionen auf Cent. Die UI kennzeichnet alle Preise als Richtpreis vorbehaltlich Prüfung durch das Architekturbüro.

## 10. Grundstück und Bauvorschriften

### 10.1 Grundstück

```ts
Site {
  id
  polygon: Point2[]
  siteRuleSetId
}

SitePlacement {
  siteId
  x
  y
  rotation
} // Ursprung: Referenzpunkt des Templates

SiteRuleSet {                      // z. B. "PLU Gemeinde X, Zone UB"
  id
  name: LocalizedText
  jurisdiction: "FR" | "DE"
}

SiteRuleSetVersion {
  id; siteRuleSetId; version
  source?: RuleSource
  parameters: Record<string, number | string | boolean>
  status: "draft" | "published"
}
```

MVP-Funktionen: Polygon zeichnen, Punkte verschieben, Fläche berechnen, Gebäude platzieren, verschieben, drehen, Abstände zur Grundstücksgrenze anzeigen.

Abstände und Flächen werden immer aus der **abgeleiteten Außenkontur** berechnet. Eine dickere Fassade verändert also Abstände und Footprint sofort.

### 10.2 Bauvorschriften

Bauvorschriften sind Adapter pro Rechtsraum (Abschnitt 3), parametriert über die `SiteRuleSetVersion`. Rechtsraumspezifische Begriffe stecken nur in Adaptern und Texten, nicht in der generischen Engine.

| Generische Regel | Frankreich (PLU) | Deutschland (B-Plan/LBO) |
|---|---|---|
| maximaler Überbauungsanteil | emprise au sol (CES) | GRZ |
| Mindestabstand zur Grenze | implantation / retrait par rapport aux limites séparatives | Abstandsflächen |
| abstandsabhängig von Höhe | prospect (z. B. L ≥ H/2) | Abstandsflächen (Faktor × H) |
| maximale Höhe | hauteur maximale | maximale Gebäudehöhe |
| überbaubare Fläche | zone constructible | Baufenster / Baugrenzen |

MVP: maximaler Überbauungsanteil, Mindestabstand zur Grenze und maximale Höhe, jeweils mit `outcome` gemäß konkreter Regeldefinition (im Demo `warning`). Die Struktur muss den späteren Import von Regelwerten aus einer separaten PLU-Analyse erlauben (Werte + Quelle + Fundstelle).

Wichtig: Die Anwendung ist kein rechtsverbindlicher Nachweis. Ein Regelresultat beschreibt die Prüfung gegen die im System hinterlegten Werte und Quellen; die fachliche Prüfung durch das Architekturbüro bleibt erforderlich.

## 11. Bauphysik (vorbereitet)

Nicht Kern des MVP, aber das Datenmodell trägt die Grundlagen von Anfang an:

- `Material.lambda`, `density`, `carbonPerM3`; `WindowType.uw`, `g`.
- MVP-Funktion: U-Wert eines Wandprofils nach vereinfachtem Verfahren: R = Rsi + Σ(d/λ) über alle Schichten mit `thermal = true` + Rse. Bei Hinterlüftung gilt Rse = Rsi. U = 1/R. Anzeige in der Optionskarte.
- MVP-Kennzahl: Fensterflächenanteil pro Fassadenrichtung.
- Später: Bbio/Cep/Ic (RE2020) bzw. GEG-Nachweis über einen Adapter. Die Mengenermittlung (Abschnitt 7) ist die gemeinsame Grundlage für Preis und Energie.

---

## 12. IFC-Import

### 12.1 Grundsätze

- Der Import läuft **serverseitig** im Admin-Bereich und erzeugt zunächst ein `ImportedTemplateDraft` + `ImportReport`. Erst nach expliziter Prüfung/Freigabe wird daraus eine veröffentlichte `HouseTemplateVersion`. Der Kunden-Client hat keine IFC-Abhängigkeit.
- IFC-Uploads gelten als nicht vertrauenswürdige Eingaben. Vor Verarbeitung gelten mindestens:
  - Authentifizierung und Autorisierung für den Admin-Endpunkt
  - Dateigrößen- und Laufzeitlimits
  - MIME-/Extension-Prüfung
  - isolierte temporäre Verarbeitung
  - kontrollierte Abhängigkeiten und kein Ausführen von IFC-Inhalten
  - Audit-Log für Upload, Import, Freigabe und Veröffentlichung
- Erkannt wird primär über **IFC-Semantik**, nicht über Layernamen oder Geometrieheuristiken. Farben werden nie verwendet.
- Keine KI, keine PDF- oder Bilderkennung, keine manuell vergebenen IDs im CAD.

### 12.2 Import-Vertrag

In `docs/ifc-import-contract.md` wird festgehalten, welche IFC-Dateien unterstützt werden:

- IFC-Schema (IFC4 bevorzugt; ob IFC2x3 unterstützt wird, entscheidet der Spike).
- Archicad-Übersetzer-Einstellungen: `IsExternal` gesetzt, Raumbegrenzungen 2nd Level exportiert, Mehrschichtaufbauten als Material-Layer-Sets, Einheiten Meter.
- Zuordnung Raumtyp: Tabelle von Archicad-Zonenkategorie (bzw. einer vereinbarten Raum-Property) auf `roomTypeId`. Ohne diese Zuordnung funktionieren raumabhängige Verfügbarkeiten und Regeln nach dem Import nicht.
- Unterstützte Teilmenge im MVP: gerade Wände mit konstanter Dicke, rechteckige Öffnungen, ebene Platten, Flachdach, ein Geschoss (Mehrgeschossigkeit im Modell vorbereitet).
- Nicht unterstützte Elemente führen zu klaren Fehlern bzw. Warnungen im Importbericht, nicht zu stillschweigend falscher Geometrie.

### 12.3 Erkennung

| Information | Primärquelle | Fallback |
|---|---|---|
| Wand außen/innen | `Pset_WallCommon.IsExternal` | Wand liegt auf dem Rand der Vereinigung aller Räume; danach Layername `CFG-WALL-EXT/INT` |
| Innenkante der Hülle | `IfcRelSpaceBoundary` (2nd Level) | `IfcMaterialLayerSetUsage` (Referenzlinie, DirectionSense, Offset) + Wandachse |
| Öffnung → Wand | `IfcRelFillsElement` → `IfcOpeningElement` → `IfcRelVoidsElement` | geometrische Überschneidung |
| Öffnung → Raum | Raumbegrenzungen | nächster Raum zur Öffnungsmitte auf der Innenseite |
| Geschosse | `IfcBuildingStorey` | – |
| Dach | `IfcRoof` inkl. aggregierter `IfcSlab` (PredefinedType ROOF) | `IfcSlab` ROOF ohne Container |
| Räume | `IfcSpace` (Name, LongName); `roomTypeId` über die Zuordnungstabelle des Import-Vertrags | nicht zuordenbarer Raum → Warnung, Admin weist Raumtyp im Draft zu |

Normalisierung: Einheiten, Projektursprung, Achsrichtung, Rundung auf die Toleranz, Schließen und Orientieren des Hüllenpolygons.

### 12.4 Importbericht

```text
IFC IMPORT – Haus 01 (IFC4, Archicad)

✓ 1 Geschoss
✓ Hülle geschlossen, 4 Segmente, Innenmaß 8,00 × 12,00 m
✓ 12 Innenwände
✓ 6 Fenster, alle einer Wand und einem Raum zugeordnet
✓ 6 Türen
✓ 6 Räume
✓ Bodenplatte, Dachdecke, Dach

⚠ Wand 2x7Kd… ohne IsExternal – über Geometrie als Außenwand erkannt
✗ Fenster 3fQa… keiner Wand zugeordnet

Status: Import mit Warnungen möglich
```

Jedes Element im Bericht ist anklickbar und wird in einer einfachen 2D/3D-Vorschau hervorgehoben.

---

## 13. 2D-Ansicht

SVG, ausschließlich aus dem `DerivedModel`.

- Darstellen: Wandschichten mit Schraffur je Material, Innenwände, Fenster, Türen (mit Aufschlag), Räume mit Name, Raumtyp und abgeleiteter Fläche, automatische Innen- und Außenbemaßung, Grundstück mit Abständen.
- Räume werden über `RoomTypeDefinition.displayKey` und das UI-Theme eingefärbt. Die Farben sind reine Darstellungsdaten und niemals eine Quelle für Geometrie- oder IFC-Erkennung.
- Bauteile mit `perElement`-Slots (z. B. Fenster) sind anklickbar; die Auswahl öffnet die Einzelkonfiguration (Abschnitt 15).
- Funktionen: Zoom, Pan, Fit to view, Elementauswahl, Hervorhebung, Ebenen ein-/ausblenden (Schichten, Bemaßung, Räume, Grundstück).
- Bei einer Auswahländerung werden die betroffenen Elemente kurz hervorgehoben.

## 14. 3D-Ansicht

React Three Fiber, ausschließlich aus dem `DerivedModel`.

- Wände mit sichtbaren Schichten (optional Schnitt-/Explosionsansicht), Fenster, Türen, Bodenplatte, Decken, Dach inkl. Gründach-Aufbau, Fassadenmaterialien über `renderKey`.
- Neuaufbau nur der geänderten Elemente (Memoisierung über Element-ID + Eingabe-Hash).
- Kamera und Navigation sind vom Konfigurations-State entkoppelt und bleiben bei Änderungen erhalten.
- Geometrieberechnung bei Bedarf in einem Web Worker.

## 15. Konfigurator-Oberfläche

Orientierung an hochwertigen Auto-Konfiguratoren, nicht an Admin-Dashboards.

```text
┌──────────────────────────────────────────────────────────────┐
│ LOGO                          FR | DE        SPEICHERN       │
├───────────────┬──────────────────────────────┬───────────────┤
│ KONFIGURATION │        2D | 3D | Grundstück  │ PREIS         │
│               │                              │ (Richtpreis)  │
│ Außenwand     │                              │ Basis         │
│ Fenster       │            HAUS              │ Optionen      │
│ Dach          │                              │ Netto / TVA   │
│ …             │                              │ Gesamt        │
│               │                              │ ─────────     │
│               │                              │ Hinweise      │
└───────────────┴──────────────────────────────┴───────────────┘
```

Jede Optionskarte zeigt: Name, Aufpreis (Delta), geometrische Auswirkung und – falls vorhanden – Kennwerte. Beispiel:

```text
Vorgehängte Ziegelfassade
+40 €/m² Fassade · ca. +6.961 € inkl. Auflager
+12 cm Außenwand · Innenmaße unverändert
U-Wert ≈ 0,20 W/(m²K)
```

Die Zustände eines Werts kommen aus `evaluateCandidates` (Abschnitt 8.2):

- **nicht verfügbar** (für kein Ziel-Element): deaktiviert, mit Grund.
- **teilweise verfügbar**: wählbar, mit Hinweis „gilt für 5 von 6 Fenstern“.
- **würde blockieren**: wählbar, aber deutlich markiert, mit Grund; nach Auswahl wird die Konfiguration `blocked` und die Übergabe ist gesperrt.
- **mit Warnung**: wählbar, Hinweis sichtbar.

Hinweise der Rule Engine und `ResolutionNote`s erscheinen im Hinweisbereich und am betroffenen Element. Vorschläge (`suggestion`) werden als ausführbare Aktion angeboten.

**Einzelkonfiguration:** Für Slots mit `perElement` oder `perRoom` kann der Kunde ein Element in 2D oder 3D anklicken (oder aus einer Liste wählen). Ein Kontextpanel zeigt den effektiven Wert, seine Herkunft (Element / Raum / global / Standard) und die verfügbaren Alternativen. Aktionen: „nur für dieses Element“, „für diesen Raum“, „Überschreibung entfernen“. Elemente mit Überschreibung sind in 2D/3D markiert.

Der Kunde sieht jederzeit: Was habe ich gewählt? Was kostet es? Was verändert sich geometrisch? Ist es zulässig?

---

## 16. Persistenz und Versionierung

Entitäten:

```text
HouseTemplate, HouseTemplateVersion, TemplateElement, ImportedTemplateDraft
Material, WallProfile, WallLayer, WindowType, DoorType, RoofType
ConfigSlot, OptionValue, Rule, PricingRule
PriceCatalog (Version, Markt)
SiteRuleSet, SiteRuleSetVersion
Site
SavedConfiguration, Submission
CatalogCompatibility
ImportJob, ImportReport
```

- Template- und Katalogversionen haben den Status `draft` oder `published`. Veröffentlichte Versionen sind unveränderlich.
- `SavedConfiguration` speichert: `templateVersionId`, `catalogVersionId`, `siteRuleSetVersionId`, `selections`, `site`, sowie einen **Ergebnis-Snapshot** (`PriceResult`, Mengen, Regelergebnisse, `engineVersion`, `computedAt`). Der Snapshot wird serverseitig berechnet. Die gespeicherte Konfiguration referenziert damit unveränderliche Versionen von Template, Katalog und Regelwerk.
- Eine gespeicherte Konfiguration behält ihre Versionen. Die Übernahme in eine neue Template-, Katalog- oder SiteRuleSet-Version ist eine explizite Aktion mit Vergleich (alter vs. neuer Preis, nicht mehr verfügbare Werte, geänderte Regelresultate).

## 17. Übergabe und Admin-Bereich

### 17.1 Übergabe an das Architekturbüro

Export einer gespeicherten Konfiguration als:

- PDF-Dossier: Grundriss mit Bemaßung, Ansichten, 3D-Bild, Lage auf dem Grundstück, Optionsliste, Mengen, Kostenschätzung, Ergebnis der Regelprüfung, verwendete Versionen.
- JSON (maschinenlesbar, vollständig).
- Später: konfiguriertes IFC für den Rückweg nach Archicad.

Die Übergabe ist ein eigener Vorgang:

```ts
Submission {
  id; savedConfigurationId
  snapshot                          // eingefrorene Kopie von Auswahl, Versionen und Ergebnis-Snapshot
  status: "submitted" | "inReview" | "returned" | "offerIssued" | "withdrawn"
  submittedAt; statusHistory[]
  agencyNotes?: string              // Rückmeldung des Büros, z. B. bei "returned"
}
```

- Nur Konfigurationen mit Status `valid` oder `validWithWarnings` können eingereicht werden.
- Eine eingereichte Konfiguration ist eingefroren. Änderungen des Kunden erzeugen eine neue `SavedConfiguration` und ggf. eine neue `Submission`.
- Das Büro sieht eingereichte Vorgänge in einer eigenen Ansicht und setzt den Status. Das verbindliche Angebot selbst entsteht außerhalb der Anwendung; im MVP wird nur sein Status erfasst.

### 17.2 Admin

- IFC hochladen, Importbericht prüfen, Template als neue Version veröffentlichen.
- Katalog pflegen: Materialien, Profile, Fenster-, Tür-, Dachtypen, Slots, Werte, Regeln, Preise.
- Katalogversion veröffentlichen, Werte aktivieren/deaktivieren.
- Vorschau: Template mit beliebiger Konfiguration im Kunden-Konfigurator öffnen.

Minimale Admin-Authentifizierung entsteht in Phase 0. Kundenkonten, Rollen (Kunde, Architekturbüro, Admin) und Mandanten werden in Phase 4 festgelegt (ADR).

---

## 18. Phasen und Abnahmekriterien

### Phase 0 – Setup und IFC-Spike

- Monorepo, Linting, Formatierung, CI mit Tests.
- Spike: eine echte Archicad-IFC-Datei in Node einlesen und dokumentieren, welche der in Abschnitt 12.3 genannten Properties und Relationen tatsächlich vorhanden sind. Ergebnis: `docs/ifc-spike.md` und erster Entwurf von `docs/ifc-import-contract.md`.
- Minimale Admin-Authentifizierung und Autorisierung als Voraussetzung für alle späteren IFC-/Katalog-Endpunkte.
- Clipper2-Port prüfen (Offset, Boolesche Operationen, Präzision).
- ADRs für IFC-Bibliothek und Polygonbibliothek.

**Abnahme:** CI grün, Spike-Bericht liegt vor, Bibliotheken entschieden.

### Phase 1 – Domänenkern (ohne UI, ohne IFC)

- Typen aus Abschnitt 5, **eingefrorene Test-Fixture** (Template-JSON + Katalog des Demohauses, Abschnitt 19) und davon getrennter Demo-Seed.
- Resolver inkl. Verfügbarkeit und `ResolutionNote`, `evaluateCandidates`, Geometry Engine, Quantity Takeoff, Pricing Engine, Rule Engine (Grundfunktionen), U-Wert.
- Kompatibilitätsprüfung Template ↔ Katalog (Invariante 5) als Funktion des Domänenkerns.
- CLI-Skript, das für die Demo-Szenarien (Abschnitt 19.7) Mengen, Preise und Regelergebnisse ausgibt.

**Abnahme:** alle Tests aus Abschnitt 20.1 grün; CLI-Ausgabe entspricht den Erwartungswerten.

### Phase 2 – Viewer und Konfigurator-UI

- 2D-Viewer, 3D-Viewer, Konfigurationspanel inkl. Einzelkonfiguration, Preispanel, Hinweisbereich, i18n FR/DE, auf Basis des Demo-Seeds.
- Performance-Zielwerte aus 4.1 messen und für das Demohaus dokumentieren.

**Abnahme:** alle Demo-Szenarien sind in 2D, 3D und Preis sichtbar nachvollziehbar; Kamera bleibt bei Änderungen stabil; Performance-Basiswerte sind dokumentiert.

### Phase 3 – IFC-Import

- Importer gemäß Abschnitt 12, Importbericht, minimale Admin-Ansicht für Upload und Bericht.
- Referenz-IFC des Demohauses aus Archicad.

**Abnahme:** Der Import der Referenz-IFC erzeugt ein Template, das mit dem Fixture aus Phase 1 innerhalb der Toleranz übereinstimmt (Golden-Test). Fehlerhafte Testdateien erzeugen die erwarteten Meldungen.

### Phase 4 – Grundstück, Regeln, Persistenz

- Grundstücksplaner, `SiteRuleSet`/`SiteRuleSetVersion` mit FR-Adapter, Datenbank, Speichern/Laden mit serverseitiger Neuberechnung, Kundenkonten und Rollen.

**Abnahme:** gespeicherte Konfiguration lässt sich nach Katalogänderung unverändert laden; Server- und Clientpreis stimmen überein.

### Phase 5 – Übergabe, Admin, Versionierung

- PDF/JSON-Export, `Submission`-Ablauf mit Ansicht für das Architekturbüro, Katalogpflege, Veröffentlichung von Versionen inkl. Kompatibilitätsfreigabe, Migration gespeicherter Konfigurationen.

---

## 19. Demo-Daten

Alle Werte sind Beispieldaten. Sie existieren zweimal:

- als **Test-Fixture** (`packages/domain/test/fixtures/demo-house/`): eingefroren, nur durch bewusste Änderung zusammen mit den Erwartungswerten in Abschnitt 19.7/20 veränderbar;
- als **Demo-Seed** für Entwicklung und Präsentation: frei änderbar, ohne dass Tests brechen.

### 19.1 Demohaus

```text
Geschosse:            1
Innenmaß Hülle:       8,00 × 12,00 m (Innenkante tragende Schicht)
Lichte Raumhöhe:      2,70 m
Fassadenhöhe:         3,20 m (UK Bodenplatte bis OK Attika, vereinfacht konstant)
Räume (6):            Wohnen/Essen (living), Küche (kitchen), Schlafen (bedroom),
                      Kind (bedroom), Bad (bathroom), Flur (corridor)
Fenster (6):          Wohnen 2, Küche 1, Schlafen 1, Kind 1, Bad 1
Türen (6):            1 Haustür 1,00 × 2,10 m, 5 Innentüren
Basis-PriceEntry:      390.000 € netto
Markt:                FR, TVA 20 %
```

### 19.2 Wandprofile (Schichten von innen nach außen)

| Profil | Schichten | Gesamt |
|---|---|---|
| Standard | Beton 20 cm (λ 2,1; 70 €/m²) · Dämmung 16 cm (λ 0,035; 50 €/m²) | 36 cm |
| Vorgehängte Ziegelfassade | wie Standard · Unterkonstruktion/Hinterlüftung 4 cm (nicht thermisch; 15 €/m²) · Ziegel 8 cm (nicht thermisch; 25 €/m²) | 48 cm |
| Holzfassade | wie Standard · Unterkonstruktion/Hinterlüftung 4 cm (nicht thermisch; 15 €/m²) · Holzverkleidung 4 cm (nicht thermisch; 50 €/m²) | 44 cm |

`openingAnchorLayerId` ist bei allen Profilen die Dämmschicht. Die Schichten Beton, Dämmung und Unterkonstruktion sind jeweils **ein** Katalogobjekt, das von mehreren Profilen referenziert wird. Default: Standard.

Zusätzlich:

| Profil | Auflager | Laibungsbekleidung |
|---|---|---|
| Standard | – | – |
| Ziegel | `foundationLedge` für die Ziegelschicht; PriceEntry `service: bearing.foundationLedge` = 45 €/m | ja, im Demo ohne eigenen Preis (in der Basisleistung enthalten) |
| Holz | – (Unterkonstruktion an der Tragschicht befestigt) | ja, im Demo ohne eigenen Preis |

### 19.3 Fenster

| Typ | Breite × Höhe | Sturz | Brüstung | Preis |
|---|---|---|---|---|
| Standard | 1,20 × 1,60 m | 2,50 m | 0,90 m | 850 € |
| Bodentief | 1,20 × 2,50 m | 2,50 m | 0,00 m | 1.250 € |

Slot „Fenstertyp“: `granularity: "perElement"`, globaler Wert mit Einzel- und Raumüberschreibung. Verfügbarkeit: Bodentief hat `availableWhen` „kein angrenzender Raum vom Typ `bathroom`“ (Beispiel in Abschnitt 8.4). Default: Standard.

### 19.4 Preisbehandlung im Demohaus

Der Basisbetrag von 390.000 € wird als `PriceEntry` des `PriceCatalog` geführt. Nicht separat konfigurierte Standardleistungen (einschließlich der im MVP nicht separat bepreisten Innentüren) sind in diesem Basisbetrag enthalten. Sobald diese Leistungen konfigurierbar werden, erhalten sie eigene `PriceEntry`-Datensätze.

Preisregeln der Demo:

| PricingRule | Methode | Menge | Preisquelle |
|---|---|---|---|
| Basisleistung | `lumpSum` | – | `entryId` Template Demohaus (390.000 €) |
| Wandschichten | `perUnit` | `wall.layer.area` | `byTarget: "wallLayer"` |
| Fenster | `perUnit` | `window.count` | `byTarget: "windowType"` |
| Dach | `perUnit` | `roof.area` | `byTarget: "roofType"` |
| Auflager | `perUnit` | `bearing.length` | `entryId` `service: bearing.foundationLedge` |

### 19.5 Dach

| Typ | Aufbau | Preis |
|---|---|---|
| Flachdach | Standardaufbau | 180 €/m² |
| Gründach (extensiv) | Standardaufbau + 12 cm Substrat/Vegetation | 260 €/m² |

Default: Flachdach.

### 19.6 Grundstück und Regeln

```text
Grundstück:            18,00 × 12,00 m (216 m²)
Platzierung:           Haus mittig, Längsseite parallel zur 18-m-Seite
SiteRuleSet:           Demo-PLU (FR)
Regel Überbauung:      max. 55 % (outcome: warning)
Regel Grenzabstand:    min. 1,50 m (outcome: warning)
```

### 19.7 Demo-Szenarien und Erwartungswerte

| Szenario | Erwartung |
|---|---|
| Ausgangszustand | Innen 8,00 × 12,00; außen 8,72 × 12,72 m; Netto 429.328,51 € |
| Ziegelfassade | Innen unverändert; außen 8,96 × 12,96 m; Wand 48 cm; Fassadenschichten +5.002,72 €, Auflager 43,52 m × 45 € = +1.958,40 €, gesamt +6.961,12 €; Laibungsfläche 3,792 m² |
| Holzfassade | außen 8,88 × 12,88 m; +8.118,22 €; kein Auflager; Laibungsfläche 2,528 m² |
| Bodentief global (Standardfassade) | Auswahl bleibt global „Bodentief“; effektiv 5 Fenster bodentief, Bad-Fenster Standard mit `ResolutionNote`; Status `valid`; Fensterpositionen unverändert; Fenster +2.000 €, Wand −648 €, gesamt +1.352 € |
| Gründach | Dachaufbau in 3D sichtbar; Dachfläche 110,92 m²; +8.873,47 € |
| Grundstück Standard | Grenzabstände 1,64 / 2,64 m; Überbauung 51,35 % |
| Grundstück Ziegel | Grenzabstände 1,52 / 2,52 m; Überbauung 53,76 % |

---

## 20. Tests

### 20.1 Unit-Tests Domänenkern (Phase 1)

Mit der Test-Fixture (nicht mit dem Demo-Seed):

- Außenkontur: Standard 8,72 × 12,72 m, Ziegel 8,96 × 12,96 m, Holz 8,88 × 12,88 m; Außenumfang 42,88 / 43,84 / 43,52 m.
- Innenkontur bei jedem Profil exakt 8,00 × 12,00 m.
- Öffnungsflächen: Standardfenster 13,62 m² (inkl. Haustür); bei Bodentief global 19,02 m².
- Schichtflächen (Standardfenster): Beton 116,94 m², Dämmung 121,548 m², UK 124,108 m², Ziegel 125,644 m², Holz 125,132 m².
- Fenster behalten `offsetAlongHost` und Sturzhöhe bei Profil- und Typwechsel; Brüstung bodentief = 0.
- Resolver: globaler Wert „Bodentief“ greift im Bad nicht; genau eine `ResolutionNote` für das Bad-Fenster; `selections` danach unverändert; Einzelüberschreibung auf ein anderes Fenster wirkt.
- Element-Override „Bodentief“ direkt am Bad-Fenster: wird übersprungen, `ResolutionNote` mit `skippedLevel: "element"`.
- Raum-Override an einer Innentür zwischen Räumen gleicher `overridePriority` greift nicht und erzeugt eine `ResolutionNote`.
- `evaluateCandidates` für den Fenster-Slot: „Bodentief“ ist teilweise verfügbar (5 von 6), Preisdelta +1.352 €.
- Auflager Ziegel: `bearing.length` 43,52 m; Laibungsfläche Ziegel 3,792 m² (Standardfenster) bzw. 4,872 m² (Bodentief global), Holz 2,528 m².
- Preise und Deltas gemäß Abschnitt 19.7; Deltas sind unabhängig von der Auswahlreihenfolge.
- Jeder Betrag im `PriceResult` ist auf genau einen `PriceEntry` zurückführbar; fehlender `PriceEntry` bei `byTarget` wird von der Kompatibilitätsprüfung gemeldet.
- Dachfläche 110,9184 m²; Gründach-Delta 8.873,47 €.
- Grundstück: Fläche 216 m²; Grenzabstände und Überbauung gemäß 19.7; mit Überbauungsgrenze 52 % ist Standard zulässig, Holz (52,95 %) und Ziegel (53,76 %) erzeugen eine Warnung.
- U-Wert Standard ≈ 0,207 W/(m²K); Ziegel/Holz ≈ 0,203 W/(m²K) (Rse = Rsi wegen Hinterlüftung).
- TVA 20 % korrekt auf Netto.
- Status: eine Regel mit `outcome: block` macht die Konfiguration `blocked`, ohne `selections` zu verändern; `blocked` kann gespeichert, aber nicht eingereicht werden.

### 20.1.1 Semantische Grundriss-Tests

Mit dem Demohaus zusätzlich:

- Jeder Raum besitzt eine gültige `roomTypeId` und eine geschlossene Geometrie.
- Raumflächen werden ausschließlich aus der Raumgeometrie abgeleitet.
- Jede Innenwand referenziert 0–2 angrenzende Räume.
- Türen referenzieren ihre angrenzenden Räume.
- Öffnungen liegen vollständig innerhalb ihres Hosts und überlappen sich nicht.
- Ein Wechsel des Außenwandprofils verändert weder Raum-Polygone noch Innenwandachsen.
- Raumfarben oder sonstige Darstellungskeys verändern keinerlei Geometrie, Mengen, Preis oder Regelresultate.

### 20.2 Property-based Tests

- Für beliebige zulässige Profile (zufällige Schichtdicken) und beliebige konvexe wie konkave rechtwinklige Hüllen: Innenkontur bleibt identisch, Außenkontur liegt vollständig außerhalb, Öffnungen bleiben an ihrer Position.
- Preisberechnung ist deterministisch und unabhängig von der Reihenfolge der Auswahl.
- Resolver-Priorität ist deterministisch: Element > Raum > global > Template-Default, jeweils nur unter verfügbaren Werten.
- Für beliebige einfache rechtwinklige Hüllen gilt: Länge der Schicht-Mittellinie = Innenumfang + 8·d.
- Inkrementelle Neuberechnung nach einer zufälligen Folge von Auswahländerungen ergibt dasselbe Ergebnis wie eine vollständige Neuberechnung (Invariante 12).
- Die Rule Engine verändert für keine Eingabe die `selections`.

### 20.3 Golden- und Integrationstests

- Referenz-IFC → Template stimmt mit Fixture überein (Phase 3).
- Fehlerhafte IFC-Dateien → erwartete Meldungen im Importbericht.
- Ende-zu-Ende: IFC importieren → Raumtypen zugeordnet → Template veröffentlichen → Kompatibilität freigeben → Konfiguration ändern → Geometrie, Mengen, Preis aktualisiert → speichern → Serverpreis = Clientpreis → einreichen.

---

## 21. Nicht-Ziele für das MVP

- Geneigte Dächer, Mehrgeschossigkeit, gekrümmte Wände, nicht rechteckige Öffnungen (Modell vorbereitet, nicht implementiert).
- Vollständiger RE2020- oder GEG-Nachweis.
- Statische Bemessung.
- Online-Bezahlung oder verbindliche Angebote.
- Beliebiges IFC aus anderen Quellen als dem definierten Archicad-Workflow.

---

## 22. Zielbild

```text
Archicad → IFC-Export → Upload → Import + Bericht → Template veröffentlichen
   → Kunde öffnet Konfigurator → Außenwand, Fenster, Dach wählen
   → 2D, 3D, Mengen, Preis und Hinweise aktualisieren sich
   → Grundstück zeichnen → Haus platzieren → Bauvorschriften geprüft
   → Konfiguration speichern → einreichen → Architekturbüro prüft → Angebot
```

Aus drei Wandvarianten, zwei Fenstertypen und zwei Dächern sollen später Hunderte Optionen werden, ohne die Engine umzubauen. Räume, Wände und Öffnungen bleiben dabei semantisch getrennte, stabile Gebäudeelemente; neue Innenausbau- und Haustechnikoptionen werden über Slots, Katalogdaten und Regeln ergänzt. Die entscheidende Designregel:

> **Das Template ist unveränderlich, die Konfiguration ist nur Auswahl, alles andere wird abgeleitet. Optionen sind Daten, Regeln sind Daten, Preise sind Daten. IFC ist ein kontrollierter Importweg.**
