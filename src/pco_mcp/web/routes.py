# src/pco_mcp/web/routes.py
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html")


@router.get("/setup-guide", response_class=HTMLResponse)
async def setup_guide(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "setup_guide.html")


@router.get("/auth/start")
async def auth_start(request: Request) -> RedirectResponse:
    """Initiate the PCO OAuth flow for direct (non-ChatGPT) users."""
    from pco_mcp.config import Settings
    from pco_mcp.main import oauth_codes
    from pco_mcp.oauth.provider import create_direct_auth_state

    settings = Settings()
    pco_auth_url = create_direct_auth_state(
        pco_client_id=settings.pco_client_id,
        base_url=settings.base_url,
        oauth_codes=oauth_codes,
    )
    return RedirectResponse(url=pco_auth_url)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = Query("")) -> HTMLResponse:
    """Show the user's MCP endpoint URL and org info after connecting."""
    from pco_mcp.config import Settings
    from pco_mcp.oauth.provider import redeem_dashboard_token

    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    payload = redeem_dashboard_token(token)
    if payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    settings = Settings()
    mcp_url = f"{settings.base_url}/mcp/"
    org_name = payload.get("org_name") or "Your Organization"

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"mcp_url": mcp_url, "org_name": org_name},
    )
