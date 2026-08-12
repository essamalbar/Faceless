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


import json as _json


def _wrap(event_type: str, data: dict, secret="pdl_ntfset_secret"):
    raw = _json.dumps({"event_type": event_type, "data": data}).encode()
    ts = str(int(time.time()))
    return raw, _sign(secret, raw, ts)


def test_webhook_transaction_completed_grants(paddle_env, mock_db, monkeypatch):
    raw, sig = _wrap("transaction.completed", {
        "id": "txn_1",
        "custom_data": {"user_id": "u1", "plan": "creator"},
        "billing_period": {"ends_at": "2026-09-11T00:00:00Z"},
    })
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    g = mock_db["grants"][-1]
    assert g["amount"] == 60 and g["kind"] == "subscription_renewal"
    assert g["reference_id"] == "txn_1"
    prof = mock_db["profiles"]["u1"]
    assert prof["current_plan"] == "creator"
    assert prof["current_period_end"] == "2026-09-11T00:00:00Z"
    assert prof["payment_status"] == "active"


def test_webhook_transaction_completed_dedupes(paddle_env, mock_db, monkeypatch):
    calls = {"n": 0}
    def grant(**kw):
        calls["n"] += 1
        return calls["n"] == 1
    monkeypatch.setattr(pb, "record_grant_once", grant)
    raw, sig = _wrap("transaction.completed", {
        "id": "txn_dup", "custom_data": {"user_id": "u1", "plan": "starter"},
        "billing_period": {"ends_at": "2026-09-11T00:00:00Z"}})
    first = pb.handle_webhook(raw, sig)
    second = pb.handle_webhook(raw, sig)
    assert first.handled and "+12" in first.note
    assert second.handled and "no-op" in second.note
    assert calls["n"] == 2


def test_webhook_transaction_zero_amount_no_grant(paddle_env, mock_db):
    # Paddle fires transaction.completed with a ZERO grand_total when a
    # subscriber only updates their card — it carries the subscription's
    # custom_data, so without the guard it would mint a full plan grant.
    raw, sig = _wrap("transaction.completed", {
        "id": "txn_cardupdate",
        "custom_data": {"user_id": "u1", "plan": "creator"},
        "details": {"totals": {"grand_total": "0"}},
        "billing_period": {"ends_at": "2026-09-11T00:00:00Z"},
    })
    out = pb.handle_webhook(raw, sig)
    assert out.handled is True
    assert "zero-amount" in out.note
    # No grant minted and the profile is untouched.
    assert mock_db["grants"] == []
    assert "u1" not in mock_db["profiles"]


def test_webhook_subscription_updated_persists_cancel(paddle_env, mock_db):
    raw, sig = _wrap("subscription.updated", {
        "id": "sub_1", "custom_data": {"user_id": "u1", "plan": "starter"},
        "current_billing_period": {"ends_at": "2026-09-11T00:00:00Z"},
        "scheduled_change": {"action": "cancel", "effective_at": "2026-09-11T00:00:00Z"},
    })
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    prof = mock_db["profiles"]["u1"]
    assert prof["current_plan"] == "starter"
    assert prof["cancel_at_period_end"] is True
    assert prof["current_period_end"] == "2026-09-11T00:00:00Z"


def test_webhook_subscription_canceled_resets_free(paddle_env, mock_db):
    mock_db["profiles"]["u1"] = {"current_plan": "pro"}
    raw, sig = _wrap("subscription.canceled",
                     {"id": "sub_1", "custom_data": {"user_id": "u1"}})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert mock_db["profiles"]["u1"]["current_plan"] == "free"
    assert mock_db["profiles"]["u1"]["cancel_at_period_end"] is False


def test_webhook_subscription_past_due_marks_dunning(paddle_env, mock_db):
    mock_db["profiles"]["u1"] = {"current_plan": "creator"}
    raw, sig = _wrap("subscription.past_due",
                     {"id": "sub_1", "custom_data": {"user_id": "u1"}})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert mock_db["profiles"]["u1"]["payment_status"] == "past_due"


