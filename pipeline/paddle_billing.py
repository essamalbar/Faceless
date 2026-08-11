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
