"""Paddle Billing (Merchant of Record) wrapper.

Mirrors pipeline.stripe_billing's public surface so the rest of the app is
provider-agnostic:
  1. Build Paddle-hosted Checkout URLs the Flutter app opens in a new tab.
  2. Verify + dispatch incoming Paddle webhooks (no bearer auth on that
     endpoint; trust is the Paddle-Signature HMAC).

Talks to Paddle's REST API via a thin httpx client — no heavyweight SDK — so
tests can monkeypatch _request() with canned JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

import httpx

from pipeline.auth import User
from pipeline.credits import PLAN_GRANTS
from pipeline.db import (
    get_grant_by_reference,
    get_user_profile,
    record_grant_once,
    upsert_user_profile,
)


class PaddleSignatureError(Exception):
    """Raised when a webhook's Paddle-Signature header fails verification."""


def _api_key() -> str:
    key = os.environ.get("PADDLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PADDLE_API_KEY not configured")
    return key


def _webhook_secret() -> str:
    s = os.environ.get("PADDLE_WEBHOOK_SECRET", "").strip()
    if not s:
        raise RuntimeError("PADDLE_WEBHOOK_SECRET not configured")
    return s


def _plan_price_id(plan: str) -> str:
    env_key = f"PADDLE_PRICE_{plan.upper()}"
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def _base_url() -> str:
    if os.environ.get("PADDLE_ENV", "sandbox").strip().lower() == "production":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def _request(method: str, path: str, *, json: dict | None = None,
             params: dict | None = None) -> dict:
    """One REST round-trip. Returns the parsed JSON body (Paddle wraps the
    resource under a top-level "data" key). Raises httpx.HTTPStatusError on
    non-2xx."""
    resp = httpx.request(
        method,
        f"{_base_url()}{path}",
        headers={"Authorization": f"Bearer {_api_key()}",
                 "Content-Type": "application/json"},
        json=json,
        params=params,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def _verify_signature(raw_body: bytes, signature_header: str,
                      max_age_s: int = 300) -> None:
    """Verify Paddle-Signature: 'ts=<unix>;h1=<hex>' where
    h1 = HMAC_SHA256(secret, b'<ts>:' + raw_body). Raises PaddleSignatureError
    on malformed header, mismatch, or a timestamp older than max_age_s."""
    parts = dict(p.split("=", 1) for p in signature_header.split(";") if "=" in p)
    ts, h1 = parts.get("ts"), parts.get("h1")
    if not ts or not h1:
        raise PaddleSignatureError("malformed Paddle-Signature header")
    signed = f"{ts}:".encode() + raw_body
    expected = hmac.new(_webhook_secret().encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, h1):
        raise PaddleSignatureError("signature mismatch")
    try:
        if abs(time.time() - int(ts)) > max_age_s:
            raise PaddleSignatureError("timestamp outside tolerance")
    except ValueError:
        raise PaddleSignatureError("non-numeric timestamp")


@dataclass(frozen=True)
class WebhookOutcome:
    event_type: str
    handled: bool
    note: str


def ensure_customer(user: User) -> str:
    """Return the Paddle customer id for this user, creating one on first call.

    Paddle rejects a duplicate email on create, so look one up by email first;
    otherwise create with user_id in custom_data."""
    profile = get_user_profile(user.id)
    if profile and getattr(profile, "paddle_customer_id", None):
        return profile.paddle_customer_id
    if user.email:
        found = _request("GET", "/customers", params={"email": user.email})
        rows = found.get("data") or []
        if rows:
            cid = rows[0]["id"]
            upsert_user_profile(user.id, paddle_customer_id=cid)
            return cid
    created = _request("POST", "/customers",
                       json={"email": user.email, "custom_data": {"user_id": user.id}})
    cid = created["data"]["id"]
    upsert_user_profile(user.id, paddle_customer_id=cid)
    return cid


def create_subscription_checkout(user: User, plan: str,
                                 success_url: str, cancel_url: str) -> str:
    """Create a Paddle transaction for a subscription and return its
    hosted checkout URL (the app opens it in a new tab)."""
    if plan not in PLAN_GRANTS:
        raise ValueError(f"unknown plan: {plan!r}")
    customer_id = ensure_customer(user)
    resp = _request("POST", "/transactions", json={
        "items": [{"price_id": _plan_price_id(plan), "quantity": 1}],
        "customer_id": customer_id,
        # custom_data set here is copied by Paddle onto the subscription this
        # transaction creates, so renewal transactions inherit it.
        "custom_data": {"user_id": user.id, "plan": plan},
        "checkout": {"url": success_url},
    })
    return resp["data"]["checkout"]["url"]


def create_portal_session(user: User, return_url: str) -> str:
    """Return a Paddle customer-portal URL for self-serve manage/cancel."""
    customer_id = ensure_customer(user)
    resp = _request("POST", f"/customers/{customer_id}/portal-sessions", json={})
    return resp["data"]["urls"]["general"]["overview"]


import json


def handle_webhook(raw_body: bytes, signature: str) -> WebhookOutcome:
    """Verify the Paddle-Signature header, decode, and dispatch.

    Raises PaddleSignatureError on a bad signature (caller returns 400).
    Returns handled=False (still HTTP 200) for events we intentionally ignore.
    """
    _verify_signature(raw_body, signature)
    event = json.loads(raw_body)
    et = event.get("event_type", "")
    data = event.get("data") or {}

    if et == "transaction.completed":
        return _on_transaction_completed(data)
    if et == "subscription.updated":
        return _on_subscription_updated(data)
    if et == "subscription.canceled":
        return _on_subscription_canceled(data)
    if et == "subscription.past_due":
        return _on_subscription_past_due(data)
    if et == "adjustment.created":
        return _on_adjustment_created(data)
    return WebhookOutcome(event_type=et, handled=False, note="ignored")


def _cd(data: dict) -> dict:
    return data.get("custom_data") or {}


def _on_transaction_completed(data: dict) -> WebhookOutcome:
    cd = _cd(data)
    user_id, plan = cd.get("user_id"), cd.get("plan")
    if not user_id or plan not in PLAN_GRANTS:
        return WebhookOutcome("transaction.completed", False,
                              f"missing user_id or plan (plan={plan!r})")
    granted = record_grant_once(
        user_id=user_id, amount=PLAN_GRANTS[plan], kind="subscription_renewal",
        reference_id=data.get("id"), description=f"{plan.capitalize()} plan renewal")
    period_end = (data.get("billing_period") or {}).get("ends_at")
    upsert_user_profile(
        user_id, current_plan=plan, current_period_end=period_end,
        payment_status="active")
    note = f"+{PLAN_GRANTS[plan]} for {plan}" if granted else "duplicate transaction, no-op"
    return WebhookOutcome("transaction.completed", True, note)


def _on_subscription_updated(data: dict) -> WebhookOutcome:
    cd = _cd(data)
    user_id, plan = cd.get("user_id"), cd.get("plan")
    if not user_id:
        return WebhookOutcome("subscription.updated", False, "no user_id")
    scheduled = data.get("scheduled_change") or {}
    period_end = ((data.get("current_billing_period") or {}).get("ends_at")
                  or data.get("next_billed_at"))
    upsert_user_profile(
        user_id,
        current_plan=(plan if plan in PLAN_GRANTS else "free"),
        current_period_end=period_end,
        cancel_at_period_end=(scheduled.get("action") == "cancel"))
    return WebhookOutcome("subscription.updated", True, f"plan={plan}")


def _on_subscription_canceled(data: dict) -> WebhookOutcome:
    user_id = _cd(data).get("user_id")
    if not user_id:
        return WebhookOutcome("subscription.canceled", False, "no user_id")
    upsert_user_profile(
        user_id, current_plan="free", current_period_end=None,
        cancel_at_period_end=False, payment_status="active")
    return WebhookOutcome("subscription.canceled", True, "plan reset to free")


def _on_subscription_past_due(data: dict) -> WebhookOutcome:
    user_id = _cd(data).get("user_id")
    if not user_id:
        return WebhookOutcome("subscription.past_due", False, "no user_id")
    upsert_user_profile(user_id, payment_status="past_due")
    return WebhookOutcome("subscription.past_due", True, "marked past_due")
