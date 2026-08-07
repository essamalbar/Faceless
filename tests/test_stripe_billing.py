"""Tests for pipeline.stripe_billing — Stripe SDK wrapper, all mocked."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pipeline.auth import User
from pipeline.stripe_billing import (
    create_portal_session,
    create_subscription_checkout,
    create_topup_checkout,
    ensure_customer,
    handle_webhook,
)


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_CREATOR", "price_creator")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_30", "price_t30")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_100", "price_t100")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_300", "price_t300")


@pytest.fixture
def mock_db(monkeypatch):
    db_state = {"profiles": {}, "transactions": []}

    def fake_get_profile(uid):
        if uid not in db_state["profiles"]:
            return None
        p = db_state["profiles"][uid]
        return SimpleNamespace(
            id=uid,
            stripe_customer_id=p.get("stripe_customer_id"),
            current_plan=p.get("current_plan", "free"),
            current_period_end=p.get("current_period_end"),
        )

    monkeypatch.setattr("pipeline.stripe_billing.get_user_profile", fake_get_profile)
    monkeypatch.setattr(
        "pipeline.stripe_billing.upsert_user_profile",
        lambda uid, **f: db_state["profiles"].setdefault(uid, {}).update(f) or None,
    )
    monkeypatch.setattr(
        "pipeline.stripe_billing.record_grant_once",
        lambda **kw: (db_state["transactions"].append(kw), True)[1],
    )
    return db_state


def _user():
    return User(id="u1", email="alice@example.com", role="user")


def test_ensure_customer_creates_when_missing(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: SimpleNamespace(id="cus_new"))
    cid = ensure_customer(_user())
    assert cid == "cus_new"
    assert mock_db["profiles"]["u1"]["stripe_customer_id"] == "cus_new"


def test_ensure_customer_reuses_existing(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"stripe_customer_id": "cus_old"}
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: pytest.fail("should not create"))
    assert ensure_customer(_user()) == "cus_old"


def test_create_subscription_checkout_url(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: SimpleNamespace(id="cus_x"))
    captured = {}
    def fake_create(**kw):
        captured.update(kw)
        return SimpleNamespace(url="https://checkout.stripe.com/x")
    monkeypatch.setattr("pipeline.stripe_billing.stripe.checkout.Session.create", fake_create)

    url = create_subscription_checkout(_user(), "starter",
                                       "https://app/success", "https://app/cancel")
    assert url == "https://checkout.stripe.com/x"
    assert captured["mode"] == "subscription"
    assert captured["line_items"][0]["price"] == "price_starter"
    # Critical: metadata must be on the subscription too
    assert captured["subscription_data"]["metadata"]["user_id"] == "u1"


def test_create_subscription_checkout_rejects_unknown_plan(stripe_env, mock_db):
    with pytest.raises(ValueError, match="unknown plan"):
        create_subscription_checkout(_user(), "elite", "u1", "u2")


def test_create_topup_checkout_rejects_when_packs_disabled(stripe_env, mock_db):
    """Top-up packs are disabled in v1 (TOPUP_PACKS is empty). Any attempt
    to create a top-up checkout must raise — the UI doesn't surface the
    option, so this is a defensive check for direct API callers."""
    with pytest.raises(ValueError, match="unknown pack"):
        create_topup_checkout(_user(), "topup_100", "u1", "u2")


def test_handle_webhook_subscription_renewal_grants(stripe_env, mock_db, monkeypatch):
    fake_event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "inv_1", "subscription": "sub_1"}},
    }
    monkeypatch.setattr(
        "pipeline.stripe_billing.stripe.Subscription.retrieve",
        lambda sid: {
            "id": sid,
            "metadata": {"user_id": "u1", "plan": "creator"},
            "current_period_end": 1788000000,
        },
    )
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    last_tx = mock_db["transactions"][-1]
    assert last_tx["amount"] == 60  # PLAN_GRANTS["creator"]
    assert last_tx["kind"] == "subscription_renewal"
    assert mock_db["profiles"]["u1"]["current_plan"] == "creator"
    # A successful renewal clears any prior past_due dunning flag.
    assert mock_db["profiles"]["u1"]["payment_status"] == "active"


def test_handle_webhook_invoice_failed_marks_past_due(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"current_plan": "creator"}
    fake_event = {"type": "invoice.payment_failed",
                  "data": {"object": {"subscription": "sub_1"}}}
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Subscription.retrieve",
                        lambda sid: {"id": sid, "metadata": {"user_id": "u1"}})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["payment_status"] == "past_due"


def test_handle_webhook_duplicate_invoice_grants_only_once(
    stripe_env, mock_db, monkeypatch,
):
    """Stripe delivers webhooks at-least-once. A retried
    invoice.payment_succeeded must grant credits only on the first delivery;
    the second hits the unique index (record_grant_once returns False) and is
    reported as a no-op — still handled=True so Stripe stops retrying."""
    fake_event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "inv_dup", "subscription": "sub_1"}},
    }
    monkeypatch.setattr(
        "pipeline.stripe_billing.stripe.Subscription.retrieve",
        lambda sid: {
            "id": sid,
            "metadata": {"user_id": "u1", "plan": "creator"},
            "current_period_end": 1788000000,
        },
    )
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    # First delivery grants (True), second is deduped (False).
    grant_calls = {"n": 0}
    def fake_grant_once(**kw):
        grant_calls["n"] += 1
        return grant_calls["n"] == 1
    monkeypatch.setattr("pipeline.stripe_billing.record_grant_once", fake_grant_once)

    first = handle_webhook(b"{}", "sig")
    assert first.handled
    assert "+60" in first.note

    second = handle_webhook(b"{}", "sig")
    assert second.handled
    assert second.note == "duplicate invoice, no-op"
    assert grant_calls["n"] == 2


def test_handle_webhook_subscription_deleted_resets_plan(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"current_plan": "starter"}
    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"user_id": "u1"}}},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["current_plan"] == "free"


def test_handle_webhook_unknown_event_is_ignored(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: {"type": "ping", "data": {"object": {}}})
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled is False


def test_handle_webhook_uses_item_period_end_for_newer_stripe(stripe_env, mock_db, monkeypatch):
    """Newer Stripe API (2025+) puts current_period_end on items.data[0],
    not on the subscription itself. Make sure we still write the right
    period_end on upsert_user_profile."""
    fake_event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "inv_2", "subscription": "sub_x"}},
    }
    # Newer Stripe: no top-level current_period_end; it's on the SubscriptionItem
    monkeypatch.setattr(
        "pipeline.stripe_billing.stripe.Subscription.retrieve",
        lambda sid: {
            "id": sid,
            "metadata": {"user_id": "u1", "plan": "starter"},
            "items": {"data": [{"current_period_end": 1781186948}]},
            # No "current_period_end" at top level — that's the new API shape
        },
    )
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    # 2026-06-11T... — derived from 1781186948 unix ts
    saved = mock_db["profiles"]["u1"]
    assert saved["current_plan"] == "starter"
    assert saved["current_period_end"] is not None
    assert "2026" in saved["current_period_end"]


def test_handle_webhook_subscription_updated_persists_cancel_flag(
    stripe_env, mock_db, monkeypatch,
):
    """When the user schedules a cancel via Customer Portal, Stripe fires
    customer.subscription.updated with cancel_at_period_end=True. We must
    persist that flag so the UI can show 'Cancels on YYYY-MM-DD' instead
    of 'Renews on YYYY-MM-DD'."""
    fake_event = {
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_x",
            "metadata": {"user_id": "u1", "plan": "starter"},
            "items": {"data": [{"current_period_end": 1781186948}]},
            "cancel_at_period_end": True,
        }},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["cancel_at_period_end"] is True


def test_handle_webhook_invoice_paid_reads_parent_subscription_details(
    stripe_env, mock_db, monkeypatch,
):
    """Stripe 2025+ invoice payload drops top-level `subscription` and moves
    the id (plus metadata) into `parent.subscription_details`. Real-world
    regression: signing up returned 200 from our webhook but no credits
    landed because invoice.get("subscription") was None."""
    fake_event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {
            "id": "in_new_shape",
            # NO top-level 'subscription' field (newer API)
            "parent": {
                "subscription_details": {
                    "subscription": "sub_new",
                    "metadata": {"user_id": "u1", "plan": "starter"},
                },
            },
        }},
    }
    monkeypatch.setattr(
        "pipeline.stripe_billing.stripe.Subscription.retrieve",
        lambda sid: {
            "id": sid,
            # The subscription itself may STILL have metadata, but in some
            # newer flows it lives only on the invoice parent. Force the
            # handler to use the parent path by leaving it blank here.
            "metadata": {},
            "items": {"data": [{"current_period_end": 1781337199}]},
        },
    )
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled, outcome.note
    last_tx = mock_db["transactions"][-1]
    assert last_tx["amount"] == 12  # PLAN_GRANTS["starter"]
    assert mock_db["profiles"]["u1"]["current_plan"] == "starter"


def test_handle_webhook_subscription_deleted_clears_cancel_flag(
    stripe_env, mock_db, monkeypatch,
):
    """Once the cancel actually takes effect (end of period), the subscription
    is deleted — we reset cancel_at_period_end to False alongside plan/free."""
    mock_db["profiles"]["u1"] = {
        "current_plan": "starter", "cancel_at_period_end": True,
    }
    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"user_id": "u1"}}},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["current_plan"] == "free"
    assert mock_db["profiles"]["u1"]["cancel_at_period_end"] is False


def test_stripe_api_version_is_pinned():
    import pipeline.stripe_billing  # noqa: F401
    import stripe
    assert stripe.api_version == "2026-04-22.dahlia"


def test_charge_dispute_claws_back_grant(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    clawed = {}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: ("u1", 60))
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_1"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.dispute.created",
                                      "data": {"object": {"charge": "ch_1"}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled
    assert clawed["amount"] == -60 and clawed["kind"] == "chargeback_clawback"
    assert clawed["user_id"] == "u1" and clawed["reference_id"] == "ch_1"


def test_charge_refunded_claws_back_grant(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    clawed = {}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: ("u1", 12))
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_2"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.refunded",
                                      "data": {"object": {"id": "ch_2", "refunded": True}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled and clawed["amount"] == -12 and clawed["reference_id"] == "ch_2"


def test_charge_dispute_no_grant_is_safe_noop(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    called = {"n": 0}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: None)
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_none"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.dispute.created",
                                      "data": {"object": {"charge": "ch_3"}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled and called["n"] == 0
