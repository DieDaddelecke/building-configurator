"""IFC lesen, nur im Kindprozess (docs/PLAN_HAUSMODELL.md 3.6, E-HM-19); gestartet über `ifc_process`.

IfcOpenShell ist C++; eine fehlerhafte Datei kann abstürzen oder Speicher fressen. Deshalb lädt nur der
Kindprozess die Bibliothek, mit Speicher- und Zeitgrenze aus `ifc_process`. Ausgabe auf stdout: das gelesene
Modell (`RawModel`) als JSON, Rückgabewert 0. Eine Datei, die sich nicht öffnen lässt, meldet `{"error": …}`
mit Rückgabewert 3; alles andere endet mit einem anderen Rückgabewert und Text auf stderr.

Gelesen wird über IFC-Semantik (P 12.1): Wände, Fenster und Türen mit ihren Öffnungen, Zonen, Platten, Dächer.
Geometrie liefert IfcOpenShell in Metern und Weltkoordinaten; Grundrisse sind die Projektion des Körpers.
"""

import json
import sys
from collections import Counter
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
import ifcopenshell.util.unit as uu
import numpy as np
from shapely import Polygon, unary_union
from shapely.geometry.base import BaseGeometry

from app.house.domain.raw import (
    Polygon2,
    RawModel,
    RawOpening,
    RawRoof,
    RawSlab,
    RawSpace,
    RawStorey,
    RawWall,
    RawZoneSource,
)
from app.house.ifc_process import EXIT_UNREADABLE

SCHEMAS = ("IFC2X3", "IFC4", "IFC4X3_ADD2")
READ = ("IfcWall", "IfcWindow", "IfcDoor", "IfcSpace", "IfcSlab", "IfcRoof", "IfcOpeningElement")
NOT_COUNTED = (
    "IfcSpatialElement",
    "IfcSpatialStructureElement",
    "IfcVirtualElement",
    "IfcAnnotation",
    "IfcGrid",
)


