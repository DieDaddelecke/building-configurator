"""Entwurf eines Haustyps: Angaben des Büros und Importbericht (docs/PLAN_HAUSMODELL.md 3.6 Nr. 5, P 12.4).

Der Entwurf entsteht immer neu aus dem gelesenen Modell und den Angaben (`assemble`); so bleibt er
nachvollziehbar, und eine Angabe lässt sich zurücknehmen, ohne die Datei erneut zu lesen.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.house.contract import FacadeRole, HouseRoofPlacement, HouseText
from app.house.domain.zones import SourceKind

IGNORE = "ignore"
"""Angabe für Zonen und Räume ohne Raumtyp."""
Key = Annotated[str, Field(min_length=1, max_length=80)]


class HouseDoorChoice(BaseModel):
    """Vom Büro gesetzt; `opening_id` null heißt ausdrücklich keine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opening_id: Key | None


class HouseDraftDecisions(BaseModel):
    """Was das Büro im Entwurf bestätigt oder ergänzt; ohne Angabe gilt der Vorschlag des Imports."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: HouseText | None
    ground_floor_offset: Annotated[float, Field(ge=-5, le=5)] | None
    """±0,00 über Gelände; ohne Angabe aus `Emprise.GroundFloorOffset`, sonst 0,20 m (E-HM-11)."""
    zone_types: dict[Key, Key]
    """Zone (`GlobalId`) → Raumtyp oder `ignore`; geht der Erkennung vor."""
    room_types: dict[Key, Key]
    """Raum ohne Zone → Raumtyp oder `ignore`."""
    confirmed_splits: list[Key] = Field(max_length=200)
    """Räume mit mehreren Zonen verschiedener Typen, deren Teilung entlang der Zonen das Büro bestätigt
    hat."""
    facade_roles: dict[Key, FacadeRole]
    """Hüllensegment → Rolle (E-HM-13)."""
    entrance: HouseDoorChoice | None
    garage_door: HouseDoorChoice | None
    defaults: dict[Key, Key]
    """Slot → Wert; ohne Angabe der häufigste erkannte Wert, sonst der erste des Slots."""
    element_defaults: dict[Key, dict[Key, Key]]
    """Öffnung → Slot → Wert, für Öffnungen ohne eindeutigen Typ im Katalog (E-HM-37)."""
    roof: HouseRoofPlacement | None
    """Geneigtes Dach statt des Dachs aus dem IFC, wenn der Import die Form nicht erkennt oder das Büro sie
    anders will (E-HM-65). Ein Flachdach braucht die Dachdecke aus dem IFC und lässt sich nicht setzen."""

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        """Angaben aus HM3 und HM4 kennen das Dach nicht."""
        if isinstance(data, dict) and "roof" not in data:
            return {**data, "roof": None}
        return data

    @field_validator("roof")
    @classmethod
    def _pitched(cls, value: HouseRoofPlacement | None) -> HouseRoofPlacement | None:
        if value is not None and value.design.form == "flat":
            raise ValueError("Im Entwurf nur ein geneigtes Dach")
        return value


EMPTY_DECISIONS = HouseDraftDecisions(
    name=None,
    ground_floor_offset=None,
    zone_types={},
    room_types={},
    confirmed_splits=[],
    facade_roles={},
    entrance=None,
    garage_door=None,
    defaults={},
    element_defaults={},
    roof=None,
)

Severity = Literal["error", "open", "warning", "info"]
"""`error`: nur mit einer neuen Datei zu beheben; `open`: im Entwurf zu klären; beide verhindern die
Veröffentlichung."""

FINDING_CODES: tuple[str, ...] = (
    # Datei lesen (`ifc_process.READ_ERRORS`, letzter Versuch des Jobs)
    "file_unreadable",
    "schema_unsupported",
    "reader_timeout",
    "reader_limit",
    "reader_failed",
    "import_failed",
    # Geschosse und Bauteile
    "no_storey",
    "roof_level",
    "element_without_storey",
    "geometry_failed",
    "elements_not_read",
    # Wände und Bezugskontur
    "envelope_not_closed",
    "wall_disconnected",
    "wall_not_straight",
    "is_external_mismatch",
    "small_area_ignored",
    # Zonen und Räume
    "zone_type_conflict",
    "zone_without_geometry",
    "zone_outside_rooms",
    "zone_outdated",
    "zone_unrecognized",
    "room_ignored",
    "room_without_zone",
    "room_split_failed",
    "room_split_unconfirmed",
    # Öffnungen und Außentüren
    "opening_without_host",
    "opening_host_by_geometry",
    "opening_in_ignored_room",
    "opening_without_room",
    "opening_outside_host",
    "opening_type_unmatched",
    "opening_type_ambiguous",
    "entrance_missing",
    "entrance_ambiguous",
    "garage_door_ambiguous",
    # Geschosse, Platten und Dach
    "storey_contour_differs",
    "ground_slab_missing",
    "ground_slab_offset",
    "ground_slab_area_mismatch",
    "floor_slab_missing",
    "floor_slab_offset",
    "roof_missing",
    "roof_multiple",
    "roof_form_not_recognized",
    "roof_incomplete",
    "roof_set_by_office",
    # Angaben und Entwurf
    "decision_invalid",
    "ground_floor_offset_invalid",
    "ground_floor_offset_default",
    "facade_roles_missing",
    "template_not_built",
    "template_invalid",
)
"""Alle Befundcodes des Imports. Die Oberfläche übersetzt sie (`house.finding.<code>`, E-HM-33); die OpenAPI
nennt sie unter `x-codes`, Tests gleichen Code, Liste und Texte ab. `code` bleibt ein String, damit
gespeicherte Berichte lesbar bleiben, wenn ein Code wegfällt."""


class HouseImportFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Severity
    code: str = Field(json_schema_extra={"x-codes": list(FINDING_CODES)})
    element_id: str | None
    """Element des Entwurfs, das die Vorschau hervorhebt."""
    ifc_guid: str | None
    params: dict[str, str | float | None]


class HouseImportZoneSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    raw: str


class HouseImportZone(BaseModel):
    """Je Zone Quelle, Rohwert und Ergebnis (3.6); keine geht still verloren."""

    model_config = ConfigDict(frozen=True)

    ifc_guid: str
    result: Literal["room", "ignored", "unrecognized"]
    room_type_id: str | None
    source: SourceKind | Literal["office"] | None
    raw: str | None
    values: list[HouseImportZoneSource]
    room_id: str | None
    share: float | None
    """Anteil der Zone im zugeordneten Raum."""


class HouseImportOpening(BaseModel):
    """Maße aus dem IFC und der Typ, den der Import im Katalog dafür gefunden hat."""

    model_config = ConfigDict(frozen=True)

    element_id: str
    ifc_guid: str
    kind: Literal["window", "door"]
    width: float | None
    height: float | None
    head_height: float | None
    shutter_box_height: float
    slot_id: str | None
    option_value_id: str | None
    source: Literal["catalog", "office"] | None


class HouseImportSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    storeys: int
    roof_levels: int
    exterior_walls: int
    interior_walls: int
    windows: int
    doors: int
    rooms: int
    zones: int
    inner_width: float | None
    inner_depth: float | None
    inner_area: float | None


class HouseImportReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: list[HouseImportFinding]
    zones: list[HouseImportZone]
    openings: list[HouseImportOpening]
    summary: HouseImportSummary
    publishable: bool
    """Kein Fehler und nichts offen; die Kompatibilitätsprüfung folgt beim Prüfen."""
