# Tier-3 Legal Blockers — Design

**Date:** 2026-08-05
**Status:** approved (brainstorm) — pending spec review → implementation plan
**Scope:** The two Tier-3 go-live *hard blockers* from `docs/GO-LIVE-READINESS.md` (#10, #11): a **ToS/Privacy/refund acceptance gate** and an **ownership-attestation gate** on the copyright-exposed song endpoints. Stripe and the app stores require accepted legal terms; the cover/import features generate "faithful covers" of arbitrary audio and need an ownership gate. Moderation (deny-list) and GDPR (`/account/delete`, anonymize-keep-financials) are a decided-but-deferred fast-follow pass.

**Hard boundary:** this work does NOT author binding legal text. It builds the *mechanism* + display pages with **clearly-marked placeholder copy** the operator replaces with lawyer-reviewed ToS/Privacy/refund wording. Shipping fabricated legal documents as if real is out of scope and off-limits.

## Context (verified against code, 2026-08-05)

- **Signup is client-side Supabase** — `lib/screens/login_screen.dart` calls `Supabase.instance.client.auth.signUp(...)` (`_Mode.signUp`, ~line 78; 8-char password check ~line 51). The backend never sees the signup, so the acceptance gate is a required control in the Flutter signup UI + a server-side record written on/after signup.
- **Copyright surface = 3 endpoints in `pipeline/api.py`**: `POST /songs` (`create_song`, model `CreateSongRequest` ~391, ~line 2818), `POST /songs/import` (YouTube, ~2930), `POST /songs/upload-cover` (multipart form upload, `upload_cover_song` ~2980).
- **Paid/generation endpoints** that should require accepted terms: the 3 above + `POST /songs/{id}/approve` (~3598) + the video `POST /runs` / approve path.
- **No legal/consent code or tables** exist (greenfield). `user_profiles` has `id, stripe_customer_id, current_plan, current_period_end, cancel_at_period_end, payment_status`.
- `PlanResponse`/`get_plan_endpoint` (~630, ~1263) is the natural place to surface acceptance status to the app.

## Architecture

### Component A — ToS/Privacy/refund acceptance gate

- **Migration** `supabase/migrations/20260805000001_tos_acceptance.sql`:
  ```sql
  alter table user_profiles
    add column if not exists tos_accepted_version text,
    add column if not exists tos_accepted_at timestamptz;
  ```
- **Version constant** — `CURRENT_LEGAL_VERSION` in `pipeline/api.py` (a date string, e.g. `"2026-08-05"`). Bumping it forces re-acceptance.
- **`pipeline/db.py`** — add `tos_accepted_version: str | None = None` + `tos_accepted_at: str | None = None` to `UserProfile`; add both to the `get_user_profile` `.select(...)` and the constructed dataclass (`.get(...)`). Reuse `upsert_user_profile` to write acceptance.
- **`POST /account/accept-terms`** (authed) — records `tos_accepted_version=CURRENT_LEGAL_VERSION`, `tos_accepted_at=<now ISO>` for the user via `upsert_user_profile`. Returns `{"ok": true, "version": CURRENT_LEGAL_VERSION}`. Idempotent.
- **Enforcement (soft-gate)** — a helper `require_terms_accepted(user)` (a FastAPI dependency layered on `require_user`, or a called guard) that reads the profile and raises `HTTPException(403, detail={"code": "terms_not_accepted", "version": CURRENT_LEGAL_VERSION})` when `tos_accepted_version != CURRENT_LEGAL_VERSION`. **Service tokens bypass** (like credits). Applied ONLY to the paid/generation endpoints (create song/video, approve, import, upload-cover) — reads (`/healthz`, `/runs`, `/billing/plan`) stay ungated so a user is never fully locked out.
- **`GET /billing/plan`** — add `terms_current: bool` (`profile.tos_accepted_version == CURRENT_LEGAL_VERSION`; service branch → `true`).
- **Flutter**:
  - New `lib/screens/legal_screen.dart` — renders placeholder **ToS**, **Privacy**, and **refund policy** sections, each topped with a visible `⚠️ PLACEHOLDER — not legal advice; replace before launch` banner. The refund section should describe the *actual* built behavior (cancel refunds; a failed render keeps the charge; `/resume` is a free retry) so the operator can finalize accurately.
  - `login_screen.dart` (signUp mode) — a **required checkbox** "I agree to the Terms of Service and Privacy Policy" (with tappable links to `legal_screen`) that disables the Sign-Up button until ticked. On `signUp` success, call `POST /account/accept-terms`.
  - `client.dart` — `acceptTerms()` + parse `terms_current` in the plan model; a shared handler that, on a `terms_not_accepted` 403, shows an acceptance dialog (checkbox + links) → `acceptTerms()` → retry. This also covers pre-existing users (who never accepted) on their next paid action.
  - `settings_screen.dart` — links to `legal_screen`.

### Component B — Ownership-attestation gate

- **Request models / form** (`pipeline/api.py`):
  - `CreateSongRequest` + the import request model → add `ownership_attested: bool = False`.
  - `upload_cover_song` (multipart) → add `ownership_attested: bool = Form(False)`.
- **Handler check** — each of the 3 endpoints rejects with `HTTPException(400, detail={"code": "ownership_not_attested"})` unless `ownership_attested is True`. (Check runs alongside `require_terms_accepted`.)
- **Audit record** — when attested, write `ownership_attested: true`, `ownership_attested_version: CURRENT_LEGAL_VERSION`, `ownership_attested_at: <now ISO>` into the run's `api_state.json` (these endpoints already create the run dir + initial state).
- **Flutter** — a required attestation checkbox before the action in `new_song_screen.dart` (and the import / upload-cover flows), worded strongest for import/upload-cover: "I own or have the rights to this material." Gates the submit button; sends `ownership_attested: true`.

## Testing

- **Backend** (`tests/test_legal.py` new, or extend `tests/test_api.py`; mocked DB — never hit real Supabase):
  - `POST /account/accept-terms` writes `tos_accepted_version=CURRENT_LEGAL_VERSION` + `tos_accepted_at`.
  - a paid endpoint → **403 `terms_not_accepted`** when the profile's version is missing/stale; **proceeds** when current; **service token bypasses**.
  - `GET /billing/plan` returns `terms_current` correctly for accepted/unaccepted.
  - each of the 3 song endpoints → **400 `ownership_not_attested`** when the flag is false/absent; **records the attestation** in state when true.
- **Flutter**: `dart analyze lib/screens/legal_screen.dart lib/screens/login_screen.dart lib/screens/new_song_screen.dart lib/screens/settings_screen.dart lib/api/client.dart` → 0 issues. (`flutter analyze` hangs in this env — use `dart analyze <files>`.) If l10n keys are added, run `flutter gen-l10n`.
- **Baseline**: clean-env suite is currently **834 passed, 0 failed** (`env -u <all API-key vars> uv run pytest -q`). No new failures; new tests pass.

## Deferred to the fast-follow pass (decisions recorded)

- **Moderation** = a maintained **deny-list keyword filter** on themes + lyrics (reject pre-generation with a clear message).
- **GDPR `/account/delete` + export** = **anonymize + keep financials**: delete the Supabase auth user + purge generated artifacts (runs/songs/personas/artists) + strip PII, but RETAIN `credit_transactions` amounts (anonymized) for tax/accounting/chargeback records; `/account/export` returns the user's transactions + run metadata.
- DMCA/abuse contact + takedown process (mostly operator/legal content).

## Key invariants respected

- External services **mocked in tests**; the migration is operator-applied (reviewed by reading), so `get_user_profile`'s new `.select(...)` columns require the migration applied **before** the code deploys (same deploy-ordering as the dunning column — note in the plan + operator handoff).
- New Python files start with `from __future__ import annotations`; `pathlib.Path`; absolute imports.
- Placeholder legal copy is unmistakably marked as non-binding; the mechanism is inert legally until real reviewed text is dropped in.
- Service tokens bypass the terms gate (consistent with the credit/service bypass).
