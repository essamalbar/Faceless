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
