# src/pco_mcp/middleware.py
"""ASGI middleware that resolves ChatGPT bearer tokens to authenticated PCO clients."""
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pco_mcp.crypto import decrypt_token, encrypt_token
from pco_mcp.models import OAuthSession, User
from pco_mcp.oauth.pco_client import refresh_pco_token
from pco_mcp.pco.client import PCOClient
from pco_mcp.tools._context import set_pco_client

logger = logging.getLogger(__name__)

# How many seconds before PCO token expiry we proactively refresh
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


def _json_error(status: int, message: str) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Build a plain-English JSON error response tuple for ASGI."""
    body = json.dumps({"error": message}).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    return status, headers, body


class BearerTokenMiddleware:
    """Resolve a ChatGPT bearer token to an authenticated PCO client.

    Only intercepts requests whose path starts with the configured MCP prefix.
    All other routes (health check, OAuth, web pages) pass through untouched.
    """

    def __init__(
        self,
        app: Any,
        session_factory: async_sessionmaker[AsyncSession],
        token_encryption_key: str,
        pco_client_id: str,
        pco_client_secret: str,
        pco_api_base: str = "https://api.planningcenteronline.com",
        mcp_path_prefix: str = "/mcp",
        base_url: str = "",
    ) -> None:
        self._app = app
        self._session_factory = session_factory
        self._encryption_key = token_encryption_key
        self._pco_client_id = pco_client_id
        self._pco_client_secret = pco_client_secret
        self._pco_api_base = pco_api_base
        self._mcp_path_prefix = mcp_path_prefix
        self._base_url = base_url.rstrip("/")

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        # Only intercept HTTP requests targeting the MCP prefix
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if not path.startswith(self._mcp_path_prefix):
            await self._app(scope, receive, send)
            return

        # Extract bearer token from Authorization header
        raw_token = self._extract_bearer(scope.get("headers", []))
        if raw_token is None:
            logger.debug("MCP request missing Authorization header — rejecting")
            await self._send_error(
                send, 401, "Authentication required. Please connect your Planning Center account."
            )
            return

        # Authenticate and set up the PCO client
        auth_result = await self._authenticate(raw_token)
        if auth_result is not None:
            # auth_result is an error message string on failure
            await self._send_error(send, 401, auth_result)
            return

        # Proceed to the wrapped MCP app
        await self._app(scope, receive, send)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_bearer(self, headers: list[tuple[bytes, bytes]]) -> str | None:
        """Return the raw bearer token from request headers, or None."""
        for name, value in headers:
            if name.lower() == b"authorization":
                decoded = value.decode("latin-1")
                parts = decoded.split(" ", 1)
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    return parts[1].strip()
        return None

    async def _authenticate(self, raw_token: str) -> str | None:
        """Resolve *raw_token* to a PCO client and call set_pco_client().

        Returns None on success, or a plain-English error string on failure.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        async with self._session_factory() as db:
            # Look up the OAuth session by token hash
            result = await db.execute(
                select(OAuthSession).where(OAuthSession.chatgpt_access_token_hash == token_hash)
            )
            session: OAuthSession | None = result.scalar_one_or_none()

            if session is None:
                logger.warning("Bearer token not found in database")
                return "Your session was not found. Please reconnect your Planning Center account."

            now = datetime.now(UTC)
            session_expires = session.expires_at
            if session_expires.tzinfo is None:
                session_expires = session_expires.replace(tzinfo=UTC)
            if session_expires <= now:
                logger.warning("Bearer token has expired (session_id=%s)", session.id)
                return "Your session has expired. Please reconnect your Planning Center account."

            # Load associated user
            user_result = await db.execute(
                select(User).where(User.id == session.user_id)
            )
            user: User | None = user_result.scalar_one_or_none()

            if user is None:
                logger.error("OAuth session references non-existent user (session_id=%s)", session.id)
                return "Your account was not found. Please reconnect your Planning Center account."

            # Refresh PCO token if it is within 5 minutes of expiry
            pco_expires = user.pco_token_expires_at
            if pco_expires.tzinfo is None:
                pco_expires = pco_expires.replace(tzinfo=UTC)
            if pco_expires <= now + timedelta(seconds=_REFRESH_BUFFER_SECONDS):
                logger.info("PCO token near expiry — refreshing (user_id=%s)", user.id)
                try:
                    refresh_token = decrypt_token(user.pco_refresh_token_enc, self._encryption_key)
                    token_data = await refresh_pco_token(
                        refresh_token=refresh_token,
                        client_id=self._pco_client_id,
                        client_secret=self._pco_client_secret,
                    )
                    new_access_token: str = token_data["access_token"]
                    new_refresh_token: str = token_data.get("refresh_token", refresh_token)
                    expires_in: int = int(token_data.get("expires_in", 7200))

                    user.pco_access_token_enc = encrypt_token(new_access_token, self._encryption_key)
                    user.pco_refresh_token_enc = encrypt_token(new_refresh_token, self._encryption_key)
                    user.pco_token_expires_at = now + timedelta(seconds=expires_in)
                    await db.commit()
                    await db.refresh(user)

                    pco_access_token = new_access_token
                    logger.info("PCO token refreshed successfully (user_id=%s)", user.id)
                except Exception:
                    logger.exception("Failed to refresh PCO token (user_id=%s)", user.id)
                    return "Unable to refresh your Planning Center credentials. Please reconnect your account."
            else:
                pco_access_token = decrypt_token(user.pco_access_token_enc, self._encryption_key)

        # Build and register the PCO client for this request context
        pco_client = PCOClient(base_url=self._pco_api_base, access_token=pco_access_token)
        set_pco_client(pco_client)
        logger.debug("PCO client set for user_id=%s", user.id)
        return None

    async def _send_error(self, send: Any, status: int, message: str) -> None:
        """Send a JSON error response through the ASGI send callable.

        For 401 responses, includes a WWW-Authenticate header per RFC 9728
        pointing to the protected-resource metadata endpoint. This lets
        OAuth clients (like ChatGPT) discover the authorization server.
        """
        body = json.dumps({"error": message}).encode()
        headers: list[list[bytes]] = [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ]
        if status == 401 and self._base_url:
            metadata_url = f"{self._base_url}/.well-known/oauth-protected-resource/mcp"
            # RFC 6750 + MCP spec: include scope in WWW-Authenticate so clients
            # can discover required scopes on the initial unauthenticated request.
            www_auth = (
                f'Bearer realm="pco-mcp", '
                f'resource_metadata="{metadata_url}", '
                f'scope="people services"'
            )
            headers.append([b"www-authenticate", www_auth.encode()])
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
