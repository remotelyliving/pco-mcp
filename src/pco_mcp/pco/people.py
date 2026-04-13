import logging
from typing import Any

from pco_mcp.pco.client import PCOAPIError, PCOClient

logger = logging.getLogger(__name__)


class PeopleAPI:
    """Wrapper for PCO People module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def search_people(
        self,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for people. Returns simplified records."""
        params: dict[str, Any] = {}
        if name:
            params["where[search_name]"] = name
        if email and phone:
            import warnings
            warnings.warn(
                "Both email and phone provided to search_people; email takes priority.",
                stacklevel=2,
            )
        if email:
            params["where[search_name_or_email]"] = email
        elif phone:
            params["where[search_name_or_email]"] = phone
        result = await self._client.get("/people/v2/people", params=params)
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def get_person(self, person_id: str) -> dict[str, Any]:
        """Get full details for a person by ID."""
        result = await self._client.get(f"/people/v2/people/{person_id}")
        return self._simplify_person(result["data"])

    async def list_lists(self) -> list[dict[str, Any]]:
        """Get all PCO Lists."""
        result = await self._client.get("/people/v2/lists")
        return [self._simplify_list(lst) for lst in result.get("data", [])]

    async def get_list_members(self, list_id: str) -> list[dict[str, Any]]:
        """Get people in a specific list."""
        result = await self._client.get(f"/people/v2/lists/{list_id}/people")
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def create_person(
        self, first_name: str, last_name: str, email: str | None = None
    ) -> dict[str, Any]:
        """Create a new person record.

        If email assignment fails (e.g., the email belongs to an existing PCO
        login), the person is created without email and then we attempt to add
        it separately. If that also fails, the person is returned with a note
        explaining the email must be linked via the PCO web UI.
        """
        attributes: dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
        }
        if email:
            attributes["email_addresses"] = [{"address": email}]
        payload: dict[str, Any] = {
            "data": {
                "type": "Person",
                "attributes": attributes,
            }
        }

        try:
            result = await self._client.post("/people/v2/people", data=payload)
            return self._simplify_person(result["data"])
        except PCOAPIError as e:
            if e.status_code != 422 or not email or "email" not in e.detail.lower():
                raise

        # Retry without email
        logger.info("Email assignment failed for %s %s, retrying without email", first_name, last_name)
        attributes.pop("email_addresses", None)
        result = await self._client.post("/people/v2/people", data=payload)
        person = self._simplify_person(result["data"])

        # Try adding the email as a separate resource
        try:
            await self._client.post(
                f"/people/v2/people/{person['id']}/emails",
                data={"data": {"type": "Email", "attributes": {"address": email, "location": "Home", "primary": True}}},
            )
            person["email"] = email
            return person
        except PCOAPIError:
            logger.info("Separate email assignment also failed for person %s", person["id"])
            person["_warning"] = (
                f"Person created but the email '{email}' could not be assigned — "
                "it belongs to an existing Planning Center account. "
                "To link this email, go to the person's profile in the Planning Center web app."
            )
            return person

    async def update_person(self, person_id: str, **fields: str) -> dict[str, Any]:
        """Update fields on an existing person."""
        payload: dict[str, Any] = {
            "data": {
                "type": "Person",
                "id": person_id,
                "attributes": fields,
            }
        }
        result = await self._client.patch(f"/people/v2/people/{person_id}", data=payload)
        return self._simplify_person(result["data"])

    async def get_person_blockouts(self, person_id: str) -> list[dict[str, Any]]:
        """Get blockout dates for a person."""
        result = await self._client.get(f"/people/v2/people/{person_id}/blockouts")
        return [self._simplify_blockout(b) for b in result.get("data", [])]

    def _simplify_person(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API person record into a simple dict."""
        attrs = raw.get("attributes", {})
        emails = attrs.get("email_addresses", [])
        phones = attrs.get("phone_numbers", [])
        return {
            "id": raw["id"],
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "email": emails[0]["address"] if emails else None,
            "phone": phones[0]["number"] if phones else None,
            "membership": attrs.get("membership"),
            "status": attrs.get("status"),
            "birthdate": attrs.get("birthdate"),
            "gender": attrs.get("gender"),
        }

    def _simplify_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API list record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": attrs.get("description"),
            "total_count": attrs.get("total_count", 0),
        }

    def _simplify_blockout(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API blockout record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "description": attrs.get("description", ""),
            "reason": attrs.get("reason", ""),
            "repeat_frequency": attrs.get("repeat_frequency"),
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
        }
