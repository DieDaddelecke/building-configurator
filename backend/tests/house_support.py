"""IFC-Dateien für die Tests des Imports (docs/PLAN_HAUSMODELL.md 6, HM3): das Demohaus aus P 19 nach dem
Importvertrag, wie Archicad es exportiert (Referenzlinie der Außenwände innen, Fenster und Türen in
Wandöffnungen, Zonenkategorie als Name des `IfcSpaceType`), und Abwandlungen für die Fehlermeldungen.

Solange die Referenz-IFC des Büros fehlt, steht diese Datei für sie; sie entsteht im Test mit IfcOpenShell.
"""

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.house.domain.roof import RoofBuilder

DOMAIN = Path(__file__).resolve().parents[2] / "packages" / "domain"
if not DOMAIN.exists():  # im Container unter /packages/domain (compose.yaml, backend-dev)
    DOMAIN = Path("/packages/domain")
FIXTURE = DOMAIN / "test" / "fixtures" / "demo-house"
PROBES = Path(__file__).resolve().parents[2] / "ifc-proben"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURE / f"{name}.json").read_text(encoding="utf-8"))
    return data


def publish_template(
    db: Any,
    catalog_version: Any,
    document: dict[str, Any],
    *,
    approved: bool = True,
    actor: str = "test",
) -> Any:
    """Veröffentlichte Templateversion mit Prüfbefund zur Katalogversion, wie nach Import, Prüfung und
    Freigabe im Büro (HM3), ohne IFC: für die Tests des Kundenwegs (HM4) und den Ende-zu-Ende-Seed. Ohne
    `approved` bleibt der Befund unbestätigt; der Haustyp wird dann nicht angeboten."""
    from sqlalchemy import func, select

    from app.house.models import HouseTemplateRecord, HouseTemplateVersion
    from app.platform.db import utcnow

    slug = document["slug"]
    record = db.scalar(select(HouseTemplateRecord).where(HouseTemplateRecord.slug == slug))
    if record is None:
        record = HouseTemplateRecord(slug=slug, created_by=actor)
        db.add(record)
        db.flush()
    number = (
        db.scalar(
            select(func.max(HouseTemplateVersion.version)).where(
                HouseTemplateVersion.template_id == record.id
            )
        )
        or 0
    ) + 1
    now = utcnow()
    version = HouseTemplateVersion(
        template_id=record.id,
        version=number,
        status="published",
        catalog_version_id=catalog_version.id,
        ifc_file_name=f"{slug}.ifc",
        ifc_sha256="0" * 64,
        ifc_key=f"house/{slug}/{number}.ifc",
        ifc_size_bytes=0,
        decisions={},
        document=document,
        reviewed_at=now,
        reviewed_by=actor,
        published_at=now,
        published_by=actor,
        created_by=actor,
    )
    db.add(version)
    db.flush()
    record.current_version_id = version.id
    approve(db, version, catalog_version, approved=approved, actor=actor)
    return version


def approve(
    db: Any, template_version: Any, catalog_version: Any, *, approved: bool = True, actor: str = "test"
) -> None:
    """Prüfbefund Template ↔ Katalog, kompatibel; mit `approved` freigegeben (HM3)."""
    from app.house.models import HouseCatalogCompatibility
    from app.platform.db import utcnow

    db.add(
        HouseCatalogCompatibility(
            template_version_id=template_version.id,
            catalog_version_id=catalog_version.id,
            domain_version="0.4.0",
            supported=True,
            issues=[],
            approved_at=utcnow() if approved else None,
            approved_by=actor if approved else None,
            created_by=actor,
        )
    )
    db.commit()


@dataclass(frozen=True)
class Opening:
    kind: str
    wall: str
    center: float
    """Abstand vom Anfang der Wand bis zur Mitte."""
    width: float
    height: float
    sill: float
    box: float = 0.0
    """Rollladenkasten: Wandöffnung um so viel höher als das Fenster."""


