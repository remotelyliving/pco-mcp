# src/pco_mcp/oauth/provider.py
"""Helpers for the direct (non-ChatGPT) dashboard authentication flow.

The ChatGPT-facing OAuth flow (DCR, authorize, token, callback) is now
handled entirely by FastMCP's OAuthProxy.  Only the direct web-dashboard
auth helpers remain here.
"""
import secrets
from typing import Any

_pending_auth_codes: dict[str, dict[str, Any]] = {}


def create_direct_auth_state(pco_client_id: str, base_url: str) -> str:
    """Create a pending state entry for the direct (non-ChatGPT) OAuth flow.

    Returns the PCO OAuth authorize URL to redirect the user to.
    """
    internal_state = secrets.token_urlsafe(32)
    _pending_auth_codes[internal_state] = {
        "flow": "direct",
    }
    pco_auth_url = (
        f"https://api.planningcenteronline.com/oauth/authorize"
        f"?client_id={pco_client_id}"
        f"&redirect_uri={base_url}/oauth/pco-callback"
        f"&response_type=code"
        f"&scope=people+services"
        f"&state={internal_state}"
    )
    return pco_auth_url


def redeem_dashboard_token(token: str) -> dict[str, Any] | None:
    """Exchange a short-lived dashboard token for user info.

    Returns the payload dict if valid, or None if invalid/expired.
    Consumes the token (single-use).
    """
    entry = _pending_auth_codes.pop(token, None)
    if entry and entry.get("type") == "dashboard_token":
        return entry
    return None
