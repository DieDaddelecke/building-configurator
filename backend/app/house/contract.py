"""Vertrag des Hausmodells (docs/PLAN_HAUSMODELL.md 3.4, E-HM-5, E-HM-29): Dokumente und Ergebnisse an der
Grenze zwischen Python und dem Rechenkern `packages/domain`.

Die Modelle gehen über `openapi.json` (`components.schemas`, Wurzeln in `x-house-contract`) nach
`packages/domain/src/contract.gen.ts`. Kein Feld hat einen Standardwert: Eingabe- und Ausgabeschema sind
gleich, und jedes Dokument steht vollständig da. Längen in Metern (lokale Modellmeter, Y = Modellnord),
Flächen in m², Beträge in Euro netto und ungerundet; der Kern rechnet die Geometrie ganzzahlig in 0,1 mm.
Höhen beziehen sich auf ±0,00 = Oberkante Bodenplatte des Erdgeschosses (E-HM-35).

Gespeicherte Dokumente bleiben unverändert (L4). Template und Katalog mit `schema_version` 1 sowie
Auswertungen des Kerns vor 0.4.0 hebt die Validierung beim Lesen auf den heutigen Stand (E-HM-58); `engine`
nimmt nur den heutigen.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.house.domain.zones import ZoneTable

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_$.\-]{1,64}$")]
"""Kennung; Elemente aus dem IFC leiten sie aus der `GlobalId` ab (stabil bei erneutem Import)."""
Coordinate = Annotated[float, Field(ge=-1000, le=1000)]
Height = Annotated[float, Field(ge=-100, le=100)]
Length = Annotated[float, Field(gt=0, le=100)]
Thickness = Annotated[float, Field(gt=0, le=2)]
NonNegative = Annotated[float, Field(ge=0, le=100)]
Amount = Annotated[float, Field(ge=-1e9, le=1e9)]
ZoneCategory = Annotated[str, Field(min_length=1, max_length=100)]
Pitch = Annotated[float, Field(gt=0, lt=90)]
"""Dachneigung in Grad."""
BreakHeight = Annotated[float, Field(gt=0, le=20)]
"""Krüppel- bzw. Knickhöhe über dem Auflager auf der Bezugskontur."""

RoofShapeKind = Literal["flat", "mono_pitch", "gable", "hip", "half_hip", "mansard", "mansard_gable"]
"""Dachformen des Kerns (Ergänzung 11). Die Begriffe der PLU-Regeln ordnet Python zu (E-HM-61)."""
TWO_PART_FORMS: tuple[RoofShapeKind, ...] = ("half_hip", "mansard", "mansard_gable")
"""Formen mit zweitem Abschnitt: Krüppelwalm über der Krüppelhöhe, Mansarde über dem Knick."""
RoofRotation = Literal[0, 90, 180, 270]
"""Drehung gegen den Uhrzeigersinn: bei Sattel-, Krüppelwalm- und Mansardsatteldach liegt der First bei 90
quer zur längeren Seite jedes Flügels, beim Pultdach dreht die Traufseite (Ergänzung 4)."""

MaterialClass = Literal[
    "render",
    "wood",
    "brick",
    "stone",
    "concrete",
    "metal",
    "glass",
    "slate",
    "clay_tile",
    "zinc",
    "composite",
    "vegetation",
    "other",
]
"""Materialklassen der PLU-Prüfung, gleich `app.rules.domain.kinds.MATERIALS` (Ergänzung 8)."""
FacadeRole = Literal["street", "garden", "side_left", "side_right"]
ElementKind = Literal["envelope_segment", "interior_wall", "opening", "roof", "room", "building", "site"]
"""`site`: Nebenbauten auf dem Grundstück, Ziel der Slots für Terrasse und Carport (Ergänzung 7)."""
Outcome = Literal["info", "warning", "block"]
ResultOutcome = Literal["info", "warning", "block", "deviation"]
"""`deviation` vergibt nur die PLU-Prüfung in Python (E-HM-6)."""
Status = Literal["valid", "valid_with_warnings", "with_deviations", "blocked"]
PriceTargetKind = Literal[
    "wall_layer",
    "window_type",
    "door_type",
    "roof_type",
    "template",
    "slot_option",
    "service",
    "terrace_type",
    "carport_type",
]
PriceUnit = Literal["m", "m2", "m3", "pcs", "lump_sum", "percent"]
QuantityUnit = Literal["m", "m2", "m3", "pcs"]


class HouseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _unique(kind: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for value in ids:
        if value in seen:
            raise ValueError(f"{kind}: Kennung {value} doppelt")
        seen.add(value)


def _shape_parameters(
    form: RoofShapeKind, pitch: object | None, upper_pitch: float | None, break_height: float | None
) -> None:
    if (form == "flat") != (pitch is None):
        raise ValueError("eine Neigung genau bei geneigten Formen")
    two_part = form in TWO_PART_FORMS
    if two_part != (upper_pitch is not None) or two_part != (break_height is not None):
        raise ValueError("obere Neigung und Knickhöhe genau bei Krüppelwalm und Mansarde")


class HouseText(HouseModel):
    """Text in den Sprachen der Oberfläche (D7: Französisch führend, Deutsch zusätzlich)."""

    fr: str = Field(min_length=1, max_length=500)
    de: str = Field(min_length=1, max_length=500)


class HousePoint(HouseModel):
    x: Coordinate
    y: Coordinate


Ring = Annotated[list[HousePoint], Field(min_length=3, max_length=1000)]


# --- Ausdrücke (P 8.4, E-HM-34) -------------------------------------------------------------------------


class HousePathExpr(HouseModel):
    path: str = Field(pattern=r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$", max_length=200)


class HouseBinaryExpr(HouseModel):
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "add", "sub", "mul", "div"]
    left: "HouseExpr"
    right: "HouseExpr"


class HouseLogicExpr(HouseModel):
    op: Literal["and", "or", "not", "exists"]
    args: list["HouseExpr"] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _arity(self) -> "HouseLogicExpr":
        if self.op in ("not", "exists") and len(self.args) != 1:
            raise ValueError(f"{self.op} braucht genau ein Argument")
        return self


type HouseLiteral = str | float | bool | None
type HouseExpr = HousePathExpr | HouseBinaryExpr | HouseLogicExpr | HouseLiteral | list[HouseLiteral]
"""Ausdruck ohne ausführbaren Code: Pfad, Operator oder Literal; Listen enthalten nur Literale."""


# --- Werte eines Slots (P 5.3) ----------------------------------------------------------------------------


class HouseSlotOption(HouseModel):
    type: Literal["option"]
    option_value_id: Id


class HouseSlotNumber(HouseModel):
    """Zahl eines Parameter-Slots, z. B. Dachneigung in Grad (E-HM-62)."""

    type: Literal["number"]
    value: Annotated[float, Field(ge=-1000, le=1000)]


type HouseSlotValue = Annotated[HouseSlotOption | HouseSlotNumber, Field(discriminator="type")]


# --- Template (P 5.1) -----------------------------------------------------------------------------------


class HouseSourceIfc(HouseModel):
    file_name: str = Field(max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ifc_schema: str = Field(max_length=20)
    imported_at: datetime


class HouseLevel(HouseModel):
    id: Id
    name: str = Field(max_length=100)
    elevation: Height
    """Oberkante Rohfußboden über ±0,00; im Erdgeschoss 0."""


class HouseEnvelopeSegment(HouseModel):
    """Kante `i` der Bezugskontur, von Punkt `i` zu Punkt `i + 1`."""

    id: Id
    source_ifc_guid: str | None
    facade_role: FacadeRole | None
    """Im Entwurf bestätigt (E-HM-13); richtet Schnellstellungen, Terrasse und Zufahrt aus."""


class HouseEnvelopeLoop(HouseModel):
    level_id: Id
    inner_polygon: Ring
    """Bezugskontur: Innenkante der innersten Profilschicht, gegen den Uhrzeigersinn (E-HM-24)."""
    segments: list[HouseEnvelopeSegment]

    @model_validator(mode="after")
    def _segments_match(self) -> "HouseEnvelopeLoop":
        if len(self.segments) != len(self.inner_polygon):
            raise ValueError("je Kante der Bezugskontur genau ein Segment")
        return self


class HouseInteriorWall(HouseModel):
    id: Id
    source_ifc_guid: str | None
    level_id: Id
    axis: tuple[HousePoint, HousePoint]
    thickness: Thickness
    adjacent_room_ids: list[Id] = Field(max_length=2)


class HouseOpening(HouseModel):
    id: Id
    source_ifc_guid: str | None
    kind: Literal["window", "door"]
    host_kind: Literal["envelope_segment", "interior_wall"]
    host_id: Id
    offset_along_host: NonNegative
    """Vom Anfang des Hosts bis zur Mitte der Öffnung: bei Hüllensegmenten auf der Bezugskontur, bei
    Innenwänden auf der Achse. Ein anderes Profil oder ein anderer Typ verschiebt die Öffnung nicht
    (P 6.3)."""
    adjacent_room_ids: list[Id] = Field(min_length=1, max_length=2)


class HouseSlab(HouseModel):
    id: Id
    source_ifc_guid: str | None
    level_id: Id
    kind: Literal["ground", "floor", "roof"]
    thickness: Thickness


class HouseRoofDesign(HouseModel):
    """Dachform mit Parametern (Ergänzung 4, 11): aus dem IFC oder im Entwurf vom Büro gesetzt; Voreinstellung
    der Dachform im Konfigurator."""

    form: RoofShapeKind
    pitch_deg: Pitch | None
    """Traufflächen; beim Mansarddach der untere, steile Abschnitt."""
    upper_pitch_deg: Pitch | None
    """Krüppelwalm bzw. oberer Abschnitt des Mansarddachs."""
    break_height: BreakHeight | None
    rotation: RoofRotation

    @model_validator(mode="after")
    def _parameters(self) -> "HouseRoofDesign":
        _shape_parameters(self.form, self.pitch_deg, self.upper_pitch_deg, self.break_height)
        return self


FLAT_DESIGN: dict[str, Any] = {
    "form": "flat",
    "pitch_deg": None,
    "upper_pitch_deg": None,
    "break_height": None,
    "rotation": 0,
}
"""Entwurf eines Templates aus Schema 1: HM1 bis HM4 kannten nur das Flachdach."""


class HouseRoofPlacement(HouseModel):
    """Dach des Templates (3.6, E-HM-10): Lage, Maße und Form aus dem IFC; Form und Aufbau wählt der
    Konfigurator."""

    bearing_height: Height
    """Oberkante der Außenwände unter dem Dach über ±0,00, auf der Bezugskontur (Flachdach: Unterkante
    Dachdecke; geneigt: Unterseite des Dachs, Probedatei 2)."""
    parapet_height: NonNegative
    """Flachdach: Attika über Oberkante Dachdecke."""
    eave_overhang: NonNegative
    """Vor der Fassade, waagerecht gemessen."""
    verge_overhang: NonNegative
    design: HouseRoofDesign


class HouseRoom(HouseModel):
    """Raum; Fläche nur aus dem Umriss, Name aus dem Raumtyp (E-HM-23)."""

    id: Id
    source_ifc_guid: str | None
    level_id: Id
    room_type_id: Id
    polygon: Ring


class HouseTemplate(HouseModel):
    """Haustyp in einer Version, unveränderlich nach der Veröffentlichung (P 5.1, L4). Keine Preise.

    Mehrere Geschosse haben dieselbe Bezugskontur (E-HM-63); das Dach liegt über dem obersten."""

    schema_version: Literal[2]
    slug: Id
    """Haustyp über alle Versionen; darüber findet der Katalog die Basisleistung
    (`target_kind` `template`)."""
    name: HouseText
    source_ifc: HouseSourceIfc | None
    ground_floor_offset: Annotated[float, Field(ge=-5, le=5)]
    """±0,00 über dem Gelände (E-HM-11, Standard 0,20 m)."""
    levels: list[HouseLevel] = Field(min_length=1, max_length=10)
    envelope: list[HouseEnvelopeLoop] = Field(min_length=1, max_length=10)
    interior_walls: list[HouseInteriorWall] = Field(max_length=500)
    openings: list[HouseOpening] = Field(max_length=500)
    slabs: list[HouseSlab] = Field(max_length=50)
    roof: HouseRoofPlacement
    rooms: list[HouseRoom] = Field(max_length=200)
    entrance_opening_id: Id | None
    garage_door_opening_id: Id | None
    defaults: dict[Id, Id]
    """Slot → Wert, solange der Kunde nichts wählt."""
    element_defaults: dict[Id, dict[Id, Id]]
    """Element → Slot → Wert: Standard eines einzelnen Bauteils, z. B. ein Fenster mit eigenem Maß aus dem
    IFC; geht `defaults` vor (E-HM-37)."""

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        """Schema 1 beim Lesen heben: Flachdach als Entwurf (E-HM-58)."""
        if isinstance(data, dict) and data.get("schema_version") == 1 and isinstance(data.get("roof"), dict):
            return {**data, "schema_version": 2, "roof": {**data["roof"], "design": FLAT_DESIGN}}
        return data

    @model_validator(mode="after")
    def _unique_ids(self) -> "HouseTemplate":
        _unique("levels", [x.id for x in self.levels])
        elements = [s.id for loop in self.envelope for s in loop.segments]
        elements += (
            [x.id for x in self.interior_walls] + [x.id for x in self.openings] + [x.id for x in self.rooms]
        )
        _unique("elements", elements + [x.id for x in self.slabs] + ["roof", "building", "site"])
        known = set(elements) | {"roof"}
        for element_id in self.element_defaults:
            if element_id not in known:
                raise ValueError(f"element_defaults: Element {element_id} unbekannt")
        return self


# --- Katalog (P 5.2, E-HM-8) ----------------------------------------------------------------------------


class HouseCatalogParameters(HouseModel):
    parapet_min_upstand: NonNegative
    """Mindestüberstand der Attika über dem Dachaufbau (P 6.4)."""
    opening_deduction_threshold: NonNegative
    """Öffnungen bis zu dieser Fläche (m²) werden nicht von der Wandfläche abgezogen (P 7)."""
    surface_resistance_inside: Annotated[float, Field(gt=0, le=1)]
    surface_resistance_outside: Annotated[float, Field(ge=0, le=1)]
    """Rsi und Rse in m²K/W; bei Hinterlüftung gilt Rse = Rsi (P 11)."""


class HouseMaterial(HouseModel):
    id: Id
    name: HouseText
    conductivity: Annotated[float, Field(gt=0, le=500)] | None
    """Wärmeleitfähigkeit λ in W/(m·K)."""
    density: Annotated[float, Field(gt=0, le=30000)] | None
    carbon_per_m3: Annotated[float, Field(ge=-10000, le=100000)] | None
    render_key: str = Field(max_length=100)


class HouseWallLayer(HouseModel):
    id: Id
    material_id: Id
    thickness: Thickness
    structural: bool
    thermal: bool
    """`false` für Schichten außerhalb einer Hinterlüftung."""


class HouseBearing(HouseModel):
    supported_layer_ids: list[Id] = Field(min_length=1)
    kind: Literal["foundation_ledge", "brackets"]


class HouseRevealFinish(HouseModel):
    material_id: Id


class HouseWallProfile(HouseModel):
    id: Id
    name: HouseText
    layer_ids: list[Id] = Field(min_length=1, max_length=20)
    """Von innen nach außen; die erste Schicht beginnt auf der Bezugskontur (E-HM-24)."""
    opening_anchor_layer_id: Id
    bearing: HouseBearing | None
    reveal_finish: HouseRevealFinish | None
    material_class: MaterialClass


class HouseWindowType(HouseModel):
    id: Id
    name: HouseText
    width: Length
    height: Length
    head_height: Length
    """Sturz über ±0,00 des Geschosses; die Brüstung ist `head_height − height` (P 6.3)."""
    shutter_box_height: NonNegative
    """Rollladenkasten über dem Fenster; zählt zum Wandabzug (E-HM-30)."""
    uw: Annotated[float, Field(gt=0, le=10)] | None
    g: Annotated[float, Field(ge=0, le=1)] | None
    render_key: str = Field(max_length=100)


class HouseDoorType(HouseModel):
    id: Id
    name: HouseText
    width: Length
    height: Length
    render_key: str = Field(max_length=100)


class HouseRoofLayer(HouseModel):
    material_id: Id
    thickness: Thickness


class HouseRoofType(HouseModel):
    """Dachaufbau (E-HM-10); `kind` sagt, zu welchen Dachformen er passt."""

    id: Id
    name: HouseText
    kind: Literal["flat", "pitched"]
    build_up: list[HouseRoofLayer] = Field(min_length=1, max_length=20)
    """Flachdach: Aufbau über der Dachdecke. Geneigt: der ganze Aufbau senkrecht zur Fläche (Sparren,
    Dämmung, Deckung)."""
    green: bool
    material_class: MaterialClass
    render_key: str = Field(max_length=100)


class HouseRoofPitch(HouseModel):
    default_deg: Pitch
    min_deg: Pitch
    max_deg: Pitch

    @model_validator(mode="after")
    def _range(self) -> "HouseRoofPitch":
        if not self.min_deg <= self.default_deg <= self.max_deg:
            raise ValueError("Neigung: Spanne muss den Standard enthalten")
        return self


class HouseRoofShape(HouseModel):
    """Dachform des Katalogs (Ergänzung 4): Voreinstellung und Spanne der Neigung, Knick- und Krüppelhöhe.
    Ist die Form die des Templates, gelten die Werte des Templates. Überstände, Dachdecke und Attika gelten
    nur, wenn das Template die andere Dachart hat (flach ↔ geneigt)."""

    id: Id
    name: HouseText
    form: RoofShapeKind
    pitch: HouseRoofPitch | None
    upper_pitch_deg: Pitch | None
    break_height: BreakHeight | None
    eave_overhang: NonNegative
    verge_overhang: NonNegative
    slab_thickness: Thickness | None
    """Dachdecke des Flachdachs."""
    parapet_height: NonNegative | None
    """Attika des Flachdachs über Oberkante Dachdecke."""
    render_key: str = Field(max_length=100)

    @model_validator(mode="after")
    def _parameters(self) -> "HouseRoofShape":
        _shape_parameters(self.form, self.pitch, self.upper_pitch_deg, self.break_height)
        flat = self.form == "flat"
        if flat != (self.slab_thickness is not None) or flat != (self.parapet_height is not None):
            raise ValueError("Dachdecke und Attika genau beim Flachdach")
        return self


class HouseTerraceType(HouseModel):
    """Terrasse (Ergänzung 7): an der längsten Gartenkante, so breit wie diese; die Lage rechnet Python."""

    id: Id
    name: HouseText
    depth: Length
    height_above_terrain: NonNegative
    sealing_factor: Annotated[float, Field(ge=0, le=1)]
    """Anteil der Fläche, der als versiegelt zählt (`unsealed_min`)."""
    render_key: str = Field(max_length=100)


class HouseCarportType(HouseModel):
    """Carport (Ergänzung 7): Maße für Preis und Prüfung; Lage und Zufahrt rechnet Python."""

    id: Id
    name: HouseText
    spaces: int = Field(ge=1, le=10)
    width: Length
    depth: Length
    height: Length
    render_key: str = Field(max_length=100)


class HouseRoomType(HouseModel):
    id: Id
    name: HouseText
    description: HouseText | None
    override_priority: int = Field(ge=0, le=1000)
    """Entscheidet bei Bauteilen zwischen zwei Räumen, welche Raum-Überschreibung gilt (P 8.2)."""
    display_key: str = Field(max_length=100)
    """Nur Darstellung, nie Quelle für Logik (P 2.1 Nr. 10)."""
    aliases: list[ZoneCategory] = Field(max_length=50)
    """Zonenkategorien, die diesen Raumtyp bezeichnen (3.6 Nr. 3); nach der Normalisierung eindeutig."""
    exterior_door_role: Literal["entrance", "garage_door"] | None
    """Eine Außentür in einen Raum dieses Typs schlägt der Import als Eingang bzw. Garagentor vor
    (E-HM-13)."""


class HouseSelector(HouseModel):
    element_kind: ElementKind
    where: HouseExpr


class HouseSlotEffects(HouseModel):
    """Nur Hinweis für Neuberechnung; die Korrektheit hängt nie davon ab (P 8.1)."""

    geometry: bool
    quantity: bool
    pricing: bool
    rules: bool
    appearance: bool


class HouseSlot(HouseModel):
    id: Id
    category: str = Field(max_length=100)
    name: HouseText
    description: HouseText | None
    target: HouseSelector
    granularity: Literal["global", "per_element", "per_room"]
    value_type: Literal["single", "number"]
    """`single`: ein Wert des Katalogs. `number`: eine Zahl für `parameter`, global am Dach (E-HM-62)."""
    parameter: Literal["roof_pitch", "roof_rotation"] | None
    """`roof_pitch`: Neigung der Traufflächen in der Spanne der wirksamen Form; `roof_rotation`: 0, 90, 180
    oder 270. Standard und Spanne leitet der Kern ab, sie stehen nicht in `defaults`."""
    parent_slot_id: Id | None
    effects: HouseSlotEffects
    sort_order: int

    @model_validator(mode="after")
    def _parameter(self) -> "HouseSlot":
        if (self.value_type == "number") != (self.parameter is not None):
            raise ValueError("parameter genau bei value_type number")
        if self.parameter is not None and (
            self.granularity != "global" or self.target.element_kind != "roof"
        ):
            raise ValueError("Parameter-Slots gelten global für das Dach")
        return self


class HouseOptionAssigns(HouseModel):
    """Ein Wert weist immer einen vollständigen Typ zu, nie eine Ergänzung (P 8.1)."""

    wall_profile_id: Id | None
    window_type_id: Id | None
    door_type_id: Id | None
    roof_type_id: Id | None
    roof_shape_id: Id | None
    terrace_type_id: Id | None
    """Am Element `site`; ein Wert ohne Typ heißt: keine Terrasse."""
    carport_type_id: Id | None


class HouseLine(HouseModel):
    """Ausstattungslinie (Ergänzung 6, E-HM-14): setzt mehrere Slots auf ausdrückliche Wahl des Kunden auf
    einmal. Sie wird nicht gespeichert und hat keinen eigenen Preis; aktiv ist sie, solange alle ihre Werte
    gelten."""

    id: Id
    name: HouseText
    description: HouseText | None
    presets: dict[Id, HouseSlotValue]
    """Slot → globaler Wert."""
    sort_order: int


class HouseOptionValue(HouseModel):
    id: Id
    slot_id: Id
    name: HouseText
    description: HouseText | None
    assigns: HouseOptionAssigns
    available_when: HouseExpr
    """`null`: immer verfügbar. Ausgewertet je Element (P 8.2)."""
    unavailable_reason: HouseText | None
    sort_order: int


class HouseSuggestion(HouseModel):
    slot_id: Id
    option_value_id: Id
    element_ids: list[Id]
    label: HouseText


class HouseRuleSource(HouseModel):
    jurisdiction: str | None
    document: str | None
    section: str | None
    reference: str | None
    retrieved_at: str | None


class HouseRule(HouseModel):
    """Technische Regel des Katalogs (P 8.3); `when` wahr heißt: trifft zu."""

    id: Id
    scope: Literal["selection", "element", "building"]
    target: HouseSelector | None
    """Bei `element` Pflicht: für welche Elemente die Regel gilt."""
    when: HouseExpr
    outcome: Outcome
    message: HouseText
    suggestion: HouseSuggestion | None
    source: HouseRuleSource | None

    @model_validator(mode="after")
    def _target(self) -> "HouseRule":
        if (self.scope == "element") != (self.target is not None):
            raise ValueError("ein Ziel genau bei scope element")
        return self


class HousePriceEntry(HouseModel):
    """Sagt nur, was wie viel kostet (P 5.2); jeder Betrag stammt aus genau einem Eintrag (P 2.1 Nr. 11)."""

    id: Id
    target_kind: PriceTargetKind
    target_id: Id
    unit: PriceUnit
    value: Amount


class HouseOptionCondition(HouseModel):
    slot_id: Id
    option_value_id: Id


class HousePricingRule(HouseModel):
    """Sagt nur, welche Menge mit welchem Eintrag verrechnet wird (P 9.2); enthält keine Beträge."""

    id: Id
    label: HouseText
    applies_to: HouseOptionCondition | None
    """`null`: immer; sonst nur, wenn der Wert bei mindestens einem Element gilt."""
    method: Literal["per_unit", "lump_sum", "percent"]
    quantity_key: str | None
    entry_id: Id | None
    by_target: PriceTargetKind | None
    """Eintrag über die `ref_id` der Menge, z. B. eine Regel für alle Wandschichten; bei `lump_sum` nur
    `template`: der Eintrag des Haustyps (`slug`)."""
    percent_base: str | None
    """`subtotal` oder ein Mengenschlüssel; nur bei `percent`."""
    order: int

    @model_validator(mode="after")
    def _consistent(self) -> "HousePricingRule":
        if (self.entry_id is None) == (self.by_target is None):
            raise ValueError("genau eine Preisquelle: entry_id oder by_target")
        if (self.method == "per_unit") != (self.quantity_key is not None):
            raise ValueError("quantity_key genau bei per_unit")
        if (self.method == "percent") != (self.percent_base is not None):
            raise ValueError("percent_base genau bei percent")
        if self.method == "percent" and self.by_target is not None:
            raise ValueError("percent nur mit entry_id")
        if self.method == "lump_sum" and self.by_target not in (None, "template"):
            raise ValueError("lump_sum mit by_target nur für template")
        return self


class HouseCatalog(HouseModel):
    """Katalogversion eines Markts: Bauteile, Slots, Werte, Regeln und Preise in einem Dokument (E-HM-8)."""

    schema_version: Literal[2]
    market: Literal["FR"]
    currency: Literal["EUR"]
    vat_rate: Annotated[float, Field(ge=0, le=1)]
    parameters: HouseCatalogParameters
    materials: list[HouseMaterial]
    wall_layers: list[HouseWallLayer]
    wall_profiles: list[HouseWallProfile]
    window_types: list[HouseWindowType]
    door_types: list[HouseDoorType]
    roof_types: list[HouseRoofType]
    roof_shapes: list[HouseRoofShape]
    """Ohne Formen gilt immer die Form des Templates."""
    terrace_types: list[HouseTerraceType]
    carport_types: list[HouseCarportType]
    room_types: list[HouseRoomType]
    slots: list[HouseSlot]
    option_values: list[HouseOptionValue]
    lines: list[HouseLine]
    rules: list[HouseRule]
    pricing_rules: list[HousePricingRule]
    price_entries: list[HousePriceEntry]
    ignored_zone_categories: list[ZoneCategory] = Field(max_length=50)
    """Zonenkategorien ohne Raum (z. B. SDP, SHAB, Emprise au sol); gelten nur für die Quellen Typ und
    Category (3.6 Nr. 3)."""

    def zone_table(self) -> ZoneTable:
        return ZoneTable.build(
            ((room_type.id, room_type.aliases) for room_type in self.room_types), self.ignored_zone_categories
        )

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        """Schema 1 beim Lesen heben: ohne Dachformen, Linien und Nebenbauten (E-HM-58)."""
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return data
        slots = [
            {**slot, "parameter": None} if isinstance(slot, dict) else slot for slot in data.get("slots", [])
        ]
        assigns = {"roof_shape_id": None, "terrace_type_id": None, "carport_type_id": None}
        options = [
            {**option, "assigns": {**option["assigns"], **assigns}}
            if isinstance(option, dict) and isinstance(option.get("assigns"), dict)
            else option
            for option in data.get("option_values", [])
        ]
        empty: dict[str, list[Any]] = {
            "roof_shapes": [],
            "terrace_types": [],
            "carport_types": [],
            "lines": [],
        }
        return {**data, **empty, "schema_version": 2, "slots": slots, "option_values": options}

    @model_validator(mode="after")
    def _zone_table_is_unique(self) -> "HouseCatalog":
        self.zone_table()
        return self

    @model_validator(mode="after")
    def _unique_ids(self) -> "HouseCatalog":
        for kind in (
            "materials",
            "wall_layers",
            "wall_profiles",
            "window_types",
            "door_types",
            "roof_types",
            "roof_shapes",
            "terrace_types",
            "carport_types",
            "room_types",
            "slots",
            "option_values",
            "lines",
            "rules",
            "pricing_rules",
            "price_entries",
        ):
            _unique(kind, [item.id for item in getattr(self, kind)])
        return self


# --- Konfiguration (P 5.3) ------------------------------------------------------------------------------


class HouseSlotSelection(HouseModel):
    value: HouseSlotValue | None
    """Globaler Wert; `null`: der Standard des Templates, nur Überschreibungen gesetzt."""
    room_overrides: dict[Id, HouseSlotValue]
    element_overrides: dict[Id, HouseSlotValue]


class HouseConfiguration(HouseModel):
    """Nur Auswahl: keine Geometrie, keine Mengen, keine Preise (P 2 Nr. 2)."""

    selections: dict[Id, HouseSlotSelection]


# --- Ergebnis ---------------------------------------------------------------------------------------------


class HouseResolvedValue(HouseModel):
    """Wirksamer Wert: ein Wert des Katalogs oder bei Parameter-Slots eine Zahl."""

    slot_id: Id
    element_id: Id
    option_value_id: Id | None
    number: float | None
    source: Literal["element", "room", "global", "default"]
    available: bool
    """`false` nur, wenn kein Wert des Slots verfügbar ist (Fehler des Katalogs, P 2.1 Nr. 5)."""

    @model_validator(mode="after")
    def _one_value(self) -> "HouseResolvedValue":
        if (self.option_value_id is None) == (self.number is None):
            raise ValueError("genau ein Wert: option_value_id oder number")
        return self


class HouseResolutionNote(HouseModel):
    """Eine Stufe der Auflösung griff nicht (P 8.2); die Auswahl bleibt unverändert. `default_replaced`: der
    Standard ist nicht verfügbar, es gilt der erste verfügbare Wert (E-HM-60). `out_of_range`: die Zahl liegt
    außerhalb der Spanne. `roof_kind_mismatch`: der Dachaufbau passt nicht zur wirksamen Dachform (flach oder
    geneigt). `roof_not_constructible`: Form, Neigung oder Drehung lässt sich auf dem Grundriss nicht erzeugen
    (Ergänzung 4)."""

    slot_id: Id
    element_id: Id
    skipped_level: Literal["element", "room", "global", "default"]
    skipped_value_ids: list[Id]
    skipped_number: float | None
    applied_value_id: Id | None
    applied_number: float | None
    code: Literal[
        "unavailable",
        "room_override_tie",
        "out_of_range",
        "roof_kind_mismatch",
        "roof_not_constructible",
        "default_replaced",
    ]
    reason: HouseText | None
    """Text aus dem Katalog (`unavailable_reason`); sonst übersetzt die Oberfläche den Code (E-HM-33)."""


class HouseQuantity(HouseModel):
    key: str
    ref_id: str | None
    value: float
    unit: QuantityUnit
    element_ids: list[Id]


class HousePriceItem(HouseModel):
    pricing_rule_id: Id
    price_entry_id: Id
    label: HouseText
    quantity_key: str | None
    ref_id: str | None
    quantity: float
    unit: PriceUnit
    unit_price: Amount
    amount: Amount
    element_ids: list[Id]


class HousePrice(HouseModel):
    """Exakte Richtpreise für Snapshot und Dossier; der Kunde sieht nur gerundete Beträge (E-HM-2, L1)."""

    market: Literal["FR"]
    currency: Literal["EUR"]
    base_amount: Amount
    items: list[HousePriceItem]
    net_amount: Amount
    vat_rate: float
    vat_amount: Amount
    gross_amount: Amount
    deltas: dict[Id, Amount]
    """Je gewähltem Slot: Netto mit der Auswahl minus Netto mit dem Standard (P 9.1)."""
    is_estimate: Literal[True]


class HouseRuleResult(HouseModel):
    code: str
    """`catalog_rule` für Katalogregeln, sonst die Prüfung der Geometrie (z. B. `opening_outside_host`)."""
    rule_id: Id | None
    outcome: ResultOutcome
    message: HouseText | None
    element_ids: list[Id]
    suggestion: HouseSuggestion | None
    source: HouseRuleSource | None
    params: dict[str, float | str]


class HouseProfileUValue(HouseModel):
    wall_profile_id: Id
    u_value: float
    """W/(m²K) nach dem vereinfachten Verfahren (P 11)."""


class HouseWindowShare(HouseModel):
    direction: Literal["n", "e", "s", "w"]
    """Ausrichtung der Fassade im Modellnorden."""
    window_area: float
    facade_area: float
    ratio: float


class HouseEnergy(HouseModel):
    wall_u_values: list[HouseProfileUValue]
    window_shares: list[HouseWindowShare]


class HouseEdgeRole(HouseModel):
    edge: int = Field(ge=0)
    role: FacadeRole


class HouseEdgePosition(HouseModel):
    edge: int = Field(ge=0)
    position: Annotated[float, Field(ge=0, le=1)]
    """Anteil der Kantenlänge vom Kantenanfang bis zur Mitte der Öffnung."""


class HouseTerraceFacts(HouseModel):
    type_id: Id
    depth: float
    width: float | None
    """Längste Fassadenkante mit Rolle `garden`; ohne sie entsteht keine Terrasse."""
    height_above_terrain: float
    sealing_factor: float


class HouseCarportFacts(HouseModel):
    type_id: Id
    spaces: int
    width: float
    depth: float
    height: float


class HouseFacts(HouseModel):
    """Hausbeschreibung für die Prüfung auf dem Grundstück in Python (3.1, E-HM-4); ersetzt `HouseType`."""

    facade_outline: Ring
    """Außenkante der äußersten Schicht, alle oberirdischen Geschosse, gegen den Uhrzeigersinn."""
    projection_outline: Ring
    """Mit Dachüberstand (geneigt: Traufkontur)."""
    storeys: int = Field(ge=1, le=10)
    roof_shape: RoofShapeKind
    """Wirksame Dachform; welche Form einer PLU-Regel sie ist, entscheidet Python (Ergänzung 11)."""
    roof_slopes_deg: list[float]
    """Neigung je geneigter Dachfläche."""
    ridge_azimuth_deg: Annotated[float, Field(ge=0, lt=180)] | None
    """Achse des längsten Firsts im Modell (0 = Modellnord, im Uhrzeigersinn); ohne First `null`."""
    eave_height: Height
    """Flachdach: Oberkante Attika. Geneigt: Oberkante der Deckung an der niedrigsten Traufe."""
    top_height: Height
    """Höchster Punkt (Attika, First oder Dachaufbau) über ±0,00."""
    ground_floor_offset: float
    floor_area: float
    facade_roles: list[HouseEdgeRole]
    """Kanten von `facade_outline`."""
    entrance: HouseEdgePosition | None
    garage_door: HouseEdgePosition | None
    facade_material_class: MaterialClass
    roof_material_class: MaterialClass
    terrace: HouseTerraceFacts | None
    carport: HouseCarportFacts | None


class HouseCandidate(HouseModel):
    """Vorschau eines Werts vor der Wahl (P 8.2 `evaluateCandidates`); bei der Drehung des Dachs je Zahl."""

    option_value_id: Id | None
    number: float | None
    available_count: int
    target_count: int
    unavailable_reason: HouseText | None
    status: Status
    rule_results: list[HouseRuleResult]
    price_delta: Amount


def _lift_evaluation(data: dict[str, Any]) -> dict[str, Any]:
    """Auswertung des Kerns vor 0.4.0 (HM4, nur Flachdach) auf den heutigen Stand heben (E-HM-58)."""
    facts = dict(data["facts"])
    axis = facts.pop("ridge_direction", None)
    facts["roof_shape"] = facts.pop("roof_form", "flat")
    facts["ridge_azimuth_deg"] = {"x": 90.0, "y": 0.0}.get(axis) if isinstance(axis, str) else None
    facts.setdefault("terrace", None)
    facts.setdefault("carport", None)
    resolved = [{**value, "number": None} for value in data.get("resolved", [])]
    notes = [{**note, "skipped_number": None, "applied_number": None} for note in data.get("notes", [])]
    candidates = data.get("candidates")
    if isinstance(candidates, list):
        candidates = [{**candidate, "number": None} for candidate in candidates]
    return {**data, "facts": facts, "resolved": resolved, "notes": notes, "candidates": candidates}


class HouseEvaluation(HouseModel):
    domain_version: str
    status: Status
    resolved: list[HouseResolvedValue]
    notes: list[HouseResolutionNote]
    quantities: list[HouseQuantity]
    price: HousePrice
    rule_results: list[HouseRuleResult]
    energy: HouseEnergy
    facts: HouseFacts
    candidates: list[HouseCandidate] | None

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("facts"), dict) and "roof_form" in data["facts"]:
            return _lift_evaluation(data)
        return data


class HouseCandidatesRequest(HouseModel):
    slot_id: Id
    element_id: Id | None


class HouseEvaluateRequest(HouseModel):
    template: HouseTemplate
    catalog: HouseCatalog
    configuration: HouseConfiguration
    candidates: HouseCandidatesRequest | None


class HouseCompatibilityIssue(HouseModel):
    code: str
    slot_id: Id | None
    element_id: Id | None
    ref_id: str | None


class HouseCompatibility(HouseModel):
    """Prüfung Template ↔ Katalog (P 2.1 Nr. 5); die Freigabe trifft danach ein Mensch."""

    domain_version: str
    supported: bool
    issues: list[HouseCompatibilityIssue]


class HouseCompatibilityRequest(HouseModel):
    template: HouseTemplate
    catalog: HouseCatalog


# --- Dach erzeugen (`engine` `/roof`, E-HM-64) -----------------------------------------------------------


class HousePoint3(HouseModel):
    x: Coordinate
    y: Coordinate
    z: Height


class HouseRoofRequest(HouseModel):
    """Geneigtes Dach aus Form und Parametern; der IFC-Import vergleicht es mit dem Dach aus Archicad."""

    contour: Ring
    """Bezugskontur gegen den Uhrzeigersinn."""
    wall_thickness: Thickness
    bearing_height: Height
    eave_overhang: NonNegative
    verge_overhang: NonNegative
    design: HouseRoofDesign
    thickness: Thickness
    """Aufbau senkrecht zur Fläche."""


class HouseRoofFace(HouseModel):
    contour_edges: list[int]
    """Kanten der Bezugskontur, zu denen die Fläche gehört."""
    segment: int
    """Abschnitt des Kantenprofils: 0 unten, 1 über Knick- bzw. Krüppelhöhe."""
    pitch_deg: float
    polygon: list[HousePoint3]
    """Unterseite, gegen den Uhrzeigersinn von oben gesehen."""


class HouseRoofLine(HouseModel):
    kind: Literal["ridge", "hip", "valley", "eave", "verge", "break"]
    a: HousePoint3
    b: HousePoint3


class HouseRoofGeometry(HouseModel):
    outline: Ring
    """Traufkontur."""
    edge_kinds: list[Literal["eave", "gable"]]
    """Je Kante der Bezugskontur."""
    faces: list[HouseRoofFace]
    lines: list[HouseRoofLine]
    top_height: float
    eave_height: float
    ridge_azimuth_deg: float | None


CONTRACT_ROOTS: tuple[type[HouseModel], ...] = (
    HouseTemplate,
    HouseCatalog,
    HouseConfiguration,
    HouseFacts,
    HouseEvaluation,
    HouseEvaluateRequest,
    HouseCompatibility,
    HouseCompatibilityRequest,
    HouseRoofRequest,
    HouseRoofGeometry,
)
"""Wurzeln des Vertrags; was sie referenzieren, kommt mit."""


def add_contract_schemas(openapi: dict[str, Any]) -> None:
    """Nimmt den Vertrag in `components.schemas` auf, solange keine Route ihn verwendet (3.4)."""
    from pydantic.json_schema import models_json_schema

    _, schema = models_json_schema(
        [(model, "validation") for model in CONTRACT_ROOTS], ref_template="#/components/schemas/{model}"
    )
    schemas = openapi.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in schema["$defs"].items():
        if name in schemas and schemas[name] != definition:
            raise RuntimeError(f"Schema {name} gibt es schon: Vertragsmodelle beginnen mit House")
        schemas[name] = definition
    openapi["x-house-contract"] = sorted(model.__name__ for model in CONTRACT_ROOTS)
