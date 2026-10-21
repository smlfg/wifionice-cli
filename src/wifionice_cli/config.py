"""Configuration: environment variables override the JSON config file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wifionice_cli import exit_codes as ec
from wifionice_cli.errors import CliError
from wifionice_cli.json_util import loads

ENV_PREFIX = "WIFIONICE_"
ENV_BASE_URL = f"{ENV_PREFIX}BASE_URL"
ENV_ICEPORTAL_URL = f"{ENV_PREFIX}ICEPORTAL_URL"
ENV_STATE = f"{ENV_PREFIX}STATE"
ENV_TIMEOUT = f"{ENV_PREFIX}TIMEOUT"
ENV_RETRIES = f"{ENV_PREFIX}RETRIES"
CONFIG_FILE_ENV = f"{ENV_PREFIX}CONFIG"

DEFAULT_BASE_URL = "https://wifi.bahn.de"
DEFAULT_ICEPORTAL_URL = "https://iceportal.de"
DEFAULT_TIMEOUT = 5.0
DEFAULT_RETRIES = 2
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "wifionice" / "config.json"
DEFAULT_STATE_PATH = Path.home() / ".local" / "state" / "wifionice" / "session.json"


@dataclass
class ResolvedConfig:
    base_url: str
    iceportal_url: str
    state_path: Path
    timeout: float
    retries: int
    sources: dict[str, str] = field(default_factory=dict)


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(f"invalid config file: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if not isinstance(data, dict):
        raise CliError(f"config file must be a JSON object: {path}", code=ec.PARSE)
    return data


def _parse_retries(value: str | int, *, source: str) -> int:
    try:
        retries = int(value)
    except (TypeError, ValueError):
        raise CliError(f"retries must be a positive integer, got {value!r} ({source})", code=ec.INPUT) from None
    if retries < 1:
        raise CliError(f"retries must be at least 1, got {retries} ({source})", code=ec.INPUT)
    return retries


def _parse_timeout(value: str | float, *, source: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        raise CliError(f"timeout must be a number, got {value!r} ({source})", code=ec.INPUT) from None
    if timeout <= 0:
        raise CliError(f"timeout must be positive, got {timeout} ({source})", code=ec.INPUT)
    return timeout


def resolve_config(
    *,
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> ResolvedConfig:
    """Merge config with precedence: environment > config file > built-in defaults."""
    environ = os.environ if env is None else env
    sources: dict[str, str] = {}

    file_path = config_path
    if file_path is None and environ.get(CONFIG_FILE_ENV):
        file_path = Path(environ[CONFIG_FILE_ENV])
    if file_path is None:
        file_path = DEFAULT_CONFIG_PATH
    file_data = _load_file(file_path)
    if file_data:
        sources["file"] = str(file_path)

    base_url = environ.get(ENV_BASE_URL)
    if base_url:
        sources["base_url"] = "env"
    elif file_data.get("base_url"):
        base_url = str(file_data["base_url"])
        sources["base_url"] = "file"
    else:
        base_url = DEFAULT_BASE_URL
        sources["base_url"] = "default"

    iceportal_url = environ.get(ENV_ICEPORTAL_URL)
    if iceportal_url:
        sources["iceportal_url"] = "env"
    elif file_data.get("iceportal_url"):
        iceportal_url = str(file_data["iceportal_url"])
        sources["iceportal_url"] = "file"
    else:
        iceportal_url = DEFAULT_ICEPORTAL_URL
        sources["iceportal_url"] = "default"

    state_raw = environ.get(ENV_STATE)
    if state_raw:
        state_path = Path(state_raw)
        sources["state_path"] = "env"
    elif file_data.get("state_path"):
        state_path = Path(str(file_data["state_path"]))
        sources["state_path"] = "file"
    else:
        state_path = DEFAULT_STATE_PATH
        sources["state_path"] = "default"

    timeout_raw = environ.get(ENV_TIMEOUT)
    if timeout_raw is not None:
        timeout = _parse_timeout(timeout_raw, source=ENV_TIMEOUT)
        sources["timeout"] = "env"
    elif file_data.get("timeout") is not None:
        timeout = _parse_timeout(file_data["timeout"], source="config file")
        sources["timeout"] = "file"
    else:
        timeout = DEFAULT_TIMEOUT
        sources["timeout"] = "default"

    retries_raw = environ.get(ENV_RETRIES)
    if retries_raw is not None:
        retries = _parse_retries(retries_raw, source=ENV_RETRIES)
        sources["retries"] = "env"
    elif file_data.get("retries") is not None:
        retries = _parse_retries(file_data["retries"], source="config file")
        sources["retries"] = "file"
    else:
        retries = DEFAULT_RETRIES
        sources["retries"] = "default"

    return ResolvedConfig(
        base_url=str(base_url).rstrip("/"),
        iceportal_url=str(iceportal_url).rstrip("/"),
        state_path=state_path,
        timeout=timeout,
        retries=retries,
        sources=sources,
    )
