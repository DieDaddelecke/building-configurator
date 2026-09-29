"""Ausgabe der Analyse (AN5, docs/PLAN_AN5_AUSGABE.md): Lage setzen, Geländeraster und Profil, DXF mit
Gabarit, GeoJSON-Aufbau und Abstände im Klartext des Berichts. Grundstück wie in G3: 20 × 31 m, Straße im
Norden."""

import io
from collections import Counter
from dataclasses import replace
from itertools import pairwise

import pytest
from shapely.geometry import LineString, Polygon, box

from app.analysis import service
from app.analysis.domain.analyse import analyse
from app.analysis.domain.parameters import DEFAULTS
from app.analysis.domain.terrain_profile import profile
from app.analysis.export import features, oriented, plan_for
from app.analysis.report import _Text, distance_text, file_stem
from app.envelope.domain.derive import derive_envelope
from app.envelope.domain.inputs import EnvelopeInput, RuleInput, TerrainInput
from app.envelope.schemas import HeightsOut, SetbackOut
from app.plan import dxf
from app.plan.geometry import Area, Plan
from app.site.domain import position
from app.site.domain.terrain import grid_points
from tests.envelope_support import edges_of_rectangle, envelope_input, rectangle, rule, site, zone

ORIGIN_L93 = (355_000.0, 6_700_000.0)
REFERENCE_NGF = 41.0


def uh_rules() -> list[RuleInput]:
    """Zone Uh des Testreglements (wie tests/unit/test_analysis_gabarit.py)."""
    return [
        rule("setback_street", {"mode": "range", "min_m": 5, "max_m": 20, "band": "building"}),
        rule("setback_side", {"min_m": 3, "allow_on_boundary": True}),
        rule("setback_rear", {"min_m": 3, "allow_on_boundary": True}),
        rule("max_footprint_ratio", {"ratio": 0.25}),
        rule("max_height", {"eave_m": 7, "ridge_m": 10}),
    ]


def plane(x: float, y: float) -> float:
    return 40.0 + 0.1 * x + 0.02 * y


def samples(polygon: Polygon) -> tuple[tuple[float, float, float], ...]:
    return tuple((x, y, round(plane(x, y), 6)) for x, y in grid_points(polygon))


def computed(*, terrain: bool = True) -> service.Computed:
    outline = rectangle(20.0, 31.0)
    base = site(polygon=outline, edges=edges_of_rectangle(20.0, 31.0))
    ground = TerrainInput(
        status="ok" if terrain else "unavailable",
        slope_percent=10.2 if terrain else None,
        reference_altitude_ngf=REFERENCE_NGF if terrain else None,
        samples=samples(outline) if terrain else (),
    )
    data: EnvelopeInput = envelope_input(
        site_input=replace(base, terrain=ground), zones=[zone(polygon=outline, rules=uh_rules())]
    )
    envelope = derive_envelope(data)
    result = analyse(data, envelope, DEFAULTS, [])
    out = service._out(result, DEFAULTS, data, custom=False, input_hash="test")
    return service.Computed(data=data, envelope=envelope, result=result, out=out)


# ---------------------------------------------------------------------------
# Lage (3.2)
# ---------------------------------------------------------------------------


def test_turning_keeps_lengths_and_area_and_turns_azimuths() -> None:
    outline = box(0.0, 0.0, 20.0, 30.0)
    centre = position.pivot(outline)
    moved = position.turn(outline, centre, ORIGIN_L93, 30.0)
    assert moved.area == pytest.approx(600.0, abs=0.01)
    before = list(outline.exterior.coords)
    after = list(moved.exterior.coords)
    for (a, b), (c, d) in zip(pairwise(before), pairwise(after), strict=True):
        assert LineString([a, b]).length == pytest.approx(LineString([c, d]).length, abs=0.001)
    # Die Strecke nach Blattoben zeigt nach 30° (im Uhrzeigersinn)
    north = position.turn(LineString([(0.0, 0.0), (0.0, 30.0)]), centre, ORIGIN_L93, 30.0)
    start, end = list(north.coords)
    assert position.azimuth(start, end) == pytest.approx(30.0, abs=1e-6)
    assert position.turn_azimuth(350.0, 30.0) == 20.0
    assert position.turn_azimuth(None, 30.0) is None


