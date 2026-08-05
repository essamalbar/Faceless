# Tier-3 Legal Blockers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Gate paid/generation actions on accepted (versioned) legal terms, and gate the 3 copyright-exposed song endpoints on an ownership attestation — the two Tier-3 hard blockers. No binding legal text is authored (placeholder only).

**Architecture:** `user_profiles` gains `tos_accepted_version`/`tos_accepted_at`; a `CURRENT_LEGAL_VERSION` constant + `POST /account/accept-terms` record acceptance; a `_require_terms_accepted(user)` guard (service-bypass) soft-gates the paid/generation endpoints with a 403 `terms_not_accepted`; `GET /billing/plan` exposes `terms_current`. The 3 song endpoints require `ownership_attested: true` (400 `ownership_not_attested`) and record the attestation in run state. Flutter adds a signup acceptance checkbox + placeholder legal screen + an attestation checkbox.

**Tech Stack:** FastAPI/Pydantic, Supabase (supabase-py), Flutter/Dart.

**Verification env (IMPORTANT):** run pytest CLEAN — sourcing `.env` flips the failing set. Baseline **834 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```
Flutter: `flutter analyze` HANGS here — use `dart analyze <files>`.

---

## File Structure
- Create: `supabase/migrations/20260805000001_tos_acceptance.sql`
- Modify: `pipeline/db.py` (UserProfile + get_user_profile)
- Modify: `pipeline/api.py` (version const, accept-terms, guard, plan field, gate paid endpoints, attestation)
- Create/extend: `tests/test_legal.py` (backend), `tests/test_db.py`
- Create: `lib/screens/legal_screen.dart`
- Modify: `lib/screens/login_screen.dart`, `lib/screens/new_song_screen.dart`, `lib/screens/settings_screen.dart`, `lib/api/client.dart`, `lib/api/models.dart`

---

## Task 1: DB layer — ToS columns

**Files:** Create `supabase/migrations/20260805000001_tos_acceptance.sql`; modify `pipeline/db.py`; test `tests/test_db.py`.

- [ ] **Step 1: Migration**
```sql
alter table user_profiles
  add column if not exists tos_accepted_version text,
  add column if not exists tos_accepted_at timestamptz;
```
(Operator-applied BEFORE deploy — `get_user_profile`'s new SELECT columns 400 against a DB missing them. Same ordering as the dunning column.)

- [ ] **Step 2: Failing test** (append to `tests/test_db.py`)
```python
def test_get_user_profile_reads_tos_fields(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data={
        "id": "u1", "stripe_customer_id": None, "current_plan": "free",
        "current_period_end": None, "cancel_at_period_end": False,
        "payment_status": "active",
        "tos_accepted_version": "2026-08-05", "tos_accepted_at": "2026-08-05T00:00:00Z",
    })
    p = get_user_profile("u1")
    assert p.tos_accepted_version == "2026-08-05"
    assert p.tos_accepted_at == "2026-08-05T00:00:00Z"


def test_get_user_profile_defaults_tos_fields_to_none(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data={
        "id": "u1", "current_plan": "free",
    })
    p = get_user_profile("u1")
    assert p.tos_accepted_version is None and p.tos_accepted_at is None
```

- [ ] **Step 3: Run — verify fail** (`uv run pytest tests/test_db.py -q`).

- [ ] **Step 4: Implement** — in `pipeline/db.py`, add to `UserProfile` (after `payment_status`):
```python
    tos_accepted_version: str | None = None
    tos_accepted_at: str | None = None
```
Add both to `get_user_profile`'s `.select("...")` list (append `,tos_accepted_version,tos_accepted_at`) and to the constructed `UserProfile(...)`:
```python
        tos_accepted_version=d.get("tos_accepted_version"),
        tos_accepted_at=d.get("tos_accepted_at"),
