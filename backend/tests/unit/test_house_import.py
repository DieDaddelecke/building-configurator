"""IFC-Import (docs/PLAN_HAUSMODELL.md 3.6, Abnahme HM3 und HM5): Leser im Kindprozess und Zusammenbau des
Entwurfs.

Referenz-IFC → Template gleich den Testdaten (1 mm, P 20.3); fehlerhafte Dateien → erwartete Meldungen;
Probedateien 1 und 2 vollständig erkannt; jede Dachform aus einer Probe erkannt, ein Typ R+1 gleich den
Testdaten (HM5). Statt `engine /roof` antworten die gespeicherten Dächer des Kerns (`roofs.json`).
Solange die Referenz-IFC des Büros fehlt, steht das Demohaus aus `tests/house_support.py` dafür; liegt sie
als `ifc-proben/demohaus_referenz.ifc` vor, gilt derselbe Vergleich auch für sie. Probedateien liegen nur
lokal (`ifc-proben/.gitignore`); ohne sie werden die Tests übersprungen.
"""

import ast
import functools
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.house.contract import HouseCatalog, HouseRoofGeometry, HouseSourceIfc, HouseTemplate, HouseText
from app.house.domain import assemble as assemble_module
from app.house.domain.assemble import assemble
from app.house.domain.draft import (
    EMPTY_DECISIONS,
    FINDING_CODES,
    HouseDoorChoice,
    HouseDraftDecisions,
    HouseImportReport,
)
from app.house.domain.raw import RawModel
from app.house.domain.roof import RoofBuilder
from app.house.ifc_process import READ_ERRORS, IfcReadError, read_failure, read_ifc
from tests.house_support import (
    PROBES,
    DemoHouse,
    Opening,
    canonical,
    fixture,
    kernel_roofs,
    roofs,
    write_ifc,
    write_template_ifc,
)

Point3 = tuple[float, float, float]
Move = Callable[[dict[str, Any], Point3], Point3]

LIMITS: dict[str, Any] = {"timeout_seconds": 120, "max_memory_bytes": 1024**3}
CATALOG_DOCUMENT = fixture("catalog")
CATALOG = HouseCatalog.model_validate(CATALOG_DOCUMENT)
KERNEL = kernel_roofs()
ROOF_PROBES = {p["name"]: p for p in roofs()["probes"]}
SOURCE = HouseSourceIfc(
    file_name="demo.ifc", sha256="0" * 64, ifc_schema="IFC4", imported_at=datetime(2026, 10, 4, tzinfo=UTC)
)
ROLES = ["street", "side_right", "garden", "side_left"]
"""Fassadenrollen der Testdaten in der Reihenfolge der Bezugskontur (Süd, Ost, Nord, West)."""
NAME = HouseText(fr="Maison de démonstration", de="Demohaus")
HEADER = (
    "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n"
    "FILE_NAME('leer.ifc','2026-10-04T00:00:00',(''),(''),'','','');\nFILE_SCHEMA(('{schema}'));\nENDSEC;\n"
    "DATA;\nENDSEC;\nEND-ISO-10303-21;\n"
)


def _read(house: DemoHouse, directory: Path) -> RawModel:
    return read_ifc(write_ifc(house, directory / "haus.ifc"), **LIMITS)


def _assemble(
    raw: RawModel, decisions: HouseDraftDecisions = EMPTY_DECISIONS, build: RoofBuilder = KERNEL
) -> tuple[HouseTemplate | None, HouseImportReport]:
    return assemble(raw, decisions, CATALOG, SOURCE, "demo_house", "Demo", build)


def _decide(**changes: Any) -> HouseDraftDecisions:
    return EMPTY_DECISIONS.model_copy(update=changes)


def _codes(report: HouseImportReport, *severities: str) -> list[str]:
    return [f.code for f in report.findings if not severities or f.severity in severities]


