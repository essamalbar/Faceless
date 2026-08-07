# Tier-4B Auth Hardening Implementation Plan

> REQUIRED SUB-SKILL: subagent-driven-development (synchronous, given background agents haven't survived idle gaps). Design: `docs/superpowers/specs/2026-08-07-tier4b-auth-hardening-design.md`.

**Goal:** Email-confirmation backstop (conservative soft-gate), a Flutter password-reset flow, and a build guard so the admin service token can't leak into a public web bundle.

**Verification env:** clean-env pytest (sourcing `.env` flips the failing set). Baseline **860 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```
Flutter: `dart analyze <files>` (NOT `flutter analyze` — it hangs).

---

## Task B1 — Email-confirmation backstop (backend)

**Files:** `pipeline/auth.py`, `pipeline/api.py`; tests `tests/test_auth.py`, `tests/test_legal.py`.

- [ ] **Tests first:** (a) `tests/test_auth.py`: `verify_supabase_jwt`/`require_user` yields `email_confirmed True` when no confirmation claim, `True` when `email_confirmed_at` set, `False` when `email_confirmed_at` present-and-`null` and when `user_metadata.email_verified` is `False`; service token → `True`. (b) `tests/test_legal.py`: a paid endpoint (e.g. `POST /songs`) 403s `{"code":"email_not_confirmed"}` when `require_user` is overridden to yield `email_confirmed=False`; passes when True; `/billing/plan` exposes `email_confirmed`.
- [ ] **Implement:**
  - `pipeline/auth.py`: add `email_confirmed: bool = True` to `User`; in `verify_supabase_jwt`, compute it per the spec's snippet (explicit-unconfirmed → False, else True); service-token `User(...)` in `require_user` gets `email_confirmed=True`.
  - `pipeline/api.py`: `_require_email_confirmed(user)` (service bypass; 403 `email_not_confirmed` when `user.email_confirmed is False`); call it immediately after `_require_terms_accepted(user)` in the same paid/generation endpoints. Add `email_confirmed: bool = True` to `PlanResponse`; set from `user.email_confirmed` in `get_plan_endpoint` (service → True).
- [ ] Run clean-env suite → green (report count). Commit: `feat(auth): email-confirmation backstop (conservative soft-gate)`.

## Task B2 — Password-reset flow (Flutter)

**Files:** `lib/screens/login_screen.dart`, new `lib/screens/reset_password_screen.dart`, `lib/main.dart`.

- [ ] **Implement:**
  - `login_screen.dart` (signIn mode): a "Forgot password?" `TextButton` → dialog asking for email (prefill from the email field) → `Supabase.instance.client.auth.resetPasswordForEmail(email)` → SnackBar "Check your email for a reset link." Guard errors.
  - `reset_password_screen.dart` (new): new-password + confirm fields (min 8, must match) → `Supabase.instance.client.auth.updateUser(UserAttributes(password: pw))` → on success pop to home with a success message.
  - `main.dart`: in the existing `onAuthStateChange` handling, on `AuthChangeEvent.passwordRecovery` push `ResetPasswordScreen`.
- [ ] `dart analyze lib/screens/login_screen.dart lib/screens/reset_password_screen.dart lib/main.dart` → 0 issues. Commit: `feat(auth): Flutter password-reset + recovery flow`.

## Task B3 — Service-token-leak build guard

**Files:** `scripts/build-and-push.sh`, `scripts/run-app.sh` (header note).

- [ ] **Implement:** in `build-and-push.sh`, before `flutter build web`, add the guard from the spec (refuse a non-empty `FACELESS_API_TOKEN` in the prod build unless `ALLOW_TOKEN_IN_PROD_BUILD=1`). Add a header line to `run-app.sh` marking it local-dev-only. `bash -n` both.
- [ ] Commit: `fix(auth): guard against baking the service token into the public build`.

## Task B4 — Verify + handoff
- [ ] Full clean-env suite → 0 failed (report count); `dart analyze` clean; `bash -n` clean.
- [ ] Append a Tier-4B note to `docs/GO-LIVE-READINESS.md` (email-confirm backstop is a code layer atop the Supabase "Confirm email" toggle; password reset shipped; token-leak guard added). Commit.
