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


# --- email-confirmation backstop (B1) -------------------------------------
# Conservative default-allow: only an EXPLICIT unconfirmed signal flips
# email_confirmed to False; an absent claim stays True (never block a legit
# user on a missing claim).

def test_verify_email_confirmed_true_when_claim_absent():
    # GOOD_PAYLOAD carries no confirmation claim → default-allow.
    token = _encode(GOOD_PAYLOAD)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is True


def test_verify_email_confirmed_true_when_confirmed_at_set():
    payload = {**GOOD_PAYLOAD, "email_confirmed_at": "2026-01-01T00:00:00Z"}
    token = _encode(payload)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is True


def test_verify_email_confirmed_false_when_confirmed_at_null():
    # Present-and-null → explicitly unconfirmed.
    payload = {**GOOD_PAYLOAD, "email_confirmed_at": None}
    token = _encode(payload)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is False


def test_verify_email_confirmed_false_when_user_metadata_flag_false():
    payload = {**GOOD_PAYLOAD, "user_metadata": {"email_verified": False}}
    token = _encode(payload)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is False


def test_verify_email_confirmed_false_when_top_level_flag_false():
    payload = {**GOOD_PAYLOAD, "email_verified": False}
    token = _encode(payload)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is False


def test_verify_email_confirmed_true_when_user_metadata_flag_true():
    payload = {**GOOD_PAYLOAD, "user_metadata": {"email_verified": True}}
    token = _encode(payload)
    assert verify_supabase_jwt(token, SECRET).email_confirmed is True


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


def test_require_user_service_token_email_confirmed(monkeypatch):
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    user = require_user(authorization="Bearer svc-secret")
    assert user.email_confirmed is True


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


# signup_grant logic was removed 2026-05-13 (no welcome credits — users
# get credits only via subscription). The auth hook that called
# ensure_signup_grant() is gone, so the matching tests went with it.
