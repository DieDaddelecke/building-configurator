"""IFC-Dateien für die Tests des Imports (docs/PLAN_HAUSMODELL.md 6, HM3): das Demohaus aus P 19 nach dem
Importvertrag, wie Archicad es exportiert (Referenzlinie der Außenwände innen, Fenster und Türen in
Wandöffnungen, Zonenkategorie als Name des `IfcSpaceType`), und Abwandlungen für die Fehlermeldungen.

Solange die Referenz-IFC des Büros fehlt, steht diese Datei für sie; sie entsteht im Test mit IfcOpenShell.
"""

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

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
            domain_version="0.3.0",
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


def write_ifc(house: DemoHouse, path: Path) -> Path:
    """Schreibt das Haus als IFC4 in Metern, wie es der Übersetzer „03 - Paramétrique (IFC4)“ ausgibt."""
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
    import numpy as np

    api = ifcopenshell.api
    f = api.project.create_file(version="IFC4")
    project = api.root.create_entity(f, ifc_class="IfcProject", name="Demo")
    api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})
    model = api.context.add_context(f, context_type="Model")
    body = api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model
    )
    site = api.root.create_entity(f, ifc_class="IfcSite", name="Site")
    building = api.root.create_entity(f, ifc_class="IfcBuilding", name="Building")
    storey = api.root.create_entity(f, ifc_class="IfcBuildingStorey", name="RDC")
    api.aggregate.assign_object(f, products=[site], relating_object=project)
    api.aggregate.assign_object(f, products=[building], relating_object=site)
    api.aggregate.assign_object(f, products=[storey], relating_object=building)
    for product in (site, building, storey):
        api.geometry.edit_object_placement(f, product=product)
    if house.ground_floor_offset is not None:
        pset = api.pset.add_pset(f, product=building, name="Emprise")
        api.pset.edit_pset(f, pset=pset, properties={"GroundFloorOffset": house.ground_floor_offset})
    ox, oy = house.offset

    def place(product: Any, origin: tuple[float, float], direction: tuple[float, float], z: float) -> None:
        dx, dy = direction
        matrix = np.array(
            [[dx, -dy, 0, origin[0] + ox], [dy, dx, 0, origin[1] + oy], [0, 0, 1, z], [0, 0, 0, 1]],
            dtype=float,
        )
        api.geometry.edit_object_placement(f, product=product, matrix=matrix)

    def box(product: Any, length: float, height: float, offset: float, thickness: float) -> None:
        representation = api.geometry.add_wall_representation(
            f, context=body, length=length, height=height, offset=offset, thickness=thickness
        )
        api.geometry.assign_representation(f, product=product, representation=representation)

    def contain(product: Any) -> None:
        api.spatial.assign_container(f, products=[product], relating_structure=storey)

    def flag(product: Any, pset_name: str, value: bool) -> None:
        pset = api.pset.add_pset(f, product=product, name=pset_name)
        api.pset.edit_pset(f, pset=pset, properties={"IsExternal": value})

    walls = {}
    for name, wall in house.walls.items():
        element = api.root.create_entity(
            f, ifc_class="IfcWall", name="MUR_EXT" if wall.external else "CLOISON"
        )
        origin, direction, length = _frame(wall)
        place(element, origin, direction, 0.0)
        offset = -wall.thickness if wall.side == "right" else -wall.thickness / 2
        box(element, length, wall.height, offset, wall.thickness)
        contain(element)
        flag(element, "Pset_WallCommon", wall.external)
        walls[name] = element

    for name, opening in house.openings.items():
        wall = house.walls[opening.wall]
        origin, direction, _ = _frame(wall)
        start = (
            origin[0] + direction[0] * (opening.center - opening.width / 2),
            origin[1] + direction[1] * (opening.center - opening.width / 2),
        )
        offset = -wall.thickness if wall.side == "right" else -wall.thickness / 2
        void = api.root.create_entity(f, ifc_class="IfcOpeningElement", name=name)
        place(void, start, direction, opening.sill)
        box(void, opening.width, opening.height + opening.box, offset - 0.01, wall.thickness + 0.02)
        api.feature.add_feature(f, feature=void, element=walls[opening.wall])
        cls = "IfcWindow" if opening.kind == "window" else "IfcDoor"
        element = api.root.create_entity(f, ifc_class=cls, name=name)
        element.OverallWidth = opening.width
        element.OverallHeight = opening.height
        place(element, start, direction, opening.sill)
        box(element, opening.width, opening.height, offset + wall.thickness / 2 - 0.03, 0.06)
        contain(element)
        api.feature.add_filling(f, opening=void, element=element)
        flag(element, "Pset_WindowCommon" if opening.kind == "window" else "Pset_DoorCommon", wall.external)

    for category, polygon in house.zones.values():
        space = api.root.create_entity(f, ifc_class="IfcSpace", name="", predefined_type="INTERNAL")
        space.LongName = "SDP"
        place(space, (0.0, 0.0), (1.0, 0.0), 0.0)
        representation = api.geometry.add_slab_representation(f, context=body, depth=2.5, polyline=polygon)
        api.geometry.assign_representation(f, product=space, representation=representation)
        space_type = api.root.create_entity(
            f, ifc_class="IfcSpaceType", name=category, predefined_type="INTERNAL"
        )
        api.type.assign_type(f, related_objects=[space], relating_type=space_type)
        api.aggregate.assign_object(f, products=[space], relating_object=storey)

    if house.ground_slab is not None:
        slab = api.root.create_entity(f, ifc_class="IfcSlab", name="DALLE", predefined_type="FLOOR")
        place(slab, (0.0, 0.0), (1.0, 0.0), -house.ground_slab)
        representation = api.geometry.add_slab_representation(
            f, context=body, depth=house.ground_slab, polyline=house.contour
        )
        api.geometry.assign_representation(f, product=slab, representation=representation)
        contain(slab)

    if house.roof is not None:
        roof = api.root.create_entity(f, ifc_class="IfcRoof", name="TOITURE", predefined_type="FLAT_ROOF")
        if house.roof == "flat":
            place(roof, (0.0, 0.0), (1.0, 0.0), 2.5)
            representation = api.geometry.add_slab_representation(
                f, context=body, depth=0.1, polyline=house.contour
            )
        else:
            place(roof, (0.0, 0.0), (1.0, 0.0), 0.0)
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
            representation = api.geometry.add_mesh_representation(
                f, context=body, vertices=[vertices], faces=[faces]
            )
        api.geometry.assign_representation(f, product=roof, representation=representation)
        contain(roof)

    f.write(str(path))
    return path


