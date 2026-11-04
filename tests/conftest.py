"""Repo-wide fixtures. Stay offline: no test may touch the network.

Shared MCP suite: copy ``tests/shared/`` into your repo and configure it via
``MCP_TEST_*`` env vars or fixtures — see README.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch):
    """Unit tests may only talk to local fake servers, never to the internet."""
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and host not in _LOCAL_HOSTS:
            raise RuntimeError(f"network access to {host!r} blocked in tests")
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_state(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_state.json"