@dataclass(frozen=True)
class Wall:
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float
    height: float
    side: str
    """`right`: Körper rechts der Referenzlinie (Außenwand gegen den Uhrzeigersinn, Referenz innen),
    `center`: mittig."""
    external: bool


@dataclass(frozen=True)
class DemoHouse:
    """Demohaus der Testdaten: Bezugskontur 12 × 8 m, Ursprung verschoben, Flachdach mit Attika."""

    offset: tuple[float, float] = (104.25, 37.5)
    walls: dict[str, Wall] = field(
        default_factory=lambda: {
            # Außenwände gegen den Uhrzeigersinn, Referenzlinie auf der Innenseite, Ecken überlappend
            "south": Wall((-0.3, 0.0), (12.3, 0.0), 0.3, 3.0, "right", True),
            "east": Wall((12.0, -0.3), (12.0, 8.3), 0.3, 3.0, "right", True),
            "north": Wall((12.3, 8.0), (-0.3, 8.0), 0.3, 3.0, "right", True),
            "west": Wall((0.0, 8.3), (0.0, -0.3), 0.3, 3.0, "right", True),
            # Innenwände mit verschiedenen Anschlüssen: an der Fläche, an der Achse, in die Außenwand hinein
            "a": Wall((5.05, 0.0), (5.05, 8.0), 0.1, 2.5, "center", False),
            "b": Wall((5.1, 3.45), (12.15, 3.45), 0.1, 2.5, "center", False),
            "c": Wall((5.05, 4.75), (12.0, 4.75), 0.1, 2.5, "center", False),
            "d": Wall((8.55, 0.0), (8.55, 3.4), 0.1, 2.5, "center", False),
            "e": Wall((8.55, 4.8), (8.55, 8.0), 0.1, 2.5, "center", False),
        }
    )
    openings: dict[str, Opening] = field(
        default_factory=lambda: {
            "win-living-south": Opening("window", "south", 2.8, 1.2, 1.6, 0.9),
            "win-bedroom": Opening("window", "south", 7.1, 1.2, 1.6, 0.9),
            "win-child": Opening("window", "south", 10.6, 1.2, 1.6, 0.9),
            "win-bath": Opening("window", "north", 2.0, 1.2, 1.6, 0.9),
            "win-kitchen": Opening("window", "north", 5.5, 1.2, 1.6, 0.9),
            "win-living-west": Opening("window", "west", 4.3, 1.2, 1.6, 0.9),
            "door-entrance": Opening("door", "east", 4.4, 1.0, 2.1, 0.0),
            "door-living": Opening("door", "a", 4.1, 0.8, 2.1, 0.0),
            "door-bedroom": Opening("door", "b", 1.7, 0.8, 2.1, 0.0),
            "door-child": Opening("door", "b", 5.15, 0.8, 2.1, 0.0),
            "door-kitchen": Opening("door", "c", 1.75, 0.8, 2.1, 0.0),
            "door-bath": Opening("door", "c", 5.2, 0.8, 2.1, 0.0),
        }
    )
    zones: dict[str, tuple[str, list[tuple[float, float]]]] = field(
        default_factory=lambda: {
            "living": ("SEJOUR", [(0, 0), (5, 0), (5, 8), (0, 8)]),
            "bedroom": ("CHAMBRE 1", [(5.1, 0), (8.5, 0), (8.5, 3.4), (5.1, 3.4)]),
            "child": ("Chambre_02", [(8.6, 0), (12, 0), (12, 3.4), (8.6, 3.4)]),
            "hall": ("ENTREE", [(5.1, 3.5), (12, 3.5), (12, 4.7), (5.1, 4.7)]),
            "kitchen": ("Cuisine", [(5.1, 4.8), (8.5, 4.8), (8.5, 8), (5.1, 8)]),
            "bath": ("SALLE DE BAIN", [(8.6, 4.8), (12, 4.8), (12, 8), (8.6, 8)]),
        }
    )
    contour: list[tuple[float, float]] = field(default_factory=lambda: [(0, 0), (12, 0), (12, 8), (0, 8)])
    ground_slab: float | None = 0.2
    roof: str | None = "flat"
    """`flat`: Dachdecke 0,10 m auf 2,50 m; `pitched`: Satteldach 30°; `None`: kein Dach."""
    ground_floor_offset: float | None = 0.2

    def without(self, *names: str) -> "DemoHouse":
        return replace(
            self,
            walls={k: v for k, v in self.walls.items() if k not in names},
            openings={k: v for k, v in self.openings.items() if v.wall not in names},
        )