def test_webhook_bad_signature_raises(paddle_env):
    raw = _json.dumps({"event_type": "transaction.completed", "data": {}}).encode()
    with pytest.raises(pb.PaddleSignatureError):
        pb.handle_webhook(raw, "ts=123;h1=deadbeef")


def test_webhook_adjustment_claws_back(paddle_env, monkeypatch):
    clawed = {}
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: ("u1", 60))
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    raw, sig = _wrap("adjustment.created", {
        "id": "adj_1", "action": "refund", "transaction_id": "txn_1", "status": "approved"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert clawed["amount"] == -60 and clawed["kind"] == "chargeback_clawback"
    # Clawback is keyed on the TRANSACTION id (not the adjustment id) so the
    # DB unique index dedupes multiple adjustments against one transaction.
    assert clawed["user_id"] == "u1" and clawed["reference_id"] == "txn_1"


def test_webhook_adjustment_no_grant_is_safe_noop(paddle_env, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: None)
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    raw, sig = _wrap("adjustment.created",
                     {"id": "adj_2", "action": "refund", "transaction_id": "txn_none",
                      "status": "approved"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled and called["n"] == 0


def test_webhook_adjustment_ignored_action_not_clawed_back(paddle_env, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    raw, sig = _wrap("adjustment.created", {
        "id": "adj_3", "action": "credit", "transaction_id": "txn_1"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled is False
    assert called["n"] == 0


def test_webhook_adjustment_pending_approval_no_clawback(paddle_env, monkeypatch):
    # Live refunds are created as status="pending_approval" and may still be
    # rejected — we must NOT claw back until they're approved.
    called = {"n": 0}
    monkeypatch.setattr(pb, "get_grant_by_reference",
                        lambda ref: pytest.fail("must not look up grant while pending"))
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    raw, sig = _wrap("adjustment.created", {
        "id": "adj_p", "action": "refund", "transaction_id": "txn_1",
        "status": "pending_approval"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled is True
    assert "pending_approval" in out.note
    assert called["n"] == 0


def test_webhook_adjustment_updated_approved_claws_back(paddle_env, monkeypatch):
    # adjustment.updated (previously unmapped) with status="approved" is the
    # event that actually authorizes the clawback.
    clawed = {}
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: ("u1", 60))
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    raw, sig = _wrap("adjustment.updated", {
        "id": "adj_u", "action": "refund", "transaction_id": "txn_1",
        "status": "approved"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled is True
    assert clawed["amount"] == -60 and clawed["kind"] == "chargeback_clawback"
    assert clawed["user_id"] == "u1" and clawed["reference_id"] == "txn_1"


def test_webhook_adjustment_double_refund_dedupes(paddle_env, monkeypatch):
    # Two approved adjustments against the SAME transaction (different adjustment
    # ids) must claw back the full grant only ONCE. Because the clawback is
    # keyed on the transaction id, the DB unique index dedupes the second —
    # simulated here by record_grant_once returning True then False.
    calls = {"n": 0}
    refs = []
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: ("u1", 60))

    def grant(**kw):
        calls["n"] += 1
        refs.append(kw["reference_id"])
        return calls["n"] == 1

    monkeypatch.setattr(pb, "record_grant_once", grant)
    raw1, sig1 = _wrap("adjustment.updated", {
        "id": "adj_a", "action": "refund", "transaction_id": "txn_1", "status": "approved"})
    raw2, sig2 = _wrap("adjustment.updated", {
        "id": "adj_b", "action": "refund", "transaction_id": "txn_1", "status": "approved"})
    first = pb.handle_webhook(raw1, sig1)
    second = pb.handle_webhook(raw2, sig2)
    assert calls["n"] == 2
    # Both attempts key on the transaction id → the unique index dedupes them.
    assert refs == ["txn_1", "txn_1"]
    assert first.handled and "clawed back" in first.note
    assert second.handled and "no-op" in second.note


def test_webhook_unknown_event_ignored(paddle_env):
    raw, sig = _wrap("report.created", {"id": "rep_1"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled is False
