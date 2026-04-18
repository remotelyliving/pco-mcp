# PCO Data Completeness Pass — Design Spec

**Date:** 2026-04-17
**Goal:** Eliminate silent data loss in `pco-mcp` so the model always receives complete, truthful data — or explicit signals that it didn't.

---

## Context

The pagination fix (uncommitted, same branch) resolved the 25-item team-member truncation the user reported. A deeper audit during that session surfaced five additional categories of silent data loss that pagination alone doesn't fix. They are memoized in `.claude/projects/-home-christian-apps-pco-mcp/memory/pco_data_quality_followups.md`.

This spec addresses all six categories in a single cohesive rewrite, landing on top of the pagination branch so the full data-completeness pass ships as one coherent change.

**Problem categories (as cataloged in the memory doc):**

1. Hard-coded filter defaults that silently exclude data (`filter=future`, `archived_at=""`)
2. Exact-match PCO filters exposed as "search" params
3. `_simplify_*` functions silently dropping user data (second email, `person_id`, relationships)
4. Missing `include=` expansions — opaque relationship pointers or avoidable N+1
5. Time-bounded endpoints with no default bounds
6. No truncation signal from `client.get_all`

**Stated objective:** *"always provide a model with full api data otherwise we get half answers or untruth."*

---

## Design Decisions

Five framing choices were made during brainstorming:

