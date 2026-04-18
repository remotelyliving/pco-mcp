import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PagedResult:
    """Result of a paginated PCO fetch. Behaves list-like for backwards compat.

    - items: raw JSON:API records collected across pages
    - total_count: from meta.total_count when PCO supplies it (may be None)
    - truncated: True if max_pages cap fired while more data was available
    """

    items: list[Any] = field(default_factory=list)
    total_count: int | None = None
    truncated: bool = False

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


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

    def __init__(
        self,
        base_url: str,
        access_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
        )

    async def close(self) -> None:
        if self._owns_client:
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
        url = self._url(path)
        response = await self._client.get(url, params=params, headers=self._auth_headers())
        logger.debug("GET %s -> %s", url, response.status_code)
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the PCO API."""
        url = self._url(path)
        response = await self._client.post(url, json=data, headers=self._auth_headers())
        logger.debug("POST %s -> %s", url, response.status_code)
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def patch(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a PATCH request to the PCO API."""
        url = self._url(path)
        response = await self._client.patch(url, json=data, headers=self._auth_headers())
        logger.debug("PATCH %s -> %s", url, response.status_code)
        self._check_response(response)
        result: dict[str, Any] = response.json()
        return result

    async def delete(self, path: str) -> None:
        """Make a DELETE request to the PCO API."""
        url = self._url(path)
        response = await self._client.delete(url, headers=self._auth_headers())
        logger.debug("DELETE %s -> %s", url, response.status_code)
        self._check_response(response)

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

    async def get_all(
        self, path: str, params: dict[str, Any] | None = None, max_pages: int = 100
    ) -> PagedResult:
        """Fetch all pages of a paginated PCO endpoint.

        Returns a PagedResult dataclass carrying items + total_count + truncated.
        PagedResult is list-like so callers can iterate/index it directly.
        Uses per_page=100 (PCO's maximum) unless the caller overrides it.
        """
        items: list[Any] = []
        current_params: dict[str, Any] = dict(params or {})
        current_params.setdefault("per_page", 100)
        total_count: int | None = None
        for page_num in range(max_pages):
            result = await self.get(path, params=current_params)
            items.extend(result.get("data", []))
            meta = result.get("meta") or {}
            if "total_count" in meta:
                total_count = meta["total_count"]
            next_link = result.get("links", {}).get("next")
            if not next_link:
                return PagedResult(items=items, total_count=total_count, truncated=False)
            next_offset = meta.get("next", {}).get("offset")
            if next_offset is None:
                return PagedResult(items=items, total_count=total_count, truncated=False)
            current_params["offset"] = next_offset
            if page_num == max_pages - 1:
                logger.warning(
                    "get_all truncated at max_pages=%d for %s (fetched %d, total_count=%s)",
                    max_pages, path, len(items), total_count,
                )
                return PagedResult(items=items, total_count=total_count, truncated=True)
        return PagedResult(items=items, total_count=total_count, truncated=False)

    def _check_response(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if response.is_success:
            # Warn if rate-limit headroom is low (threshold: <10 remaining)
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                try:
                    if int(remaining) < 10:
                        logger.warning(
                            "PCO rate limit approaching: %s requests remaining", remaining
                        )
                except ValueError:
                    pass
            return
        detail = self._extract_error_detail(response)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "20"))
            logger.error(
                "PCO rate limit hit (429) — retry after %ss: %s", retry_after, detail
            )
            raise PCORateLimitError(retry_after=retry_after, detail=detail)
        logger.warning("PCO API non-success response: %s %s", response.status_code, detail)
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
