from __future__ import annotations

import sys
import socket
import threading
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sdk"))
sys.path.insert(0, str(ROOT / "integrations" / "mcp_ci"))


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    original_pair, original_connect = socket.socketpair, socket.socket.connect
    state = threading.local()
    def blocked(*args, **kwargs):
        if getattr(state, 'in_socketpair', False):
            return original_connect(*args, **kwargs)
        raise AssertionError("Network access is disabled in the offline test suite")
    def local_pair(*args, **kwargs):
        # Windows asyncio implements its wakeup pipe via a loopback socketpair.
        state.in_socketpair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            state.in_socketpair = False
    monkeypatch.setattr(socket, "socketpair", local_pair)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
