# Supabase Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single shared `FACELESS_API_TOKEN` with per-user Supabase Auth (email + password), and isolate every user's runs into their own directory.

**Architecture:** Flutter uses `supabase_flutter` to sign in and obtain a JWT. The backend's existing `require_token` dependency is replaced with `require_user`, which first tries the service token (`FACELESS_API_TOKEN` → synthetic user `admin`) and falls back to verifying the bearer as a Supabase HS256 JWT against `SUPABASE_JWT_SECRET`. Every endpoint that touches files now scopes paths under `/mnt/runs/{user_id}/{run_id}/`. Spec: `docs/superpowers/specs/2026-05-10-supabase-auth-design.md`.

**Tech Stack:** PyJWT (HS256 verification), `supabase_flutter` package, FastAPI dependency injection, the existing Cloud Run + GCS-fuse stack from B1.

**Important context for implementers:**
- All Python files start with `from __future__ import annotations`. Use `pathlib.Path`, never `os.path`.
- Run `uv run pytest tests/test_<file>.py -v` to test individual files. Run `uv run pytest -q` for the full suite.
- External services (Supabase, Anthropic, Kie, Edge TTS, FFmpeg) are mocked in tests; never hit them for real.
- Frequent commits — every task ends with a commit. Use Conventional Commits style (`feat:`, `fix:`, `test:`).
- The current Cloud Run service is `faceless-api`, region `us-central1`, project `project-affccfbf-a37c-4648-a0b`. Bucket is `${PROJECT_ID}-faceless-runs`.
- Existing endpoints live in `pipeline/api.py`. The `require_token` dependency is currently at the top of that file (`def require_token(authorization: str = Header(None))`).

---

## File Structure

| File | Purpose | Status |
|---|---|---|
| `pipeline/auth.py` | `User` dataclass + `verify_supabase_jwt` + `require_user` FastAPI dependency | **NEW** |
| `tests/test_auth.py` | Unit tests for token verification + dependency behavior | **NEW** |
| `pipeline/api.py` | Replace every `require_token` with `require_user`; add `_user_runs_root(user)` helper; thread `user` through all endpoints | MODIFY |
| `tests/test_api.py` | Update existing tests to send valid JWTs; add cross-user isolation tests | MODIFY |
| `run.py` | Accept `--user-id` arg, default `"admin"`, write to per-user directory | MODIFY |
| `pyproject.toml` | Add `pyjwt>=2.8` | MODIFY |
| `lib/main.dart` | Initialize Supabase, route guard on `auth.onAuthStateChange` | MODIFY |
| `lib/screens/login_screen.dart` | Email + password sign-up / sign-in | **NEW** |
| `lib/api/client.dart` | Pull access token from `Supabase.instance.client.auth.currentSession` | MODIFY |
| `lib/api/settings.dart` | Drop manual token field; keep base URL only | MODIFY |
| `lib/screens/settings_screen.dart` | Remove token UI; add Sign Out button | MODIFY |
| `pubspec.yaml` | Add `supabase_flutter: ^2.5.0` | MODIFY |
| `deploy/cloud-run-service.yaml` | Mount `SUPABASE_URL` env + `SUPABASE_JWT_SECRET` from Secret Manager | MODIFY |
| `scripts/setup-cloud-run.sh` | Add `supabase-jwt-secret` to the secrets-write list | MODIFY |
| `scripts/run-app.sh` | Pass `--dart-define=SUPABASE_URL`/`SUPABASE_ANON_KEY` to `flutter run` | MODIFY |
| `scripts/migrate-runs-to-admin.sh` | One-shot mover for existing local `out/<timestamp>/` → `out/admin/<timestamp>/` | **NEW** |

---

## Task 1: Add PyJWT and `verify_supabase_jwt`

**Files:**
- Modify: `pyproject.toml`
- Create: `pipeline/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1.1: Add PyJWT to dependencies**

Edit `pyproject.toml`. In the `dependencies = [...]` array, add the line below right after `"pyyaml>=6.0",`:

```toml
    "pyjwt>=2.8",
