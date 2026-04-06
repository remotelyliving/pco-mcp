# src/pco_mcp/oauth/provider.py
"""Helpers for the direct (non-ChatGPT) dashboard authentication flow.

These functions work with the in-memory stores defined in main.py.
The ``_pending_dashboard_tokens`` dict is local to this module and
holds short-lived dashboard tokens consumed by the /dashboard route.
"""
import secrets
from typing import Any
from urllib.parse import urlencode

# Short-lived dashboard tokens (separate from the main OAuth stores)
_pending_dashboard_tokens: dict[str, dict[str, Any]] = {}


def create_direct_auth_state(
    pco_client_id: str,
    base_url: str,
    oauth_codes: dict[str, dict[str, Any]],
) -> str:
    """Create a pending state entry for the direct (non-ChatGPT) OAuth flow.

    Stores the pending auth in the shared ``oauth_codes`` dict so that
    /oauth/pco-callback can handle both ChatGPT and direct flows.

    Returns the PCO OAuth authorize URL to redirect the user to.
    """
    from datetime import UTC, datetime, timedelta

    internal_state = secrets.token_urlsafe(32)
    oauth_codes[internal_state] = {
        "type": "pending_direct_auth",
        "expires": datetime.now(UTC) + timedelta(minutes=10),
    }
    params = {
        "client_id": pco_client_id,
        "redirect_uri": f"{base_url.rstrip('/')}/oauth/pco-callback",
        "response_type": "code",
        "scope": "people services",
        "state": internal_state,
    }
    pco_auth_url = f"https://api.planningcenteronline.com/oauth/authorize?{urlencode(params)}"
    return pco_auth_url


def store_dashboard_token(token: str, payload: dict[str, Any]) -> None:
    """Store a short-lived dashboard token for the /dashboard route."""
    _pending_dashboard_tokens[token] = {**payload, "type": "dashboard_token"}


def redeem_dashboard_token(token: str) -> dict[str, Any] | None:
    """Exchange a short-lived dashboard token for user info.

    Returns the payload dict if valid, or None if invalid/expired.
    Consumes the token (single-use).
    """
    entry = _pending_dashboard_tokens.pop(token, None)
    if entry and entry.get("type") == "dashboard_token":
        return entry
    return None
