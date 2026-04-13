# Services Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 16 new Services tools — song CRUD, arrangement CRUD, file attachments, media management, CCLI compliance, and service type creation.

**Architecture:** Extend `ServicesAPI` in `src/pco_mcp/pco/services.py` with new methods following the existing pattern (HTTP call -> simplify -> return). Add a `put_raw` method to `PCOClient` and an `upload_attachment` helper on `ServicesAPI` for the 3-step S3 upload flow. Register 16 new tools in `src/pco_mcp/tools/services.py`.

**Tech Stack:** Python 3.12, httpx, FastMCP, pytest, pytest-asyncio

---

### Task 1: Add `put_raw` to PCOClient

The S3 upload flow requires PUTting raw bytes to a presigned URL with a specific content type. The existing `PCOClient` only does JSON requests. Add a `put_raw` method.

**Files:**
- Modify: `src/pco_mcp/pco/client.py`
- Test: `tests/test_pco_client.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_pco_client.py`, add:

```python
class TestPutRaw:
    async def test_put_raw_sends_bytes(self) -> None:
        import httpx
        from unittest.mock import AsyncMock, MagicMock

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_http.put.return_value = mock_response

        client = PCOClient(
            base_url="https://api.example.com",
            access_token="test-token",
            http_client=mock_http,
        )
        await client.put_raw(
            "https://s3.amazonaws.com/presigned-url",
            data=b"file-bytes",
            content_type="application/pdf",
        )
        mock_http.put.assert_called_once_with(
            "https://s3.amazonaws.com/presigned-url",
            content=b"file-bytes",
            headers={"Content-Type": "application/pdf"},
        )

    async def test_put_raw_raises_on_failure(self) -> None:
        import httpx
        from unittest.mock import AsyncMock, MagicMock

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 403
        mock_response.headers = {}
        mock_response.json.side_effect = Exception("not json")
        mock_http.put.return_value = mock_response

        client = PCOClient(
            base_url="https://api.example.com",
            access_token="test-token",
            http_client=mock_http,
        )
        with pytest.raises(PCOAPIError, match="403"):
            await client.put_raw(
                "https://s3.amazonaws.com/presigned-url",
                data=b"file-bytes",
                content_type="application/pdf",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pco_client.py::TestPutRaw -v`
Expected: FAIL — `PCOClient` has no `put_raw` method

- [ ] **Step 3: Implement `put_raw`**

Add to `PCOClient` in `src/pco_mcp/pco/client.py`, after the `delete` method:

```python
async def put_raw(self, url: str, data: bytes, content_type: str) -> None:
    """PUT raw bytes to a URL (used for S3 presigned uploads).

    Unlike other methods, this does NOT send auth headers — presigned
    URLs carry their own authentication.
    """
    response = await self._client.put(
        url, content=data, headers={"Content-Type": content_type}
    )
    logger.debug("PUT %s -> %s", url, response.status_code)
    self._check_response(response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pco_client.py::TestPutRaw -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/pco/client.py tests/test_pco_client.py
git commit -m "feat(services): add put_raw to PCOClient for S3 uploads"
```

---

### Task 2: Song CRUD — API methods

Add `get_song`, `create_song`, `update_song`, `delete_song` to `ServicesAPI`.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Create: `tests/fixtures/services/get_song.json`
- Create: `tests/fixtures/services/create_song.json`
- Create: `tests/fixtures/services/update_song.json`
- Test: `tests/test_pco_services.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/services/get_song.json`:
```json
{
    "data": {
        "type": "Song",
        "id": "4001",
        "attributes": {
            "title": "Amazing Grace",
            "author": "John Newton",
            "copyright": "Public Domain",
            "ccli_number": 4669344,
            "themes": "Grace, Redemption",
            "admin": "Standard hymn",
            "created_at": "2025-01-15T10:00:00Z",
            "last_scheduled_at": "2026-03-30T09:00:00Z"
        }
    }
}
```

`tests/fixtures/services/create_song.json`:
```json
{
    "data": {
        "type": "Song",
        "id": "4010",
        "attributes": {
            "title": "New Song",
            "author": "Test Author",
            "copyright": "2026 Test",
            "ccli_number": 9999999,
            "themes": "",
            "admin": "",
            "created_at": "2026-04-13T10:00:00Z",
            "last_scheduled_at": null
        }
    }
}
```

`tests/fixtures/services/update_song.json`:
```json
{
    "data": {
        "type": "Song",
        "id": "4001",
        "attributes": {
            "title": "Amazing Grace (Updated)",
            "author": "John Newton",
            "copyright": "Public Domain",
            "ccli_number": 1234567,
            "themes": "Grace",
            "admin": "Updated notes",
            "created_at": "2025-01-15T10:00:00Z",
            "last_scheduled_at": "2026-03-30T09:00:00Z"
        }
    }
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_services.py`:

```python
class TestGetSong:
    async def test_returns_full_song_detail(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song.json")
        api = ServicesAPI(mock_client)
        song = await api.get_song("4001")
        assert song["id"] == "4001"
        assert song["title"] == "Amazing Grace"
        assert song["copyright"] == "Public Domain"
        assert song["themes"] == "Grace, Redemption"
        assert song["admin"] == "Standard hymn"
        assert song["created_at"] == "2025-01-15T10:00:00Z"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song.json")
        api = ServicesAPI(mock_client)
        await api.get_song("4001")
        call_path = mock_client.get.call_args.args[0]
        assert "4001" in call_path
        assert "/songs/" in call_path


class TestCreateSong:
    async def test_returns_created_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        song = await api.create_song(title="New Song", author="Test Author", ccli_number=9999999)
        assert song["id"] == "4010"
        assert song["title"] == "New Song"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        await api.create_song(
            title="New Song", author="Test Author", copyright="2026 Test", ccli_number=9999999
        )
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Song"
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "New Song"
        assert attrs["author"] == "Test Author"
        assert attrs["copyright"] == "2026 Test"
        assert attrs["ccli_number"] == 9999999

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        await api.create_song(title="New Song")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "New Song"
        assert "author" not in attrs


class TestUpdateSong:
    async def test_returns_updated_song(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_song.json")
        api = ServicesAPI(mock_client)
        song = await api.update_song("4001", title="Amazing Grace (Updated)")
        assert song["title"] == "Amazing Grace (Updated)"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_song.json")
        api = ServicesAPI(mock_client)
        await api.update_song("4001", ccli_number=1234567)
        call_path = mock_client.patch.call_args.args[0]
        assert "4001" in call_path
        data = mock_client.patch.call_args.kwargs["data"]
        assert data["data"]["attributes"]["ccli_number"] == 1234567


class TestDeleteSong:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.delete_song("4001")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "4001" in call_path
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py::TestGetSong tests/test_pco_services.py::TestCreateSong tests/test_pco_services.py::TestUpdateSong tests/test_pco_services.py::TestDeleteSong -v`
Expected: FAIL — methods don't exist

- [ ] **Step 4: Implement API methods**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def get_song(self, song_id: str) -> dict[str, Any]:
    """Get full details for a song."""
    result = await self._client.get(f"/services/v2/songs/{song_id}")
    return self._simplify_song_full(result["data"])

