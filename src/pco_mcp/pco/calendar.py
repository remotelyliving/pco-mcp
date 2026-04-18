from typing import Any

from pco_mcp.pco._envelope import index_included, make_envelope, merge_filters
from pco_mcp.pco.client import PCOClient


class CalendarAPI:
    """Wrapper for PCO Calendar module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def get_events(
        self,
        featured_only: bool = False,
        include_past: bool = False,
    ) -> dict[str, Any]:
        """List calendar events. Returns envelope `{items, meta}`.

        Defaults to future events. Pass `include_past=True` to remove the
        future-only filter. Pass `featured_only=True` to restrict to
        featured events.

        NOTE: PCO does not support filtering the event list by start time
        (starts_at/ends_at live on EventInstance, not Event). To find events
        that occur on a specific date, list all events and then use
        `get_event_detail(event_id)` to inspect their instances.
        """
        defaults: dict[str, Any] = {
            "filter": "future",
            "include": "owner",
        }
        overrides: dict[str, Any] = {}
        if featured_only:
            overrides["where[featured]"] = "true"
        if include_past:
            overrides["filter"] = None  # removes the default
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

        Kept: id, name, description (full text), starts_at, ends_at,
        recurrence, visible_in_church_center, owner_id, owner_name (from
        include=owner), instances (from include=event_instances, simplified).
        Dropped: links.*, raw relationships (replaced by flattened fields).
        """
        attrs = raw.get("attributes", {})
        simplified: dict[str, Any] = {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": attrs.get("description") or "",
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
            "recurrence": attrs.get("recurrence"),
            "visible_in_church_center": attrs.get("visible_in_church_center", False),
        }
        rels = raw.get("relationships", {})
        owner_ref = rels.get("owner", {}).get("data")
        if owner_ref:
            owner_id = owner_ref.get("id")
            if owner_id:
                simplified["owner_id"] = owner_id
            if included_index:
                owner_type = owner_ref.get("type")
                if owner_type and owner_id:
                    owner = included_index.get((owner_type, owner_id))
                    if owner:
                        oattrs = owner.get("attributes", {})
                        simplified["owner_name"] = (
                            f"{oattrs.get('first_name', '')} {oattrs.get('last_name', '')}".strip()
                        )
        instance_refs = rels.get("event_instances", {}).get("data") or []
        if instance_refs and included_index:
            instances = []
            for ref in instance_refs:
                ref_type = ref.get("type")
                ref_id = ref.get("id")
                if not (ref_type and ref_id):
                    continue
                inst = included_index.get((ref_type, ref_id))
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
