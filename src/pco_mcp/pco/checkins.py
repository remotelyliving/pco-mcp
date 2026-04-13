from typing import Any

from pco_mcp.pco.client import PCOClient


class CheckInsAPI:
    """Wrapper for PCO Check-ins module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def get_events(self) -> list[dict[str, Any]]:
        """List all check-in events (non-archived)."""
        result = await self._client.get(
            "/check-ins/v2/events",
            params={"where[archived_at]": ""},
        )
        return [self._simplify_event(e) for e in result.get("data", [])]

    async def get_event_checkins(
        self,
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get check-in records for an event, optionally filtered by date. Capped at ~500 records."""
        params: dict[str, Any] = {"per_page": 25}
        if start_date:
            params["where[created_at][gte]"] = start_date
        if end_date:
            params["where[created_at][lte]"] = end_date
        all_checkins = await self._client.get_all(
            f"/check-ins/v2/events/{event_id}/check_ins",
            params=params,
            max_pages=20,
        )
        return [self._simplify_checkin(c) for c in all_checkins]

    def _simplify_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "created_at": attrs.get("created_at"),
            "archived": attrs.get("archived_at") is not None,
        }

    def _simplify_checkin(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "created_at": attrs.get("created_at"),
            "security_code": attrs.get("security_code"),
        }
