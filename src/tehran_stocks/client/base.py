"""Synchronous and asynchronous TSETMC client facades."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx2

from tehran_stocks.client.resolver import AsyncResolver, SyncResolver
from tehran_stocks.client.resources import (
    AsyncClientType,
    AsyncDisclosures,
    AsyncFunds,
    AsyncInstruments,
    AsyncMarket,
    AsyncPrices,
    SyncClientType,
    SyncDisclosures,
    SyncFunds,
    SyncInstruments,
    SyncMarket,
    SyncPrices,
)
from tehran_stocks.client.transport import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    AsyncTransport,
    SyncTransport,
)


class TSETMCClient:
    """Synchronous client facade for ``cdn.tsetmc.com`` APIs."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        proxy: str | httpx2.Proxy | None = None,
        headers: Mapping[str, str] | None = None,
        cache_ttl: float = 3600.0,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self.transport = SyncTransport(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            proxy=proxy,
            headers=headers,
            transport=transport,
        )
        self.resolver = SyncResolver(self.transport, cache_ttl=cache_ttl)
        self.instruments = SyncInstruments(self.transport, self.resolver)
        self.prices = SyncPrices(self.transport, self.resolver)
        self.client_type = SyncClientType(self.transport, self.resolver)
        self.market = SyncMarket(self.transport, self.resolver)
        self.disclosures = SyncDisclosures(self.transport, self.resolver)
        self.funds = SyncFunds(self.transport, self.resolver)

    def resolve(self, symbol: str | int) -> str:
        """Resolve a symbol, ISIN, or numeric insCode to an ``insCode`` string."""
        return self.resolver.resolve(symbol)

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self.transport.close()

    def __enter__(self) -> TSETMCClient:
        self.transport.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.transport.__exit__(exc_type, exc_val, exc_tb)


class AsyncTSETMCClient:
    """Asynchronous client facade for ``cdn.tsetmc.com`` APIs."""

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
        cache_ttl: float = 3600.0,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self.transport = AsyncTransport(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            max_concurrency=max_concurrency,
            proxy=proxy,
            headers=headers,
            transport=transport,
        )
        self.resolver = AsyncResolver(self.transport, cache_ttl=cache_ttl)
        self.instruments = AsyncInstruments(self.transport, self.resolver)
        self.prices = AsyncPrices(self.transport, self.resolver)
        self.client_type = AsyncClientType(self.transport, self.resolver)
        self.market = AsyncMarket(self.transport, self.resolver)
        self.disclosures = AsyncDisclosures(self.transport, self.resolver)
        self.funds = AsyncFunds(self.transport, self.resolver)

    async def resolve(self, symbol: str | int) -> str:
        """Resolve a symbol, ISIN, or numeric insCode to an ``insCode`` string."""
        return await self.resolver.resolve(symbol)

    async def aclose(self) -> None:
        """Close the underlying async HTTP transport."""
        await self.transport.aclose()

    async def __aenter__(self) -> AsyncTSETMCClient:
        await self.transport.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.transport.__aexit__(exc_type, exc_val, exc_tb)


Client = TSETMCClient
AsyncClient = AsyncTSETMCClient
