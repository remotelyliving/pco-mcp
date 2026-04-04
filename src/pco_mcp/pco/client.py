from typing import Any

import httpx


class PCOAPIError(Exception):
    """Raised when the PCO API returns a non-success status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PCO API error {status_code}: {detail}")


class PCORateLimitError(PCOAPIError):
    """Raised when the PCO API returns 429 Too Many Requests."""

    def __init__(self, retry_after: int, detail: str) -> None:
        self.retry_after = retry_after
        super().__init__(status_code=429, detail=detail)


class PCOClient:
    """Async HTTP client for the Planning Center Online API."""

    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _url(self, path: str) -> str:
        """Build a full URL from a relative path."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self._base_url + "/" + path.lstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers for each request."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the PCO API. Raises on non-2xx."""
        response = await self._client.get(
            self._url(path), params=params, headers=self._auth_headers()
        )
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the PCO API."""
        response = await self._client.post(
            self._url(path), json=data, headers=self._auth_headers()
        )
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def patch(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a PATCH request to the PCO API."""
        response = await self._client.patch(
            self._url(path), json=data, headers=self._auth_headers()
        )
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def get_all(
        self, path: str, params: dict[str, Any] | None = None, max_pages: int = 50
    ) -> list[Any]:
        """Fetch all pages of a paginated PCO endpoint. Returns flat list of data items."""
        all_data: list[Any] = []
        current_params: dict[str, Any] = dict(params or {})
        for _ in range(max_pages):
            result = await self.get(path, params=current_params)
            all_data.extend(result.get("data", []))
            next_link = result.get("links", {}).get("next")
            if not next_link:
                break
            next_offset = result.get("meta", {}).get("next", {}).get("offset")
            if next_offset is None:
                break
            current_params["offset"] = next_offset
        return all_data

    def _check_response(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if response.is_success:
            return
        detail = self._extract_error_detail(response)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "20"))
            raise PCORateLimitError(retry_after=retry_after, detail=detail)
        raise PCOAPIError(status_code=response.status_code, detail=detail)

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract error detail from a PCO error response."""
        try:
            body: dict[str, Any] = response.json()
            errors = body.get("errors", [])
            if errors:
                detail: str = errors[0].get("detail", "Unknown error")
                return detail
        except Exception:  # noqa: S110
            pass
        return f"HTTP {response.status_code}"
