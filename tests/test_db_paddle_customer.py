from __future__ import annotations

from types import SimpleNamespace

import pipeline.db as db

# Captured at import time, i.e. before tests/conftest.py's autouse
# `_auto_accept_terms` fixture monkeypatches `pipeline.db.get_user_profile`
# for the duration of each test. Calling the module attribute directly from
# inside the test would hit that fixture's stub instead of the real
# implementation this test exercises.
_get_user_profile = db.get_user_profile


def test_get_user_profile_maps_paddle_customer_id(monkeypatch):
    row = {
        "id": "u1", "stripe_customer_id": None, "paddle_customer_id": "ctm_1",
        "current_plan": "free", "current_period_end": None,
        "cancel_at_period_end": False, "payment_status": "active",
    }

    class _Resp:
        data = row

    class _Tbl:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def single(self, *a, **k): return self
        def maybe_single(self, *a, **k): return self
        def execute(self): return _Resp()

    monkeypatch.setattr(db, "_client", lambda: SimpleNamespace(table=lambda *_: _Tbl()))
    p = _get_user_profile("u1")
    assert p is not None and p.paddle_customer_id == "ctm_1"
