# src/pco_mcp/auth.py
"""Bearer-token middleware for the MCP transport.

Resolves our issued access tokens to upstream PCO access tokens and
injects them into the ASGI scope so that FastMCP's
``get_access_token()`` (used by tools via ``_context.py``) finds them.

Includes DB fallback lookup (survives restarts) and PCO token refresh.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.dependencies import AuthenticatedUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from pco_mcp.config import Settings
from pco_mcp.crypto import decrypt_token, encrypt_token
from pco_mcp.models import OAuthSession, User

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _lookup_token_in_db(
    bearer_token: str,
    session_factory: async_sessionmaker,
    settings: Settings,
) -> dict[str, Any] | None:
    """Look up a bearer token in the database. Returns token_data dict or None."""
    token_hash = _hash_token(bearer_token)
    try:
        async with session_factory() as db:
            stmt = (
                select(OAuthSession, User)
                .join(User, OAuthSession.user_id == User.id)
                .where(OAuthSession.chatgpt_access_token_hash == token_hash)
                .where(OAuthSession.expires_at > datetime.now(UTC))
            )
            result = await db.execute(stmt)
            row = result.one_or_none()
            if row is None:
                return None
            oauth_session, user = row
            pco_access = decrypt_token(user.pco_access_token_enc, settings.token_encryption_key)
            pco_refresh = decrypt_token(user.pco_refresh_token_enc, settings.token_encryption_key)
            return {
                "pco_access_token": pco_access,
                "pco_refresh_token": pco_refresh or None,
                "pco_token_expires": user.pco_token_expires_at,
                "pco_me": {"id": user.pco_person_id, "org_name": user.pco_org_name},
                "expires": oauth_session.expires_at,
            }
    except Exception:
        logger.warning("DB lookup for bearer token failed", exc_info=True)
        return None


async def _try_refresh_pco_token(
    token_data: dict[str, Any],
    settings: Settings,
    oauth_tokens: dict[str, dict[str, Any]],
    bearer_token: str,
    session_factory: async_sessionmaker | None = None,
) -> str | None:
    """If the PCO token is near expiry, try to refresh it. Returns new access token or None."""
    pco_token_expires = token_data.get("pco_token_expires")
    pco_refresh_token = token_data.get("pco_refresh_token")
    if not pco_token_expires or not pco_refresh_token:
        return None
    if pco_token_expires > datetime.now(UTC) + timedelta(minutes=5):
        return None  # Not near expiry

    try:
        from pco_mcp.oauth.pco_client import refresh_pco_token  # noqa: PLC0415

        new_tokens = await refresh_pco_token(
            refresh_token=pco_refresh_token,
            client_id=settings.pco_client_id,
            client_secret=settings.pco_client_secret,
        )
        new_access = new_tokens["access_token"]
        new_refresh = new_tokens.get("refresh_token", pco_refresh_token)
        new_expires = datetime.now(UTC) + timedelta(hours=2)

        # Update in-memory
        token_data["pco_access_token"] = new_access
        token_data["pco_refresh_token"] = new_refresh
        token_data["pco_token_expires"] = new_expires

        # Update DB if available
        if session_factory is not None:
            try:
                pco_me = token_data.get("pco_me", {})
                pco_person_id = pco_me.get("id")
                if pco_person_id:
                    async with session_factory() as db:
                        stmt = select(User).where(User.pco_person_id == pco_person_id)
                        result = await db.execute(stmt)
                        user = result.scalar_one_or_none()
                        if user:
                            user.pco_access_token_enc = encrypt_token(
                                new_access, settings.token_encryption_key
                            )
                            user.pco_refresh_token_enc = encrypt_token(
                                new_refresh, settings.token_encryption_key
                            )
                            user.pco_token_expires_at = new_expires
                            user.last_used_at = datetime.now(UTC)
                            await db.commit()
            except Exception:
                logger.warning("Failed to persist refreshed token to DB", exc_info=True)

        logger.info("Refreshed PCO token successfully")
        return new_access
    except Exception:
        logger.warning("PCO token refresh failed", exc_info=True)
        return None


async def inject_pco_bearer(
    request: Request,
    call_next: Any,
    oauth_tokens: dict[str, dict[str, Any]],
    session_factory: async_sessionmaker | None = None,
    settings: Settings | None = None,
) -> Any:
    """Middleware helper: resolve Bearer token to PCO credentials.

    If the request carries a valid ``Authorization: Bearer <token>`` that
    maps to one of our issued tokens, we create an ``AuthenticatedUser``
    and stash it in ``request.scope["user"]`` so that FastMCP's
    ``get_access_token()`` returns the upstream PCO access token.

    Falls back to DB lookup if the token is not in the in-memory dict.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:]
        token_data = oauth_tokens.get(bearer_token)

        # DB fallback: if not in memory but we have DB access
        if token_data is None and session_factory is not None and settings is not None:
            token_data = await _lookup_token_in_db(bearer_token, session_factory, settings)
            if token_data is not None:
                # Cache in memory for future fast-path lookups
                oauth_tokens[bearer_token] = token_data
                logger.info("Restored token from DB into in-memory cache")

        if token_data is not None:
            # Check expiry
            expires = token_data.get("expires")
            if expires and expires < datetime.now(UTC):
                logger.warning("Bearer token expired")
                response = JSONResponse(
                    {"error": "Session expired. Please reconnect."},
                    status_code=401,
                )
                return response

            pco_access_token = token_data.get("pco_access_token")
            if pco_access_token:
                # Try refreshing PCO token if near expiry
                if settings is not None:
                    refreshed = await _try_refresh_pco_token(
                        token_data, settings, oauth_tokens, bearer_token, session_factory
                    )
                    if refreshed:
                        pco_access_token = refreshed

                pco_me = token_data.get("pco_me", {})
                person_id = str(pco_me.get("id", "unknown"))

                access_token = AccessToken(
                    token=pco_access_token,
                    client_id=person_id,
                    scopes=["people", "services"],
                    expires_at=None,
                    claims={
                        "sub": person_id,
                        "pco_person_id": pco_me.get("id"),
                    },
                )
                request.scope["user"] = AuthenticatedUser(access_token)
                logger.debug(
                    "Authenticated request for person_id=%s", person_id
                )

    # Fallback: treat the bearer token as a raw PCO access token.
    # This supports direct MCP clients (like pco-agent) that send the
    # PCO access token directly rather than going through pco-mcp's
    # own OAuth flow.
    if auth_header.lower().startswith("bearer ") and "user" not in request.scope:
        raw_token = auth_header[7:]
        access_token = AccessToken(
            token=raw_token,
            client_id="direct",
            scopes=["people", "services"],
            expires_at=None,
        )
        request.scope["user"] = AuthenticatedUser(access_token)
        logger.debug("Using raw Bearer token as PCO access token (direct client)")

    return await call_next(request)