```

- [ ] **Step 5: Run — verify pass**; then full clean-env suite → 836 passed (834 + 2), 0 failed.

- [ ] **Step 6: Commit** — `feat(legal): user_profiles tos_accepted_version/at + reader` (+ trailer).

---

## Task 2: Backend acceptance gate

**Files:** `pipeline/api.py`; test `tests/test_legal.py` (new).

- [ ] **Step 1: Failing tests** (`tests/test_legal.py` — mirror the auth/override + monkeypatch patterns used in `tests/test_api.py`; use its `client`/`auth` fixtures via `from tests.test_api import ...` OR replicate the app TestClient + a user override). The essential assertions:
```python
# 1) POST /account/accept-terms records the CURRENT version via upsert.
#    monkeypatch pipeline.api.upsert_user_profile (or pipeline.db) to capture fields;
#    assert captured["tos_accepted_version"] == api_mod.CURRENT_LEGAL_VERSION and tos_accepted_at set.
# 2) A gated endpoint (use create_song) returns 403 with detail code
#    "terms_not_accepted" when get_user_profile returns a profile whose
#    tos_accepted_version != CURRENT (or None).
# 3) Same endpoint proceeds past the gate when the profile's version == CURRENT.
# 4) Service-token caller bypasses the gate (no 403).
# 5) GET /billing/plan includes terms_current True/False matching the profile.
```
**Concrete template:** copy the mocking shape from `tests/test_api.py::test_get_plan_surfaces_past_due` — it uses the `client_factory(user_id=...)` fixture and `monkeypatch.setattr("pipeline.db.get_user_profile", lambda uid: UserProfile(...))` + `monkeypatch.setattr("pipeline.db.get_balance", lambda uid: N)`. For `accept_terms`, monkeypatch `pipeline.db.upsert_user_profile` to capture kwargs. For the service-bypass case, build the client with the service token (see how `test_billing_get_endpoints_bypass_db_for_service_tokens` does it). Build a `UserProfile(...)` with `tos_accepted_version=api_mod.CURRENT_LEGAL_VERSION` (accepted) or `None`/stale (unaccepted).

- [ ] **Step 2: Run — verify fail.**

- [ ] **Step 3: Implement** in `pipeline/api.py`:

Near the top constants:
```python
CURRENT_LEGAL_VERSION = "2026-08-05"  # bump to force re-acceptance of ToS/Privacy
```
Helpers + endpoint (place near the billing/account endpoints):
```python
def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _require_terms_accepted(user: User) -> None:
    """Soft-gate for paid/generation actions. Service tokens bypass. Raises a
    403 with a machine-readable code the app catches to prompt acceptance."""
    if user.role == "service":
        return
    from pipeline.db import get_user_profile
    profile = get_user_profile(user.id)
    if profile is None or profile.tos_accepted_version != CURRENT_LEGAL_VERSION:
        raise HTTPException(status_code=403,
                            detail={"code": "terms_not_accepted",
                                    "version": CURRENT_LEGAL_VERSION})


class AcceptTermsResponse(BaseModel):
    ok: bool
    version: str


@app.post("/account/accept-terms", response_model=AcceptTermsResponse)
def accept_terms(user: User = Depends(require_user)):
    if user.role != "service":
        from pipeline.db import upsert_user_profile
        upsert_user_profile(user.id,
                            tos_accepted_version=CURRENT_LEGAL_VERSION,
                            tos_accepted_at=_now_iso())
    return AcceptTermsResponse(ok=True, version=CURRENT_LEGAL_VERSION)
```
Add `terms_current: bool = True` to `PlanResponse`; in `get_plan_endpoint`, service branch → `terms_current=True`; profile branch →
```python
        terms_current=(bool(profile) and profile.tos_accepted_version == CURRENT_LEGAL_VERSION),
```
Apply the guard at the top of each paid/generation endpoint (after the `user` is resolved): `create_song` (~2818), `import_song` (~2931), `upload_cover_song` (~2981), `approve_song` (~3598), and the VIDEO create + approve endpoints (`POST /runs`, `POST /runs/{id}/approve` — locate via `git grep -n '@app.post("/runs"' pipeline/api.py`):
```python
    _require_terms_accepted(user)
```

- [ ] **Step 4: Run — verify pass** (`tests/test_legal.py` + `tests/test_api.py -k "plan or cancel or approve"`); existing HTTP codes unchanged; full clean-env suite no new failures.

- [ ] **Step 5: Commit** — `feat(legal): versioned ToS acceptance gate on paid endpoints + /account/accept-terms` (+ trailer).

---

## Task 3: Backend ownership-attestation gate

**Files:** `pipeline/api.py`; test `tests/test_legal.py`.

- [ ] **Step 1: Failing tests** — for each of `POST /songs`, `POST /songs/import`, `POST /songs/upload-cover`: 400 with detail code `ownership_not_attested` when the flag is false/absent (with terms accepted, so the terms gate passes first); and when true, the run's `api_state.json` contains `ownership_attested: true`. (Mock the LLM/generation + DB so the create proceeds to the state write.)

- [ ] **Step 2: Run — verify fail.**

- [ ] **Step 3: Implement:**
- `CreateSongRequest` (391) + `CreateSongImportRequest` (449): add `ownership_attested: bool = False`.
- `upload_cover_song` (2981) signature: add `ownership_attested: bool = Form(False)`.
- At the top of each of the 3 handlers (right after `_require_terms_accepted(user)`):
```python
    if not <flag>:   # req.ownership_attested  (or the form param for upload-cover)
        raise HTTPException(400, detail={"code": "ownership_not_attested"})
```
- Record it in the create-time state write (the `_write_state(run_dir, ...)` that first creates the song run — `create_song` ~2865; the analogous writes in `import_song` + `upload_cover_song`): add
```python
        ownership_attested=True,
        ownership_attested_version=CURRENT_LEGAL_VERSION,
        ownership_attested_at=_now_iso(),
