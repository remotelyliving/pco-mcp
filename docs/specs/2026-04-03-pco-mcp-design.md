# pco-mcp Design Spec

**Date:** 2026-04-03
**Status:** Draft
**Goal:** A hosted MCP server that lets ChatGPT (and other MCP clients) query and interact with Planning Center Online data. Turnkey for non-technical church staff.

---

## 1. User Journey & Onboarding

1. User visits the pco-mcp landing page ("Connect ChatGPT to your Planning Center data")
2. Clicks "Get Started" — redirected to PCO's OAuth consent screen
3. Logs into their PCO account, grants access
4. Redirected back — shown their unique MCP endpoint URL + copy button
5. Simple visual instructions: "Open ChatGPT > Settings > Apps > Create > Paste this URL"
6. Done. ChatGPT can now query their PCO data.

No API keys, no terminal, no JSON editing, no config files. Token refresh is automatic.

---

## 2. Architecture

```
[ChatGPT] --HTTPS/Streamable HTTP--> [pco-mcp server on Railway]
                                          |
                                    [OAuth 2.1 layer]
                                          |
                                    [PCO API client]
                                          |
                                    [Planning Center API]
```

**Stack:**
- Python 3.12+
- FastMCP (MCP framework with Streamable HTTP transport)
- httpx (async HTTP client for PCO API calls)
- PostgreSQL on Railway (user tokens, sessions)
- Jinja2 or simple HTML for landing page + setup wizard

**Single deployable:** One Python app handles the landing page, OAuth flows, MCP protocol, and PCO API proxying.

---

## 3. Authentication — Dual OAuth

Two separate OAuth flows are needed:

### 3a. ChatGPT <-> pco-mcp (OAuth 2.1)
ChatGPT mandates OAuth 2.1 with Dynamic Client Registration for MCP servers. The pco-mcp server acts as an OAuth provider from ChatGPT's perspective:
- Implements `/oauth/authorize`, `/oauth/token`, `/oauth/register` endpoints
- When ChatGPT hits `/oauth/authorize`, pco-mcp chains into the PCO OAuth flow — the user sees PCO's login screen, not a separate pco-mcp login. On callback, pco-mcp stores the PCO tokens and issues its own access token back to ChatGPT.
- Issues access tokens that map to a PCO user session
- ChatGPT handles token refresh automatically

### 3b. pco-mcp <-> Planning Center (OAuth 2.0)
Standard PCO OAuth 2.0 Authorization Code flow:
- Register pco-mcp as an OAuth app in PCO developer portal (one-time setup by us)
- Users authorize during onboarding — we store their PCO access + refresh tokens
- Auto-refresh PCO tokens before expiry

**Token storage:** PostgreSQL table mapping `pco_mcp_user_id -> pco_access_token, pco_refresh_token, pco_org_id, expires_at`. Tokens encrypted at rest.

---

## 4. MCP Tools — v1 Scope

### People Module
| Tool | Type | Description |
|------|------|-------------|
| `search_people` | read | Search by name, email, phone. Returns list with basic info. |
| `get_person` | read | Get full details for a person by ID. |
| `list_lists` | read | Get all PCO Lists (smart groups, tags). |
| `get_list_members` | read | Get people in a specific list. |
| `create_person` | write | Create a new person record. Requires confirmation annotation. |
| `update_person` | write | Update fields on an existing person. Requires confirmation annotation. |

### Services Module
| Tool | Type | Description |
|------|------|-------------|
| `list_service_types` | read | List all service types (e.g., "Sunday Morning", "Wednesday Night"). |
| `get_upcoming_plans` | read | Get upcoming service plans for a service type. |
| `get_plan_details` | read | Get full plan details (songs, items, team, times). |
| `list_songs` | read | Search/list songs in the library. |
| `list_team_members` | read | List team members and their positions for a plan. |
| `schedule_team_member` | write | Schedule a person to a team position. Requires confirmation. |

### Tool Annotations
All write tools include MCP tool annotations:
- `readOnlyHint: false`
- `destructiveHint: false` (creates/updates, not deletes — no delete tools in v1)
- `confirmationHint: true` — signals to ChatGPT that user confirmation is needed before execution

All read tools include:
- `readOnlyHint: true`

---

## 5. PCO API Client Layer

