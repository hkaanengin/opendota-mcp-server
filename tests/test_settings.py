import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from opendota_mcp.settings import Settings

MakeSettings = Callable[..., Settings]


def test_defaults_need_no_configuration(make_settings: MakeSettings) -> None:
    settings = make_settings()

    assert settings.opendota_api_key is None
    assert settings.opendota_rate_limit_rpm is None
    assert settings.opendota_player_aliases == {}
    assert settings.mcp_transport == "stdio"
    assert settings.port == 8080
    assert settings.mcp_auth_token is None
    assert settings.log_level == "INFO"


def test_every_setting_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, make_settings: MakeSettings
) -> None:
    monkeypatch.setenv("OPENDOTA_API_KEY", "key-123")
    monkeypatch.setenv("OPENDOTA_RATE_LIMIT_RPM", "120")
    monkeypatch.setenv("OPENDOTA_PLAYER_ALIASES", "Me=123456, Friend = 789012")
    monkeypatch.setenv("MCP_TRANSPORT", "HTTP")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "token-abc")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = make_settings()

    assert settings.opendota_api_key is not None
    assert settings.opendota_api_key.get_secret_value() == "key-123"
    assert settings.opendota_rate_limit_rpm == 120
    assert settings.opendota_player_aliases == {"me": 123456, "friend": 789012}
    assert settings.mcp_transport == "http"
    assert settings.port == 9000
    assert settings.mcp_auth_token is not None
    assert settings.mcp_auth_token.get_secret_value() == "token-abc"
    assert settings.log_level == "DEBUG"


def test_secrets_never_show_in_the_settings_repr(
    monkeypatch: pytest.MonkeyPatch, make_settings: MakeSettings
) -> None:
    monkeypatch.setenv("OPENDOTA_API_KEY", "key-123")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "token-abc")

    shown = repr(make_settings())

    assert "key-123" not in shown
    assert "token-abc" not in shown


def test_empty_values_fall_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch, make_settings: MakeSettings
) -> None:
    for var in ("OPENDOTA_API_KEY", "OPENDOTA_RATE_LIMIT_RPM", "OPENDOTA_PLAYER_ALIASES", "PORT"):
        monkeypatch.setenv(var, "")

    settings = make_settings()

    assert settings.opendota_api_key is None
    assert settings.opendota_rate_limit_rpm is None
    assert settings.opendota_player_aliases == {}
    assert settings.port == 8080


def test_player_aliases_can_come_from_a_json_file(
    monkeypatch: pytest.MonkeyPatch, make_settings: MakeSettings, tmp_path: Path
) -> None:
    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({"Me": 123456, "kürlo": "789012"}))
    monkeypatch.setenv("OPENDOTA_PLAYER_ALIASES", str(alias_file))

    assert make_settings().opendota_player_aliases == {"me": 123456, "kürlo": 789012}


def test_settings_are_read_from_a_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENDOTA_API_KEY=from-dotenv\nOPENDOTA_PLAYER_ALIASES=me=123456\n")

    settings = Settings(_env_file=env_file)

    assert settings.opendota_api_key is not None
    assert settings.opendota_api_key.get_secret_value() == "from-dotenv"
    assert settings.opendota_player_aliases == {"me": 123456}


@pytest.mark.parametrize(
    ("var", "value", "complaint"),
    [
        ("MCP_TRANSPORT", "sse", "mcp_transport"),
        ("PORT", "eighty", "port"),
        ("PORT", "70000", "port"),
        ("OPENDOTA_RATE_LIMIT_RPM", "0", "opendota_rate_limit_rpm"),
        ("LOG_LEVEL", "LOUD", "log_level"),
        ("OPENDOTA_PLAYER_ALIASES", "me=123456,friend", "malformed alias 'friend'"),
        ("OPENDOTA_PLAYER_ALIASES", "me=not-a-number", "opendota_player_aliases"),
        ("OPENDOTA_PLAYER_ALIASES", "=123456", "malformed alias '=123456'"),
        ("OPENDOTA_PLAYER_ALIASES", "/nowhere/aliases.json", "not found"),
    ],
)
def test_invalid_settings_fail_at_startup_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: MakeSettings,
    var: str,
    value: str,
    complaint: str,
) -> None:
    monkeypatch.setenv(var, value)

    with pytest.raises(ValidationError) as error:
        make_settings()

    assert complaint in str(error.value)


def test_an_alias_file_that_is_not_json_fails_at_startup(
    monkeypatch: pytest.MonkeyPatch, make_settings: MakeSettings, tmp_path: Path
) -> None:
    alias_file = tmp_path / "aliases.json"
    alias_file.write_text("me: 123456")
    monkeypatch.setenv("OPENDOTA_PLAYER_ALIASES", str(alias_file))

    with pytest.raises(ValidationError, match="is not valid JSON"):
        make_settings()
