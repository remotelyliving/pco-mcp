# PCO Data Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate silent data loss in the pco-mcp tool layer by introducing a `PagedResult` dataclass, an `{items, meta}` envelope on all list-returning tools, curated-but-complete simplification, hard-coded `include=` expansions, parameterized filter defaults, and a truncation signal the model can see.

**Architecture:** Three contracts — `PagedResult` (client-level), envelope `{items, meta}` (API-method-level for list tools), curated-but-complete simplification (resource-level). Backwards compat during transition: `PagedResult` behaves list-like so existing call sites iterating over `client.get_all(...)` keep working until each module migrates to the envelope response.

**Tech Stack:** Python 3.12, httpx, FastMCP, pydantic-settings, pytest, pytest-asyncio, uv. Tests use `AsyncMock(spec=PCOClient)` + JSON fixtures.

**Spec:** `docs/specs/2026-04-17-pco-data-completeness-design.md`

---

## Task 1: PagedResult dataclass + envelope helpers

Add the foundation data structures used by every subsequent task.

**Files:**
- Modify: `src/pco_mcp/pco/client.py` (add `PagedResult` above `PCOClient`)
- Create: `src/pco_mcp/pco/_envelope.py`
- Create: `tests/test_envelope_helpers.py`

- [ ] **Step 1.1: Write failing tests for PagedResult**

Create `tests/test_envelope_helpers.py`:

```python
"""Tests for PagedResult and envelope helpers."""
from pco_mcp.pco._envelope import make_envelope, merge_filters
from pco_mcp.pco.client import PagedResult


class TestPagedResult:
    def test_stores_fields(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=10, truncated=False)
        assert pr.items == [1, 2, 3]
        assert pr.total_count == 10
        assert pr.truncated is False

    def test_iterates_like_list(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=None, truncated=False)
        assert list(pr) == [1, 2, 3]

    def test_len_like_list(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=None, truncated=False)
        assert len(pr) == 3

    def test_indexable_like_list(self) -> None:
        pr = PagedResult(items=["a", "b", "c"], total_count=None, truncated=False)
        assert pr[0] == "a"
        assert pr[-1] == "c"


class TestMakeEnvelope:
    def test_wraps_items_with_meta(self) -> None:
        pr = PagedResult(items=[{"raw": 1}], total_count=42, truncated=True)
        env = make_envelope(pr, simplified=[{"id": "1"}], filters_applied={"filter": "future"})
        assert env == {
            "items": [{"id": "1"}],
            "meta": {"total_count": 42, "truncated": True, "filters_applied": {"filter": "future"}},
        }

    def test_empty_items_still_includes_meta(self) -> None:
        pr = PagedResult(items=[], total_count=0, truncated=False)
        env = make_envelope(pr, simplified=[], filters_applied={"foo": "bar"})
        assert env["items"] == []
        assert env["meta"] == {"total_count": 0, "truncated": False, "filters_applied": {"foo": "bar"}}

    def test_none_total_count_passes_through(self) -> None:
        pr = PagedResult(items=[1], total_count=None, truncated=False)
        env = make_envelope(pr, simplified=[1], filters_applied={})
        assert env["meta"]["total_count"] is None


class TestMergeFilters:
    def test_overrides_win(self) -> None:
        result = merge_filters({"filter": "future"}, {"filter": "past"})
        assert result == {"filter": "past"}

    def test_none_value_removes_default(self) -> None:
        result = merge_filters({"filter": "future", "order": "starts_at"}, {"filter": None})
        assert result == {"order": "starts_at"}

    def test_defaults_preserved_without_override(self) -> None:
        result = merge_filters({"filter": "future"}, {})
        assert result == {"filter": "future"}

    def test_adds_new_keys_from_overrides(self) -> None:
        result = merge_filters({"filter": "future"}, {"where[starts_at][gte]": "2025-01-01"})
        assert result == {"filter": "future", "where[starts_at][gte]": "2025-01-01"}
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_envelope_helpers.py -v
```

Expected: ImportError or AttributeError — `PagedResult` and the helpers don't exist yet.

- [ ] **Step 1.3: Add PagedResult to client.py**

Edit `src/pco_mcp/pco/client.py` — add imports and the dataclass near the top, just below the existing imports:

```python
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PagedResult:
    """Result of a paginated PCO fetch. Behaves list-like for backwards compat.

    - items: raw JSON:API records collected across pages
    - total_count: from meta.total_count when PCO supplies it (may be None)
    - truncated: True if max_pages cap fired while more data was available
    """

    items: list[Any] = field(default_factory=list)
    total_count: int | None = None
    truncated: bool = False

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]
```

- [ ] **Step 1.4: Create the envelope helpers module**

Create `src/pco_mcp/pco/_envelope.py`:

```python
"""Helpers for building list-tool response envelopes."""
from typing import Any

from pco_mcp.pco.client import PagedResult


def make_envelope(
    result: PagedResult,
    simplified: list[Any],
    filters_applied: dict[str, Any],
) -> dict[str, Any]:
    """Wrap a simplified list + PagedResult metadata into the standard envelope.

    Shape: {items, meta: {total_count, truncated, filters_applied}}.
    filters_applied mirrors the params actually sent to PCO so the model can
    see the scope of what it received.
    """
    return {
        "items": simplified,
        "meta": {
            "total_count": result.total_count,
            "truncated": result.truncated,
            "filters_applied": filters_applied,
        },
    }


def merge_filters(
    defaults: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Merge override params over defaults. None values in overrides REMOVE the default.

    Example:
        merge_filters({"filter": "future"}, {"filter": None}) == {}
        merge_filters({"filter": "future"}, {"where[x]": "y"}) == {"filter": "future", "where[x]": "y"}
    """
    merged = dict(defaults)
    for key, value in overrides.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged
```

- [ ] **Step 1.5: Run tests to verify they pass**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_envelope_helpers.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 1.6: Commit**

```bash
git add src/pco_mcp/pco/client.py src/pco_mcp/pco/_envelope.py tests/test_envelope_helpers.py
git commit -m "$(cat <<'EOF'
feat(pco): add PagedResult dataclass and envelope helpers

PagedResult is list-like so existing get_all callers keep iterating
without change. make_envelope + merge_filters provide the shared
shape for list-tool responses.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: client.get_all returns PagedResult

Change `client.get_all`'s return type to `PagedResult` and set `truncated=True` when `max_pages` fires. Because `PagedResult` is list-like from Task 1, existing API methods iterating over the result keep working — no changes needed in per-module code yet.

**Files:**
- Modify: `src/pco_mcp/pco/client.py` (get_all body)
- Modify: `tests/test_client.py` (or whatever test file covers get_all — verify first)

- [ ] **Step 2.1: Check which test file covers get_all**

```bash
cd /home/christian/apps/pco-mcp && grep -l "get_all" tests/
```

Expected: identifies the file (likely `tests/test_client.py` or `tests/test_pco_client.py`). If there is no dedicated test file for get_all, create `tests/test_pco_client.py`.

- [ ] **Step 2.2: Write failing tests for PagedResult return from get_all**

Add to the test file identified in 2.1 (or create `tests/test_pco_client.py` with the full import scaffolding):

```python
import pytest
from unittest.mock import AsyncMock

from pco_mcp.pco.client import PCOClient, PagedResult


@pytest.fixture
def make_client() -> PCOClient:
    c = PCOClient(base_url="https://api.example.com", access_token="t")
    c.get = AsyncMock()  # type: ignore[method-assign]
    return c


class TestGetAllReturnsPagedResult:
    async def test_returns_paged_result_single_page(self, make_client: PCOClient) -> None:
        make_client.get.return_value = {
            "data": [{"id": "1"}, {"id": "2"}],
            "links": {},
            "meta": {"total_count": 2},
        }
        result = await make_client.get_all("/things")
        assert isinstance(result, PagedResult)
        assert result.items == [{"id": "1"}, {"id": "2"}]
        assert result.truncated is False

    async def test_sets_truncated_when_max_pages_fires(self, make_client: PCOClient) -> None:
        # Every page has a next link and offset, simulating unlimited pagination
        make_client.get.return_value = {
            "data": [{"id": "x"}],
            "links": {"next": "https://api.example.com/things?offset=100"},
            "meta": {"next": {"offset": 100}, "total_count": 500},
        }
        result = await make_client.get_all("/things", max_pages=3)
        assert result.truncated is True
        assert result.total_count == 500
        assert len(result.items) == 3  # one item per page, three pages

    async def test_total_count_captured_from_last_page(self, make_client: PCOClient) -> None:
        # When next link clears, the response's meta.total_count is captured
        make_client.get.return_value = {
            "data": [{"id": "1"}],
            "links": {},
            "meta": {"total_count": 1},
        }
        result = await make_client.get_all("/things")
        assert result.total_count == 1
        assert result.truncated is False

    async def test_iterable_like_list(self, make_client: PCOClient) -> None:
        # Confirms the list-like shim works end-to-end
        make_client.get.return_value = {
            "data": [{"id": "a"}, {"id": "b"}],
            "links": {},
            "meta": {},
        }
        result = await make_client.get_all("/things")
        as_list = [item["id"] for item in result]
        assert as_list == ["a", "b"]
