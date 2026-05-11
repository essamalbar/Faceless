"""Stripe SDK wrapper.

Two responsibilities:
  1. Build Stripe-hosted Checkout / Portal URLs that the Flutter app opens
     in a new tab to collect payment.
  2. Verify + dispatch incoming Stripe webhooks (no auth on that endpoint;
     trust is via the Stripe-Signature header).

The rest of the codebase never imports `stripe` directly — it goes through
this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import stripe

from pipeline.auth import User
from pipeline.credits import PLAN_GRANTS, TOPUP_PACKS
from pipeline.db import get_user_profile, record_transaction, upsert_user_profile


def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")
    return key


def _webhook_secret() -> str:
    s = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not s:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")
    return s


def _plan_price_id(plan: str) -> str:
    env_key = f"STRIPE_PRICE_{plan.upper()}"
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def _pack_price_id(pack: str) -> str:
    env_key = f"STRIPE_PRICE_{pack.upper()}"  # e.g. STRIPE_PRICE_TOPUP_30
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def ensure_customer(user: User) -> str:
    """Return the Stripe customer_id for this user, creating one on first call."""
    stripe.api_key = _api_key()
    profile = get_user_profile(user.id)
    if profile and profile.stripe_customer_id:
        return profile.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email or None,
        metadata={"user_id": user.id},
    )
    upsert_user_profile(user.id, stripe_customer_id=customer.id)
    return customer.id


def create_subscription_checkout(
    user: User, plan: str, success_url: str, cancel_url: str,
) -> str:
    """Returns a Stripe Checkout URL for a new subscription."""
    if plan not in PLAN_GRANTS:
        raise ValueError(f"unknown plan: {plan!r}")
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": _plan_price_id(plan), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id, "plan": plan},
        # CRITICAL: must duplicate metadata onto the subscription so the
        # invoice.payment_succeeded webhook can find the user.
        subscription_data={"metadata": {"user_id": user.id, "plan": plan}},
    )
    return session.url


def create_topup_checkout(
    user: User, pack: str, success_url: str, cancel_url: str,
) -> str:
    """Returns a Stripe Checkout URL for a one-time top-up pack."""
    if pack not in TOPUP_PACKS:
        raise ValueError(f"unknown pack: {pack!r}")
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        line_items=[{"price": _pack_price_id(pack), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id, "pack": pack},
    )
    return session.url


def create_portal_session(user: User, return_url: str) -> str:
    """Returns a Stripe Customer Portal URL for self-serve subscription management."""
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


@dataclass(frozen=True)
class WebhookOutcome:
    event_type: str
    handled: bool
    note: str


def handle_webhook(raw_body: bytes, signature: str) -> WebhookOutcome:
    """Verify the Stripe-Signature header, decode, and dispatch.

    Raises stripe.SignatureVerificationError on bad signatures (caller should
    return 400). Returns the outcome for logging.
    """
    stripe.api_key = _api_key()
    event = stripe.Webhook.construct_event(
        payload=raw_body,
        sig_header=signature,
        secret=_webhook_secret(),
    )
    et = event["type"]
    data = event["data"]["object"]

    if et == "checkout.session.completed":
        return _on_checkout_completed(data)
    if et == "invoice.payment_succeeded":
        return _on_invoice_paid(data)
    if et == "customer.subscription.updated":
        return _on_subscription_updated(data)
    if et == "customer.subscription.deleted":
        return _on_subscription_deleted(data)
    return WebhookOutcome(event_type=et, handled=False, note="ignored")


def _on_checkout_completed(session) -> WebhookOutcome:
    user_id = (session.get("metadata") or {}).get("user_id")
    mode = session.get("mode")
    if not user_id:
        return WebhookOutcome("checkout.session.completed", False, "no user_id metadata")

    if mode == "subscription":
        # First-time subscriber — link the customer id (already done by ensure_customer,
        # but safe to refresh). Credit grant happens on invoice.payment_succeeded.
        customer_id = session.get("customer")
        if customer_id:
            upsert_user_profile(user_id, stripe_customer_id=customer_id)
        return WebhookOutcome("checkout.session.completed", True, "subscription linked")

    if mode == "payment":
        pack = (session.get("metadata") or {}).get("pack")
        if pack not in TOPUP_PACKS:
            return WebhookOutcome("checkout.session.completed", False, f"unknown pack {pack!r}")
        record_transaction(
            user_id=user_id,
            amount=TOPUP_PACKS[pack],
            kind="topup",
            reference_id=session.get("id"),
            description=f"Top-up pack ({pack})",
        )
        return WebhookOutcome("checkout.session.completed", True, f"+{TOPUP_PACKS[pack]} credits")

    return WebhookOutcome("checkout.session.completed", False, f"unknown mode {mode!r}")


def _on_invoice_paid(invoice) -> WebhookOutcome:
    sub_id = invoice.get("subscription")
    if not sub_id:
        return WebhookOutcome("invoice.payment_succeeded", False, "no subscription id")
    subscription = stripe.Subscription.retrieve(sub_id)
    user_id = (subscription.get("metadata") or {}).get("user_id")
    plan = (subscription.get("metadata") or {}).get("plan")
    if not user_id or plan not in PLAN_GRANTS:
        return WebhookOutcome("invoice.payment_succeeded", False,
                              f"missing user_id or plan (plan={plan!r})")

    record_transaction(
        user_id=user_id,
        amount=PLAN_GRANTS[plan],
        kind="subscription_renewal",
        reference_id=invoice.get("id"),
        description=f"{plan.capitalize()} plan renewal",
    )
    upsert_user_profile(
        user_id,
        current_plan=plan,
        current_period_end=_iso(subscription.get("current_period_end")),
    )
    return WebhookOutcome("invoice.payment_succeeded", True,
                          f"+{PLAN_GRANTS[plan]} for {plan}")


def _on_subscription_updated(subscription) -> WebhookOutcome:
    user_id = (subscription.get("metadata") or {}).get("user_id")
    plan = (subscription.get("metadata") or {}).get("plan")
    if not user_id:
        return WebhookOutcome("customer.subscription.updated", False, "no user_id metadata")
    upsert_user_profile(
        user_id,
        current_plan=(plan if plan in PLAN_GRANTS else "free"),
        current_period_end=_iso(subscription.get("current_period_end")),
    )
    return WebhookOutcome("customer.subscription.updated", True, f"plan={plan}")


def _on_subscription_deleted(subscription) -> WebhookOutcome:
    user_id = (subscription.get("metadata") or {}).get("user_id")
    if not user_id:
        return WebhookOutcome("customer.subscription.deleted", False, "no user_id metadata")
    upsert_user_profile(user_id, current_plan="free", current_period_end=None)
    return WebhookOutcome("customer.subscription.deleted", True, "plan reset to free")


def _iso(unix_ts) -> str | None:
    if not unix_ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()
