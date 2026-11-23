"""Zero-side-effect top-level on-demand functions for the Tehran Stock Exchange."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TypeVar

from tehran_stocks.client.base import TSETMCClient
from tehran_stocks.types.client_type import ClientTypeDaily, ClientTypeLive
from tehran_stocks.types.disclosure import CodalAnnouncement, ETFInfo, Shareholder
from tehran_stocks.types.instrument import Instrument
from tehran_stocks.types.market import IndexQuote, MarketOverview, Sector
from tehran_stocks.types.price import DailyBar, OrderBook, Quote

_T = TypeVar("_T")


def _with_client(client: TSETMCClient | None, fn: Callable[[TSETMCClient], _T]) -> _T:
    if client is not None:
        return fn(client)
    with TSETMCClient() as managed:
        return fn(managed)


def search(query: str, *, client: TSETMCClient | None = None) -> list[Instrument]:
    """Search instruments on TSETMC by symbol, name, or ISIN."""
    return _with_client(client, lambda c: c.instruments.search(query))


def quote(symbol: str | int, *, client: TSETMCClient | None = None) -> Quote:
    """Fetch the live or latest closing quote for ``symbol``."""
    return _with_client(client, lambda c: c.prices.quote(symbol))


def history(
    symbol: str | int,
    days: int = 0,
    start: date | int | str | None = None,
    end: date | int | str | None = None,
    adjusted: bool = False,
    *,
    client: TSETMCClient | None = None,
) -> list[DailyBar]:
    """Fetch chronological daily OHLCV bars for ``symbol``."""
    return _with_client(
        client,
        lambda c: c.prices.history(symbol, days=days, start=start, end=end, adjusted=adjusted),
    )


def client_type(symbol: str | int, *, client: TSETMCClient | None = None) -> ClientTypeLive:
    """Fetch live individual (حقیقی) vs. institutional (حقوقی) flow for ``symbol``."""
    return _with_client(client, lambda c: c.client_type.live(symbol))


def client_type_history(
    symbol: str | int,
    days: int | None = None,
    *,
    client: TSETMCClient | None = None,
) -> list[ClientTypeDaily]:
    """Fetch daily individual vs. institutional flow history for ``symbol``."""
    return _with_client(client, lambda c: c.client_type.history(symbol, days=days))


def order_book(
    symbol: str | int,
    *,
    include_thresholds: bool = False,
    client: TSETMCClient | None = None,
) -> OrderBook:
    """Fetch the 5-level limit order book for ``symbol``."""
    return _with_client(
        client,
        lambda c: c.prices.order_book(symbol, include_thresholds=include_thresholds),
    )


def market_overview(
    flow: int = 1,
    *,
    client: TSETMCClient | None = None,
) -> MarketOverview:
    """Fetch market overview summary for ``flow`` (1=TSE, 2=Farabourse)."""
    return _with_client(client, lambda c: c.market.overview(flow=flow))


def sectors(*, client: TSETMCClient | None = None) -> list[Sector]:
    """Fetch TSE industrial sectors with definitions and summary counts."""
    return _with_client(client, lambda c: c.market.sectors())


def indices(flow: int = 1, *, client: TSETMCClient | None = None) -> list[IndexQuote]:
    """Fetch all live market and industry indices for ``flow``."""
    return _with_client(client, lambda c: c.market.indices(flow=flow))


def shareholders(
    symbol: str | int,
    *,
    client: TSETMCClient | None = None,
) -> list[Shareholder]:
    """Fetch major shareholders (>1% stake) for ``symbol``."""
    return _with_client(client, lambda c: c.disclosures.shareholders(symbol))


def codal(
    symbol: str | int,
    limit: int = 10,
    *,
    client: TSETMCClient | None = None,
) -> list[CodalAnnouncement]:
    """Fetch recent Codal corporate disclosures for ``symbol``."""
    return _with_client(client, lambda c: c.disclosures.codal(symbol, limit=limit))


def etf(symbol: str | int, *, client: TSETMCClient | None = None) -> ETFInfo:
    """Fetch ETF redemption/subscription NAV details for ``symbol``."""
    return _with_client(client, lambda c: c.funds.etf(symbol))


__all__ = [
    "client_type",
    "client_type_history",
    "codal",
    "etf",
    "history",
    "indices",
    "market_overview",
    "order_book",
    "quote",
    "search",
    "sectors",
    "shareholders",
]
