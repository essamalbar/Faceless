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