```

- [ ] **Step 2.3: Run tests to verify they fail**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_client.py -v
```

Expected: failures on `isinstance(result, PagedResult)` and `result.truncated` assertions (get_all still returns `list[Any]`).

- [ ] **Step 2.4: Update get_all to return PagedResult**

Edit `src/pco_mcp/pco/client.py` — replace the `get_all` method body:

```python
    async def get_all(
        self, path: str, params: dict[str, Any] | None = None, max_pages: int = 100
    ) -> PagedResult:
        """Fetch all pages of a paginated PCO endpoint.

        Returns a PagedResult dataclass carrying items + total_count + truncated.
        PagedResult is list-like so callers can iterate/index it directly.
        Uses per_page=100 (PCO's maximum) unless the caller overrides it.
        """
        items: list[Any] = []
        current_params: dict[str, Any] = dict(params or {})
        current_params.setdefault("per_page", 100)
        total_count: int | None = None
        for page_num in range(max_pages):
            result = await self.get(path, params=current_params)
            items.extend(result.get("data", []))
            meta = result.get("meta") or {}
            if "total_count" in meta:
                total_count = meta["total_count"]
            next_link = result.get("links", {}).get("next")
            if not next_link:
                return PagedResult(items=items, total_count=total_count, truncated=False)
            next_offset = meta.get("next", {}).get("offset")
            if next_offset is None:
                return PagedResult(items=items, total_count=total_count, truncated=False)
            current_params["offset"] = next_offset
            if page_num == max_pages - 1:
                logger.warning(
                    "get_all truncated at max_pages=%d for %s (fetched %d, total_count=%s)",
                    max_pages, path, len(items), total_count,
                )
                return PagedResult(items=items, total_count=total_count, truncated=True)
        return PagedResult(items=items, total_count=total_count, truncated=False)
```

- [ ] **Step 2.5: Run tests to verify they pass**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_client.py -v
```

Expected: all four new tests pass.

- [ ] **Step 2.6: Run the full test suite to verify nothing else broke**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/ -q --ignore=tests/test_config.py 2>&1 | tail -20
```

Expected: tests that were passing before Task 2 still pass. The PagedResult list-shim means existing API methods iterating over `get_all` output keep working. Pre-existing 18 env-pollution failures in test_config/test_main/test_oauth/test_web_routes/test_coverage_boost* stay failing (unrelated).

- [ ] **Step 2.7: Commit**