def _frame(wall: Wall) -> tuple[tuple[float, float], tuple[float, float], float]:
    (x0, y0), (x1, y1) = wall.start, wall.end
    length = math.hypot(x1 - x0, y1 - y0)
    return (x0, y0), ((x1 - x0) / length, (y1 - y0) / length), length


class IfcWriter:
    """IFC4 in Metern, wie es der Übersetzer „03 - Paramétrique (IFC4)“ ausgibt: Geschosse auf ihrer Höhe,
    Bauteile in Weltkoordinaten, Grundriss um `offset` verschoben."""

    def __init__(self, offset: tuple[float, float], ground_floor_offset: float | None) -> None:
        import ifcopenshell.api
        import ifcopenshell.api.aggregate
        import ifcopenshell.api.context
        import ifcopenshell.api.feature
        import ifcopenshell.api.geometry
        import ifcopenshell.api.project
        import ifcopenshell.api.pset
        import ifcopenshell.api.root
        import ifcopenshell.api.spatial
        import ifcopenshell.api.type
        import ifcopenshell.api.unit

        self.api = api = ifcopenshell.api
        self.f = f = api.project.create_file(version="IFC4")
        project = api.root.create_entity(f, ifc_class="IfcProject", name="Demo")
        api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})
        model = api.context.add_context(f, context_type="Model")
        self.body = api.context.add_context(
            f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model
        )
        site = api.root.create_entity(f, ifc_class="IfcSite", name="Site")
        self.building = api.root.create_entity(f, ifc_class="IfcBuilding", name="Building")
        api.aggregate.assign_object(f, products=[site], relating_object=project)
        api.aggregate.assign_object(f, products=[self.building], relating_object=site)
        for product in (site, self.building):
            api.geometry.edit_object_placement(f, product=product)
        if ground_floor_offset is not None:
            pset = api.pset.add_pset(f, product=self.building, name="Emprise")
            api.pset.edit_pset(f, pset=pset, properties={"GroundFloorOffset": ground_floor_offset})
        self.offset = offset

    def storey(self, name: str, z: float) -> Any:
        storey = self.api.root.create_entity(self.f, ifc_class="IfcBuildingStorey", name=name)
        self.api.aggregate.assign_object(self.f, products=[storey], relating_object=self.building)
        self.place(storey, (-self.offset[0], -self.offset[1]), (1.0, 0.0), z)
        return storey

    def place(
        self, product: Any, origin: tuple[float, float], direction: tuple[float, float], z: float
    ) -> None:
        import numpy as np

        dx, dy = direction
        ox, oy = self.offset
        matrix = np.array(
            [[dx, -dy, 0, origin[0] + ox], [dy, dx, 0, origin[1] + oy], [0, 0, 1, z], [0, 0, 0, 1]],
            dtype=float,
        )
        self.api.geometry.edit_object_placement(self.f, product=product, matrix=matrix)

    def box(self, product: Any, length: float, height: float, offset: float, thickness: float) -> None:
        representation = self.api.geometry.add_wall_representation(
            self.f, context=self.body, length=length, height=height, offset=offset, thickness=thickness
        )
        self.api.geometry.assign_representation(self.f, product=product, representation=representation)

    def contain(self, product: Any, storey: Any) -> None:
        self.api.spatial.assign_container(self.f, products=[product], relating_structure=storey)

    def flag(self, product: Any, pset_name: str, value: bool) -> None:
        pset = self.api.pset.add_pset(self.f, product=product, name=pset_name)
        self.api.pset.edit_pset(self.f, pset=pset, properties={"IsExternal": value})

    def wall(self, storey: Any, wall: Wall, z: float) -> Any:
        element = self.api.root.create_entity(
            self.f, ifc_class="IfcWall", name="MUR_EXT" if wall.external else "CLOISON"
        )
        origin, direction, length = _frame(wall)
        self.place(element, origin, direction, z)
        offset = -wall.thickness if wall.side == "right" else -wall.thickness / 2
        self.box(element, length, wall.height, offset, wall.thickness)
        self.contain(element, storey)
        self.flag(element, "Pset_WallCommon", wall.external)
        return element

    def opening(self, storey: Any, host: Any, wall: Wall, name: str, opening: Opening, z: float) -> None:
        """Wandöffnung (mit Rollladenkasten höher als das Bauteil) und Fenster bzw. Tür darin."""
        origin, direction, _ = _frame(wall)
        start = (
            origin[0] + direction[0] * (opening.center - opening.width / 2),
            origin[1] + direction[1] * (opening.center - opening.width / 2),
        )
        offset = -wall.thickness if wall.side == "right" else -wall.thickness / 2
        void = self.api.root.create_entity(self.f, ifc_class="IfcOpeningElement", name=name)
        self.place(void, start, direction, z + opening.sill)
        self.box(void, opening.width, opening.height + opening.box, offset - 0.01, wall.thickness + 0.02)
        self.api.feature.add_feature(self.f, feature=void, element=host)
        cls = "IfcWindow" if opening.kind == "window" else "IfcDoor"
        element = self.api.root.create_entity(self.f, ifc_class=cls, name=name)
        element.OverallWidth = opening.width
        element.OverallHeight = opening.height
        self.place(element, start, direction, z + opening.sill)
        self.box(element, opening.width, opening.height, offset + wall.thickness / 2 - 0.03, 0.06)
        self.contain(element, storey)
        self.api.feature.add_filling(self.f, opening=void, element=element)
        pset = "Pset_WindowCommon" if opening.kind == "window" else "Pset_DoorCommon"
        self.flag(element, pset, wall.external)

    def zone(self, storey: Any, category: str, polygon: list[tuple[float, float]], z: float) -> None:
        """Zone mit der Kategorie als Name des `IfcSpaceType` und dem Zonennamen „SDP“ (Probedateien)."""
        api, f = self.api, self.f
        space = api.root.create_entity(f, ifc_class="IfcSpace", name="", predefined_type="INTERNAL")
        space.LongName = "SDP"
        self.place(space, (0.0, 0.0), (1.0, 0.0), z)
        representation = api.geometry.add_slab_representation(
            f, context=self.body, depth=2.5, polyline=polygon
        )
        api.geometry.assign_representation(f, product=space, representation=representation)
        space_type = api.root.create_entity(
            f, ifc_class="IfcSpaceType", name=category, predefined_type="INTERNAL"
        )
        api.type.assign_type(f, related_objects=[space], relating_type=space_type)
        api.aggregate.assign_object(f, products=[space], relating_object=storey)

    def slab(
        self,
        storey: Any,
        polygon: list[tuple[float, float]],
        z_bottom: float,
        thickness: float,
        ifc_class: str,
    ) -> None:
        """Platte mit Unterkante `z_bottom`: `IfcSlab` FLOOR oder Flachdach als `IfcRoof`."""
        api, f = self.api, self.f
        if ifc_class == "IfcRoof":
            element = api.root.create_entity(
                f, ifc_class="IfcRoof", name="TOITURE", predefined_type="FLAT_ROOF"
            )
        else:
            element = api.root.create_entity(f, ifc_class="IfcSlab", name="DALLE", predefined_type="FLOOR")
        self.place(element, (0.0, 0.0), (1.0, 0.0), z_bottom)
        representation = api.geometry.add_slab_representation(
            f, context=self.body, depth=thickness, polyline=polygon
        )
        api.geometry.assign_representation(f, product=element, representation=representation)
        self.contain(element, storey)

    def roof_mesh(
        self, storey: Any, vertices: list[tuple[float, float, float]], faces: list[list[int]]
    ) -> None:
        api, f = self.api, self.f
        roof = api.root.create_entity(f, ifc_class="IfcRoof", name="TOITURE", predefined_type="FREEFORM")
        self.place(roof, (0.0, 0.0), (1.0, 0.0), 0.0)
        representation = api.geometry.add_mesh_representation(
            f, context=self.body, vertices=[vertices], faces=[faces]
        )
        api.geometry.assign_representation(f, product=roof, representation=representation)
        self.contain(roof, storey)

    def write(self, path: Path) -> Path:
        self.f.write(str(path))
        return path


