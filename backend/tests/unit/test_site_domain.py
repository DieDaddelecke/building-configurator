"""Grundstück bilden, Kanten einordnen, Gelände auswerten (Spez. 5.1.3, 5.1.4, 5.9.4; Plan 3.3)."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely import affinity
from shapely.geometry import LineString, Polygon, box

from app.site.domain import terrain
from app.site.domain.edges import NeighbourParcel, Override, RoadLine, classify, edge_facts, split_edges
from app.site.domain.outline import ParcelInput, SiteNotContiguous, merge_parcels

E0, N0 = 350_000.0, 6_700_000.0


def rect(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return box(E0 + x0, N0 + y0, E0 + x1, N0 + y1)


def neighbour(idu: str, geometry: Polygon, building: bool = True) -> NeighbourParcel:
    return NeighbourParcel(idu=idu, geometry=geometry, has_building=building)


def run(parcel: Polygon, neighbours: list[NeighbourParcel], overrides: dict[int, Override] | None = None):  # type: ignore[no-untyped-def]
    outline = merge_parcels([ParcelInput("44209000AB0147", parcel, None)])
    edges = split_edges(outline.polygon)
    facts = edge_facts(edges, neighbours)
    return outline, classify(
        edges,
        facts,
        overrides,
        site_area_m2=outline.area_m2,
        neighbour_coverage="complete" if neighbours else "none",
    )


def kind_facing(result, azimuth: float) -> str:  # type: ignore[no-untyped-def]
    """Art der Kante, deren Außennormale am nächsten an `azimuth` liegt."""
    edge = min(
        result.edges,
        key=lambda e: abs((e.geometry.normal_azimuth_deg - azimuth + 180) % 360 - 180),
    )
    return str(edge.kind)


# Mockup: 20 × 31 m, Straße im Norden, Nachbarn Ost, West und Süd bebaut (Spez. 11.2)
MOCKUP_PARCEL = rect(0, 0, 20, 31)
MOCKUP_NEIGHBOURS = [
    neighbour("W", rect(-20, 0, 0, 31)),
    neighbour("E", rect(20, 0, 40, 31)),
    neighbour("S", rect(-20, -30, 40, 0)),
]


def test_mockup_rectangle_street_north_neighbours_side_and_rear() -> None:
    outline, result = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS)
    assert outline.area_m2 == pytest.approx(620.0)
    assert outline.local_origin == (E0, N0)
    assert len(result.edges) == 4
    assert kind_facing(result, 0) == "street"
    assert kind_facing(result, 90) == "side"
    assert kind_facing(result, 270) == "side"
    assert kind_facing(result, 180) == "rear"
    assert result.street_azimuth_deg == pytest.approx(0.0, abs=0.01)
    assert result.garden_azimuth_deg == pytest.approx(180.0, abs=0.01)
    assert result.warnings == ()
    assert result.binding
    east = next(e for e in result.edges if e.kind == "side" and e.geometry.normal_azimuth_deg < 180)
    assert east.facts.adjacent == ("E",)
    assert east.confidence >= 0.8


def test_kinked_side_boundary_stays_side() -> None:
    parcel = Polygon([(E0, N0), (E0 + 20, N0), (E0 + 22, N0 + 15), (E0 + 20, N0 + 31), (E0, N0 + 31)])
    neighbours = [
        neighbour("W", rect(-20, 0, 0, 31)),
        neighbour(
            "E",
            Polygon(
                [(E0 + 20, N0), (E0 + 40, N0), (E0 + 40, N0 + 31), (E0 + 20, N0 + 31), (E0 + 22, N0 + 15)]
            ),
        ),
        neighbour("S", rect(-20, -30, 40, 0)),
    ]
    _, result = run(parcel, neighbours)
    kinds = sorted(str(e.kind) for e in result.edges)
    assert kinds == ["rear", "side", "side", "side", "street"]


def test_corner_lot_warns_and_keeps_both_streets() -> None:
    neighbours = [neighbour("W", rect(-20, 0, 0, 31)), neighbour("S", rect(-20, -30, 20, 0))]
    _, result = run(MOCKUP_PARCEL, neighbours)
    assert kind_facing(result, 0) == "street"
    assert kind_facing(result, 90) == "street"
    assert "corner_lot" in result.warnings


def test_narrow_unbuilt_neighbour_is_private_road_candidate() -> None:
    neighbours = [*MOCKUP_NEIGHBOURS, neighbour("ROAD", rect(-20, 31, 40, 35), building=False)]
    _, result = run(MOCKUP_PARCEL, neighbours)
    north = min(result.edges, key=lambda e: abs((e.geometry.normal_azimuth_deg + 180) % 360 - 180))
    assert north.kind == "street"
    assert north.facts.street_candidate == "private_road"
    assert north.confidence < 0.65
    assert "edges_need_review" in result.warnings


def test_built_narrow_neighbour_is_not_a_road() -> None:
    neighbours = [*MOCKUP_NEIGHBOURS, neighbour("HOUSE", rect(-20, 31, 40, 35), building=True)]
    _, result = run(MOCKUP_PARCEL, neighbours)
    assert "no_street_edge" in result.warnings
    assert all(e.kind == "other" for e in result.edges)


def test_flag_lot_lowers_confidence() -> None:
    parcel = Polygon(
        [
            (E0, N0),
            (E0 + 25, N0),
            (E0 + 25, N0 + 25),
            (E0 + 14, N0 + 25),
            (E0 + 14, N0 + 50),
            (E0 + 10, N0 + 50),
            (E0 + 10, N0 + 25),
            (E0, N0 + 25),
        ]
    )
    neighbours = [
        neighbour(
            "W",
            Polygon(
                [
                    (E0 - 20, N0),
                    (E0, N0),
                    (E0, N0 + 25),
                    (E0 + 10, N0 + 25),
                    (E0 + 10, N0 + 50),
                    (E0 - 20, N0 + 50),
                ]
            ),
        ),
        neighbour(
            "E",
            Polygon(
                [
                    (E0 + 25, N0),
                    (E0 + 45, N0),
                    (E0 + 45, N0 + 50),
                    (E0 + 14, N0 + 50),
                    (E0 + 14, N0 + 25),
                    (E0 + 25, N0 + 25),
                ]
            ),
        ),
        neighbour("S", rect(-20, -30, 45, 0)),
    ]
    _, result = run(parcel, neighbours)
    assert "flag_lot" in result.warnings
    assert [e.kind for e in result.edges].count("street") == 1
    assert all(e.confidence <= 0.4 for e in result.edges if e.kind != "street")


def test_hole_edges_are_other() -> None:
    parcel = Polygon(MOCKUP_PARCEL.exterior.coords, [list(rect(5, 5, 8, 8).exterior.coords)])
    _, result = run(parcel, MOCKUP_NEIGHBOURS)
    holes = [e for e in result.edges if e.geometry.ring == 1]
    assert len(holes) == 4
    assert {e.kind for e in holes} == {"other"}


def test_no_neighbour_data_requires_manual_classification() -> None:
    _, result = run(MOCKUP_PARCEL, [])
    assert {e.kind for e in result.edges} == {"other"}
    assert {"no_neighbour_data", "no_street_edge"} <= set(result.warnings)


def test_merge_adjacent_parcels_and_collinear_segments() -> None:
    outline = merge_parcels(
        [ParcelInput("A", rect(0, 0, 10, 31), 310), ParcelInput("B", rect(10.01, 0, 20, 31), 310)]
    )
    assert outline.polygon.is_valid
    assert len(split_edges(outline.polygon)) == 4
    assert outline.area_official_m2 == 620
    assert not outline.area_mismatch


def test_non_contiguous_parcels_are_rejected() -> None:
    with pytest.raises(SiteNotContiguous):
        merge_parcels(
            [ParcelInput("A", rect(0, 0, 10, 10), None), ParcelInput("B", rect(12, 0, 20, 10), None)]
        )


def test_area_mismatch_over_three_percent() -> None:
    assert merge_parcels([ParcelInput("A", MOCKUP_PARCEL, 590)]).area_mismatch
    assert not merge_parcels([ParcelInput("A", MOCKUP_PARCEL, 612)]).area_mismatch


def test_split_is_independent_of_start_vertex_and_extra_vertices() -> None:
    a = split_edges(MOCKUP_PARCEL)
    shifted = Polygon([(E0 + 20, N0 + 10), (E0 + 20, N0 + 31), (E0, N0 + 31), (E0, N0), (E0 + 20, N0)])
    b = split_edges(merge_parcels([ParcelInput("A", shifted, None)]).polygon)
    assert {(e.start, e.end) for e in a} == {(e.start, e.end) for e in b}


def test_customer_street_correction_is_not_binding_and_keeps_auto_kind() -> None:
    _, auto = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS)
    rear_seq = next(e.geometry.seq for e in auto.edges if e.kind == "rear")
    _, corrected = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS, {rear_seq: Override("street", "customer")})
    edge = next(e for e in corrected.edges if e.geometry.seq == rear_seq)
    assert (edge.kind, edge.kind_auto, edge.source) == ("street", "rear", "customer")
    assert not corrected.binding
    assert "customer_corrections_unconfirmed" in corrected.warnings
    assert "corner_lot" not in corrected.warnings  # parallel zur Hauptstraße: kein Eck


def test_customer_not_street_reclassifies_neighbours() -> None:
    _, auto = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS)
    street_seq = next(e.geometry.seq for e in auto.edges if e.kind == "street")
    _, corrected = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS, {street_seq: Override("not_street", "customer")})
    assert "no_street_edge" in corrected.warnings
    assert {e.kind for e in corrected.edges} == {"other"}


def test_architect_override_is_binding() -> None:
    _, auto = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS)
    rear_seq = next(e.geometry.seq for e in auto.edges if e.kind == "rear")
    _, corrected = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS, {rear_seq: Override("side", "architect")})
    edge = next(e for e in corrected.edges if e.geometry.seq == rear_seq)
    assert (edge.kind, edge.source, edge.confidence) == ("side", "architect", 1.0)
    assert corrected.binding


@settings(max_examples=40, deadline=None)
@given(angle=st.floats(min_value=0, max_value=360, allow_nan=False))
def test_classification_is_rotation_invariant(angle: float) -> None:
    """Gedrehtes Grundstück samt Nachbarn: gleiche Arten, Außennormalen um den Drehwinkel verschoben."""
    centre = (E0 + 10, N0 + 15)

    def turn(geometry: Polygon) -> Polygon:
        return affinity.rotate(geometry, -angle, origin=centre)  # shapely dreht gegen den Uhrzeigersinn

    _, base = run(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS)
    _, rotated = run(turn(MOCKUP_PARCEL), [neighbour(n.idu, turn(n.geometry)) for n in MOCKUP_NEIGHBOURS])  # type: ignore[arg-type]
    for azimuth_deg in (0, 90, 180, 270):
        assert kind_facing(rotated, (azimuth_deg + angle) % 360) == kind_facing(base, azimuth_deg)
    assert rotated.street_azimuth_deg is not None
    assert math.isclose((rotated.street_azimuth_deg - angle) % 360, 0, abs_tol=0.05) or math.isclose(
        (rotated.street_azimuth_deg - angle) % 360, 360, abs_tol=0.05
    )


def test_terrain_plane_fit_and_flat_threshold() -> None:
    polygon = rect(0, 0, 20, 30)
    points = terrain.sample_points(polygon)
    assert len(points) == 9
    assert all(polygon.contains(__import__("shapely").geometry.Point(p)) for p in points)
    sloped = terrain.evaluate(points, [50 + 0.1 * (x - E0) for x, _ in points])
    assert sloped is not None
    assert sloped.slope_percent == pytest.approx(10.0, abs=0.01)
    assert not sloped.flat
    level = terrain.evaluate(points, [56.0] * len(points))
    assert level is not None and level.flat and level.reference_altitude_ngf == 56.0
    assert terrain.evaluate(points[:2], [1.0, 2.0]) is None
    assert terrain.evaluate(points, [None] * 7 + [1.0, 2.0]) is None


# ---------------------------------------------------------------------------
# Straßenachsen (BD TOPO) als Bestätigung der Straßenkante
# ---------------------------------------------------------------------------


def run_with_roads(parcel: Polygon, neighbours: list[NeighbourParcel], roads: list[RoadLine]):  # type: ignore[no-untyped-def]
    outline = merge_parcels([ParcelInput("44209000AB0147", parcel, None)])
    edges = split_edges(outline.polygon)
    facts = edge_facts(edges, neighbours, roads, outline.polygon)
    return classify(edges, facts, site_area_m2=outline.area_m2)


def road(name: str, *points: tuple[float, float]) -> RoadLine:
    return RoadLine(name, LineString([(E0 + x, N0 + y) for x, y in points]))


def test_road_on_own_parcel_confirms_front_but_not_green_strip_behind() -> None:
    """Lotissement: Straße und Grünstreifen gehören zu einer großen, unbebauten Parzelle (wie AD0071)."""
    common = neighbour(
        "COMMON",
        Polygon(
            rect(-30, 31, 50, 45).union(rect(-30, -12, 50, 0)).union(rect(-30, -12, -20, 45)).exterior.coords
        ),
        building=False,
    )
    neighbours = [neighbour("W", rect(-20, 0, 0, 31)), neighbour("E", rect(20, 0, 40, 31)), common]
    result = run_with_roads(MOCKUP_PARCEL, neighbours, [road("Rue des chênes", (-30, 37), (50, 37))])
    assert kind_facing(result, 0) == "street"
    assert kind_facing(result, 180) == "rear"
    north = next(e for e in result.edges if e.kind == "street")
    assert north.facts.street_name == "Rue des chênes" and north.facts.road_share == 1.0


def test_road_behind_built_neighbour_does_not_count() -> None:
    neighbours = [*MOCKUP_NEIGHBOURS[:2], neighbour("S", rect(-20, -10, 40, 0), building=True)]
    result = run_with_roads(
        MOCKUP_PARCEL,
        neighbours,
        [road("Rue du fond", (-20, -12), (40, -12)), road("Rue", (-20, 36), (40, 36))],
    )
    assert kind_facing(result, 180) == "rear"
    assert kind_facing(result, 0) == "street"


def test_open_edge_without_road_is_uncertain() -> None:
    """Keine Nachbarparzelle, aber auch keine Achse in 15 m: Grünfläche, Bach oder Bahn möglich."""
    result = run_with_roads(MOCKUP_PARCEL, MOCKUP_NEIGHBOURS, [])
    north = next(e for e in result.edges if e.kind == "street")
    assert north.confidence < 0.65 and "edges_need_review" in result.warnings


def test_main_street_prefers_confirmed_edge_over_longer_uncertain_one() -> None:
    """Kurze Front mit Straßenachse (12 m) gegen lange offene Kante hinten ohne Achse (20 m): Hauptstraße ist
    die Front, sonst wären Straßen- und Gartenseite vertauscht."""
    parcel = Polygon([(E0 + x, N0 + y) for x, y in ((0, 0), (12, 0), (20, 40), (0, 40))])
    east = Polygon([(E0 + x, N0 + y) for x, y in ((12, 0), (40, 0), (40, 40), (20, 40))])
    neighbours = [neighbour("W", rect(-20, 0, 0, 40)), neighbour("E", east)]
    result = run_with_roads(parcel, neighbours, [road("Rue", (-30, -6), (50, -6))])
    main = next(e for e in result.edges if e.geometry.seq == result.main_street_seq)
    assert main.confidence >= 0.65 and round(main.geometry.length_m) == 12
    assert result.street_azimuth_deg == pytest.approx(180, abs=1)
    assert "edges_need_review" in result.warnings  # die lange offene Kante bleibt zur Prüfung markiert


def test_narrow_unbuilt_strip_without_road_axis_is_uncertain_neighbour() -> None:
    """Mit Straßendaten: schmaler Streifen ohne Achse ist Zufahrt oder Grün, keine Straße und kein Eck."""
    neighbours = [*MOCKUP_NEIGHBOURS, neighbour("STRIP", rect(-20, 31, 40, 35), building=False)]
    east_road = road("Rue", (30, -30), (30, 60))
    result = run_with_roads(MOCKUP_PARCEL, [neighbours[0], neighbours[2], neighbours[3]], [east_road])
    assert kind_facing(result, 90) == "street"
    north = min(result.edges, key=lambda e: abs((e.geometry.normal_azimuth_deg + 180) % 360 - 180))
    assert north.kind != "street" and north.confidence <= 0.4
    assert "corner_lot" not in result.warnings and "edges_need_review" in result.warnings


def test_context_rings_skip_empty_parts() -> None:
    """Der Zuschnitt der Umgebung per ST_Intersection kann leere Polygone liefern (gefunden im E2E-Test)."""
    from shapely.geometry import GeometryCollection, MultiPolygon

    from app.site.service import _rings

    geometry = GeometryCollection([Polygon(), MultiPolygon([rect(0, 0, 1, 1)])])
    rings = _rings(geometry, (E0, N0))
    assert rings == [] or all(len(r) >= 4 for r in rings)
    assert _rings(Polygon(), (E0, N0)) == []
    assert len(_rings(rect(0, 0, 2, 2), (E0, N0))) == 1