def _with_roles(raw: RawModel, **changes: Any) -> tuple[HouseTemplate | None, HouseImportReport]:
    """Zweiter Durchgang wie im Entwurf: Fassadenrollen zu den Segmenten des ersten."""
    template, _ = _assemble(raw, _decide(**changes))
    assert template is not None
    segments = [s.id for s in template.envelope[0].segments]
    roles = dict(zip(segments, ROLES, strict=True))
    return _assemble(raw, _decide(facade_roles=roles, **changes))


@pytest.fixture(scope="module")
def demo_raw(tmp_path_factory: pytest.TempPathFactory) -> RawModel:
    return _read(DemoHouse(), tmp_path_factory.mktemp("demo"))


def _variant(tmp_path: Path, **changes: Any) -> RawModel:
    return _read(replace(DemoHouse(), **changes), tmp_path)


# --- Template gleich den Testdaten ------------------------------------------------------------------------


def test_demo_ifc_gives_the_fixture_template(demo_raw: RawModel) -> None:
    template, report = _with_roles(demo_raw, name=NAME)
    assert template is not None
    assert report.findings == []
    assert report.publishable
    assert canonical(template.model_dump(mode="json")) == canonical(fixture("template"))
    assert template.source_ifc == SOURCE
    guids = {w.guid for w in demo_raw.walls} | {o.guid for o in demo_raw.openings}
    assert all(w.source_ifc_guid in guids for w in template.interior_walls)
    assert {o.id for o in template.openings} == {
        f"{'win' if o.kind == 'window' else 'door'}-{o.guid}" for o in demo_raw.openings
    }
    assert report.summary.model_dump() == {
        "storeys": 1,
        "roof_levels": 0,
        "exterior_walls": 4,
        "interior_walls": 5,
        "windows": 6,
        "doors": 6,
        "rooms": 6,
        "zones": 6,
        "inner_width": 12.0,
        "inner_depth": 8.0,
        "inner_area": 96.0,
    }


def test_import_is_stable(demo_raw: RawModel) -> None:
    """Gleiche Datei, gleicher Entwurf: Kennungen aus den `GlobalId`, keine Zufallswerte."""
    first, _ = _with_roles(demo_raw)
    second, _ = _with_roles(demo_raw)
    assert first == second


def test_draft_proposes_what_it_recognizes(demo_raw: RawModel) -> None:
    template, report = _assemble(demo_raw)
    assert template is not None
    assert _codes(report) == ["facade_roles_missing"]
    assert report.publishable, "eine Warnung hindert die Veröffentlichung nicht"
    entrance = next(o for o in template.openings if o.id == template.entrance_opening_id)
    hall = next(r for r in template.rooms if r.id in entrance.adjacent_room_ids)
    assert hall.room_type_id == "corridor"
    assert {z.source for z in report.zones} == {"type"}
    assert all(z.result == "room" and z.room_id and z.share == 1.0 for z in report.zones)
    assert {o.source for o in report.openings} == {"catalog"}


@pytest.mark.skipif(not (PROBES / "demohaus_referenz.ifc").exists(), reason="Referenz-IFC des Büros fehlt")
def test_reference_ifc_of_the_office_gives_the_fixture_template() -> None:
    raw = read_ifc(PROBES / "demohaus_referenz.ifc", **LIMITS)
    template, report = _with_roles(raw, name=NAME)
    assert template is not None, _codes(report)
    assert _codes(report, "error", "open") == []
    assert canonical(template.model_dump(mode="json")) == canonical(fixture("template"))


# --- Probedateien des Büros -------------------------------------------------------------------------------


PROBE_ROOMS = ["bathroom", "bedroom", "bedroom", "corridor", "living"]


@functools.cache
def _probe_file(name: str) -> RawModel:
    path = PROBES / name
    if not path.exists():
        pytest.skip(f"Probedatei {name} fehlt (nur lokal)")
    return read_ifc(path, **LIMITS)


@pytest.mark.parametrize("name", ["test_building_1_ifc.ifc", "test_building_2_ifc.ifc"])
def test_probe_files_recognize_every_zone(name: str) -> None:
    raw = _probe_file(name)
    template, report = _assemble(raw)
    assert template is not None
    assert len(report.zones) == len(raw.spaces) == 5
    assert all(z.result == "room" and z.source == "type" and z.room_id for z in report.zones)
    assert sorted(r.room_type_id for r in template.rooms) == PROBE_ROOMS
    unrecognized = {"zone_unrecognized", "zone_outside_rooms", "room_without_zone", "zone_without_geometry"}
    assert not unrecognized & set(_codes(report))


