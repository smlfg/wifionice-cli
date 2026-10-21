"""Contract tests for the wifionice commands against an offline fake portal."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wifionice_cli import exit_codes as ec
from fake_server import dead_url, start_fake_portal

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def portal():
    backend, url, server = start_fake_portal()
    yield backend, url
    server.shutdown()
    server.server_close()


def run_cli(
    tmp_path: Path,
    *args: str,
    base_url: str | None = None,
    iceportal_url: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["WIFIONICE_CONFIG"] = str(tmp_path / "no-config.json")
    env["WIFIONICE_STATE"] = str(tmp_path / "session.json")
    if base_url:
        env["WIFIONICE_BASE_URL"] = base_url
    if iceportal_url:
        env["WIFIONICE_ICEPORTAL_URL"] = iceportal_url
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-m", "wifionice_cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def one_json(proc: subprocess.CompletedProcess[str]) -> dict:
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON object, got: {proc.stdout!r}"
    return json.loads(lines[0])


def state_path(tmp_path: Path) -> Path:
    return tmp_path / "session.json"


def test_checkin_happy_path_writes_state(portal, tmp_path: Path):
    backend, url = portal
    proc = run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url)
    assert proc.returncode == ec.OK, proc.stderr
    payload = one_json(proc)
    assert payload["ok"] is True
    assert payload["checked_in"] is True
    assert payload["method"] == "cna"
    assert backend.authenticated is True

    assert "POST /cna/logon" in backend.paths()
    logon = next(r for r in backend.requests if r["path"] == "/cna/logon")
    assert logon["headers"]["X-Csrf-Token"] == "csrf"
    assert logon["body"] == "{}"

    state = json.loads(state_path(tmp_path).read_text(encoding="utf-8"))
    assert state["authenticated"] is True
    assert state["method"] == "cna"
    assert state["checked_in_at"]


def test_checkin_requires_accept_terms(portal, tmp_path: Path):
    backend, url = portal
    proc = run_cli(tmp_path, "checkin", "--json", base_url=url)
    assert proc.returncode == ec.INPUT
    payload = one_json(proc)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.INPUT
    assert "--accept-terms" in payload["error"]["message"]
    assert backend.requests == []
    assert not state_path(tmp_path).exists()


def test_checkin_dry_run_no_network_no_state(portal, tmp_path: Path):
    backend, url = portal
    proc = run_cli(tmp_path, "checkin", "--accept-terms", "--dry-run", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["dry_run"] is True
    assert len(payload["requests"]) == 2
    assert payload["requests"][0]["url"].endswith("/cna/logon")
    assert backend.requests == []
    assert not state_path(tmp_path).exists()


def test_checkin_dry_run_without_accept_terms_shows_plan(portal, tmp_path: Path):
    backend, url = portal
    proc = run_cli(tmp_path, "checkin", "--dry-run", "--json", base_url=url)
    assert proc.returncode == ec.OK
    assert backend.requests == []


def test_checkin_portal_rejection_is_auth(portal, tmp_path: Path):
    backend, url = portal
    backend.logon_result = "failure"
    proc = run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url)
    assert proc.returncode == ec.AUTH
    payload = one_json(proc)
    assert payload["error"]["code"] == ec.AUTH
    assert not state_path(tmp_path).exists()


def test_checkin_network_down(portal, tmp_path: Path):
    proc = run_cli(
        tmp_path,
        "checkin",
        "--accept-terms",
        "--json",
        base_url=dead_url(),
    )
    assert proc.returncode == ec.NETWORK
    payload = one_json(proc)
    assert payload["error"]["code"] == ec.NETWORK


def test_checkin_legacy_fallback(portal, tmp_path: Path):
    backend, url = portal
    backend.cna_available = False
    proc = run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url)
    assert proc.returncode == ec.OK, proc.stderr
    payload = one_json(proc)
    assert payload["method"] == "legacy"
    assert backend.authenticated is True
    assert any(p.startswith("GET /de") for p in backend.paths())
    assert any(p.startswith("POST /de") for p in backend.paths())


def test_status_unauthenticated(portal, tmp_path: Path):
    _, url = portal
    proc = run_cli(tmp_path, "status", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["authenticated"] is False
    assert payload["method"] == "cna"
    assert payload["portal_reachable"] is True
    assert payload["session"]["limit_mb"] == "200"


def test_status_authenticated_after_checkin(portal, tmp_path: Path):
    _, url = portal
    assert (
        run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url).returncode == ec.OK
    )
    proc = run_cli(tmp_path, "status", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["authenticated"] is True
    assert payload["local"]["checked_in_at"]


def test_status_legacy_fallback(portal, tmp_path: Path):
    backend, url = portal
    backend.cna_available = False
    proc = run_cli(tmp_path, "status", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["method"] == "legacy"
    assert payload["authenticated"] is False


def test_status_network_down(tmp_path: Path):
    proc = run_cli(tmp_path, "status", "--json", base_url=dead_url())
    assert proc.returncode == ec.NETWORK
    payload = one_json(proc)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.NETWORK


def test_status_bad_json(portal, tmp_path: Path):
    backend, url = portal
    backend.user_info_mode = "bad_json"
    proc = run_cli(tmp_path, "status", "--json", base_url=url)
    assert proc.returncode == ec.PARSE
    assert one_json(proc)["error"]["code"] == ec.PARSE


def test_status_rejects_dry_run(portal, tmp_path: Path):
    _, url = portal
    proc = run_cli(tmp_path, "status", "--dry-run", "--json", base_url=url)
    assert proc.returncode == ec.INPUT


def test_speed_happy_path(portal, tmp_path: Path):
    backend, url = portal
    backend.iceportal_speed = 175
    proc = run_cli(tmp_path, "speed", "--json", iceportal_url=url, base_url=url)
    assert proc.returncode == ec.OK, proc.stderr
    payload = one_json(proc)
    assert payload["train_speed_kmh"] == 175.0
    assert payload["measurement"] == "train_speed_kmh"
    assert "bandwidth" in payload["note"].lower()
    assert payload["servicelevel"] == "AVAILABLE_SERVICE"


def test_speed_bandwidth_flag_rejected(portal, tmp_path: Path):
    _, url = portal
    proc = run_cli(tmp_path, "speed", "--bandwidth", "--json", iceportal_url=url, base_url=url)
    assert proc.returncode == ec.INPUT
    err = one_json(proc)["error"]["message"]
    assert "train speed" in err.lower()
    assert "bandwidth" in err.lower()


def test_speed_network_down(tmp_path: Path):
    proc = run_cli(tmp_path, "speed", "--json", iceportal_url=dead_url())
    assert proc.returncode == ec.NETWORK
    assert one_json(proc)["error"]["code"] == ec.NETWORK


def test_speed_bad_json(portal, tmp_path: Path):
    backend, url = portal
    backend.iceportal_mode = "bad_json"
    proc = run_cli(tmp_path, "speed", "--json", iceportal_url=url)
    assert proc.returncode == ec.PARSE


def test_speed_missing_field(portal, tmp_path: Path):
    backend, url = portal
    backend.iceportal_mode = "no_speed"
    proc = run_cli(tmp_path, "speed", "--json", iceportal_url=url)
    assert proc.returncode == ec.PARSE


def test_logout_removes_local_state(portal, tmp_path: Path):
    backend, url = portal
    assert (
        run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url).returncode == ec.OK
    )
    assert state_path(tmp_path).exists()
    backend.requests.clear()
    proc = run_cli(tmp_path, "logout", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["removed"] is True
    assert payload["portal_logoff"] is True
    assert "POST /cna/logoff" in backend.paths()
    assert backend.authenticated is False
    assert not state_path(tmp_path).exists()


def test_logout_unreachable_portal_still_removes_state(portal, tmp_path: Path):
    _, url = portal
    assert (
        run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url).returncode == ec.OK
    )
    proc = run_cli(tmp_path, "logout", "--json", base_url=dead_url())
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["removed"] is True
    assert payload["portal_logoff"] is False
    assert not state_path(tmp_path).exists()
    assert "warning" in proc.stderr.lower()


def test_logout_dry_run_keeps_state(portal, tmp_path: Path):
    _, url = portal
    assert (
        run_cli(tmp_path, "checkin", "--accept-terms", "--json", base_url=url).returncode == ec.OK
    )
    proc = run_cli(tmp_path, "logout", "--dry-run", "--json", base_url=url)
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["removed"] is False
    assert payload["dry_run"] is True
    assert state_path(tmp_path).exists()


def test_logout_without_state_is_ok(tmp_path: Path):
    proc = run_cli(tmp_path, "logout", "--json", base_url=dead_url())
    assert proc.returncode == ec.OK
    payload = one_json(proc)
    assert payload["removed"] is False
    assert payload["portal_logoff"] is False


def test_missing_command_is_input(tmp_path: Path):
    proc = run_cli(tmp_path, "--json", base_url=dead_url())
    assert proc.returncode == ec.INPUT
    assert one_json(proc)["error"]["code"] == ec.INPUT


def test_unknown_command_is_input(tmp_path: Path):
    proc = run_cli(tmp_path, "warp", "--json")
    assert proc.returncode == ec.INPUT


def test_human_error_message_on_stderr(tmp_path: Path):
    proc = run_cli(tmp_path, "status", base_url=dead_url())
    assert proc.returncode == ec.NETWORK
    assert proc.stdout == ""
    assert "cannot reach" in proc.stderr
