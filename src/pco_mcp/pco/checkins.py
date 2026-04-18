from typing import Any

from pco_mcp.pco._envelope import make_envelope, merge_filters
from pco_mcp.pco.client import PCOClient


class CheckInsAPI:
    """Wrapper for PCO Check-ins module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def get_events(self, include_archived: bool = False) -> dict[str, Any]:
        """List check-in events. Returns envelope `{items, meta}`.

        Defaults to active (non-archived) events by forcing
        `where[archived_at]=""`. Pass `include_archived=True` to drop that
        default and include archived events. `meta.filters_applied` reports
        the scoping actually sent to PCO.
        """
        defaults: dict[str, Any] = {"where[archived_at]": ""}
        overrides: dict[str, Any] = {}
        if include_archived:
            overrides["where[archived_at]"] = None
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/check-ins/v2/events", params=params)
        simplified = [self._simplify_event(e) for e in result.items]
        return make_envelope(result, simplified, params)

    async def get_event_checkins(
        self,
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get check-in records for an event. Returns envelope `{items, meta}`.

        No default date filter — pass `start_date`/`end_date` (ISO) to scope.
        Records are ordered newest-first; if a very high-volume event hits
        the internal `max_pages` ceiling, `meta.truncated` will be True.
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
        return make_envelope(result, simplified, params)

    async def get_headcounts(
        self,
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get headcount data aggregated by event period. Returns envelope `{items, meta}`.

        Each item is one event period with total attendance and a
        `by_location` breakdown sourced from per-period headcount calls.
        """
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
        return make_envelope(periods_result, aggregated, params)

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
