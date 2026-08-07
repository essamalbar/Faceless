# Tier-4B Auth Hardening — Design

**Date:** 2026-08-07
**Status:** approved to proceed (user: "complete the Tier-4") — spec for the record
**Scope:** Second Tier-4 sub-project (B auth). Three items from `docs/GO-LIVE-READINESS.md` Tier 4: (B1) **email-confirmation backstop**, (B2) **password-reset flow**, (B3) **service-token-leak build guard**.

## Context (verified 2026-08-07)

- `pipeline/auth.py`: `verify_supabase_jwt` decodes the Supabase JWT (HS256 or ES256/RS256-via-JWKS), checks `aud="authenticated"` + `sub`, and builds `User(id=sub, email=payload.get("email"), role="user")`. **No email-confirmation claim is inspected.** Supabase's project-level "Confirm email" toggle already blocks unconfirmed users from getting a session — so a code check is a *backstop* for a misconfigured project, not the primary control.
- Flutter `login_screen.dart`: sign-in / sign-up only — **no forgot-password / recovery flow**.
- `scripts/run-app.sh`: bakes `FACELESS_API_TOKEN` via `--dart-define` for **local** dev; `scripts/build-and-push.sh` bakes it **empty** for prod (per CLAUDE.md). Risk is only if `run-app.sh` were misused to produce a public build.

## Architecture

### B1 — Email-confirmation backstop (conservative, default-allow)
- **`pipeline/auth.py`**: add `email_confirmed: bool = True` to `User`. In `verify_supabase_jwt`, set it from whatever confirmation signal the JWT carries, defaulting to **True (allow)** when no such claim is present:
  ```python
  confirmed = True
  if payload.get("email_confirmed_at") is not None:
      confirmed = True
  elif "email_confirmed_at" in payload:            # present but null → explicitly unconfirmed
      confirmed = False
  else:
      um = payload.get("user_metadata") or {}
      if um.get("email_verified") is False or payload.get("email_verified") is False:
          confirmed = False
  ```
  (Only an **explicit** unconfirmed signal flips it to False; an absent claim stays True so legit users are never blocked. Service tokens: `email_confirmed=True`.)
- **`pipeline/api.py`**: `_require_email_confirmed(user)` — a soft-gate (service bypass) raising `HTTPException(403, {"code": "email_not_confirmed"})` when `user.email_confirmed is False`. Call it alongside `_require_terms_accepted(user)` in the paid/generation endpoints (reuse the same call sites). Surface `email_confirmed` on `GET /billing/plan` (from the token, no DB).
- Rationale: near-zero risk (default-allow), satisfies "soft-gate spend if unconfirmed" as a real backstop for the misconfig case.

### B2 — Password-reset flow (Flutter + Supabase, no backend)
- `login_screen.dart` (signIn mode): a **"Forgot password?"** link → prompts for the email → `Supabase.instance.client.auth.resetPasswordForEmail(email, redirectTo: <app deep link>)` → shows "check your email".
- Handle the recovery return: `onAuthStateChange` emits `AuthChangeEvent.passwordRecovery` → route to a small **`reset_password_screen.dart`** (new password + confirm → `auth.updateUser(UserAttributes(password: ...))` → back to app). Wire the event in `main.dart`'s existing auth-state stream.
- No backend/API changes (Supabase handles the email + token).

### B3 — Service-token-leak build guard
- **`scripts/build-and-push.sh`**: before the `flutter build web`, assert the prod bundle is built with an **empty** `FACELESS_API_TOKEN` dart-define (it already is) — make it explicit + fail loudly if a non-empty token would be baked:
  ```bash
  if [ -n "${FACELESS_API_TOKEN:-}" ] && [ "${ALLOW_TOKEN_IN_PROD_BUILD:-0}" != "1" ]; then
    echo "ERROR: refusing to bake FACELESS_API_TOKEN into the PUBLIC web bundle." >&2
    echo "       The prod build must ship an empty token (users auth via Supabase)." >&2
    exit 1
  fi
  ```
  (The escape hatch `ALLOW_TOKEN_IN_PROD_BUILD=1` is documented but off by default — the guard is the point.)
- Add a one-line note to `scripts/run-app.sh`'s header that it is **local-dev only** (bakes the service token) and must never be used to produce a public build.

## Testing
- **`tests/test_auth.py`** (extend; mocked JWTs — the file already builds/decodes test tokens): `email_confirmed` is True when the claim is absent, True when `email_confirmed_at` set, **False** when `email_confirmed_at` present-and-null / `email_verified: false`. Service token → `email_confirmed=True`.
- **`tests/test_legal.py`** or `test_api.py`: a paid endpoint 403s `email_not_confirmed` when `require_user` yields `email_confirmed=False`; passes when True; service bypass. `/billing/plan` exposes `email_confirmed`. (The autouse `_auto_accept_terms` fixture keeps the terms gate transparent; email-confirm defaults True so existing tests are unaffected unless they build an explicitly-unconfirmed token.)
- **`scripts/build-and-push.sh`**: `bash -n` + reviewed by reading (operator script).
- **Flutter**: `dart analyze` the changed/new screens → 0 issues (use `dart analyze`, not `flutter analyze`).
- **Baseline**: clean-env suite **860 passed, 0 failed**; no new failures.

## Deferred / operator
- None new for B (all code). The Supabase project "Confirm email" toggle remains the primary email-confirmation control (operator).

## Key invariants
- Conservative default-allow on B1 (never block a legit user on an absent claim). Service tokens bypass all gates. External services mocked in tests. New Dart via `dart analyze`.