# --- Fehlerhafte Dateien ----------------------------------------------------------------------------------


def test_random_bytes_are_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "zufall.ifc"
    path.write_bytes(os.urandom(4000))
    with pytest.raises(IfcReadError) as caught:
        read_ifc(path, **LIMITS)
    assert caught.value.code == "file_unreadable"


def test_unknown_schema_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "alt.ifc"
    path.write_text(HEADER.format(schema="IFC2X2_FINAL"), encoding="ascii")
    with pytest.raises(IfcReadError) as caught:
        read_ifc(path, **LIMITS)
    assert caught.value.code == "schema_unsupported"


def test_file_without_building_has_no_storey(tmp_path: Path) -> None:
    path = tmp_path / "leer.ifc"
    path.write_text(HEADER.format(schema="IFC4"), encoding="ascii")
    template, report = _assemble(read_ifc(path, **LIMITS))
    assert template is None
    assert _codes(report, "error") == ["no_storey"]
    assert not report.publishable


def test_reader_limits_end_only_the_child(tmp_path: Path) -> None:
    path = write_ifc(DemoHouse(), tmp_path / "haus.ifc")
    with pytest.raises(IfcReadError) as slow:
        read_ifc(path, timeout_seconds=0.2, max_memory_bytes=1024**3)
    assert slow.value.code == "reader_timeout"
    # Weit unter dem Bedarf (IfcOpenShell mit numpy: lokal 200 bis 300 MB); wo es scheitert, ist Zufall
    with pytest.raises(IfcReadError) as small:
        read_ifc(path, timeout_seconds=120, max_memory_bytes=100 * 1024**2)
    assert small.value.code == "reader_limit", small.value.detail


@pytest.mark.parametrize(
    ("returncode", "stderr", "code"),
    [
        (-6, "", "reader_limit"),  # Abbruch per Signal, z. B. nach std::bad_alloc
        (1, "MemoryError", "reader_limit"),
        (1, "OpenBLAS error: Memory allocation still failed after 10 retries, giving up.", "reader_limit"),
        (1, "ImportError: libTKFillet.so.7.8: failed to map segment from shared object", "reader_limit"),
        (1, "Traceback …\nValueError: kaputt", "reader_failed"),
        (1, "", "reader_failed"),
    ],
)
def test_reader_failure_tells_the_memory_limit_apart(returncode: int, stderr: str, code: str) -> None:
    failure = read_failure(returncode, stderr)
    assert failure.code == code
    assert failure.detail == (stderr.splitlines()[-1] if stderr else f"Rückgabewert {returncode}")


