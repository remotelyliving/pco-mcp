from typing import Any

from pco_mcp.pco._envelope import index_included, make_envelope, merge_filters
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
        included_index = index_included(result.included)
        simplified = [self._simplify_event(e, included_index) for e in result.items]
        return make_envelope(result, simplified, params)

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