A thin wrapper around `httpx` that handles:
- **Base URL construction:** `https://api.planningcenteronline.com/{module}/v2/{resource}`
- **Authentication:** Injects the user's PCO OAuth Bearer token
- **Rate limiting:** Reads `X-PCO-API-Request-Rate-Count` and `X-PCO-API-Request-Rate-Limit` headers. Backs off with `Retry-After` on 429s.
- **Pagination:** PCO uses JSON:API pagination (`?per_page=25&offset=0`). The client auto-paginates when a tool needs all results (with a configurable max).
- **Error mapping:** Translates PCO HTTP errors into human-readable MCP tool errors:
  - 401 -> "Your Planning Center session has expired. Please reconnect at [URL]."
  - 403 -> "You don't have permission to access this in Planning Center."
  - 404 -> "That record wasn't found in Planning Center."
  - 429 -> "Planning Center is rate-limiting requests. Please wait a moment and try again."
  - 5xx -> "Planning Center is temporarily unavailable. Please try again shortly."

---

## 6. Database Schema

PostgreSQL with 2 tables for v1:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pco_person_id BIGINT UNIQUE NOT NULL,
    pco_org_name TEXT,
    pco_access_token_enc BYTEA NOT NULL,
    pco_refresh_token_enc BYTEA NOT NULL,
    pco_token_expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE oauth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    chatgpt_access_token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Token encryption using Fernet (from `cryptography` library) with a server-side key stored as an environment variable.

---

## 7. Landing Page & Setup Wizard

A minimal web UI served by the same Python app:

- **`/`** — Landing page. "Connect ChatGPT to Planning Center" with a "Get Started" button.
- **`/auth/start`** — Initiates PCO OAuth flow (redirects to PCO).
- **`/auth/callback`** — Handles PCO OAuth callback, stores tokens, shows success page.
- **`/dashboard`** — Shows the user's MCP endpoint URL, connection status, and "Disconnect" button.
- **`/setup-guide`** — Step-by-step visual guide for adding the URL to ChatGPT (with screenshots).

No JavaScript framework. Plain HTML + minimal CSS (Pico CSS or similar classless framework for clean styling with zero effort).

---

## 8. Error Handling

All errors returned to ChatGPT are plain-English, actionable messages. Never expose stack traces, internal IDs, or technical details.

**Error categories:**
- **Auth errors:** Guide user to reconnect ("Your session expired. Visit [URL] to reconnect.")
- **Permission errors:** Explain what permission is needed in PCO
- **Not found:** Clear message about what wasn't found
- **Rate limits:** Ask to wait and retry
- **Server errors:** Apologize and suggest retrying

---

## 9. Security

- PCO tokens encrypted at rest (Fernet)
- Encryption key in environment variable, never in code
- HTTPS enforced (Railway provides this)
- No delete operations in v1
- Write operations annotated with `confirmationHint: true`
- OAuth state parameter validated to prevent CSRF
- Token scoping: each user's ChatGPT session can only access their own PCO data
- Automatic token expiry and cleanup

---

## 10. Deployment

- **Platform:** Railway
- **Database:** Railway PostgreSQL addon
- **Domain:** Custom domain via Railway (e.g., `pco-mcp.com` or similar)
- **Environment variables:** `DATABASE_URL`, `PCO_CLIENT_ID`, `PCO_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `SECRET_KEY`
- **CI/CD:** GitHub push to `main` triggers Railway deploy
- **Monitoring:** Railway built-in logs + metrics. Add Sentry for error tracking in v2.

---

## 11. Testing Strategy

- **Unit tests:** Each MCP tool function tested with mocked PCO API responses
- **Integration tests:** OAuth flow tested end-to-end with PCO sandbox (if available) or recorded HTTP fixtures
- **MCP protocol tests:** Verify tool discovery, schema validation, and error responses using the MCP SDK test client
- **Target:** 80%+ code coverage for v1

---

## 12. Future Expansion (Not in v1)

- Additional PCO modules: Check-Ins, Giving, Groups, Calendar
- Claude Desktop support via MCPB (.dxt) packaging
- Multi-client support (Cursor, VS Code, etc.)
- Webhook subscriptions for real-time PCO data changes
- Usage analytics dashboard
- Rate limit pooling per organization
