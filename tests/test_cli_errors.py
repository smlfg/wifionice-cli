"""Error-path templates: subprocess CLI, no network, isolated config/state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from wifionice_cli import exit_codes as ec

ROOT = Path(__file__).resolve().parents[1]


def run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["WIFIONICE_CONFIG"] = str(tmp_path / "no-config.json")
    env["WIFIONICE_STATE"] = str(tmp_path / "session.json")
    return subprocess.run(
        [sys.executable, "-m", "wifionice_cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_unknown_flag_exit_input(tmp_path: Path):
    proc = run_cli(tmp_path, "--json", "--nope")
    assert proc.returncode == ec.INPUT
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.INPUT
    assert len(proc.stdout.strip().splitlines()) == 1


def test_checkin_missing_accept_terms_human(tmp_path: Path):
    proc = run_cli(tmp_path, "checkin")
    assert proc.returncode == ec.INPUT
    assert proc.stderr.strip()
    assert "--accept-terms" in proc.stderr


def test_version_json_is_single_object(tmp_path: Path):
    proc = run_cli(tmp_path, "version", "--json")
    assert proc.returncode == ec.OK
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["version"]


def test_config_shows_defaults_without_files(tmp_path: Path):
    proc = run_cli(tmp_path, "config", "--json")
    assert proc.returncode == ec.OK
    payload = json.loads(proc.stdout)
    assert payload["base_url"] == "https://wifi.bahn.de"
    assert payload["sources"]["base_url"] == "default"
    assert payload["state_path"] == str(tmp_path / "session.json")
    assert payload["sources"]["state_path"] == "env"


def test_status_never_writes_state_with_dry_run(tmp_path: Path):
    dest = tmp_path / "session.json"
    proc = run_cli(tmp_path, "status", "--dry-run", "--json")
    assert proc.returncode == ec.INPUT
    assert not dest.exists()


def test_nan_timeout_is_clean_input_error_json(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WIFIONICE_TIMEOUT", "nan")
    proc = run_cli(tmp_path, "status", "--json")
    assert proc.returncode == ec.INPUT
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.INPUT
    assert "Traceback" not in proc.stderr
    assert len(proc.stdout.strip().splitlines()) == 1


def test_nan_timeout_is_clean_input_error_human(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WIFIONICE_TIMEOUT", "nan")
    proc = run_cli(tmp_path, "status")
    assert proc.returncode == ec.INPUT
    assert "Traceback" not in proc.stderr
    assert "timeout" in proc.stderr