def canonical(template: dict[str, Any]) -> dict[str, Any]:
    """Template ohne Kennungen: Elemente über ihre Geometrie, auf 1 mm gerundet (P 20.3)."""

    def mm(value: float) -> float:
        return round(value, 3) + 0.0

    def ring(points: list[dict[str, float]]) -> tuple[tuple[float, float], ...]:
        return tuple((mm(p["x"]), mm(p["y"])) for p in points)

    rooms = {r["id"]: (r["room_type_id"], ring(r["polygon"])) for r in template["rooms"]}
    loop = template["envelope"][0]
    segments = {s["id"]: i for i, s in enumerate(loop["segments"])}
    walls = {
        w["id"]: (
            ring(w["axis"]),
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
    return {
        "levels": [(level["name"], mm(level["elevation"])) for level in template["levels"]],
        "ground_floor_offset": mm(template["ground_floor_offset"]),
        "inner_polygon": ring(loop["inner_polygon"]),
        "facade_roles": [s["facade_role"] for s in loop["segments"]],
        "interior_walls": sorted(walls.values()),
        "openings": sorted(openings.values()),
        "rooms": sorted(rooms.values()),
        "slabs": sorted((s["kind"], mm(s["thickness"])) for s in template["slabs"]),
        "roof": {k: mm(v) for k, v in template["roof"].items()},
        "entrance": openings.get(template["entrance_opening_id"]),
        "garage_door": openings.get(template["garage_door_opening_id"]),
        "defaults": template["defaults"],
        "element_defaults": sorted((openings[k], v) for k, v in template["element_defaults"].items()),
    }
