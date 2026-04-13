# Check-ins (Read-only) — MCP Tool Design Spec

**Date:** 2026-04-13
**Sub-project:** 3 of 4 (Check-ins)
**Goal:** Surface attendance and headcount data for service planning. Read-only — no check-in creation or event management.

---

## Context

Historical attendance data is valuable for planning: knowing typical Sunday attendance helps with volunteer scheduling, room setup, and resource planning. The PCO Check-ins API provides event listings, individual attendance records, and headcount aggregates.

**PCO API base:** `https://api.planningcenteronline.com/check-ins/v2`

---

## New Tools (3)

#### `list_checkin_events`
- **Type:** READ
- **Endpoint:** `GET /check-ins/v2/events`
- **Parameters:** None (returns all check-in events for the org)
- **Returns:** List of events with ID, name, frequency, created_at, archived status
- **Notes:** These are event definitions (e.g., "Sunday Morning", "Wednesday Night"), not individual occurrences. Paginated, filtered to non-archived by default.

#### `get_event_attendance`
- **Type:** READ
- **Endpoint:** `GET /check-ins/v2/events/{event_id}/check_ins` with date filtering
- **Parameters:** `event_id` (required), `start_date` (optional, ISO date), `end_date` (optional, ISO date)
- **Returns:** List of check-in records: person name, check-in time, location, security code
- **Notes:** Date filtering via `?where[created_at][gte]=...&where[created_at][lte]=...` if the API supports it, otherwise filter client-side. Paginated, capped at 500 records to prevent excessive API calls. Returns total count even if truncated.

#### `get_headcounts`
- **Type:** READ
- **Endpoint:** `GET /check-ins/v2/events/{event_id}/event_periods` then `GET .../headcounts` per period
- **Parameters:** `event_id` (required), `start_date` (optional), `end_date` (optional)
- **Returns:** List of headcounts by date: `{ date, total, by_location: { "Main Sanctuary": 150, "Kids": 45 } }`
- **Notes:** This is the primary "how many showed up?" tool. Headcounts in PCO are entered per-location per-event-period. The tool aggregates across locations for total and also returns the per-location breakdown. Date filtering narrows to a specific range. Capped at 100 periods.

---

## PCO Client Layer

Add a new API wrapper: `src/pco_mcp/pco/checkins.py`

Follow the existing pattern from `people.py` and `services.py`:
- Class `CheckInsAPI` with methods for each endpoint
- Constructor takes the shared `PCOClient` instance
- Methods return simplified dicts

New methods:
- `get_events()` — list all check-in events
- `get_event_checkins(event_id, start_date, end_date)` — attendance records with date filter
- `get_headcounts(event_id, start_date, end_date)` — aggregated headcount data

---

## Tool Registration

Add `src/pco_mcp/tools/checkins.py` with a `register_checkins_tools()` function, called from `main.py` alongside the existing `register_people_tools()` and `register_services_tools()`.

---

## Tool Annotations

All READ: `readOnlyHint: true, openWorldHint: true`

---

## Testing Strategy

- Unit tests for `CheckInsAPI` methods (mock HTTP responses)
- Unit tests for each MCP tool
- Test headcount aggregation logic (multiple locations, date filtering)
- Test pagination capping behavior
- Fixtures: new directory `tests/fixtures/checkins/` with sample API responses

---

## Out of Scope

- Write operations (creating events, check-ins, stations)
- Location/station management
- Labels, themes, security configuration
- Giving (removed from scope — outside Service Planner domain)