async def create_song(
    self,
    title: str,
    author: str | None = None,
    copyright: str | None = None,
    ccli_number: int | None = None,
    themes: str | None = None,
    admin: str | None = None,
) -> dict[str, Any]:
    """Create a new song in the library."""
    attributes: dict[str, Any] = {"title": title}
    if author is not None:
        attributes["author"] = author
    if copyright is not None:
        attributes["copyright"] = copyright
    if ccli_number is not None:
        attributes["ccli_number"] = ccli_number
    if themes is not None:
        attributes["themes"] = themes
    if admin is not None:
        attributes["admin"] = admin
    payload: dict[str, Any] = {"data": {"type": "Song", "attributes": attributes}}
    result = await self._client.post("/services/v2/songs", data=payload)
    return self._simplify_song_full(result["data"])

async def update_song(
    self,
    song_id: str,
    title: str | None = None,
    author: str | None = None,
    copyright: str | None = None,
    ccli_number: int | None = None,
    themes: str | None = None,
    admin: str | None = None,
) -> dict[str, Any]:
    """Update an existing song."""
    attributes: dict[str, Any] = {}
    if title is not None:
        attributes["title"] = title
    if author is not None:
        attributes["author"] = author
    if copyright is not None:
        attributes["copyright"] = copyright
    if ccli_number is not None:
        attributes["ccli_number"] = ccli_number
    if themes is not None:
        attributes["themes"] = themes
    if admin is not None:
        attributes["admin"] = admin
    payload: dict[str, Any] = {"data": {"type": "Song", "attributes": attributes}}
    result = await self._client.patch(f"/services/v2/songs/{song_id}", data=payload)
    return self._simplify_song_full(result["data"])

async def delete_song(self, song_id: str) -> None:
    """Delete a song and all its arrangements/attachments."""
    await self._client.delete(f"/services/v2/songs/{song_id}")
