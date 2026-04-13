# Calendar (Read-only) — MCP Tool Design Spec

**Date:** 2026-04-13
**Sub-project:** 4 of 4 (Calendar)
**Goal:** Surface calendar events so the agent can help plan future events without scheduling conflicts. Read-only.

---

## Context

When planning new services or events, staff need to know what's already on the calendar to avoid conflicts (double-booking rooms, overlapping events, competing for the same volunteers). The PCO Calendar API provides event listings with dates, times, and resource bookings.

**PCO API base:** `https://api.planningcenteronline.com/calendar/v2`

---

## New Tools (2)

#### `list_calendar_events`
- **Type:** READ
- **Endpoint:** `GET /calendar/v2/events` with date range filtering
- **Parameters:** `start_date` (optional, ISO date — defaults to today), `end_date` (optional, ISO date — defaults to 30 days from start), `featured_only` (optional, boolean — filter to featured events)
- **Returns:** List of events with ID, name, description (truncated to 200 chars), dates, recurrence info, visible_in_church_center status
- **Notes:** Returns upcoming events within the date window. Paginated, capped at 200 events. Default 30-day window keeps results focused. Use `?filter=future&order=starts_at` for chronological ordering.

#### `get_event_details`
- **Type:** READ
- **Endpoint:** Composite:
  1. `GET /calendar/v2/events/{event_id}` — event metadata
  2. `GET /calendar/v2/events/{event_id}/event_instances` — individual occurrences (for recurring events)
  3. `GET /calendar/v2/events/{event_id}/event_resource_requests` — what resources/rooms are booked
- **Parameters:** `event_id` (required)
- **Returns:** Full event detail: `{ name, description, dates, instances: [{ starts_at, ends_at, location }], resources: [{ name, type, status }] }`
- **Notes:** The resource booking data is the key value here — it answers "is the sanctuary booked that Saturday?" Fetches event instances and resource requests in parallel for efficiency. Capped at 50 instances (covers ~1 year of weekly events).

---

## PCO Client Layer

Add a new API wrapper: `src/pco_mcp/pco/calendar.py`

Class `CalendarAPI`:
- `get_events(start_date, end_date, featured_only)` — list events with date filter
- `get_event_detail(event_id)` — full event with instances and resource requests

---

## Tool Registration

Add `src/pco_mcp/tools/calendar.py` with `register_calendar_tools()`, called from `main.py`.

---

## Tool Annotations

All READ: `readOnlyHint: true, openWorldHint: true`

---

## Testing Strategy

- Unit tests for `CalendarAPI` methods (mock HTTP responses)
- Unit tests for each MCP tool
- Test date range defaulting logic (today + 30 days)
- Test parallel fetch in `get_event_details`
- Fixtures: new directory `tests/fixtures/calendar/` with sample API responses

---

## Out of Scope

- Write operations (creating events, booking resources)
- Resource management, room setups
- Approval workflows
- Tags, feeds, conflicts detection (beyond what resource bookings show)
- Groups (separate product — not part of Calendar API)
