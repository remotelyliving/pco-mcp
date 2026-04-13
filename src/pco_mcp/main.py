# src/pco_mcp/main.py
"""Application factory.

Implements the OAuth layer as plain FastAPI routes (matching the proven
ChatGPT-compatible pattern from adamgivon/chatgpt-custom-mcp-for-local-files)
and mounts the FastMCP transport separately at /mcp.
"""
import asyncio
import base64
import hashlib
import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastmcp import FastMCP
from sqlalchemy import select, text

from pco_mcp.auth import inject_pco_bearer
from pco_mcp.config import Settings
from pco_mcp.crypto import decrypt_token, encrypt_token
from pco_mcp.db import create_engine, create_session_factory
from pco_mcp.models import Base, OAuthSession, User
from pco_mcp.oauth.pco_client import exchange_pco_code, get_pco_me
from pco_mcp.tools._context import close_shared_client
from pco_mcp.tools.checkins import register_checkins_tools
from pco_mcp.tools.people import register_people_tools
from pco_mcp.tools.services import register_services_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores (mirrors the working reference server exactly)
# ---------------------------------------------------------------------------
registered_clients: dict[str, dict[str, Any]] = {}
oauth_codes: dict[str, dict[str, Any]] = {}
oauth_tokens: dict[str, dict[str, Any]] = {}

PCO_AUTHORIZE_URL = "https://api.planningcenteronline.com/oauth/authorize"


