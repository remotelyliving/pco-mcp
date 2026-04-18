from typing import Any

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
    ) -> list[dict[str, Any]]:
        """List calendar events. Defaults to future events."""
        params: dict[str, Any] = {"order": "starts_at"}
        if featured_only:
            params["filter"] = "featured,future"
        else:
            params["filter"] = "future"
        if start_date:
            params["where[starts_at][gte]"] = start_date
        if end_date:
            params["where[starts_at][lte]"] = end_date
        all_events = await self._client.get_all("/calendar/v2/events", params=params)
        return [self._simplify_event(e) for e in all_events]

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event detail with instances and resource bookings."""
        base = f"/calendar/v2/events/{event_id}"
        event_result = await self._client.get(base)
        instances = await self._client.get_all(f"{base}/event_instances")
        resources = await self._client.get_all(f"{base}/event_resource_requests")
        event = self._simplify_event(event_result["data"])
        event["instances"] = [self._simplify_instance(i) for i in instances]
        event["resources"] = [self._simplify_resource(r) for r in resources]
        return event

    def _simplify_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        desc = attrs.get("description") or ""
        if len(desc) > 200:
            desc = desc[:197] + "..."
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": desc,
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
            "recurrence": attrs.get("recurrence"),
            "visible_in_church_center": attrs.get("visible_in_church_center", False),
        }

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
