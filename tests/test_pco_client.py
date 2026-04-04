
import httpx
import pytest

from pco_mcp.pco.client import PCOAPIError, PCOClient, PCORateLimitError


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
