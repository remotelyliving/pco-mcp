# pco-mcp

A hosted MCP server that connects ChatGPT (and other MCP clients) to [Planning Center Online](https://www.planningcenteronline.com/) data. Turnkey for non-technical church staff -- no API keys, no terminal, no config files.

## How It Works

1. User visits the landing page and clicks "Get Started"
2. Redirected to PCO's OAuth consent screen to grant access
3. Redirected back with a unique MCP endpoint URL
4. Paste the URL into ChatGPT (Settings > Apps > Create)
5. Done -- ChatGPT can now query and manage their PCO data

Token refresh is automatic. The server handles dual OAuth (ChatGPT <-> pco-mcp <-> Planning Center) transparently.

## Architecture

```
[ChatGPT / MCP Client] --Streamable HTTP--> [pco-mcp server]
                                                  |
                                            [OAuth 2.1 layer]
                                                  |
                                            [PCO API client]
                                                  |
                                            [Planning Center API]
```

- **Python 3.12+** with [FastMCP](https://github.com/jlowin/fastmcp) for the MCP protocol
- **FastAPI** for the web UI and OAuth endpoints
- **httpx** for async HTTP to the PCO API
- **PostgreSQL** for user tokens and sessions (encrypted at rest via Fernet)

Single deployable -- one app handles the landing page, OAuth flows, MCP protocol, and PCO API proxying.

## Tools (58)

### Services (34 tools)

Plan management, team scheduling, song library, arrangements, attachments, media, and CCLI compliance.

| Tool | Type | Description |
|------|------|-------------|
| `list_service_types` | READ | List all service types (Sunday Morning, Wednesday Night, etc.) |
| `get_upcoming_plans` | READ | Get future plans for a service type |
| `get_plan_details` | READ | Full plan with songs, items, team assignments |
| `list_plan_items` | READ | Ordered items (songs/elements) in a plan |
| `list_plan_templates` | READ | Saved plan templates for a service type |
| `list_songs` | READ | Search/list songs in the library |
| `get_song` | READ | Full song detail (title, author, copyright, CCLI, themes) |
| `list_song_arrangements` | READ | Arrangements for a song (BPM, meter, key) |
| `get_song_schedule_history` | READ | When a song was last scheduled |
| `list_teams` | READ | Teams for a service type |
| `list_team_positions` | READ | Positions within a team |
| `list_team_members` | READ | Team members and positions for a plan |
| `get_needed_positions` | READ | Unfilled positions for a plan |
| `list_attachments` | READ | File attachments on an arrangement |
| `list_media` | READ | Org-level media items (backgrounds, countdowns) |
| `get_ccli_reporting` | READ | CCLI usage counts for a plan item |
| `get_song_usage_report` | READ | All dates a song was scheduled (for CCLI reporting) |
| `flag_missing_ccli` | READ | Scan library for songs missing CCLI numbers |
| `create_plan` | WRITE | Create a new service plan |
| `create_plan_time` | WRITE | Add a service/rehearsal time to a plan |
| `create_service_type` | WRITE | Create a new service type |
| `create_song` | WRITE | Create a song in the library |
| `update_song` | WRITE | Update song metadata (title, author, CCLI, etc.) |
| `create_arrangement` | WRITE | Create arrangement with lyrics/chords (ChordPro) |
| `update_arrangement` | WRITE | Update arrangement metadata, lyrics, key |
| `create_attachment` | WRITE | Upload file to an arrangement (PDF, MP3, etc.) |
| `create_media` | WRITE | Upload org-level media (background, countdown) |
| `update_media` | WRITE | Update media title, themes, creator |
| `add_item_to_plan` | WRITE | Add a song or element to a plan |
| `schedule_team_member` | WRITE | Schedule a person to a team position |
| `delete_song` | DESTRUCTIVE | Delete a song and all arrangements/attachments |
| `delete_arrangement` | DESTRUCTIVE | Delete an arrangement |
| `remove_item_from_plan` | DESTRUCTIVE | Remove an item from a plan |
| `remove_team_member` | DESTRUCTIVE | Remove a person from a plan's team |

### People (19 tools)

People search, contact details, notes, blockouts, and workflows.

| Tool | Type | Description |
|------|------|-------------|
| `search_people` | READ | Search by name, email, or phone |
| `get_person` | READ | Full person detail (name, membership, status) |
| `list_lists` | READ | All PCO lists (smart groups, tags) |
| `get_list_members` | READ | People in a specific list |
| `get_person_blockouts` | READ | Blockout/unavailability dates |
| `list_person_details` | READ | All contact info (emails, phones, addresses) in one call |
| `list_notes` | READ | Notes on a person's record |
| `list_workflows` | READ | All workflows (New Member Follow-up, etc.) |
| `create_person` | WRITE | Create a new person record |
| `update_person` | WRITE | Update person fields |
| `add_email` | WRITE | Add an email address |
| `update_email` | WRITE | Update an email address |
| `add_phone_number` | WRITE | Add a phone number |
| `update_phone_number` | WRITE | Update a phone number |
| `add_address` | WRITE | Add a mailing address |
| `update_address` | WRITE | Update an address |
| `add_note` | WRITE | Add a pastoral/admin note |
| `add_blockout` | WRITE | Create a blockout date |
| `add_person_to_workflow` | WRITE | Add a person to a workflow |

### Check-ins (3 tools)

Read-only attendance and headcount data for service planning.

| Tool | Type | Description |
|------|------|-------------|
| `list_checkin_events` | READ | List check-in event definitions |
| `get_event_attendance` | READ | Attendance records with date filtering |
| `get_headcounts` | READ | Headcount totals and per-location breakdown |

### Calendar (2 tools)

Read-only calendar events and resource bookings for conflict avoidance.

| Tool | Type | Description |
|------|------|-------------|
| `list_calendar_events` | READ | Upcoming events with date range filtering |
| `get_event_details` | READ | Event detail with room/resource bookings |

## Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Setup

```bash
git clone https://github.com/remotelyliving/pco-mcp.git
cd pco-mcp
uv sync --dev
```

### Running Tests

```bash
uv run pytest tests/ -v
```

Coverage target is 90%+:

```bash
uv run pytest tests/ --cov=pco_mcp --cov-report=term-missing
```

### Linting and Type Checking

```bash
uv run ruff check src/
uv run mypy src/ --ignore-missing-imports
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `PCO_CLIENT_ID` | Yes | PCO OAuth app client ID |
| `PCO_CLIENT_SECRET` | Yes | PCO OAuth app client secret |
| `TOKEN_ENCRYPTION_KEY` | Yes | Fernet key for encrypting stored tokens |
| `BASE_URL` | Yes | Public URL of the deployed server |
| `PCO_API_BASE` | No | PCO API base URL (default: `https://api.planningcenteronline.com`) |
| `TOKEN_EXPIRY_HOURS` | No | Token lifetime in hours (default: 24) |
| `DEBUG` | No | Enable debug mode (default: false) |

### Project Structure

```
src/pco_mcp/
  pco/              # PCO API client wrappers
    client.py       # HTTP client with auth, pagination, rate limiting
    services.py     # ServicesAPI (plans, songs, teams, media, CCLI)
    people.py       # PeopleAPI (contacts, notes, blockouts, workflows)
    checkins.py     # CheckInsAPI (events, attendance, headcounts)
    calendar.py     # CalendarAPI (events, resources)
  tools/            # MCP tool registration
    services.py     # 34 Services tools
    people.py       # 19 People tools
    checkins.py     # 3 Check-ins tools
    calendar.py     # 2 Calendar tools
    _context.py     # Dependency injection (token -> client -> API)
  oauth/            # OAuth provider implementation
  web/              # Landing page and setup wizard
  auth.py           # Dual OAuth flow orchestration
  config.py         # Environment-based settings
  main.py           # FastMCP + FastAPI app factory
```

## Security

- PCO tokens encrypted at rest (Fernet)
- OAuth 2.1 with PKCE for ChatGPT integration
- OAuth state parameter validation (CSRF protection)
- Write operations annotated with `confirmationHint: true`
- Destructive operations annotated with `destructiveHint: true`
- Token scoping: each session can only access its own PCO data
- No credentials in code -- all secrets via environment variables

## Deployment

Designed for [Railway](https://railway.app/):

- PostgreSQL addon for token storage
- GitHub push to `main` triggers deploy
- HTTPS provided by Railway
- Custom domain support

## License

Private -- not open source.