```bash
git add src/pco_mcp/pco/client.py tests/test_pco_client.py
git commit -m "$(cat <<'EOF'
feat(pco): get_all returns PagedResult with truncated signal

Return type changes from list[Any] to PagedResult but the dataclass
is list-like, so existing callers that iterate the result keep
working. Truncation now surfaces as result.truncated=True alongside
the existing log warning.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Calendar envelope migration

First module migration — establishes the pattern the remaining modules will follow.

**Files:**
- Modify: `src/pco_mcp/pco/calendar.py`
- Modify: `src/pco_mcp/tools/calendar.py`
- Modify: `tests/fixtures/calendar/list_events.json` (add `included` array for event_instances+owner)
- Modify: `tests/test_pco_calendar.py`
- Modify: `tests/test_tools_calendar_body.py`

- [ ] **Step 3.1: Update list_events fixture with included records**

Replace `tests/fixtures/calendar/list_events.json` so it reflects a response with `?include=event_instances,owner`:

```json
{
    "data": [
        {
            "type": "Event",
            "id": "201",
            "attributes": {
                "name": "Easter Sunday Service",
                "description": "Annual Easter celebration.",
                "starts_at": "2026-04-20T09:00:00Z",
                "ends_at": "2026-04-20T11:00:00Z",
                "recurrence": null,
                "visible_in_church_center": true
            },
            "relationships": {
                "owner": {"data": {"type": "Person", "id": "5"}},
                "event_instances": {"data": [{"type": "EventInstance", "id": "301"}]}
            }
        }
    ],
    "included": [
        {
            "type": "Person",
            "id": "5",
            "attributes": {"first_name": "Alice", "last_name": "Smith"}
        },
        {
            "type": "EventInstance",
            "id": "301",
            "attributes": {
                "starts_at": "2026-04-20T09:00:00Z",
                "ends_at": "2026-04-20T11:00:00Z",
                "location": "Sanctuary"
            }
        }
    ],
    "links": {},
    "meta": {"total_count": 1, "count": 1}
}
```

- [ ] **Step 3.2: Rewrite test_pco_calendar.py TestGetEvents for envelope + filter params**

Find the `TestGetEvents` class in `tests/test_pco_calendar.py` and replace it with:

```python
class TestGetEvents:
    async def test_returns_envelope_shape(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=1,
            truncated=False,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 1
        assert result["meta"]["truncated"] is False

    async def test_default_applies_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("filter") == "future"
        assert result["meta"]["filters_applied"].get("filter") == "future"

    async def test_include_past_drops_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events(include_past=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "filter" not in call_params
        assert "filter" not in result["meta"]["filters_applied"]

    async def test_passes_include_param_for_instances_and_owner(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        await api.get_events()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "event_instances" in call_params["include"]
        assert "owner" in call_params["include"]

    async def test_simplified_event_includes_owner_name(self, mock_client: AsyncMock) -> None:
        # Raw data carries relationships; the _simplify_event should flatten
        # the included Person into an owner_name field.
        from pco_mcp.pco.client import PagedResult
        raw_events = load_fixture("list_events.json")["data"]
        raw_included = load_fixture("list_events.json")["included"]
        # The API method is expected to stash included records on PagedResult-like
        # data so simplify can look them up. See step 3.4 for the pattern.
        mock_client.get_all.return_value = PagedResult(
            items=raw_events, total_count=1, truncated=False,
        )
        mock_client.get_all.return_value.included = raw_included  # attach for simplify
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        event = result["items"][0]
        assert event["owner_name"] == "Alice Smith"
        assert event["instances"][0]["location"] == "Sanctuary"

    async def test_truncation_surfaces_in_meta(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=15000, truncated=True,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert result["meta"]["truncated"] is True
        assert result["meta"]["total_count"] == 15000
```

The `included` field on `PagedResult` is a new extension added in Step 3.3. Leaving it here so the test drives the need.

- [ ] **Step 3.3: Extend PagedResult to carry included records**

Edit `src/pco_mcp/pco/client.py` — extend the `PagedResult` dataclass:

```python
@dataclass
class PagedResult:
    """Result of a paginated PCO fetch. Behaves list-like for backwards compat.

    - items: raw JSON:API records (top-level data array, collected across pages)
    - total_count: from meta.total_count when PCO supplies it (may be None)
    - truncated: True if max_pages cap fired while more data was available
    - included: flat list of records from the JSON:API 'included' key (may be empty)
    """

    items: list[Any] = field(default_factory=list)
    total_count: int | None = None
    truncated: bool = False
    included: list[Any] = field(default_factory=list)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]
```

Also update `client.get_all` to accumulate `included` across pages:

Find the accumulation block in `get_all` and change to:

```python
        items: list[Any] = []
        included: list[Any] = []
        current_params: dict[str, Any] = dict(params or {})
        current_params.setdefault("per_page", 100)
        total_count: int | None = None
        for page_num in range(max_pages):
            result = await self.get(path, params=current_params)
            items.extend(result.get("data", []))
            included.extend(result.get("included", []))
            meta = result.get("meta") or {}
            if "total_count" in meta:
                total_count = meta["total_count"]
            next_link = result.get("links", {}).get("next")
            if not next_link:
                return PagedResult(
                    items=items, total_count=total_count, truncated=False, included=included
                )
            next_offset = meta.get("next", {}).get("offset")
            if next_offset is None:
                return PagedResult(
                    items=items, total_count=total_count, truncated=False, included=included
                )
            current_params["offset"] = next_offset
            if page_num == max_pages - 1:
                logger.warning(
                    "get_all truncated at max_pages=%d for %s (fetched %d, total_count=%s)",
                    max_pages, path, len(items), total_count,
                )
                return PagedResult(
                    items=items, total_count=total_count, truncated=True, included=included
                )
        return PagedResult(
            items=items, total_count=total_count, truncated=False, included=included
        )
```

- [ ] **Step 3.4: Rewrite CalendarAPI.get_events with envelope + includes + filter params**

Replace `get_events` and `_simplify_event` in `src/pco_mcp/pco/calendar.py`:

```python
from typing import Any

from pco_mcp.pco._envelope import make_envelope, merge_filters
from pco_mcp.pco.client import PCOClient


class CalendarAPI:
    """Wrapper for PCO Calendar module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def get_events(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        featured_only: bool = False,
        include_past: bool = False,
    ) -> dict[str, Any]:
        """List calendar events. Returns an envelope `{items, meta}`.

        Defaults to future non-featured events ordered by start date. Pass
        `include_past=True` to remove the future-only default. `start_date` /
        `end_date` scope by the events' start time and do NOT remove the
        future default — pass `include_past=True` alongside them to search
        history.
        """
        defaults: dict[str, Any] = {
            "order": "starts_at",
            "filter": "featured,future" if featured_only else "future",
            "include": "event_instances,owner",
        }
        overrides: dict[str, Any] = {}
        if include_past:
            overrides["filter"] = None  # removes the default
        if start_date:
            overrides["where[starts_at][gte]"] = start_date
        if end_date:
            overrides["where[starts_at][lte]"] = end_date
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/calendar/v2/events", params=params)
        included_index = _index_included(result.included)
        simplified = [self._simplify_event(e, included_index) for e in result.items]
        # filters_applied strips noise like include/order/per_page so the model
        # sees only the scoping filters that matter for truthfulness.
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event detail with instances and resource bookings.

        Single-resource call — returns a curated dict, NOT an envelope.
        """
        base = f"/calendar/v2/events/{event_id}"
        event_result = await self._client.get(base)
        instances_result = await self._client.get_all(f"{base}/event_instances")
        resources_result = await self._client.get_all(f"{base}/event_resource_requests")
        event = self._simplify_event(event_result["data"], included_index={})
        event["instances"] = [self._simplify_instance(i) for i in instances_result.items]
        event["resources"] = [self._simplify_resource(r) for r in resources_result.items]
        return event

    def _simplify_event(
        self, raw: dict[str, Any], included_index: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        """Curated event record — strips JSON:API scaffolding, flattens include=.

        Kept: id, name, description (200-char truncated), starts_at, ends_at,
        recurrence, visible_in_church_center, owner_name (from include=owner),
        instances (from include=event_instances, simplified).
        Dropped: links.*, raw relationships (replaced by flattened fields).
        """
        attrs = raw.get("attributes", {})
        desc = attrs.get("description") or ""
        if len(desc) > 200:
            desc = desc[:197] + "..."
        simplified: dict[str, Any] = {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": desc,
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
            "recurrence": attrs.get("recurrence"),
            "visible_in_church_center": attrs.get("visible_in_church_center", False),
        }
        rels = raw.get("relationships", {})
        owner_ref = rels.get("owner", {}).get("data")
        if owner_ref and included_index:
            owner = included_index.get((owner_ref["type"], owner_ref["id"]))
            if owner:
                oattrs = owner.get("attributes", {})
                simplified["owner_name"] = (
                    f"{oattrs.get('first_name', '')} {oattrs.get('last_name', '')}".strip()
                )
        instance_refs = rels.get("event_instances", {}).get("data") or []
        if instance_refs and included_index:
            instances = []
            for ref in instance_refs:
                inst = included_index.get((ref["type"], ref["id"]))
                if inst:
                    instances.append(self._simplify_instance(inst))
            if instances:
                simplified["instances"] = instances
        return simplified

    def _simplify_instance(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
            "location": attrs.get("location"),
        }

    def _simplify_resource(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "resource_type": attrs.get("resource_type"),
            "approval_status": attrs.get("approval_status"),
        }


def _index_included(included: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a (type, id) → record lookup from a JSON:API `included` array."""
    return {(rec["type"], rec["id"]): rec for rec in included}
```

Note the `_index_included` helper is module-level so other modules' migrations in later tasks can reuse it (import it or re-implement — see Task 5 and 6).

- [ ] **Step 3.5: Update tools/calendar.py to expose new filter params and document defaults**

Replace contents of `src/pco_mcp/tools/calendar.py`:

```python
from typing import Any

from fastmcp import FastMCP

from pco_mcp.pco.calendar import CalendarAPI
from pco_mcp.tools._context import get_pco_client


def register_calendar_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_calendar_events(
        start_date: str | None = None,
        end_date: str | None = None,
        featured_only: bool = False,
        include_past: bool = False,
    ) -> dict[str, Any]:
        """List calendar events. Returns `{items, meta: {total_count, truncated, filters_applied}}`.

        By default returns ONLY future non-featured events ordered by start
        date. Pass `include_past=True` to include past events. Pass
        `start_date`/`end_date` (ISO date strings) to scope the window.
        `start_date`/`end_date` do NOT remove the future-only default on
        their own — pair them with `include_past=True` to search history.

        `meta.filters_applied` reports exactly what scoping was sent to PCO
        so you can tell an empty result from a narrow filter.
        """
        async with get_pco_client() as client:
            return await CalendarAPI(client).get_events(
                start_date=start_date,
                end_date=end_date,
                featured_only=featured_only,
                include_past=include_past,
            )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_event_details(event_id: str) -> dict[str, Any]:
        """Get full event detail with instances and resource bookings.

        Single-resource call — returns a curated dict (not an envelope).
        Includes all event instances and all resource requests for the
        event, unconditionally.
        """
        async with get_pco_client() as client:
            return await CalendarAPI(client).get_event_detail(event_id)
```

- [ ] **Step 3.6: Update test_tools_calendar_body.py for envelope shape**

Replace `TestListCalendarEventsToolBody` in `tests/test_tools_calendar_body.py`:

```python
class TestListCalendarEventsToolBody:
    async def test_list_events_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "Event",
                    "id": "201",
                    "attributes": {
                        "name": "Easter Service",
                        "description": "Easter.",
                        "starts_at": "2026-04-20T09:00:00Z",
                        "ends_at": "2026-04-20T11:00:00Z",
                        "recurrence": None,
                        "visible_in_church_center": True,
                    },
                    "relationships": {},
                }
            ],
            total_count=1,
            truncated=False,
        )
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_calendar_events")
        result = await fn()
        assert result["items"][0]["name"] == "Easter Service"
        assert result["meta"]["total_count"] == 1
        assert result["meta"]["truncated"] is False
        assert result["meta"]["filters_applied"].get("filter") == "future"

    async def test_list_events_include_past(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_calendar_events")
        result = await fn(include_past=True)
        assert "filter" not in result["meta"]["filters_applied"]
```

Leave `TestGetEventDetailsToolBody` unchanged — `get_event_details` is a single-resource call that stays a plain dict.

- [ ] **Step 3.7: Run calendar tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_calendar.py tests/test_tools_calendar_body.py tests/test_envelope_helpers.py tests/test_pco_client.py -v
```

Expected: all green. If any test fails, fix before committing.

- [ ] **Step 3.8: Commit**

```bash
git add src/pco_mcp/pco/calendar.py src/pco_mcp/pco/client.py src/pco_mcp/tools/calendar.py tests/fixtures/calendar/list_events.json tests/test_pco_calendar.py tests/test_tools_calendar_body.py
git commit -m "$(cat <<'EOF'
feat(calendar): envelope response, include=owner,event_instances, include_past param

list_calendar_events now returns {items, meta} with total_count,
truncated, and filters_applied. include_past=True removes the
default filter=future. Curated event records flatten owner_name and
instances from the JSON:API include array. PagedResult carries
included records across pages.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Check-ins envelope migration

Migrate `CheckInsAPI` to the envelope pattern; parameterize the forced `where[archived_at]=""` default.

**Files:**
- Modify: `src/pco_mcp/pco/checkins.py`
- Modify: `src/pco_mcp/tools/checkins.py`
- Modify: `tests/test_pco_checkins.py`
- Modify: `tests/test_tools_checkins_body.py`

- [ ] **Step 4.1: Rewrite test_pco_checkins.py for envelope shape**

Replace `TestGetEvents` in `tests/test_pco_checkins.py`:

```python
class TestGetEvents:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=1,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_events()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["filters_applied"].get("where[archived_at]") == ""

    async def test_include_archived_drops_default(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        result = await api.get_events(include_archived=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "where[archived_at]" not in call_params
        assert "where[archived_at]" not in result["meta"]["filters_applied"]
```

Update `TestGetEventCheckins` to expect envelope shape (replace class body):

```python
class TestGetEventCheckins:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_event_checkins.json")["data"],
            total_count=2,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_event_checkins("101")
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["meta"]["total_count"] == 2

    async def test_passes_date_filters(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        result = await api.get_event_checkins("101", start_date="2026-01-01", end_date="2026-04-01")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[created_at][gte]") == "2026-01-01"
        assert call_params.get("where[created_at][lte]") == "2026-04-01"
        assert result["meta"]["filters_applied"].get("where[created_at][gte]") == "2026-01-01"
```

Update `TestGetHeadcounts` to expect envelope shape. Because `get_headcounts` aggregates internally (one get_all for periods + one get per period for headcount), it still produces a single envelope at the end:

```python
class TestGetHeadcounts:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "EventPeriod", "id": "301",
                "attributes": {"starts_at": "2026-04-13T09:00:00Z"},
            }],
            total_count=1, truncated=False,
        )
        mock_client.get.return_value = {
            "data": [{
                "type": "Headcount", "id": "401",
                "attributes": {"total": 150},
                "relationships": {
                    "attendance_type": {
                        "data": {
                            "type": "AttendanceType", "id": "50",
                            "attributes": {"name": "Main Sanctuary"},
                        }
                    }
                }
            }]
        }
        api = CheckInsAPI(mock_client)
        result = await api.get_headcounts("101")
        assert "items" in result
        assert result["items"][0]["total"] == 150
```

- [ ] **Step 4.2: Rewrite CheckInsAPI**

Replace `src/pco_mcp/pco/checkins.py`:

```python
from typing import Any

from pco_mcp.pco._envelope import make_envelope, merge_filters
from pco_mcp.pco.client import PCOClient


class CheckInsAPI:
    """Wrapper for PCO Check-ins module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def get_events(self, include_archived: bool = False) -> dict[str, Any]:
        """List check-in events. Returns envelope `{items, meta}`.

        Defaults to active (non-archived) events. Pass `include_archived=True`
        to include archived events. `meta.filters_applied` reports the scoping
        sent to PCO.
        """
        defaults: dict[str, Any] = {"where[archived_at]": ""}
        overrides: dict[str, Any] = {}
        if include_archived:
            overrides["where[archived_at]"] = None
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/check-ins/v2/events", params=params)
        simplified = [self._simplify_event(e) for e in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def get_event_checkins(
        self,
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get check-in records for an event. Returns envelope `{items, meta}`.

        No default date filter — pass `start_date`/`end_date` (ISO) to scope.
        Records are ordered oldest-first by PCO; if a very high-volume event
        hits the internal `max_pages` ceiling, `meta.truncated` will be True.
        """
        defaults: dict[str, Any] = {"order": "-created_at"}
        overrides: dict[str, Any] = {}
        if start_date:
            overrides["where[created_at][gte]"] = start_date
        if end_date:
            overrides["where[created_at][lte]"] = end_date
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all(
            f"/check-ins/v2/events/{event_id}/check_ins",
            params=params,
        )
        simplified = [self._simplify_checkin(c) for c in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def get_headcounts(
        self,
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get headcount data aggregated by event period. Returns envelope `{items, meta}`."""
        defaults: dict[str, Any] = {}
        overrides: dict[str, Any] = {}
        if start_date:
            overrides["where[starts_at][gte]"] = start_date
        if end_date:
            overrides["where[starts_at][lte]"] = end_date
        params = merge_filters(defaults, overrides)
        periods_result = await self._client.get_all(
            f"/check-ins/v2/events/{event_id}/event_periods",
            params=params,
        )
        aggregated: list[dict[str, Any]] = []
        for period in periods_result.items:
            period_id = period["id"]
            period_attrs = period.get("attributes", {})
            hc_result = await self._client.get(
                f"/check-ins/v2/event_periods/{period_id}/headcounts"
            )
            by_location: dict[str, int] = {}
            total = 0
            for hc in hc_result.get("data", []):
                hc_attrs = hc.get("attributes", {})
                count = hc_attrs.get("total", 0)
                total += count
                at_data = (
                    hc.get("relationships", {})
                    .get("attendance_type", {})
                    .get("data", {})
                )
                loc_name = at_data.get("attributes", {}).get("name", "Unknown")
                by_location[loc_name] = count
            aggregated.append({
                "date": period_attrs.get("starts_at"),
                "total": total,
                "by_location": by_location,
            })
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(periods_result, aggregated, filters_applied)

    def _simplify_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Curated check-in event. Kept: id, name, frequency, created_at, archived flag + timestamp."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "created_at": attrs.get("created_at"),
            "archived": attrs.get("archived_at") is not None,
            "archived_at": attrs.get("archived_at"),
        }

    def _simplify_checkin(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Curated check-in. Kept: id, first_name, last_name, created_at, security_code, kind."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "created_at": attrs.get("created_at"),
            "security_code": attrs.get("security_code"),
            "kind": attrs.get("kind"),
        }
```

- [ ] **Step 4.3: Update tools/checkins.py**

Replace `src/pco_mcp/tools/checkins.py`:

```python
from typing import Any

from fastmcp import FastMCP

from pco_mcp.pco.checkins import CheckInsAPI
from pco_mcp.tools._context import get_pco_client


def register_checkins_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_checkin_events(include_archived: bool = False) -> dict[str, Any]:
        """List check-in events. Returns `{items, meta: {total_count, truncated, filters_applied}}`.

        Defaults to active (non-archived) events only. Pass
        `include_archived=True` to include archived events. Check
        `meta.filters_applied` to see what scoping was applied.
        """
        async with get_pco_client() as client:
            return await CheckInsAPI(client).get_events(include_archived=include_archived)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_event_attendance(
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get check-in records for an event. Returns `{items, meta}`.

        No default date filter. For high-volume events, pass `start_date`
        and/or `end_date` (ISO dates) to scope, or watch `meta.truncated`.
        Results are ordered newest-first.
        """
        async with get_pco_client() as client:
            return await CheckInsAPI(client).get_event_checkins(
                event_id, start_date=start_date, end_date=end_date,
            )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_headcounts(
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get headcount data aggregated by event period. Returns `{items, meta}`.

        Each item is one event period with total attendance and a
        by_location breakdown.
        """
        async with get_pco_client() as client:
            return await CheckInsAPI(client).get_headcounts(
                event_id, start_date=start_date, end_date=end_date,
            )
```

- [ ] **Step 4.4: Update test_tools_checkins_body.py for envelope shape**

Replace the three test classes in `tests/test_tools_checkins_body.py`:

```python
class TestListCheckinEventsToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "Event", "id": "101",
                "attributes": {
                    "name": "Sunday Morning", "frequency": "weekly",
                    "created_at": "2025-01-01T00:00:00Z", "archived_at": None,
                },
            }],
            total_count=1, truncated=False,
        )
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_checkin_events")
        result = await fn()
        assert result["items"][0]["name"] == "Sunday Morning"
        assert result["meta"]["filters_applied"].get("where[archived_at]") == ""


class TestGetEventAttendanceToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "CheckIn", "id": "501",
                "attributes": {
                    "first_name": "Alice", "last_name": "Smith",
                    "created_at": "2026-04-13T09:15:00Z", "security_code": "ABC123",
                },
            }],
            total_count=1, truncated=False,
        )
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_event_attendance")
        result = await fn(event_id="101")
        assert result["items"][0]["first_name"] == "Alice"
        assert result["meta"]["total_count"] == 1


class TestGetHeadcountsToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "EventPeriod", "id": "301",
                "attributes": {"starts_at": "2026-04-13T09:00:00Z"},
            }],
            total_count=1, truncated=False,
        )
        mock_client.get.return_value = {
            "data": [{
                "type": "Headcount", "id": "401",
                "attributes": {"total": 150},
                "relationships": {
                    "attendance_type": {
                        "data": {
                            "type": "AttendanceType", "id": "50",
                            "attributes": {"name": "Main Sanctuary"},
                        }
                    }
                }
            }]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_headcounts")
        result = await fn(event_id="101")
        assert result["items"][0]["total"] == 150
```

- [ ] **Step 4.5: Run check-in tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_checkins.py tests/test_tools_checkins_body.py -v
```

Expected: all green.

- [ ] **Step 4.6: Commit**

```bash
git add src/pco_mcp/pco/checkins.py src/pco_mcp/tools/checkins.py tests/test_pco_checkins.py tests/test_tools_checkins_body.py
git commit -m "$(cat <<'EOF'
feat(checkins): envelope response + include_archived param

list_checkin_events now returns {items, meta} and exposes
include_archived to disable the forced where[archived_at]="" default.
get_event_attendance and get_headcounts also return envelopes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: People envelope migration

Migrate `PeopleAPI` read methods to envelopes and update `_simplify_person` to return all emails/phones as arrays (curated-but-complete).

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Modify: `tests/test_pco_people.py`
- Modify: `tests/test_tools_people_body.py`

Scope — these methods migrate to envelopes: `search_people`, `list_lists`, `get_list_members`, `get_person_blockouts`, `get_notes`, `get_workflows`. Write methods (`create_person`, `update_person`, `add_email`, `add_phone_number`, `add_address`, `add_blockout`, `add_note`, `add_person_to_workflow`) and the single-resource `get_person` / `get_person_details` stay as plain dicts.

- [ ] **Step 5.1: Write failing tests for envelope + curated person schema**

Edit `tests/test_pco_people.py`. Replace `TestSearchPeople` with:

```python
class TestSearchPeople:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("search_people.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2

    async def test_filters_applied_reports_search(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        assert result["meta"]["filters_applied"].get("where[search_name_or_email]") == "Alice"
```

Add a new test class covering curated-but-complete person shape:

```python
class TestSimplifyPersonCompleteness:
    async def test_returns_all_emails_and_phones(self, mock_client: AsyncMock) -> None:
        """A person with multiple emails/phones must return them all as arrays."""
        from pco_mcp.pco.client import PagedResult
        raw = {
            "type": "Person",
            "id": "1",
            "attributes": {
                "first_name": "Alice",
                "last_name": "Smith",
                "email_addresses": [
                    {"address": "a@example.com", "location": "Home", "primary": True},
                    {"address": "a@work.com", "location": "Work", "primary": False},
                ],
                "phone_numbers": [
                    {"number": "555-0001", "location": "Mobile", "primary": True},
                    {"number": "555-0002", "location": "Home", "primary": False},
                ],
            },
        }
        mock_client.get_all.return_value = PagedResult(items=[raw], total_count=1, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        person = result["items"][0]
        assert len(person["emails"]) == 2
        assert person["emails"][0]["address"] == "a@example.com"
        assert person["emails"][1]["address"] == "a@work.com"
        assert len(person["phone_numbers"]) == 2
```

Replace `TestListLists`, `TestGetPersonBlockouts`, `TestGetNotes`, `TestGetWorkflows`, `TestGetListMembers` in their respective files (`test_pco_people.py` and `test_pco_people_write.py`) with envelope-shaped assertions using the same pattern — `PagedResult(items=fixture_data, total_count=N, truncated=False)` + `assert "items" in result and "meta" in result`.

Also replace `TestGetPersonDetails` — this method stays a single-resource dict but its nested lists change: `emails`, `phone_numbers`, `addresses` stay as bare arrays (no envelope) because they're part of the person's curated schema.

```python
class TestGetPersonDetails:
    async def test_returns_single_resource_dict(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.side_effect = [
            PagedResult(items=load_fixture("person_emails.json")["data"], total_count=2, truncated=False),
            PagedResult(items=load_fixture("person_phones.json")["data"], total_count=1, truncated=False),
            PagedResult(items=load_fixture("person_addresses.json")["data"], total_count=1, truncated=False),
        ]
        api = PeopleAPI(mock_client)
        result = await api.get_person_details("1")
        assert "emails" in result
        assert "phone_numbers" in result
        assert "addresses" in result
        assert "items" not in result  # NOT an envelope
        assert "meta" not in result
        assert len(result["emails"]) == 2
```

- [ ] **Step 5.2: Run the new tests to see failures**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_people.py tests/test_pco_people_write.py -v
```

Expected: failures — envelope not yet applied, emails/phones still single.

- [ ] **Step 5.3: Rewrite people.py read methods + _simplify_person**

Edit `src/pco_mcp/pco/people.py`. Add imports at top:

```python
from pco_mcp.pco._envelope import make_envelope, merge_filters
```

Replace the read methods and `_simplify_person`:

```python
    async def search_people(
        self,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> dict[str, Any]:
        """Search for people. Returns envelope `{items, meta}`.

        Uses PCO's `search_name_or_email` param which matches names and
        emails with partial/fuzzy behavior. `phone` is matched against
        the same search field when passed (PCO's behavior may not always
        match on phone — verify results). When `email` and `phone` are
        both supplied, email takes priority.
        """
        defaults: dict[str, Any] = {"include": "emails,phone_numbers"}
        overrides: dict[str, Any] = {}
        if email and phone:
            import warnings
            warnings.warn(
                "Both email and phone provided to search_people; email takes priority.",
                stacklevel=2,
            )
        if email:
            overrides["where[search_name_or_email]"] = email
        elif phone:
            overrides["where[search_name_or_email]"] = phone
        elif name:
            overrides["where[search_name_or_email]"] = name
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/people/v2/people", params=params)
        simplified = [self._simplify_person(p) for p in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def get_person(self, person_id: str) -> dict[str, Any]:
        """Get full details for a person by ID (single-resource dict)."""
        api_result = await self._client.get(f"/people/v2/people/{person_id}")
        return self._simplify_person(api_result["data"])

    async def list_lists(self) -> dict[str, Any]:
        """Get all PCO Lists. Returns envelope `{items, meta}`."""
        result = await self._client.get_all("/people/v2/lists")
        simplified = [self._simplify_list(lst) for lst in result.items]
        return make_envelope(result, simplified, {})

    async def get_list_members(self, list_id: str) -> dict[str, Any]:
        """Get people in a specific list. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(f"/people/v2/lists/{list_id}/people")
        simplified = [self._simplify_person(p) for p in result.items]
        return make_envelope(result, simplified, {})

    async def get_person_details(self, person_id: str) -> dict[str, Any]:
        """Get all contact details for a person. Single-resource dict (no envelope).

        Nested lists (emails, phone_numbers, addresses) are bare arrays —
        they're part of the person's curated schema. If any of these
        internal fetches hit the max_pages cap (very rare), a warning is
        logged but not propagated to the caller.
        """
        base = f"/people/v2/people/{person_id}"
        emails_result = await self._client.get_all(f"{base}/emails")
        phones_result = await self._client.get_all(f"{base}/phone_numbers")
        addresses_result = await self._client.get_all(f"{base}/addresses")
        for name, r in [
            ("emails", emails_result),
            ("phone_numbers", phones_result),
            ("addresses", addresses_result),
        ]:
            if r.truncated:
                logger.warning(
                    "get_person_details %s for person_id=%s truncated at max_pages",
                    name, person_id,
                )
        return {
            "emails": [self._simplify_email(e) for e in emails_result.items],
            "phone_numbers": [self._simplify_phone(p) for p in phones_result.items],
            "addresses": [self._simplify_address(a) for a in addresses_result.items],
        }

    async def get_person_blockouts(self, person_id: str) -> dict[str, Any]:
        """Get blockout dates for a person. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(f"/people/v2/people/{person_id}/blockouts")
        simplified = [self._simplify_blockout(b) for b in result.items]
        return make_envelope(result, simplified, {})

    async def get_notes(self, person_id: str) -> dict[str, Any]:
        """Get notes for a person (most recent first). Returns envelope `{items, meta}`."""
        params = {"order": "-created_at"}
        result = await self._client.get_all(
            f"/people/v2/people/{person_id}/notes",
            params=params,
        )
        simplified = [self._simplify_note(n) for n in result.items]
        return make_envelope(result, simplified, {})

    async def get_workflows(self) -> dict[str, Any]:
        """List all workflows for the org. Returns envelope `{items, meta}`."""
        result = await self._client.get_all("/people/v2/workflows")
        simplified = [self._simplify_workflow(w) for w in result.items]
        return make_envelope(result, simplified, {})
```

Replace `_simplify_person` with curated-but-complete version (all emails/phones as arrays):

```python
    def _simplify_person(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Curated person record.

        Kept: id, first_name, last_name, name, emails[], phone_numbers[],
        membership, status, birthdate, gender, created_at, avatar,
        site_administrator.
        Dropped: JSON:API links, relationships, meta.
        """
        attrs = raw.get("attributes", {})
        raw_emails = attrs.get("email_addresses") or []
        raw_phones = attrs.get("phone_numbers") or []
        return {
            "id": raw["id"],
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "name": attrs.get("name") or (
                f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
            ),
            "emails": [
                {
                    "address": e.get("address", ""),
                    "location": e.get("location"),
                    "primary": e.get("primary", False),
                }
                for e in raw_emails
            ],
            "phone_numbers": [
                {
                    "number": p.get("number", ""),
                    "location": p.get("location"),
                    "primary": p.get("primary", False),
                }
                for p in raw_phones
            ],
            "membership": attrs.get("membership"),
            "status": attrs.get("status"),
            "birthdate": attrs.get("birthdate"),
            "gender": attrs.get("gender"),
            "created_at": attrs.get("created_at"),
            "avatar": attrs.get("avatar"),
            "site_administrator": attrs.get("site_administrator"),
        }
```

Leave the other `_simplify_*` helpers in the file (`_simplify_email`, `_simplify_phone`, `_simplify_address`, `_simplify_blockout`, `_simplify_note`, `_simplify_list`, `_simplify_workflow`, `_simplify_workflow_card`) unchanged — they already return curated-but-complete records.

- [ ] **Step 5.4: Update tools/people.py for envelope-returning tools**

The existing tools return from API methods directly. Since the API methods now return envelopes, the tools automatically pass those through. But we need to update docstrings to document the new shape and new params.

Edit `src/pco_mcp/tools/people.py`. For each of the list-returning tools (e.g., `search_people`, `list_lists`, `get_list_members`, `get_person_blockouts`, `get_person_notes`, `list_workflows`), update docstrings to reflect envelope and mention `meta.filters_applied` / `meta.truncated` where relevant. Single-resource tools (`get_person_by_id`, `list_person_details`, write tools) keep their existing docstrings.

Example — `search_people` docstring:

```
"""Search for people by name, email, or phone.

Returns `{items, meta: {total_count, truncated, filters_applied}}` where
items is a list of curated person records. Each person includes all
emails and phone_numbers as arrays (not just the primary).

PCO uses a fuzzy `search_name_or_email` under the hood. Phone searches
pass the phone number to that same field and results may be partial —
verify by scanning returned records.
"""
```

Apply equivalent docstring updates to the other list tools.

- [ ] **Step 5.5: Update test_tools_people_body.py for envelope shape**

For each of `TestSearchPeople`, `TestListLists`, `TestGetListMembers`, `TestListPersonDetails` (keep dict shape), `TestListNotes`, `TestListWorkflows` in `tests/test_tools_people_body.py`:

- Change mock setup to `PagedResult(items=[...], total_count=N, truncated=False)`.
- Change assertion from `assert len(result) == N` / `result[0][...]` to `assert len(result["items"]) == N` / `result["items"][0][...]` plus `assert result["meta"]["total_count"] == N`.
- `TestListPersonDetails` stays single-resource — assert `emails`/`phone_numbers`/`addresses` keys directly.

- [ ] **Step 5.6: Run people tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_people.py tests/test_pco_people_write.py tests/test_tools_people_body.py -v
```

Expected: all green. If `_simplify_person` changes break other tests (e.g., tests asserting `person["email"]` — now `person["emails"][0]["address"]`), fix those tests.

- [ ] **Step 5.7: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_pco_people_write.py tests/test_tools_people_body.py
git commit -m "$(cat <<'EOF'
feat(people): envelope response + all emails/phones on person

Person records now expose emails[] and phone_numbers[] as arrays
(curated-but-complete — no more silent drop of secondary contacts).
Read methods return {items, meta} envelopes. get_person_details
stays a single-resource dict.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Services read methods — envelope + team_member include

Services is the largest module. Split across two tasks to keep scope manageable. This task handles the first half.

**In scope for this task:** `list_service_types`, `get_upcoming_plans` (with `include_past`), `list_team_members` (with `include=person,team_position` + `person_id` on curated record), `list_songs` (docstring warning on exact-match), `list_plan_items`, `list_teams`, `list_team_positions`.

**Out of scope for this task** (Task 7): `get_song_schedule_history`, `list_song_arrangements`, `list_plan_templates`, `get_needed_positions`, `list_attachments`, `list_media`, `flag_missing_ccli`, `get_plan_details`.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Modify: `src/pco_mcp/tools/services.py`
- Modify: `tests/test_pco_services.py` (and/or `test_pco_services_write.py`)
- Modify: `tests/test_tools_services_body.py`
- Modify: `tests/fixtures/services/list_team_members.json` (add included person + team_position)

- [ ] **Step 6.1: Update list_team_members fixture with included person + team_position**

Replace `tests/fixtures/services/list_team_members.json`:

```json
{
    "data": [
        {
            "type": "PlanPerson",
            "id": "501",
            "attributes": {
                "name": "Alice Smith",
                "team_position_name": "Vocalist",
                "status": "C",
                "notification_sent_at": "2026-04-10T12:00:00Z"
            },
            "relationships": {
                "person": {"data": {"type": "Person", "id": "1001"}},
                "team_position": {"data": {"type": "TeamPosition", "id": "11"}}
            }
        },
        {
            "type": "PlanPerson",
            "id": "502",
            "attributes": {
                "name": "Bob Jones",
                "team_position_name": "Guitarist",
                "status": "U",
                "notification_sent_at": null
            },
            "relationships": {
                "person": {"data": {"type": "Person", "id": "1002"}},
                "team_position": {"data": {"type": "TeamPosition", "id": "12"}}
            }
        }
    ],
    "included": [
        {
            "type": "Person",
            "id": "1001",
            "attributes": {"first_name": "Alice", "last_name": "Smith"}
        },
        {
            "type": "Person",
            "id": "1002",
            "attributes": {"first_name": "Bob", "last_name": "Jones"}
        },
        {
            "type": "TeamPosition",
            "id": "11",
            "attributes": {"name": "Vocalist"}
        },
        {
            "type": "TeamPosition",
            "id": "12",
            "attributes": {"name": "Guitarist"}
        }
    ],
    "links": {},
    "meta": {"total_count": 2, "count": 2}
}
```

- [ ] **Step 6.2: Rewrite test_pco_services.py classes for in-scope methods**

For `TestListServiceTypes`, `TestGetUpcomingPlans`, `TestListTeamMembers`, `TestListSongs`, `TestListPlanItems`, `TestListTeams`, `TestListTeamPositions` — convert to envelope shape. Sample (copy-paste and adjust per class):

```python
class TestListTeamMembers:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_team_members.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_team_members("201", "301")
        assert "items" in result
        assert result["meta"]["total_count"] == 2

    async def test_curated_includes_person_id_and_name(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_team_members.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_team_members("201", "301")
        tm = result["items"][0]
        assert tm["person_id"] == "1001"
        assert tm["person_name"] == "Alice Smith"
        assert tm["team_position_id"] == "11"
        assert tm["team_position_name"] == "Vocalist"

    async def test_passes_include_params(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        await api.list_team_members("201", "301")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "person" in call_params["include"]
        assert "team_position" in call_params["include"]


class TestGetUpcomingPlans:
    async def test_default_applies_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.get_upcoming_plans("201")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("filter") == "future"
        assert result["meta"]["filters_applied"].get("filter") == "future"

    async def test_include_past_drops_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.get_upcoming_plans("201", include_past=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "filter" not in call_params
        assert "filter" not in result["meta"]["filters_applied"]
```

Apply the same envelope pattern (with class-specific fixture + simplified schema assertions) to all other in-scope classes in `tests/test_pco_services.py`.

- [ ] **Step 6.3: Rewrite in-scope methods in services.py**

Edit `src/pco_mcp/pco/services.py`. Add imports at top:

```python
from pco_mcp.pco._envelope import make_envelope, merge_filters
```

Replace the in-scope read methods:

```python
    async def list_service_types(self) -> dict[str, Any]:
        """List all service types. Returns envelope `{items, meta}`."""
        result = await self._client.get_all("/services/v2/service_types")
        simplified = [self._simplify_service_type(st) for st in result.items]
        return make_envelope(result, simplified, {})

    async def get_upcoming_plans(
        self, service_type_id: str, include_past: bool = False,
    ) -> dict[str, Any]:
        """Get plans for a service type. Returns envelope `{items, meta}`.

        Defaults to future plans ordered by sort_date. Pass
        `include_past=True` to drop the future filter and include history.
        `meta.filters_applied` reports the active scoping.
        """
        defaults: dict[str, Any] = {"filter": "future", "order": "sort_date"}
        overrides: dict[str, Any] = {}
        if include_past:
            overrides["filter"] = None
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans",
            params=params,
        )
        simplified = [self._simplify_plan(p) for p in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def list_songs(self, query: str | None = None) -> dict[str, Any]:
        """List/search songs. Returns envelope `{items, meta}`.

        NOTE: PCO's `where[title]` filter is an EXACT match — "Amazing" will
        NOT find "Amazing Grace". Pass the full song title or omit the query
        to fetch everything.
        """
        defaults: dict[str, Any] = {}
        overrides: dict[str, Any] = {}
        if query:
            overrides["where[title]"] = query
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/services/v2/songs", params=params)
        simplified = [self._simplify_song(s) for s in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def list_team_members(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """List team members for a plan. Returns envelope `{items, meta}`.

        Hard-codes `include=person,team_position` so each member's curated
        record carries person_id, person_name, team_position_id, and
        team_position_name directly (no follow-up lookup needed).
        """
        defaults: dict[str, Any] = {"include": "person,team_position"}
        params = merge_filters(defaults, {})
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            params=params,
        )
        included_index = _index_included(result.included)
        simplified = [self._simplify_team_member(tm, included_index) for tm in result.items]
        return make_envelope(result, simplified, {})

    async def list_plan_items(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """List items (songs/elements) on a plan. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items"
        )
        simplified = [self._simplify_item(i) for i in result.items]
        return make_envelope(result, simplified, {})

    async def list_teams(self, service_type_id: str) -> dict[str, Any]:
        """List teams for a service type. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/teams"
        )
        simplified = [self._simplify_team(t) for t in result.items]
        return make_envelope(result, simplified, {})

    async def list_team_positions(self, team_id: str) -> dict[str, Any]:
        """List positions for a team. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(f"/services/v2/teams/{team_id}/team_positions")
        simplified = [self._simplify_position(p) for p in result.items]
        return make_envelope(result, simplified, {})
```

Add the module-level `_index_included` helper at the bottom of the file (same as in calendar.py):

```python
def _index_included(included: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a (type, id) → record lookup from a JSON:API `included` array."""
    return {(rec["type"], rec["id"]): rec for rec in included}
```

Update `_simplify_team_member` to accept an included index and flatten person + team_position:

```python
    def _simplify_team_member(
        self,
        raw: dict[str, Any],
        included_index: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Curated team_member record.

        Kept: id, status, notification_sent_at, name attribute (legacy),
        person_id, person_name, team_position_id, team_position_name
        (both derived from include=person,team_position where available).
        Dropped: JSON:API links and raw relationships.
        """
        attrs = raw.get("attributes", {})
        rels = raw.get("relationships", {})
        simplified: dict[str, Any] = {
            "id": raw["id"],
            "person_name": attrs.get("name", ""),
            "team_position_name": attrs.get("team_position_name"),
            "status": attrs.get("status"),
            "notification_sent_at": attrs.get("notification_sent_at"),
        }
        person_ref = rels.get("person", {}).get("data")
        if person_ref:
            simplified["person_id"] = person_ref.get("id")
            if included_index:
                person = included_index.get((person_ref["type"], person_ref["id"]))
                if person:
                    pattrs = person.get("attributes", {})
                    simplified["person_name"] = (
                        f"{pattrs.get('first_name', '')} {pattrs.get('last_name', '')}".strip()
                    )
        position_ref = rels.get("team_position", {}).get("data")
        if position_ref:
            simplified["team_position_id"] = position_ref.get("id")
            if included_index:
                position = included_index.get((position_ref["type"], position_ref["id"]))
                if position:
                    simplified["team_position_name"] = position.get("attributes", {}).get("name")
        return simplified
```

Because `schedule_team_member` (a write method) also calls `_simplify_team_member`, it will pass no `included_index` and the function handles that via the `if included_index:` guards. The result will still carry `person_id` from the `relationships.person.data` pointer.

- [ ] **Step 6.4: Update tools/services.py in-scope tools**

In `src/pco_mcp/tools/services.py`, update each in-scope tool's docstring to describe the envelope and any new params. For `list_plans_for_service_type` (or whatever the tool wraps `get_upcoming_plans`), add the `include_past: bool = False` param and pass it through.

Example for the upcoming plans tool (find the existing decorator and replace):

```python
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_plans_for_service_type(
        service_type_id: str, include_past: bool = False,
    ) -> dict[str, Any]:
        """List plans for a service type. Returns `{items, meta}`.

        Defaults to future plans ordered by sort_date. Pass
        `include_past=True` to also include past plans. The `meta.filters_applied`
        entry reports the active PCO filter so you can tell an empty result
        from a too-narrow filter.
        """
        async with get_pco_client() as client:
            return await ServicesAPI(client).get_upcoming_plans(
                service_type_id, include_past=include_past,
            )
```

For `list_songs`, update the docstring to loudly state exact-match:

```python
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_songs(query: str | None = None) -> dict[str, Any]:
        """List songs in the library. Returns `{items, meta}`.

        IMPORTANT: the `query` param is an EXACT-match title filter, not
        a substring/fuzzy search. "Amazing" will NOT find "Amazing Grace".
        Pass the full song title, or omit `query` to fetch everything and
        filter in memory.
        """
        async with get_pco_client() as client:
            return await ServicesAPI(client).list_songs(query=query)
```

Apply envelope-wording updates to the other in-scope tool docstrings (`list_service_types`, `list_plan_items`, `list_teams`, `list_team_positions`, `list_team_members`).

- [ ] **Step 6.5: Update test_tools_services_body.py for in-scope tools**

In `tests/test_tools_services_body.py`, find the test classes corresponding to the in-scope tools and update them to use `PagedResult` mocks + envelope assertions. The pattern is the same as Task 4 / Task 5.

- [ ] **Step 6.6: Run services tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_services.py tests/test_pco_services_write.py tests/test_tools_services_body.py -v
```

Expected: tests for in-scope methods pass; other services tests (which cover out-of-scope methods from Task 7) may fail if they relied on the old bare-list shape — those get fixed in Task 7.

Acceptable intermediate state: specifically, Task 6 is allowed to leave `TestGetSongScheduleHistory`, `TestListSongArrangements`, `TestListPlanTemplates`, `TestGetNeededPositions`, `TestListAttachments`, `TestListMedia`, `TestFlagMissingCcli`, and `TestGetPlanDetails` failing at this point — Task 7 fixes them.

- [ ] **Step 6.7: Commit**

```bash
git add src/pco_mcp/pco/services.py src/pco_mcp/tools/services.py tests/fixtures/services/list_team_members.json tests/test_pco_services.py tests/test_pco_services_write.py tests/test_tools_services_body.py
git commit -m "$(cat <<'EOF'
feat(services): envelope + include=person,team_position + include_past

list_service_types, get_upcoming_plans (with include_past), list_songs
(exact-match warning), list_team_members (with person_id/team_position_id
flattened from include=), list_plan_items, list_teams, list_team_positions
all return {items, meta} envelopes. team_member curated records now carry
person_id so the model can pivot without an extra lookup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Services read methods (part 2) — remaining envelopes

Finish the services migration: the remaining list-returning methods plus the composite `get_plan_details` and `flag_missing_ccli`.

**In scope:** `get_song_schedule_history`, `list_song_arrangements`, `list_plan_templates`, `get_needed_positions`, `list_attachments`, `list_media`, `flag_missing_ccli`, `get_plan_details` (composite single-resource).

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Modify: `src/pco_mcp/tools/services.py`
- Modify: `tests/test_pco_services.py`, `tests/test_pco_services_write.py`, `tests/test_tools_services_body.py`, `tests/test_coverage_boost2.py` (as needed)

- [ ] **Step 7.1: Update the failing test classes to expect envelopes**

In `tests/test_pco_services.py` (or the relevant file), replace `TestGetSongScheduleHistory`, `TestListSongArrangements`, `TestListPlanTemplates`, `TestGetNeededPositions`, `TestListAttachments`, `TestListMedia`, `TestFlagMissingCcli`, `TestGetPlanDetails` with envelope-shape assertions. Pattern (copy & adjust):

```python
class TestListSongArrangements:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_song_arrangements.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_song_arrangements("701")
        assert "items" in result
        assert result["meta"]["total_count"] == 2


class TestFlagMissingCcli:
    async def test_returns_envelope_style_dict(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {"type": "Song", "id": "1", "attributes": {"title": "With CCLI", "ccli_number": 12345}},
                {"type": "Song", "id": "2", "attributes": {"title": "Missing", "ccli_number": None}},
            ],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.flag_missing_ccli()
        # Custom aggregated shape (not a straight envelope) but items/meta
        # are still the top-level keys so the model can reason about it
        # uniformly.
        assert result["total_scanned"] == 2
        assert result["total_missing"] == 1
        assert len(result["items"]) == 1  # "Missing" song only
        assert result["meta"]["total_count"] == 2
        assert result["meta"]["truncated"] is False


class TestGetPlanDetails:
    async def test_returns_single_resource_dict_with_nested_lists(
        self, mock_client: AsyncMock,
    ) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=[], total_count=0, truncated=False),  # items
            PagedResult(items=[], total_count=0, truncated=False),  # team_members
        ]
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        # Single-resource dict — no envelope, but nested arrays are bare lists
        assert "items" in plan  # list, not envelope (part of curated plan)
        assert "team_members" in plan
        assert isinstance(plan["items"], list)
        assert "meta" not in plan  # confirms it's NOT an envelope
```

Apply the same envelope-assertion updates to the remaining classes. Include one test per method asserting `result["meta"]["truncated"]` exists.

- [ ] **Step 7.2: Rewrite remaining services.py methods**

Replace the out-of-scope-from-Task-6 methods in `src/pco_mcp/pco/services.py`:

```python
    async def get_plan_details(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """Get full plan detail with items + team members.

        Single-resource composite call — returns a curated dict, NOT an
        envelope. Nested lists `items` and `team_members` are bare arrays
        (part of the plan's curated schema). If either internal fetch
        truncates, a warning is logged but not propagated.
        """
        base = f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        plan_result = await self._client.get(base)
        plan = self._simplify_plan(plan_result["data"])
        items_result = await self._client.get_all(f"{base}/items")
        team_result = await self._client.get_all(
            f"{base}/team_members", params={"include": "person,team_position"},
        )
        for name, r in [("items", items_result), ("team_members", team_result)]:
            if r.truncated:
                import logging
                logging.getLogger(__name__).warning(
                    "get_plan_details %s for plan_id=%s truncated at max_pages",
                    name, plan_id,
                )
        included_index = _index_included(team_result.included)
        plan["items"] = [self._simplify_item(i) for i in items_result.items]
        plan["team_members"] = [
            self._simplify_team_member(tm, included_index) for tm in team_result.items
        ]
        return plan

    async def get_song_schedule_history(self, song_id: str) -> dict[str, Any]:
        """Get schedule history for a song. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/songs/{song_id}/song_schedules"
        )
        simplified = [self._simplify_song_schedule(s) for s in result.items]
        return make_envelope(result, simplified, {})

    async def list_song_arrangements(self, song_id: str) -> dict[str, Any]:
        """List arrangements for a song. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(f"/services/v2/songs/{song_id}/arrangements")
        simplified = [self._simplify_arrangement(a) for a in result.items]
        return make_envelope(result, simplified, {})

    async def list_plan_templates(self, service_type_id: str) -> dict[str, Any]:
        """List plan templates for a service type. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plan_templates"
        )
        simplified = [self._simplify_template(t) for t in result.items]
        return make_envelope(result, simplified, {})

    async def get_needed_positions(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """Get needed (unfilled) positions for a plan. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/needed_positions"
        )
        simplified = [self._simplify_needed_position(np) for np in result.items]
        return make_envelope(result, simplified, {})

    async def list_attachments(
        self, song_id: str, arrangement_id: str,
    ) -> dict[str, Any]:
        """List attachments for an arrangement. Returns envelope `{items, meta}`."""
        result = await self._client.get_all(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
        )
        simplified = [self._simplify_attachment(a) for a in result.items]
        return make_envelope(result, simplified, {})

    async def list_media(self, media_type: str | None = None) -> dict[str, Any]:
        """List org-level media items. Returns envelope `{items, meta}`.

        Optional `media_type` filter (e.g., "background", "countdown") is
        reported in `meta.filters_applied` when passed.
        """
        defaults: dict[str, Any] = {}
        overrides: dict[str, Any] = {}
        if media_type:
            overrides["where[media_type]"] = media_type
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/services/v2/media", params=params)
        simplified = [self._simplify_media(m) for m in result.items]
        filters_applied = {
            k: v for k, v in params.items()
            if k not in {"include", "order", "per_page"}
        }
        return make_envelope(result, simplified, filters_applied)

    async def flag_missing_ccli(self) -> dict[str, Any]:
        """Scan the song library for missing CCLI numbers.

        Returns a composite dict:
            {
                "total_scanned": int,
                "total_missing": int,
                "items": [<simplified song>, ...],   # missing CCLI only
                "meta": {"total_count", "truncated", "filters_applied"}
            }

        The top-level `items` + `meta` follow the envelope convention so
        the model can reason about completeness the same way it does for
        other list tools. `meta.truncated` reflects the underlying song
        scan.
        """
        result = await self._client.get_all("/services/v2/songs")
        missing: list[dict[str, Any]] = []
        for raw in result.items:
            attrs = raw.get("attributes", {})
            if not attrs.get("ccli_number"):
                missing.append(self._simplify_song(raw))
        return {
            "total_scanned": len(result.items),
            "total_missing": len(missing),
            "items": missing,
            "meta": {
                "total_count": result.total_count,
                "truncated": result.truncated,
                "filters_applied": {},
            },
        }
```

- [ ] **Step 7.3: Update tools/services.py for remaining tools**

For each corresponding tool in `src/pco_mcp/tools/services.py`, update the docstring to describe the envelope shape. The tool wrappers just forward — no signature changes needed for this batch.

- [ ] **Step 7.4: Update test_tools_services_body.py and test_coverage_boost2.py**

Apply envelope-shape mocks + assertions to the tool-body tests for these methods. Same pattern as prior tasks. For `test_coverage_boost2.py`, classes `TestGetSongScheduleHistoryToolBody`, `TestListSongArrangementsToolBody`, `TestListPlanTemplatesToolBody`, `TestGetNeededPositionsToolBody` (and any others covering the in-scope methods) need to be updated.

- [ ] **Step 7.5: Run all services tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_pco_services.py tests/test_pco_services_write.py tests/test_tools_services_body.py tests/test_coverage_boost2.py -v
```

Expected: every services-related test passes.

- [ ] **Step 7.6: Run the full suite and confirm no new regressions**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/ -q 2>&1 | tail -30
```

Expected: only the pre-existing 18 env-pollution failures remain (from `test_config`, `test_main`, `test_oauth_endpoints`, `test_web_routes`, some `test_coverage_boost*` classes that load Settings). All pagination/envelope tests pass.

- [ ] **Step 7.7: Commit**

```bash
git add src/pco_mcp/pco/services.py src/pco_mcp/tools/services.py tests/test_pco_services.py tests/test_pco_services_write.py tests/test_tools_services_body.py tests/test_coverage_boost2.py
git commit -m "$(cat <<'EOF'
feat(services): finish envelope migration for remaining read methods

get_song_schedule_history, list_song_arrangements, list_plan_templates,
get_needed_positions, list_attachments, list_media, and
flag_missing_ccli all return {items, meta} envelopes.
get_plan_details stays a single-resource dict but now logs truncation
warnings for internal items/team_members paginated fetches.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Cross-cutting envelope tests + search docstring lint

Final cross-cutting regression guards.

**Files:**
- Create: `tests/test_envelope.py`

- [ ] **Step 8.1: Write cross-cutting envelope tests**

Create `tests/test_envelope.py`:

```python
"""Cross-cutting tests that hold every module to the envelope contract."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pco_mcp.pco.client import PCOClient, PagedResult


def _fake_access_token(token: str = "test-pco-token"):
    at = MagicMock()
    at.token = token
    return at


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


@pytest.fixture(autouse=True)
def setup_context(mock_client: PCOClient) -> None:
    with patch(
        "pco_mcp.tools._context.get_access_token",
        return_value=_fake_access_token(),
    ), patch(
        "pco_mcp.tools._context.PCOClient",
        return_value=mock_client,
    ):
        yield


def _get_tool_fn(mcp, name):
    for k, v in mcp._local_provider._components.items():
        if k.startswith("tool:") and v.name == name:
            return v.fn
    raise KeyError(f"Tool {name!r} not found")


def _make_all_mcp():
    """Build a FastMCP with every module's tools registered."""
    from fastmcp import FastMCP
    from pco_mcp.tools.calendar import register_calendar_tools
    from pco_mcp.tools.checkins import register_checkins_tools
    from pco_mcp.tools.people import register_people_tools
    from pco_mcp.tools.services import register_services_tools
    mcp = FastMCP("test")
    register_calendar_tools(mcp)
    register_checkins_tools(mcp)
    register_people_tools(mcp)
    register_services_tools(mcp)
    return mcp


# Tools that return envelopes (list-returning). This list MUST be kept in
# sync when new list tools are added. A missing entry silently skips
# coverage — a new entry that doesn't exist fails loudly in the tests.
ENVELOPE_TOOLS: list[tuple[str, dict]] = [
    ("list_calendar_events", {}),
    ("list_checkin_events", {}),
    ("get_event_attendance", {"event_id": "1"}),
    ("get_headcounts", {"event_id": "1"}),
    ("search_people", {"name": "x"}),
    ("list_lists", {}),
    # Add more as tool names are verified; empty-list is acceptable here
    # for tools whose arg shape is best covered in their own test files.
]


class TestTruncationPropagation:
    @pytest.mark.parametrize("tool_name,args", ENVELOPE_TOOLS)
    async def test_meta_truncated_surfaces_to_caller(
        self, mock_client: AsyncMock, tool_name: str, args: dict,
    ) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=15000, truncated=True,
        )
        # get_headcounts also calls .get for per-period detail — stub it
        mock_client.get.return_value = {"data": []}
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, tool_name)
        result = await fn(**args)
        assert isinstance(result, dict), f"{tool_name} must return a dict"
        assert "meta" in result, f"{tool_name} missing meta"
        assert result["meta"]["truncated"] is True, (
            f"{tool_name} did not propagate truncated signal"
        )
        assert result["meta"]["total_count"] == 15000, (
            f"{tool_name} did not propagate total_count"
        )


class TestIncludeWiring:
    async def test_calendar_list_events_sends_include(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_calendar_events")
        await fn()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "event_instances" in call_params["include"]
        assert "owner" in call_params["include"]

    async def test_services_list_team_members_sends_include(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_team_members")
        # Tool signature — adjust kwargs to match actual registered tool
        try:
            await fn(service_type_id="1", plan_id="1")
        except TypeError:
            # Fallback in case the registered tool uses different arg names
            await fn("1", "1")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "person" in call_params["include"]
        assert "team_position" in call_params["include"]


class TestSearchDocstringLint:
    """Regression guard: search/query tools must flag their match semantics."""

    def test_list_songs_docstring_mentions_exact_match(self) -> None:
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_songs")
        doc = fn.__doc__ or ""
        doc_lower = doc.lower()
        assert "exact" in doc_lower or "pco search" in doc_lower, (
            "list_songs docstring must tell the model the query is exact-match, "
            "not substring. Current docstring: " + repr(doc[:200])
        )

    def test_search_people_docstring_mentions_search_semantics(self) -> None:
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "search_people")
        doc = fn.__doc__ or ""
        doc_lower = doc.lower()
        assert "pco" in doc_lower and ("search" in doc_lower or "fuzzy" in doc_lower), (
            "search_people docstring must document PCO's search behavior. "
            "Current docstring: " + repr(doc[:200])
        )
```

- [ ] **Step 8.2: Run cross-cutting tests**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/test_envelope.py -v
```

Expected: all green. If `TestTruncationPropagation` fails for a tool, the tool is not propagating `meta.truncated` — fix the tool (likely a missed spot in Task 3–7). If `TestSearchDocstringLint` fails, the docstring is too vague — rewrite it.

- [ ] **Step 8.3: Run the full suite one last time**

```bash
cd /home/christian/apps/pco-mcp && uv run pytest tests/ -q 2>&1 | tail -30
```

Expected: only the pre-existing 18 env-pollution failures remain. Every pagination/envelope test green.

- [ ] **Step 8.4: Commit**

```bash
git add tests/test_envelope.py
git commit -m "$(cat <<'EOF'
test: cross-cutting envelope + docstring lint

Parametrized tests verify every list tool propagates meta.truncated
and meta.total_count. Docstring lint catches regressions where a
search/query tool fails to document its match semantics.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Out of Scope

- Changes to `config.py`, `oauth.py`, `main.py`, web routes — pure data-layer refactor.
- New PCO API surface (no new endpoints or tools beyond those already registered).
- A debug `raw_pco_get(path, params)` escape hatch — deferred until a concrete need arises.
- Backfilling truncation signals into `get_plan_details` / `get_person_details` nested arrays — these single-resource composites log warnings on truncation but do not propagate. If a real PCO tenant hits this, revisit.
- Pre-existing 18 env-pollution test failures in `test_config`, `test_main`, `test_oauth_endpoints`, `test_web_routes`, and some `test_coverage_boost*` classes — unrelated to this work, handled separately.

## Notes for the implementer

- **Tests first.** Every task is written TDD-style. Write the failing test, run it red, then write the implementation. Don't skip the red check — it confirms the test actually exercises the code path.
- **One task = one commit.** The commits are small and narrative. If a task's scope blows up mid-implementation, stop and surface the problem rather than shipping a mega-commit.
- **Fixture shape matters.** When a method gains `?include=`, the test fixture MUST include an `included` array or the simplified record won't have the flattened fields. Tasks 3 and 6 call out the fixture updates explicitly.
- **PagedResult is list-like by design.** Existing code that iterates `await client.get_all(...)` keeps working without changes. That's the whole point of Task 1's list-shim: migrations can happen module-by-module.
- **filters_applied semantics.** Strip `include`, `order`, `per_page` from the dict — they're implementation details, not scoping filters. The model should see only filters that affect *what records* were returned.
- **Docstring quality is the model's primary interface.** The envelope shape, default filter, and override params must all be in the docstring. If the docstring doesn't say it, the model can't use it.