```

Then run:

```bash
uv lock
uv sync
```

- [ ] **Step 1.2: Write the failing test for `verify_supabase_jwt`**

Create `tests/test_auth.py`:

```python
"""Tests for Supabase JWT verification."""
from __future__ import annotations

import time

import jwt
import pytest

from pipeline.auth import User, verify_supabase_jwt

SECRET = "test-secret-not-the-real-one"
GOOD_PAYLOAD = {
    "sub": "11111111-2222-3333-4444-555555555555",
    "email": "alice@example.com",
    "role": "authenticated",
    "aud": "authenticated",
    "exp": int(time.time()) + 3600,
}


def _encode(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_returns_user_for_valid_token():
    token = _encode(GOOD_PAYLOAD)
    user = verify_supabase_jwt(token, SECRET)
    assert user == User(
        id="11111111-2222-3333-4444-555555555555",
        email="alice@example.com",
        role="user",
    )


def test_verify_rejects_expired_token():
    payload = {**GOOD_PAYLOAD, "exp": int(time.time()) - 60}
    token = _encode(payload)
    with pytest.raises(ValueError, match="expired"):
        verify_supabase_jwt(token, SECRET)


def test_verify_rejects_bad_signature():
    token = _encode(GOOD_PAYLOAD, secret="other-secret")
    with pytest.raises(ValueError, match="signature"):
        verify_supabase_jwt(token, SECRET)


def test_verify_rejects_wrong_audience():
    payload = {**GOOD_PAYLOAD, "aud": "service_role"}
    token = _encode(payload)
    with pytest.raises(ValueError, match="audience"):
        verify_supabase_jwt(token, SECRET)


def test_verify_rejects_token_without_sub():
    payload = {k: v for k, v in GOOD_PAYLOAD.items() if k != "sub"}
    token = _encode(payload)
    with pytest.raises(ValueError, match="sub"):
        verify_supabase_jwt(token, SECRET)
```

- [ ] **Step 1.3: Run the test, verify it fails**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: ImportError / ModuleNotFoundError on `pipeline.auth`.

- [ ] **Step 1.4: Implement `pipeline/auth.py`**

Create `pipeline/auth.py`:

```python
"""Auth: Supabase JWT verification + FastAPI request dependency.

Two paths:
  1. Service token — the bearer matches FACELESS_API_TOKEN. Returns a synthetic
     "admin" user. Used by the CLI, cron jobs, and curl-based smoke tests.
  2. Supabase JWT — HS256 verified against SUPABASE_JWT_SECRET. Returns a user
     whose id is the Supabase auth.users.id (UUID).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class User:
    id: str            # "admin" for service-token, otherwise Supabase UUID
    email: str | None  # None for service-token
    role: str          # "service" | "user"


def verify_supabase_jwt(token: str, secret: str) -> User:
    """Verify a Supabase HS256 access token and return the User.

    Raises ValueError with a short reason on any failure.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("token expired") from None
    except jwt.InvalidAudienceError:
        raise ValueError("wrong audience") from None
    except jwt.InvalidSignatureError:
        raise ValueError("bad signature") from None
    except jwt.InvalidTokenError as e:
        raise ValueError(f"invalid token: {e}") from None

    sub = payload.get("sub")
    if not sub:
        raise ValueError("token missing sub claim")
    return User(
        id=str(sub),
        email=payload.get("email"),
        role="user",
    )
```

- [ ] **Step 1.5: Run the tests, verify they pass**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: 5 passed.

- [ ] **Step 1.6: Commit**

```bash
git add pyproject.toml uv.lock pipeline/auth.py tests/test_auth.py
git commit -m "feat(auth): Supabase JWT verification (HS256)"
```

---

## Task 2: `require_user` dependency (service token + Supabase JWT)

**Files:**
- Modify: `pipeline/auth.py`
- Modify: `tests/test_auth.py`

- [ ] **Step 2.1: Add failing tests for `require_user`**

Append to `tests/test_auth.py`:

```python
import pytest_asyncio  # noqa: F401  (only needed if you use asyncio later)
from pipeline.auth import require_user


def _setenv(monkeypatch, **kw):
    for k, v in kw.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_require_user_accepts_service_token(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    user = require_user(authorization="Bearer svc-secret")
    assert user == User(id="admin", email=None, role="service")


def test_require_user_accepts_supabase_jwt(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    token = _encode(GOOD_PAYLOAD)
    user = require_user(authorization=f"Bearer {token}")
    assert user.id == GOOD_PAYLOAD["sub"]
    assert user.email == "alice@example.com"
    assert user.role == "user"


def test_require_user_rejects_no_header(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_user(authorization=None)
    assert exc.value.status_code == 401


def test_require_user_rejects_garbage_token(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_user(authorization="Bearer not-a-real-token")
    assert exc.value.status_code == 401


def test_require_user_503_when_neither_secret_set(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN=None, SUPABASE_JWT_SECRET=None)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_user(authorization="Bearer anything")
    assert exc.value.status_code == 503
```

- [ ] **Step 2.2: Run the tests, verify they fail**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: 5 fail (no `require_user` exported).

- [ ] **Step 2.3: Add `require_user` to `pipeline/auth.py`**

Append to `pipeline/auth.py`:

```python
def require_user(authorization: str | None = Header(None)) -> User:
    """FastAPI dependency. Tries service token first, then Supabase JWT.

    Returns a User on success; raises HTTPException(401) on auth failure or
    HTTPException(503) if the server has neither auth mechanism configured.
    """
    service_token = os.environ.get("FACELESS_API_TOKEN")
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")

    if not service_token and not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured (FACELESS_API_TOKEN or "
                   "SUPABASE_JWT_SECRET must be set).",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if service_token and token == service_token:
        return User(id="admin", email=None, role="service")

    if jwt_secret:
        try:
            return verify_supabase_jwt(token, jwt_secret)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            ) from None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token.",
    )
```

- [ ] **Step 2.4: Run the tests, verify they pass**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: 10 passed.

- [ ] **Step 2.5: Commit**

```bash
git add pipeline/auth.py tests/test_auth.py
git commit -m "feat(auth): require_user dep — service token + Supabase JWT"
```

---

## Task 3: Per-user run-path helper in `pipeline/api.py`

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

**Context:** `pipeline/api.py` currently has a function `_out_root()` at the
top of the file. Find it (`grep -n '_out_root' pipeline/api.py`). Most
endpoints call `_out_root() / run_id / ...` to read or write files.

- [ ] **Step 3.1: Write a failing test for cross-user isolation**

Append to `tests/test_api.py`:

```python
def test_user_a_cannot_see_user_b_runs(monkeypatch, tmp_path, client_factory):
    """A run created under one user_id must not appear in another user's listing."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    # Stage one run under "alice", one under "bob"
    (tmp_path / "alice" / "run-1").mkdir(parents=True)
    (tmp_path / "alice" / "run-1" / "manifest.json").write_text('{"theme":"a"}')
    (tmp_path / "bob" / "run-2").mkdir(parents=True)
    (tmp_path / "bob" / "run-2" / "manifest.json").write_text('{"theme":"b"}')

    # client_factory should produce a TestClient that uses a fake user header
    alice = client_factory(user_id="alice")
    bob = client_factory(user_id="bob")

    a_runs = alice.get("/runs").json()
    b_runs = bob.get("/runs").json()

    assert {r["run_id"] for r in a_runs} == {"run-1"}
    assert {r["run_id"] for r in b_runs} == {"run-2"}
```

You will need a `client_factory` fixture. Add this to `tests/conftest.py` (create it if missing):

```python
"""Shared pytest fixtures for the API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from pipeline.api import app
from pipeline.auth import User, require_user


@pytest.fixture
def client_factory():
    """Returns a callable that builds a TestClient with a forced user_id."""
    def _make(user_id: str = "admin", role: str = "user", email: str | None = None):
        async def _fake_user():
            return User(id=user_id, email=email, role=role)
        app.dependency_overrides[require_user] = _fake_user
        return TestClient(app)
    yield _make
    app.dependency_overrides.clear()
```

- [ ] **Step 3.2: Run the new test, verify it fails**

```bash
uv run pytest tests/test_api.py::test_user_a_cannot_see_user_b_runs -v
```

Expected: FAIL — runs not scoped by user (or `client_factory` fixture missing if conftest didn't apply yet).

- [ ] **Step 3.3: Add `_user_runs_root` and refactor `list_runs`**

Find `_out_root()` in `pipeline/api.py`. Right after its definition, add:

```python
def _user_runs_root(user: User) -> Path:
    """Per-user runs directory. All endpoints scope file reads/writes here."""
    return _out_root() / user.id
```

Then update `list_runs` (search for `@app.get("/runs"` then `def list_runs`) to:

```python
@app.get(
    "/runs",
    response_model=list[RunSummary],
    dependencies=[Depends(require_user)],
)
def list_runs(user: User = Depends(require_user)):
    out = _user_runs_root(user)
    if not out.exists():
        return []
    runs: list[RunSummary] = []
    for p in sorted(out.iterdir()):
        if not p.is_dir():
            continue
        runs.append(_summarize(p))
    return runs
```

Also add to the imports at the top of `pipeline/api.py`:

```python
from pipeline.auth import User, require_user
```

- [ ] **Step 3.4: Run the test, verify it passes**

```bash
uv run pytest tests/test_api.py::test_user_a_cannot_see_user_b_runs -v
```

Expected: PASS.

- [ ] **Step 3.5: Commit**

```bash
git add pipeline/api.py tests/test_api.py tests/conftest.py
git commit -m "feat(api): per-user run isolation — _user_runs_root helper"
```

---

## Task 4: Replace every `require_token` with `require_user` and thread `user` through

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

**Context:** `pipeline/api.py` has ~25 endpoints. Most look like:

```python
@app.post("/runs/{run_id}/approve", dependencies=[Depends(require_token)])
def approve(run_id: str, body: ApproveBody):
    run_dir = _out_root() / run_id
    ...
```

Each one needs:
1. `dependencies=[Depends(require_user)]` (already covers the auth check)
2. A `user: User = Depends(require_user)` parameter (so the function can use `user`)
3. `_out_root() / run_id` → `_user_runs_root(user) / run_id`

- [ ] **Step 4.1: Find every `require_token` and `_out_root()` call site**

```bash
grep -n 'require_token\|_out_root()' pipeline/api.py
```

Read the output and make a checklist of every line.

- [ ] **Step 4.2: For each endpoint, do the three replacements**

Pattern to apply (do this for every endpoint that currently uses `require_token`):

| Find | Replace with |
|---|---|
| `dependencies=[Depends(require_token)]` | `dependencies=[Depends(require_user)]` |
| `def endpoint_name(run_id: str, ...):` | `def endpoint_name(run_id: str, ..., user: User = Depends(require_user)):` |
| `_out_root() / run_id` | `_user_runs_root(user) / run_id` |
| `_out_root() / ...` (any other use) | `_user_runs_root(user) / ...` |

After this task, `require_token` should not appear anywhere in `pipeline/api.py`.

- [ ] **Step 4.3: Delete `require_token` definition**

Find `def require_token(` in `pipeline/api.py` and delete the function plus its
imports if they become unused. Run:

```bash
grep -n 'require_token' pipeline/api.py
```

Expected: no output.

- [ ] **Step 4.4: Update existing tests to use the `client_factory` fixture**

In `tests/test_api.py`, find places that build `TestClient(app)` directly with a
`monkeypatch.setenv("FACELESS_API_TOKEN", ...)` and an `Authorization` header.
Replace those constructions with `client = client_factory()` which auto-injects
the admin user.

The exact list of tests to update will vary; run `uv run pytest tests/test_api.py -v`
after the refactor and fix the failures one at a time.

- [ ] **Step 4.5: Run the full test suite**

```bash
uv run pytest -q
```

Expected: ~95+ tests pass. Anything that was previously hitting 401 with a hardcoded token may need to switch to `client_factory` — fix those if they show up.

- [ ] **Step 4.6: Commit**

```bash
git add pipeline/api.py tests/test_api.py tests/conftest.py
git commit -m "feat(api): scope every endpoint by user — drop require_token"
```

---

## Task 5: Per-user output directory in `run.py`

**Files:**
- Modify: `run.py`

**Context:** `run.py` is the CLI orchestrator. It currently writes to `out/<run-timestamp>/`. Find the line that builds this path (`grep -n 'out_root\|FACELESS_OUT_ROOT' run.py`).

- [ ] **Step 5.1: Add `--user-id` CLI argument**

Find the `click.command()` block in `run.py`. Add a new option right after the existing options:

```python
@click.option(
    "--user-id",
    default="admin",
    help="User who owns this run. Defaults to 'admin' for CLI / cron use.",
)
```

And add `user_id: str` to the function signature.

- [ ] **Step 5.2: Use `user_id` in the output directory**

Find the line that constructs the run directory (probably looks like
`run_dir = Path(out_root) / run_timestamp` or similar) and change it to:

```python
run_dir = Path(out_root) / user_id / run_timestamp
```

If the API server (`pipeline/api.py`) spawns `run.py` as a subprocess (it
does — see `pipeline/spawn_backends.py`), update the spawner to pass
`--user-id <user.id>`. Find the call site:

```bash
grep -n 'run.py\|run\.py' pipeline/spawn_backends.py pipeline/api.py
```

In each spawner, append `["--user-id", user.id]` to the args list.

- [ ] **Step 5.3: Smoke test the CLI**

```bash
uv run python run.py --skip-images --theme folkloric --seed "بئر قديم"
```

Expected: a directory appears under `out/admin/<timestamp>/`, not `out/<timestamp>/`.

- [ ] **Step 5.4: Commit**

```bash
git add run.py pipeline/spawn_backends.py pipeline/api.py
git commit -m "feat(orchestrator): per-user output directory (--user-id)"
```

---

## Task 6: Mount Supabase env on Cloud Run Service

**Files:**
- Modify: `deploy/cloud-run-service.yaml`
- Modify: `scripts/setup-cloud-run.sh`

- [ ] **Step 6.1: Add Supabase env to the Service YAML**

In `deploy/cloud-run-service.yaml`, find the `env:` block of the container.
Add these two entries at the end (after `KIE_API_KEY`):

```yaml
            - name: SUPABASE_URL
              value: https://eorpqwvjbljsjlzvmvom.supabase.co
            - name: SUPABASE_JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: supabase-jwt-secret
                  key: latest
```

- [ ] **Step 6.2: Add the secret to `setup-cloud-run.sh`'s write list**

In `scripts/setup-cloud-run.sh`, find the block that calls `write_secret`. Add:

```bash
write_secret "supabase-jwt-secret" "${SUPABASE_JWT_SECRET:-}"
```

- [ ] **Step 6.3: Roll out the new revision**

```bash
./scripts/build-and-push.sh
```

Expected: build succeeds, new revision deploys, new revision name printed.

- [ ] **Step 6.4: Smoke test that the service token still works**

```bash
SERVICE_URL="https://faceless-api-uplzdtffeq-uc.a.run.app"
source .env
curl -s -H "Authorization: Bearer $FACELESS_API_TOKEN" $SERVICE_URL/runs
```

Expected: `200 []` (empty list, since `out/admin/` is empty on Cloud Run).

- [ ] **Step 6.5: Smoke test that wrong tokens are rejected**

```bash
curl -s -w "%{http_code}\n" -o /dev/null \
  -H "Authorization: Bearer not-a-token" $SERVICE_URL/runs
```

Expected: `401`.

- [ ] **Step 6.6: Commit**

```bash
git add deploy/cloud-run-service.yaml scripts/setup-cloud-run.sh
git commit -m "feat(deploy): mount SUPABASE_URL + SUPABASE_JWT_SECRET on Cloud Run"
```

---

## Task 7: Add `supabase_flutter` and initialize it

**Files:**
- Modify: `pubspec.yaml`
- Modify: `lib/main.dart`

- [ ] **Step 7.1: Add the package**

Edit `pubspec.yaml`. Under `dependencies:`, add:

```yaml
  supabase_flutter: ^2.5.0
```

Then run:

```bash
flutter pub get
```

- [ ] **Step 7.2: Initialize Supabase in `main.dart`**

In `lib/main.dart`, replace the `void main()` (or `Future<void> main()`)
function with:

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

const _supabaseUrl = String.fromEnvironment('SUPABASE_URL');
const _supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (_supabaseUrl.isNotEmpty && _supabaseAnonKey.isNotEmpty) {
    await Supabase.initialize(
      url: _supabaseUrl,
      anonKey: _supabaseAnonKey,
    );
  }
  runApp(const MyApp());
}
```

(If the existing `main` already does other setup, keep that and add the
Supabase init right before `runApp`.)

- [ ] **Step 7.3: Verify the app still builds**

```bash
flutter analyze
flutter build web --dart-define=SUPABASE_URL=https://eorpqwvjbljsjlzvmvom.supabase.co \
                  --dart-define=SUPABASE_ANON_KEY=<anon-key-from-.env>
```

Expected: build succeeds with zero errors.

- [ ] **Step 7.4: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/main.dart
git commit -m "feat(flutter): wire supabase_flutter into main"
```

---

## Task 8: Login screen + route guard

**Files:**
- Create: `lib/screens/login_screen.dart`
- Modify: `lib/main.dart`

- [ ] **Step 8.1: Build `LoginScreen`**

Create `lib/screens/login_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;
  String? _info;

  Future<void> _signIn() async {
    setState(() { _busy = true; _error = null; _info = null; });
    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: _email.text.trim(),
        password: _password.text,
      );
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _signUp() async {
    setState(() { _busy = true; _error = null; _info = null; });
    try {
      await Supabase.instance.client.auth.signUp(
        email: _email.text.trim(),
        password: _password.text,
      );
      setState(() => _info = 'Check your email to confirm your account.');
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Faceless', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 24),
                TextField(
                  controller: _email,
                  decoration: const InputDecoration(labelText: 'Email'),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  decoration: const InputDecoration(labelText: 'Password'),
                  obscureText: true,
                ),
                const SizedBox(height: 16),
                if (_error != null)
                  Text(_error!, style: const TextStyle(color: Colors.redAccent)),
                if (_info != null)
                  Text(_info!, style: const TextStyle(color: Colors.green)),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _busy ? null : _signUp,
                        child: const Text('Sign up'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: _busy ? null : _signIn,
                        child: const Text('Sign in'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 8.2: Wire the route guard in `main.dart`**

Find the `home:` argument of `MaterialApp` in `lib/main.dart`. Replace it with
a `StreamBuilder` that listens to auth state:

```dart
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/login_screen.dart';

// ...

return MaterialApp(
  // ...other args unchanged...
  home: StreamBuilder<AuthState>(
    stream: Supabase.instance.client.auth.onAuthStateChange,
    builder: (context, snap) {
      final session = Supabase.instance.client.auth.currentSession;
      if (session == null) return const LoginScreen();
      return const _Bootstrap();
    },
  ),
);
```

- [ ] **Step 8.3: Verify the build**

```bash
flutter analyze
```

Expected: zero errors. Warnings about `LoginScreen` being unused are gone.

- [ ] **Step 8.4: Commit**

```bash
git add lib/screens/login_screen.dart lib/main.dart
git commit -m "feat(flutter): login screen + auth-state route guard"
```

---

## Task 9: API client uses Supabase JWT; remove manual token from Settings

**Files:**
- Modify: `lib/api/client.dart`
- Modify: `lib/api/settings.dart`
- Modify: `lib/screens/settings_screen.dart`

- [ ] **Step 9.1: Read JWT from Supabase in `FacelessApiClient._headers`**

Find this block in `lib/api/client.dart`:

```dart
Future<Map<String, String>> _headers({bool authed = true}) async {
  final h = <String, String>{'Accept': 'application/json'};
  if (authed) {
    final token = await _settings.token();
    if (token == null || token.isEmpty) {
      throw FacelessApiException('API token not configured (open Settings)');
    }
    h['Authorization'] = 'Bearer $token';
  }
  return h;
}
```

Replace with:

```dart
Future<Map<String, String>> _headers({bool authed = true}) async {
  final h = <String, String>{'Accept': 'application/json'};
  if (authed) {
    final session = Supabase.instance.client.auth.currentSession;
    final token = session?.accessToken;
    if (token == null || token.isEmpty) {
      throw FacelessApiException('Not signed in');
    }
    h['Authorization'] = 'Bearer $token';
  }
  return h;
}
```

Add `import 'package:supabase_flutter/supabase_flutter.dart';` at the top of
`client.dart`.

- [ ] **Step 9.2: Drop the token field from `FacelessSettings`**

In `lib/api/settings.dart`, find the `token()` method and any setters/getters
for it. Delete them. Also delete the storage-key constant for the token (e.g.
`_tokenKey`).

If the settings storage uses `flutter_secure_storage`, that's fine — the
remaining `baseUrl` setting can keep using it.

- [ ] **Step 9.3: Update `SettingsScreen` to drop the token UI and add Sign Out**

In `lib/screens/settings_screen.dart`:

1. Remove the `TextField` and the `Save token` button for the bearer token.
2. Remove the `client.healthz()` call (the `/healthz` is not reachable on Cloud Run anyway — see CLAUDE.md). Keep the rest of the connectivity check, or replace with a `client.listRuns()` call as the new "Test connection".
3. Add a `Sign out` button at the bottom:

```dart
ElevatedButton.icon(
  icon: const Icon(Icons.logout),
  label: const Text('Sign out'),
  onPressed: () async {
    await Supabase.instance.client.auth.signOut();
    if (context.mounted) Navigator.of(context).pop();
  },
),
```

Add `import 'package:supabase_flutter/supabase_flutter.dart';` at the top.

- [ ] **Step 9.4: Run analyzer**

```bash
flutter analyze
```

Expected: zero errors. (References to the deleted token methods will be flagged — fix them.)

- [ ] **Step 9.5: Commit**

```bash
git add lib/api/client.dart lib/api/settings.dart lib/screens/settings_screen.dart
git commit -m "feat(flutter): use Supabase JWT for API auth; drop manual token UI"
```

---

## Task 10: Update `run-app.sh` to pass Supabase --dart-defines

**Files:**
- Modify: `scripts/run-app.sh`

- [ ] **Step 10.1: Find the existing `flutter run` invocation**

```bash
grep -n 'flutter run\|dart-define' scripts/run-app.sh
```

- [ ] **Step 10.2: Add Supabase --dart-defines**

Find the line that runs `flutter` (or `flutter run`) with `--dart-define=FACELESS_API_URL=...`. Add two more `--dart-define` arguments:

```bash
  --dart-define="SUPABASE_URL=${SUPABASE_URL}" \
  --dart-define="SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}" \
```

The script already sources `.env` at the top, so `SUPABASE_URL` and
`SUPABASE_ANON_KEY` are already in scope.

- [ ] **Step 10.3: Verify**

```bash
./scripts/run-app.sh -d chrome
```

Expected: app boots, lands on the LoginScreen.

- [ ] **Step 10.4: Commit**

```bash
git add scripts/run-app.sh
git commit -m "feat(launcher): pass SUPABASE_URL + SUPABASE_ANON_KEY to flutter"
```

---

## Task 11: Migrate existing local runs to per-user layout

**Files:**
- Create: `scripts/migrate-runs-to-admin.sh`

- [ ] **Step 11.1: Create the migration script**

```bash
cat > scripts/migrate-runs-to-admin.sh <<'SCRIPT'
#!/usr/bin/env bash
# scripts/migrate-runs-to-admin.sh — one-shot mover for legacy out/<timestamp>/
# directories into the new per-user layout (out/admin/<timestamp>/).
#
# Idempotent: skips runs that are already nested under out/admin/.
set -euo pipefail

OUT_ROOT="${FACELESS_OUT_ROOT:-out}"

if [ ! -d "$OUT_ROOT" ]; then
  echo "No $OUT_ROOT/ directory found — nothing to migrate."
  exit 0
fi

mkdir -p "$OUT_ROOT/admin"

moved=0
for d in "$OUT_ROOT"/*/; do
  name=$(basename "$d")
  # Skip the per-user dirs themselves
  case "$name" in
    admin|tests) continue ;;
  esac
  # Only move directories whose name starts with 4 digits (timestamp)
  if [[ "$name" =~ ^[0-9]{4} ]]; then
    mv "$d" "$OUT_ROOT/admin/$name"
    echo "  -> moved $name"
    moved=$((moved + 1))
  fi
done

echo "Migrated $moved runs into $OUT_ROOT/admin/."
SCRIPT
chmod +x scripts/migrate-runs-to-admin.sh
```

- [ ] **Step 11.2: Run it**

```bash
./scripts/migrate-runs-to-admin.sh
```

Expected: prints "Migrated N runs" (or "0 runs" if there are no legacy dirs).

- [ ] **Step 11.3: Commit**

```bash
git add scripts/migrate-runs-to-admin.sh
git commit -m "chore(scripts): migrate-runs-to-admin one-shot helper"
```

---

## Task 12: End-to-end smoke test

**Files:** none — this is a manual verification step.

- [ ] **Step 12.1: Boot the app**

```bash
./scripts/run-app.sh -d chrome
```

- [ ] **Step 12.2: Sign up a fresh test user**

In the LoginScreen:
1. Email: `essam+test1@<yourdomain>` (Gmail also works with `+` aliases)
2. Password: any 8+ chars
3. Click **Sign up**

Expected: "Check your email to confirm" toast.

- [ ] **Step 12.3: Confirm the email**

Open the link Supabase emailed you. The app may not auto-redirect, but the
account is now confirmed.

- [ ] **Step 12.4: Sign in**

Same email + password → **Sign in**. App should land on the home screen with
an empty run list (`/runs` returns `[]`).

- [ ] **Step 12.5: Start a run, verify it appears**

Click "New Run" (or whatever your home-screen button is), submit the form. The
run should appear in the list under your account.

- [ ] **Step 12.6: Verify isolation against the admin token**

```bash
SERVICE_URL="https://faceless-api-uplzdtffeq-uc.a.run.app"
source .env
curl -s -H "Authorization: Bearer $FACELESS_API_TOKEN" $SERVICE_URL/runs
```

Expected: a list that does **not** include the run you just created in Flutter
(because that run is under your Supabase user_id, not under "admin").

- [ ] **Step 12.7: Sign out and back in**

Click Sign Out in Settings → app returns to LoginScreen. Sign in again →
your run reappears.

If all six checks pass, B2 is done.

---

## What the human reviewer should verify after the agent finishes

1. `grep -rn 'require_token' pipeline/ tests/` returns nothing.
2. `grep -rn '_out_root()' pipeline/api.py` returns nothing — every call site goes through `_user_runs_root(user)`.
3. `grep -rn 'FACELESS_API_TOKEN' lib/` returns nothing — Flutter doesn't ship the token anywhere.
4. The full pytest suite passes (`uv run pytest -q`).
5. The Cloud Run revision logs show no startup errors (`gcloud run services logs read faceless-api --region=us-central1 --limit=50`).
6. A fresh `gcloud secrets list` shows `supabase-jwt-secret`.