def write_ifc(house: DemoHouse, path: Path) -> Path:
    """Schreibt das Demohaus als IFC4 in Metern, wie es der Übersetzer „03 - Paramétrique (IFC4)“ ausgibt."""
    writer = IfcWriter(house.offset, house.ground_floor_offset)
    storey = writer.storey("RDC", 0.0)
    walls = {name: writer.wall(storey, wall, 0.0) for name, wall in house.walls.items()}
    for name, opening in house.openings.items():
        writer.opening(storey, walls[opening.wall], house.walls[opening.wall], name, opening, 0.0)
    for category, polygon in house.zones.values():
        writer.zone(storey, category, polygon, 0.0)
    if house.ground_slab is not None:
        writer.slab(storey, house.contour, -house.ground_slab, house.ground_slab, "IfcSlab")
    if house.roof == "flat":
        writer.slab(storey, house.contour, 2.5, 0.1, "IfcRoof")
    elif house.roof == "pitched":
        # Satteldach mit flacher Unterseite: kein Dach, das der Kern erzeugt
        rise = 4.3 * math.tan(math.radians(30))
        vertices = [
            (-0.3, -0.3, 3.0),
            (12.3, -0.3, 3.0),
            (12.3, 8.3, 3.0),
            (-0.3, 8.3, 3.0),
            (-0.3, 4.0, 3.0 + rise),
            (12.3, 4.0, 3.0 + rise),
        ]
        faces = [[0, 1, 5, 4], [2, 3, 4, 5], [1, 2, 5], [3, 0, 4], [0, 3, 2, 1]]
        writer.roof_mesh(storey, vertices, faces)
    return writer.write(path)


