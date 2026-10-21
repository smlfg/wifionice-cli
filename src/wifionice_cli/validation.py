"""Input validation helpers; raise :class:`~wifionice_cli.errors.CliError` on failure."""

from __future__ import annotations

import math
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any

from wifionice_cli import exit_codes as ec
from wifionice_cli.errors import CliError


def require_absolute_http_url(value: str, *, name: str = "url") -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise CliError(
            f"{name} must be an absolute http or https URL, got {value!r}",
            code=ec.INPUT,
        )
    return value


def require_positive_int(value: int | str, *, name: str = "value") -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise CliError(f"{name} must be a positive integer", code=ec.INPUT) from None
    if n <= 0:
        raise CliError(f"{name} must be positive, got {n}", code=ec.INPUT)
    return n


def require_non_negative_int(value: int | str, *, name: str = "value") -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise CliError(f"{name} must be a non-negative integer", code=ec.INPUT) from None
    if n < 0:
        raise CliError(f"{name} must be non-negative, got {n}", code=ec.INPUT)
    return n


def require_finite_number(value: float, *, name: str = "value") -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CliError(f"{name} must be a number", code=ec.INPUT)
    if not math.isfinite(float(value)):
        raise CliError(f"{name} must be finite", code=ec.INPUT)
    return float(value)


def reject_nan_in_json_tree(obj: Any, *, path: str = "$") -> None:
    """Reject NaN/Infinity inside structures before persisting or emitting JSON."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CliError(f"non-finite number at {path}", code=ec.INPUT)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            reject_nan_in_json_tree(v, path=f"{path}.{k}")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            reject_nan_in_json_tree(v, path=f"{path}[{i}]")


def parse_date(value: str, *, name: str = "date") -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CliError(f"{name} must be ISO date (YYYY-MM-DD), got {value!r}", code=ec.INPUT) from None


def parse_datetime(value: str, *, name: str = "datetime") -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CliError(
            f"{name} must be ISO-8601 datetime, got {value!r}",
            code=ec.INPUT,
        ) from None


def require_file(path: Path | str, *, name: str = "path") -> Path:
    p = Path(path)
    if not p.is_file():
        raise CliError(f"{name} must be an existing file: {p}", code=ec.INPUT)
    return p


def require_directory(path: Path | str, *, name: str = "path") -> Path:
    p = Path(path)
    if not p.is_dir():
        raise CliError(f"{name} must be an existing directory: {p}", code=ec.INPUT)
    return p


def require_existing_path(path: Path | str, *, name: str = "path") -> Path:
    p = Path(path)
    if not p.exists():
        raise CliError(f"{name} does not exist: {p}", code=ec.INPUT)
    return p
