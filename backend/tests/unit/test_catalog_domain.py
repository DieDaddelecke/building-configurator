"""Domäne des Moduls H1: XLSX-Einlesen, DXF-Umriss, Konsistenzprüfungen (Plan H1 3.2, 3.3, 3.5)."""

import io

import ezdxf
import pytest
from openpyxl import Workbook

from app.catalog.domain.consistency import check_roof_pitch, check_room_area_share
from app.catalog.domain.dxf import FootprintDxfInvalid, read_footprints
from app.catalog.domain.tolerances import FOOTPRINT_LAYER_FACADE, FOOTPRINT_LAYER_PROJECTION
from app.catalog.domain.xlsx import TypeWorkbookInvalid, read_type_workbook


def _workbook(kennwerte: dict[str, str], rooms: list[tuple], prices: list[tuple]) -> bytes:
    wb = Workbook()
    k = wb.active
    k.title = "Kennwerte"
    for key, value in kennwerte.items():
        k.append([key, value])

    r = wb.create_sheet("Räume")
    r.append(["name", "kategorie", "geschoss", "flaeche_m2"])
    for row in rooms:
        r.append(list(row))

    p = wb.create_sheet("Preise")
    p.append(["art", "referenz", "aufpreis_eur"])
    for row in prices:
        p.append(list(row))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


LIGNE_KENNWERTE = {
    "name": "Ligne",
    "geschosse": "R+1",
    "dachform": "gable",
    "neigung_deg": "40",
    "firstrichtung": "laengs",
    "firsthoehe_m": "8.4",
    "traufhoehe_m": "5.6",
    "wohnflaeche_m2": "158",
    "zimmer_text": "4 Zimmer, 1 Bad + 1 Gäste-WC",
    "basispreis_min_eur": "328000",
    "basispreis_max_eur": "362000",
}
LIGNE_ROOMS = [("Wohnen", "living", "R", 42.0), ("Bad", "bathroom", "R", 6.0)]
LIGNE_PRICES = [("linie", "confort", "34000"), ("option", "pv", "11200")]


def test_type_workbook_reads_all_three_sheets() -> None:
    data = read_type_workbook(_workbook(LIGNE_KENNWERTE, LIGNE_ROOMS, LIGNE_PRICES))
    assert data.name == "Ligne"
    assert data.roof_form == "gable"
    assert data.pitch_deg == 40.0
    assert data.ridge_direction == "laengs"
    assert data.base_price_min_eur == 328000
    assert data.base_price_max_eur == 362000
    assert [r.name for r in data.rooms] == ["Wohnen", "Bad"]
    assert data.prices[0].kind == "linie"
    assert data.prices[1].kind == "option"


def test_type_workbook_missing_required_field_is_rejected() -> None:
    incomplete = {k: v for k, v in LIGNE_KENNWERTE.items() if k != "wohnflaeche_m2"}
    with pytest.raises(TypeWorkbookInvalid, match="wohnflaeche_m2"):
        read_type_workbook(_workbook(incomplete, LIGNE_ROOMS, LIGNE_PRICES))


def test_type_workbook_unknown_roof_form_is_rejected() -> None:
    bad = {**LIGNE_KENNWERTE, "dachform": "kuppel"}
    with pytest.raises(TypeWorkbookInvalid):
        read_type_workbook(_workbook(bad, LIGNE_ROOMS, LIGNE_PRICES))


def test_type_workbook_invalid_base_price_span_is_rejected() -> None:
    bad = {**LIGNE_KENNWERTE, "basispreis_min_eur": "400000", "basispreis_max_eur": "300000"}
    with pytest.raises(TypeWorkbookInvalid, match="Spanne"):
        read_type_workbook(_workbook(bad, LIGNE_ROOMS, LIGNE_PRICES))


def test_type_workbook_unknown_room_category_is_rejected() -> None:
    with pytest.raises(TypeWorkbookInvalid, match="nicht in"):
        rooms = [("Keller", "unterirdisch", "R", 20.0)]
        read_type_workbook(_workbook(LIGNE_KENNWERTE, rooms, LIGNE_PRICES))


def test_type_workbook_missing_sheet_is_rejected() -> None:
    wb = Workbook()
    k = wb.active
    k.title = "Kennwerte"
    for key, value in LIGNE_KENNWERTE.items():
        k.append([key, value])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(TypeWorkbookInvalid, match="Räume"):
        read_type_workbook(buf.getvalue())


