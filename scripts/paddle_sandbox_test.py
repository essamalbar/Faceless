"""Paddle sandbox smoke test — run via scripts/paddle-sandbox-test.sh.

Proves the shipped Paddle integration is correctly wired to YOUR sandbox
credentials, WITHOUT minting real credits:

  1. Checkout: calls create_subscription_checkout against sandbox-api.paddle.com
     with your PADDLE_API_KEY + PADDLE_PRICE_STARTER → expects a hosted checkout
     URL back. Proves the API key and price ids are valid.
  2. Webhook: forges a Paddle-Signature-signed `transaction.completed` with a
     ZERO total (a real Paddle event shape that the handler intentionally does
     NOT grant on), POSTs it to the local /paddle/webhook → expects HTTP 200 and
     the "zero-amount ... no grant" outcome. Then a bad signature → HTTP 400.
     Proves PADDLE_WEBHOOK_SECRET is wired and signature verification works.
     No credit_transactions rows are written.

Assumes the API is already running locally on $HARNESS_PORT (the .sh starts it),
PADDLE_ENV=sandbox, and .env is sourced.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request

PORT = os.environ.get("HARNESS_PORT", "8073")
BASE = f"http://127.0.0.1:{PORT}"
TEST_UID = "00000000-0000-0000-0000-0000000000aa"   # throwaway; cleaned up after
TEST_EMAIL = "paddle-harness@faceless-lab.test"

_ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global _ok
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        _ok = False


def test_checkout() -> None:
    print("[1/2] Checkout against Paddle sandbox (validates API key + price id)")
    from pipeline.auth import User
    from pipeline import paddle_billing
    try:
        url = paddle_billing.create_subscription_checkout(
            User(id=TEST_UID, email=TEST_EMAIL, role="user"),
            "starter",
            "https://faceless-lab.com/thanks",
            "https://faceless-lab.com/cancel",
        )
        check("checkout URL returned", isinstance(url, str) and url.startswith("http"),
              url[:70] + ("…" if len(url) > 70 else ""))
    except Exception as e:
        check("checkout URL returned", False, f"{type(e).__name__}: {e}")
    finally:
        # Clean up the throwaway profile row ensure_customer created.
        try:
            from pipeline import db
            db._client().table("user_profiles").delete().eq("id", TEST_UID).execute()
            print("       (cleaned up throwaway user_profiles row)")
        except Exception as e:
            print(f"       (cleanup note: {type(e).__name__}: {e})")


def _post_webhook(body: bytes, signature: str):
    req = urllib.request.Request(
        f"{BASE}/paddle/webhook", data=body, method="POST",
        headers={"Content-Type": "application/json", "Paddle-Signature": signature},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_webhook_signature() -> None:
    print("[2/2] Webhook signature + dispatch (validates PADDLE_WEBHOOK_SECRET)")
    secret = os.environ["PADDLE_WEBHOOK_SECRET"].strip()
    # A real-shaped transaction.completed with grand_total 0 → handler dispatches
    # but grants nothing (no ledger write).
    event = {
        "event_type": "transaction.completed",
        "data": {
            "id": "txn_harness_zero",
            "custom_data": {"user_id": TEST_UID, "plan": "starter"},
            "details": {"totals": {"grand_total": "0"}},
        },
    }
    body = json.dumps(event).encode()
    ts = str(int(time.time()))
    good = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()

    status, resp = _post_webhook(body, f"ts={ts};h1={good}")
    check("valid signature accepted (HTTP 200)", status == 200, f"HTTP {status} {resp[:80]}")
    check("zero-amount event granted nothing", '"handled": true' in resp and "zero-amount" in resp,
          resp[:90])

    status_bad, _ = _post_webhook(body, f"ts={ts};h1=deadbeefbad")
    check("bad signature rejected (HTTP 400)", status_bad == 400, f"HTTP {status_bad}")


def main() -> int:
    print("=== Paddle sandbox smoke test ===")
    print(f"PADDLE_ENV={os.environ.get('PADDLE_ENV')}  (must be 'sandbox' for this test)\n")
    test_checkout()
    print()
    test_webhook_signature()
    print()
    print("RESULT:", "ALL PASS ✅ — sandbox keys are correctly wired" if _ok
          else "FAILURES ✗ — see above")
    return 0 if _ok else 1


if __name__ == "__main__":
    sys.exit(main())
