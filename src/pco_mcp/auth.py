# src/pco_mcp/auth.py
"""PCO OAuth provider for FastMCP using OAuthProxy."""
from __future__ import annotations

import contextlib
import logging
from typing import Literal

import httpx
from pydantic import AnyHttpUrl

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy

logger = logging.getLogger(__name__)

PCO_AUTHORIZE_URL = "https://api.planningcenteronline.com/oauth/authorize"
PCO_TOKEN_URL = "https://api.planningcenteronline.com/oauth/token"  # noqa: S105
PCO_ME_URL = "https://api.planningcenteronline.com/people/v2/me"


class PCOTokenVerifier(TokenVerifier):
    """Verify PCO OAuth tokens by calling the /people/v2/me endpoint.

    PCO tokens are opaque, so we validate them by making an authenticated
    API call.  On success the upstream PCO access token is stashed in the
    AccessToken so that tools can use it directly.
    """

    def __init__(
        self,
        *,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(required_scopes=required_scopes)
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a PCO access token by calling /people/v2/me."""
        try:
            async with (
                contextlib.nullcontext(self._http_client)
                if self._http_client is not None
                else httpx.AsyncClient(timeout=self.timeout_seconds)
            ) as client:
                response = await client.get(
                    PCO_ME_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                )

                if response.status_code != 200:
                    logger.debug(
                        "PCO token verification failed: %d",
                        response.status_code,
                    )
                    return None

                body = response.json()
                data = body["data"]
                person_id = data["id"]

                return AccessToken(
                    token=token,
                    client_id=str(person_id),
                    scopes=["people", "services"],
                    expires_at=None,
                    claims={
                        "sub": str(person_id),
                        "pco_person_id": person_id,
                    },
                )

        except httpx.RequestError as e:
            logger.debug("Failed to verify PCO token: %s", e)
            return None
        except Exception as e:
            logger.debug("PCO token verification error: %s", e)
            return None


class PCOProvider(OAuthProxy):
    """Complete PCO OAuth provider for FastMCP.

    Wraps Planning Center Online as the upstream identity provider.
    ChatGPT/Claude register via DCR, users authorize via PCO, and
    tools receive the upstream PCO access token through
    ``get_access_token().token``.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        base_url: AnyHttpUrl | str,
        issuer_url: AnyHttpUrl | str | None = None,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
        require_authorization_consent: bool | Literal["external"] = "external",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        required_scopes_final = required_scopes or ["people", "services"]

        token_verifier = PCOTokenVerifier(
            required_scopes=required_scopes_final,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )

        super().__init__(
            upstream_authorization_endpoint=PCO_AUTHORIZE_URL,
            upstream_token_endpoint=PCO_TOKEN_URL,
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            token_verifier=token_verifier,
            base_url=base_url,
            issuer_url=issuer_url or base_url,
            require_authorization_consent=require_authorization_consent,
            extra_authorize_params={"scope": "people services"},
        )

        logger.info(
            "Initialized PCO OAuth provider (base_url=%s)",
            base_url,
        )