```

And add the new simplify method alongside the existing `_simplify_song`:

```python
def _simplify_song_full(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "title": attrs.get("title", ""),
        "author": attrs.get("author"),
        "copyright": attrs.get("copyright"),
        "ccli_number": attrs.get("ccli_number"),
        "themes": attrs.get("themes"),
        "admin": attrs.get("admin"),
        "created_at": attrs.get("created_at"),
        "last_scheduled_at": attrs.get("last_scheduled_at"),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestGetSong tests/test_pco_services.py::TestCreateSong tests/test_pco_services.py::TestUpdateSong tests/test_pco_services.py::TestDeleteSong -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/get_song.json tests/fixtures/services/create_song.json tests/fixtures/services/update_song.json
git commit -m "feat(services): add song CRUD API methods"
```

---

### Task 3: Song CRUD — MCP tools

Register `get_song`, `create_song`, `update_song`, `delete_song` tools.

**Files:**
- Modify: `src/pco_mcp/tools/services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_services_body.py`:

```python
class TestGetSongToolBody:
    async def test_get_song(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "type": "Song",
                "id": "4001",
                "attributes": {
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "copyright": "Public Domain",
                    "ccli_number": 4669344,
                    "themes": "Grace",
                    "admin": "",
                    "created_at": "2025-01-15T10:00:00Z",
                    "last_scheduled_at": "2026-03-30T09:00:00Z",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_song")
        song = await fn(song_id="4001")
        assert song["id"] == "4001"
        assert song["title"] == "Amazing Grace"


class TestCreateSongToolBody:
    async def test_create_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Song",
                "id": "4010",
                "attributes": {
                    "title": "New Song",
                    "author": "Test Author",
                    "copyright": "",
                    "ccli_number": None,
                    "themes": "",
                    "admin": "",
                    "created_at": "2026-04-13T10:00:00Z",
                    "last_scheduled_at": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_song")
        song = await fn(title="New Song", author="Test Author")
        assert song["id"] == "4010"
        assert song["title"] == "New Song"


class TestUpdateSongToolBody:
    async def test_update_song(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Song",
                "id": "4001",
                "attributes": {
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "copyright": "Public Domain",
                    "ccli_number": 1234567,
                    "themes": "",
                    "admin": "",
                    "created_at": "2025-01-15T10:00:00Z",
                    "last_scheduled_at": "2026-03-30T09:00:00Z",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_song")
        song = await fn(song_id="4001", ccli_number=1234567)
        assert song["ccli_number"] == 1234567


class TestDeleteSongToolBody:
    async def test_delete_song(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "delete_song")
        result = await fn(song_id="4001")
        assert result["status"] == "deleted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services_body.py::TestGetSongToolBody tests/test_tools_services_body.py::TestCreateSongToolBody tests/test_tools_services_body.py::TestUpdateSongToolBody tests/test_tools_services_body.py::TestDeleteSongToolBody -v`
Expected: FAIL — tools not registered

- [ ] **Step 3: Register the tools**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=READ_ANNOTATIONS)
async def get_song(song_id: str) -> dict[str, Any]:
    """Get full details for a song including title, author, copyright, CCLI number, themes, and admin notes."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.get_song(song_id))

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def create_song(
    title: str,
    author: str | None = None,
    copyright: str | None = None,
    ccli_number: int | None = None,
    themes: str | None = None,
    admin: str | None = None,
) -> dict[str, Any]:
    """Create a new song in the Planning Center song library.

    After creation, use create_arrangement to add lyrics, chord charts, and keys.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.create_song(
            title=title,
            author=author,
            copyright=copyright,
            ccli_number=ccli_number,
            themes=themes,
            admin=admin,
        )
    )

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_song(
    song_id: str,
    title: str | None = None,
    author: str | None = None,
    copyright: str | None = None,
    ccli_number: int | None = None,
    themes: str | None = None,
    admin: str | None = None,
) -> dict[str, Any]:
    """Update an existing song's metadata. Useful for populating missing CCLI numbers."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.update_song(
            song_id,
            title=title,
            author=author,
            copyright=copyright,
            ccli_number=ccli_number,
            themes=themes,
            admin=admin,
        )
    )

@mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
async def delete_song(song_id: str) -> dict[str, Any]:
    """Delete a song and all its arrangements and attachments. This cannot be undone."""
    from pco_mcp.tools._context import get_services_api

    api = get_services_api()
    await api.delete_song(song_id)
    return {"status": "deleted"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services_body.py::TestGetSongToolBody tests/test_tools_services_body.py::TestCreateSongToolBody tests/test_tools_services_body.py::TestUpdateSongToolBody tests/test_tools_services_body.py::TestDeleteSongToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services_body.py
git commit -m "feat(services): register song CRUD MCP tools"
```

---

### Task 4: Arrangement CRUD — API methods

Add `create_arrangement`, `update_arrangement`, `delete_arrangement` to `ServicesAPI`.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Create: `tests/fixtures/services/create_arrangement.json`
- Create: `tests/fixtures/services/update_arrangement.json`
- Test: `tests/test_pco_services.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/services/create_arrangement.json`:
```json
{
    "data": {
        "type": "Arrangement",
        "id": "1010",
        "attributes": {
            "name": "Default Arrangement",
            "bpm": 120.0,
            "length": 300,
            "meter": "4/4",
            "chord_chart": "[G]Amazing [C]grace, how [G]sweet the sound",
            "chord_chart_key": "G",
            "notes": "Standard version",
            "sequence": ["Verse 1", "Chorus"],
            "lyrics": "Amazing grace, how sweet the sound"
        }
    }
}
```

`tests/fixtures/services/update_arrangement.json`:
```json
{
    "data": {
        "type": "Arrangement",
        "id": "1001",
        "attributes": {
            "name": "Standard",
            "bpm": 80.0,
            "length": 240,
            "meter": "4/4",
            "chord_chart": "[A]Amazing [D]grace",
            "chord_chart_key": "A",
            "notes": "Updated key",
            "sequence": ["Verse 1", "Chorus", "Verse 2"],
            "lyrics": "Amazing grace"
        }
    }
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_services.py`:

```python
class TestCreateArrangement:
    async def test_returns_created_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        arr = await api.create_arrangement(
            song_id="4001", name="Default Arrangement", chord_chart="[G]Amazing [C]grace"
        )
        assert arr["id"] == "1010"
        assert arr["name"] == "Default Arrangement"
        assert arr["chord_chart_key"] == "G"
        assert arr["chord_chart"] == "[G]Amazing [C]grace, how [G]sweet the sound"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.create_arrangement(
            song_id="4001",
            name="Default Arrangement",
            chord_chart="[G]Amazing",
            bpm=120.0,
            meter="4/4",
            chord_chart_key="G",
            sequence=["Verse 1", "Chorus"],
        )
        call_path = mock_client.post.call_args.args[0]
        assert "4001" in call_path
        assert "arrangements" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["name"] == "Default Arrangement"
        assert attrs["bpm"] == 120.0
        assert attrs["sequence"] == ["Verse 1", "Chorus"]

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.create_arrangement(song_id="4001", name="Default")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["name"] == "Default"
        assert "bpm" not in attrs


class TestUpdateArrangement:
    async def test_returns_updated_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_arrangement.json")
        api = ServicesAPI(mock_client)
        arr = await api.update_arrangement("4001", "1001", bpm=80.0, chord_chart_key="A")
        assert arr["bpm"] == 80.0
        assert arr["chord_chart_key"] == "A"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.update_arrangement("4001", "1001", bpm=80.0)
        call_path = mock_client.patch.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "arrangements" in call_path


class TestDeleteArrangement:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.delete_arrangement("4001", "1001")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py::TestCreateArrangement tests/test_pco_services.py::TestUpdateArrangement tests/test_pco_services.py::TestDeleteArrangement -v`
Expected: FAIL

- [ ] **Step 4: Implement API methods**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def create_arrangement(
    self,
    song_id: str,
    name: str,
    chord_chart: str | None = None,
    bpm: float | None = None,
    meter: str | None = None,
    length: int | None = None,
    chord_chart_key: str | None = None,
    sequence: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Create an arrangement for a song."""
    attributes: dict[str, Any] = {"name": name}
    if chord_chart is not None:
        attributes["chord_chart"] = chord_chart
    if bpm is not None:
        attributes["bpm"] = bpm
    if meter is not None:
        attributes["meter"] = meter
    if length is not None:
        attributes["length"] = length
    if chord_chart_key is not None:
        attributes["chord_chart_key"] = chord_chart_key
    if sequence is not None:
        attributes["sequence"] = sequence
    if notes is not None:
        attributes["notes"] = notes
    payload: dict[str, Any] = {"data": {"type": "Arrangement", "attributes": attributes}}
    result = await self._client.post(
        f"/services/v2/songs/{song_id}/arrangements", data=payload
    )
    return self._simplify_arrangement_full(result["data"])

async def update_arrangement(
    self,
    song_id: str,
    arrangement_id: str,
    name: str | None = None,
    chord_chart: str | None = None,
    bpm: float | None = None,
    meter: str | None = None,
    length: int | None = None,
    chord_chart_key: str | None = None,
    sequence: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update an arrangement."""
    attributes: dict[str, Any] = {}
    if name is not None:
        attributes["name"] = name
    if chord_chart is not None:
        attributes["chord_chart"] = chord_chart
    if bpm is not None:
        attributes["bpm"] = bpm
    if meter is not None:
        attributes["meter"] = meter
    if length is not None:
        attributes["length"] = length
    if chord_chart_key is not None:
        attributes["chord_chart_key"] = chord_chart_key
    if sequence is not None:
        attributes["sequence"] = sequence
    if notes is not None:
        attributes["notes"] = notes
    payload: dict[str, Any] = {"data": {"type": "Arrangement", "attributes": attributes}}
    result = await self._client.patch(
        f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}", data=payload
    )
    return self._simplify_arrangement_full(result["data"])

async def delete_arrangement(self, song_id: str, arrangement_id: str) -> None:
    """Delete an arrangement from a song."""
    await self._client.delete(
        f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}"
    )
```

And add the new simplify method:

```python
def _simplify_arrangement_full(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "name": attrs.get("name", ""),
        "bpm": attrs.get("bpm"),
        "length": attrs.get("length"),
        "meter": attrs.get("meter"),
        "chord_chart": attrs.get("chord_chart"),
        "chord_chart_key": attrs.get("chord_chart_key"),
        "lyrics": attrs.get("lyrics"),
        "sequence": attrs.get("sequence"),
        "notes": attrs.get("notes"),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestCreateArrangement tests/test_pco_services.py::TestUpdateArrangement tests/test_pco_services.py::TestDeleteArrangement -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/create_arrangement.json tests/fixtures/services/update_arrangement.json
git commit -m "feat(services): add arrangement CRUD API methods"
```

---

### Task 5: Arrangement CRUD — MCP tools

Register `create_arrangement`, `update_arrangement`, `delete_arrangement` tools.

**Files:**
- Modify: `src/pco_mcp/tools/services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_services_body.py`:

```python
class TestCreateArrangementToolBody:
    async def test_create_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Arrangement",
                "id": "1010",
                "attributes": {
                    "name": "Default",
                    "bpm": 120.0,
                    "length": 300,
                    "meter": "4/4",
                    "chord_chart": "[G]Amazing grace",
                    "chord_chart_key": "G",
                    "lyrics": "Amazing grace",
                    "sequence": ["Verse 1"],
                    "notes": "",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_arrangement")
        arr = await fn(song_id="4001", name="Default", chord_chart="[G]Amazing grace")
        assert arr["id"] == "1010"
        assert arr["name"] == "Default"


class TestUpdateArrangementToolBody:
    async def test_update_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Arrangement",
                "id": "1001",
                "attributes": {
                    "name": "Standard",
                    "bpm": 80.0,
                    "length": 240,
                    "meter": "4/4",
                    "chord_chart": "[A]Amazing grace",
                    "chord_chart_key": "A",
                    "lyrics": "Amazing grace",
                    "sequence": [],
                    "notes": "",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_arrangement")
        arr = await fn(song_id="4001", arrangement_id="1001", bpm=80.0)
        assert arr["bpm"] == 80.0


class TestDeleteArrangementToolBody:
    async def test_delete_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "delete_arrangement")
        result = await fn(song_id="4001", arrangement_id="1001")
        assert result["status"] == "deleted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services_body.py::TestCreateArrangementToolBody tests/test_tools_services_body.py::TestUpdateArrangementToolBody tests/test_tools_services_body.py::TestDeleteArrangementToolBody -v`
Expected: FAIL

- [ ] **Step 3: Register the tools**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def create_arrangement(
    song_id: str,
    name: str,
    chord_chart: str | None = None,
    bpm: float | None = None,
    meter: str | None = None,
    length: int | None = None,
    chord_chart_key: str | None = None,
    sequence: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Create an arrangement for a song with lyrics, chord charts, and key.

    Use ChordPro format for chord_chart to embed chords inline: '[G]Amazing [C]grace'.
    Plain text is lyrics-only. The sequence field takes section labels like ['Verse 1', 'Chorus'].
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.create_arrangement(
            song_id=song_id,
            name=name,
            chord_chart=chord_chart,
            bpm=bpm,
            meter=meter,
            length=length,
            chord_chart_key=chord_chart_key,
            sequence=sequence,
            notes=notes,
        )
    )

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_arrangement(
    song_id: str,
    arrangement_id: str,
    name: str | None = None,
    chord_chart: str | None = None,
    bpm: float | None = None,
    meter: str | None = None,
    length: int | None = None,
    chord_chart_key: str | None = None,
    sequence: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update an arrangement's metadata, lyrics, chord chart, or key."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.update_arrangement(
            song_id=song_id,
            arrangement_id=arrangement_id,
            name=name,
            chord_chart=chord_chart,
            bpm=bpm,
            meter=meter,
            length=length,
            chord_chart_key=chord_chart_key,
            sequence=sequence,
            notes=notes,
        )
    )

@mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
async def delete_arrangement(song_id: str, arrangement_id: str) -> dict[str, Any]:
    """Delete an arrangement from a song. This cannot be undone."""
    from pco_mcp.tools._context import get_services_api

    api = get_services_api()
    await api.delete_arrangement(song_id, arrangement_id)
    return {"status": "deleted"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services_body.py::TestCreateArrangementToolBody tests/test_tools_services_body.py::TestUpdateArrangementToolBody tests/test_tools_services_body.py::TestDeleteArrangementToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services_body.py
git commit -m "feat(services): register arrangement CRUD MCP tools"
```

---

### Task 6: Attachment upload helper + `create_attachment` API

Add the shared `upload_attachment` helper and `create_attachment`, `list_attachments` API methods.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Create: `tests/fixtures/services/create_attachment.json`
- Create: `tests/fixtures/services/create_attachment_upload.json`
- Create: `tests/fixtures/services/list_attachments.json`
- Test: `tests/test_pco_services.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/services/create_attachment.json` (POST response with upload URL):
```json
{
    "data": {
        "type": "Attachment",
        "id": "5001",
        "attributes": {
            "filename": "chord-chart.pdf",
            "content_type": "application/pdf",
            "file_size": null,
            "url": null,
            "allow_mp3_download": false
        },
        "links": {
            "self": "https://api.planningcenteronline.com/services/v2/attachments/5001"
        }
    },
    "meta": {
        "upload": {
            "url": "https://s3.amazonaws.com/presigned-upload-url",
            "fields": {}
        }
    }
}
```

`tests/fixtures/services/create_attachment_upload.json` (PATCH to mark complete):
```json
{
    "data": {
        "type": "Attachment",
        "id": "5001",
        "attributes": {
            "filename": "chord-chart.pdf",
            "content_type": "application/pdf",
            "file_size": 12345,
            "url": "https://cdn.planningcenteronline.com/chord-chart.pdf"
        }
    }
}
```

`tests/fixtures/services/list_attachments.json`:
```json
{
    "data": [
        {
            "type": "Attachment",
            "id": "5001",
            "attributes": {
                "filename": "chord-chart.pdf",
                "content_type": "application/pdf",
                "file_size": 12345,
                "url": "https://cdn.planningcenteronline.com/chord-chart.pdf"
            }
        },
        {
            "type": "Attachment",
            "id": "5002",
            "attributes": {
                "filename": "reference-track.mp3",
                "content_type": "audio/mpeg",
                "file_size": 5000000,
                "url": "https://cdn.planningcenteronline.com/reference-track.mp3"
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_services.py`:

```python
class TestUploadAttachment:
    async def test_three_step_upload_flow(self, mock_client: AsyncMock) -> None:
        """Verify the helper does POST -> fetch URL -> PUT bytes -> PATCH complete."""
        mock_client.post.return_value = load_fixture("create_attachment.json")
        mock_client.patch.return_value = load_fixture("create_attachment_upload.json")
        # Mock the HTTP client for fetching the source URL and S3 PUT
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.upload_attachment(
            create_url="/services/v2/songs/4001/arrangements/1001/attachments",
            source_url="https://example.com/chord-chart.pdf",
            filename="chord-chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"
        assert result["filename"] == "chord-chart.pdf"
        # Verify POST was called to create the record
        mock_client.post.assert_called_once()
        # Verify PUT was called to upload bytes to S3
        mock_client.put_raw.assert_called_once_with(
            "https://s3.amazonaws.com/presigned-upload-url",
            data=b"fake-pdf-bytes",
            content_type="application/pdf",
        )
        # Verify PATCH was called to mark upload complete
        mock_client.patch.assert_called_once()


class TestCreateAttachment:
    async def test_calls_upload_attachment(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_attachment.json")
        mock_client.patch.return_value = load_fixture("create_attachment_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.create_attachment(
            song_id="4001",
            arrangement_id="1001",
            url="https://example.com/chord-chart.pdf",
            filename="chord-chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"
        call_path = mock_client.post.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "attachments" in call_path


class TestListAttachments:
    async def test_returns_attachments(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_attachments.json")
        api = ServicesAPI(mock_client)
        attachments = await api.list_attachments("4001", "1001")
        assert len(attachments) == 2
        assert attachments[0]["filename"] == "chord-chart.pdf"
        assert attachments[1]["content_type"] == "audio/mpeg"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_attachments.json")
        api = ServicesAPI(mock_client)
        await api.list_attachments("4001", "1001")
        call_path = mock_client.get.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "attachments" in call_path
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py::TestUploadAttachment tests/test_pco_services.py::TestCreateAttachment tests/test_pco_services.py::TestListAttachments -v`
Expected: FAIL

- [ ] **Step 4: Implement API methods**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def upload_attachment(
    self,
    create_url: str,
    source_url: str,
    filename: str,
    content_type: str,
) -> dict[str, Any]:
    """Shared 3-step S3 upload flow.

    1. POST to create_url to create attachment record and get presigned URL
    2. Fetch file from source_url, PUT bytes to presigned URL
    3. PATCH attachment to mark upload complete
    """
    # Step 1: Create attachment record
    payload: dict[str, Any] = {
        "data": {
            "type": "Attachment",
            "attributes": {
                "filename": filename,
                "content_type": content_type,
            },
        }
    }
    create_result = await self._client.post(create_url, data=payload)
    attachment_id = create_result["data"]["id"]
    upload_url = create_result["meta"]["upload"]["url"]

    # Step 2: Fetch file from source URL and upload to S3
    response = await self._client._client.get(source_url)
    response.raise_for_status()
    file_bytes = response.content
    await self._client.put_raw(upload_url, data=file_bytes, content_type=content_type)

    # Step 3: Mark upload complete
    complete_payload: dict[str, Any] = {
        "data": {
            "type": "Attachment",
            "attributes": {"remote_link": None},
        }
    }
    result = await self._client.patch(
        f"/services/v2/attachments/{attachment_id}", data=complete_payload
    )
    return self._simplify_attachment(result["data"])

async def create_attachment(
    self,
    song_id: str,
    arrangement_id: str,
    url: str,
    filename: str,
    content_type: str,
) -> dict[str, Any]:
    """Create a file attachment on an arrangement (PDF, MP3, etc.)."""
    create_url = (
        f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
    )
    return await self.upload_attachment(create_url, url, filename, content_type)

async def list_attachments(
    self, song_id: str, arrangement_id: str
) -> list[dict[str, Any]]:
    """List attachments for an arrangement."""
    result = await self._client.get(
        f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
    )
    return [self._simplify_attachment(a) for a in result.get("data", [])]
```

And add the simplify method:

```python
def _simplify_attachment(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "filename": attrs.get("filename", ""),
        "content_type": attrs.get("content_type"),
        "file_size": attrs.get("file_size"),
        "url": attrs.get("url"),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestUploadAttachment tests/test_pco_services.py::TestCreateAttachment tests/test_pco_services.py::TestListAttachments -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/create_attachment.json tests/fixtures/services/create_attachment_upload.json tests/fixtures/services/list_attachments.json
git commit -m "feat(services): add attachment upload helper and list_attachments"
```

---

### Task 7: Attachment — MCP tools

Register `create_attachment` and `list_attachments` tools.

**Files:**
- Modify: `src/pco_mcp/tools/services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_services_body.py`:

```python
class TestCreateAttachmentToolBody:
    async def test_create_attachment(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Attachment",
                "id": "5001",
                "attributes": {
                    "filename": "chart.pdf",
                    "content_type": "application/pdf",
                    "file_size": None,
                    "url": None,
                },
                "links": {"self": "https://api.planningcenteronline.com/services/v2/attachments/5001"},
            },
            "meta": {"upload": {"url": "https://s3.example.com/upload", "fields": {}}},
        }
        mock_client.patch.return_value = {
            "data": {
                "type": "Attachment",
                "id": "5001",
                "attributes": {
                    "filename": "chart.pdf",
                    "content_type": "application/pdf",
                    "file_size": 1234,
                    "url": "https://cdn.example.com/chart.pdf",
                },
            }
        }
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_attachment")
        result = await fn(
            song_id="4001",
            arrangement_id="1001",
            url="https://example.com/chart.pdf",
            filename="chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"


class TestListAttachmentsToolBody:
    async def test_list_attachments(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Attachment",
                    "id": "5001",
                    "attributes": {
                        "filename": "chart.pdf",
                        "content_type": "application/pdf",
                        "file_size": 1234,
                        "url": "https://cdn.example.com/chart.pdf",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_attachments")
        attachments = await fn(song_id="4001", arrangement_id="1001")
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "chart.pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services_body.py::TestCreateAttachmentToolBody tests/test_tools_services_body.py::TestListAttachmentsToolBody -v`
Expected: FAIL

- [ ] **Step 3: Register the tools**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def create_attachment(
    song_id: str,
    arrangement_id: str,
    url: str,
    filename: str,
    content_type: str,
) -> dict[str, Any]:
    """Upload a file attachment to an arrangement (PDF chord chart, MP3 reference track, etc.).

    Provide a publicly accessible URL — the server fetches the file and uploads it to PCO.
    Supported content types: application/pdf, audio/mpeg, image/png, image/jpeg, etc.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.create_attachment(song_id, arrangement_id, url, filename, content_type)
    )

@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_attachments(song_id: str, arrangement_id: str) -> list[dict[str, Any]]:
    """List file attachments on an arrangement (PDFs, audio files, etc.)."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.list_attachments(song_id, arrangement_id))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services_body.py::TestCreateAttachmentToolBody tests/test_tools_services_body.py::TestListAttachmentsToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services_body.py
git commit -m "feat(services): register attachment MCP tools"
```

---

### Task 8: Media management — API methods

Add `create_media`, `list_media`, `update_media` to `ServicesAPI`.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Create: `tests/fixtures/services/create_media.json`
- Create: `tests/fixtures/services/create_media_upload.json`
- Create: `tests/fixtures/services/list_media.json`
- Create: `tests/fixtures/services/update_media.json`
- Test: `tests/test_pco_services.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/services/create_media.json`:
```json
{
    "data": {
        "type": "Media",
        "id": "6001",
        "attributes": {
            "title": "Worship Background",
            "media_type": "image",
            "thumbnail_url": null,
            "creator_name": "Admin"
        }
    },
    "meta": {
        "upload": {
            "url": "https://s3.amazonaws.com/media-presigned-url",
            "fields": {}
        }
    }
}
```

`tests/fixtures/services/create_media_upload.json`:
```json
{
    "data": {
        "type": "Attachment",
        "id": "6010",
        "attributes": {
            "filename": "background.jpg",
            "content_type": "image/jpeg",
            "file_size": 500000,
            "url": "https://cdn.planningcenteronline.com/background.jpg"
        }
    }
}
```

`tests/fixtures/services/list_media.json`:
```json
{
    "data": [
        {
            "type": "Media",
            "id": "6001",
            "attributes": {
                "title": "Worship Background",
                "media_type": "image",
                "thumbnail_url": "https://cdn.planningcenteronline.com/thumb.jpg",
                "creator_name": "Admin"
            }
        },
        {
            "type": "Media",
            "id": "6002",
            "attributes": {
                "title": "Countdown 5min",
                "media_type": "countdown",
                "thumbnail_url": "https://cdn.planningcenteronline.com/thumb2.jpg",
                "creator_name": "Tech Lead"
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

`tests/fixtures/services/update_media.json`:
```json
{
    "data": {
        "type": "Media",
        "id": "6001",
        "attributes": {
            "title": "Updated Background",
            "media_type": "image",
            "thumbnail_url": "https://cdn.planningcenteronline.com/thumb.jpg",
            "creator_name": "Admin",
            "themes": "Worship, Nature"
        }
    }
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_services.py`:

```python
class TestCreateMedia:
    async def test_creates_media_with_upload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_media.json")
        mock_client.patch.return_value = load_fixture("create_media_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-image-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.create_media(
            title="Worship Background",
            media_type="image",
            url="https://example.com/background.jpg",
            filename="background.jpg",
            content_type="image/jpeg",
        )
        assert result["id"] == "6001"
        assert result["title"] == "Worship Background"

    async def test_posts_media_then_attachment(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_media.json")
        mock_client.patch.return_value = load_fixture("create_media_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-image-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        await api.create_media(
            title="Worship Background",
            media_type="image",
            url="https://example.com/background.jpg",
            filename="background.jpg",
            content_type="image/jpeg",
        )
        # First POST creates the media, second would be the attachment
        first_post_path = mock_client.post.call_args_list[0].args[0]
        assert "/media" in first_post_path


class TestListMedia:
    async def test_returns_media_list(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_media.json")
        api = ServicesAPI(mock_client)
        media = await api.list_media()
        assert len(media) == 2
        assert media[0]["title"] == "Worship Background"
        assert media[1]["media_type"] == "countdown"

    async def test_filters_by_media_type(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_media.json")
        api = ServicesAPI(mock_client)
        await api.list_media(media_type="image")
        params = mock_client.get.call_args.kwargs.get("params", {})
        assert params.get("where[media_type]") == "image"


class TestUpdateMedia:
    async def test_returns_updated_media(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_media.json")
        api = ServicesAPI(mock_client)
        media = await api.update_media("6001", title="Updated Background")
        assert media["title"] == "Updated Background"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_media.json")
        api = ServicesAPI(mock_client)
        await api.update_media("6001", title="Updated Background")
        call_path = mock_client.patch.call_args.args[0]
        assert "6001" in call_path
        assert "/media/" in call_path
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py::TestCreateMedia tests/test_pco_services.py::TestListMedia tests/test_pco_services.py::TestUpdateMedia -v`
Expected: FAIL

- [ ] **Step 4: Implement API methods**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def create_media(
    self,
    title: str,
    media_type: str,
    url: str,
    filename: str,
    content_type: str,
    creator_name: str | None = None,
) -> dict[str, Any]:
    """Create an org-level media item (background, countdown, etc.) with file upload."""
    # Step 1: Create the media record
    attributes: dict[str, Any] = {"title": title, "media_type": media_type}
    if creator_name is not None:
        attributes["creator_name"] = creator_name
    payload: dict[str, Any] = {"data": {"type": "Media", "attributes": attributes}}
    create_result = await self._client.post("/services/v2/media", data=payload)
    media_id = create_result["data"]["id"]
    media_record = self._simplify_media(create_result["data"])

    # Step 2: Upload the file as an attachment on the media
    upload_url = create_result["meta"]["upload"]["url"]
    response = await self._client._client.get(url)
    response.raise_for_status()
    file_bytes = response.content
    await self._client.put_raw(upload_url, data=file_bytes, content_type=content_type)

    # Step 3: Mark upload complete
    complete_payload: dict[str, Any] = {
        "data": {
            "type": "Attachment",
            "attributes": {"filename": filename, "content_type": content_type},
        }
    }
    await self._client.patch(
        f"/services/v2/media/{media_id}/attachments", data=complete_payload
    )
    return media_record

async def list_media(self, media_type: str | None = None) -> list[dict[str, Any]]:
    """List org-level media items, optionally filtered by type."""
    params: dict[str, Any] = {}
    if media_type:
        params["where[media_type]"] = media_type
    result = await self._client.get("/services/v2/media", params=params)
    return [self._simplify_media(m) for m in result.get("data", [])]

async def update_media(
    self,
    media_id: str,
    title: str | None = None,
    themes: str | None = None,
    creator_name: str | None = None,
) -> dict[str, Any]:
    """Update a media item's metadata."""
    attributes: dict[str, Any] = {}
    if title is not None:
        attributes["title"] = title
    if themes is not None:
        attributes["themes"] = themes
    if creator_name is not None:
        attributes["creator_name"] = creator_name
    payload: dict[str, Any] = {"data": {"type": "Media", "attributes": attributes}}
    result = await self._client.patch(f"/services/v2/media/{media_id}", data=payload)
    return self._simplify_media(result["data"])
```

And add the simplify method:

```python
def _simplify_media(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "id": raw["id"],
        "title": attrs.get("title", ""),
        "media_type": attrs.get("media_type"),
        "thumbnail_url": attrs.get("thumbnail_url"),
        "creator_name": attrs.get("creator_name"),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestCreateMedia tests/test_pco_services.py::TestListMedia tests/test_pco_services.py::TestUpdateMedia -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/create_media.json tests/fixtures/services/create_media_upload.json tests/fixtures/services/list_media.json tests/fixtures/services/update_media.json
git commit -m "feat(services): add media management API methods"
```

---

### Task 9: Media management — MCP tools

Register `create_media`, `list_media`, `update_media` tools.

**Files:**
- Modify: `src/pco_mcp/tools/services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_services_body.py`:

```python
class TestCreateMediaToolBody:
    async def test_create_media(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Media",
                "id": "6001",
                "attributes": {
                    "title": "Background",
                    "media_type": "image",
                    "thumbnail_url": None,
                    "creator_name": "Admin",
                },
            },
            "meta": {"upload": {"url": "https://s3.example.com/upload", "fields": {}}},
        }
        mock_client.patch.return_value = {
            "data": {
                "type": "Attachment",
                "id": "6010",
                "attributes": {
                    "filename": "bg.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 5000,
                    "url": "https://cdn.example.com/bg.jpg",
                },
            }
        }
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"img-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_media")
        result = await fn(
            title="Background",
            media_type="image",
            url="https://example.com/bg.jpg",
            filename="bg.jpg",
            content_type="image/jpeg",
        )
        assert result["id"] == "6001"


class TestListMediaToolBody:
    async def test_list_media(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Media",
                    "id": "6001",
                    "attributes": {
                        "title": "Background",
                        "media_type": "image",
                        "thumbnail_url": None,
                        "creator_name": "Admin",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_media")
        media = await fn()
        assert len(media) == 1
        assert media[0]["title"] == "Background"


class TestUpdateMediaToolBody:
    async def test_update_media(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Media",
                "id": "6001",
                "attributes": {
                    "title": "New Title",
                    "media_type": "image",
                    "thumbnail_url": None,
                    "creator_name": "Admin",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_media")
        result = await fn(media_id="6001", title="New Title")
        assert result["title"] == "New Title"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services_body.py::TestCreateMediaToolBody tests/test_tools_services_body.py::TestListMediaToolBody tests/test_tools_services_body.py::TestUpdateMediaToolBody -v`
Expected: FAIL

- [ ] **Step 3: Register the tools**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def create_media(
    title: str,
    media_type: str,
    url: str,
    filename: str,
    content_type: str,
    creator_name: str | None = None,
) -> dict[str, Any]:
    """Upload an org-level media item (background image, countdown video, bumper video).

    media_type must be one of: 'image', 'video', 'countdown', 'document'.
    Provide a publicly accessible URL — the server fetches and uploads to PCO.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.create_media(title, media_type, url, filename, content_type, creator_name)
    )

@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_media(media_type: str | None = None) -> list[dict[str, Any]]:
    """List org-level media items (backgrounds, countdowns, videos). Optionally filter by type."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.list_media(media_type=media_type))

@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def update_media(
    media_id: str,
    title: str | None = None,
    themes: str | None = None,
    creator_name: str | None = None,
) -> dict[str, Any]:
    """Update a media item's title, themes, or creator."""
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(
        api.update_media(media_id, title=title, themes=themes, creator_name=creator_name)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services_body.py::TestCreateMediaToolBody tests/test_tools_services_body.py::TestListMediaToolBody tests/test_tools_services_body.py::TestUpdateMediaToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services_body.py
git commit -m "feat(services): register media management MCP tools"
```

---

### Task 10: CCLI compliance — API methods

Add `get_ccli_reporting`, `get_song_usage_report` (reuse existing `get_song_schedule_history`), and `flag_missing_ccli`.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Create: `tests/fixtures/services/get_ccli_reporting.json`
- Create: `tests/fixtures/services/list_songs_page1.json`
- Create: `tests/fixtures/services/list_songs_page2.json`
- Test: `tests/test_pco_services.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/services/get_ccli_reporting.json`:
```json
{
    "data": {
        "type": "ItemNote",
        "id": "7001",
        "attributes": {
            "print_count": 5,
            "digital_count": 12,
            "recording_count": 2,
            "translation_count": 0
        }
    }
}
```

`tests/fixtures/services/list_songs_page1.json`:
```json
{
    "data": [
        {
            "type": "Song",
            "id": "4001",
            "attributes": {
                "title": "Amazing Grace",
                "author": "John Newton",
                "ccli_number": 4669344,
                "last_scheduled_at": "2026-03-30T09:00:00Z"
            }
        },
        {
            "type": "Song",
            "id": "4002",
            "attributes": {
                "title": "How Great Is Our God",
                "author": "Chris Tomlin",
                "ccli_number": null,
                "last_scheduled_at": "2026-03-23T09:00:00Z"
            }
        }
    ],
    "meta": {"total_count": 4, "count": 2, "next": {"offset": 2}},
    "links": {"next": "https://api.planningcenteronline.com/services/v2/songs?offset=2"}
}
```

`tests/fixtures/services/list_songs_page2.json`:
```json
{
    "data": [
        {
            "type": "Song",
            "id": "4003",
            "attributes": {
                "title": "Oceans",
                "author": "Hillsong UNITED",
                "ccli_number": 6428767,
                "last_scheduled_at": "2026-02-15T09:00:00Z"
            }
        },
        {
            "type": "Song",
            "id": "4004",
            "attributes": {
                "title": "Custom Song",
                "author": "Local Writer",
                "ccli_number": null,
                "last_scheduled_at": null
            }
        }
    ],
    "meta": {"total_count": 4, "count": 2},
    "links": {}
}
```

- [ ] **Step 2: Write failing tests**

Add to `tests/test_pco_services.py`:

```python
class TestGetCCLIReporting:
    async def test_returns_ccli_data(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_ccli_reporting.json")
        api = ServicesAPI(mock_client)
        report = await api.get_ccli_reporting("201", "301", "501")
        assert report["print_count"] == 5
        assert report["digital_count"] == 12
        assert report["recording_count"] == 2
        assert report["translation_count"] == 0

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_ccli_reporting.json")
        api = ServicesAPI(mock_client)
        await api.get_ccli_reporting("201", "301", "501")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "501" in call_path
        assert "ccli_reporting" in call_path


class TestFlagMissingCCLI:
    async def test_returns_songs_without_ccli(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = (
            load_fixture("list_songs_page1.json")["data"]
            + load_fixture("list_songs_page2.json")["data"]
        )
        api = ServicesAPI(mock_client)
        result = await api.flag_missing_ccli()
        assert result["total_scanned"] == 4
        assert result["total_missing"] == 2
        missing_titles = [s["title"] for s in result["songs"]]
        assert "How Great Is Our God" in missing_titles
        assert "Custom Song" in missing_titles
        assert "Amazing Grace" not in missing_titles

    async def test_caps_at_200_songs(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = (
            load_fixture("list_songs_page1.json")["data"]
            + load_fixture("list_songs_page2.json")["data"]
        )
        api = ServicesAPI(mock_client)
        await api.flag_missing_ccli()
        call_kwargs = mock_client.get_all.call_args.kwargs
        assert call_kwargs.get("max_pages", 50) <= 10  # 25 per page * 10 = 250 max
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py::TestGetCCLIReporting tests/test_pco_services.py::TestFlagMissingCCLI -v`
Expected: FAIL

- [ ] **Step 4: Implement API methods**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def get_ccli_reporting(
    self, service_type_id: str, plan_id: str, item_id: str
) -> dict[str, Any]:
    """Get CCLI reporting data for a plan item."""
    result = await self._client.get(
        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        f"/items/{item_id}/ccli_reporting"
    )
    return self._simplify_ccli_reporting(result["data"])

async def flag_missing_ccli(self) -> dict[str, Any]:
    """Scan the song library and return songs missing CCLI numbers.

    Caps at ~200 songs to avoid excessive API calls.
    """
    all_songs = await self._client.get_all(
        "/services/v2/songs", params={"per_page": 25}, max_pages=8
    )
    missing = []
    for raw in all_songs:
        attrs = raw.get("attributes", {})
        if not attrs.get("ccli_number"):
            missing.append(self._simplify_song(raw))
    return {
        "total_scanned": len(all_songs),
        "total_missing": len(missing),
        "songs": missing,
    }
```

And add the simplify method:

```python
def _simplify_ccli_reporting(self, raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes", {})
    return {
        "print_count": attrs.get("print_count", 0),
        "digital_count": attrs.get("digital_count", 0),
        "recording_count": attrs.get("recording_count", 0),
        "translation_count": attrs.get("translation_count", 0),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestGetCCLIReporting tests/test_pco_services.py::TestFlagMissingCCLI -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/get_ccli_reporting.json tests/fixtures/services/list_songs_page1.json tests/fixtures/services/list_songs_page2.json
git commit -m "feat(services): add CCLI reporting and flag_missing_ccli API methods"
```

---

### Task 11: CCLI compliance — MCP tools

Register `get_ccli_reporting`, `get_song_usage_report`, and `flag_missing_ccli` tools.

Note: `get_song_usage_report` reuses the existing `get_song_schedule_history` API method — it's a new tool name wrapping the same data for CCLI context.

**Files:**
- Modify: `src/pco_mcp/tools/services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_services_body.py`:

```python
class TestGetCCLIReportingToolBody:
    async def test_get_ccli_reporting(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "type": "ItemNote",
                "id": "7001",
                "attributes": {
                    "print_count": 5,
                    "digital_count": 12,
                    "recording_count": 2,
                    "translation_count": 0,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_ccli_reporting")
        report = await fn(service_type_id="201", plan_id="301", item_id="501")
        assert report["print_count"] == 5


class TestGetSongUsageReportToolBody:
    async def test_get_song_usage_report(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "SongSchedule",
                    "id": "8001",
                    "attributes": {
                        "plan_dates": "March 30, 2026",
                        "plan_sort_date": "2026-03-30T09:00:00Z",
                        "service_type_name": "Sunday Morning",
                        "arrangement_name": "Standard",
                        "key_name": "G",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_song_usage_report")
        history = await fn(song_id="4001")
        assert len(history) == 1
        assert history[0]["service_type_name"] == "Sunday Morning"


class TestFlagMissingCCLIToolBody:
    async def test_flag_missing_ccli(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = [
            {
                "type": "Song",
                "id": "4001",
                "attributes": {
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "ccli_number": 4669344,
                    "last_scheduled_at": "2026-03-30T09:00:00Z",
                },
            },
            {
                "type": "Song",
                "id": "4002",
                "attributes": {
                    "title": "Missing CCLI Song",
                    "author": "Unknown",
                    "ccli_number": None,
                    "last_scheduled_at": None,
                },
            },
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "flag_missing_ccli")
        result = await fn()
        assert result["total_scanned"] == 2
        assert result["total_missing"] == 1
        assert result["songs"][0]["title"] == "Missing CCLI Song"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services_body.py::TestGetCCLIReportingToolBody tests/test_tools_services_body.py::TestGetSongUsageReportToolBody tests/test_tools_services_body.py::TestFlagMissingCCLIToolBody -v`
Expected: FAIL

- [ ] **Step 3: Register the tools**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=READ_ANNOTATIONS)
async def get_ccli_reporting(
    service_type_id: str, plan_id: str, item_id: str
) -> dict[str, Any]:
    """Get CCLI reporting data for a plan item (print, digital, recording, translation counts).

    CCLI reporting is tracked automatically by PCO when songs are added to plans.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.get_ccli_reporting(service_type_id, plan_id, item_id))

@mcp.tool(annotations=READ_ANNOTATIONS)
async def get_song_usage_report(song_id: str) -> list[dict[str, Any]]:
    """Get all dates a song was scheduled, with service type, key, and arrangement.

    Useful for CCLI annual reporting — shows how many times a song was used.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.get_song_schedule_history(song_id))

@mcp.tool(annotations=READ_ANNOTATIONS)
async def flag_missing_ccli() -> dict[str, Any]:
    """Scan the song library for songs missing CCLI numbers.

    Returns a list of songs without CCLI numbers along with total counts.
    Scans up to ~200 songs. Use update_song to fill in missing numbers.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.flag_missing_ccli())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services_body.py::TestGetCCLIReportingToolBody tests/test_tools_services_body.py::TestGetSongUsageReportToolBody tests/test_tools_services_body.py::TestFlagMissingCCLIToolBody -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services_body.py
git commit -m "feat(services): register CCLI compliance MCP tools"
```

---

### Task 12: Service type creation — API method + MCP tool

Add `create_service_type` to `ServicesAPI` and register the tool.

**Files:**
- Modify: `src/pco_mcp/pco/services.py`
- Modify: `src/pco_mcp/tools/services.py`
- Create: `tests/fixtures/services/create_service_type.json`
- Test: `tests/test_pco_services.py`
- Test: `tests/test_tools_services_body.py`

- [ ] **Step 1: Create fixture**

`tests/fixtures/services/create_service_type.json`:
```json
{
    "data": {
        "type": "ServiceType",
        "id": "210",
        "attributes": {
            "name": "Wednesday Night",
            "frequency": "Every 1 week",
            "last_plan_from": null
        }
    }
}
```

- [ ] **Step 2: Write failing API tests**

Add to `tests/test_pco_services.py`:

```python
class TestCreateServiceType:
    async def test_returns_created_service_type(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        st = await api.create_service_type("Wednesday Night", frequency="Every 1 week")
        assert st["id"] == "210"
        assert st["name"] == "Wednesday Night"
        assert st["frequency"] == "Every 1 week"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        await api.create_service_type("Wednesday Night", frequency="Every 1 week")
        call_path = mock_client.post.call_args.args[0]
        assert "service_types" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "ServiceType"
        assert data["data"]["attributes"]["name"] == "Wednesday Night"
        assert data["data"]["attributes"]["frequency"] == "Every 1 week"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        await api.create_service_type("Wednesday Night")
        data = mock_client.post.call_args.kwargs["data"]
        assert "frequency" not in data["data"]["attributes"]
```

- [ ] **Step 3: Write failing tool test**

Add to `tests/test_tools_services_body.py`:

```python
class TestCreateServiceTypeToolBody:
    async def test_create_service_type(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "ServiceType",
                "id": "210",
                "attributes": {
                    "name": "Wednesday Night",
                    "frequency": "Every 1 week",
                    "last_plan_from": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_service_type")
        st = await fn(name="Wednesday Night", frequency="Every 1 week")
        assert st["id"] == "210"
        assert st["name"] == "Wednesday Night"
```

- [ ] **Step 4: Run all failing tests**

Run: `pytest tests/test_pco_services.py::TestCreateServiceType tests/test_tools_services_body.py::TestCreateServiceTypeToolBody -v`
Expected: FAIL

- [ ] **Step 5: Implement API method**

Add to `ServicesAPI` in `src/pco_mcp/pco/services.py`:

```python
async def create_service_type(
    self, name: str, frequency: str | None = None
) -> dict[str, Any]:
    """Create a new service type."""
    attributes: dict[str, Any] = {"name": name}
    if frequency is not None:
        attributes["frequency"] = frequency
    payload: dict[str, Any] = {"data": {"type": "ServiceType", "attributes": attributes}}
    result = await self._client.post("/services/v2/service_types", data=payload)
    return self._simplify_service_type(result["data"])
```

- [ ] **Step 6: Register the tool**

Add to `register_services_tools` in `src/pco_mcp/tools/services.py`:

```python
@mcp.tool(annotations=WRITE_ANNOTATIONS)
async def create_service_type(
    name: str, frequency: str | None = None
) -> dict[str, Any]:
    """Create a new service type (e.g., 'Sunday Morning', 'Wednesday Night').

    A blank org needs service types before plans can be created.
    Frequency examples: 'Every 1 week', 'Every 2 weeks'.
    """
    from pco_mcp.tools._context import get_services_api, safe_tool_call

    api = get_services_api()
    return await safe_tool_call(api.create_service_type(name, frequency=frequency))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py::TestCreateServiceType tests/test_tools_services_body.py::TestCreateServiceTypeToolBody -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/pco_mcp/pco/services.py src/pco_mcp/tools/services.py tests/test_pco_services.py tests/test_tools_services_body.py tests/fixtures/services/create_service_type.json
git commit -m "feat(services): add create_service_type API method and MCP tool"
```

---

### Task 13: Full test suite + coverage check

Run the entire test suite to ensure nothing is broken and coverage stays above 90%.

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run with coverage**

Run: `pytest tests/ --cov=pco_mcp --cov-report=term-missing`
Expected: Coverage >= 90%, no unexpected missing lines

- [ ] **Step 3: Run linter**

Run: `ruff check src/pco_mcp/pco/services.py src/pco_mcp/tools/services.py`
Expected: No issues

- [ ] **Step 4: Run type checker**

Run: `mypy src/pco_mcp/pco/services.py src/pco_mcp/tools/services.py`
Expected: No errors

- [ ] **Step 5: Fix any issues found in steps 1-4**

Address any test failures, coverage gaps, lint errors, or type errors.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test(services): full suite passing with services expansion"
```
