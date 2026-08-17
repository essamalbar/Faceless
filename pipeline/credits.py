"""Credit ledger business logic.

Thin layer on top of pipeline.db that adds:
  - The "service-token bypass" rule (admin/CLI never spends credits)
  - Raises InsufficientCredits when a deduction would push the balance below zero

Pricing model (locked 2026-05-13):
  - 1 credit = 1 video clip. Each beat in a script becomes one clip.
  - No welcome credit. Script generation is free for anyone signed in;
    paid stages (character sheet + clip generation + assembly) require
    a subscription that grants monthly credits.
  - Plans: starter 12 cr/mo, creator 60 cr/mo, pro 200 cr/mo.

Every entry point takes a `User` (from pipeline.auth) — never a bare user_id —
so the bypass check happens in one place.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.auth import User
from pipeline.db import (
    deduct_credits_atomic,
    get_balance,
    list_transactions,
    record_transaction,
)

PLAN_GRANTS = {"starter": 12, "creator": 60, "pro": 200}
TOPUP_PACKS: dict[str, int] = {}  # disabled in v1; kept for future


@dataclass(frozen=True)
class InsufficientCredits(Exception):
    """Raised when a deduction would push the balance below zero."""
    balance: int
    required: int

    def __str__(self) -> str:
        return f"insufficient credits: have {self.balance}, need {self.required}"


@dataclass(frozen=True)
class PerformInFlight(Exception):
    """Raised when a "Make me sing this" render is already in flight for this
    run — a second concurrent/rapid perform request is refused before it can
    charge."""
    run_id: str

    def __str__(self) -> str:
        return f"a perform render is already in flight for run {self.run_id}"


def _is_service(user: User) -> bool:
    return user.role == "service"


def check_or_deduct(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> int:
    """Verify the user has at least `amount` credits, then deduct.
    Returns the new balance. Service tokens bypass entirely.

    Delegates the check-and-deduct to an atomic Postgres function
    (`deduct_credits`) that serializes concurrent runs from the same user
    with a per-user advisory lock — so two parallel approvals can't both
    pass the balance check and drive the balance negative.
    """
    if _is_service(user):
        return 10**9  # sentinel — callers won't divide by this
    new_balance = deduct_credits_atomic(
        user_id=user.id, amount=amount, kind="run_charge",
        reference_id=run_id, description=reason,
    )
    if new_balance < 0:
        raise InsufficientCredits(balance=get_balance(user.id), required=amount)
    return new_balance


def refund(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> None:
    """Insert a positive transaction. Used when a clip fails after deduction.
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


def refund_run_charges(
    user: User,
    *,
    run_id: str,
    reason: str,
) -> int:
    """Refund every credit the user has net-paid for `run_id` so far.

    Used when a stage AFTER clip generation fails (assembly, captions,
    music, faststart, etc.) — the user has been charged per-clip but
    will never see a finished video. This restores the credits.

    Computes net = sum of all transactions for (user_id, run_id) and,
    if the net is negative, inserts a single positive transaction to
    bring it back to zero. So per-clip refunds that already happened
    (Veo timeout, etc.) are accounted for: we never over-refund.

    Returns the amount refunded (0 if there was nothing net-charged).
    No-op for service tokens.
    """
    if _is_service(user):
        return 0
    # Read all ledger entries tied to this run for this user. The list
    # query in pipeline.db is per-user already; we just filter by
    # reference_id in memory since the table is tiny.
    txs = list_transactions(user.id, limit=500)
    net = sum(t.amount for t in txs if t.reference_id == run_id)
    if net >= 0:
        return 0  # nothing to refund, or already refunded
    refund_amount = -net
    record_transaction(
        user_id=user.id,
        amount=refund_amount,
        kind="run_refund",
        reference_id=run_id,
        description=reason,
    )
    return refund_amount


def claim_perform(
    user: User,
    *,
    run_id: str,
    amount: int,
    reference_id: str,
    reason: str,
    stale_seconds: int,
) -> int:
    """Atomically guard + charge one "Make me sing this" render. Returns the new
    balance.

    Exactly one caller can hold a run's in-flight perform at a time, across all
    Cloud Run instances — the guard is a single Postgres transaction (per-run +
    per-user advisory locks), not the old cross-instance-unsafe file lock. A
    crashed prior render's claim (older than ``stale_seconds``) is stolen and its
    charge auto-refunded here so the run is never wedged.

    Raises:
      PerformInFlight     — a live render already owns this run.
      InsufficientCredits — the balance can't cover ``amount`` (nothing charged).

    Service tokens bypass the ledger but STILL take the claim, so a service redo
    cannot double-spawn a render."""
    from pipeline.db import claim_perform_atomic
    result = claim_perform_atomic(
        user_id=user.id, run_id=run_id, amount=amount,
        reference_id=reference_id, description=reason,
        is_service=_is_service(user), stale_seconds=stale_seconds,
    )
    stolen = result.get("stolen_reference_id")
    if stolen:
        # A prior render crashed past the staleness ceiling; its charge never
        # delivered a video. Net it back to zero (idempotent) before proceeding.
        refund_run_charges(
            user, run_id=stolen, reason="perform render abandoned — auto-refund")
    if not result.get("ok"):
        if result.get("reason") == "in_flight":
            raise PerformInFlight(run_id=run_id)
        raise InsufficientCredits(
            balance=int(result.get("balance", 0)), required=amount)
    return int(result.get("balance", 0))


def release_perform_claim(*, run_id: str, reference_id: str) -> None:
    """Release the in-flight perform claim for ``run_id`` — but only if it still
    holds ``reference_id`` (compare-and-delete). Idempotent: a no-op if the claim
    was already released or a newer attempt now owns the run. Call this on every
    terminal outcome (success, failure, spawn error) so a redo can re-claim."""
    from pipeline.db import release_perform_claim as _release
    _release(run_id=run_id, reference_id=reference_id)