def roof_mesh(geometry: dict[str, Any]) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Dachkörper aus einem Dach des Kerns (`HouseRoofGeometry`): je Fläche die Unterseite mit Normale nach
    unten und darüber dieselbe Fläche, um 0,30 m angehoben, mit Normale nach oben."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []
    for face in geometry["faces"]:
        lift = 0.3 / math.cos(math.radians(face["pitch_deg"]))
        points = [(p["x"], p["y"], p["z"]) for p in face["polygon"]]
        start = len(vertices)
        vertices += points + [(x, y, z + lift) for x, y, z in points]
        count = len(points)
        faces.append([start + i for i in reversed(range(count))])
        faces.append([start + count + i for i in range(count)])
    return vertices, faces


def write_template_ifc(
    template: dict[str, Any],
    catalog: dict[str, Any],
    path: Path,
    *,
    roof: dict[str, Any] | None = None,
    wall: float = 0.3,
    offset: tuple[float, float] = (104.25, 37.5),
) -> Path:
    """Template der Testdaten als IFC nach dem Importvertrag: je Geschoss Außenwände `wall` dick außen an der
    Bezugskontur (an ausspringenden Ecken überlappend), Innenwände auf ihren Achsen, Öffnungen mit den Maßen
    ihrer Standardtypen, Zonen mit dem ersten Alias ihres Raumtyps, Bodenplatte und Decken. Das Dach ist das
    Netz eines Dachs des Kerns (`roof`, aus `roofs.json`) oder, beim Flachdach, die Dachdecke."""
    writer = IfcWriter(offset, template["ground_floor_offset"])
    levels = {level["id"]: level for level in template["levels"]}
    storeys = {level["id"]: writer.storey(level["name"], level["elevation"]) for level in template["levels"]}
    elevations = sorted(level["elevation"] for level in template["levels"])
    placement = template["roof"]
    flat = placement["design"]["form"] == "flat"
    slabs = {s["kind"]: s for s in template["slabs"]}
    top = placement["bearing_height"] + (
        slabs["roof"]["thickness"] + placement["parapet_height"] if flat else 0.0
    )

    # Host → Wand, ihre Maße, Geschoss und Weg vom Anfang der Wand bis zum Anfang des Hosts
    hosts: dict[str, tuple[Any, Wall, str, float]] = {}
    for loop in template["envelope"]:
        level = loop["level_id"]
        z = levels[level]["elevation"]
        above = [e for e in elevations if e > z + 1e-9]
        height = (above[0] if above else top) - z
        points = [(p["x"], p["y"]) for p in loop["inner_polygon"]]
        n = len(points)
        convex = [
            (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) > 0
            for a, b, c in ((points[i - 1], points[i], points[(i + 1) % n]) for i in range(n))
        ]
        for i, segment in enumerate(loop["segments"]):
            a, b = points[i], points[(i + 1) % n]
            length = math.dist(a, b)
            d = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
            before = wall if convex[i] else 0.0
            after = wall if convex[(i + 1) % n] else 0.0
            data = Wall(
                (a[0] - d[0] * before, a[1] - d[1] * before),
                (b[0] + d[0] * after, b[1] + d[1] * after),
                wall,
                height,
                "right",
                True,
            )
            hosts[segment["id"]] = (writer.wall(storeys[level], data, z), data, level, before)
    for interior in template["interior_walls"]:
        level = interior["level_id"]
        a, b = ((p["x"], p["y"]) for p in interior["axis"])
        data = Wall(a, b, interior["thickness"], 2.5, "center", False)
        hosts[interior["id"]] = (
            writer.wall(storeys[level], data, levels[level]["elevation"]),
            data,
            level,
            0.0,
        )

    options = {o["id"]: o["assigns"] for o in catalog["option_values"]}
    windows = {t["id"]: t for t in catalog["window_types"]}
    doors = {t["id"]: t for t in catalog["door_types"]}
    for item in template["openings"]:
        element, data, level, before = hosts[item["host_id"]]
        slot = (
            "window_type"
            if item["kind"] == "window"
            else "entrance_door"
            if item["host_kind"] == "envelope_segment"
            else "interior_door"
        )
        value = template["element_defaults"].get(item["id"], {}).get(slot, template["defaults"][slot])
        center = item["offset_along_host"] + before
        if item["kind"] == "window":
            t = windows[options[value]["window_type_id"]]
            opening = Opening(
                "window",
                "",
                center,
                t["width"],
                t["height"],
                t["head_height"] - t["height"],
                t["shutter_box_height"],
            )
        else:
            t = doors[options[value]["door_type_id"]]
            opening = Opening("door", "", center, t["width"], t["height"], 0.0)
        writer.opening(storeys[level], element, data, item["id"], opening, levels[level]["elevation"])

    aliases = {t["id"]: t["aliases"][0] for t in catalog["room_types"]}
    for room in template["rooms"]:
        polygon = [(p["x"], p["y"]) for p in room["polygon"]]
        writer.zone(
            storeys[room["level_id"]],
            aliases[room["room_type_id"]],
            polygon,
            levels[room["level_id"]]["elevation"],
        )

    contour = [(p["x"], p["y"]) for p in template["envelope"][0]["inner_polygon"]]
    for slab in template["slabs"]:
        z = levels[slab["level_id"]]["elevation"]
        if slab["kind"] == "ground":
            writer.slab(storeys[slab["level_id"]], contour, -slab["thickness"], slab["thickness"], "IfcSlab")
        elif slab["kind"] == "floor":
            writer.slab(
                storeys[slab["level_id"]], contour, z - slab["thickness"], slab["thickness"], "IfcSlab"
            )
        else:
            writer.slab(
                storeys[slab["level_id"]], contour, placement["bearing_height"], slab["thickness"], "IfcRoof"
            )
    if roof is not None:
        vertices, faces = roof_mesh(roof)
        writer.roof_mesh(storeys[template["levels"][-1]["id"]], vertices, faces)
    return writer.write(path)