def test_cut_file_reports_failed_geometry(tmp_path: Path) -> None:
    data = write_ifc(DemoHouse(), tmp_path / "haus.ifc").read_bytes()
    path = tmp_path / "halb.ifc"
    path.write_bytes(data[: len(data) // 2])
    template, report = _assemble(read_ifc(path, **LIMITS))
    assert "geometry_failed" in _codes(report, "warning")
    assert template is None or not report.publishable


@pytest.mark.parametrize(
    ("changes", "severity", "code"),
    [
        ({"roof": None}, "error", "roof_missing"),
        ({"roof": "pitched"}, "open", "roof_form_not_recognized"),
        ({"ground_slab": None}, "error", "ground_slab_missing"),
        ({"ground_floor_offset": None}, "info", "ground_floor_offset_default"),
    ],
)
def test_missing_parts_are_reported(
    tmp_path: Path, changes: dict[str, Any], severity: str, code: str
) -> None:
    template, report = _assemble(_variant(tmp_path, **changes))
    assert code in _codes(report, severity)
    if severity in ("error", "open"):
        assert not report.publishable
    if code == "roof_form_not_recognized":
        # Satteldach mit waagerechter Unterseite: keine Traufe, die der Kern so erzeugt
        finding = next(f for f in report.findings if f.code == code)
        assert finding.params == {"reason": "no_eave", "slopes": "0°"}
    if code == "ground_floor_offset_default":
        assert template is not None
        assert template.ground_floor_offset == 0.2


def test_open_envelope_is_an_error(tmp_path: Path) -> None:
    """Ohne Ostwand liegen Innenwände auf dem Rand; sie umschließen Wohnen, Schlafen und Küche getrennt."""
    template, report = _assemble(_read(DemoHouse().without("east"), tmp_path))
    assert template is None
    assert [(f.severity, f.code, f.params) for f in report.findings] == [
        ("error", "envelope_not_closed", {"areas": 3.0})
    ]


# --- Geschosse und Dach (HM5) -----------------------------------------------------------------------------


def _probe_template(request: dict[str, Any]) -> dict[str, Any]:
    """Was `write_template_ifc` braucht: ein Geschoss mit der Kontur und dem Dach einer Probe, ein Raum,
    keine Öffnungen."""
    contour = request["contour"]
    return {
        "ground_floor_offset": 0.2,
        "levels": [{"id": "rdc", "name": "RDC", "elevation": 0.0}],
        "envelope": [
            {
                "level_id": "rdc",
                "inner_polygon": contour,
                "segments": [{"id": f"seg-{i}"} for i in range(len(contour))],
            }
        ],
        "interior_walls": [],
        "openings": [],
        "slabs": [{"level_id": "rdc", "kind": "ground", "thickness": 0.2}],
        "roof": _placement(request),
        "rooms": [{"level_id": "rdc", "room_type_id": "living", "polygon": contour}],
    }


def _placement(request: dict[str, Any]) -> dict[str, Any]:
    keys = ("bearing_height", "eave_overhang", "verge_overhang", "design")
    return {"parapet_height": 0.0} | {k: request[k] for k in keys}


def _probe_raw(name: str, directory: Path, move: Move | None = None) -> RawModel:
    """IFC mit dem Dach einer Probe als Platzhalter; `move` verschiebt die Punkte einer Fläche des Dachs."""
    probe = ROOF_PROBES[name]
    geometry = probe["geometry"]
    if move is not None:
        faces = [
            f
            | {
                "polygon": [
                    dict(zip("xyz", move(f, (p["x"], p["y"], p["z"])), strict=True)) for p in f["polygon"]
                ]
            }
            for f in geometry["faces"]
        ]
        geometry = geometry | {"faces": faces}
    path = write_template_ifc(
        _probe_template(probe["request"]), CATALOG_DOCUMENT, directory / f"{name}.ifc", roof=geometry
    )
    return read_ifc(path, **LIMITS)


def _roof_findings(report: HouseImportReport) -> list[tuple[str, str, dict[str, str | float]]]:
    return [(f.severity, f.code, f.params) for f in report.findings if f.code.startswith("roof")]


@pytest.mark.parametrize("name", list(ROOF_PROBES))
def test_every_roof_form_is_recognized(tmp_path: Path, name: str) -> None:
    """Abnahme HM5: jede Form der Ergänzung 11 auf Rechteck und L-Grundriss aus dem Platzhalter im IFC
    erkannt; der Kern erzeugt dasselbe Dach (E-HM-65)."""
    request = ROOF_PROBES[name]["request"]
    template, report = _assemble(_probe_raw(name, tmp_path))
    assert template is not None
    assert _roof_findings(report) == []
    assert template.roof.model_dump(mode="json") == _placement(request)
    shapes = {s.id: s.form for s in CATALOG.roof_shapes}
    shape = next(
        o.assigns.roof_shape_id for o in CATALOG.option_values if o.id == template.defaults["roof_shape"]
    )
    assert shape is not None and shapes[shape] == request["design"]["form"], (
        "Standard der Dachform nach dem Dach"
    )
    assert template.defaults["roof_type"] == "roof.tiles"


def test_two_storey_type_gives_the_fixture_template(tmp_path: Path) -> None:
    """Abnahme HM5: ein Typ R+1 aus IFC gleich den Testdaten, Satteldach als Platzhalter, Decke über dem RDC,
    Fassadenrollen vom Erdgeschoss übernommen (E-HM-63)."""
    expected = fixture("template-r1")
    roof = ROOF_PROBES["rectangle-gable"]["geometry"]
    raw = read_ifc(write_template_ifc(expected, CATALOG_DOCUMENT, tmp_path / "r1.ifc", roof=roof), **LIMITS)
    template, report = _with_roles(raw)
    assert template is not None
    assert report.findings == []
    assert report.publishable
    assert canonical(template.model_dump(mode="json")) == canonical(expected)
    assert (report.summary.storeys, report.summary.rooms) == (2, 8)


def test_probe_file_2_has_a_hip_roof() -> None:
    """Probedatei 2 aus Archicad: Walmdach 20° auf dem L-Grundriss, Dachkörper als ein `IfcRoof`."""
    raw = _probe_file("test_building_2_ifc.ifc")
    template, report = _assemble(raw)
    assert template is not None
    # Das Dach steht in einem eigenen Geschoss „R+1“ ohne Wände: Dachgeschoss, kein Wohngeschoss
    assert _roof_findings(report) == [("info", "roof_level", {"name": "R+1"})]
    hip = {"form": "hip", "pitch_deg": 20.0, "upper_pitch_deg": None, "break_height": None, "rotation": 0}
    assert template.roof.model_dump(mode="json") == {
        "bearing_height": 3.77,
        "parapet_height": 0.0,
        "eave_overhang": 0.5,
        "verge_overhang": 0.5,
        "design": hip,
    }


def _flared(face: dict[str, Any], point: Point3) -> Point3:
    """Ortgang an der Traufe 0,20 m weiter außen als am First: Ebenen und Überstände in der Mitte gleich."""
    x, y, z = point
    if z < 6.0 and not 0 <= x <= 10:
        return (x - 0.2 if x < 0 else x + 0.2, y, z)
    return point


@pytest.mark.parametrize(
    ("move", "params"),
    [
        (lambda face, p: (p[0] + 30.0, p[1], p[2]), {"reason": "contour_not_covered"}),
        (
            lambda face, p: (p[0], p[1], p[2] + 0.1) if face["contour_edges"] == [2] else p,
            {"reason": "eave_heights_differ", "spread": 0.1},
        ),
        (lambda face, p: (p[0] + 0.1, p[1], p[2]), {"reason": "overhangs_differ"}),
        (_flared, {"reason": "shape_differs", "distance": 0.2}),
    ],
)
def test_roof_unlike_the_kernel_is_open(tmp_path: Path, move: Move, params: dict[str, str | float]) -> None:
    """Ein Dach, das der Kern so nicht erzeugt, ist nicht erkannt: offen, bis das Büro es setzt (E-HM-65)."""
    template, report = _assemble(_probe_raw("rectangle-gable", tmp_path, move))
    assert template is not None
    assert _roof_findings(report) == [("open", "roof_form_not_recognized", params | {"slopes": "35°"})]
    assert not report.publishable
    assert template.roof.design.form == "flat", "Platzhalter bis zur Angabe des Büros"


def test_roof_the_kernel_refuses_or_builds_otherwise_is_open(tmp_path: Path) -> None:
    raw = _probe_raw("rectangle-gable", tmp_path)
    _, refused = _assemble(raw, build=lambda request: "gables_adjacent")
    assert _roof_findings(refused) == [
        (
            "open",
            "roof_form_not_recognized",
            {"reason": "not_constructible", "slopes": "35°", "refusal": "gables_adjacent"},
        )
    ]
    turned = HouseRoofGeometry.model_validate(ROOF_PROBES["rectangle-gable-90"]["geometry"])
    _, other = _assemble(raw, build=lambda request: turned)
    assert _roof_findings(other) == [
        ("open", "roof_form_not_recognized", {"reason": "edges_differ", "slopes": "35°"})
    ]


ROOF = {
    "bearing_height": 3.0,
    "parapet_height": 0.0,
    "eave_overhang": 0.5,
    "verge_overhang": 0.3,
    "design": {
        "form": "gable",
        "pitch_deg": 30.0,
        "upper_pitch_deg": None,
        "break_height": None,
        "rotation": 0,
    },
}


def test_office_sets_a_pitched_roof(tmp_path: Path) -> None:
    """Das Büro setzt ein geneigtes Dach, wenn der Import es nicht erkennt oder es anders will; dann zählt
    das Dach im IFC nicht. Ein Flachdach braucht die Dachdecke aus dem IFC (E-HM-65)."""
    decisions = HouseDraftDecisions.model_validate(EMPTY_DECISIONS.model_dump() | {"roof": ROOF})
    raw = _variant(tmp_path, roof="pitched")
    template, report = _assemble(raw, decisions)
    assert template is not None
    assert _roof_findings(report) == [("info", "roof_set_by_office", {"form": "gable"})]
    assert template.roof.model_dump(mode="json") == ROOF
    assert [s.kind for s in template.slabs] == ["ground"]
    assert (template.defaults["roof_shape"], template.defaults["roof_type"]) == ("shape.gable", "roof.tiles")
    _, without = _assemble(_variant(tmp_path, roof=None), decisions)
    assert "roof_missing" not in _codes(without)
    flat = ROOF | {
        "design": {"form": "flat", "pitch_deg": None, "upper_pitch_deg": None, "break_height": None}
    }
    with pytest.raises(ValidationError):
        HouseDraftDecisions.model_validate(EMPTY_DECISIONS.model_dump() | {"roof": flat})


def test_older_decisions_are_lifted() -> None:
    """Angaben aus HM3 und HM4 kennen das Dach nicht (E-HM-58)."""
    stored = EMPTY_DECISIONS.model_dump(mode="json")
    stored.pop("roof")
    assert HouseDraftDecisions.model_validate(stored) == EMPTY_DECISIONS


def test_upper_storey_needs_a_floor_and_the_same_contour(tmp_path: Path) -> None:
    """E-HM-63: unter jedem Obergeschoss eine Decke, alle Geschosse auf der Bezugskontur des Erdgeschosses."""
    r1 = fixture("template-r1")
    roof = ROOF_PROBES["rectangle-gable"]["geometry"]
    no_floor = r1 | {"slabs": [s for s in r1["slabs"] if s["kind"] != "floor"]}
    path = write_template_ifc(no_floor, CATALOG_DOCUMENT, tmp_path / "ohne_decke.ifc", roof=roof)
    _, report = _assemble(read_ifc(path, **LIMITS))
    assert [(f.code, f.params) for f in report.findings if f.severity == "error"] == [
        ("floor_slab_missing", {"name": "R+1"})
    ]

    wider = [{"x": p["x"], "y": 8.5 if p["y"] == 8 else p["y"]} for p in r1["envelope"][1]["inner_polygon"]]
    envelope = [r1["envelope"][0], r1["envelope"][1] | {"inner_polygon": wider}]
    path = write_template_ifc(
        r1 | {"envelope": envelope}, CATALOG_DOCUMENT, tmp_path / "breiter.ifc", roof=roof
    )
    _, report = _assemble(read_ifc(path, **LIMITS))
    assert ("storey_contour_differs", {"name": "R+1"}) in [
        (f.code, f.params) for f in report.findings if f.severity == "error"
    ]
    assert not report.publishable


# --- Zonen und Räume im Entwurf ---------------------------------------------------------------------------


Zones = dict[str, tuple[str, list[tuple[float, float]]]]


def _zones(**changes: tuple[str, list[tuple[float, float]]] | None) -> Zones:
    zones = dict(DemoHouse().zones)
    for key, value in changes.items():
        if value is None:
            zones.pop(key)
        else:
            zones[key] = value
    return zones


def test_unrecognized_zone_is_open_until_the_office_decides(tmp_path: Path) -> None:
    raw = _variant(tmp_path, zones=_zones(bath=("BUANDERIE", DemoHouse().zones["bath"][1])))
    template, report = _assemble(raw)
    assert template is not None
    assert _codes(report, "open") == ["zone_unrecognized"]
    zone = next(z for z in report.zones if z.result == "unrecognized")
    assert zone.raw is None and [v.raw for v in zone.values] == ["BUANDERIE", "SDP"]
    assert "unassigned" in {r.room_type_id for r in template.rooms}

    decided, report = _assemble(raw, _decide(zone_types={zone.ifc_guid: "bathroom"}))
    assert decided is not None
    assert _codes(report, "open") == []
    assert next(z for z in report.zones if z.ifc_guid == zone.ifc_guid).source == "office"
    assert sorted(r.room_type_id for r in decided.rooms) == sorted(
        r["room_type_id"] for r in fixture("template")["rooms"]
    )

    _, invalid = _assemble(raw, _decide(zone_types={zone.ifc_guid: "garage"}))
    assert "decision_invalid" in _codes(invalid, "open")


def test_zone_of_an_ignored_category_leaves_the_room_open(tmp_path: Path) -> None:
    raw = _variant(tmp_path, zones=_zones(child=("SDP", DemoHouse().zones["child"][1])))
    _, report = _assemble(raw)
    assert [z.result for z in report.zones].count("ignored") == 1
    assert _codes(report, "open") == ["room_without_zone"]
    finding = next(f for f in report.findings if f.code == "room_without_zone")
    assert finding.element_id == "room-0-x860-y0"
    decided, report = _assemble(raw, _decide(room_types={"room-0-x860-y0": "bedroom"}))
    assert decided is not None and _codes(report, "open") == []
    ignored, report = _assemble(raw, _decide(room_types={"room-0-x860-y0": "ignore"}))
    assert ignored is not None
    assert len(ignored.rooms) == 5
    # Fenster und Tür des ignorierten Raums brauchen einen Raum: offen, bis das Büro entscheidet
    assert set(_codes(report, "open")) == {"opening_in_ignored_room"}


def test_zone_outside_every_room_is_an_error(tmp_path: Path) -> None:
    outside = ("CHAMBRE", [(13.0, 0.0), (15.0, 0.0), (15.0, 2.0), (13.0, 2.0)])
    _, report = _assemble(_variant(tmp_path, zones=_zones(garden=outside)))
    assert "zone_outside_rooms" in _codes(report, "error")
    assert not report.publishable


def test_zone_not_updated_after_moving_walls_warns(tmp_path: Path) -> None:
    stale = ("CUISINE", [(5.1, 4.8), (8.3, 4.8), (8.3, 8.0), (5.1, 8.0)])
    template, report = _assemble(_variant(tmp_path, zones=_zones(kitchen=stale)))
    assert template is not None
    assert _codes(report, "warning") == ["zone_outdated", "facade_roles_missing"]
    finding = next(f for f in report.findings if f.code == "zone_outdated")
    assert finding.params["deviation"] == pytest.approx(0.0588, abs=1e-3)
    kitchen = next(r for r in template.rooms if r.room_type_id == "kitchen")
    assert [(p.x, p.y) for p in kitchen.polygon] == [(5.1, 4.8), (8.5, 4.8), (8.5, 8.0), (5.1, 8.0)]


def test_open_kitchen_is_split_along_its_zones_after_confirmation(tmp_path: Path) -> None:
    zones = _zones(
        living=("SEJOUR", [(0, 0), (5, 0), (5, 5), (0, 5)]),
        open_kitchen=("CUISINE", [(0, 5), (5, 5), (5, 8), (0, 8)]),
    )
    raw = _variant(tmp_path, zones=zones)
    template, report = _assemble(raw)
    assert template is not None
    assert _codes(report, "open") == ["room_split_unconfirmed"]
    room_id = next(f.element_id for f in report.findings if f.code == "room_split_unconfirmed")
    assert room_id is not None
    split, report = _assemble(raw, _decide(confirmed_splits=[room_id]))
    assert split is not None and _codes(report, "open") == []
    parts = sorted(
        (r.room_type_id, [(p.x, p.y) for p in r.polygon]) for r in split.rooms if r.polygon[0].x == 0
    )
    assert parts == [
        ("kitchen", [(0.0, 5.0), (5.0, 5.0), (5.0, 8.0), (0.0, 8.0)]),
        ("living", [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)]),
    ]


# --- Öffnungen, Typen, Eingang ----------------------------------------------------------------------------


def test_window_without_catalog_type_gets_an_element_default(tmp_path: Path) -> None:
    """E-HM-37: Maß aus dem IFC ohne Typ im Katalog bleibt offen, bis das Büro einen Wert wählt; der Wert
    gilt nur für dieses Fenster."""
    openings = dict(DemoHouse().openings)
    openings["win-bath"] = Opening("window", "north", 2.0, 1.2, 1.6, 0.9, box=0.25)
    raw = _variant(tmp_path, openings=openings)
    _, report = _assemble(raw)
    assert _codes(report, "open") == ["opening_type_unmatched"]
    opening = next(o for o in report.openings if o.slot_id is None)
    assert (opening.width, opening.height, opening.head_height, opening.shutter_box_height) == (
        1.2,
        1.6,
        2.5,
        0.25,
    )
    choice = {opening.element_id: {"window_type": "window.floor_length"}}
    decided, report = _assemble(raw, _decide(element_defaults=choice))
    assert decided is not None and _codes(report, "open") == []
    assert decided.element_defaults == choice
    assert decided.defaults["window_type"] == "window.standard"
    assert next(o for o in report.openings if o.element_id == opening.element_id).source == "office"

    wrong = {opening.element_id: {"window_type": "door.interior"}}
    _, report = _assemble(raw, _decide(element_defaults=wrong))
    assert set(_codes(report, "open")) == {"decision_invalid", "opening_type_unmatched"}


def test_entrance_can_be_overridden_or_removed(demo_raw: RawModel) -> None:
    template, _ = _assemble(demo_raw)
    assert template is not None
    interior = next(o.id for o in template.openings if o.host_kind == "interior_wall")
    none, report = _assemble(demo_raw, _decide(entrance=HouseDoorChoice(opening_id=None)))
    assert none is not None and none.entrance_opening_id is None
    assert "entrance_missing" not in _codes(report)
    _, report = _assemble(demo_raw, _decide(entrance=HouseDoorChoice(opening_id=interior)))
    assert "decision_invalid" in _codes(report, "open")


def test_is_external_is_only_compared(demo_raw: RawModel) -> None:
    """Außen ist, was auf dem Rand liegt (P 12.3); ein falsches `IsExternal` ist nur eine Warnung."""
    interior = next(w for w in demo_raw.walls if w.is_external is False)
    walls = [w.model_copy(update={"is_external": True}) if w is interior else w for w in demo_raw.walls]
    template, report = _assemble(demo_raw.model_copy(update={"walls": walls}))
    assert template is not None
    mismatch = [f for f in report.findings if f.code == "is_external_mismatch"]
    assert [(f.severity, f.ifc_guid) for f in mismatch] == [("warning", interior.guid)]


def _emitted_codes() -> set[str]:
    """Codes aus allen `findings.add(…)` in `assemble.py`; nur Literale, damit die Liste prüfbar bleibt."""
    source = Path(assemble_module.__file__).read_text(encoding="utf-8")
    codes: set[str] = set()

    def literals(node: ast.expr) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.IfExp):
            return literals(node.body) + literals(node.orelse)
        raise AssertionError(f"Befundcode ohne Literal in Zeile {node.lineno}")

    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "findings"
        ):
            codes.update(literals(node.args[1]))
    return codes


def test_finding_codes_are_complete() -> None:
    """Jeder Code, den Import und Job melden, steht in `FINDING_CODES` und umgekehrt (Texte: E-HM-33)."""
    expected = _emitted_codes() | set(READ_ERRORS) | {"import_failed"}
    assert len(FINDING_CODES) == len(set(FINDING_CODES))
    assert set(FINDING_CODES) == expected
