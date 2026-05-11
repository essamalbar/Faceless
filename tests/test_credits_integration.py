"""Integration test for per-clip credit deduction in the worker."""
from __future__ import annotations

import pytest

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
        return {"url": "https://kie/clip"}

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
    assert deducted == [10, 10, 10, 10, 10, 10]  # all 6 deducted up front
    assert refunded == [10]  # only the failed clip refunded


def test_per_clip_charges_use_ceil_of_seconds(monkeypatch):
    """A 9.5-second clip charges 10 credits (ceil), matching how Kie bills."""
    user = User(id="u1", email="alice@example.com", role="user")
    charged: list[int] = []
    monkeypatch.setattr(
        "pipeline.credits.check_or_deduct",
        lambda u, *, amount, run_id, reason: charged.append(amount) or 999,
    )
    monkeypatch.setattr("pipeline.credits.refund", lambda *a, **kw: None)

    from pipeline.video import _charge_and_submit_clip
    _charge_and_submit_clip(
        user=user, run_id="r", beat={"clip_duration_s": 9.5},
        clip_index=0, submit_fn=lambda b, *, clip_index: {"url": "x"},
    )
    assert charged == [10]
