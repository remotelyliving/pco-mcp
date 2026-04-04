from pco_mcp.pco.client import PCOClient


class PeopleAPI:
    """Wrapper for PCO People module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def search_people(
        self,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict]:
        """Search for people. Returns simplified records."""
        params: dict = {}
        if name:
            params["where[search_name]"] = name
        if email:
            params["where[search_name_or_email]"] = email
        if phone:
            params["where[search_name_or_email]"] = phone
        result = await self._client.get("/people/v2/people", params=params)
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def get_person(self, person_id: str) -> dict:
        """Get full details for a person by ID."""
        result = await self._client.get(f"/people/v2/people/{person_id}")
        return self._simplify_person(result["data"])

    async def list_lists(self) -> list[dict]:
        """Get all PCO Lists."""
        result = await self._client.get("/people/v2/lists")
        return [self._simplify_list(lst) for lst in result.get("data", [])]

    async def get_list_members(self, list_id: str) -> list[dict]:
        """Get people in a specific list."""
        result = await self._client.get(f"/people/v2/lists/{list_id}/people")
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def create_person(self, first_name: str, last_name: str, email: str | None = None) -> dict:
        """Create a new person record."""
        payload = {
            "data": {
                "type": "Person",
                "attributes": {
                    "first_name": first_name,
                    "last_name": last_name,
                },
            }
        }
        if email:
            payload["data"]["attributes"]["email_addresses"] = [{"address": email}]
        result = await self._client.post("/people/v2/people", data=payload)
        return self._simplify_person(result["data"])

    async def update_person(self, person_id: str, **fields: str) -> dict:
        """Update fields on an existing person."""
        payload = {
            "data": {
                "type": "Person",
                "id": person_id,
                "attributes": fields,
            }
        }
        result = await self._client.patch(f"/people/v2/people/{person_id}", data=payload)
        return self._simplify_person(result["data"])

    def _simplify_person(self, raw: dict) -> dict:
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
        }

    def _simplify_list(self, raw: dict) -> dict:
        """Flatten a JSON:API list record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": attrs.get("description"),
            "total_count": attrs.get("total_count", 0),
        }
