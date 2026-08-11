"""Tests for pipeline.paddle_billing — Paddle REST wrapper, all mocked."""
from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest

import pipeline.paddle_billing as pb


@pytest.fixture
def paddle_env(monkeypatch):
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_key")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_secret")
    monkeypatch.setenv("PADDLE_PRICE_STARTER", "pri_starter")
    monkeypatch.setenv("PADDLE_PRICE_CREATOR", "pri_creator")
    monkeypatch.setenv("PADDLE_PRICE_PRO", "pri_pro")
    monkeypatch.delenv("PADDLE_ENV", raising=False)


def _sign(secret: str, raw: bytes, ts: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={mac}"


def test_base_url_defaults_to_sandbox(paddle_env):
    assert pb._base_url() == "https://sandbox-api.paddle.com"


def test_base_url_production(paddle_env, monkeypatch):
    monkeypatch.setenv("PADDLE_ENV", "production")
    assert pb._base_url() == "https://api.paddle.com"


def test_plan_price_id_reads_env(paddle_env):
    assert pb._plan_price_id("creator") == "pri_creator"


def test_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PADDLE_API_KEY"):
        pb._api_key()


def test_verify_signature_accepts_valid(paddle_env):
    raw = b'{"event_type":"x"}'
    ts = str(int(time.time()))
    pb._verify_signature(raw, _sign("pdl_ntfset_secret", raw, ts))  # no raise


def test_verify_signature_rejects_tampered_body(paddle_env):
    ts = str(int(time.time()))
    header = _sign("pdl_ntfset_secret", b'{"a":1}', ts)
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(b'{"a":2}', header)


def test_verify_signature_rejects_stale(paddle_env):
    raw = b"{}"
    ts = str(int(time.time()) - 10_000)
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(raw, _sign("pdl_ntfset_secret", raw, ts))


def test_verify_signature_rejects_malformed_header(paddle_env):
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(b"{}", "garbage")
