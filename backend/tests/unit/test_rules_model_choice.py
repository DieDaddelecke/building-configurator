"""KI-Modell der Auswertung: Liste von OpenRouter filtern und vorhalten, Preise (PLAN_AN2_PLU 8, PU11)."""

from collections.abc import Iterator

import httpx2
import pytest

from app.config import Settings
from app.integrations.http import ExternalServiceError, new_client
from app.integrations.openrouter import prices
from app.rules import model_choice
from tests.rules_model_support import LISTING


@pytest.fixture(autouse=True)
def empty_cache() -> Iterator[None]:
    model_choice.clear_cache()
    yield
    model_choice.clear_cache()


def test_only_models_that_force_a_tool_with_a_fixed_name_and_price() -> None:
    options = model_choice.parse_models(LISTING)
    ids = [o.id for o in options]
    assert ids == ["anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5", "openai/text-only"]
    # Ohne PDF-Eingabe wählbar, aber mit der Textschicht (PU12)
    assert [o.reads_pdf for o in options] == [True, True, False]
    opus = options[0]
    # Preise je Token → je Million Token
    assert (opus.price_input_per_mtok, opus.price_output_per_mtok) == (4.0, 20.0)
    assert (opus.price_cache_read_per_mtok, opus.price_cache_write_per_mtok) == (0.4, 5.0)
    assert options[1].price_cache_read_per_mtok is None
    assert model_choice.parse_models({"unerwartet": True}) == []


def test_the_listing_is_fetched_without_a_key_and_kept_for_an_hour() -> None:
    calls: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(200, json=LISTING)

    settings = Settings(openrouter_api_key=None)
    client = new_client(settings, httpx2.MockTransport(handler))
    clock = [1000.0]
    first = model_choice.available_models(client, settings, now=lambda: clock[0])
    clock[0] += 3599
    assert model_choice.available_models(client, settings, now=lambda: clock[0]) == first
    assert len(calls) == 1 and "authorization" not in calls[0].headers
    assert str(calls[0].url) == "https://openrouter.ai/api/v1/models"
    clock[0] += 2
    model_choice.available_models(client, settings, now=lambda: clock[0])
    assert len(calls) == 2


def test_a_listing_without_usable_models_counts_as_unavailable() -> None:
    settings = Settings()
    client = new_client(settings, httpx2.MockTransport(lambda r: httpx2.Response(200, json={"data": []})))
    with pytest.raises(ExternalServiceError):
        model_choice.available_models(client, settings)


def test_cache_prices_from_the_listing_replace_the_derived_ones() -> None:
    derived = prices(Settings(rules_price_input_per_mtok=4.0, rules_price_output_per_mtok=20.0))
    assert (derived.cache_read, derived.cache_write_1h) == pytest.approx((0.4, 8.0))
    listed = prices(
        Settings(
            rules_price_input_per_mtok=4.0,
            rules_price_output_per_mtok=20.0,
            rules_price_cache_read_per_mtok=0.3,
            rules_price_cache_write_per_mtok=5.0,
        )
    )
    assert (listed.cache_read, listed.cache_write_1h) == (0.3, 5.0)
