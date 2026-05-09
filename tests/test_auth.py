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
