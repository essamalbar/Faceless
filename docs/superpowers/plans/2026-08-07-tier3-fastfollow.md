# Tier-3 Compliance Fast-Follow Implementation Plan

> SUB-SKILL: subagent-driven (synchronous). Design: `docs/superpowers/specs/2026-08-07-tier3-fastfollow-design.md`.

**Goal:** Deny-list content moderation on user inputs; GDPR `/account/export` + `/account/delete` (anonymize + keep financials); a DMCA/abuse-contact section.

**Verification env:** clean-env pytest. Baseline **901 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```
Flutter: `dart analyze` (never `flutter analyze`).

---

## Task M — Content moderation (deny-list, inputs-only) — TDD
**Files:** new `pipeline/moderation.py`, `pipeline/api.py`; tests new `tests/test_moderation.py`, `tests/test_api.py`.
- [ ] Tests: `find_violations` word-boundary + case-insensitive matching (matches a seeded term standalone; does NOT match it inside an innocent word; [] for clean); `FACELESS_MODERATION_DENYLIST` file unions extra terms; `assert_clean` raises `ModerationError` on a hit. A create endpoint (e.g. `POST /songs`) → `400 {"code":"content_rejected"}` when a field trips a monkeypatched deny-list; passes clean.
- [ ] Implement `pipeline/moderation.py` per the spec (conservative seed frozenset; file-override union; `find_violations`; `assert_clean`; `ModerationError`). In `api.py`, `_screen_content(*texts)` (log a `[moderation]` WARNING with run/user on reject — never echo matched terms; raise `HTTPException(400, {"code":"content_rejected"})`); call it in `create_song` (theme, custom_lyrics, style_hint), `import_song` (instruction), `create_run`/`create_run_from_script`/`create_freeform_run` (theme + free-text), `regenerate_song_lyrics` — after the existing gates. NOT service-bypassed.
- [ ] Clean-env suite green (report count). Commit: `feat(moderation): deny-list screening of user content inputs`.

## Task G — GDPR export + delete (anonymize, keep financials) — TDD
**Files:** `pipeline/db.py`, `pipeline/api.py`; tests `tests/test_db.py`, `tests/test_api.py` (or `test_legal.py`).
- [ ] Tests: `db.anonymize_user_profile` upserts nulled PII (`stripe_customer_id=None`, `current_plan="deleted"`, `tos_accepted_version=None`); `db.delete_auth_user` calls `_client().auth.admin.delete_user(id)` (mock client). `GET /account/export` returns `{profile, transactions, runs}` for the user (mock db + a tmp run dir). `POST /account/delete` with `{"confirm":"DELETE"}` → calls `delete_auth_user` + `anonymize_user_profile` + rmtrees the user's runs root (tmp), and does NOT call any `credit_transactions` delete; wrong/absent confirm → 400; service token → 403.
- [ ] Implement: db helpers per spec; `GET /account/export` (authed, read-only; service → 400); `POST /account/delete` (authed; body `{confirm}`; typed-"DELETE" guard; best-effort purge→anonymize→admin-delete, each logged; service → 403; retain ledger). Reuse `_user_runs_root(user)`, `list_transactions`, `get_user_profile`.
- [ ] Clean-env suite green (report count). Commit: `feat(gdpr): /account/export + /account/delete (anonymize, keep financials)`.

## Task G2 — Flutter danger zone (export + delete)
**Files:** `lib/api/client.dart`, `lib/screens/settings_screen.dart`.
- [ ] `client.dart`: `exportAccount()` (GET /account/export → returns/saves the JSON) + `deleteAccount()` (POST /account/delete `{confirm:"DELETE"}`). `settings_screen.dart`: a "Danger zone" with **Export my data** (fetch + save/share JSON) and **Delete account** (dialog requiring the user to type `DELETE` → `deleteAccount()` → `Supabase.instance.client.auth.signOut()` → back to landing).
- [ ] `dart analyze lib/api/client.dart lib/screens/settings_screen.dart` → 0 issues. Commit: `feat(gdpr): Flutter export + delete-account danger zone`.

## Task D — DMCA/abuse contact
**Files:** `lib/screens/legal_screen.dart`.
- [ ] Add a "Copyright / DMCA & Abuse" section (placeholder takedown process + placeholder `abuse@<domain>` contact, same non-binding banner treatment). `dart analyze` → 0.
- [ ] Commit: `feat(legal): DMCA/abuse-contact section (placeholder)`.

## Task V — verify + handoff
- [ ] Full clean-env suite → 0 failed (report count); `dart analyze` clean. Append a Tier-3-fast-follow note to `docs/GO-LIVE-READINESS.md` (moderation deny-list seeded + `FACELESS_MODERATION_DENYLIST` override; GDPR export/delete shipped — operator verifies `auth.admin.delete_user` works with the service key; DMCA contact placeholder to fill). Commit.
