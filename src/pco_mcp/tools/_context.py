# src/pco_mcp/tools/_context.py
"""Per-request context for MCP tools.

The upstream PCO access token is obtained via FastMCP's dependency
injection (get_access_token().token) which is populated by the
OAuthProxy auth layer.  A PCOClient is built on-the-fly from that
token for each request.
"""
from fastmcp.server.dependencies import get_access_token

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI

PCO_API_BASE = "https://api.planningcenteronline.com"


def get_pco_client() -> PCOClient:
    """Build a PCOClient from the current request's upstream access token."""
    access_token = get_access_token()
    if access_token is None:
        raise RuntimeError("No authenticated PCO access token available")
    return PCOClient(base_url=PCO_API_BASE, access_token=access_token.token)


def get_people_api() -> PeopleAPI:
    return PeopleAPI(get_pco_client())


def get_services_api() -> ServicesAPI:
    return ServicesAPI(get_pco_client())
