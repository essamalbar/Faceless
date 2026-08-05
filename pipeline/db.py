"""Supabase-backed access for the credit ledger and user_profiles.

The backend uses the *service role* key (already in Secret Manager from B2)
so it can bypass RLS for ledger inserts. End users never touch this module
directly — they hit the FastAPI endpoints, which scope queries by their
authenticated user id.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from supabase import Client, create_client


@dataclass(frozen=True)
class UserProfile:
    id: str
    stripe_customer_id: str | None
    current_plan: str
    current_period_end: str | None  # ISO timestamp as Supabase returns it
    cancel_at_period_end: bool = False


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
            "current_period_end,cancel_at_period_end",
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
