"""Auth: Supabase JWT verification + FastAPI request dependency.

Three paths:
  1. Service token — the bearer matches FACELESS_API_TOKEN. Returns a synthetic
     "admin" user. Used by the CLI, cron jobs, and curl-based smoke tests.
  2. Supabase HS256 JWT — verified against SUPABASE_JWT_SECRET. Used by older
     Supabase projects and any test that signs its own tokens.
  3. Supabase ES256 JWT — verified against the public key published at
     SUPABASE_URL/auth/v1/.well-known/jwks.json. Supabase's newer projects
     sign user access tokens with ES256 (P-256 elliptic curve) by default.

The verifier peeks at the JWT header's `alg` and picks the right path.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient

# Module-level cache for the JWKS client — first lookup hits the network,
# subsequent calls reuse the cached keys. The client itself caches the
# response for ~10 min per PyJWT defaults, plus refreshes on key rotation.
_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    key = supabase_url.rstrip("/")
    if key not in _JWKS_CLIENTS:
        _JWKS_CLIENTS[key] = PyJWKClient(
            f"{key}/auth/v1/.well-known/jwks.json",
        )
    return _JWKS_CLIENTS[key]


@dataclass(frozen=True)
class User:
    id: str            # "admin" for service-token, otherwise Supabase UUID
    email: str | None  # None for service-token
    role: str          # "service" | "user"


def verify_supabase_jwt(
    token: str,
    secret: str | None = None,
    supabase_url: str | None = None,
) -> User:
    """Verify a Supabase access token and return the User.

    Picks the verification method based on the JWT's `alg` header:
      - HS256 → verify against `secret` (the project's legacy JWT secret).
      - ES256 / RS256 → fetch the public key from Supabase's JWKS endpoint
        at `{supabase_url}/auth/v1/.well-known/jwks.json`.

    Raises ValueError on any failure (expired, bad signature, etc.).
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError as e:
        raise ValueError(f"invalid token: {e}") from None
    alg = unverified_header.get("alg", "")

    try:
        if alg == "HS256":
            if not secret:
                raise ValueError(
                    "HS256 token received but SUPABASE_JWT_SECRET not set",
                )
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        elif alg in ("ES256", "RS256"):
            if not supabase_url:
                raise ValueError(
                    f"{alg} token received but SUPABASE_URL not set",
                )
            signing_key = (
                _get_jwks_client(supabase_url)
                .get_signing_key_from_jwt(token)
                .key
            )
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience="authenticated",
            )
        else:
            raise ValueError(f"unsupported alg: {alg!r}")
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
    supabase_url = os.environ.get("SUPABASE_URL")
    can_verify_jwt = bool(jwt_secret) or bool(supabase_url)

    if not service_token and not can_verify_jwt:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured (FACELESS_API_TOKEN, or "
                   "SUPABASE_URL + SUPABASE_JWT_SECRET, must be set).",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if service_token and token == service_token:
        return User(id="admin", email=None, role="service")

    if can_verify_jwt:
        try:
            user = verify_supabase_jwt(
                token,
                secret=jwt_secret,
                supabase_url=supabase_url,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            ) from None
        # Lazy-init: ensures the user has a profile + signup grant the first time
        # they hit any authenticated endpoint. Cheap (one SELECT for repeat users).
        # Imported lazily to avoid a cycle (credits imports auth.User).
        from pipeline.credits import ensure_signup_grant
        try:
            ensure_signup_grant(user)
        except Exception:
            # If the DB is unreachable, don't block auth — log it and continue.
            # The user just won't have their grant; we can backfill later.
            pass
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token.",
    )


def require_user_header_or_query(
    authorization: str | None = Header(None),
    token: str | None = None,
) -> User:
    """Like require_user, but also accepts ?token=... in the query string.

    Used by /video and /thumbnail endpoints — Flutter's video_player on Chrome
    web silently drops httpHeaders, so a query-string token is the standard
    workaround for browser-driven media streaming.
    """
    if authorization and authorization.startswith("Bearer "):
        return require_user(authorization=authorization)
    if token:
        return require_user(authorization=f"Bearer {token}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Provide either Authorization: Bearer header or ?token=… query.",
    )
