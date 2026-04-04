# src/pco_mcp/main.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from pco_mcp.config import Settings
from pco_mcp.db import create_engine, create_session_factory
from pco_mcp.models import Base
from pco_mcp.oauth.provider import create_oauth_router
from pco_mcp.tools.people import register_people_tools
from pco_mcp.tools.services import register_services_tools


def create_app() -> FastAPI:
    """Create and wire the full application."""
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

    oauth_router = create_oauth_router(
        session_factory=session_factory,
        pco_client_id=settings.pco_client_id,
        pco_client_secret=settings.pco_client_secret,
        base_url=settings.base_url,
        token_encryption_key=settings.token_encryption_key,
        secret_key=settings.secret_key,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async with mcp_app.lifespan(mcp_app):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            yield
            await engine.dispose()

    app = FastAPI(title="pco-mcp", lifespan=lifespan)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    app.include_router(oauth_router, prefix="/oauth")

    # Web routes (Task 14)
    from pco_mcp.web.routes import router as web_router  # noqa: PLC0415
    app.include_router(web_router)

    app.mount("/mcp", mcp_app)

    return app
