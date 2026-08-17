from __future__ import annotations

import pytest

from pipeline import credits as _credits_mod, db as _db_mod
from pipeline.auth import User
from pipeline.kie import KieClient, KieError
from pipeline.perform import _best_hook_offset, render_avatar


# --- hook selection (pure) --------------------------------------------------

def test_best_hook_offset_picks_energy_peak():
    # low(0-10s) / high(10-20s) / low(20-30s); a 10s hook must land on the peak.
    rms = [0.0] * 10 + [1.0] * 10 + [0.0] * 10
    assert _best_hook_offset(rms, hop_s=1.0, hook_s=10.0, total_s=30.0) == 10.0


def test_best_hook_offset_clamps_window_into_track():
    # flat energy near the end → offset must keep the window inside [0, total].
    rms = [1.0] * 30
    off = _best_hook_offset(rms, hop_s=1.0, hook_s=10.0, total_s=30.0)
    assert 0.0 <= off <= 20.0


def test_best_hook_offset_short_track_returns_zero():
    # track shorter than the hook → start at 0.
    assert _best_hook_offset([1.0, 2.0], hop_s=1.0, hook_s=30.0, total_s=2.0) == 0.0


# --- kie avatar submit ------------------------------------------------------

def test_submit_avatar_job_posts_image_and_audio(monkeypatch):
    client = KieClient(api_key="stub")
    captured: dict = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"data": {"taskId": "task-123"}}

    monkeypatch.setattr(client, "_post_json", fake_post)
    tid = client.submit_avatar_job(
        image_url="http://img", audio_url="http://aud", model="kling/ai-avatar",
        prompt="sing it")
    assert tid == "task-123"
    assert captured["body"]["model"] == "kling/ai-avatar"
    assert captured["body"]["input"]["image_url"] == "http://img"
    assert captured["body"]["input"]["audio_url"] == "http://aud"
    # Kie rejects a submit without a prompt ("prompt is required") — it must be
    # in the request body.
    assert captured["body"]["input"]["prompt"] == "sing it"


def test_submit_avatar_job_missing_taskid_raises(monkeypatch):
    client = KieClient(api_key="stub")
    monkeypatch.setattr(client, "_post_json", lambda p, b: {"data": {}})
    with pytest.raises(KieError):
        client.submit_avatar_job(
            image_url="i", audio_url="a", model="m", prompt="p")


# --- orchestration ----------------------------------------------------------

def test_render_avatar_submits_waits_downloads(monkeypatch, tmp_path):
    client = KieClient(api_key="stub")
    seen: dict = {}
    monkeypatch.setattr(client, "submit_avatar_job",
                        lambda **k: seen.update(submit=k) or "t1")
    monkeypatch.setattr(
        client, "wait_for_unified_video", lambda tid, **k: "http://video.mp4")

    def fake_dl(url, out):
        seen["url"] = url
        out.write_text("mp4")

    monkeypatch.setattr(client, "download", fake_dl)
    out = tmp_path / "perform.mp4"
    render_avatar(client=client, image_url="i", audio_url="a", model="m",
                  prompt="p", out_path=out)
    assert seen["url"] == "http://video.mp4"
    # prompt must be forwarded to the submit call (Kie requires it).
    assert seen["submit"]["prompt"] == "p"
    assert out.exists()


# --- perform credits layer (atomic claim / release) -------------------------
# These unit-test pipeline.credits.claim_perform / release_perform_claim over a
# MOCKED pipeline.db (the RPC verdict), verifying the thin business layer: it
# maps the atomic verdict to the right return/exception, auto-refunds a stolen
# (crashed) prior charge, and passes the service-token flag through. The atomic
# in-flight serialization itself lives in the Postgres claim_perform function
# and is out of scope for a mocked DB (see the note in tests/test_song_api.py).


def _perform_user() -> User:
    return User(id="u-1", email="u@example.com", role="user")


def _perform_service_user() -> User:
    return User(id="admin", email=None, role="service")


