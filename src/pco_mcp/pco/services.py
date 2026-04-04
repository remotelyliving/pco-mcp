from pco_mcp.pco.client import PCOClient


class ServicesAPI:
    """Wrapper for PCO Services module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def list_service_types(self) -> list[dict]:
        """List all service types."""
        result = await self._client.get("/services/v2/service_types")
        return [self._simplify_service_type(st) for st in result.get("data", [])]

    async def get_upcoming_plans(self, service_type_id: str) -> list[dict]:
        """Get upcoming plans for a service type."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans",
            params={"filter": "future", "order": "sort_date"},
        )
        return [self._simplify_plan(p) for p in result.get("data", [])]

    async def get_plan_details(self, service_type_id: str, plan_id: str) -> dict:
        """Get full details for a specific plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        )
        return self._simplify_plan(result["data"])

    async def list_songs(self, query: str | None = None) -> list[dict]:
        """List/search songs in the library."""
        params: dict = {}
        if query:
            params["where[title]"] = query
        result = await self._client.get("/services/v2/songs", params=params)
        return [self._simplify_song(s) for s in result.get("data", [])]

    async def list_team_members(self, service_type_id: str, plan_id: str) -> list[dict]:
        """List team members for a plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members"
        )
        return [self._simplify_team_member(tm) for tm in result.get("data", [])]

    async def schedule_team_member(
        self, service_type_id: str, plan_id: str, person_id: str, team_position_name: str
    ) -> dict:
        """Schedule a person to a team position in a plan."""
        payload = {
            "data": {
                "type": "PlanPerson",
                "attributes": {
                    "person_id": int(person_id),
                    "team_position_name": team_position_name,
                },
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            data=payload,
        )
        return self._simplify_team_member(result["data"])

    def _simplify_service_type(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "last_plan_from": attrs.get("last_plan_from"),
        }

    def _simplify_plan(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "dates": attrs.get("dates", ""),
            "sort_date": attrs.get("sort_date"),
            "items_count": attrs.get("items_count", 0),
            "needed_positions_count": attrs.get("needed_positions_count", 0),
        }

    def _simplify_song(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "author": attrs.get("author"),
            "ccli_number": attrs.get("ccli_number"),
            "last_scheduled_at": attrs.get("last_scheduled_at"),
        }

    def _simplify_team_member(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "person_name": attrs.get("name", ""),
            "team_position_name": attrs.get("team_position_name"),
            "status": attrs.get("status"),
            "notification_sent_at": attrs.get("notification_sent_at"),
        }
