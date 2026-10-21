import json
from pathlib import Path

from wifionice_cli import exit_codes as ec
from wifionice_cli.config import (
    ENV_BASE_URL,
    ENV_ICEPORTAL_URL,
    ENV_STATE,
    ENV_TIMEOUT,
    resolve_config,
)
from wifionice_cli.errors import CliError


def _clear(monkeypatch):
    for name in (ENV_BASE_URL, ENV_ICEPORTAL_URL, ENV_STATE, ENV_TIMEOUT):
        monkeypatch.delenv(name, raising=False)


def test_env_overrides_file(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "base_url": "https://file.example",
                "iceportal_url": "https://ice.file.example",
                "state_path": str(tmp_path / "file-state.json"),
                "timeout": 9,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_BASE_URL, "https://env.example")
    monkeypatch.setenv(ENV_ICEPORTAL_URL, "https://ice.env.example")
    monkeypatch.setenv(ENV_STATE, str(tmp_path / "env-state.json"))
    monkeypatch.setenv(ENV_TIMEOUT, "2.5")
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://env.example"
    assert cfg.iceportal_url == "https://ice.env.example"
    assert cfg.state_path == tmp_path / "env-state.json"
    assert cfg.timeout == 2.5
    assert cfg.sources["base_url"] == "env"
    assert cfg.sources["timeout"] == "env"


def test_file_used_when_no_env(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://file.example", "timeout": 7}),
        encoding="utf-8",
    )
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://file.example"
    assert cfg.sources["base_url"] == "file"
    assert cfg.timeout == 7.0


def test_defaults_when_nothing_set(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    cfg = resolve_config(config_path=tmp_path / "missing.json")
    assert cfg.base_url == "https://wifi.bahn.de"
    assert cfg.iceportal_url == "https://iceportal.de"
    assert cfg.sources["base_url"] == "default"


def test_invalid_base_url_is_input_error(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(ENV_BASE_URL, "not-a-url")
    try:
        resolve_config(config_path=tmp_path / "missing.json")
    except CliError as e:
        assert e.code == ec.INPUT
        assert "base_url" in e.message.lower() or "BASE_URL" in str(e.message)
    else:
        raise AssertionError("expected CliError")


def test_invalid_timeout_is_input_error(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(ENV_TIMEOUT, "abc")
    try:
        resolve_config(config_path=tmp_path / "missing.json")
    except CliError as e:
        assert e.code == ec.INPUT
    else:
        raise AssertionError("expected CliError")


def test_nan_timeout_env_is_input_error(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(ENV_TIMEOUT, "nan")
    try:
        resolve_config(config_path=tmp_path / "missing.json")
    except CliError as e:
        assert e.code == ec.INPUT
        assert "finite" in e.message.lower()
    else:
        raise AssertionError("expected CliError")


def test_broken_config_file_is_parse_error(tmp_path: Path, monkeypatch):
    _clear(monkeypatch)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{not json", encoding="utf-8")
    try:
        resolve_config(config_path=cfg_file)
    except CliError as e:
        assert e.code == ec.PARSE
    else:
        raise AssertionError("expected CliError")
