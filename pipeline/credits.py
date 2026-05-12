"""Credit ledger business logic.

Thin layer on top of pipeline.db that adds:
  - The "service-token bypass" rule (admin/CLI never spends credits)
  - Idempotent signup-grant on first authenticated request
  - Raises InsufficientCredits when a deduction would push the balance below zero

Every entry point takes a `User` (from pipeline.auth) — never a bare user_id —
so the bypass check happens in one place.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.auth import User
from pipeline.db import (
    _client,
    get_balance,
    get_user_profile,
    record_transaction,
    upsert_user_profile,
)

SIGNUP_GRANT = 60
PLAN_GRANTS = {"starter": 60, "creator": 250, "pro": 800}
TOPUP_PACKS = {"topup_30": 30, "topup_100": 100, "topup_300": 300}


@dataclass(frozen=True)
class InsufficientCredits(Exception):
    """Raised when a deduction would push the balance below zero."""
    balance: int
    required: int

    def __str__(self) -> str:
        return f"insufficient credits: have {self.balance}, need {self.required}"


def _is_service(user: User) -> bool:
    return user.role == "service"


def _has_signup_grant(user_id: str) -> bool:
    """True iff a `signup_grant` transaction already exists for this user.

    Used as the idempotency guard for ensure_signup_grant — it survives the
    concurrent first-auth race that "check the profile" doesn't, because the
    profile is upserted BEFORE the transaction is inserted. Two parallel calls
    can both see no profile → both upsert (idempotent) → both insert a grant.
    Checking for the grant row itself is the authoritative guard.
    """
    resp = (
        _client()
        .table("credit_transactions")
        .select("id")
        .eq("user_id", user_id)
        .eq("kind", "signup_grant")
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def ensure_signup_grant(user: User) -> None:
    """If user has no signup_grant transaction yet, create their profile + grant
    SIGNUP_GRANT credits. Idempotent — safe to call on every authenticated
    request, and safe under concurrent first-auth (modulo Postgres
    serializability; for absolute safety, add a partial unique index — see
    docs/superpowers/specs/2026-05-11-stripe-credits-design.md)."""
    if _is_service(user):
        return
    if _has_signup_grant(user.id):
        return  # already granted
    upsert_user_profile(user.id, current_plan="free")
    record_transaction(
        user_id=user.id,
        amount=SIGNUP_GRANT,
        kind="signup_grant",
        description=f"Welcome — {SIGNUP_GRANT} free credits",
    )


def check_or_deduct(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> int:
    """Verify the user has at least `amount` credits, then deduct.
    Returns the new balance. Service tokens bypass entirely.

    Note: this is the simple non-locked variant — concurrent runs from the same
    user could transiently overspend by one clip (~$0.10). The spec calls this
    out as an accepted tradeoff for v1.
    """
    if _is_service(user):
        return 10**9  # sentinel — callers won't divide by this
    balance = get_balance(user.id)
    if balance < amount:
        raise InsufficientCredits(balance=balance, required=amount)
    record_transaction(
        user_id=user.id,
        amount=-amount,
        kind="run_charge",
        reference_id=run_id,
        description=reason,
    )
    return balance - amount


def refund(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> None:
    """Insert a positive transaction. Used when a Veo clip fails after deduction.
    No-op for service tokens."""
    if _is_service(user):
        return
    record_transaction(
        user_id=user.id,
        amount=amount,
        kind="run_refund",
        reference_id=run_id,
        description=reason,
    )
