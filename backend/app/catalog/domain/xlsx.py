"""Typdatenblatt aus XLSX lesen (Plan H1 3.2).

Drei Blätter je Typ: `Kennwerte` (Feld/Wert), `Räume` (Tabelle), `Preise` (Tabelle). Das Schema ist so
streng wie bei der Regelauswertung (G2): feste Spaltenüberschriften, Fehlermeldung mit Blatt und Zelle statt
stillem Fehlinterpretieren.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

ROOF_FORMS = ("gable", "hip", "flat", "complex")
RIDGE_DIRECTIONS = ("laengs", "quer")
ROOM_CATEGORIES = ("living", "bedroom", "bathroom", "kitchen", "circulation", "storage", "garage", "other")
PRICE_KINDS = ("linie", "option")
"""RE2020-Bewertungen kommen nicht aus dem Typdatenblatt (Plan H1 3.8), sondern aus einer eigenen
Erfassung in der Katalogpflege: der Befund ist Freitext, kein Kennwert, den ein Typdatenblatt sinnvoll
trüge."""

_KENNWERTE_REQUIRED = (
    "name",
    "geschosse",
    "dachform",
    "firsthoehe_m",
    "traufhoehe_m",
    "wohnflaeche_m2",
    "zimmer_text",
    "basispreis_min_eur",
    "basispreis_max_eur",
)
_RAEUME_COLUMNS = ("name", "kategorie", "geschoss", "flaeche_m2")
_PREISE_COLUMNS = ("art", "referenz", "aufpreis_eur")


class TypeWorkbookInvalid(ValueError):
    """Das Typdatenblatt weicht vom Schema ab (Code `type_workbook_invalid`)."""


@dataclass(frozen=True)
class RoomEntry:
    name: str
    category: str
    storey: str
    area_m2: float


@dataclass(frozen=True)
class PriceEntry:
    kind: str
    reference: str
    surcharge_eur: int


@dataclass(frozen=True)
class TypeSheetData:
    name: str
    family: str | None
    storeys: str
    roof_form: str
    pitch_deg: float | None
    ridge_direction: str | None
    ridge_height_m: float
    eave_height_m: float
    living_area_m2: float
    rooms_text: str
    base_price_min_eur: int
    base_price_max_eur: int
    rooms: list[RoomEntry]
    prices: list[PriceEntry]


def _sheet(workbook: Any, name: str) -> Worksheet:
    if name not in workbook.sheetnames:
        raise TypeWorkbookInvalid(f"Blatt „{name}“ fehlt")
    sheet: Worksheet = workbook[name]
    return sheet


def _read_kennwerte(sheet: Worksheet) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in sheet.iter_rows(min_row=1, max_col=2, values_only=False):
        key_cell, value_cell = row[0], row[1]
        if key_cell.value is None:
            continue
        key = str(key_cell.value).strip()
        if value_cell.value is None:
            continue
        values[key] = str(value_cell.value).strip()
    missing = [key for key in _KENNWERTE_REQUIRED if key not in values or not values[key]]
    if missing:
        raise TypeWorkbookInvalid(f"Kennwerte: Pflichtfeld(er) fehlen: {', '.join(missing)}")
    return values


def _float(values: dict[str, str], key: str, sheet_name: str = "Kennwerte") -> float:
    try:
        return float(str(values[key]).replace(",", "."))
    except ValueError as exc:
        raise TypeWorkbookInvalid(f"{sheet_name}!{key}: Zahl erwartet, „{values[key]}“ gefunden") from exc


def _int_eur(values: dict[str, str], key: str) -> int:
    return round(_float(values, key))


def _parse_kennwerte(values: dict[str, str]) -> TypeSheetData:
    roof_form = values["dachform"].strip().lower()
    if roof_form not in ROOF_FORMS:
        raise TypeWorkbookInvalid(f"Kennwerte!dachform: „{values['dachform']}“ nicht in {ROOF_FORMS}")

    pitch_deg: float | None = None
    if values.get("neigung_deg"):
        pitch_deg = _float(values, "neigung_deg")
    ridge_direction: str | None = None
    if values.get("firstrichtung"):
        ridge_direction = values["firstrichtung"].strip().lower()
        if ridge_direction not in RIDGE_DIRECTIONS:
            raise TypeWorkbookInvalid(f"Kennwerte!firstrichtung: nicht in {RIDGE_DIRECTIONS}")

    base_min = _int_eur(values, "basispreis_min_eur")
    base_max = _int_eur(values, "basispreis_max_eur")
    if base_min <= 0 or base_max < base_min:
        raise TypeWorkbookInvalid("Kennwerte!basispreis_min_eur/basispreis_max_eur: ungültige Spanne")

    return TypeSheetData(
        name=values["name"],
        family=values.get("familie") or None,
        storeys=values["geschosse"],
        roof_form=roof_form,
        pitch_deg=pitch_deg,
        ridge_direction=ridge_direction,
        ridge_height_m=_float(values, "firsthoehe_m"),
        eave_height_m=_float(values, "traufhoehe_m"),
        living_area_m2=_float(values, "wohnflaeche_m2"),
        rooms_text=values["zimmer_text"],
        base_price_min_eur=base_min,
        base_price_max_eur=base_max,
        rooms=[],
        prices=[],
    )


def _header_index(sheet: Worksheet, expected: tuple[str, ...]) -> dict[str, int]:
    header = [str(c.value).strip() if c.value is not None else "" for c in next(sheet.iter_rows(max_row=1))]
    missing = [col for col in expected if col not in header]
    if missing:
        raise TypeWorkbookInvalid(f"{sheet.title}: Spalte(n) fehlen: {', '.join(missing)}")
    return {col: header.index(col) for col in expected}


def _read_rooms(sheet: Worksheet) -> list[RoomEntry]:
    idx = _header_index(sheet, _RAEUME_COLUMNS)
    rooms: list[RoomEntry] = []
    for r, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if row[idx["name"]] is None:
            continue
        category = str(row[idx["kategorie"]] or "").strip().lower()
        if category not in ROOM_CATEGORIES:
            raise TypeWorkbookInvalid(f"Räume!B{r}: „{category}“ nicht in {ROOM_CATEGORIES}")
        try:
            area = float(row[idx["flaeche_m2"]])
        except (TypeError, ValueError) as exc:
            raise TypeWorkbookInvalid(f"Räume!D{r}: Zahl erwartet") from exc
        if area <= 0:
            raise TypeWorkbookInvalid(f"Räume!D{r}: Fläche muss positiv sein")
        rooms.append(
            RoomEntry(
                name=str(row[idx["name"]]),
                category=category,
                storey=str(row[idx["geschoss"]] or ""),
                area_m2=area,
            )
        )
    if not rooms:
        raise TypeWorkbookInvalid("Räume: keine Zeile mit Inhalt")
    return rooms


def _read_prices(sheet: Worksheet) -> list[PriceEntry]:
    idx = _header_index(sheet, _PREISE_COLUMNS)
    prices: list[PriceEntry] = []
    for r, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if row[idx["art"]] is None:
            continue
        kind = str(row[idx["art"]]).strip().lower()
        if kind not in PRICE_KINDS:
            raise TypeWorkbookInvalid(f"Preise!A{r}: „{kind}“ nicht in {PRICE_KINDS}")
        reference = row[idx["referenz"]]
        reference = str(reference).strip() if reference is not None else None
        if not reference:
            raise TypeWorkbookInvalid(f"Preise!B{r}: Referenz fehlt für Art „{kind}“")
        try:
            surcharge = round(float(row[idx["aufpreis_eur"]]))
        except (TypeError, ValueError) as exc:
            raise TypeWorkbookInvalid(f"Preise!C{r}: Zahl erwartet") from exc
        prices.append(PriceEntry(kind=kind, reference=reference, surcharge_eur=surcharge))
    return prices


def read_type_workbook(data: bytes) -> TypeSheetData:
    try:
        workbook = load_workbook(BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises plain Exception/zipfile errors on corrupt files
        raise TypeWorkbookInvalid("Datei ist keine gültige XLSX-Arbeitsmappe") from exc

    kennwerte = _parse_kennwerte(_read_kennwerte(_sheet(workbook, "Kennwerte")))
    rooms = _read_rooms(_sheet(workbook, "Räume"))
    prices = _read_prices(_sheet(workbook, "Preise"))
    return TypeSheetData(
        name=kennwerte.name,
        family=kennwerte.family,
        storeys=kennwerte.storeys,
        roof_form=kennwerte.roof_form,
        pitch_deg=kennwerte.pitch_deg,
        ridge_direction=kennwerte.ridge_direction,
        ridge_height_m=kennwerte.ridge_height_m,
        eave_height_m=kennwerte.eave_height_m,
        living_area_m2=kennwerte.living_area_m2,
        rooms_text=kennwerte.rooms_text,
        base_price_min_eur=kennwerte.base_price_min_eur,
        base_price_max_eur=kennwerte.base_price_max_eur,
        rooms=rooms,
        prices=prices,
    )
