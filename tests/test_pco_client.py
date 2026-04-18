
from unittest.mock import AsyncMock

import httpx
import pytest

from pco_mcp.pco.client import PagedResult, PCOAPIError, PCOClient, PCORateLimitError


@pytest.fixture
def pco_client() -> PCOClient:
    return PCOClient(
        base_url="https://api.planningcenteronline.com",
        access_token="test-token-123",
    )


class TestPCOClientGet:
    async def test_get_success(self, pco_client: PCOClient) -> None:
        response_data = {
            "data": [{"type": "Person", "id": "1", "attributes": {"first_name": "Alice"}}]
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=response_data,
                headers={
                    "X-PCO-API-Request-Rate-Count": "5",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        result = await pco_client.get("/people/v2/people")
        assert result["data"][0]["attributes"]["first_name"] == "Alice"

    async def test_get_401_raises_api_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                401,
                json={"errors": [{"detail": "unauthorized"}]},
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCOAPIError) as exc_info:
            await pco_client.get("/people/v2/people")
        assert exc_info.value.status_code == 401

    async def test_get_429_raises_rate_limit_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                429,
                json={"errors": [{"detail": "rate limited"}]},
                headers={
                    "Retry-After": "5",
                    "X-PCO-API-Request-Rate-Count": "100",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCORateLimitError) as exc_info:
            await pco_client.get("/people/v2/people")
        assert exc_info.value.retry_after == 5

    async def test_get_includes_bearer_auth(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                200,
                json={"data": []},
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )

        pco_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(capture_handler)
        )
        await pco_client.get("/people/v2/people")
        assert captured_request is not None
        assert captured_request.headers["authorization"] == "Bearer test-token-123"


class TestPCOClientDelete:
    async def test_delete_success(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                204,
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        result = await pco_client.delete("/services/v2/service_types/201/plans/301/items/504")
        assert result is None

    async def test_delete_404_raises_api_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                404,
                json={"errors": [{"detail": "not found"}]},
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCOAPIError) as exc_info:
            await pco_client.delete("/services/v2/service_types/201/plans/301/items/999")
        assert exc_info.value.status_code == 404

    async def test_delete_includes_bearer_auth(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                204,
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )

        pco_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(capture_handler)
        )
        await pco_client.delete("/services/v2/service_types/201/plans/301/items/504")
        assert captured_request is not None
        assert captured_request.headers["authorization"] == "Bearer test-token-123"
        assert captured_request.method == "DELETE"


class TestPCOClientPagination:
    async def test_get_all_pages(self, pco_client: PCOClient) -> None:
        page1 = {
            "data": [{"id": "1"}],
            "meta": {"total_count": 2, "count": 1, "next": {"offset": 1}},
            "links": {"next": "https://api.planningcenteronline.com/people/v2/people?offset=1"},
        }
        page2 = {
            "data": [{"id": "2"}],
            "meta": {"total_count": 2, "count": 1},
        }
        call_count = 0

        def paginated_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            data = page1 if call_count == 1 else page2
            return httpx.Response(
                200,
                json=data,
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )

        pco_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(paginated_handler)
        )
        results = await pco_client.get_all("/people/v2/people")
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[1]["id"] == "2"


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


@pytest.fixture
def make_client() -> PCOClient:
    c = PCOClient(base_url="https://api.example.com", access_token="t")
    c.get = AsyncMock()  # type: ignore[method-assign]
    return c


class TestGetAllReturnsPagedResult:
    async def test_returns_paged_result_single_page(self, make_client: PCOClient) -> None:
        make_client.get.return_value = {
            "data": [{"id": "1"}, {"id": "2"}],
            "links": {},
            "meta": {"total_count": 2},
        }
        result = await make_client.get_all("/things")
        assert isinstance(result, PagedResult)
        assert result.items == [{"id": "1"}, {"id": "2"}]
        assert result.truncated is False

    async def test_sets_truncated_when_max_pages_fires(self, make_client: PCOClient) -> None:
        # Every page has a next link and offset, simulating unlimited pagination
        make_client.get.return_value = {
            "data": [{"id": "x"}],
            "links": {"next": "https://api.example.com/things?offset=100"},
            "meta": {"next": {"offset": 100}, "total_count": 500},
        }
        result = await make_client.get_all("/things", max_pages=3)
        assert result.truncated is True
        assert result.total_count == 500
        assert len(result.items) == 3  # one item per page, three pages

    async def test_total_count_captured_from_last_page(self, make_client: PCOClient) -> None:
        # When next link clears, the response's meta.total_count is captured
        make_client.get.return_value = {
            "data": [{"id": "1"}],
            "links": {},
            "meta": {"total_count": 1},
        }
        result = await make_client.get_all("/things")
        assert result.total_count == 1
        assert result.truncated is False

    async def test_iterable_like_list(self, make_client: PCOClient) -> None:
        # Confirms the list-like shim works end-to-end
        make_client.get.return_value = {
            "data": [{"id": "a"}, {"id": "b"}],
            "links": {},
            "meta": {},
        }
        result = await make_client.get_all("/things")
        as_list = [item["id"] for item in result]
        assert as_list == ["a", "b"]
