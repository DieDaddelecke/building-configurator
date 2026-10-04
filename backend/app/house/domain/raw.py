"""Gelesenes Modell: was der IFC-Leser im Kindprozess aus der Datei holt (docs/PLAN_HAUSMODELL.md 3.6).

Alles in Metern und Weltkoordinaten der Datei, ohne Deutung: welche Wand außen liegt, welche Zone zu welchem
Raum gehört und wo die Bezugskontur verläuft, entscheidet `assemble`. So bleibt der Leser klein, und ein
Entwurf lässt sich mit den Angaben des Büros neu bilden, ohne die Datei erneut zu öffnen.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.house.domain.zones import SourceKind

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Ring2 = list[Point2]
Polygon2 = list[Ring2]
"""Außenring, danach Löcher."""


class Raw(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RawStorey(Raw):
    guid: str
    name: str
    z: float
    """Höhe der Geschossplatzierung in der Welt; Wände, Zonen und Öffnungen beziehen sich darauf."""


class RawWall(Raw):
    guid: str
    name: str
    storey_guid: str | None
    is_external: bool | None
    """`Pset_WallCommon.IsExternal`; nur zum Vergleich, außen ist, was auf dem Rand liegt (P 12.3)."""
    footprint: Polygon2
    """Grundriss des Körpers ohne Öffnungen."""
    z_min: float
    z_max: float


class RawOpening(Raw):
    guid: str
    """`GlobalId` des Fensters oder der Tür."""
    name: str
    kind: Literal["window", "door"]
    storey_guid: str | None
    host_guid: str | None
    """Wand über `IfcRelFillsElement` und `IfcRelVoidsElement`."""
    is_external: bool | None
    width: float | None
    height: float | None
    """`OverallWidth`, `OverallHeight`."""
    sill: float | None
    """Unterkante des Fensters bzw. der Tür (Platzierung) in der Welt."""
    center: Point2
    """Mitte der Öffnung im Grundriss: Wandöffnung, sonst das Bauteil selbst."""
    top: float
    """Oberkante der Wandöffnung (mit Rollladenkasten), sonst des Bauteils."""


class RawZoneSource(Raw):
    kind: SourceKind
    raw: str


class RawSpace(Raw):
    guid: str
    storey_guid: str | None
    sources: list[RawZoneSource]
    footprint: Polygon2 | None


class RawSlab(Raw):
    guid: str
    name: str
    storey_guid: str | None
    predefined_type: str | None
    footprint: Polygon2
    z_min: float
    z_max: float


class RawRoof(Raw):
    """Dach (`IfcRoof` mit Körper oder Teilen, sonst `IfcSlab` ROOF) als Dreiecksnetz in der Welt."""

    guid: str
    name: str
    storey_guid: str | None
    vertices: list[Point3]
    triangles: list[tuple[int, int, int]]


class RawModel(Raw):
    reader_version: Literal[1]
    ifc_schema: str
    application: str | None
    building_name: str | None
    ground_floor_offset: float | None
    """Eigenschaft `Emprise.GroundFloorOffset` am Gebäude (Ergänzung 1), in Metern."""
    storeys: list[RawStorey]
    walls: list[RawWall]
    openings: list[RawOpening]
    spaces: list[RawSpace]
    slabs: list[RawSlab]
    roofs: list[RawRoof]
    skipped: dict[str, int] = Field(default_factory=dict)
    """Bauteile, die der Import nicht liest, je IFC-Klasse (Importvertrag 9)."""
    failed: list[str] = Field(default_factory=list)
    """`GlobalId` der Bauteile, deren Geometrie sich nicht bilden ließ."""