def test_rotation_adds_the_convergence_and_a_correction_does_not_turn_twice() -> None:
    # Erste Lage: Blattoben = geografisch Nord, Δ = 30°, γ = 3° → Gitterazimut 33°
    assert position.rotation(0.0, 30.0, 3.0) == pytest.approx(33.0)
    # Korrektur ohne Änderung: Karte zeigt −γ_alt, Δ = 0, γ_neu ≈ γ_alt → keine Drehung
    assert position.rotation(-3.0, 0.0, 3.0004) == pytest.approx(0.0, abs=0.001)
    assert position.signed(350.0) == pytest.approx(-10.0)
    assert position.inside_france(-1.6, 47.3) and not position.inside_france(13.4, 52.5)


# ---------------------------------------------------------------------------
# Gelände (3.3)
# ---------------------------------------------------------------------------


def test_grid_uses_two_metres_on_a_small_site_and_at_most_200_points() -> None:
    small = grid_points(box(0.0, 0.0, 20.0, 30.0))
    assert len(small) == 150
    assert all(
        box(0.0, 0.0, 20.0, 30.0).contains(Polygon([(x, y), (x + 1e-6, y), (x, y + 1e-6)])) for x, y in small
    )
    large = grid_points(box(0.0, 0.0, 250.0, 200.0))
    assert 150 <= len(large) <= 200


def test_grid_falls_back_to_nine_samples_on_a_tiny_site() -> None:
    assert len(grid_points(box(0.0, 0.0, 3.0, 3.0))) == 9


def test_profile_reproduces_a_plane_also_beyond_the_outermost_samples() -> None:
    outline = rectangle(20.0, 31.0)
    points = profile(samples(outline), (10.0, 31.0), (10.0, 0.0), [(0.0, 31.0)], REFERENCE_NGF)
    assert points[0][0] == 0.0 and points[-1][0] == 31.0
    for s, dz in points:
        assert dz == pytest.approx(plane(10.0, 31.0 - s) - REFERENCE_NGF, abs=0.01)


def test_profile_needs_three_samples() -> None:
    assert profile(((0.0, 0.0, 1.0), (1.0, 0.0, 1.0)), (0.0, 0.0), (0.0, 5.0), [(0.0, 5.0)], 0.0) == []


def test_sections_carry_the_profile_only_with_terrain() -> None:
    with_terrain = computed()
    assert all(section.terrain for section in with_terrain.result.sections)
    assert with_terrain.out.gabarit is not None
    assert with_terrain.out.gabarit.reference_altitude_ngf == REFERENCE_NGF
    assert all(section.terrain == [] for section in computed(terrain=False).result.sections)


# ---------------------------------------------------------------------------
# DXF (3.4)
# ---------------------------------------------------------------------------


def _read(data: bytes):  # type: ignore[no-untyped-def]
    import ezdxf

    return ezdxf.read(io.StringIO(data.decode()))


def _closed(face_list: list[list[tuple[float, float, float]]]) -> bool:
    edges: Counter[tuple[tuple[float, float, float], ...]] = Counter()
    for face in face_list:
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            edges[tuple(sorted((a, b)))] += 1
    return all(count == 2 for count in edges.values())


