import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PCO_TOKEN_URL = "https://api.planningcenteronline.com/oauth/token"  # noqa: S105
PCO_ME_URL = "https://api.planningcenteronline.com/people/v2/me"


async def exchange_pco_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Exchange a PCO authorization code for access + refresh tokens."""
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.post(
            PCO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        if not resp.is_success:
            logger.warning("PCO token exchange failed: status=%s", resp.status_code)
            raise Exception(f"PCO token exchange failed: {resp.status_code} {resp.text}")
        logger.info("PCO token exchange successful")
        result: dict[str, Any] = resp.json()
        return result
    finally:
        if http_client is None:
            await client.aclose()


async def get_pco_me(
    access_token: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Get the current user's PCO person ID and org info."""
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(
            PCO_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not resp.is_success:
            logger.warning("PCO /me request failed: status=%s", resp.status_code)
            raise Exception(f"PCO /me request failed: {resp.status_code}")
        body: dict[str, Any] = resp.json()
        data = body["data"]
        meta = body.get("meta", {})
        parent = meta.get("parent", {})
        parent_attrs = parent.get("attributes", {})
        return {
            "id": int(data["id"]),
            "first_name": data["attributes"].get("first_name"),
            "last_name": data["attributes"].get("last_name"),
            "org_name": parent_attrs.get("name"),
        }
    finally:
        if http_client is None:
            await client.aclose()


async def refresh_pco_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Refresh a PCO access token using a refresh token."""
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.post(
            PCO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if not resp.is_success:
            raise Exception(f"PCO token refresh failed: {resp.status_code}")
        result: dict[str, Any] = resp.json()
        return result
    finally:
        if http_client is None:
            await client.aclose()