```

- [ ] **Step 4: Run — verify pass**; full clean-env suite no new failures.

- [ ] **Step 5: Commit** — `feat(legal): ownership attestation required on song create/import/upload-cover` (+ trailer).

---

## Task 4: Flutter — legal screen + signup gate + client

**Files:** Create `lib/screens/legal_screen.dart`; modify `lib/api/client.dart`, `lib/api/models.dart`, `lib/screens/login_screen.dart`, `lib/screens/settings_screen.dart`.

- [ ] **Step 1: Create `lib/screens/legal_screen.dart`** — a scrollable screen with three sections (Terms of Service, Privacy Policy, Refund Policy), each preceded by a highly-visible placeholder banner. Use the app's existing theme (`FacelessTheme`). Structure:
```dart
// A single StatelessWidget `LegalScreen` taking an optional initial section.
// Top of page: a Container banner (FacelessTheme.danger tint) with text:
//   "⚠️ PLACEHOLDER — not legal advice. Replace with lawyer-reviewed text
//    before launch."
// Then three headed sections with a few paragraphs of placeholder copy each.
// The Refund section MUST describe the real built behavior:
//   "Cancel a run for a refund of unused credits; a failed render keeps the
//    charge and can be resumed for free; completed renders are non-refundable."
```
(Reachable via `Navigator.push` from login + settings. Keep it self-contained; no backend call.)

- [ ] **Step 2: `lib/api/client.dart`** — add:
```dart
Future<void> acceptTerms() async { /* POST /account/accept-terms, bearer auth */ }
```
and in the shared response handler, detect HTTP 403 whose JSON `detail.code == "terms_not_accepted"` and throw a typed `TermsNotAcceptedException` the UI can catch.

- [ ] **Step 3: `lib/api/models.dart`** — add `final bool termsCurrent;` to `PlanInfo` (default `true`), parse `termsCurrent: (j['terms_current'] as bool?) ?? true` in `fromJson`.

- [ ] **Step 4: `lib/screens/login_screen.dart`** — in signUp mode: a required `Checkbox` + label with tappable "Terms of Service" / "Privacy Policy" links (→ `LegalScreen`). The Sign-Up button `onPressed` is null (disabled) until the box is ticked. After a successful `supabase.auth.signUp(...)` that yields a session, call `api.acceptTerms()` (best-effort; if it fails, the paid-action gate will re-prompt).

- [ ] **Step 5: `lib/screens/settings_screen.dart`** — add "Terms & Privacy" list tiles → `LegalScreen`.

- [ ] **Step 6: Analyze** — `dart analyze lib/screens/legal_screen.dart lib/screens/login_screen.dart lib/screens/settings_screen.dart lib/api/client.dart lib/api/models.dart` → 0 issues. (If l10n keys added, `flutter gen-l10n` first.)

- [ ] **Step 7: Commit** — `feat(legal): Flutter signup acceptance gate + placeholder legal screen` (+ trailer).

---

## Task 5: Flutter — ownership-attestation checkbox

**Files:** `lib/screens/new_song_screen.dart` (+ the import / upload-cover entry points if separate).

- [ ] **Step 1: Implement** — a required attestation `Checkbox` shown before the Create / Import / Upload-cover action, disabling the submit button until ticked. Wording strongest for import/upload-cover: "I own or have the rights to this material." Send `ownership_attested: true` in the request (JSON body for create/import; a form field for upload-cover). Wire the client methods to pass the flag.

- [ ] **Step 2: Analyze** — `dart analyze lib/screens/new_song_screen.dart lib/api/client.dart` → 0 issues.

- [ ] **Step 3: Commit** — `feat(legal): ownership-attestation checkbox on song create/import/upload` (+ trailer).

---

## Task 6: Full-suite verification + operator handoff

**Files:** none (verification) + append to `docs/GO-LIVE-READINESS.md`.

- [ ] **Step 1: Full clean-env suite** (the `env -u ...` invocation) → report the exact count; 0 failed.
- [ ] **Step 2: dart analyze** all changed Dart files → 0 issues.
- [ ] **Step 3: Operator handoff** — append a Tier-3 note to `docs/GO-LIVE-READINESS.md`: apply migration `20260805000001_tos_acceptance.sql` BEFORE deploy; replace the placeholder legal copy in `legal_screen.dart` with lawyer-reviewed ToS/Privacy/refund text; bump `CURRENT_LEGAL_VERSION` when terms change (forces re-acceptance). Note the deferred fast-follow (moderation deny-list, GDPR anonymize-keep-financials).
- [ ] **Step 4: Commit** — `docs: tier-3 legal blockers operator handoff` (+ trailer).
