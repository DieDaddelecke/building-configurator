"""Lesen einer Parzellendatei ohne Datenbank (AN1, `app/site/domain/upload.py`)."""

import json

import pytest

from app.site.domain.upload import (
    UploadInvalid,
    build_candidates,
    detect_crs,
    read_geojson,
    read_parcel_file,
)

LOCAL = [(0.0, 0.0), (20.0, 0.0), (20.0, 30.0), (0.0, 30.0)]
L93 = [(355_000.0, 6_705_000.0), (355_020.0, 6_705_000.0), (355_020.0, 6_705_030.0), (355_000.0, 6_705_030.0)]
WGS84 = [(-1.5970, 47.2818), (-1.5967, 47.2818), (-1.5967, 47.2821), (-1.5970, 47.2821)]


def geojson(geometry: dict[str, object]) -> bytes:
    return json.dumps(geometry).encode("utf-8")


def identity(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Statt PostGIS: verschiebt die Grade nur grob in Meter, reicht für die Prüfung der Schranken."""
    return [((x + 2) * 70_000, (y - 47) * 111_000) for x, y in points]


def test_detects_the_coordinate_system_from_the_magnitude() -> None:
    assert detect_crs(L93) == "EPSG:2154"
    assert detect_crs(WGS84) == "EPSG:4326"
    assert detect_crs(LOCAL) == "local"


def test_reads_a_bare_polygon() -> None:
    data = geojson({"type": "Polygon", "coordinates": [[list(p) for p in [*L93, L93[0]]]]})
    rings = read_geojson(data)
    assert len(rings) == 1 and rings[0].crs == "EPSG:2154"
    # Der schließende Punkt fällt weg
    assert len(rings[0].points) == 4


def test_reads_multipolygon_and_feature_names() -> None:
    data = geojson(
        {
            "type": "Feature",
            "properties": {"idu": "44209000AD0065"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[list(p) for p in [*L93, L93[0]]]],
                    [[list(p) for p in [*LOCAL, LOCAL[0]]]],
                ],
            },
        }
    )
    rings = read_geojson(data)
    assert [r.name for r in rings] == ["44209000AD0065"] * 2
    assert [r.crs for r in rings] == ["EPSG:2154", "local"]


def test_wgs84_ring_is_converted_before_the_area_check() -> None:
    data = geojson({"type": "Polygon", "coordinates": [[list(p) for p in [*WGS84, WGS84[0]]]]})
    candidates = build_candidates(read_geojson(data), identity)
    assert len(candidates) == 1 and candidates[0].georeferenced
    assert candidates[0].area_m2 > 100  # in Grad gerechnet wäre die Fläche winzig


def test_candidates_are_sorted_by_area_and_implausible_ones_drop_out() -> None:
    tiny = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    data = geojson(
        {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Polygon", "coordinates": [[list(p) for p in [*tiny, tiny[0]]]]},
                {"type": "Polygon", "coordinates": [[list(p) for p in [*LOCAL, LOCAL[0]]]]},
            ],
        }
    )
    candidates = build_candidates(read_geojson(data), identity)
    assert [c.area_m2 for c in candidates] == [600.0]


def test_self_intersecting_ring_is_dropped() -> None:
    bowtie = [(0.0, 0.0), (20.0, 20.0), (20.0, 0.0), (0.0, 20.0)]
    data = geojson({"type": "Polygon", "coordinates": [[list(p) for p in [*bowtie, bowtie[0]]]]})
    with pytest.raises(UploadInvalid):
        build_candidates(read_geojson(data), identity)


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(UploadInvalid):
        read_parcel_file("parzelle.dwg", b"egal")