def _dxf_with_layers(facade: list[tuple[float, float]], projection: list[tuple[float, float]]) -> bytes:
    doc = ezdxf.new()
    doc.layers.add(FOOTPRINT_LAYER_FACADE)
    doc.layers.add(FOOTPRINT_LAYER_PROJECTION)
    msp = doc.modelspace()
    msp.add_lwpolyline(facade, close=True, dxfattribs={"layer": FOOTPRINT_LAYER_FACADE})
    msp.add_lwpolyline(projection, close=True, dxfattribs={"layer": FOOTPRINT_LAYER_PROJECTION})
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


_RECT_10x8 = [(0, 0), (10, 0), (10, 8), (0, 8)]
_RECT_11x9 = [(-0.5, -0.5), (10.5, -0.5), (10.5, 8.5), (-0.5, 8.5)]


def test_read_footprints_returns_facade_and_projection() -> None:
    facade, projection = read_footprints(_dxf_with_layers(_RECT_10x8, _RECT_11x9))
    assert facade.area == pytest.approx(80.0)
    assert projection.area == pytest.approx(99.0)


def test_read_footprints_rejects_projection_smaller_than_facade() -> None:
    with pytest.raises(FootprintDxfInvalid, match="kleiner"):
        read_footprints(_dxf_with_layers(_RECT_11x9, _RECT_10x8))


def test_read_footprints_rejects_self_intersecting_polygon() -> None:
    bowtie = [(0, 0), (10, 8), (10, 0), (0, 8)]
    with pytest.raises(FootprintDxfInvalid):
        read_footprints(_dxf_with_layers(bowtie, _RECT_11x9))


def test_read_footprints_rejects_missing_layer() -> None:
    doc = ezdxf.new()
    doc.layers.add(FOOTPRINT_LAYER_FACADE)
    msp = doc.modelspace()
    msp.add_lwpolyline(_RECT_10x8, close=True, dxfattribs={"layer": FOOTPRINT_LAYER_FACADE})
    stream = io.StringIO()
    doc.write(stream)
    with pytest.raises(FootprintDxfInvalid, match=FOOTPRINT_LAYER_PROJECTION):
        read_footprints(stream.getvalue().encode("utf-8"))


# Neigungsprüfung mit den Kennwerten der fünf Platzhalter-Typen (Plan H1 12) – zugleich eine Gegenprobe der
# dort von Hand berechneten Werte.
@pytest.mark.parametrize(
    ("roof_form", "declared", "ridge", "eave", "depth", "expect_mismatch"),
    [
        ("gable", 40.0, 8.4, 5.6, 8.0, True),  # Ligne, Spez. 5.4.5: berechnet 35,0°, Angabe 40° -> Fehler
        ("gable", 38.0, 8.1, 4.97, 8.0, False),  # Plateau — angepasst (Traufe aus Rückfallformel)
        ("hip", 31.8, 6.3, 3.2, 10.0, False),  # Carré
        ("gable", 36.9, 8.8, 5.8, 8.0, False),  # Attique
        ("flat", 0.0, 6.8, 3.4, 8.0, False),  # Plateau: Flachdach, keine Prüfung
    ],
)
def test_roof_pitch_consistency_matches_placeholder_types(
    roof_form: str, declared: float, ridge: float, eave: float, depth: float, expect_mismatch: bool
) -> None:
    finding = check_roof_pitch(
        roof_form=roof_form,
        declared_pitch_deg=None if roof_form == "flat" else declared,
        ridge_height_m=ridge,
        eave_height_m=eave,
        depth_m=depth,
    )
    if roof_form == "flat":
        assert finding is None
    elif expect_mismatch:
        assert finding is not None and finding.code == "pitch_mismatch"
    else:
        assert finding is None


def test_roof_pitch_missing_declared_value_is_an_error() -> None:
    finding = check_roof_pitch(
        roof_form="gable", declared_pitch_deg=None, ridge_height_m=8.0, eave_height_m=5.0, depth_m=8.0
    )
    assert finding is not None
    assert finding.code == "pitch_missing"


def test_room_area_share_within_bounds_is_silent() -> None:
    assert check_room_area_share(room_area_sum_m2=80.0, storey_footprint_m2=96.0) is None


def test_room_area_share_far_outside_bounds_warns() -> None:
    finding = check_room_area_share(room_area_sum_m2=40.0, storey_footprint_m2=96.0)
    assert finding is not None
    assert finding.level == "warning"