def test_claim_perform_ok_returns_balance_and_does_not_refund(monkeypatch):
    monkeypatch.setattr(
        _db_mod, "claim_perform_atomic",
        lambda **k: {"ok": True, "balance": 7, "stolen_reference_id": None})
    refunds: list = []
    monkeypatch.setattr(
        _credits_mod, "refund_run_charges",
        lambda *a, **k: refunds.append(k) or 0)

    bal = _credits_mod.claim_perform(
        _perform_user(), run_id="r", amount=3, reference_id="r:perform:x",
        reason="perform-spend", stale_seconds=900)
    assert bal == 7
    assert refunds == []  # no stolen ref → nothing to net back


def test_claim_perform_in_flight_verdict_raises(monkeypatch):
    monkeypatch.setattr(
        _db_mod, "claim_perform_atomic",
        lambda **k: {"ok": False, "reason": "in_flight"})
    with pytest.raises(_credits_mod.PerformInFlight) as excinfo:
        _credits_mod.claim_perform(
            _perform_user(), run_id="r", amount=3, reference_id="ref",
            reason="perform-spend", stale_seconds=900)
    assert excinfo.value.run_id == "r"


def test_claim_perform_insufficient_verdict_raises_with_balance(monkeypatch):
    monkeypatch.setattr(
        _db_mod, "claim_perform_atomic",
        lambda **k: {"ok": False, "reason": "insufficient", "balance": 1})
    with pytest.raises(_credits_mod.InsufficientCredits) as excinfo:
        _credits_mod.claim_perform(
            _perform_user(), run_id="r", amount=3, reference_id="ref",
            reason="perform-spend", stale_seconds=900)
    assert excinfo.value.balance == 1
    assert excinfo.value.required == 3


def test_claim_perform_refunds_stolen_reference_then_returns_balance(monkeypatch):
    monkeypatch.setattr(
        _db_mod, "claim_perform_atomic",
        lambda **k: {"ok": True, "balance": 4,
                     "stolen_reference_id": "r:perform:CRASHED"})
    refunds: list[str] = []
    monkeypatch.setattr(
        _credits_mod, "refund_run_charges",
        lambda user, *, run_id, reason: refunds.append(run_id) or 3)

    bal = _credits_mod.claim_perform(
        _perform_user(), run_id="r", amount=3, reference_id="r:perform:new",
        reason="perform-spend", stale_seconds=900)
    assert bal == 4
    # The crashed prior render's charge was netted back exactly once, on the
    # STOLEN ref (never the new attempt's ref, never the bare run id).
    assert refunds == ["r:perform:CRASHED"]


def test_claim_perform_service_passes_is_service_and_skips_ledger(monkeypatch):
    """A service token still takes the claim (is_service=True). Even when the
    verdict carries a stolen ref, the real refund_run_charges no-ops for service
    BEFORE touching the ledger — proven by making any ledger access blow up."""
    captured: dict = {}

    def fake_atomic(**k):
        captured.update(k)
        return {"ok": True, "balance": 10**9,
                "stolen_reference_id": "r:perform:CRASHED"}

    monkeypatch.setattr(_db_mod, "claim_perform_atomic", fake_atomic)

    def _no_ledger(*a, **k):
        raise AssertionError("service refund must not touch the ledger")

    monkeypatch.setattr(_credits_mod, "list_transactions", _no_ledger)
    monkeypatch.setattr(_credits_mod, "record_transaction", _no_ledger)

    bal = _credits_mod.claim_perform(
        _perform_service_user(), run_id="r", amount=3, reference_id="r:perform:new",
        reason="perform-spend", stale_seconds=900)
    assert captured["is_service"] is True
    assert captured["user_id"] == "admin"
    assert bal == 10**9


def test_release_perform_claim_delegates_to_db_with_exact_kwargs(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        _db_mod, "release_perform_claim", lambda **k: captured.update(k))
    _credits_mod.release_perform_claim(run_id="r", reference_id="ref")
    assert captured == {"run_id": "r", "reference_id": "ref"}
