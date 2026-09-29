"""Lesen einer Parzellendatei ohne Datenbank (AN1, `app/site/domain/upload.py`)."""

import hashlib
import json

import pytest
from shapely.geometry import Polygon

from app.site.domain.upload import (
    Candidate,
    Crs,
    ParcelFile,
    UploadInvalid,
    build_candidates,
    detect_crs,
    merge_candidates,
    read_geojson,
    read_parcel_file,
    short_piece_m_for,
    upload_provenance,
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


# ---------------------------------------------------------------------------
# Mehrere Konturen zu einem Grundstück (UP17)
# ---------------------------------------------------------------------------


def piece(
    index: int, points: list[tuple[float, float]], name: str | None = None, crs: Crs = "local"
) -> Candidate:
    polygon = Polygon(points)
    return Candidate(index=index, polygon=polygon, area_m2=polygon.area, crs=crs, name=name)


def test_a_single_contour_stays_as_it_is() -> None:
    only = piece(3, LOCAL, "65")
    assert merge_candidates([only]) is only


def test_two_pieces_of_a_split_parcel_become_one_outline() -> None:
    # Parzelle 20 × 30 m, von einer fremden Linie bei x = 7,5 geteilt
    left = piece(4, [(0.0, 0.0), (7.5, 0.0), (7.5, 30.0), (0.0, 30.0)], "65")
    right = piece(9, [(7.5, 0.0), (20.0, 0.0), (20.0, 30.0), (7.5, 30.0)])
    merged = merge_candidates([left, right])
    assert merged.area_m2 == pytest.approx(600.0)
    assert len(merged.polygon.exterior.coords) == 5  # Stützpunkte der Teilungslinie fallen weg
    assert (merged.index, merged.name, merged.crs) == (4, "65", "local")


def test_a_house_on_the_dividing_line_does_not_leave_a_hole() -> None:
    # Beide Teile haben am Haus (x 5–11, y 10–16) nur eine Einbuchtung
    left = piece(1, [(0, 0), (8, 0), (8, 10), (5, 10), (5, 16), (8, 16), (8, 30), (0, 30)])
    right = piece(2, [(8, 0), (20, 0), (20, 30), (8, 30), (8, 16), (11, 16), (11, 10), (8, 10)])
    merged = merge_candidates([left, right])
    assert not merged.polygon.interiors and merged.area_m2 == pytest.approx(600.0)


def test_separate_contours_are_not_one_site() -> None:
    far = piece(2, [(50.0, 0.0), (70.0, 0.0), (70.0, 30.0), (50.0, 30.0)])
    with pytest.raises(UploadInvalid) as caught:
        merge_candidates([piece(1, LOCAL), far])
    assert caught.value.code == "site_not_contiguous"


def test_contours_with_and_without_position_are_not_merged() -> None:
    with pytest.raises(UploadInvalid) as caught:
        merge_candidates([piece(1, LOCAL), piece(2, L93, crs="EPSG:2154")])
    assert caught.value.code == "upload_outlines_incompatible"


def test_the_short_piece_threshold_grows_with_the_plan_scale() -> None:
    # Ohne Maßstab (DXF, GeoJSON) 2 m; bei PDF 1 mm auf dem Papier, mindestens 2 m (UP18)
    assert short_piece_m_for(None) == 2.0
    assert short_piece_m_for(500) == 2.0
    assert short_piece_m_for(2500) == pytest.approx(2.5)
    assert short_piece_m_for(5000) == pytest.approx(5.0)


def test_provenance_names_file_and_contour_without_keeping_the_file() -> None:
    parcel_file = ParcelFile(rings=[], format="geojson")
    info = upload_provenance("plan.geojson", b"{}", parcel_file, piece(3, L93, "65", crs="EPSG:2154"), [3])
    assert info == {
        "file_name": "plan.geojson",
        "sha256": hashlib.sha256(b"{}").hexdigest(),
        "format": "geojson",
        "layer": None,
        "name": "65",
        "index": 3,
        "crs": "EPSG:2154",
        "short_piece_m": 2.0,
        "position": {"method": "file"},
    }


def test_provenance_of_merged_pdf_contours_keeps_scale_page_and_pieces() -> None:
    parcel_file = ParcelFile(rings=[], format="pdf", scale=2500, scale_source="input", page=2)
    info = upload_provenance("plan.pdf", b"%PDF", parcel_file, piece(4, LOCAL), [4, 9])
    assert (info["index"], info["indices"]) == (None, [4, 9])
    assert (info["scale"], info["scale_source"], info["page"]) == (2500, "input", 2)
    assert info["short_piece_m"] == pytest.approx(2.5)
    assert "position" not in info
