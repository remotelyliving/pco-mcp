"""Tests for PCOClient.post() and PCOClient.patch() methods."""
import httpx
import pytest

from pco_mcp.pco.client import PCOAPIError, PCOClient, PCORateLimitError


@pytest.fixture
def pco_client() -> PCOClient:
    return PCOClient(
        base_url="https://api.planningcenteronline.com",
        access_token="test-token-123",
    )


class TestPCOClientPost:
    async def test_post_success_returns_json(self, pco_client: PCOClient) -> None:
        response_data = {"data": {"type": "Person", "id": "99", "attributes": {}}}
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=response_data)
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        result = await pco_client.post("/people/v2/people", data={"data": {"type": "Person"}})
        assert result["data"]["id"] == "99"

    async def test_post_sends_json_body(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"data": {}})

        pco_client._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        payload = {"data": {"type": "Person", "attributes": {"first_name": "New"}}}
        await pco_client.post("/people/v2/people", data=payload)
        assert captured_request is not None
        import json
        body = json.loads(captured_request.content)
        assert body["data"]["type"] == "Person"

    async def test_post_sends_bearer_auth(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"data": {}})

        pco_client._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        await pco_client.post("/people/v2/people", data={})
        assert captured_request is not None
        assert captured_request.headers["authorization"] == "Bearer test-token-123"

    async def test_post_raises_on_error_response(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                422,
                json={"errors": [{"detail": "Validation failed"}]},
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCOAPIError) as exc_info:
            await pco_client.post("/people/v2/people", data={})
        assert exc_info.value.status_code == 422

    async def test_post_raises_rate_limit_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                429,
                json={"errors": [{"detail": "rate limited"}]},
                headers={"Retry-After": "30"},
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCORateLimitError) as exc_info:
            await pco_client.post("/people/v2/people", data={})
        assert exc_info.value.retry_after == 30


class TestPCOClientPatch:
    async def test_patch_success_returns_json(self, pco_client: PCOClient) -> None:
        response_data = {"data": {"type": "Person", "id": "1001", "attributes": {"first_name": "Updated"}}}
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=response_data)
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        result = await pco_client.patch("/people/v2/people/1001", data={"data": {"type": "Person", "id": "1001"}})
        assert result["data"]["attributes"]["first_name"] == "Updated"

    async def test_patch_sends_bearer_auth(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"data": {}})

        pco_client._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        await pco_client.patch("/people/v2/people/1001", data={})
        assert captured_request is not None
        assert captured_request.headers["authorization"] == "Bearer test-token-123"

    async def test_patch_raises_on_404(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                404,
                json={"errors": [{"detail": "Not found"}]},
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCOAPIError) as exc_info:
            await pco_client.patch("/people/v2/people/9999", data={})
        assert exc_info.value.status_code == 404

    async def test_patch_uses_patch_method(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"data": {}})

        pco_client._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        await pco_client.patch("/people/v2/people/1001", data={})
        assert captured_request is not None
        assert captured_request.method == "PATCH"
