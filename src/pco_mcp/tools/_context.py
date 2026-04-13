# src/pco_mcp/tools/_context.py
"""Per-request context for MCP tools.

The upstream PCO access token is obtained via FastMCP's dependency
injection (get_access_token().token) which is populated by the
OAuthProxy auth layer.  A PCOClient is built on-the-fly from that
token for each request, sharing a single httpx.AsyncClient to avoid
resource leaks.
"""
from __future__ import annotations

import logging
from collections.abc import Coroutine
from typing import Any, TypeVar

import httpx
from fastmcp.server.dependencies import get_access_token

from pco_mcp.errors import map_pco_error
from pco_mcp.pco.calendar import CalendarAPI
from pco_mcp.pco.checkins import CheckInsAPI
from pco_mcp.pco.client import PCOAPIError, PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI

logger = logging.getLogger(__name__)

PCO_API_BASE = "https://api.planningcenteronline.com"


def configure(settings: Any) -> None:
    """Override module-level config from the application Settings object."""
    global PCO_API_BASE  # noqa: PLW0603
    PCO_API_BASE = settings.pco_api_base


# Module-level shared httpx.AsyncClient — created once, reused across
# all tool calls to avoid leaking connections.
_shared_http_client: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_http_client
    if _shared_http_client is None:
        _shared_http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    return _shared_http_client


async def close_shared_client() -> None:
    """Close the shared httpx client (call on shutdown)."""
    global _shared_http_client
    if _shared_http_client is not None:
        await _shared_http_client.aclose()
        _shared_http_client = None


def get_pco_client() -> PCOClient:
    """Build a PCOClient from the current request's upstream access token."""
    access_token = get_access_token()
    if access_token is None:
        raise RuntimeError("No authenticated PCO access token available")
    return PCOClient(
        base_url=PCO_API_BASE,
        access_token=access_token.token,
        http_client=_get_shared_client(),
    )


def get_people_api() -> PeopleAPI:
    return PeopleAPI(get_pco_client())


def get_services_api() -> ServicesAPI:
    return ServicesAPI(get_pco_client())


def get_checkins_api() -> CheckInsAPI:
    return CheckInsAPI(get_pco_client())


def get_calendar_api() -> CalendarAPI:
    return CalendarAPI(get_pco_client())


T = TypeVar("T")


async def safe_tool_call(coro: Coroutine[Any, Any, T]) -> T | dict[str, str]:
    """Wrap a tool coroutine to return friendly errors instead of raising."""
    try:
        return await coro
    except PCOAPIError as e:
        logger.warning("PCO API error in tool call: %s", e)
        if e.status_code == 422:
            return {"error": f"Planning Center rejected the request: {e.detail}"}
        return {"error": map_pco_error(e.status_code, "https://pco-mcp.com")}
    except RuntimeError as e:
        if "No authenticated" in str(e):
            return {"error": "Please reconnect your Planning Center account."}
        raise
