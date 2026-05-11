# B2 — Supabase Auth + Per-User Run Isolation Design

**Status:** approved 2026-05-10
**Owner:** Essam
**Phase:** 2 (cloud + auth) — first of B2-B7
**Builds on:** B1 (Cloud Run deploy live at `https://faceless-api-uplzdtffeq-uc.a.run.app`)

## Goal

Replace the single shared bearer token (`FACELESS_API_TOKEN`) with per-user
Supabase Auth, so the product can have more than one customer without leaking
runs across accounts. This is the foundation B3 (DB schema + credits), B4
(Stripe), B5 (marketing site), B6 (Flutter Web) all build on.

## Decisions (locked)

| Question | Choice | Reason |
|---|---|---|
| Auth method | Email + password only | Lowest friction for B2 alone. OAuth (Google/Apple) deferred to B5 when the marketing site lands. |
| Email confirmation | **ON** | Stops bots from day one; the user already toggled it in Supabase. |
| Per-user file isolation | **Now (in B2)** | Same complexity now vs migrating data later. Backend stops being multi-tenant unsafe. |
| JWT verification | **HS256 with shared secret** | Supabase HS256 is stable, well-documented, and PyJWT verifies it in two lines. RS256/JWKS can replace this transparently in the future without breaking the wire format. |
| Service-account fallback | **Keep `FACELESS_API_TOKEN`** | The CLI (`run.py`) and any cron job we add later need a bearer token that isn't tied to a human user. Map it to a synthetic `user_id="admin"` so it shares the per-user file layout. |

## Architecture

```
                        ┌──────────────────────┐
                        │   Flutter app        │
                        │   supabase_flutter   │
                        └──────┬───────────────┘
                               │ JWT in Authorization header
                               ▼
              ┌────────────────────────────────────┐
              │ Cloud Run Service (faceless-api)   │
              │                                    │
              │   require_user dependency:         │
              │     1. Bearer == FACELESS_API_TOKEN│
              │        → User(id="admin", role="service")
              │     2. Otherwise → PyJWT.decode    │
              │        with SUPABASE_JWT_SECRET    │
              │        → User(id=sub, email=..., role="user")
              │     3. Else → 401                  │
              │                                    │
              │   _user_root(user) =               │
              │     /mnt/runs/{user.id}/           │
              └──────┬─────────────────────────────┘
                     │ writes / reads
                     ▼
              ┌──────────────────────────────────┐
              │ GCS bucket via gcsfuse mount     │
              │ /mnt/runs/<user_id>/<run_id>/    │
              └──────────────────────────────────┘
```

## What changes for users

- **First-launch experience:** users land on a Login screen instead of the Settings screen.
- **No more manual API token:** the bearer token field disappears from Settings; the only thing they may want to configure is the API URL (which is also auto-set when launched via `run-app.sh`).
- **Sign-out button** appears in Settings.
- **Run history** is per-account — switching accounts shows a different list of runs.

## What stays the same

- The CLI (`uv run python run.py …`) still works — it doesn't talk to the API; it writes directly to `out/`. It is a separate code path that doesn't go through `require_user`.
- All existing API endpoints keep their shape — they just authenticate differently and scope file paths by `user.id`.
- `FACELESS_API_TOKEN` keeps working for `curl` / dev / cron / future automation.

## Out of scope for B2

- Postgres `users` / `runs` / `credit_transactions` tables → **B3**
- Per-user credit deduction on run start → **B3**
- Stripe billing → **B4**
- Marketing site (sign-up landing page) → **B5**
- Flutter Web build → **B6**
- Apple/Google OAuth → **B5**
- Password reset flow → can come for free with `supabase_flutter` later; not building UI for it in B2

## Backend behavior changes (file-by-file)

### `pipeline/auth.py` (new)

```python
@dataclass(frozen=True)
class User:
    id: str           # "admin" for service-token, else Supabase auth.users.id (UUID)
    email: str | None # None for service-token
    role: str         # "service" | "user"

def verify_supabase_jwt(token: str, secret: str) -> User:
    """HS256 verify; raise ValueError on bad signature, expired, or wrong issuer."""

async def require_user(authorization: str = Header(None)) -> User:
    """FastAPI dep. Tries service token first, then Supabase JWT. 401 on failure."""
```

