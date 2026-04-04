# src/pco_mcp/tools/_context.py
"""Per-request context for MCP tools."""
from contextvars import ContextVar

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI

_pco_client_var: ContextVar[PCOClient] = ContextVar("pco_client")


def set_pco_client(client: PCOClient) -> None:
    _pco_client_var.set(client)


def get_pco_client() -> PCOClient:
    return _pco_client_var.get()


def get_people_api() -> PeopleAPI:
    return PeopleAPI(get_pco_client())


def get_services_api() -> ServicesAPI:
    return ServicesAPI(get_pco_client())
