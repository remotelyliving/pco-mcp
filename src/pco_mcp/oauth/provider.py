import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_registered_clients: dict[str, dict[str, Any]] = {}
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


def create_oauth_router(
    session_factory: async_sessionmaker[AsyncSession],
    pco_client_id: str,
    pco_client_secret: str,
    base_url: str,
    token_encryption_key: str,
    templates: Jinja2Templates | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201)
    async def register_client(request: Request) -> JSONResponse:
        """Dynamic Client Registration (RFC 7591) for ChatGPT."""
        body = await request.json()
        redirect_uris = body.get("redirect_uris")
        if not redirect_uris:
            raise HTTPException(status_code=400, detail="redirect_uris required")

        client_id = secrets.token_urlsafe(32)
        client_secret = secrets.token_urlsafe(48)
        _registered_clients[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": redirect_uris,
        }
        logger.info("Client registered (client_id=%s, redirect_uris=%s)", client_id, redirect_uris)
        return JSONResponse(
            content={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": redirect_uris,
            },
            status_code=201,
        )

    @router.get("/authorize")
    async def authorize(
        client_id: str = Query(...),
        redirect_uri: str = Query(...),
        response_type: str = Query(...),
        state: str = Query(""),
        code_challenge: str = Query(""),
        code_challenge_method: str = Query(""),
    ) -> RedirectResponse:
        """Authorization endpoint. Chains into PCO OAuth flow."""
        # C5: Validate redirect_uri against registered client.
        # Allow unregistered client_ids through — ChatGPT may hit /authorize before /register.
        if client_id in _registered_clients:
            registered = _registered_clients[client_id]
            if redirect_uri not in registered["redirect_uris"]:
                raise HTTPException(
                    status_code=400, detail="redirect_uri not registered for client"
                )

        internal_state = secrets.token_urlsafe(32)
        _pending_auth_codes[internal_state] = {
            "chatgpt_client_id": client_id,
            "chatgpt_redirect_uri": redirect_uri,
            "chatgpt_state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }

        pco_auth_url = (
            f"https://api.planningcenteronline.com/oauth/authorize"
            f"?client_id={pco_client_id}"
            f"&redirect_uri={base_url}/oauth/pco-callback"
            f"&response_type=code"
            f"&scope=people+services"
            f"&state={internal_state}"
        )
        logger.info(
            "Authorization redirect initiated (client_id=%s, internal_state=%s)",
            client_id,
            internal_state,
        )
        return RedirectResponse(url=pco_auth_url)

    @router.get("/pco-callback")
    async def pco_callback(
        code: str = Query(""),
        state: str = Query(""),
        error: str = Query(""),
    ) -> RedirectResponse:
        """Handle PCO OAuth callback, exchange code, issue our own code to ChatGPT."""
        if error:
            logger.error("PCO OAuth callback error (state=%s, error=%s)", state, error)
            if templates is not None:
                return templates.TemplateResponse(
                    request,
                    "error.html",
                    {"message": "We couldn't connect to your Planning Center account. Please try again."},
                    status_code=400,
                )
            raise HTTPException(status_code=400, detail=f"PCO auth error: {error}")

        pending = _pending_auth_codes.pop(state, None)
        if not pending:
            logger.warning("Invalid or expired OAuth state received (state=%s)", state)
            if templates is not None:
                return templates.TemplateResponse(
                    request,
                    "error.html",
                    {"message": "Your session expired. Please start over."},
                    status_code=400,
                )
            raise HTTPException(status_code=400, detail="Invalid or expired state")

        from pco_mcp.oauth.pco_client import exchange_pco_code

        pco_tokens = await exchange_pco_code(
            code=code,
            client_id=pco_client_id,
            client_secret=pco_client_secret,
            redirect_uri=f"{base_url}/oauth/pco-callback",
        )

        from sqlalchemy import select

        from pco_mcp.crypto import encrypt_token  # noqa: PLC0415
        from pco_mcp.models import User  # noqa: PLC0415

        async with session_factory() as db:
            from pco_mcp.oauth.pco_client import get_pco_me

            me = await get_pco_me(pco_tokens["access_token"])

            result = await db.execute(
                select(User).where(User.pco_person_id == me["id"])
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    pco_person_id=me["id"],
                    pco_org_name=me.get("org_name"),
                    pco_access_token_enc=encrypt_token(
                        pco_tokens["access_token"], token_encryption_key
                    ),
                    pco_refresh_token_enc=encrypt_token(
                        pco_tokens["refresh_token"], token_encryption_key
                    ),
                    pco_token_expires_at=datetime.now(UTC)
                    + timedelta(seconds=pco_tokens.get("expires_in", 7200)),
                )
                db.add(user)
            else:
                user.pco_access_token_enc = encrypt_token(
                    pco_tokens["access_token"], token_encryption_key
                )
                user.pco_refresh_token_enc = encrypt_token(
                    pco_tokens["refresh_token"], token_encryption_key
                )
                user.pco_token_expires_at = datetime.now(UTC) + timedelta(
                    seconds=pco_tokens.get("expires_in", 7200)
                )
            await db.commit()
            await db.refresh(user)

        # Direct flow: redirect to dashboard with a short-lived token
        if pending.get("flow") == "direct":
            dashboard_token = secrets.token_urlsafe(32)
            _pending_auth_codes[dashboard_token] = {
                "user_id": str(user.id),
                "org_name": user.pco_org_name,
                "type": "dashboard_token",
            }
            logger.info("Direct flow: redirecting user %s to dashboard", user.id)
            return RedirectResponse(url=f"{base_url}/dashboard?token={dashboard_token}")

        # ChatGPT flow: issue auth code and redirect back to ChatGPT
        our_code = secrets.token_urlsafe(48)
        _pending_auth_codes[our_code] = {
            "user_id": str(user.id),
            "chatgpt_client_id": pending["chatgpt_client_id"],
            "code_challenge": pending["code_challenge"],
            "type": "auth_code",
        }
        logger.info(
            "PCO callback complete — auth code issued (user_id=%s, org=%s)",
            user.id,
            user.pco_org_name,
        )

        redirect = (
            f"{pending['chatgpt_redirect_uri']}"
            f"?code={our_code}"
            f"&state={pending['chatgpt_state']}"
        )
        return RedirectResponse(url=redirect)

    @router.post("/token")
    async def token(
        grant_type: str = Form(...),
        code: str = Form(""),
        redirect_uri: str = Form(""),
        client_id: str = Form(""),
        client_secret: str = Form(""),
        refresh_token: str = Form(""),
        code_verifier: str = Form(""),
    ) -> JSONResponse:
        """Token endpoint. Exchanges auth codes for access tokens."""
        if grant_type == "authorization_code":
            # C4: Validate client credentials
            registered = _registered_clients.get(client_id)
            if registered is None:
                raise HTTPException(status_code=401, detail="Unknown client_id")
            if not secrets.compare_digest(client_secret, registered["client_secret"]):
                raise HTTPException(status_code=401, detail="Invalid client_secret")

            pending = _pending_auth_codes.pop(code, None)
            if not pending or pending.get("type") != "auth_code":
                logger.warning("Invalid authorization code presented at /token")
                raise HTTPException(status_code=400, detail="Invalid authorization code")

            # C3: Verify PKCE code_verifier if a code_challenge was stored
            stored_challenge = pending.get("code_challenge", "")
            if stored_challenge:
                if not code_verifier:
                    raise HTTPException(status_code=400, detail="code_verifier required")
                verifier_hash = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).rstrip(b"=").decode()
                if not secrets.compare_digest(verifier_hash, stored_challenge):
                    raise HTTPException(status_code=400, detail="Invalid code_verifier")

            access_token = secrets.token_urlsafe(48)
            new_refresh_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(access_token.encode()).hexdigest()
            rt_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()

            import uuid

            from pco_mcp.models import OAuthSession

            async with session_factory() as db:
                session = OAuthSession(
                    user_id=uuid.UUID(pending["user_id"]),
                    chatgpt_access_token_hash=token_hash,
                    refresh_token_hash=rt_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                db.add(session)
                await db.commit()

            logger.info(
                "Access token issued (user_id=%s, client_id=%s)",
                pending["user_id"],
                pending["chatgpt_client_id"],
            )
            return JSONResponse(
                content={
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": 86400,
                    "refresh_token": new_refresh_token,
                }
            )

        if grant_type == "refresh_token":
            # C2: Validate refresh token, rotate session
            if not refresh_token:
                raise HTTPException(status_code=400, detail="refresh_token required")

            rt_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

            from sqlalchemy import select

            from pco_mcp.models import OAuthSession

            async with session_factory() as db:
                result = await db.execute(
                    select(OAuthSession).where(OAuthSession.refresh_token_hash == rt_hash)
                )
                old_session = result.scalar_one_or_none()
                if old_session is None:
                    raise HTTPException(status_code=401, detail="Invalid refresh_token")

                user_id = old_session.user_id

                # Delete old session (token rotation)
                await db.delete(old_session)

                # Issue new tokens
                new_access_token = secrets.token_urlsafe(48)
                new_rt = secrets.token_urlsafe(48)
                new_token_hash = hashlib.sha256(new_access_token.encode()).hexdigest()
                new_rt_hash = hashlib.sha256(new_rt.encode()).hexdigest()

                new_session = OAuthSession(
                    user_id=user_id,
                    chatgpt_access_token_hash=new_token_hash,
                    refresh_token_hash=new_rt_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                db.add(new_session)
                await db.commit()

            return JSONResponse(
                content={
                    "access_token": new_access_token,
                    "token_type": "bearer",
                    "expires_in": 86400,
                    "refresh_token": new_rt,
                }
            )

        logger.warning("Unsupported grant_type received: %s", grant_type)
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")

    return router
