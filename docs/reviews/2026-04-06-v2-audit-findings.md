# pco-mcp v2 Audit Findings

**Date:** 2026-04-06
**Reviewers:** Security (opus), SRE (opus), Code Quality (opus)
**Baseline:** 219 tests, 94.5% coverage, 25 MCP tools

## All findings resolved in this cycle:

### Tier 1 — Security (DONE)
- [x] C2: redirect_uri validation
- [x] C4: Auth code bound to client_id at exchange
- [x] I1: PKCE verification implemented
- [x] I2: Explicit 401 on expired tokens
- [x] I3: client_credentials grant rejected

### Tier 2 — Stability (DONE)
- [x] C1: DB-backed token persistence (models/crypto wired up)
- [x] C2: PCOClient resource leak fixed (shared httpx client)
- [x] I2: In-memory dict cleanup (5-min sweep task)
- [x] I5: Tool errors wrapped with safe_tool_call + map_pco_error
- [x] I5: PCO token refresh in auth middleware

### Tier 3 — Code Quality (DONE)
- [x] DRY annotations (tools/__init__.py)
- [x] Settings() re-creation fixed (lru_cache + Depends)
- [x] _context.py hardcoded URL fixed (configure() from settings)
- [x] Bare Exception replaced with PCOOAuthError
- [x] URL construction uses urlencode
- [x] Delete tools return {"status": "removed"}
- [x] Unused pco_rate_limit_buffer removed
- [x] Docker runs as non-root user

### Post-fix stats
- 269 tests, 96% coverage
- 25 MCP tools, all with proper error handling
- DB persistence survives restarts
- PKCE, redirect validation, auth code binding all enforced
