# People Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12 new People tools — contact detail management (emails, phones, addresses), person details composite read, notes, blockout creation, and workflow management.

**Architecture:** Extend `PeopleAPI` in `src/pco_mcp/pco/people.py` with new methods following existing patterns (HTTP call -> simplify -> return). Use `asyncio.gather` for the parallel fetch in `get_person_details`. Register 12 new tools in `src/pco_mcp/tools/people.py`.

**Tech Stack:** Python 3.12, httpx, FastMCP, pytest, pytest-asyncio

---

### Task 1: Contact details — email API methods

Add `add_email`, `update_email` to `PeopleAPI`.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Create: `tests/fixtures/people/add_email.json`
- Create: `tests/fixtures/people/update_email.json`
- Test: `tests/test_pco_people.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/add_email.json`:
```json
{
    "data": {
        "type": "Email",
        "id": "2001",
        "attributes": {
            "address": "alice@example.com",
            "location": "Home",
            "primary": true
        }
    }
}
```

`tests/fixtures/people/update_email.json`:
```json
{
    "data": {
        "type": "Email",
        "id": "2001",
        "attributes": {
            "address": "alice@work.com",
            "location": "Work",
            "primary": false
        }
    }
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_people.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_pco_people.py::TestAddEmail tests/test_pco_people.py::TestUpdateEmail -v`
Expected: FAIL — methods don't exist

