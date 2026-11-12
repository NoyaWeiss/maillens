import os
import socket

import pytest

os.environ.setdefault("MAILLENS_API_KEY", "test-key-" + "x" * 40)
API_KEY = os.environ["MAILLENS_API_KEY"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """The backend must never make outbound calls; any socket connect fails the test."""

    def guard(*_a, **_k):
        raise AssertionError("outbound network access attempted")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": API_KEY}
