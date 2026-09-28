"""KI-Modell der Auswertung wählen (docs/PLAN_AN2_PLU.md 8, ANNAHMEN PU11); seit VA09 in der gemeinsamen
Datenbank beider Produkte. In Tests liegt sie in der Testdatenbank (keine eigene Verbindung)."""

import uuid
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.integrations.http import new_client, shared_client
from app.platform.models import AppSetting, StaffUser
from app.platform.shared import SharedAudit, SharedSetting
from app.rules import extract, jobs, model_choice
from tests.rules_model_support import LISTING

DEFAULT = get_settings().rules_model


@pytest.fixture
def openrouter(app: Any) -> Iterator[list[int]]:
    """Liste von OpenRouter ohne Netz; `status[0]` steuert die Antwort (200 oder Störung)."""
    status = [200]

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status[0], json=LISTING if status[0] == 200 else {})

    model_choice.clear_cache()
    transport = httpx2.MockTransport(handler)
    app.dependency_overrides[shared_client] = lambda: new_client(get_settings(), transport)
    yield status
    model_choice.clear_cache()


def test_architect_sees_the_default_but_cannot_change_it(
    client: Any, login_as: Callable[..., Any], openrouter: list[int]
) -> None:
    login_as("architect")
    body = client.get("/api/v1/admin/rules/model").json()
    assert (body["model"], body["source"], body["default_model"]) == (DEFAULT, "default", DEFAULT)
    assert body["updated_at"] is None and body["budget_month_usd"] > 0
    assert client.get("/api/v1/admin/rules/models").status_code == 403
    change = client.put("/api/v1/admin/rules/model", json={"model": "anthropic/claude-sonnet-5"})
    assert change.status_code == 403


def test_operator_chooses_a_model_for_all_future_evaluations(
    client: Any, login_as: Callable[..., Any], openrouter: list[int], db_session: Any
) -> None:
    login_as("ops")
    listed = client.get("/api/v1/admin/rules/models").json()
    ids = ["anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5", "openai/text-only"]
    assert [m["id"] for m in listed] == ids
    assert [m["reads_pdf"] for m in listed] == [True, True, False]

    chosen = client.put("/api/v1/admin/rules/model", json={"model": "anthropic/claude-opus-5.5"})
    assert chosen.status_code == 200, chosen.json()
    body = chosen.json()
    assert (body["model"], body["source"]) == ("anthropic/claude-opus-5.5", "setting")
    assert (body["price_input_per_mtok"], body["price_output_per_mtok"]) == (4.0, 20.0)
    assert body["updated_at"] is not None and body["input"] == "pdf"
    # Die Abdeckung (Seite „Regelwerke“) nennt ebenfalls das gewählte Modell
    assert client.get("/api/v1/admin/rules/coverage").json()["model"] == "anthropic/claude-opus-5.5"

    effective = model_choice.effective_settings(db_session, get_settings())
    assert effective.rules_model == "anthropic/claude-opus-5.5"
    assert effective.rules_price_cache_read_per_mtok == 0.4
    audit = db_session.execute(
        select(SharedAudit).where(SharedAudit.action == "rules_model_changed")
    ).scalar_one()
    assert (audit.before, audit.after) == ({"model": DEFAULT}, {"model": "anthropic/claude-opus-5.5"})
    assert audit.product == "configurator" and audit.actor_id.startswith("configurator:")
    setting = db_session.get(SharedSetting, model_choice.SETTING_KEY)
    assert setting.updated_by_name and body["updated_by_name"] == setting.updated_by_name

    # Die Vorgabe der Umgebung hebt die Wahl auf – auch ohne Liste von OpenRouter
    openrouter[0] = 502
    back = client.put("/api/v1/admin/rules/model", json={"model": DEFAULT}).json()
    assert (back["model"], back["source"]) == (DEFAULT, "default")
    db_session.expire_all()
    assert db_session.get(SharedSetting, model_choice.SETTING_KEY) is None


