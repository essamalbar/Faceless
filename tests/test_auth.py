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


def test_require_user_header_or_query_accepts_query_token(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    from pipeline.auth import require_user_header_or_query
    user = require_user_header_or_query(authorization=None, token="svc-secret")
    assert user.id == "admin"


def test_require_user_header_or_query_accepts_header(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    from pipeline.auth import require_user_header_or_query
    user = require_user_header_or_query(
        authorization="Bearer svc-secret", token=None,
    )
    assert user.id == "admin"


def test_require_user_header_or_query_401_when_neither(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    from pipeline.auth import require_user_header_or_query
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_user_header_or_query(authorization=None, token=None)
    assert exc.value.status_code == 401


def test_require_user_calls_ensure_signup_grant(monkeypatch):
    """A successful JWT verification triggers the signup-grant hook exactly once."""
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    called: list[str] = []
    def fake_grant(user):
        called.append(user.id)
    monkeypatch.setattr("pipeline.credits.ensure_signup_grant", fake_grant)
    token = _encode(GOOD_PAYLOAD)
    user = require_user(authorization=f"Bearer {token}")
    assert called == [user.id]


def test_require_user_swallows_db_errors_in_signup_grant(monkeypatch):
    """If the DB is down, auth must still succeed (with no grant)."""
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    def fake_grant(user):
        raise RuntimeError("supabase down")
    monkeypatch.setattr("pipeline.credits.ensure_signup_grant", fake_grant)
    token = _encode(GOOD_PAYLOAD)
    # Should not raise
    user = require_user(authorization=f"Bearer {token}")
    assert user.id == GOOD_PAYLOAD["sub"]
