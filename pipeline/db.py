"""Supabase-backed access for the credit ledger and user_profiles.

The backend uses the *service role* key (already in Secret Manager from B2)
so it can bypass RLS for ledger inserts. End users never touch this module
directly — they hit the FastAPI endpoints, which scope queries by their
authenticated user id.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from supabase import Client, create_client


@dataclass(frozen=True)
class UserProfile:
    id: str
    stripe_customer_id: str | None
    current_plan: str
    current_period_end: str | None  # ISO timestamp as Supabase returns it
    cancel_at_period_end: bool = False
    payment_status: str = "active"  # 'active' | 'past_due' (dunning flag)
    tos_accepted_version: str | None = None
    tos_accepted_at: str | None = None


@dataclass(frozen=True)
class Transaction:
    id: str
    user_id: str
    amount: int
    kind: str
    reference_id: str | None
    description: str | None
    created_at: str


@lru_cache(maxsize=1)
def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for db access",
        )
    return create_client(url, key)


def get_user_profile(user_id: str) -> UserProfile | None:
    # `.maybe_single()` returns data=None when there are 0 rows. `.single()`
    # would raise PGRST116 — which we'd then have to catch and translate to
    # None, every call site. A missing profile is the normal pre-signup-grant
    # state for newly-signed-up users; an exception isn't the right signal.
    resp = (
        _client()
        .table("user_profiles")
        .select(
            "id,stripe_customer_id,current_plan,"
            "current_period_end,cancel_at_period_end,payment_status,"
            "tos_accepted_version,tos_accepted_at",
        )
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if resp is None or not resp.data:
        return None
    d = resp.data
    return UserProfile(
        id=d["id"],
        stripe_customer_id=d.get("stripe_customer_id"),
        current_plan=d.get("current_plan", "free"),
        current_period_end=d.get("current_period_end"),
        cancel_at_period_end=bool(d.get("cancel_at_period_end", False)),
        payment_status=d.get("payment_status", "active"),
        tos_accepted_version=d.get("tos_accepted_version"),
        tos_accepted_at=d.get("tos_accepted_at"),
    )


def upsert_user_profile(user_id: str, **fields) -> None:
    payload = {"id": user_id, **fields}
    _client().table("user_profiles").upsert(payload).execute()


def get_balance(user_id: str) -> int:
    # `.maybe_single()` returns data=None when there are 0 rows (new user with
    # no transactions yet). `.single()` would raise PGRST116.
    resp = (
        _client()
        .table("user_balance")
        .select("user_id,balance")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if resp is None or not resp.data:
        return 0
    return int(resp.data.get("balance", 0))


def record_transaction(
    *,
    user_id: str,
    amount: int,
    kind: str,
    reference_id: str | None = None,
    description: str | None = None,
) -> None:
    payload = {
        "user_id": user_id,
        "amount": amount,
        "kind": kind,
        "reference_id": reference_id,
        "description": description,
    }
    _client().table("credit_transactions").insert(payload).execute()


def _is_unique_violation(exc: Exception) -> bool:
    s = str(exc).lower()
    return "23505" in s or "duplicate key" in s or "unique constraint" in s


def record_grant_once(*, user_id: str, amount: int, kind: str,
                      reference_id: str | None, description: str | None) -> bool:
    """Insert a grant transaction idempotently. Returns False (no-op) if a grant
    with the same (reference_id, kind) already exists — the unique index rejects
    it — so a duplicate Stripe webhook delivery never double-grants."""
    try:
        _client().table("credit_transactions").insert({
            "user_id": user_id, "amount": amount, "kind": kind,
            "reference_id": reference_id, "description": description,
        }).execute()
        return True
    except Exception as e:
        if _is_unique_violation(e):
            return False
        raise


def get_grant_by_reference(reference_id: str) -> tuple[str, int] | None:
    """(user_id, total granted credits) for the grant(s) recorded under this
    reference_id (subscription_renewal / topup), or None. Sizes a clawback."""
    resp = (
        _client()
        .table("credit_transactions")
        .select("user_id,amount,kind")
        .eq("reference_id", reference_id)
        .execute()
    )
    rows = [r for r in (resp.data or [])
            if r.get("kind") in ("subscription_renewal", "topup")]
    if not rows:
        return None
    return rows[0]["user_id"], sum(int(r["amount"]) for r in rows)


def deduct_credits_atomic(*, user_id: str, amount: int, kind: str,
                          reference_id: str, description: str) -> int:
    """Atomic check-and-deduct via the deduct_credits Postgres function
    (per-user advisory lock). Returns the new balance, or -1 if the balance
    was insufficient (nothing was deducted)."""
    resp = _client().rpc("deduct_credits", {
        "p_user_id": user_id, "p_amount": amount, "p_kind": kind,
        "p_reference_id": reference_id, "p_description": description,
    }).execute()
    return int(resp.data)


def record_rate_event(user_id: str, action: str) -> None:
    """Append one rate-limit event for (user, action). Backs the DB-backed
    daily song cap and the LLM draft/regen throttle — shared across all
    Cloud Run instances, unlike the old per-instance JSON file."""
    _client().table("rate_events").insert(
        {"user_id": user_id, "action": action}
    ).execute()


def count_rate_events(user_id: str, action: str, within_seconds: int) -> int:
    """Count this user's events for `action` in the last `within_seconds`.
    Uses count="exact" (resp.count) when the client populates it, falling
    back to len(data) otherwise — the window is tiny (soft caps), so either
    is cheap."""
    since = (
        datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
    ).isoformat()
    resp = (
        _client()
        .table("rate_events")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("action", action)
        .gte("created_at", since)
        .execute()
    )
    count = getattr(resp, "count", None)
    if count is not None:
        return count
    return len(resp.data or [])


def anonymize_user_profile(user_id: str) -> None:
    """Scrub PII from a user's profile on GDPR account deletion while keeping
    the row itself. Retained `credit_transactions` (tax/chargeback) still
    reference this `user_id`, so the row must survive — we only null the
    personal/billing fields and mark the plan as `deleted`. `payment_status`
    is reset to `active` so any retained dunning state is neutralized."""
    upsert_user_profile(
        user_id,
        stripe_customer_id=None,
        current_plan="deleted",
        tos_accepted_version=None,
        payment_status="active",
    )


def delete_auth_user(user_id: str) -> None:
    """Permanently delete the Supabase auth user via the service-role admin
    API. Irreversible. The financial ledger is intentionally NOT touched."""
    _client().auth.admin.delete_user(user_id)


def list_transactions(user_id: str, limit: int = 50) -> list[Transaction]:
    resp = (
        _client()
        .table("credit_transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        Transaction(
            id=r["id"], user_id=r["user_id"], amount=r["amount"],
            kind=r["kind"], reference_id=r.get("reference_id"),
            description=r.get("description"), created_at=r["created_at"],
        )
        for r in (resp.data or [])
    ]
