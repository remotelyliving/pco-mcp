import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI

FIXTURES = Path(__file__).parent / "fixtures" / "people"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def mock_client() -> PCOClient:
    client = AsyncMock(spec=PCOClient)
    return client


class TestSearchPeople:
    async def test_search_by_name(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("search_people.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        mock_client.get_all.assert_called_once()
        call_args = mock_client.get_all.call_args
        assert "/people/v2/people" in call_args.args[0]
        assert len(result["items"]) == 2
        assert result["items"][0]["first_name"] == "Alice"

    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("search_people.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2

    async def test_filters_applied_reports_search(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        assert result["meta"]["filters_applied"].get("where[search_name_or_email]") == "Alice"

    async def test_search_returns_simplified_records(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("search_people.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        record = result["items"][0]
        assert "id" in record
        assert "first_name" in record
        assert "last_name" in record
        assert "emails" in record

    async def test_emails_populated_from_included(self, mock_client: AsyncMock) -> None:
        """After search, returned persons must have populated emails and
        phone_numbers arrays sourced from the JSON:API included records."""
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("search_people.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        alice = result["items"][0]
        assert alice["emails"] == [
            {"address": "alice@example.com", "location": "Home", "primary": True}
        ]
        assert alice["phone_numbers"] == [
            {"number": "555-0101", "location": "Mobile", "primary": True}
        ]
        bob = result["items"][1]
        assert bob["emails"][0]["address"] == "bob@example.com"
        assert bob["phone_numbers"] == []

    async def test_phone_e164_format_routes_to_e164_filter(self, mock_client: AsyncMock) -> None:
        """E.164-formatted phone (starts with +, 8-15 digits) routes to the
        exact-match where[search_phone_number_e164] filter."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.search_people(phone="+15551234567")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[search_phone_number_e164]") == "+15551234567"
        assert "where[search_phone_number]" not in call_params
        assert "where[search_name_or_email]" not in call_params
        assert result["meta"]["filters_applied"].get(
            "where[search_phone_number_e164]"
        ) == "+15551234567"

    async def test_phone_non_e164_routes_to_search_phone_number(self, mock_client: AsyncMock) -> None:
        """Non-E.164 phone formats route to the partial-match
        where[search_phone_number] filter."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.search_people(phone="555-1234")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[search_phone_number]") == "555-1234"
        assert "where[search_phone_number_e164]" not in call_params
        assert "where[search_name_or_email]" not in call_params
        assert result["meta"]["filters_applied"].get(
            "where[search_phone_number]"
        ) == "555-1234"


class TestSimplifyPersonCompleteness:
    async def test_returns_all_emails_and_phones(self, mock_client: AsyncMock) -> None:
        """A person with multiple emails/phones must return them all as arrays."""
        from pco_mcp.pco.client import PagedResult
        raw = {
            "type": "Person",
            "id": "1",
            "attributes": {"first_name": "Alice", "last_name": "Smith"},
            "relationships": {
                "emails": {"data": [
                    {"type": "Email", "id": "10"},
                    {"type": "Email", "id": "11"},
                ]},
                "phone_numbers": {"data": [
                    {"type": "PhoneNumber", "id": "20"},
                    {"type": "PhoneNumber", "id": "21"},
                ]},
            },
        }
        included = [
            {"type": "Email", "id": "10", "attributes": {"address": "a@example.com", "location": "Home", "primary": True}},
            {"type": "Email", "id": "11", "attributes": {"address": "a@work.com", "location": "Work", "primary": False}},
            {"type": "PhoneNumber", "id": "20", "attributes": {"number": "555-0001", "location": "Mobile", "primary": True}},
            {"type": "PhoneNumber", "id": "21", "attributes": {"number": "555-0002", "location": "Home", "primary": False}},
        ]
        mock_client.get_all.return_value = PagedResult(
            items=[raw], total_count=1, truncated=False, included=included,
        )
        api = PeopleAPI(mock_client)
        result = await api.search_people(name="Alice")
        person = result["items"][0]
        assert len(person["emails"]) == 2
        assert person["emails"][0]["address"] == "a@example.com"
        assert person["emails"][1]["address"] == "a@work.com"
        assert len(person["phone_numbers"]) == 2
        assert person["phone_numbers"][0]["number"] == "555-0001"


class TestGetPerson:
    async def test_get_by_id(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        mock_client.get.assert_called_once()
        call_path = mock_client.get.call_args.args[0]
        assert call_path == "/people/v2/people/1001"
        assert person["first_name"] == "Alice"
        assert person["id"] == "1001"

    async def test_sends_include_emails_and_phone_numbers(
        self, mock_client: AsyncMock,
    ) -> None:
        """get_person must send include=emails,phone_numbers so the curated
        record actually has populated contact arrays."""
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        await api.get_person("1001")
        call_kwargs = mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert "emails" in params.get("include", "")
        assert "phone_numbers" in params.get("include", "")

    async def test_populates_emails_and_phones_from_included(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        assert person["emails"] == [
            {"address": "alice@example.com", "location": "Home", "primary": True}
        ]
        assert person["phone_numbers"] == [
            {"number": "555-0101", "location": "Mobile", "primary": True}
        ]


class TestListLists:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_lists.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.list_lists()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "Volunteers"
        assert result["items"][0]["total_count"] == 45


class TestSimplifyPersonIncludesBirthdateGender:
    async def test_get_person_includes_birthdate(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        assert "birthdate" in person
        assert person["birthdate"] == "1990-05-15"

    async def test_get_person_includes_gender(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        assert "gender" in person
        assert person["gender"] == "Female"


class TestGetPersonBlockouts:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_person_blockouts.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_person_blockouts("1001")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["description"] == "Vacation"
        assert result["items"][0]["reason"] == "Out of town"
        assert result["items"][1]["repeat_frequency"] == "weekly"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_person_blockouts.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        await api.get_person_blockouts("1001")
        call_path = mock_client.get_all.call_args.args[0]
        assert "/services/v2/people/1001/blockouts" in call_path

    async def test_blockout_has_expected_fields(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_person_blockouts.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_person_blockouts("1001")
        b = result["items"][0]
        assert "id" in b
        assert "description" in b
        assert "starts_at" in b
        assert "ends_at" in b
        assert "repeat_frequency" in b

    async def test_returns_empty_envelope_when_no_blockouts(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        result = await api.get_person_blockouts("9999")
        assert result["items"] == []
        assert result["meta"]["total_count"] == 0


class TestAddEmail:
    async def test_returns_created_email(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        email = await api.add_email("1001", address="alice@example.com", location="Home", is_primary=True)
        assert email["id"] == "2001"
        assert email["address"] == "alice@example.com"
        assert email["location"] == "Home"
        assert email["primary"] is True

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        await api.add_email("1001", address="alice@example.com")
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/emails" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Email"
        assert data["data"]["attributes"]["address"] == "alice@example.com"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        await api.add_email("1001", address="alice@example.com")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "address" in attrs
        assert "location" not in attrs
        assert "primary" not in attrs


class TestUpdateEmail:
    async def test_returns_updated_email(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_email.json")
        api = PeopleAPI(mock_client)
        email = await api.update_email("1001", "2001", address="alice@work.com", location="Work")
        assert email["address"] == "alice@work.com"
        assert email["location"] == "Work"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_email.json")
        api = PeopleAPI(mock_client)
        await api.update_email("1001", "2001", location="Work")
        call_path = mock_client.patch.call_args.args[0]
        assert "1001" in call_path
        assert "2001" in call_path
        assert "/emails/" in call_path


class TestAddPhoneNumber:
    async def test_returns_created_phone(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_phone_number.json")
        api = PeopleAPI(mock_client)
        phone = await api.add_phone_number("1001", number="5550101", location="Mobile", is_primary=True)
        assert phone["id"] == "3001"
        assert phone["number"] == "5550101"
        assert phone["location"] == "Mobile"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_phone_number.json")
        api = PeopleAPI(mock_client)
        await api.add_phone_number("1001", number="5550101")
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/phone_numbers" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "PhoneNumber"
        assert data["data"]["attributes"]["number"] == "5550101"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_phone_number.json")
        api = PeopleAPI(mock_client)
        await api.add_phone_number("1001", number="5550101")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "number" in attrs
        assert "location" not in attrs


class TestAddAddress:
    async def test_returns_created_address(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_address.json")
        api = PeopleAPI(mock_client)
        addr = await api.add_address("1001", street="123 Main St", city="Springfield", state="IL", zip_code="62701")
        assert addr["id"] == "4001"
        assert addr["street"] == "123 Main St"
        assert addr["city"] == "Springfield"
        assert addr["state"] == "IL"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_address.json")
        api = PeopleAPI(mock_client)
        await api.add_address("1001", street="123 Main St", city="Springfield", state="IL", zip_code="62701", location="Home")
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/addresses" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["street"] == "123 Main St"
        assert attrs["location"] == "Home"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_address.json")
        api = PeopleAPI(mock_client)
        await api.add_address("1001", street="123 Main St", city="Springfield", state="IL", zip_code="62701")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "street" in attrs
        assert "location" not in attrs


class TestUpdateAddress:
    async def test_returns_updated_address(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_address.json")
        api = PeopleAPI(mock_client)
        addr = await api.update_address("1001", "4001", street="456 Oak Ave")
        assert addr["street"] == "456 Oak Ave"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_address.json")
        api = PeopleAPI(mock_client)
        await api.update_address("1001", "4001", zip_code="62702")
        call_path = mock_client.patch.call_args.args[0]
        assert "1001" in call_path
        assert "4001" in call_path
        assert "/addresses/" in call_path


class TestGetPersonDetails:
    async def test_returns_single_resource_dict(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.side_effect = [
            PagedResult(items=load_fixture("list_emails.json")["data"], total_count=1, truncated=False),
            PagedResult(items=load_fixture("list_phone_numbers.json")["data"], total_count=1, truncated=False),
            PagedResult(items=load_fixture("list_addresses.json")["data"], total_count=1, truncated=False),
        ]
        api = PeopleAPI(mock_client)
        details = await api.get_person_details("1001")
        assert "emails" in details
        assert "phone_numbers" in details
        assert "addresses" in details
        assert "items" not in details  # NOT an envelope
        assert "meta" not in details
        assert len(details["emails"]) == 1
        assert details["emails"][0]["address"] == "alice@example.com"
        assert len(details["phone_numbers"]) == 1
        assert details["phone_numbers"][0]["number"] == "5550101"
        assert len(details["addresses"]) == 1
        assert details["addresses"][0]["city"] == "Springfield"

    async def test_calls_three_endpoints(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.side_effect = [
            PagedResult(items=load_fixture("list_emails.json")["data"], total_count=1, truncated=False),
            PagedResult(items=load_fixture("list_phone_numbers.json")["data"], total_count=1, truncated=False),
            PagedResult(items=load_fixture("list_addresses.json")["data"], total_count=1, truncated=False),
        ]
        api = PeopleAPI(mock_client)
        await api.get_person_details("1001")
        assert mock_client.get_all.call_count == 3
        paths = [c.args[0] for c in mock_client.get_all.call_args_list]
        assert any("/emails" in p for p in paths)
        assert any("/phone_numbers" in p for p in paths)
        assert any("/addresses" in p for p in paths)


class TestAddNote:
    async def test_returns_created_note(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_note.json")
        api = PeopleAPI(mock_client)
        note = await api.add_note("1001", note="Had a great conversation about volunteering.")
        assert note["id"] == "5001"
        assert note["note"] == "Had a great conversation about volunteering."

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_note.json")
        api = PeopleAPI(mock_client)
        await api.add_note("1001", note="Test note", note_category_id="100")
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/notes" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["attributes"]["note"] == "Test note"
        assert data["data"]["attributes"]["note_category_id"] == "100"

    async def test_optional_category(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_note.json")
        api = PeopleAPI(mock_client)
        await api.add_note("1001", note="Test note")
        data = mock_client.post.call_args.kwargs["data"]
        assert "note_category_id" not in data["data"]["attributes"]


class TestGetNotes:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_notes.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_notes("1001")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["note"] == "Had a great conversation about volunteering."
        assert result["items"][1]["id"] == "5002"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_notes.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        await api.get_notes("1001")
        call_path = mock_client.get_all.call_args.args[0]
        assert "1001" in call_path
        assert "/notes" in call_path

    async def test_order_param_preserved(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = PeopleAPI(mock_client)
        await api.get_notes("1001")
        call_kwargs = mock_client.get_all.call_args.kwargs
        assert call_kwargs["params"].get("order") == "-created_at"


class TestAddBlockout:
    async def test_returns_created_blockout(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        blockout = await api.add_blockout("1001", description="Family vacation", starts_at="2026-04-20T00:00:00Z", ends_at="2026-04-27T00:00:00Z")
        assert blockout["id"] == "6001"
        assert blockout["description"] == "Family vacation"
        assert blockout["starts_at"] == "2026-04-20T00:00:00Z"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout("1001", description="Family vacation", starts_at="2026-04-20T00:00:00Z", ends_at="2026-04-27T00:00:00Z")
        call_path = mock_client.post.call_args.args[0]
        assert "/services/v2/people/1001/blockouts" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["description"] == "Family vacation"
        assert attrs["starts_at"] == "2026-04-20T00:00:00Z"

    async def test_with_repeat_params(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout("1001", description="Weekly commitment", starts_at="2026-04-20T09:00:00Z", ends_at="2026-04-20T12:00:00Z", repeat_frequency="every_1_week", repeat_until="2026-12-31")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["repeat_frequency"] == "every_1_week"
        assert attrs["repeat_until"] == "2026-12-31"

    async def test_optional_repeat_fields_omitted(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout("1001", description="One-time", starts_at="2026-04-20T00:00:00Z", ends_at="2026-04-21T00:00:00Z")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "repeat_frequency" not in attrs
        assert "repeat_until" not in attrs


class TestUpdatePhoneNumber:
    async def test_returns_updated_phone(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_phone_number.json")
        api = PeopleAPI(mock_client)
        phone = await api.update_phone_number("1001", "3001", number="5550202", location="Work")
        assert phone["number"] == "5550202"
        assert phone["location"] == "Work"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_phone_number.json")
        api = PeopleAPI(mock_client)
        await api.update_phone_number("1001", "3001", location="Work")
        call_path = mock_client.patch.call_args.args[0]
        assert "1001" in call_path
        assert "3001" in call_path
        assert "/phone_numbers/" in call_path


class TestGetWorkflows:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_workflows.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_workflows()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "New Member Follow-up"
        assert result["items"][0]["ready_card_count"] == 3
        assert result["items"][1]["name"] == "Baptism Prep"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_workflows.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        await api.get_workflows()
        call_path = mock_client.get_all.call_args.args[0]
        assert "/workflows" in call_path


class TestAddPersonToWorkflow:
    async def test_returns_created_card(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_person_to_workflow.json")
        api = PeopleAPI(mock_client)
        card = await api.add_person_to_workflow("7001", "1001")
        assert card["id"] == "8001"
        assert card["stage"] == "Ready"
        assert card["person_id"] == "1001"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_person_to_workflow.json")
        api = PeopleAPI(mock_client)
        await api.add_person_to_workflow("7001", "1001")
        call_path = mock_client.post.call_args.args[0]
        assert "7001" in call_path
        assert "/cards" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["attributes"]["person_id"] == 1001
