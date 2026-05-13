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
    get_balance,
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

    Note: simple non-locked variant — concurrent runs from the same user could
    transiently overspend by one clip. Accepted tradeoff for v1.
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