def _hash_token(token: str) -> str:
    """SHA-256 hash of a bearer token for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _persist_session_to_db(
    *,
    session_factory: Any,
    settings: Settings,
    bearer_token: str,
    pco_access_token: str,
    pco_refresh_token: str,
    pco_token_expires: datetime,
    our_token_expires: datetime,
    pco_person_id: int,
    pco_org_name: str | None,
) -> None:
    """Create/update User and OAuthSession records in the database."""
    async with session_factory() as db:
        # Upsert User
        stmt = select(User).where(User.pco_person_id == pco_person_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                pco_person_id=pco_person_id,
                pco_org_name=pco_org_name,
                pco_access_token_enc=encrypt_token(pco_access_token, settings.token_encryption_key),
                pco_refresh_token_enc=encrypt_token(
                    pco_refresh_token or "", settings.token_encryption_key
                ),
                pco_token_expires_at=pco_token_expires,
            )
            db.add(user)
            await db.flush()
        else:
            user.pco_access_token_enc = encrypt_token(
                pco_access_token, settings.token_encryption_key
            )
            user.pco_refresh_token_enc = encrypt_token(
                pco_refresh_token or "", settings.token_encryption_key
            )
            user.pco_token_expires_at = pco_token_expires
            user.pco_org_name = pco_org_name
            user.last_used_at = datetime.now(UTC)

        # Create OAuthSession
        oauth_session = OAuthSession(
            user_id=user.id,
            chatgpt_access_token_hash=_hash_token(bearer_token),
            expires_at=our_token_expires,
        )
        db.add(oauth_session)
        await db.commit()
        logger.info(
            "Persisted session to DB for person_id=%s", pco_person_id
        )


def create_app() -> FastAPI:
    """Create and wire the full application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings()

    from pco_mcp.tools._context import configure as configure_context  # noqa: PLC0415

    configure_context(settings)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # Build FastMCP *without* auth — we handle OAuth ourselves
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
    register_checkins_tools(mcp)

    # The raw MCP transport app (no OAuth baked in)
    mcp_app = mcp.http_app(path="/mcp")

    async def _cleanup_expired() -> None:
        """Periodically sweep expired entries from in-memory OAuth stores."""
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            now = datetime.now(UTC)
            expired_codes = [k for k, v in oauth_codes.items() if v.get("expires", now) < now]
            for k in expired_codes:
                del oauth_codes[k]
            expired_tokens = [k for k, v in oauth_tokens.items() if v.get("expires", now) < now]
            for k in expired_tokens:
                del oauth_tokens[k]
            if expired_codes or expired_tokens:
                logger.info(
                    "Cleanup: removed %d codes, %d tokens",
                    len(expired_codes),
                    len(expired_tokens),
                )

    async def _reload_sessions_from_db() -> None:
        """On startup, reload active OAuth sessions from the database."""
        try:
            async with session_factory() as db:
                stmt = (
                    select(OAuthSession, User)
                    .join(User, OAuthSession.user_id == User.id)
                    .where(OAuthSession.expires_at > datetime.now(UTC))
                )
                result = await db.execute(stmt)
                count = 0
                for oauth_session, user in result:
                    pco_access = decrypt_token(
                        user.pco_access_token_enc, settings.token_encryption_key
                    )
                    pco_refresh = decrypt_token(
                        user.pco_refresh_token_enc, settings.token_encryption_key
                    )
                    # Reconstruct the in-memory token entry using the hash as key
                    # We can't recover the original bearer token, but we stored the hash.
                    # The middleware will check DB as fallback, so this is supplementary.
                    count += 1
                logger.info("Loaded %d active sessions from DB", count)
        except Exception:
            logger.warning("Could not reload sessions from DB (table may not exist yet)")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("pco-mcp starting up (base_url=%s)", settings.base_url)
        async with mcp_app.lifespan(mcp_app):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema ready")
            await _reload_sessions_from_db()
            cleanup_task = asyncio.create_task(_cleanup_expired())
            try:
                yield
            finally:
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
                await close_shared_client()
                await engine.dispose()
                logger.info("pco-mcp shut down")

    app = FastAPI(title="pco-mcp", lifespan=lifespan)

    # ------------------------------------------------------------------
    # Bearer-token middleware: resolves our access tokens to PCO tokens
    # and injects them into the request scope so FastMCP's
    # get_access_token() finds them in tools.
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def bearer_middleware(request: Request, call_next):  # type: ignore[misc]
        response = await inject_pco_bearer(
            request, call_next, oauth_tokens, session_factory, settings
        )
        # Security headers on every response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # ------------------------------------------------------------------
    # OAuth Discovery (matches working reference EXACTLY)
    # ------------------------------------------------------------------
    # Use settings.base_url (not request.base_url) because behind
    # Cloudflare tunnel, request.base_url is http:// not https://.
    # OAuth 2.1 requires HTTPS for all endpoints.
    base = settings.base_url.rstrip("/")

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/openid-configuration")
    async def oauth_discovery(request: Request) -> JSONResponse:
        return JSONResponse({
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "registration_endpoint": f"{base}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
            ],
        })

    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource(request: Request) -> JSONResponse:
        return JSONResponse({
            "resource": base,
            "authorization_servers": [base],
            "bearer_methods_supported": ["header"],
            "resource_documentation": base,
        })

    # ------------------------------------------------------------------
    # OAuth Register (DCR) — always returns client_secret
    # ------------------------------------------------------------------
    @app.post("/oauth/register")
    async def oauth_register(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        client_id = f"chatgpt-{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(48)

        registered_clients[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": body.get("redirect_uris", []),
            "client_name": body.get("client_name", "ChatGPT MCP"),
            "created_at": datetime.now(UTC),
        }
        logger.info("Registered new client: %s (%s)", client_id, body.get("client_name"))

        return JSONResponse(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "client_id_issued_at": int(datetime.now(UTC).timestamp()),
                "client_secret_expires_at": 0,
                "redirect_uris": body.get("redirect_uris", []),
                "token_endpoint_auth_method": "client_secret_post",
                "grant_types": ["authorization_code", "client_credentials"],
                "response_types": ["code"],
            },
            status_code=201,
        )

    # ------------------------------------------------------------------
    # OAuth Authorize — redirects to PCO OAuth (the upstream IDP)
    # ------------------------------------------------------------------
    @app.get("/oauth/authorize")
    async def oauth_authorize(
        client_id: str,
        redirect_uri: str,
        response_type: str = "code",
        state: str | None = None,
        scope: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> RedirectResponse:
        if client_id not in registered_clients:
            raise HTTPException(status_code=400, detail="Invalid client_id")

        client_data = registered_clients[client_id]
        if redirect_uris := client_data.get("redirect_uris"):
            if redirect_uri not in redirect_uris:
                raise HTTPException(status_code=400, detail="redirect_uri not registered for this client")

        # Generate a random internal state to track this flow
        internal_state = secrets.token_urlsafe(32)
        oauth_codes[internal_state] = {
            "type": "pending_pco_auth",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "chatgpt_state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        # Redirect to PCO OAuth
        base_url = settings.base_url.rstrip("/")
        pco_params = {
            "client_id": settings.pco_client_id,
            "redirect_uri": f"{base_url}/oauth/pco-callback",
            "response_type": "code",
            "scope": "people services",
            "state": internal_state,
        }
        pco_url = f"{PCO_AUTHORIZE_URL}?{urlencode(pco_params)}"
        return RedirectResponse(url=pco_url, status_code=302)

    # ------------------------------------------------------------------
    # PCO Callback — exchanges PCO code, generates our auth code
    # ------------------------------------------------------------------
    @app.get("/oauth/pco-callback")
    async def oauth_pco_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> RedirectResponse:
        if error:
            raise HTTPException(status_code=400, detail=f"PCO OAuth error: {error}")
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")

        pending = oauth_codes.pop(state, None)
        if not pending or pending.get("type") not in (
            "pending_pco_auth",
            "pending_direct_auth",
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        if pending["expires"] < datetime.now(UTC):
            raise HTTPException(status_code=400, detail="Authorization request expired")

        # Exchange PCO auth code for PCO tokens
        base_url = settings.base_url.rstrip("/")
        pco_tokens = await exchange_pco_code(
            code=code,
            client_id=settings.pco_client_id,
            client_secret=settings.pco_client_secret,
            redirect_uri=f"{base_url}/oauth/pco-callback",
        )

        pco_access_token = pco_tokens["access_token"]
        pco_refresh_token = pco_tokens.get("refresh_token")

        # Fetch user info for logging / dashboard
        try:
            pco_me = await get_pco_me(pco_access_token)
            logger.info(
                "PCO auth complete for person_id=%s org=%s",
                pco_me.get("id"),
                pco_me.get("org_name"),
            )
        except Exception:
            pco_me = {}

        # --- Direct (non-ChatGPT) flow: redirect to dashboard ---
        if pending["type"] == "pending_direct_auth":
            from pco_mcp.oauth.provider import store_dashboard_token  # noqa: PLC0415

            dashboard_token = secrets.token_urlsafe(32)
            store_dashboard_token(dashboard_token, {
                "user_id": str(pco_me.get("id", "")),
                "org_name": pco_me.get("org_name"),
                "pco_access_token": pco_access_token,
            })
            return RedirectResponse(
                url=f"{base_url}/dashboard?token={dashboard_token}",
                status_code=302,
            )

        # --- ChatGPT flow: generate our auth code ---
        our_code = secrets.token_urlsafe(32)
        oauth_codes[our_code] = {
            "type": "auth_code",
            "client_id": pending["client_id"],
            "pco_access_token": pco_access_token,
            "pco_refresh_token": pco_refresh_token,
            "pco_me": pco_me,
            "code_challenge": pending.get("code_challenge"),
            "code_challenge_method": pending.get("code_challenge_method"),
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        # Redirect back to ChatGPT with our auth code
        redirect_uri = pending["redirect_uri"]
        redirect_url = f"{redirect_uri}?code={our_code}"
        if pending.get("chatgpt_state"):
            redirect_url += f"&state={pending['chatgpt_state']}"
        return RedirectResponse(url=redirect_url, status_code=302)

    # ------------------------------------------------------------------
    # OAuth Token — exchanges auth code for access token
    # ------------------------------------------------------------------
    @app.post("/oauth/token")
    async def oauth_token(
        grant_type: str = Form(...),
        client_id: str = Form(...),
        client_secret: str = Form(...),
        code: str | None = Form(None),
        refresh_token: str | None = Form(None),
        code_verifier: str | None = Form(None),
    ) -> JSONResponse:
        # Validate client
        if client_id not in registered_clients:
            raise HTTPException(status_code=401, detail="Invalid client")
        if client_secret != registered_clients[client_id]["client_secret"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if grant_type == "authorization_code":
            if not code or code not in oauth_codes:
                raise HTTPException(status_code=400, detail="Invalid code")
            code_data = oauth_codes.pop(code)
            if code_data.get("type") != "auth_code":
                raise HTTPException(status_code=400, detail="Invalid code")
            if code_data["expires"] < datetime.now(UTC):
                raise HTTPException(status_code=400, detail="Code expired")
            if code_data.get("client_id") != client_id:
                raise HTTPException(status_code=400, detail="Code was not issued to this client")

            # PKCE verification
            stored_challenge = code_data.get("code_challenge") or ""
            if stored_challenge:
                if not code_verifier:
                    raise HTTPException(status_code=400, detail="code_verifier required")
                computed = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).rstrip(b"=").decode()
                if not secrets.compare_digest(computed, stored_challenge):
                    raise HTTPException(status_code=400, detail="Invalid code_verifier")

            access_token = secrets.token_urlsafe(32)
            pco_token_expires = datetime.now(UTC) + timedelta(hours=2)
            oauth_tokens[access_token] = {
                "pco_access_token": code_data["pco_access_token"],
                "pco_refresh_token": code_data.get("pco_refresh_token"),
                "pco_token_expires": pco_token_expires,
                "pco_me": code_data.get("pco_me", {}),
                "expires": datetime.now(UTC) + timedelta(hours=1),
            }
            logger.info("Issued access token for client %s", client_id)

            # Persist to DB (best-effort, don't block response)
            pco_me = code_data.get("pco_me", {})
            pco_person_id = pco_me.get("id")
            if pco_person_id:
                try:
                    await _persist_session_to_db(
                        session_factory=session_factory,
                        settings=settings,
                        bearer_token=access_token,
                        pco_access_token=code_data["pco_access_token"],
                        pco_refresh_token=code_data.get("pco_refresh_token", ""),
                        pco_token_expires=pco_token_expires,
                        our_token_expires=oauth_tokens[access_token]["expires"],
                        pco_person_id=pco_person_id,
                        pco_org_name=pco_me.get("org_name"),
                    )
                except Exception:
                    logger.warning("Failed to persist session to DB", exc_info=True)

            return JSONResponse({
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 3600,
            })

        if grant_type == "client_credentials":
            raise HTTPException(
                status_code=400,
                detail="client_credentials grant not supported. Use authorization_code.",
            )

        raise HTTPException(status_code=400, detail="Unsupported grant type")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> JSONResponse:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "unhealthy", "db": "error"}, status_code=503)
        return JSONResponse({"status": "healthy"})

    # ------------------------------------------------------------------
    # Web routes (landing page, setup guide, dashboard)
    # ------------------------------------------------------------------
    from pco_mcp.web.routes import router as web_router  # noqa: PLC0415

    app.include_router(web_router)

    # Mount the MCP app (just transport, no OAuth)
    app.mount("/", mcp_app)

    return app
