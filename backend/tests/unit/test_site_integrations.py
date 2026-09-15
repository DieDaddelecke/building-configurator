"""Vertragstests der Adapter mit aufgezeichneten Antworten vom 14.09.2026 (Spez. 9, 11.1)."""

import gzip
import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from app.config import get_settings
from app.integrations import geoplateforme, georisques, http, ign_bdtopo
from app.integrations.http import ExternalServiceError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "site"


def load(name: str) -> Any:
    raw = (FIXTURES / name).read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)


def test_geocode_search_parses_lambert93_and_citycode() -> None:
    candidates = geoplateforme.parse_search(load("geocode_search.json"))
    first = candidates[0]
    assert first.label == "8 Rue des chênes 44119 Treillières"
    assert (first.citycode, first.kind) == ("44209", "housenumber")
    assert first.x == pytest.approx(352711.4) and first.lon == pytest.approx(-1.596965)


def test_elevations_with_missing_values() -> None:
    assert geoplateforme.parse_elevations(load("altimetry.json"), 3) == [52.83, 52.92, 52.89]
    missing = {"elevations": [{"z": -99999}, {"z": 10.5}]}
    assert geoplateforme.parse_elevations(missing, 2) == [None, 10.5]
    with pytest.raises(ExternalServiceError):
        geoplateforme.parse_elevations(missing, 3)


def test_georisques_report_levels_and_scope() -> None:
    items = {i.kind: i for i in georisques.parse_report(load("georisques_report.json"))}
    assert items["radon"].level == "high"
    assert items["seismic"].level in ("moderate", "low")
    assert all(i.level in ("low", "moderate", "high", "present", "unknown") for i in items.values())
    assert georisques.parse_rga(load("georisques_rga.json")) == georisques.RiskItem(
        "clay_shrink_swell", "low", "address", "Exposition faible"
    )
    assert georisques.parse_rga({"codeExposition": "0"}) is None


def test_georisques_unexpected_report_shape_is_a_service_error() -> None:
    """Sonst bräche der Job mit einer beliebigen Ausnahme ab statt „nicht abgefragt“ zu melden."""
    with pytest.raises(ExternalServiceError):
        georisques.parse_report({"risquesNaturels": None, "risquesTechnologiques": {}})
    assert georisques.parse_report({"risquesNaturels": {"radon": None}, "risquesTechnologiques": {}}) == []


@pytest.mark.parametrize(
    ("status", "level"),
    [
        ("Risque Existant - important", "high"),
        ("Risque Existant - modéré", "moderate"),
        ("Risque Existant - faible", "low"),
        ("Risque Existant", "present"),
        ("Risque Concerne", "present"),
        ("Risque Inconnu", "unknown"),
        ("Risque non Connu", "unknown"),
        (None, None),
    ],
)
def test_georisques_status_mapping(status: str | None, level: str | None) -> None:
    assert georisques.level_from_status(status) == level


def test_bdtopo_parser_drops_fictive_and_tunnels() -> None:
    segments = ign_bdtopo.parse(load("bdtopo-44209-troncons.json.gz"))
    assert segments and all(len(s.coords) >= 2 for s in segments)
    assert "Rue des chênes" in {s.name for s in segments}
    synthetic = {
        "features": [
            {
                "properties": {"fictif": True},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
            {
                "properties": {"position_par_rapport_au_sol": "-1", "nature": "Route à 1 chaussée"},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
            {
                "properties": {"nature": "Sentier"},
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
        ]
    }
    assert ign_bdtopo.parse(synthetic) == []


def test_http_retries_server_errors_but_not_client_errors() -> None:
    calls: list[int] = []

    def flaky(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(503 if len(calls) == 1 else 200, json={"ok": True})

    with http.new_client(get_settings(), httpx2.MockTransport(flaky)) as client:
        assert http.get_json(client, "test", "https://example.test/a") == {"ok": True}
    assert len(calls) == 2

    not_found = httpx2.MockTransport(lambda r: httpx2.Response(404))
    with (
        http.new_client(get_settings(), not_found) as client,
        pytest.raises(ExternalServiceError, match="http_404"),
    ):
        http.get(client, "test", "https://example.test/b", attempts=3)
