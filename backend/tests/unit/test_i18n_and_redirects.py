import pytest

from app.platform.auth.staff import safe_next
from app.platform.i18n import parse_accept_language, translate


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "fr"),
        ("", "fr"),
        ("de-DE,de;q=0.9", "de"),
        ("en-US,en;q=0.9", "fr"),
        ("en;q=1, de;q=0.5, fr;q=0.8", "fr"),
        ("de;q=0.9, fr-FR;q=0.2", "de"),
        ("de;q=abc, fr", "fr"),
    ],
)
def test_accept_language(header: str | None, expected: str) -> None:
    assert parse_accept_language(header) == expected


def test_translate_falls_back_to_french_and_key() -> None:
    assert translate("problem.not_found", "de") == "Nicht gefunden"
    assert translate("does.not.exist", "de") == "does.not.exist"
    assert "Umgebung: test" in translate("mail.platform_test.body", "de", env="test")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/buero"),
        ("/buero/regeln", "/buero/regeln"),
        ("https://evil.example/buero", "/buero"),
        ("//evil.example/buero", "/buero"),
        ("/\\evil.example", "/buero"),
        ("/projekt", "/buero"),
    ],
)
def test_safe_next_prevents_open_redirect(value: str | None, expected: str) -> None:
    assert safe_next(value) == expected
