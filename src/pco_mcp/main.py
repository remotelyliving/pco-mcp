# src/pco_mcp/main.py
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from sqlalchemy import text

from pco_mcp.config import Settings
from pco_mcp.db import create_engine, create_session_factory
from pco_mcp.middleware import BearerTokenMiddleware
from pco_mcp.models import Base
from pco_mcp.oauth.provider import create_oauth_router
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

    mcp = FastMCP(
        "Planning Center MCP",
        instructions=(
            "You are connected to Planning Center Online, a church management platform. "
            "You can search people, view service plans, list songs, and manage team schedules. "
            "Always confirm before creating or updating records."
        ),
    )
    register_people_tools(mcp)
    register_services_tools(mcp)

    mcp_app = mcp.http_app(path="/")

    from pathlib import Path  # noqa: PLC0415

    from fastapi.templating import Jinja2Templates  # noqa: PLC0415

    _template_dir = Path(__file__).parent / "web" / "templates"
    _templates = Jinja2Templates(directory=str(_template_dir))

    oauth_router = create_oauth_router(
        session_factory=session_factory,
        pco_client_id=settings.pco_client_id,
        pco_client_secret=settings.pco_client_secret,
        base_url=settings.base_url,
        token_encryption_key=settings.token_encryption_key,
        templates=_templates,
    )

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
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.get("/health")
    async def health() -> JSONResponse:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "unhealthy", "db": "error"}, status_code=503)
        return JSONResponse({"status": "healthy"})

    # OAuth 2.1 Authorization Server Metadata (RFC 8414)
    # ChatGPT queries these to discover authorize/token/register endpoints.
    def _auth_server_metadata() -> dict:
        return {
            "issuer": settings.base_url,
            "authorization_endpoint": f"{settings.base_url}/oauth/authorize",
            "token_endpoint": f"{settings.base_url}/oauth/token",
            "registration_endpoint": f"{settings.base_url}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
                "none",
            ],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["people", "services"],
        }

    # Protected Resource Metadata (RFC 9728)
    def _protected_resource_metadata() -> dict:
        return {
            "resource": f"{settings.base_url}/mcp",
            "authorization_servers": [settings.base_url],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["people", "services"],
        }

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/oauth-authorization-server/mcp")
    async def oauth_metadata() -> JSONResponse:
        return JSONResponse(_auth_server_metadata())

    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    async def protected_resource_metadata() -> JSONResponse:
        return JSONResponse(_protected_resource_metadata())

    app.include_router(oauth_router, prefix="/oauth")

    # Web routes (Task 14)
    from pco_mcp.web.routes import router as web_router  # noqa: PLC0415
    app.include_router(web_router)

    wrapped_mcp = BearerTokenMiddleware(
        mcp_app,
        session_factory=session_factory,
        token_encryption_key=settings.token_encryption_key,
        pco_client_id=settings.pco_client_id,
        pco_client_secret=settings.pco_client_secret,
        pco_api_base=settings.pco_api_base,
        base_url=settings.base_url,
    )
    app.mount("/mcp", wrapped_mcp)

    return app
