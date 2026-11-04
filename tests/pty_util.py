"""Run a CLI under a pseudo terminal so human-mode output is testable."""

from __future__ import annotations

import os
import pty
import select
import subprocess
import time
from pathlib import Path


def run_pty(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path | str,
    timeout: float = 20.0,
    marker: str | None = None,
    response: str | None = None,
) -> tuple[int, str]:
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        env=env,
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
                if marker and not answered and marker.encode() in output:
                    payload = b"\x04" if response is None else response.encode()
                    os.write(master, payload)
                    answered = True
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=5)
                break
    finally:
        os.close(master)
    return proc.returncode, output.decode("utf-8", "replace")