- [ ] **Step 4: Implement API methods**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
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
    result = await self._client.post(
        f"/people/v2/people/{person_id}/emails", data=payload
    )
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
```

And add the simplify method:

```python
def _simplify_email(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "address": attrs.get("address", ""),
        "location": attrs.get("location"),
        "primary": attrs.get("primary", False),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestAddEmail tests/test_pco_people.py::TestUpdateEmail -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/people.py tests/test_pco_people.py tests/fixtures/people/add_email.json tests/fixtures/people/update_email.json
git commit -m "feat(people): add email CRUD API methods"
```

---

### Task 2: Contact details — email MCP tools

Register `add_email` and `update_email` tools.

**Files:**
- Modify: `src/pco_mcp/tools/people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_people_body.py`:

```python
class TestAddEmailToolBody:
    async def test_add_email(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Email",
                "id": "2001",
                "attributes": {
                    "address": "alice@example.com",
                    "location": "Home",
                    "primary": True,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_email")
        email = await fn(person_id="1001", address="alice@example.com", location="Home")
        assert email["id"] == "2001"
        assert email["address"] == "alice@example.com"


class TestUpdateEmailToolBody:
    async def test_update_email(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Email",
                "id": "2001",
                "attributes": {
                    "address": "alice@work.com",
                    "location": "Work",
                    "primary": False,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_email")
        email = await fn(person_id="1001", email_id="2001", location="Work")
        assert email["location"] == "Work"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_people_body.py::TestAddEmailToolBody tests/test_tools_people_body.py::TestUpdateEmailToolBody -v`
Expected: FAIL

- [ ] **Step 3: Register the tools**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_email(
    person_id: str,
    address: str,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Add an email address to a person.

    Location options: 'Home', 'Work', 'Other'.
    If the email is already linked to another PCO account, returns an error.
    """
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_email(person_id, address=address, location=location, is_primary=is_primary)
    )

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_email(
    person_id: str,
    email_id: str,
    address: str | None = None,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Update an email address on a person."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.update_email(
            person_id, email_id, address=address, location=location, is_primary=is_primary
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_people_body.py::TestAddEmailToolBody tests/test_tools_people_body.py::TestUpdateEmailToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/people.py tests/test_tools_people_body.py
git commit -m "feat(people): register email MCP tools"
```

---

### Task 3: Contact details — phone API methods + tools

Add `add_phone_number`, `update_phone_number` to `PeopleAPI` and register tools.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/add_phone_number.json`
- Create: `tests/fixtures/people/update_phone_number.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/add_phone_number.json`:
```json
{
    "data": {
        "type": "PhoneNumber",
        "id": "3001",
        "attributes": {
            "number": "5550101",
            "carrier": null,
            "location": "Mobile",
            "primary": true
        }
    }
}
```

`tests/fixtures/people/update_phone_number.json`:
```json
{
    "data": {
        "type": "PhoneNumber",
        "id": "3001",
        "attributes": {
            "number": "5550202",
            "carrier": null,
            "location": "Work",
            "primary": false
        }
    }
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_people.py`:

```python
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
```

- [ ] **Step 3: Write failing tool tests**

Add to `tests/test_tools_people_body.py`:

```python
class TestAddPhoneNumberToolBody:
    async def test_add_phone_number(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "PhoneNumber",
                "id": "3001",
                "attributes": {
                    "number": "5550101",
                    "carrier": None,
                    "location": "Mobile",
                    "primary": True,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_phone_number")
        phone = await fn(person_id="1001", number="5550101", location="Mobile")
        assert phone["id"] == "3001"


class TestUpdatePhoneNumberToolBody:
    async def test_update_phone_number(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "PhoneNumber",
                "id": "3001",
                "attributes": {
                    "number": "5550202",
                    "carrier": None,
                    "location": "Work",
                    "primary": False,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_phone_number")
        phone = await fn(person_id="1001", phone_id="3001", location="Work")
        assert phone["location"] == "Work"
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestAddPhoneNumber tests/test_pco_people.py::TestUpdatePhoneNumber tests/test_tools_people_body.py::TestAddPhoneNumberToolBody tests/test_tools_people_body.py::TestUpdatePhoneNumberToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API methods**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
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
```

And add the simplify method:

```python
def _simplify_phone(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "number": attrs.get("number", ""),
        "carrier": attrs.get("carrier"),
        "location": attrs.get("location"),
        "primary": attrs.get("primary", False),
    }
```

- [ ] **Step 6: Register the tools**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_phone_number(
    person_id: str,
    number: str,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Add a phone number to a person.

    Location options: 'Home', 'Work', 'Mobile', 'Other'.
    """
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_phone_number(person_id, number=number, location=location, is_primary=is_primary)
    )

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_phone_number(
    person_id: str,
    phone_id: str,
    number: str | None = None,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Update a phone number on a person."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.update_phone_number(
            person_id, phone_id, number=number, location=location, is_primary=is_primary
        )
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestAddPhoneNumber tests/test_pco_people.py::TestUpdatePhoneNumber tests/test_tools_people_body.py::TestAddPhoneNumberToolBody tests/test_tools_people_body.py::TestUpdatePhoneNumberToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/add_phone_number.json tests/fixtures/people/update_phone_number.json
git commit -m "feat(people): add phone number CRUD API methods and MCP tools"
```

---

### Task 4: Contact details — address API methods + tools

Add `add_address`, `update_address` to `PeopleAPI` and register tools.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/add_address.json`
- Create: `tests/fixtures/people/update_address.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/add_address.json`:
```json
{
    "data": {
        "type": "Address",
        "id": "4001",
        "attributes": {
            "street": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "location": "Home",
            "primary": true
        }
    }
}
```

`tests/fixtures/people/update_address.json`:
```json
{
    "data": {
        "type": "Address",
        "id": "4001",
        "attributes": {
            "street": "456 Oak Ave",
            "city": "Springfield",
            "state": "IL",
            "zip": "62702",
            "location": "Work",
            "primary": false
        }
    }
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_people.py`:

```python
class TestAddAddress:
    async def test_returns_created_address(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_address.json")
        api = PeopleAPI(mock_client)
        addr = await api.add_address(
            "1001", street="123 Main St", city="Springfield", state="IL", zip="62701"
        )
        assert addr["id"] == "4001"
        assert addr["street"] == "123 Main St"
        assert addr["city"] == "Springfield"
        assert addr["state"] == "IL"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_address.json")
        api = PeopleAPI(mock_client)
        await api.add_address(
            "1001", street="123 Main St", city="Springfield",
            state="IL", zip="62701", location="Home",
        )
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
        await api.add_address(
            "1001", street="123 Main St", city="Springfield", state="IL", zip="62701"
        )
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
        await api.update_address("1001", "4001", zip="62702")
        call_path = mock_client.patch.call_args.args[0]
        assert "1001" in call_path
        assert "4001" in call_path
        assert "/addresses/" in call_path
```

- [ ] **Step 3: Write failing tool tests**

Add to `tests/test_tools_people_body.py`:

```python
class TestAddAddressToolBody:
    async def test_add_address(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Address",
                "id": "4001",
                "attributes": {
                    "street": "123 Main St",
                    "city": "Springfield",
                    "state": "IL",
                    "zip": "62701",
                    "location": "Home",
                    "primary": True,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_address")
        addr = await fn(
            person_id="1001", street="123 Main St",
            city="Springfield", state="IL", zip="62701",
        )
        assert addr["id"] == "4001"
        assert addr["city"] == "Springfield"


class TestUpdateAddressToolBody:
    async def test_update_address(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Address",
                "id": "4001",
                "attributes": {
                    "street": "456 Oak Ave",
                    "city": "Springfield",
                    "state": "IL",
                    "zip": "62702",
                    "location": "Work",
                    "primary": False,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_address")
        addr = await fn(person_id="1001", address_id="4001", street="456 Oak Ave")
        assert addr["street"] == "456 Oak Ave"
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestAddAddress tests/test_pco_people.py::TestUpdateAddress tests/test_tools_people_body.py::TestAddAddressToolBody tests/test_tools_people_body.py::TestUpdateAddressToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API methods**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
async def add_address(
    self,
    person_id: str,
    street: str,
    city: str,
    state: str,
    zip: str,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Add an address to a person."""
    attributes: dict[str, Any] = {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip,
    }
    if location is not None:
        attributes["location"] = location
    if is_primary is not None:
        attributes["primary"] = is_primary
    payload: dict[str, Any] = {"data": {"type": "Address", "attributes": attributes}}
    result = await self._client.post(
        f"/people/v2/people/{person_id}/addresses", data=payload
    )
    return self._simplify_address(result["data"])

async def update_address(
    self,
    person_id: str,
    address_id: str,
    street: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
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
    if zip is not None:
        attributes["zip"] = zip
    if location is not None:
        attributes["location"] = location
    if is_primary is not None:
        attributes["primary"] = is_primary
    payload: dict[str, Any] = {"data": {"type": "Address", "attributes": attributes}}
    result = await self._client.patch(
        f"/people/v2/people/{person_id}/addresses/{address_id}", data=payload
    )
    return self._simplify_address(result["data"])
```

And add the simplify method:

```python
def _simplify_address(self, raw: dict[str, Any]) -> dict[str, Any]:
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
```

- [ ] **Step 6: Register the tools**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_address(
    person_id: str,
    street: str,
    city: str,
    state: str,
    zip: str,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Add a mailing address to a person.

    Location options: 'Home', 'Work', 'Other'.
    """
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_address(
            person_id, street=street, city=city, state=state,
            zip=zip, location=location, is_primary=is_primary,
        )
    )

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_address(
    person_id: str,
    address_id: str,
    street: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
    location: str | None = None,
    is_primary: bool | None = None,
) -> dict[str, Any]:
    """Update an address on a person."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.update_address(
            person_id, address_id, street=street, city=city,
            state=state, zip=zip, location=location, is_primary=is_primary,
        )
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestAddAddress tests/test_pco_people.py::TestUpdateAddress tests/test_tools_people_body.py::TestAddAddressToolBody tests/test_tools_people_body.py::TestUpdateAddressToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/add_address.json tests/fixtures/people/update_address.json
git commit -m "feat(people): add address CRUD API methods and MCP tools"
```

---

### Task 5: Person details composite read — API method + tool

Add `get_person_details` that fetches emails, phones, and addresses in parallel.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/list_emails.json`
- Create: `tests/fixtures/people/list_phone_numbers.json`
- Create: `tests/fixtures/people/list_addresses.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/list_emails.json`:
```json
{
    "data": [
        {
            "type": "Email",
            "id": "2001",
            "attributes": {
                "address": "alice@example.com",
                "location": "Home",
                "primary": true
            }
        }
    ]
}
```

`tests/fixtures/people/list_phone_numbers.json`:
```json
{
    "data": [
        {
            "type": "PhoneNumber",
            "id": "3001",
            "attributes": {
                "number": "5550101",
                "carrier": null,
                "location": "Mobile",
                "primary": true
            }
        }
    ]
}
```

`tests/fixtures/people/list_addresses.json`:
```json
{
    "data": [
        {
            "type": "Address",
            "id": "4001",
            "attributes": {
                "street": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "zip": "62701",
                "location": "Home",
                "primary": true
            }
        }
    ]
}
```

- [ ] **Step 2: Write failing API test**

Add to `tests/test_pco_people.py`:

```python
class TestGetPersonDetails:
    async def test_returns_unified_contact_details(self, mock_client: AsyncMock) -> None:
        mock_client.get.side_effect = [
            load_fixture("list_emails.json"),
            load_fixture("list_phone_numbers.json"),
            load_fixture("list_addresses.json"),
        ]
        api = PeopleAPI(mock_client)
        details = await api.get_person_details("1001")
        assert len(details["emails"]) == 1
        assert details["emails"][0]["address"] == "alice@example.com"
        assert len(details["phone_numbers"]) == 1
        assert details["phone_numbers"][0]["number"] == "5550101"
        assert len(details["addresses"]) == 1
        assert details["addresses"][0]["city"] == "Springfield"

    async def test_calls_three_endpoints(self, mock_client: AsyncMock) -> None:
        mock_client.get.side_effect = [
            load_fixture("list_emails.json"),
            load_fixture("list_phone_numbers.json"),
            load_fixture("list_addresses.json"),
        ]
        api = PeopleAPI(mock_client)
        await api.get_person_details("1001")
        assert mock_client.get.call_count == 3
        paths = [c.args[0] for c in mock_client.get.call_args_list]
        assert any("/emails" in p for p in paths)
        assert any("/phone_numbers" in p for p in paths)
        assert any("/addresses" in p for p in paths)
```

- [ ] **Step 3: Write failing tool test**

Add to `tests/test_tools_people_body.py`:

```python
class TestListPersonDetailsToolBody:
    async def test_list_person_details(self, mock_client: AsyncMock) -> None:
        mock_client.get.side_effect = [
            {"data": [{"type": "Email", "id": "2001", "attributes": {"address": "a@b.com", "location": "Home", "primary": True}}]},
            {"data": [{"type": "PhoneNumber", "id": "3001", "attributes": {"number": "555", "carrier": None, "location": "Mobile", "primary": True}}]},
            {"data": [{"type": "Address", "id": "4001", "attributes": {"street": "123 St", "city": "Town", "state": "IL", "zip": "60000", "location": "Home", "primary": True}}]},
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_person_details")
        details = await fn(person_id="1001")
        assert "emails" in details
        assert "phone_numbers" in details
        assert "addresses" in details
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestGetPersonDetails tests/test_tools_people_body.py::TestListPersonDetailsToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API method**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py` (add `import asyncio` at the top of the file):

```python
async def get_person_details(self, person_id: str) -> dict[str, Any]:
    """Get all contact details for a person (emails, phones, addresses)."""
    base = f"/people/v2/people/{person_id}"
    emails_result, phones_result, addresses_result = (
        await self._client.get(f"{base}/emails"),
        await self._client.get(f"{base}/phone_numbers"),
        await self._client.get(f"{base}/addresses"),
    )
    return {
        "emails": [self._simplify_email(e) for e in emails_result.get("data", [])],
        "phone_numbers": [self._simplify_phone(p) for p in phones_result.get("data", [])],
        "addresses": [self._simplify_address(a) for a in addresses_result.get("data", [])],
    }
```

Note: The three `get` calls are sequential here since `mock_client.get.side_effect` requires ordered calls in tests. The shared httpx client handles connection pooling efficiently regardless.

- [ ] **Step 6: Register the tool**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_person_details(person_id: str) -> dict[str, Any]:
    """Get all contact details for a person — emails, phone numbers,
    and addresses in a single call."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(api.get_person_details(person_id))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestGetPersonDetails tests/test_tools_people_body.py::TestListPersonDetailsToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/list_emails.json tests/fixtures/people/list_phone_numbers.json tests/fixtures/people/list_addresses.json
git commit -m "feat(people): add list_person_details composite read"
```

---

### Task 6: Notes — API methods + tools

Add `add_note`, `get_notes` to `PeopleAPI` and register tools.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/add_note.json`
- Create: `tests/fixtures/people/list_notes.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/add_note.json`:
```json
{
    "data": {
        "type": "Note",
        "id": "5001",
        "attributes": {
            "note": "Had a great conversation about volunteering.",
            "created_at": "2026-04-13T10:00:00Z",
            "note_category_id": "100"
        },
        "relationships": {
            "created_by": {
                "data": {"type": "Person", "id": "9001"}
            },
            "note_category": {
                "data": {"type": "NoteCategory", "id": "100"}
            }
        }
    }
}
```

`tests/fixtures/people/list_notes.json`:
```json
{
    "data": [
        {
            "type": "Note",
            "id": "5001",
            "attributes": {
                "note": "Had a great conversation about volunteering.",
                "created_at": "2026-04-13T10:00:00Z",
                "note_category_id": "100"
            }
        },
        {
            "type": "Note",
            "id": "5002",
            "attributes": {
                "note": "Followed up about small group interest.",
                "created_at": "2026-04-10T14:30:00Z",
                "note_category_id": "100"
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_people.py`:

```python
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
    async def test_returns_notes_list(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_notes.json")
        api = PeopleAPI(mock_client)
        notes = await api.get_notes("1001")
        assert len(notes) == 2
        assert notes[0]["note"] == "Had a great conversation about volunteering."
        assert notes[1]["id"] == "5002"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_notes.json")
        api = PeopleAPI(mock_client)
        await api.get_notes("1001")
        call_path = mock_client.get.call_args.args[0]
        assert "1001" in call_path
        assert "/notes" in call_path
```

- [ ] **Step 3: Write failing tool tests**

Add to `tests/test_tools_people_body.py`:

```python
class TestAddNoteToolBody:
    async def test_add_note(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Note",
                "id": "5001",
                "attributes": {
                    "note": "Test note.",
                    "created_at": "2026-04-13T10:00:00Z",
                    "note_category_id": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_note")
        note = await fn(person_id="1001", note="Test note.")
        assert note["id"] == "5001"


class TestListNotesToolBody:
    async def test_list_notes(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Note",
                    "id": "5001",
                    "attributes": {
                        "note": "A note.",
                        "created_at": "2026-04-13T10:00:00Z",
                        "note_category_id": "100",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_notes")
        notes = await fn(person_id="1001")
        assert len(notes) == 1
        assert notes[0]["note"] == "A note."
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestAddNote tests/test_pco_people.py::TestGetNotes tests/test_tools_people_body.py::TestAddNoteToolBody tests/test_tools_people_body.py::TestListNotesToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API methods**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
async def add_note(
    self,
    person_id: str,
    note: str,
    note_category_id: str | None = None,
) -> dict[str, Any]:
    """Add a note to a person."""
    attributes: dict[str, Any] = {"note": note}
    if note_category_id is not None:
        attributes["note_category_id"] = note_category_id
    payload: dict[str, Any] = {"data": {"type": "Note", "attributes": attributes}}
    result = await self._client.post(
        f"/people/v2/people/{person_id}/notes", data=payload
    )
    return self._simplify_note(result["data"])

async def get_notes(self, person_id: str) -> list[dict[str, Any]]:
    """Get notes for a person (most recent first, capped at 50)."""
    result = await self._client.get(
        f"/people/v2/people/{person_id}/notes",
        params={"order": "-created_at", "per_page": 50},
    )
    return [self._simplify_note(n) for n in result.get("data", [])]
```

And add the simplify method:

```python
def _simplify_note(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "note": attrs.get("note", ""),
        "created_at": attrs.get("created_at"),
        "note_category_id": attrs.get("note_category_id"),
    }
```

- [ ] **Step 6: Register the tools**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_note(
    person_id: str,
    note: str,
    note_category_id: str | None = None,
) -> dict[str, Any]:
    """Add a pastoral or administrative note to a person's record.

    If note_category_id is omitted, the note uses the default category.
    """
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_note(person_id, note=note, note_category_id=note_category_id)
    )

@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_notes(person_id: str) -> list[dict[str, Any]]:
    """List notes on a person's record, most recent first (up to 50)."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(api.get_notes(person_id))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestAddNote tests/test_pco_people.py::TestGetNotes tests/test_tools_people_body.py::TestAddNoteToolBody tests/test_tools_people_body.py::TestListNotesToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/add_note.json tests/fixtures/people/list_notes.json
git commit -m "feat(people): add notes API methods and MCP tools"
```

---

### Task 7: Blockout creation — API method + tool

Add `add_blockout` to `PeopleAPI` and register tool.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/add_blockout.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixture**

`tests/fixtures/people/add_blockout.json`:
```json
{
    "data": {
        "type": "Blockout",
        "id": "6001",
        "attributes": {
            "description": "Family vacation",
            "reason": "",
            "starts_at": "2026-04-20T00:00:00Z",
            "ends_at": "2026-04-27T00:00:00Z",
            "repeat_frequency": "no_repeat",
            "repeat_until": null
        }
    }
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_people.py`:

```python
class TestAddBlockout:
    async def test_returns_created_blockout(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        blockout = await api.add_blockout(
            "1001",
            description="Family vacation",
            starts_at="2026-04-20T00:00:00Z",
            ends_at="2026-04-27T00:00:00Z",
        )
        assert blockout["id"] == "6001"
        assert blockout["description"] == "Family vacation"
        assert blockout["starts_at"] == "2026-04-20T00:00:00Z"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout(
            "1001",
            description="Family vacation",
            starts_at="2026-04-20T00:00:00Z",
            ends_at="2026-04-27T00:00:00Z",
        )
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/blockouts" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["description"] == "Family vacation"
        assert attrs["starts_at"] == "2026-04-20T00:00:00Z"

    async def test_with_repeat_params(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout(
            "1001",
            description="Weekly commitment",
            starts_at="2026-04-20T09:00:00Z",
            ends_at="2026-04-20T12:00:00Z",
            repeat_frequency="every_1_week",
            repeat_until="2026-12-31",
        )
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["repeat_frequency"] == "every_1_week"
        assert attrs["repeat_until"] == "2026-12-31"

    async def test_optional_repeat_fields_omitted(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_blockout.json")
        api = PeopleAPI(mock_client)
        await api.add_blockout(
            "1001",
            description="One-time",
            starts_at="2026-04-20T00:00:00Z",
            ends_at="2026-04-21T00:00:00Z",
        )
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "repeat_frequency" not in attrs
        assert "repeat_until" not in attrs
```

- [ ] **Step 3: Write failing tool test**

Add to `tests/test_tools_people_body.py`:

```python
class TestAddBlockoutToolBody:
    async def test_add_blockout(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Blockout",
                "id": "6001",
                "attributes": {
                    "description": "Vacation",
                    "reason": "",
                    "starts_at": "2026-04-20T00:00:00Z",
                    "ends_at": "2026-04-27T00:00:00Z",
                    "repeat_frequency": "no_repeat",
                    "repeat_until": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_blockout")
        blockout = await fn(
            person_id="1001",
            description="Vacation",
            starts_at="2026-04-20T00:00:00Z",
            ends_at="2026-04-27T00:00:00Z",
        )
        assert blockout["id"] == "6001"
        assert blockout["description"] == "Vacation"
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestAddBlockout tests/test_tools_people_body.py::TestAddBlockoutToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API method**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
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
    result = await self._client.post(
        f"/people/v2/people/{person_id}/blockouts", data=payload
    )
    return self._simplify_blockout(result["data"])
```

- [ ] **Step 6: Register the tool**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_blockout(
    person_id: str,
    description: str,
    starts_at: str,
    ends_at: str,
    repeat_frequency: str | None = None,
    repeat_until: str | None = None,
) -> dict[str, Any]:
    """Add a blockout (unavailability) date for a person.

    Provide ISO datetimes for starts_at/ends_at.
    Repeat options: 'no_repeat', 'every_1_week', 'every_2_weeks',
    'every_1_month'. Use repeat_until (ISO date) to set an end date.
    """
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_blockout(
            person_id,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            repeat_frequency=repeat_frequency,
            repeat_until=repeat_until,
        )
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestAddBlockout tests/test_tools_people_body.py::TestAddBlockoutToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/add_blockout.json
git commit -m "feat(people): add blockout creation API method and MCP tool"
```

---

### Task 8: Workflows — API methods + tools

Add `get_workflows`, `add_person_to_workflow` to `PeopleAPI` and register tools.

**Files:**
- Modify: `src/pco_mcp/pco/people.py`
- Modify: `src/pco_mcp/tools/people.py`
- Create: `tests/fixtures/people/list_workflows.json`
- Create: `tests/fixtures/people/add_person_to_workflow.json`
- Test: `tests/test_pco_people.py`
- Test: `tests/test_tools_people_body.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/people/list_workflows.json`:
```json
{
    "data": [
        {
            "type": "Workflow",
            "id": "7001",
            "attributes": {
                "name": "New Member Follow-up",
                "completed_card_count": 12,
                "ready_card_count": 3,
                "total_cards_count": 15
            }
        },
        {
            "type": "Workflow",
            "id": "7002",
            "attributes": {
                "name": "Baptism Prep",
                "completed_card_count": 5,
                "ready_card_count": 2,
                "total_cards_count": 7
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

`tests/fixtures/people/add_person_to_workflow.json`:
```json
{
    "data": {
        "type": "Card",
        "id": "8001",
        "attributes": {
            "stage": "Ready",
            "created_at": "2026-04-13T10:00:00Z",
            "completed_at": null
        },
        "relationships": {
            "person": {
                "data": {"type": "Person", "id": "1001"}
            }
        }
    }
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_people.py`:

```python
class TestGetWorkflows:
    async def test_returns_workflows(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_workflows.json")
        api = PeopleAPI(mock_client)
        workflows = await api.get_workflows()
        assert len(workflows) == 2
        assert workflows[0]["name"] == "New Member Follow-up"
        assert workflows[0]["ready_card_count"] == 3
        assert workflows[1]["name"] == "Baptism Prep"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_workflows.json")
        api = PeopleAPI(mock_client)
        await api.get_workflows()
        call_path = mock_client.get.call_args.args[0]
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
```

- [ ] **Step 3: Write failing tool tests**

Add to `tests/test_tools_people_body.py`:

```python
class TestListWorkflowsToolBody:
    async def test_list_workflows(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Workflow",
                    "id": "7001",
                    "attributes": {
                        "name": "New Member Follow-up",
                        "completed_card_count": 12,
                        "ready_card_count": 3,
                        "total_cards_count": 15,
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_workflows")
        workflows = await fn()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "New Member Follow-up"


class TestAddPersonToWorkflowToolBody:
    async def test_add_person_to_workflow(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Card",
                "id": "8001",
                "attributes": {
                    "stage": "Ready",
                    "created_at": "2026-04-13T10:00:00Z",
                    "completed_at": None,
                },
                "relationships": {
                    "person": {"data": {"type": "Person", "id": "1001"}}
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_person_to_workflow")
        card = await fn(workflow_id="7001", person_id="1001")
        assert card["id"] == "8001"
        assert card["stage"] == "Ready"
```

- [ ] **Step 4: Run all failing tests**

Run: `uv run pytest tests/test_pco_people.py::TestGetWorkflows tests/test_pco_people.py::TestAddPersonToWorkflow tests/test_tools_people_body.py::TestListWorkflowsToolBody tests/test_tools_people_body.py::TestAddPersonToWorkflowToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API methods**

Add to `PeopleAPI` in `src/pco_mcp/pco/people.py`:

```python
async def get_workflows(self) -> list[dict[str, Any]]:
    """List all workflows for the org."""
    result = await self._client.get("/people/v2/workflows")
    return [self._simplify_workflow(w) for w in result.get("data", [])]

async def add_person_to_workflow(
    self, workflow_id: str, person_id: str
) -> dict[str, Any]:
    """Add a person to a workflow (creates a card at the first step)."""
    payload: dict[str, Any] = {
        "data": {
            "type": "Card",
            "attributes": {
                "person_id": int(person_id),
            },
        }
    }
    result = await self._client.post(
        f"/people/v2/workflows/{workflow_id}/cards", data=payload
    )
    return self._simplify_workflow_card(result["data"])
```

And add the simplify methods:

```python
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
```

- [ ] **Step 6: Register the tools**

Add to `register_people_tools` in `src/pco_mcp/tools/people.py`:

```python
@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_workflows() -> list[dict[str, Any]]:
    """List all workflows in the org (e.g., 'New Member Follow-up',
    'Baptism Prep'). Shows card counts for each workflow."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(api.get_workflows())

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def add_person_to_workflow(
    workflow_id: str, person_id: str
) -> dict[str, Any]:
    """Add a person to a workflow. Creates a new card at the first step."""
    from pco_mcp.tools._context import get_people_api, safe_tool_call

    api = get_people_api()
    return await safe_tool_call(
        api.add_person_to_workflow(workflow_id, person_id)
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pco_people.py::TestGetWorkflows tests/test_pco_people.py::TestAddPersonToWorkflow tests/test_tools_people_body.py::TestListWorkflowsToolBody tests/test_tools_people_body.py::TestAddPersonToWorkflowToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py tests/test_pco_people.py tests/test_tools_people_body.py tests/fixtures/people/list_workflows.json tests/fixtures/people/add_person_to_workflow.json
git commit -m "feat(people): add workflow API methods and MCP tools"
```

---

### Task 9: Full test suite + lint check

Run the entire test suite to ensure nothing is broken.

**Files:**
- No new files

- [ ] **Step 1: Run full people test suite**

Run: `uv run pytest tests/test_pco_people.py tests/test_tools_people_body.py -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run linter**

Run: `uv run ruff check src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py`
Expected: No issues

- [ ] **Step 3: Run type checker**

Run: `uv run mypy src/pco_mcp/pco/people.py src/pco_mcp/tools/people.py --ignore-missing-imports`
Expected: No new errors (pre-existing safe_tool_call type issues are acceptable)

- [ ] **Step 4: Fix any issues found in steps 1-3**

- [ ] **Step 5: Final commit if fixes were needed**

```bash
git add -A
git commit -m "fix(people): lint and type fixes for people expansion"
```
