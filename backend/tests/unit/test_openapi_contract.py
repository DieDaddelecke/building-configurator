"""Die eingecheckte `openapi.json` ist die Quelle des Frontend-Clients und muss zum Code passen."""

import json
from pathlib import Path

from app.main import create_full_app

OPENAPI_FILE = Path(__file__).resolve().parents[2] / "openapi.json"


def test_committed_openapi_matches_code() -> None:
    generated = create_full_app().openapi()
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))
    assert generated == committed, "openapi.json veraltet: python -m app.cli openapi openapi.json"


def test_no_single_total_price_field() -> None:
    """L1: Kein Feld, das als exakter Gesamtpreis gelesen werden kann."""
    text = OPENAPI_FILE.read_text(encoding="utf-8").lower()
    for forbidden in ('"total"', '"total_price"', '"price_total"'):
        assert forbidden not in text
