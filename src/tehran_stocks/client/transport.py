"""Sync and async HTTP/2 transports built on Pydantic's httpx2."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import math
import time
from typing import Any

import httpx2

from tehran_stocks.exceptions import RateLimitError, TSETMCError

DEFAULT_BASE_URL = "https://cdn.tsetmc.com"
DEFAULT_TIMEOUT = 15.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}
RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 502, 503, 504})


class _BaseTransport:
    """Shared configuration, backoff, and error mapping for TSETMC HTTP transports."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        proxy: str | httpx2.Proxy | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_backoff < 0:
            raise ValueError("retry_backoff must be >= 0")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.proxy = proxy or None
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        self.headers = merged_headers

    def _client_kwargs(self, transport: Any = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "base_url": self.base_url,
            "headers": self.headers,
            "timeout": self.timeout,
            "http2": True,
            "follow_redirects": True,
        }
        if self.proxy is not None:
            kwargs["proxy"] = self.proxy
        if transport is not None:
            kwargs["transport"] = transport
        return kwargs

    @staticmethod
    def _create_http_client(client_cls: Any, kwargs: dict[str, Any]) -> Any:
        try:
            return client_cls(**kwargs)
        except ImportError as exc:
            if "Using SOCKS proxy" in str(exc) and "'socksio' package is not installed" in str(exc):
                raise TSETMCError(
                    "SOCKS proxy support requires the optional 'socksio' dependency. "
                    'Install it with `pip install "tehran-stocks[socks]"` '
                    'or use `uvx --from "tehran-stocks[socks]" tse ...`.'
                ) from exc
            raise

    @staticmethod
    def _parse_retry_after(response: httpx2.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            seconds = float(raw.strip())
        except ValueError:
            return None
        return seconds if math.isfinite(seconds) and seconds >= 0 else None

    def _backoff_delay(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return retry_after
        return float(self.retry_backoff * (2**attempt))

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        return status_code in RETRY_STATUS_CODES

    @staticmethod
    def _extract_url(response: httpx2.Response, fallback_url: str | None = None) -> str | None:
        try:
            return str(response.request.url)
        except RuntimeError:
            return fallback_url

    @staticmethod
    def _decode_json_response(
        response: httpx2.Response,
        fallback_url: str | None = None,
    ) -> Any:
        url = _BaseTransport._extract_url(response, fallback_url)
        status_code = response.status_code

        if status_code == 429:
            retry_after = _BaseTransport._parse_retry_after(response)
            raise RateLimitError(
                message=f"TSETMC rate limit exceeded (HTTP 429) for {url or 'request'}",
                status_code=status_code,
                url=url,
                retry_after=retry_after,
            )

        if status_code >= 400:
            raise TSETMCError(
                message=f"TSETMC HTTP {status_code} error for {url or 'request'}",
                status_code=status_code,
                url=url,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise TSETMCError(
                message=f"Invalid JSON response from TSETMC for {url or 'request'}: {exc}",
                status_code=status_code,
                url=url,
            ) from exc

    def _map_transport_error(self, exc: httpx2.TransportError, path: str) -> TSETMCError:
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        return TSETMCError(
            message=f"Transport error requesting {url}: {exc}",
            status_code=None,
            url=url,
        )


class SyncTransport(_BaseTransport):
    """Synchronous HTTP/2 transport for ``cdn.tsetmc.com`` using ``httpx2.Client``."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        proxy: str | httpx2.Proxy | None = None,
        headers: Mapping[str, str] | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            proxy=proxy,
            headers=headers,
        )
        self._client = self._create_http_client(httpx2.Client, self._client_kwargs(transport))

    def get_json(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        """Perform an HTTP GET request with exponential-backoff retries and parse JSON."""
        last_error: TSETMCError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx2.TransportError as exc:
                last_error = self._map_transport_error(exc, path)
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    if delay > 0:
                        time.sleep(delay)
                    continue
                raise last_error from exc

            if self._should_retry_status(response.status_code) and attempt < self.max_retries:
                delay = self._backoff_delay(attempt, self._parse_retry_after(response))
                if delay > 0:
                    time.sleep(delay)
                continue

            return self._decode_json_response(response, fallback_url=path)

        if last_error is not None:  # pragma: no cover
            raise last_error
        raise TSETMCError(f"Request failed after retries: {path}")  # pragma: no cover

    def close(self) -> None:
        """Close the underlying ``httpx2.Client``."""
        self._client.close()

    def __enter__(self) -> SyncTransport:
        self._client.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._client.__exit__(exc_type, exc_val, exc_tb)


class AsyncTransport(_BaseTransport):
    """Asynchronous HTTP/2 transport with concurrency limiting using ``httpx2.AsyncClient``."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        max_concurrency: int = 8,
        proxy: str | httpx2.Proxy | None = None,
        headers: Mapping[str, str] | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            proxy=proxy,
            headers=headers,
        )
        self.max_concurrency = max_concurrency
        self._client = self._create_http_client(httpx2.AsyncClient, self._client_kwargs(transport))
        self._semaphore: asyncio.Semaphore | None = None
        self._semaphore_loop: asyncio.AbstractEventLoop | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._semaphore_loop is not loop:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    async def get_json(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        """Perform an async HTTP GET request with concurrency semaphore, retries, and JSON parse."""
        semaphore = self._get_semaphore()
        last_error: TSETMCError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with semaphore:
                    response = await self._client.get(path, params=params)
            except httpx2.TransportError as exc:
                last_error = self._map_transport_error(exc, path)
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                raise last_error from exc

            if self._should_retry_status(response.status_code) and attempt < self.max_retries:
                delay = self._backoff_delay(attempt, self._parse_retry_after(response))
                if delay > 0:
                    await asyncio.sleep(delay)
                continue

            return self._decode_json_response(response, fallback_url=path)

        if last_error is not None:  # pragma: no cover
            raise last_error
        raise TSETMCError(f"Request failed after retries: {path}")  # pragma: no cover

    async def aclose(self) -> None:
        """Close the underlying ``httpx2.AsyncClient``."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncTransport:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
