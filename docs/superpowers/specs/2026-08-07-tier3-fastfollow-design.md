# Tier-3 Compliance Fast-Follow — Design

**Date:** 2026-08-07
**Status:** approved (brainstorm; decisions locked) — spec for review → plan
**Scope:** The deferred Tier-3 items (`docs/GO-LIVE-READINESS.md` #11 moderation, #12 DMCA, #13 GDPR): (M) deny-list content moderation on user inputs, (G) GDPR `/account/delete` + `/account/export` (anonymize + keep financials), (D) DMCA/abuse contact. Decisions locked in the Tier-3 brainstorm + confirmed now: **inputs-only** moderation; **delete = purge artifacts + scrub profile PII + admin-delete auth user, retain `credit_transactions`**.

## Context (verified 2026-08-07)
- No moderation exists. User free-text enters via `CreateSongRequest.theme/custom_lyrics/style_hint`, `CreateSongImportRequest.instruction`, video `CreateRunRequest.theme` / `CreateFreeformRunRequest.theme`, and `regenerate_song_lyrics` (custom text). All create endpoints already run `_require_terms_accepted` + `_require_email_confirmed`.
- Per-resource deletes exist (`delete_run` 2566, `delete_song` 4308, `delete_persona` 4473, `delete_artist` 4613) but no account-level delete/export. supabase-py service client exposes `auth.admin.delete_user(id)`. `user_profiles` PII = `stripe_customer_id` (+ plan/period fields); `credit_transactions` is the financial ledger to retain.
- `legal_screen.dart` has placeholder legal sections; `settings_screen.dart` has a `_DangerButton` (sign-out) pattern + `_SettingTile`.

## Architecture

### M — Content moderation (deny-list, inputs-only)
- **`pipeline/moderation.py`** (new, stdlib only):
  - `DENYLIST: frozenset[str]` — a CONSERVATIVE seed of unambiguous prohibited-category terms (primarily sexual-content-involving-minors, which is zero-tolerance). NOT an exhaustive slur/abuse list in-repo. Extendable at runtime: if `FACELESS_MODERATION_DENYLIST` points to a file, load newline-separated terms and union them (operator maintains the real list privately).
  - `find_violations(text: str) -> list[str]` — case-insensitive, **word-boundary** match (`re.search(r"\b" + re.escape(term) + r"\b", text, re.I)`) so `grape`≠`rape`, `assassin`≠`ass`. Returns matched terms (for logging, not echoed to the user).
  - `assert_clean(*texts: str | None) -> None` — raises `ModerationError` (a plain exception with the matched terms) if any provided text trips the list; skips None/empty.
- **`pipeline/api.py`**: `_screen_content(*texts)` wrapper → on `ModerationError`, log at WARNING with a `[moderation]` token (for the Tier-2 alert metric) + the run/user (NOT the matched terms in the user response) and raise `HTTPException(400, {"code": "content_rejected"})`. Call it in `create_song` (theme, custom_lyrics, style_hint), `import_song` (instruction), `create_run`/`create_run_from_script`/`create_freeform_run` (theme + any premise/controls free-text), and `regenerate_song_lyrics` — placed right after the existing terms/email/llm gates. Service tokens are NOT exempt (moderation applies to content regardless of caller). Inputs only — generated lyrics are not re-screened (decided).

### G — GDPR export + delete (anonymize + keep financials)
- **`pipeline/db.py`**:
  - `delete_auth_user(user_id: str) -> None` — `_client().auth.admin.delete_user(user_id)` (service client).
  - `anonymize_user_profile(user_id: str) -> None` — upsert the profile with PII nulled: `stripe_customer_id=None`, `current_plan="deleted"`, `tos_accepted_version=None`, `payment_status="active"` (keep the row so retained ledger rows still reference a valid `user_id`).
  - (Ledger `credit_transactions` is intentionally left untouched.)
- **`pipeline/api.py`**:
  - `GET /account/export` (authed) → JSON: `{profile, transactions: list_transactions(user.id, limit=big), runs: [run metadata for the user's dirs]}`. Read-only. Service token → 400 (nothing to export).
  - `POST /account/delete` (authed) — body `{confirm: "DELETE"}` (typed confirm; 400 if not exactly "DELETE"). Steps, best-effort + logged: (1) purge the user's on-disk artifacts (`shutil.rmtree(_user_runs_root(user))`), (2) `anonymize_user_profile(user.id)`, (3) `delete_auth_user(user.id)`. Return `{ok: true}`. Service token → 403 (no self-serve delete for the admin/service identity). Idempotent-ish (rmtree missing_ok; admin delete of an already-gone user is tolerated/logged).
- **Flutter `settings_screen.dart`**: a "Danger zone" with **Export my data** (calls `/account/export`, saves/downloads JSON) and **Delete account** (a dialog requiring the user to type `DELETE` → `POST /account/delete` → sign out + return to landing). `client.dart`: `exportAccount()` + `deleteAccount()`.

### D — DMCA/abuse contact
- **`legal_screen.dart`**: add a fourth section "Copyright / DMCA & Abuse" with placeholder copy + a placeholder contact (`abuse@<your-domain>` / a takedown-process outline), same non-binding-placeholder banner treatment. Operator fills the real contact/process.

## Testing
- **`tests/test_moderation.py`** (new): `find_violations` matches a seeded term on a word boundary, does NOT match a substring inside an innocent word, is case-insensitive, and returns [] for clean text; the file-override unions extra terms; `assert_clean` raises `ModerationError` on a hit and passes clean text.
- **`tests/test_api.py`/`test_legal.py`**: a create endpoint 400s `content_rejected` when a field trips the deny-list (monkeypatch the deny-list to a known term), passes clean; `/account/export` returns the user's txns+profile (mocked db + a tmp run dir); `/account/delete` with `confirm="DELETE"` calls `delete_auth_user` + `anonymize_user_profile` + rmtrees the user root (all mocked/tmp) and does NOT touch `credit_transactions`; wrong/absent confirm → 400; service token → 403.
- **`tests/test_db.py`**: `anonymize_user_profile` upserts nulled PII; `delete_auth_user` calls the admin path (mocked client).
- **Flutter**: `dart analyze` the changed files → 0 (use `dart analyze`).
- **Baseline**: clean-env suite **901 passed, 0 failed**; no new failures.

## Deploy / operator
- No migration (uses existing tables). Operator: extend the moderation deny-list via `FACELESS_MODERATION_DENYLIST`; fill the real DMCA/abuse contact in `legal_screen.dart`; verify `auth.admin.delete_user` works with the service role key in prod.

## Key invariants
- Moderation applies to content regardless of caller (NOT service-bypassed); GDPR delete/export are per-user (service token can't self-delete). `credit_transactions` retained on delete (tax/chargeback). Matched deny-list terms are logged, never echoed to the user. External services mocked in tests. New Python: `from __future__ import annotations`.