def test_a_model_without_pdf_input_gets_the_text_layer(
    client: Any, login_as: Callable[..., Any], openrouter: list[int], db_session: Any
) -> None:
    login_as("ops")
    body = client.put("/api/v1/admin/rules/model", json={"model": "openai/text-only"}).json()
    assert (body["model"], body["input"]) == ("openai/text-only", "text")
    assert model_choice.effective_settings(db_session, get_settings()).rules_input == "text"


def test_unknown_model_and_missing_listing_are_refused(
    client: Any, login_as: Callable[..., Any], openrouter: list[int]
) -> None:
    login_as("rules_admin")
    unknown = client.put("/api/v1/admin/rules/model", json={"model": "anthropic/claude-opus-5.5:batch"})
    assert unknown.status_code == 422 and unknown.json()["code"] == "model_not_available"
    openrouter[0] = 502
    model_choice.clear_cache()
    assert client.get("/api/v1/admin/rules/models").json()["code"] == "models_unavailable"
    down = client.put("/api/v1/admin/rules/model", json={"model": "anthropic/claude-sonnet-5"})
    assert down.status_code == 503
    assert client.get("/api/v1/admin/rules/model").json()["source"] == "default"


def test_the_evaluation_job_uses_the_chosen_model_from_its_start(
    client: Any,
    login_as: Callable[..., Any],
    openrouter: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_as("ops")
    client.put("/api/v1/admin/rules/model", json={"model": "anthropic/claude-sonnet-5"})
    seen: dict[str, Any] = {}

    def fake_extract(sessions: Any, settings: Any, chapter_id: uuid.UUID, factory: Any, **kwargs: Any) -> Any:
        seen["settings"], seen["factory"] = settings, factory
        return extract.ChapterOutcome("succeeded")

    monkeypatch.setattr(extract, "extract_chapter", fake_extract)
    jobs.rules_extract(SimpleNamespace(attempt=1), {"chapter_id": str(uuid.uuid4())})  # type: ignore[arg-type]
    settings = seen["settings"]
    assert (settings.rules_model, settings.rules_price_input_per_mtok) == ("anthropic/claude-sonnet-5", 2.0)
    # Eingabe-Hash und Kosten hängen am gewählten Modell; der Aufruf nutzt dieselben Einstellungen
    assert settings.rules_price_output_per_mtok == 10.0


def test_shared_migrate_moves_the_instance_choice_once(
    db_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine Wahl aus PU11 (`app_setting`) zieht beim Migrate-Job in die gemeinsame Datenbank (VA09)."""
    from app import cli

    value = {"model": "anthropic/claude-sonnet-5", "price_input_per_mtok": 2.0, "price_output_per_mtok": 10.0}
    staff = StaffUser(email="sarah@emprise.local", display_name="Sarah", roles=["ops"])
    db_session.add(staff)
    db_session.flush()
    db_session.add(AppSetting(key=model_choice.SETTING_KEY, value=value, updated_by=str(staff.id)))
    db_session.commit()
    cli._move_model_setting(get_settings())
    db_session.expire_all()
    assert db_session.get(AppSetting, model_choice.SETTING_KEY) is None
    moved = db_session.get(SharedSetting, model_choice.SETTING_KEY)
    assert moved is not None and moved.value["model"] == "anthropic/claude-sonnet-5"
    assert moved.updated_by_name == "Sarah"
    assert (
        model_choice.effective_settings(db_session, get_settings()).rules_model == "anthropic/claude-sonnet-5"
    )
    # Eine zweite Instanz mit eigener Wahl: die gemeinsame gilt, die eigene entfällt
    db_session.add(
        AppSetting(key=model_choice.SETTING_KEY, value={**value, "model": "x/y"}, updated_by="staff-2")
    )
    db_session.commit()
    cli._move_model_setting(get_settings())
    db_session.expire_all()
    assert (
        db_session.get(SharedSetting, model_choice.SETTING_KEY).value["model"] == "anthropic/claude-sonnet-5"
    )
    assert "verworfen" in capsys.readouterr().out
