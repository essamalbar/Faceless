"""Tests for pipeline.paddle_billing — Paddle REST wrapper, all mocked."""
from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest

import pipeline.paddle_billing as pb
from pipeline.auth import User


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


def _user():
    return User(id="u1", email="alice@example.com", role="user")


@pytest.fixture
def mock_db(monkeypatch):
    state = {"profiles": {}, "grants": []}
    monkeypatch.setattr(pb, "get_user_profile",
        lambda uid: (SimpleNamespace(id=uid, paddle_customer_id=state["profiles"][uid].get("paddle_customer_id"))
                     if uid in state["profiles"] else None))
    monkeypatch.setattr(pb, "upsert_user_profile",
        lambda uid, **f: state["profiles"].setdefault(uid, {}).update(f) or None)
    monkeypatch.setattr(pb, "record_grant_once",
        lambda **kw: (state["grants"].append(kw), True)[1])
    return state


def test_ensure_customer_creates_when_missing(paddle_env, mock_db, monkeypatch):
    calls = {}
    def fake_request(method, path, *, json=None, params=None):
        calls.update(method=method, path=path, json=json, params=params)
        if method == "GET":
            return {"data": []}       # no existing customer for this email
        return {"data": {"id": "ctm_new"}}
    monkeypatch.setattr(pb, "_request", fake_request)
    assert pb.ensure_customer(_user()) == "ctm_new"
    assert mock_db["profiles"]["u1"]["paddle_customer_id"] == "ctm_new"


def test_ensure_customer_reuses_stored(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_old"}
    monkeypatch.setattr(pb, "_request",
        lambda *a, **k: pytest.fail("should not hit Paddle when id is stored"))
    assert pb.ensure_customer(_user()) == "ctm_old"


def test_create_subscription_checkout_returns_hosted_url(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_x"}
    captured = {}
    def fake_request(method, path, *, json=None, params=None):
        captured.update(method=method, path=path, json=json)
        return {"data": {"id": "txn_1",
                         "checkout": {"url": "https://pay.paddle.io/txn_1"}}}
    monkeypatch.setattr(pb, "_request", fake_request)
    url = pb.create_subscription_checkout(_user(), "creator",
                                          "https://app/success", "https://app/cancel")
    assert url == "https://pay.paddle.io/txn_1"
    assert captured["path"] == "/transactions"
    assert captured["json"]["items"][0]["price_id"] == "pri_creator"
    # Critical: user_id + plan ride in custom_data so renewal transactions
    # (which inherit the subscription's custom_data) can find the user.
    assert captured["json"]["custom_data"] == {"user_id": "u1", "plan": "creator"}


def test_create_subscription_checkout_rejects_unknown_plan(paddle_env, mock_db):
    with pytest.raises(ValueError, match="unknown plan"):
        pb.create_subscription_checkout(_user(), "elite", "s", "c")


def test_create_portal_session_returns_url(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_x"}
    monkeypatch.setattr(pb, "_request",
        lambda *a, **k: {"data": {"urls": {"general": {"overview": "https://portal/x"}}}})
    assert pb.create_portal_session(_user(), "https://app/back") == "https://portal/x"
