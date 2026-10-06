"""Every setting the server reads, validated once at startup."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    opendota_api_key: SecretStr | None = None
    opendota_rate_limit_rpm: PositiveInt | None = None
    opendota_player_aliases: Annotated[dict[str, PositiveInt], NoDecode] = {}
    """Player alias (lowercased) → Account ID."""
    mcp_transport: Literal["stdio", "http"] = "stdio"
    port: int = Field(default=8080, ge=1, le=65535)
    mcp_auth_token: SecretStr | None = None
    log_level: LogLevel = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("mcp_transport", mode="before")
    @classmethod
    def _normalize_transport(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("opendota_player_aliases", mode="before")
    @classmethod
    def _parse_aliases(cls, value: Any) -> Any:
        """Accept `name=id,name=id` inline, or the path to a JSON object of name → id."""
        if not isinstance(value, str):
            return _lowercase_keys(value)
        text = value.strip()
        if not text:
            return {}
        if "=" not in text:
            return _lowercase_keys(_read_alias_file(Path(text)))
        aliases: dict[str, str] = {}
        for pair in text.split(","):
            name, sep, account_id = pair.partition("=")
            if not sep or not name.strip() or not account_id.strip():
                raise ValueError(
                    f"malformed alias {pair.strip()!r}: expected name=account_id, "
                    "e.g. 'me=123456,friend=789012'"
                )
            aliases[name.strip().lower()] = account_id.strip()
        return aliases


def _read_alias_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise ValueError(
            f"alias file {str(path)!r} not found (expected name=account_id pairs "
            "or the path to a JSON file)"
        ) from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"alias file {str(path)!r} is not valid JSON: {exc}") from None


def _lowercase_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(name).strip().lower(): account_id for name, account_id in value.items()}
    return value