def canonical(template: dict[str, Any]) -> dict[str, Any]:
    """Template ohne Kennungen: Elemente über ihre Geometrie und die Höhe ihres Geschosses, auf 1 mm gerundet
    (P 20.3)."""

    def mm(value: float) -> float:
        return round(value, 3) + 0.0

    def ring(points: list[dict[str, float]]) -> tuple[tuple[float, float], ...]:
        return tuple((mm(p["x"]), mm(p["y"])) for p in points)

    height = {level["id"]: mm(level["elevation"]) for level in template["levels"]}
    rooms = {
        r["id"]: (height[r["level_id"]], r["room_type_id"], ring(r["polygon"])) for r in template["rooms"]
    }
    loops = template["envelope"]
    segments = {
        s["id"]: (height[loop["level_id"]], i) for loop in loops for i, s in enumerate(loop["segments"])
    }
    walls = {
        w["id"]: (
            (height[w["level_id"]], ring(w["axis"])),
            mm(w["thickness"]),
            tuple(sorted(rooms[r] for r in w["adjacent_room_ids"])),
        )
        for w in template["interior_walls"]
    }

    def opening_key(opening: dict[str, Any]) -> tuple[Any, ...]:
        host = (
            segments[opening["host_id"]]
            if opening["host_kind"] == "envelope_segment"
            else walls[opening["host_id"]][0]
        )
        return (
            opening["kind"],
            opening["host_kind"],
            host,
            mm(opening["offset_along_host"]),
            tuple(sorted(rooms[r] for r in opening["adjacent_room_ids"])),
        )

    openings = {o["id"]: opening_key(o) for o in template["openings"]}
    roof = template["roof"]
    return {
        "levels": [(level["name"], mm(level["elevation"])) for level in template["levels"]],
        "ground_floor_offset": mm(template["ground_floor_offset"]),
        "inner_polygon": [ring(loop["inner_polygon"]) for loop in loops],
        "facade_roles": [[s["facade_role"] for s in loop["segments"]] for loop in loops],
        "interior_walls": sorted(walls.values()),
        "openings": sorted(openings.values()),
        "rooms": sorted(rooms.values()),
        "slabs": sorted((height[s["level_id"]], s["kind"], mm(s["thickness"])) for s in template["slabs"]),
        "roof": {**{k: mm(v) for k, v in roof.items() if k != "design"}, "design": roof["design"]},
        "entrance": openings.get(template["entrance_opening_id"]),
        "garage_door": openings.get(template["garage_door_opening_id"]),
        "defaults": template["defaults"],
        "element_defaults": sorted((openings[k], v) for k, v in template["element_defaults"].items()),
    }


def roofs() -> dict[str, Any]:
    """Dächer des Kerns für die Proben aller Dachformen (`packages/domain/scripts/roofs.ts`)."""
    return fixture("roofs")


def kernel_roofs(data: dict[str, Any] | None = None) -> "RoofBuilder":
    """Ersatz für `engine /roof` in den Tests: Antworten aus `roofs.json`. Fehlt eine, hat der Import anders
    gefragt als erwartet; dann `pnpm run roofs` prüfen."""
    from app.house.contract import HouseRoofGeometry, HouseRoofRequest

    def key(request: dict[str, Any]) -> str:
        return json.dumps(HouseRoofRequest.model_validate(request).model_dump(mode="json"), sort_keys=True)

    answers = {key(a["request"]): a for a in (data or roofs())["answers"]}

    def build(request: HouseRoofRequest) -> HouseRoofGeometry | str:
        found = answers.get(key(request.model_dump(mode="json")))
        assert found is not None, f"Antwort des Kerns fehlt in roofs.json: {request.model_dump_json()}"
        if found["geometry"] is None:
            return str(found["rejection"]["detail"].get("reason", found["rejection"]["code"]))
        return HouseRoofGeometry.model_validate(found["geometry"])

    return build
