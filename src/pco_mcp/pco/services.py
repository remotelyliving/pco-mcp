from typing import Any

from pco_mcp.pco.client import PCOClient


class ServicesAPI:
    """Wrapper for PCO Services module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def list_service_types(self) -> list[dict[str, Any]]:
        """List all service types."""
        result = await self._client.get("/services/v2/service_types")
        return [self._simplify_service_type(st) for st in result.get("data", [])]

    async def get_upcoming_plans(self, service_type_id: str) -> list[dict[str, Any]]:
        """Get upcoming plans for a service type (all pages)."""
        data = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans",
            params={"filter": "future", "order": "sort_date"},
        )
        return [self._simplify_plan(p) for p in data]

    async def get_plan_details(self, service_type_id: str, plan_id: str) -> dict[str, Any]:
        """Get full details for a specific plan, including items and team members."""
        base = f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        result = await self._client.get(base)
        plan = self._simplify_plan(result["data"])
        # Fetch items (songs/elements in the service order)
        items_result = await self._client.get(f"{base}/items")
        plan["items"] = [self._simplify_item(i) for i in items_result.get("data", [])]
        # Fetch team members
        team_result = await self._client.get(f"{base}/team_members")
        plan["team_members"] = [self._simplify_team_member(tm) for tm in team_result.get("data", [])]
        return plan

    async def list_songs(self, query: str | None = None) -> list[dict[str, Any]]:
        """List/search songs in the library.

        Note: PCO's ``where[title]`` filter performs an exact match.
        For partial/fuzzy matching, iterate client-side or omit the query
        to fetch all songs.
        """
        params: dict[str, Any] = {}
        if query:
            params["where[title]"] = query
        result = await self._client.get("/services/v2/songs", params=params)
        return [self._simplify_song(s) for s in result.get("data", [])]

    async def list_team_members(self, service_type_id: str, plan_id: str) -> list[dict[str, Any]]:
        """List team members for a plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members"
        )
        return [self._simplify_team_member(tm) for tm in result.get("data", [])]

    async def schedule_team_member(
        self, service_type_id: str, plan_id: str, person_id: str, team_position_name: str
    ) -> dict[str, Any]:
        """Schedule a person to a team position in a plan."""
        payload: dict[str, Any] = {
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

    async def create_plan(
        self, service_type_id: str, title: str, sort_date: str
    ) -> dict[str, Any]:
        """Create a new plan for a service type."""
        payload: dict[str, Any] = {
            "data": {
                "type": "Plan",
                "attributes": {
                    "title": title,
                    "sort_date": sort_date,
                },
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans", data=payload
        )
        return self._simplify_plan(result["data"])

    async def create_plan_time(
        self,
        service_type_id: str,
        plan_id: str,
        starts_at: str,
        ends_at: str,
        name: str | None = None,
        time_type: str = "service",
    ) -> dict[str, Any]:
        """Create a time entry on a plan."""
        attributes: dict[str, Any] = {
            "starts_at": starts_at,
            "ends_at": ends_at,
            "time_type": time_type,
        }
        if name:
            attributes["name"] = name
        payload: dict[str, Any] = {
            "data": {
                "type": "PlanTime",
                "attributes": attributes,
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/plan_times",
            data=payload,
        )
        return self._simplify_plan_time(result["data"])

    async def list_plan_items(
        self, service_type_id: str, plan_id: str
    ) -> list[dict[str, Any]]:
        """List items (songs/elements) on a plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items"
        )
        return [self._simplify_item(i) for i in result.get("data", [])]

    async def add_item_to_plan(
        self,
        service_type_id: str,
        plan_id: str,
        title: str | None = None,
        song_id: str | None = None,
        arrangement_id: str | None = None,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        """Add an item (song or custom element) to a plan."""
        attributes: dict[str, Any] = {}
        if title:
            attributes["title"] = title
        if song_id:
            attributes["song_id"] = int(song_id)
        if arrangement_id:
            attributes["arrangement_id"] = int(arrangement_id)
        if key_id:
            attributes["key_id"] = int(key_id)
        payload: dict[str, Any] = {
            "data": {
                "type": "Item",
                "attributes": attributes,
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            data=payload,
        )
        return self._simplify_item(result["data"])

    async def remove_item_from_plan(
        self, service_type_id: str, plan_id: str, item_id: str
    ) -> None:
        """Remove an item from a plan."""
        await self._client.delete(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items/{item_id}"
        )

    async def list_teams(self, service_type_id: str) -> list[dict[str, Any]]:
        """List teams for a service type."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/teams"
        )
        return [self._simplify_team(t) for t in result.get("data", [])]

    async def list_team_positions(self, team_id: str) -> list[dict[str, Any]]:
        """List positions for a team."""
        result = await self._client.get(
            f"/services/v2/teams/{team_id}/team_positions"
        )
        return [self._simplify_position(p) for p in result.get("data", [])]

    async def remove_team_member(
        self, service_type_id: str, plan_id: str, team_member_id: str
    ) -> None:
        """Remove a team member from a plan."""
        await self._client.delete(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members/{team_member_id}"
        )

    async def get_song_schedule_history(self, song_id: str) -> list[dict[str, Any]]:
        """Get schedule history for a song."""
        result = await self._client.get(
            f"/services/v2/songs/{song_id}/song_schedules"
        )
        return [self._simplify_song_schedule(s) for s in result.get("data", [])]

    async def list_song_arrangements(self, song_id: str) -> list[dict[str, Any]]:
        """List arrangements for a song."""
        result = await self._client.get(
            f"/services/v2/songs/{song_id}/arrangements"
        )
        return [self._simplify_arrangement(a) for a in result.get("data", [])]

    async def list_plan_templates(self, service_type_id: str) -> list[dict[str, Any]]:
        """List plan templates for a service type."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plan_templates"
        )
        return [self._simplify_template(t) for t in result.get("data", [])]

    async def get_needed_positions(
        self, service_type_id: str, plan_id: str
    ) -> list[dict[str, Any]]:
        """Get needed (unfilled) positions for a plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/needed_positions"
        )
        return [self._simplify_needed_position(np) for np in result.get("data", [])]

    def _simplify_service_type(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "last_plan_from": attrs.get("last_plan_from"),
        }

    def _simplify_plan(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "dates": attrs.get("dates", ""),
            "sort_date": attrs.get("sort_date"),
            "items_count": attrs.get("items_count", 0),
            "needed_positions_count": attrs.get("needed_positions_count", 0),
        }

    def _simplify_song(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "author": attrs.get("author"),
            "ccli_number": attrs.get("ccli_number"),
            "last_scheduled_at": attrs.get("last_scheduled_at"),
        }

    def _simplify_team_member(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "person_name": attrs.get("name", ""),
            "team_position_name": attrs.get("team_position_name"),
            "status": attrs.get("status"),
            "notification_sent_at": attrs.get("notification_sent_at"),
        }

    def _simplify_item(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "sequence": attrs.get("sequence"),
            "item_type": attrs.get("item_type"),
            "length": attrs.get("length"),
            "song_id": attrs.get("song_id"),
            "description": attrs.get("description"),
            "service_position": attrs.get("service_position"),
        }

    def _simplify_plan_time(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "time_type": attrs.get("time_type"),
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
        }

    def _simplify_team(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "schedule_to": attrs.get("schedule_to"),
            "rehearsal_team": attrs.get("rehearsal_team", False),
        }

    def _simplify_position(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "tags": attrs.get("tags", []),
        }

    def _simplify_song_schedule(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "plan_dates": attrs.get("plan_dates"),
            "plan_sort_date": attrs.get("plan_sort_date"),
            "service_type_name": attrs.get("service_type_name"),
            "arrangement_name": attrs.get("arrangement_name"),
            "key_name": attrs.get("key_name"),
        }

    def _simplify_arrangement(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "bpm": attrs.get("bpm"),
            "length": attrs.get("length"),
            "meter": attrs.get("meter"),
            "notes": attrs.get("notes"),
        }

    def _simplify_template(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "item_count": attrs.get("item_count", 0),
            "team_count": attrs.get("team_count", 0),
        }

    def _simplify_needed_position(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "team_position_name": attrs.get("team_position_name", ""),
            "quantity": attrs.get("quantity", 0),
            "scheduled_to": attrs.get("scheduled_to"),
        }
