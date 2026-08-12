from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_secret")
    monkeypatch.setenv("FACELESS_API_TOKEN", "t")
    import pipeline.api as api
    return TestClient(api.app)


def _signed(body: dict):
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    mac = hmac.new(b"pdl_ntfset_secret", f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return raw, f"ts={ts};h1={mac}"


def test_paddle_webhook_ok(client, monkeypatch):
    raw, sig = _signed({"event_type": "report.created", "data": {}})
    r = client.post("/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert r.status_code == 200
    assert r.json()["handled"] is False


def test_paddle_webhook_bad_sig_returns_400(client):
    raw, _ = _signed({"event_type": "transaction.completed", "data": {}})
    r = client.post("/paddle/webhook", content=raw,
                    headers={"Paddle-Signature": "ts=1;h1=bad"})
    assert r.status_code == 400