### `pipeline/api.py` (modify)

- Replace every `Depends(require_token)` with `Depends(require_user)`.
- Add `user: User = Depends(require_user)` parameter to each endpoint that
  reads/writes runs.
- Replace `_out_root()` with `_user_runs_root(user)` returning
  `Path(FACELESS_OUT_ROOT) / user.id`.
- `list_runs` returns only that user's runs.

### Orchestrator (`run.py` and `pipeline/orchestrator.py` if it exists)

- Accept `user_id` argument (default `"admin"` for backwards-compat with CLI).
- Output goes to `out_root / user_id / run_timestamp/`.

## Flutter behavior changes

### `lib/main.dart`
- Initialize `Supabase.initialize(url, anonKey)` with `--dart-define` values.
- Wrap the app in a `StreamBuilder` on `Supabase.instance.client.auth.onAuthStateChange`.
  Show `LoginScreen` if no session; the existing `_Bootstrap` if signed-in.

### `lib/screens/login_screen.dart` (new)
- Email + password fields, "Sign up" and "Sign in" buttons.
- Sign-up shows "Check your email to confirm" toast on success.
- Sign-in either lands them on the home screen or surfaces the Supabase error.

### `lib/api/client.dart`
- Replace `final token = await _settings.token();` with
  `final session = Supabase.instance.client.auth.currentSession; final token = session?.accessToken;`.
- Throws `FacelessApiException('Not signed in')` if no session.

### `lib/api/settings.dart` and `lib/screens/settings_screen.dart`
- Drop the bearer-token field from settings. The only persisted setting becomes
  the API base URL.
- Add a "Sign out" button calling `Supabase.instance.client.auth.signOut()`.

## Cloud Run config

- Add env var `SUPABASE_URL` (public) to the Service.
- Add secret `supabase-jwt-secret` (already in Secret Manager) → env
  `SUPABASE_JWT_SECRET` on the Service.
- The Job doesn't need either: it only does file I/O.

## Wire format for the JWT

A Supabase HS256 access token is a standard JWT with the following claims we
care about:

```json
{
  "iss":   "https://<project>.supabase.co/auth/v1",
  "sub":   "<UUID — this is auth.users.id>",
  "email": "user@example.com",
  "role":  "authenticated",
  "aud":   "authenticated",
  "exp":   <unix>
}
```

We verify `exp` (built-in to PyJWT), `aud="authenticated"`, and the HS256
signature against `SUPABASE_JWT_SECRET`. We do NOT verify `iss` because that
buys nothing extra given the secret is project-scoped.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| User signs up, can't log in (email link broken) | Document SMTP setup; for now, use Supabase's default SMTP (rate-limited but free) |
| Existing local `out/` runs don't match new layout | Migration: `mv out/<timestamp> out/admin/<timestamp>` one-shot script. Most existing runs are throwaway. |
| Flutter app crashes if `--dart-define` values not passed | Default to empty strings; show clear "Supabase not configured" error in LoginScreen |
| Backend crashes if `SUPABASE_JWT_SECRET` not set on Cloud Run | Startup check — log warning + reject all non-service-token requests with 503 |

## Migration plan for existing local runs

```bash
# One-time, on dev machine, after upgrading
mkdir -p out/admin
find out/ -maxdepth 1 -type d -name '20*' -exec mv {} out/admin/ \;
```

## Acceptance criteria

1. A new user can sign up via the Flutter app, confirm their email, sign in,
   and see an empty run list.
2. That user starts a run; it appears in their list, and **does not** appear
   in another user's list.
3. The CLI (`uv run python run.py --shorts ...`) still produces a working video.
4. `curl -H "Authorization: Bearer $FACELESS_API_TOKEN" $URL/runs` still works
   and returns admin-scoped runs.
5. `curl $URL/runs` (no auth) returns 401.
6. `curl -H "Authorization: Bearer wrong-token" $URL/runs` returns 401.
