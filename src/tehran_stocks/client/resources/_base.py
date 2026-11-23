"""Shared resource base classes for sync and async API namespaces."""

from __future__ import annotations

from tehran_stocks.client.resolver import AsyncResolver, SyncResolver
from tehran_stocks.client.transport import AsyncTransport, SyncTransport


class _SyncResource:
    """Base class for synchronous API resource namespaces."""

    def __init__(self, transport: SyncTransport, resolver: SyncResolver) -> None:
        self._transport = transport
        self._resolver = resolver

    def _resolve(self, symbol: str | int) -> str:
        return self._resolver.resolve(symbol)


class _AsyncResource:
    """Base class for asynchronous API resource namespaces."""

    def __init__(self, transport: AsyncTransport, resolver: AsyncResolver) -> None:
        self._transport = transport
        self._resolver = resolver

    async def _resolve(self, symbol: str | int) -> str:
        return await self._resolver.resolve(symbol)