| # | Question | Decision |
|---|---|---|
| Q1 | Hidden default filters (#1, #5) | **Parameterize + document.** Keep sensible defaults but expose override params and state the default in the docstring. |
| Q2 | Response shape for list tools (#6) | **Always-envelope** `{items, meta}`. Uniform shape; meta carries truncation and filter state. |
| Q3 | `_simplify_*` philosophy (#3) | **Curated-but-complete.** Strip JSON:API scaffolding, never drop user data. |
| Q4 | Exact-match search (#2) | **Real PCO search where it exists** (e.g., people `search_name_or_email`); explicit docstring warning where it doesn't. |
| Q5 | `include=` (#4) | **Implementation detail.** Each tool hard-codes the includes its curated schema requires. Not exposed to the model. |

---

## Architecture — Three Contracts

### Contract A: Paginated client result

`client.get_all()` returns a dataclass instead of `list[Any]`:

```python
@dataclass
class PagedResult:
    items: list[Any]           # raw JSON:API records from PCO
    total_count: int | None    # from meta.total_count when PCO provides it
    truncated: bool            # True if max_pages cap fired before next_link cleared
```

API methods now have truncation and total info they can propagate into the response envelope. The existing warning log stays as a defense-in-depth signal for ops; `truncated=True` is the caller-visible signal.

### Contract B: List-returning API method envelope

Every API method that returns a collection returns:

```python
{
    "items": [<curated record>, ...],
    "meta": {
        "total_count": int | None,   # from PagedResult
        "truncated": bool,            # from PagedResult
        "filters_applied": dict       # the defaults/params actually sent to PCO
    }
}
```

`filters_applied` is the truthfulness mechanism for Q1. If the tool sent `filter=future` to PCO, the model sees `{"filter": "future"}` in `meta.filters_applied` and knows the result's scope. If the caller overrides the default, `filters_applied` reflects the override.

Single-resource API methods (`get_person_details`, `get_plan_details`, `get_event_details`, etc.) remain plain curated dicts. Envelopes are a list-only concept.

### Contract C: Curated-but-complete simplification

Each `_simplify_*` function becomes an explicit written contract. Rule: **strip JSON:API scaffolding, never drop user data.**

- **Drop:** `links.*`, `meta.can_update`, opaque `relationships.*.data` pointers that aren't backed by an included record
- **Keep:** every attribute, every ID (including foreign keys like `person_id`, `team_position_id`), every repeated sub-record as an array (all emails, all phones, all addresses)
- **When `include=` is hard-coded:** flatten included records into the curated parent (e.g., `person_name`, `person_id`, `team_position_name` appear directly on the team_member)

The contract for each resource is documented in code via a module-level comment on each `_simplify_*` function listing the fields it promises.

---

## Components & File Changes

### New file: `src/pco_mcp/pco/_envelope.py`

Small helper module used by every API method:

```python
def make_envelope(result: PagedResult, simplified: list, filters_applied: dict) -> dict: ...
def merge_filters(defaults: dict, overrides: dict) -> dict:
    """Merge override params over defaults. None values in overrides remove the default."""
```

Centralizes envelope assembly so the shape stays consistent across modules.

### Changed: `src/pco_mcp/pco/client.py`

- Add `PagedResult` dataclass
- `get_all()` returns `PagedResult`; sets `truncated=True` when `max_pages` cap fires (replaces warning-only behavior — warning stays as defense-in-depth)
- `get()` unchanged

### Changed: `src/pco_mcp/pco/services.py`, `people.py`, `calendar.py`, `checkins.py`

For every list-returning method:

- Build response envelope via `make_envelope(...)`
- Update `_simplify_*` to curated-but-complete rule (all emails/phones as arrays, `person_id` on team_member, foreign keys preserved)
- Hard-code `include=` where the curated schema depends on related records (e.g., `plans/{id}/team_members?include=person,team_position`, `calendar/v2/events?include=event_instances,owner`)

Parameterize forced filters:

- `CalendarAPI.get_events(include_past=False, since=None, until=None)` — when `since`/`until` are passed, the `filter=future` default is dropped
- `CheckInsAPI.get_events(include_archived=False)` — when `True`, `where[archived_at]=""` is not sent
- `ServicesAPI.get_upcoming_plans(include_past=False)` — same pattern
- `CheckInsAPI.get_event_checkins(since=None, until=None)` — no forced default; when neither is passed, `filters_applied` records `{}` and `meta.total_count` signals how much history is loaded

Search (Q4):

- Audit PCO's search params per resource during implementation
- Wire real search where it exists (people `search_name_or_email` is known)
- For resources without real search (e.g., songs), keep exact-match `where[title]=` but rewrite the docstring to state the behavior explicitly

### Changed: `src/pco_mcp/tools/services.py`, `people.py`, `calendar.py`, `checkins.py`

- Tool signatures get the new filter params (forwarded to API methods)
- Tool docstrings state the default scope explicitly: e.g., "By default returns only future non-archived events. Pass `include_past=True` to include past events or pass `since`/`until` to scope to an explicit date range (which drops the default future filter)."
- Search/query tools get docstring warnings about exact-match semantics where applicable

### Unchanged

`config.py`, `oauth.py`, `main.py`, web routes. Pure data-layer refactor.

---

## Data Flow

**List-returning tool call:**

1. Model calls tool, e.g., `list_calendar_events(include_past=True, since="2025-01-01")`
2. Tool wrapper reads OAuth token, instantiates `PCOClient`, calls `CalendarAPI.get_events(include_past=True, since="2025-01-01")`
3. API method computes `filters_applied`: base defaults `{}` (because `include_past=True` drops `filter=future`), adds `{"where[starts_at][gte]": "2025-01-01"}`
4. API method calls `client.get_all(path, params=filters_applied)` with `include=event_instances,owner` hard-coded → returns `PagedResult(items, total_count, truncated)`
5. API method maps each raw item through `_simplify_event` (which flattens included records)
6. API method returns `make_envelope(result, simplified, filters_applied)` → `{items, meta}`
7. Tool wrapper returns that dict unchanged to the MCP layer

**Single-resource tool call:** unchanged — returns curated dict, no envelope.

---

## Error Handling

- **PCO HTTP errors** — bubble up as `httpx.HTTPStatusError`; MCP layer surfaces them as tool errors. No change.
- **Truncation** — not an error. `meta.truncated=True` is the signal. With `max_pages=100` at `per_page=100`, only fires above 10,000 records — rare, but visible when it happens.
- **Empty results** — `{"items": [], "meta": {"total_count": 0, "truncated": False, "filters_applied": {...}}}`. Filters are still reported so the model distinguishes "nothing matches" from "my filter was too narrow."
- **Partial include failures** — if PCO omits an expected included record, `_simplify_*` falls back to attribute-level data and omits the flattened fields silently. A debug log records the gap for later investigation.
- **Invalid filter params** — caught at the tool-wrapper layer via fastmcp type hints; returns an MCP validation error before the PCO call.

**Invariant:** the model always has enough metadata to know the scope, completeness, and shape of what it received.

---

## Testing Strategy

Unit tests against `AsyncMock(spec=PCOClient)`. Fixtures stay as raw PCO JSON.

**Per API method, three test classes:**

1. **Envelope shape** — result has `items` and `meta`; `meta` has `total_count`, `truncated`, `filters_applied`.
2. **Curated schema completeness** — every field the contract promises is present. Person: all emails as an array, all phones as an array, `person_id`. Team member: `person_id`, `person_name`, `team_position_id`, `team_position_name`.
3. **Filter param pass-through** — without overrides: request params include the default AND `meta.filters_applied` reflects it. With override: request params do NOT include the default AND `meta.filters_applied` reflects the override.

**Cross-cutting tests in new `tests/test_envelope.py`:**

- **Truncation propagation** — `client.get_all` returns `PagedResult(truncated=True, total_count=15000, ...)`; tool response surfaces `meta.truncated=True` and `meta.total_count=15000`.
- **Include= wiring** — for methods with hard-coded includes, assert the request URL/params carry the expected `include=`. Prevents regressions where someone "simplifies" by dropping an include and silently breaks the curated schema.
- **Search docstring lint** — walk every registered tool; assert search/query tools have "exact match" or "PCO search" language in the docstring. Cheap regression guard on Q4.

**Scope:** the ~11 test files already modified in the pagination pass get a second update round; add `tests/test_envelope.py`. Pre-existing 18 env-pollution failures stay out of scope. Target: all pagination-touched tests green + every new test green.

---

## Out of Scope

- Changing auth, config, web routes, or OAuth flows
- Adding new PCO API surface (no new endpoints or tools beyond those already registered)
- Rewriting fixtures — raw PCO JSON structure is unchanged
- The `raw_pco_get(path, params)` debug escape hatch discussed during Q5 brainstorm — deferred until there's a concrete need

---

## Open Questions

None at spec time. Implementation may surface specifics (which PCO endpoints have real search params, which includes are available where) that get resolved during the plan phase.