class Reader:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.scale = float(uu.calculate_unit_scale(model))
        self.settings = ifcopenshell.geom.settings()
        self.settings.set("use-world-coords", True)
        self.settings.set("disable-opening-subtractions", True)
        self.failed: list[str] = []

    # --- Geometrie --------------------------------------------------------------------------------------

    def mesh(self, element: Any) -> tuple[np.ndarray, np.ndarray] | None:
        if not getattr(element, "Representation", None):
            return None
        try:
            shape: Any = ifcopenshell.geom.create_shape(self.settings, element)
        except Exception:
            self.failed.append(element.GlobalId)
            return None
        vertices = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        triangles = np.asarray(shape.geometry.faces, dtype=int).reshape(-1, 3)
        if not len(triangles):
            return None
        return vertices, triangles

    @staticmethod
    def footprint(vertices: np.ndarray, triangles: np.ndarray) -> BaseGeometry:
        flat = np.round(vertices[:, :2], 5)
        pieces = []
        for a, b, c in triangles:
            triangle = Polygon([flat[a], flat[b], flat[c]])
            if triangle.area > 1e-9:
                pieces.append(triangle)
        return unary_union(pieces).buffer(0) if pieces else Polygon()

    @staticmethod
    def polygon(geometry: BaseGeometry) -> Polygon2 | None:
        """Größter Teil als Außenring mit Löchern, auf 0,01 mm gerundet."""
        parts = list(getattr(geometry, "geoms", [geometry]))
        parts = [p for p in parts if isinstance(p, Polygon) and not p.is_empty]
        if not parts:
            return None
        largest = max(parts, key=lambda p: p.area)

        def ring(coords: Any) -> list[tuple[float, float]]:
            return [(round(x, 5), round(y, 5)) for x, y in list(coords)[:-1]]

        return [ring(largest.exterior.coords), *(ring(hole.coords) for hole in largest.interiors)]

    def outline(self, element: Any) -> tuple[Polygon2 | None, float, float]:
        found = self.mesh(element)
        if found is None:
            return None, 0.0, 0.0
        vertices, triangles = found
        return (
            self.polygon(self.footprint(vertices, triangles)),
            float(vertices[:, 2].min()),
            float(vertices[:, 2].max()),
        )

    # --- Bezüge -----------------------------------------------------------------------------------------

    @staticmethod
    def storey(element: Any) -> Any:
        current = element
        for _ in range(10):
            parent = ue.get_container(current) or ue.get_aggregate(current)
            if parent is None:
                return None
            if parent.is_a("IfcBuildingStorey"):
                return parent
            current = parent
        return None

    def storey_guid(self, element: Any) -> str | None:
        found = self.storey(element)
        return str(found.GlobalId) if found is not None else None

    @staticmethod
    def flag(element: Any, pset: str, name: str) -> bool | None:
        value = ue.get_psets(element).get(pset, {}).get(name)
        return value if isinstance(value, bool) else None

    def z(self, element: Any) -> float:
        matrix = up.get_local_placement(element.ObjectPlacement)
        return float(matrix[2][3]) * self.scale

    def length(self, value: Any) -> float | None:
        return float(value) * self.scale if isinstance(value, int | float) else None

    # --- Bauteile ---------------------------------------------------------------------------------------

    def storeys(self) -> list[RawStorey]:
        return [
            RawStorey(guid=s.GlobalId, name=s.Name or "", z=self.z(s))
            for s in self.model.by_type("IfcBuildingStorey")
        ]

    def walls(self) -> list[RawWall]:
        walls = []
        for wall in self.model.by_type("IfcWall"):
            footprint, z_min, z_max = self.outline(wall)
            if footprint is None:
                continue
            walls.append(
                RawWall(
                    guid=wall.GlobalId,
                    name=wall.Name or "",
                    storey_guid=self.storey_guid(wall),
                    is_external=self.flag(wall, "Pset_WallCommon", "IsExternal"),
                    footprint=footprint,
                    z_min=z_min,
                    z_max=z_max,
                )
            )
        return walls

    def openings(self) -> list[RawOpening]:
        openings = []
        for element in [*self.model.by_type("IfcWindow"), *self.model.by_type("IfcDoor")]:
            kind = "window" if element.is_a("IfcWindow") else "door"
            void = next((rel.RelatingOpeningElement for rel in element.FillsVoids or []), None)
            host = None
            if void is not None and void.VoidsElements:
                host = void.VoidsElements[0].RelatingBuildingElement
            source = void if void is not None and getattr(void, "Representation", None) else element
            found = self.mesh(source)
            if found is None:
                continue
            vertices, triangles = found
            shape = self.footprint(vertices, triangles)
            if shape.is_empty:
                continue
            pset = "Pset_WindowCommon" if kind == "window" else "Pset_DoorCommon"
            openings.append(
                RawOpening(
                    guid=element.GlobalId,
                    name=element.Name or "",
                    kind=kind,
                    storey_guid=self.storey_guid(element),
                    host_guid=host.GlobalId if host is not None and host.is_a("IfcWall") else None,
                    is_external=self.flag(element, pset, "IsExternal"),
                    width=self.length(element.OverallWidth),
                    height=self.length(element.OverallHeight),
                    sill=self.z(element) if element.ObjectPlacement else None,
                    center=(round(shape.centroid.x, 5), round(shape.centroid.y, 5)),
                    top=float(vertices[:, 2].max()),
                )
            )
        return openings

    @staticmethod
    def zone_sources(space: Any) -> list[RawZoneSource]:
        """Quellen der Zonenkategorie in der Reihenfolge von 3.6 Nr. 1."""
        values: list[tuple[str, Any]] = []
        space_type = ue.get_type(space)
        values.append(("type", space_type.Name if space_type is not None else None))
        values.append(("category", ue.get_psets(space).get("Pset_SpaceCommon", {}).get("Category")))
        values += [("object_type", space.ObjectType), ("long_name", space.LongName), ("name", space.Name)]
        for rel in getattr(space, "HasAssociations", None) or []:
            if rel.is_a("IfcRelAssociatesClassification"):
                reference = rel.RelatingClassification
                values.append(("classification", getattr(reference, "Name", None)))
                for attribute in ("Identification", "ItemReference"):
                    if hasattr(reference, attribute):
                        values.append(("classification", getattr(reference, attribute)))
        return [
            RawZoneSource(kind=kind, raw=value) for kind, value in values if isinstance(value, str) and value
        ]

    def spaces(self) -> list[RawSpace]:
        spaces = []
        for space in self.model.by_type("IfcSpace"):
            footprint, _, _ = self.outline(space)
            spaces.append(
                RawSpace(
                    guid=space.GlobalId,
                    storey_guid=self.storey_guid(space),
                    sources=self.zone_sources(space),
                    footprint=footprint,
                )
            )
        return spaces

    def roof_parts(self) -> set[str]:
        return {
            part.GlobalId
            for roof in self.model.by_type("IfcRoof")
            for rel in roof.IsDecomposedBy or []
            for part in rel.RelatedObjects
        }

    def slabs(self, parts: set[str]) -> list[RawSlab]:
        slabs = []
        for slab in self.model.by_type("IfcSlab"):
            if slab.GlobalId in parts or slab.PredefinedType == "ROOF":
                continue
            footprint, z_min, z_max = self.outline(slab)
            if footprint is None:
                continue
            slabs.append(
                RawSlab(
                    guid=slab.GlobalId,
                    name=slab.Name or "",
                    storey_guid=self.storey_guid(slab),
                    predefined_type=slab.PredefinedType,
                    footprint=footprint,
                    z_min=z_min,
                    z_max=z_max,
                )
            )
        return slabs

    def roofs(self, parts: set[str]) -> list[RawRoof]:
        roofs = []
        elements = [*self.model.by_type("IfcRoof")]
        elements += [
            s for s in self.model.by_type("IfcSlab") if s.PredefinedType == "ROOF" and s.GlobalId not in parts
        ]
        for roof in elements:
            pieces = [roof]
            if roof.is_a("IfcRoof") and not getattr(roof, "Representation", None):
                pieces = [part for rel in roof.IsDecomposedBy or [] for part in rel.RelatedObjects]
            vertices: list[tuple[float, float, float]] = []
            triangles: list[tuple[int, int, int]] = []
            for piece in pieces:
                found = self.mesh(piece)
                if found is None:
                    continue
                offset = len(vertices)
                vertices += [(round(x, 5), round(y, 5), round(z, 5)) for x, y, z in found[0].tolist()]
                triangles += [(a + offset, b + offset, c + offset) for a, b, c in found[1].tolist()]
            if triangles:
                roofs.append(
                    RawRoof(
                        guid=roof.GlobalId,
                        name=roof.Name or "",
                        storey_guid=self.storey_guid(roof),
                        vertices=vertices,
                        triangles=triangles,
                    )
                )
        return roofs

    def skipped(self, parts: set[str]) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for product in self.model.by_type("IfcProduct"):
            if any(product.is_a(cls) for cls in (*READ, *NOT_COUNTED)) or product.GlobalId in parts:
                continue
            counts[product.is_a()] += 1
        return dict(sorted(counts.items()))

    def ground_floor_offset(self) -> float | None:
        """`Emprise.GroundFloorOffset` am Gebäude; eine Länge in Projekteinheiten, eine Zahl in Metern."""
        for building in self.model.by_type("IfcBuilding"):
            for definition in getattr(building, "IsDefinedBy", None) or []:
                pset = getattr(definition, "RelatingPropertyDefinition", None)
                if pset is None or not pset.is_a("IfcPropertySet") or pset.Name != "Emprise":
                    continue
                for prop in pset.HasProperties:
                    if prop.Name == "GroundFloorOffset" and prop.is_a("IfcPropertySingleValue"):
                        value = prop.NominalValue
                        if value is None or not isinstance(value.wrappedValue, int | float):
                            return None
                        scale = self.scale if value.is_a("IfcLengthMeasure") else 1.0
                        return float(value.wrappedValue) * scale
        return None

    def read(self) -> RawModel:
        parts = self.roof_parts()
        buildings = self.model.by_type("IfcBuilding")
        header = self.model.header.file_name
        model = RawModel(
            reader_version=1,
            ifc_schema=self.model.schema,
            application=str(header.originating_system) or None,
            building_name=buildings[0].Name if buildings else None,
            ground_floor_offset=self.ground_floor_offset(),
            storeys=self.storeys(),
            walls=self.walls(),
            openings=self.openings(),
            spaces=self.spaces(),
            slabs=self.slabs(parts),
            roofs=self.roofs(parts),
            skipped=self.skipped(parts),
        )
        return model.model_copy(update={"failed": sorted(set(self.failed))})


def main(argv: list[str]) -> int:
    try:
        model = ifcopenshell.open(argv[1])
    except Exception as exc:
        # IfcOpenShell meldet ein unbekanntes Schema (z. B. IFC2X2) beim Öffnen
        code = "schema_unsupported" if "unsupported schema" in str(exc).lower() else "file_unreadable"
        print(json.dumps({"error": code, "detail": str(exc)[:300]}))
        return EXIT_UNREADABLE
    if model.schema not in SCHEMAS:
        print(json.dumps({"error": "schema_unsupported", "detail": str(model.schema)}))
        return EXIT_UNREADABLE
    print(Reader(model).read().model_dump_json())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
