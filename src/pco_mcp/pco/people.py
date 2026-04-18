import logging
from typing import Any

from pco_mcp.pco._envelope import make_envelope, merge_filters
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
    ) -> dict[str, Any]:
        """Search for people by name/email/phone. Returns envelope ``{items, meta}``.

        Uses PCO's ``search_name_or_email`` param which matches both names and
        email addresses with partial/fuzzy behavior. The ``phone`` param falls
        back to the same search field — PCO's behavior may not always match
        on phone, so verify returned records. When ``email`` and ``phone`` are
        both supplied, ``email`` takes priority.
        """
        defaults: dict[str, Any] = {}
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
        return make_envelope(result, simplified, params)

    async def get_person(self, person_id: str) -> dict[str, Any]:
        """Get full details for a person by ID (single-resource dict)."""
        api_result = await self._client.get(f"/people/v2/people/{person_id}")
        return self._simplify_person(api_result["data"])

    async def list_lists(self) -> dict[str, Any]:
        """Get all PCO Lists. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all("/people/v2/lists", params=params)
        simplified = [self._simplify_list(lst) for lst in result.items]
        return make_envelope(result, simplified, params)

    async def get_list_members(self, list_id: str) -> dict[str, Any]:
        """Get people in a specific list. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all(
            f"/people/v2/lists/{list_id}/people", params=params,
        )
        simplified = [self._simplify_person(p) for p in result.items]
        return make_envelope(result, simplified, params)

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
        logger.info(
            "Email assignment failed for %s %s, retrying without email", first_name, last_name
        )
        attributes.pop("email_addresses", None)
        result = await self._client.post("/people/v2/people", data=payload)
        person = self._simplify_person(result["data"])

        # Try adding the email as a separate resource
        try:
            await self._client.post(
                f"/people/v2/people/{person['id']}/emails",
                data={
                    "data": {
                        "type": "Email",
                        "attributes": {"address": email, "location": "Home", "primary": True},
                    }
                },
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

    async def add_email(
        self,
        person_id: str,
        address: str,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Add an email address to a person."""
        attributes: dict[str, Any] = {"address": address}
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "Email", "attributes": attributes}}
        result = await self._client.post(f"/people/v2/people/{person_id}/emails", data=payload)
        return self._simplify_email(result["data"])

    async def update_email(
        self,
        person_id: str,
        email_id: str,
        address: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update an email address."""
        attributes: dict[str, Any] = {}
        if address is not None:
            attributes["address"] = address
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "Email", "attributes": attributes}}
        result = await self._client.patch(
            f"/people/v2/people/{person_id}/emails/{email_id}", data=payload
        )
        return self._simplify_email(result["data"])

    async def add_phone_number(
        self,
        person_id: str,
        number: str,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Add a phone number to a person."""
        attributes: dict[str, Any] = {"number": number}
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "PhoneNumber", "attributes": attributes}}
        result = await self._client.post(
            f"/people/v2/people/{person_id}/phone_numbers", data=payload
        )
        return self._simplify_phone(result["data"])

    async def update_phone_number(
        self,
        person_id: str,
        phone_id: str,
        number: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update a phone number."""
        attributes: dict[str, Any] = {}
        if number is not None:
            attributes["number"] = number
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "PhoneNumber", "attributes": attributes}}
        result = await self._client.patch(
            f"/people/v2/people/{person_id}/phone_numbers/{phone_id}", data=payload
        )
        return self._simplify_phone(result["data"])

    async def add_address(
        self,
        person_id: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Add an address to a person."""
        attributes: dict[str, Any] = {
            "street": street, "city": city, "state": state, "zip": zip_code,
        }
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "Address", "attributes": attributes}}
        result = await self._client.post(f"/people/v2/people/{person_id}/addresses", data=payload)
        return self._simplify_address(result["data"])

    async def update_address(
        self,
        person_id: str,
        address_id: str,
        street: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update an address."""
        attributes: dict[str, Any] = {}
        if street is not None:
            attributes["street"] = street
        if city is not None:
            attributes["city"] = city
        if state is not None:
            attributes["state"] = state
        if zip_code is not None:
            attributes["zip"] = zip_code
        if location is not None:
            attributes["location"] = location
        if is_primary is not None:
            attributes["primary"] = is_primary
        payload: dict[str, Any] = {"data": {"type": "Address", "attributes": attributes}}
        result = await self._client.patch(
            f"/people/v2/people/{person_id}/addresses/{address_id}", data=payload
        )
        return self._simplify_address(result["data"])

    async def get_person_details(self, person_id: str) -> dict[str, Any]:
        """Get all contact details for a person. Single-resource dict (no envelope).

        Nested lists (emails, phone_numbers, addresses) are bare arrays —
        they're part of the person's curated schema. If any of these internal
        fetches hits the max_pages cap (very rare), a warning is logged but
        not propagated to the caller.
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
        """Get blockout dates for a person. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all(
            f"/people/v2/people/{person_id}/blockouts", params=params,
        )
        simplified = [self._simplify_blockout(b) for b in result.items]
        return make_envelope(result, simplified, params)

    async def add_blockout(
        self,
        person_id: str,
        description: str,
        starts_at: str,
        ends_at: str,
        repeat_frequency: str | None = None,
        repeat_until: str | None = None,
    ) -> dict[str, Any]:
        """Create a blockout date for a person."""
        attributes: dict[str, Any] = {
            "description": description,
            "starts_at": starts_at,
            "ends_at": ends_at,
        }
        if repeat_frequency is not None:
            attributes["repeat_frequency"] = repeat_frequency
        if repeat_until is not None:
            attributes["repeat_until"] = repeat_until
        payload: dict[str, Any] = {"data": {"type": "Blockout", "attributes": attributes}}
        result = await self._client.post(f"/people/v2/people/{person_id}/blockouts", data=payload)
        return self._simplify_blockout(result["data"])

    async def add_note(
        self, person_id: str, note: str, note_category_id: str | None = None
    ) -> dict[str, Any]:
        """Add a note to a person."""
        attributes: dict[str, Any] = {"note": note}
        if note_category_id is not None:
            attributes["note_category_id"] = note_category_id
        payload: dict[str, Any] = {"data": {"type": "Note", "attributes": attributes}}
        result = await self._client.post(f"/people/v2/people/{person_id}/notes", data=payload)
        return self._simplify_note(result["data"])

    async def get_notes(self, person_id: str) -> dict[str, Any]:
        """Get notes for a person (most recent first). Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {"order": "-created_at"}
        result = await self._client.get_all(
            f"/people/v2/people/{person_id}/notes", params=params,
        )
        simplified = [self._simplify_note(n) for n in result.items]
        return make_envelope(result, simplified, params)

    async def get_workflows(self) -> dict[str, Any]:
        """List all workflows for the org. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all("/people/v2/workflows", params=params)
        simplified = [self._simplify_workflow(w) for w in result.items]
        return make_envelope(result, simplified, params)

    async def add_person_to_workflow(self, workflow_id: str, person_id: str) -> dict[str, Any]:
        """Add a person to a workflow (creates a card at the first step)."""
        payload: dict[str, Any] = {
            "data": {
                "type": "Card",
                "attributes": {"person_id": int(person_id)},
            }
        }
        result = await self._client.post(f"/people/v2/workflows/{workflow_id}/cards", data=payload)
        return self._simplify_workflow_card(result["data"])

    def _simplify_workflow(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "completed_card_count": attrs.get("completed_card_count", 0),
            "ready_card_count": attrs.get("ready_card_count", 0),
            "total_cards_count": attrs.get("total_cards_count", 0),
        }

    def _simplify_workflow_card(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        person_data = raw.get("relationships", {}).get("person", {}).get("data", {})
        return {
            "id": raw["id"],
            "stage": attrs.get("stage"),
            "created_at": attrs.get("created_at"),
            "completed_at": attrs.get("completed_at"),
            "person_id": person_data.get("id"),
        }

    def _simplify_person(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Curated person record (curated-but-complete).

        Kept: id, first_name, last_name, name, emails[] (all addresses),
        phone_numbers[] (all numbers), membership, status, birthdate, gender,
        created_at, avatar, site_administrator.
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

    def _simplify_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API list record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": attrs.get("description"),
            "total_count": attrs.get("total_count", 0),
        }

    def _simplify_email(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API email record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "address": attrs.get("address", ""),
            "location": attrs.get("location"),
            "primary": attrs.get("primary", False),
        }

    def _simplify_phone(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API phone number record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "number": attrs.get("number", ""),
            "carrier": attrs.get("carrier"),
            "location": attrs.get("location"),
            "primary": attrs.get("primary", False),
        }

    def _simplify_address(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API address record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "street": attrs.get("street", ""),
            "city": attrs.get("city", ""),
            "state": attrs.get("state", ""),
            "zip": attrs.get("zip", ""),
            "location": attrs.get("location"),
            "primary": attrs.get("primary", False),
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

    def _simplify_note(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten a JSON:API note record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "note": attrs.get("note", ""),
            "created_at": attrs.get("created_at"),
            "note_category_id": attrs.get("note_category_id"),
        }