def test_solid_is_closed_with_a_hole_and_a_point_on_a_straight_side() -> None:
    area = Area(
        exterior=[(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        holes=[[(3.0, 3.0), (3.0, 7.0), (7.0, 7.0), (7.0, 3.0)]],
    )
    faces = dxf.solid(area, 0.0, 3.0)
    assert faces and _closed(faces)
    assert dxf.solid(area, 3.0, 3.0) == []


def test_v_keeps_its_layers() -> None:
    plan = Plan(
        origin=(0.0, 0.0), georeferenced=False, parcel=[[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]], edges=[]
    )
    doc = _read(dxf.render(plan, "local", ["V"]))
    assert {layer.dxf.name for layer in doc.layers} - {"0", "Defpoints"} == set(dxf.LAYERS)


def test_analysis_dxf_has_gabarit_bodies_contours_and_cuts() -> None:
    from ezdxf.render import MeshBuilder

    plan = replace(plan_for(computed(), georeferenced=True), origin=ORIGIN_L93)
    local = _read(dxf.render(plan, "local", ["A"], all_layers=False))
    l93 = _read(dxf.render(plan, "L93", ["A"], all_layers=False))
    names = {layer.dxf.name for layer in local.layers}
    assert {
        "PARCELLE",
        "COUPE",
        "BANDE_CONSTRUCTIBLE",
        "GABARIT_LARGE_COURBES",
        "GABARIT_LARGE_VOLUME",
    } <= names
    assert "MAISON_FACADE" not in names
    bodies = [e for e in local.modelspace().query("POLYLINE") if e.is_poly_face_mesh]
    assert len(bodies) == sum(len(stage.areas) for stage in plan.stages) > 0
    for body in bodies:
        diagnose = MeshBuilder.from_polyface(body).optimize_vertices(precision=3).diagnose()
        assert diagnose.is_closed_surface and not diagnose.is_edge_balance_broken
        assert diagnose.volume() > 0
    # Lambert-93 = lokal + Ursprung, Z in m NGF
    local_parcel = local.modelspace().query('LWPOLYLINE[layer=="PARCELLE"]')[0].get_points("xy")
    l93_parcel = l93.modelspace().query('LWPOLYLINE[layer=="PARCELLE"]')[0].get_points("xy")
    for (x, y), (e, n) in zip(local_parcel, l93_parcel, strict=True):
        assert (e - x, n - y) == pytest.approx(ORIGIN_L93, abs=0.001)
    top = max(stage.to_m for stage in plan.stages)
    local_z = max(
        e.dxf.elevation for e in local.modelspace().query('LWPOLYLINE[layer=="GABARIT_LARGE_COURBES"]')
    )
    l93_z = max(e.dxf.elevation for e in l93.modelspace().query('LWPOLYLINE[layer=="GABARIT_LARGE_COURBES"]'))
    assert local_z == pytest.approx(min(top, local_z))
    assert l93_z == pytest.approx(local_z + REFERENCE_NGF)


def test_l93_needs_a_position() -> None:
    plan = plan_for(computed(), georeferenced=False)
    with pytest.raises(ValueError):
        dxf.render(plan, "L93", [])


def test_file_stem_is_plain_ascii() -> None:
    assert file_stem("Maison Dupré – Treillières 12/3") == "Maison-Dupre-Treillieres-12-3"
    assert file_stem("« »") == "emprise-analyse"


# ---------------------------------------------------------------------------
# GeoJSON (3.5)
# ---------------------------------------------------------------------------


def test_geojson_features_carry_layers_and_properties() -> None:
    items = features(computed())
    layers = Counter(props["layer"] for _, props in items)
    assert layers["PARCELLE"] == 1 and layers["LIMITE_VOIE"] == 1 and layers["COUPE"] == 2
    gabarit = [props for _, props in items if props["layer"].startswith("GABARIT_")]
    assert gabarit and all(
        props["z_ngf_top"] == pytest.approx(REFERENCE_NGF + props["to_m"]) for props in gabarit
    )
    assert all(not geometry.is_empty for geometry, _ in items)


def test_rings_follow_rfc_7946() -> None:
    clockwise = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)], [[(2, 2), (4, 2), (4, 4), (2, 4)]])
    turned = oriented(clockwise)
    assert isinstance(turned, Polygon)
    assert turned.exterior.is_ccw and not turned.interiors[0].is_ccw


# ---------------------------------------------------------------------------
# Bericht: Abstände im Klartext (3.6, EA10)
# ---------------------------------------------------------------------------


def _setback(kind: str, params: dict[str, object], status: str = "effective") -> SetbackOut:
    return SetbackOut.model_validate(
        {
            "zone_code": "Uh",
            "kind": kind,
            "building_kind": "main",
            "status": status,
            "params": params,
            "markers": [],
        }
    )


HEIGHTS = HeightsOut(eave_m=7.0, ridge_m=10.0, reference="natural_ground", measured_at="eave", assumptions=[])


@pytest.mark.parametrize(
    ("kind", "params", "status", "text"),
    [
        (
            "setback_side",
            {"min_m": 3.0, "height_factor": 0.5, "height_basis": "eave"},
            "effective",
            "H/2 (Traufhöhe), mindestens 3,00 m – bei 7,00 m Höhe also 3,50 m",
        ),
        (
            "setback_side",
            {"min_m": 3.0, "allow_on_boundary": True, "on_boundary_max_height_m": 3.5},
            "effective",
            "auf der Grenze zulässig bis 3,50 m Höhe, sonst mindestens 3,00 m",
        ),
        (
            "setback_street",
            {"mode": "range", "min_m": 5, "max_m": 20, "band": "building"},
            "effective",
            "zwischen 5,00 m und 20,00 m (ganzer Baukörper im Band)",
        ),
        ("setback_rear", {}, "unknown", "nicht ermittelt"),
        ("setback_rear", {}, "not_regulated", "nicht geregelt – kein Mindestabstand"),
    ],
)
def test_distance_in_plain_words(kind: str, params: dict[str, object], status: str, text: str) -> None:
    assert distance_text(_setback(kind, params, status), HEIGHTS, _Text("de")) == text
