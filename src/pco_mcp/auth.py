# src/pco_mcp/auth.py
"""Bearer-token middleware for the MCP transport.

Resolves our issued access tokens to upstream PCO access tokens and
injects them into the ASGI scope so that FastMCP's
``get_access_token()`` (used by tools via ``_context.py``) finds them.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.dependencies import AuthenticatedUser

logger = logging.getLogger(__name__)


async def inject_pco_bearer(
    request: Request,
    call_next: Any,
    oauth_tokens: dict[str, dict[str, Any]],
) -> Any:
    """Middleware helper: resolve Bearer token to PCO credentials.

    If the request carries a valid ``Authorization: Bearer <token>`` that
    maps to one of our issued tokens, we create an ``AuthenticatedUser``
    and stash it in ``request.scope["user"]`` so that FastMCP's
    ``get_access_token()`` returns the upstream PCO access token.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:]
        token_data = oauth_tokens.get(bearer_token)
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
            else:
                pco_access_token = token_data.get("pco_access_token")
                if pco_access_token:
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

    return await call_next(request)
