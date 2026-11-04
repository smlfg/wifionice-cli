"""Akzeptanztests aus docs/UX.md gegen den UX-Fake-Server.

Jede der drei UX-Sitzungen (status, speed, checkin) läuft als Subprozess gegen
``tests/harness/fake_server.py`` mit den ux-routes/ux-formsteps. Die Tests
beschreiben das Zielverhalten; solange die Nachrüstung nicht gebaut ist, dürfen
sie rot sein.
"""

from __future__ import annotations

import importlib.util
import os
import pty
import re
import select
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "harness"
SCRATCH_TMP = ROOT / "scratch" / "tmp"


def _load_ux_spec():
    if "ux_spec" in sys.modules:
        return sys.modules["ux_spec"]
    spec = importlib.util.spec_from_file_location("ux_spec", HARNESS / "ux_spec.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ux_spec"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


UX_SPEC = _load_ux_spec()


def _load_fake_server():
    name = "acceptance_harness_fake_server"
    if name in sys.modules:
        return sys.modules[name]
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location(name, HARNESS / "fake_server.py")
    )
    sys.modules[name] = module
    assert module.__spec__ is not None and module.__spec__.loader is not None
    module.__spec__.loader.exec_module(module)
    return module


FAKE_SERVER = _load_fake_server()
SPEC = UX_SPEC.parse(ROOT / "docs" / "UX.md")
TOOL = str((SPEC.meta or {}).get("tool", "wifionice"))


def _session_for(subcommand: str):
    wanted = f"{TOOL} {subcommand}"
    for session in SPEC.sessions:
        if any(command.strip() == wanted for command in UX_SPEC.commands(session)):
            return session
    raise AssertionError(f"docs/UX.md hat keine Sitzung mit Befehl {wanted!r}")


def _session_args(subcommand: str) -> list[str]:
    commands = UX_SPEC.commands(_session_for(subcommand))
    command = next(cmd for cmd in commands if cmd.strip() == f"{TOOL} {subcommand}")
    return shlex.split(command)[1:]


def _workdir() -> Path:
    SCRATCH_TMP.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="acceptance-ux-", dir=SCRATCH_TMP))


def _env(server, workdir: Path) -> dict[str, str]:
    home = workdir / "home"
    for relative in (".config", ".local/share", ".local/state", ".cache"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "PYTHONPATH": str(ROOT / "src"),
            "WIFIONICE_BASE_URL": server.base_url,
            "WIFIONICE_ICEPORTAL_URL": server.base_url,
            "WIFIONICE_STATE": str(home / ".local/state/wifionice/session.json"),
            "WIFIONICE_CONFIG": str(home / ".config/wifionice/config.json"),
            "TERM": "xterm",
            "LANG": "C.UTF-8",
        }
    )
    return env


def _run(server, workdir: Path, args: list[str]):
    return subprocess.run(
        [sys.executable, "-m", "wifionice_cli", *args],
        cwd=ROOT,
        env=_env(server, workdir),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_pty(server, workdir: Path, args: list[str], answer: str, timeout: float = 20.0):
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-m", "wifionice_cli", *args],
        cwd=ROOT,
        env=_env(server, workdir),
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    output = b""
    answered = False
    deadline = time.monotonic() + timeout
    try:
        while True:
            if proc.poll() is not None:
                while True:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        break
                    output += chunk
                break
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    chunk = b""
                output += chunk
                if not answered and b"[j/N]" in output:
                    os.write(master, (answer + "\n").encode("utf-8"))
                    answered = True
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=5)
                break
    finally:
        os.close(master)
    return proc.returncode, output.decode("utf-8", "replace")


def test_ux_session_status():
    with FAKE_SERVER.FakeServer(SPEC, ROOT) as server:
        workdir = _workdir()
        code, text = _run_pty(server, workdir, _session_args("status"), answer="")
    assert code == 0, text
    assert re.search(r"Portal: http://127\.0\.0\.1:\d+", text), text
    assert "Erreichbar: ja" in text, text
    assert "Session: nicht angemeldet" in text, text


def test_ux_session_speed():
    with FAKE_SERVER.FakeServer(SPEC, ROOT) as server:
        workdir = _workdir()
        code, text = _run_pty(server, workdir, _session_args("speed"), answer="")
    assert code == 0, text
    assert "Zuggeschwindigkeit: 109 km/h" in text, text
    assert "Servicelevel: AVAILABLE_SERVICE" in text, text
    assert "Verbindung: ja" in text, text


def test_ux_session_checkin_cancel_sends_nothing():
    with FAKE_SERVER.FakeServer(SPEC, ROOT) as server:
        workdir = _workdir()
        code, text = _run_pty(server, workdir, _session_args("checkin"), answer="N")
        requests = list(server.requests)
        sent = list(server.sent_formsteps())
    assert code == 0, text
    assert "Checkin verbindlich? [j/N]" in text, text
    assert requests == [], f"N darf keinen Request senden, gesehen: {requests!r}"
    assert sent == [], f"N darf keinen formstep senden, gesehen: {sent!r}"


def test_ux_session_checkin_confirm_sends_all_formsteps():
    with FAKE_SERVER.FakeServer(SPEC, ROOT) as server:
        workdir = _workdir()
        code, text = _run_pty(server, workdir, _session_args("checkin"), answer="j")
        sent = [step_id for step_id, _record in server.sent_formsteps()]
    assert code == 0, text
    assert "AGB: Der Checkin bestätigt die Nutzungsbedingungen des WIFIonICE-Portals." in text, text
    assert "Checkin verbindlich? [j/N]" in text, text
    assert "Checkin erfolgreich (Methode: cna)." in text, text
    assert sent == [step.id for step in SPEC.formsteps], text
