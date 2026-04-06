# src/pco_mcp/main.py
import json
import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastmcp import FastMCP
from sqlalchemy import text

from pco_mcp.auth import PCOProvider
from pco_mcp.config import Settings
from pco_mcp.db import create_engine, create_session_factory
from pco_mcp.models import Base
from pco_mcp.tools.people import register_people_tools
from pco_mcp.tools.services import register_services_tools

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and wire the full application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # Build the PCO OAuth provider — handles DCR, PKCE, CORS, token mgmt
    auth = PCOProvider(
        client_id=settings.pco_client_id,
        client_secret=settings.pco_client_secret,
        base_url=settings.base_url,
    )

    mcp = FastMCP(
        "Planning Center MCP",
        instructions=(
            "You are connected to Planning Center Online, a church management platform. "
            "You can search people, view service plans, list songs, and manage team schedules. "
            "Always confirm before creating or updating records."
        ),
        auth=auth,
    )
    register_people_tools(mcp)
    register_services_tools(mcp)

    # FastMCP's http_app now includes all OAuth endpoints (.well-known, /register,
    # /authorize, /token, /callback, protected-resource metadata, CORS, etc.)
    mcp_app = mcp.http_app(path="/mcp")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("pco-mcp starting up (base_url=%s)", settings.base_url)
        async with mcp_app.lifespan(mcp_app):
            # In production, run `alembic upgrade head` instead.
            # create_all is kept for development with SQLite.
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema ready")
            yield
            await engine.dispose()
            logger.info("pco-mcp shut down")

    app = FastAPI(title="pco-mcp", lifespan=lifespan)

    @app.middleware("http")
    async def patch_dcr_response(request: Request, call_next):  # type: ignore[misc]
        """Patch the DCR response to always include client_secret.

        ChatGPT has a known quirk: it registers with token_endpoint_auth_method="none"
        (public client) but still expects client_secret in the response. FastMCP correctly
        omits it per RFC 7591, but that causes ChatGPT to reject with "doesn't support
        RFC 7591 Dynamic Client Registration".

        See: https://community.openai.com/t/mcp-with-oauth-dynamic-registration/1366118
        """
        response = await call_next(request)
        # Security headers on all responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Patch DCR 201 responses to include client_secret if missing
        if (
            request.url.path.rstrip("/") == "/register"
            and request.method == "POST"
            and response.status_code == 201
        ):
            # Read the response body
            body_bytes = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    body_bytes += chunk.encode()
                else:
                    body_bytes += chunk
            try:
                body = json.loads(body_bytes)
                if "client_secret" not in body:
                    body["client_secret"] = secrets.token_urlsafe(48)
                    body["client_secret_expires_at"] = 0
                    logger.info("Patched DCR response with client_secret for ChatGPT compat")
                patched = json.dumps(body).encode()
                return JSONResponse(
                    content=body,
                    status_code=201,
                    headers=dict(response.headers),
                )
            except Exception:
                # If we can't parse, return original
                from starlette.responses import Response
                return Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
        return response

    @app.get("/health")
    async def health() -> JSONResponse:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "unhealthy", "db": "error"}, status_code=503)
        return JSONResponse({"status": "healthy"})

    # ChatGPT checks /.well-known/oauth-protected-resource at the ROOT
    # before checking the /mcp subpath variant. FastMCP only serves the
    # subpath variant. Add a root fallback that points to the MCP resource.
    @app.get("/.well-known/oauth-protected-resource")
    async def root_protected_resource() -> JSONResponse:
        return JSONResponse({
            "resource": f"{settings.base_url}/mcp",
            "authorization_servers": [f"{settings.base_url}/"],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["people", "services"],
        })

    # Web routes (landing page, setup guide, dashboard)
    from pco_mcp.web.routes import router as web_router  # noqa: PLC0415
    app.include_router(web_router)

    # Mount the MCP app (includes all OAuth + MCP transport endpoints)
    app.mount("/", mcp_app)

    return app
