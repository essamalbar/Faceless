"""Integration tests for per-clip credit deduction in the worker.

Pricing (locked 2026-05-13): 1 credit = 1 clip regardless of duration.
"""
from __future__ import annotations

from pipeline.auth import User


def test_per_clip_deduct_then_refund_on_failure(monkeypatch):
    """When a 6-clip run has clip 4 fail, 6 charges + 1 refund land in the
    ledger — net charge for the 5 that worked, refund for the 1 that failed."""
    user = User(id="u1", email="alice@example.com", role="user")

    deducted: list[int] = []
    refunded: list[int] = []
    monkeypatch.setattr(
        "pipeline.credits.check_or_deduct",
        lambda u, *, amount, run_id, reason: deducted.append(amount) or 999,
    )
    monkeypatch.setattr(
        "pipeline.credits.refund",
        lambda u, *, amount, run_id, reason: refunded.append(amount),
    )

    from pipeline.video import _charge_and_submit_clip

    submit_results = [True, True, True, False, True, True]  # clip 4 fails
    submit_calls = iter(submit_results)

    def fake_submit(beat, *, clip_index):
        ok = next(submit_calls)
        if not ok:
            raise RuntimeError("submit failed")
        return {"url": "https://generated/clip"}

    beats = [{"clip_duration_s": 10.0} for _ in range(6)]
    successes = 0
    for i, beat in enumerate(beats):
        try:
            _charge_and_submit_clip(
                user=user, run_id="run-x", beat=beat, clip_index=i,
                submit_fn=fake_submit,
            )
            successes += 1
        except RuntimeError:
            pass

    assert successes == 5  # clips 1,2,3,5,6 succeed; 4 fails
    # Each clip charges exactly 1 credit, regardless of clip_duration_s.
    assert deducted == [1, 1, 1, 1, 1, 1]
    assert refunded == [1]  # only the failed clip refunded


def test_per_clip_charge_is_always_one_credit(monkeypatch):
    """1 credit = 1 clip is a flat rate — a 4-second clip and a 12-second
    clip both cost the same."""
    user = User(id="u1", email="alice@example.com", role="user")
    charged: list[int] = []
    monkeypatch.setattr(
        "pipeline.credits.check_or_deduct",
        lambda u, *, amount, run_id, reason: charged.append(amount) or 999,
    )
    monkeypatch.setattr("pipeline.credits.refund", lambda *a, **kw: None)

    from pipeline.video import _charge_and_submit_clip
    for dur in (4.0, 8.0, 12.0):
        _charge_and_submit_clip(
            user=user, run_id="r", beat={"clip_duration_s": dur},
            clip_index=0, submit_fn=lambda b, *, clip_index: {"url": "x"},
        )
    assert charged == [1, 1, 1]
