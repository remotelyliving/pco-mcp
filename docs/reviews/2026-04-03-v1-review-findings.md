# pco-mcp v1 Review Findings

**Date:** 2026-04-03
**Reviewers:** Senior Engineer (opus), SRE, Security, UX
**Baseline:** 117 tests, 97% coverage, 0 mypy/ruff/bandit errors

---

## Critical (blocks production)

### C1. No bearer token resolution middleware
**Flagged by:** SRE, Sr. Eng, Security
`set_pco_client()` is never called in the production code path. MCP tools will raise `LookupError` on every real request. Need middleware that: reads bearer token from request -> hashes it -> looks up `OAuthSession` -> finds `User` -> decrypts PCO token -> creates `PCOClient` -> calls `set_pco_client()`.

### C2. Refresh token grant is a no-op
**Flagged by:** Sr. Eng, Security
Accepts any string, no DB validation, doesn't create `OAuthSession`, doesn't persist the new access token. After first token expires, ChatGPT gets a useless token.

### C3. PKCE accepted but never verified
**Flagged by:** Security
`code_challenge` stored but `code_verifier` never checked at `/oauth/token`. OAuth 2.1 mandates PKCE.

### C4. OAuth client credentials never validated at token endpoint
**Flagged by:** Security
`client_id`/`client_secret` from `/oauth/register` never checked during code exchange. Any code interceptor can exchange.

### C5. Open redirect in `/oauth/authorize`
**Flagged by:** Security
`redirect_uri` never validated against registered URIs. Attacker can redirect auth codes to evil.com.

### C6. `/auth/start` and `/dashboard` routes don't exist
**Flagged by:** UX
"Get Started" button 404s. Dashboard template exists but no route renders it. User flow is completely broken.

---

## Important (should fix for v1)

### I1. No logging anywhere
**Flagged by:** SRE
Zero uses of `logging` in all of `src/`. No observability.

### I2. In-memory OAuth state lost on restart, no expiry
**Flagged by:** SRE, Sr. Eng, Security
`_registered_clients` and `_pending_auth_codes` are plain dicts. Lost on deploy/restart. No TTL — memory leak.

### I3. No HTTP timeouts on outbound calls
**Flagged by:** SRE, Security
All httpx clients use defaults. Hung PCO API = hung workers.

### I4. `update_person` drops email parameter
**Flagged by:** UX, SRE, Sr. Eng
`email` accepted but never added to `fields` dict. Silently discarded.

### I5. Missing `confirmationHint: true` on write annotations
**Flagged by:** Sr. Eng
Spec requires it. ChatGPT won't prompt for confirmation before writes.

### I6. `search_people` email/phone parameter collision
**Flagged by:** SRE, Sr. Eng
Both set `where[search_name_or_email]`. Phone silently overwrites email.

### I7. Token refresh never called — PCO tokens expire silently
**Flagged by:** SRE
`refresh_pco_token` exists but is dead code. After 2h tokens expire with no recovery.

### I8. Health check doesn't validate DB
**Flagged by:** SRE
Returns healthy even if DB is down.

### I9. No `pool_pre_ping` on SQLAlchemy engine
**Flagged by:** SRE
Stale connections will error instead of recycling.

### I10. No Alembic initial migration, hardcoded DB URL
**Flagged by:** SRE, Sr. Eng
`create_all` in lifespan, empty versions dir, localhost URL in alembic.ini.

### I11. OAuth errors are raw JSON, not human-readable pages
**Flagged by:** UX
Non-technical users see JSON 400 responses during auth failures.

### I12. "MCP" jargon on user-facing pages
**Flagged by:** UX
Church staff won't know what MCP means.

### I13. Missing security headers on HTML routes
**Flagged by:** Security
No CSP, X-Frame-Options, X-Content-Type-Options.

### I14. `WRITE_ANNOTATIONS` duplicated across two files
**Flagged by:** Sr. Eng
Should be in `tools/__init__.py`.

### I15. PCO error reflected verbatim in HTTP response
**Flagged by:** Security
`f"PCO auth error: {error}"` reflects external input.

### I16. `secret_key` loaded but never used
**Flagged by:** Security
Dead config value. Remove or use.

### I17. `last_used_at` never updated
**Flagged by:** Security, SRE
Set at creation, never touched again.

### I18. Test conftest key is not valid Fernet key
**Flagged by:** Security, Sr. Eng
Will break any future test that round-trips through encryption.
