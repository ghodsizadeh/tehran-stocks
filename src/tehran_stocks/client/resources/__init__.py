"""Modular sync and async TSETMC resource namespaces."""

from __future__ import annotations

from tehran_stocks.client.resources.client_type import AsyncClientType, SyncClientType
from tehran_stocks.client.resources.disclosures import AsyncDisclosures, SyncDisclosures
from tehran_stocks.client.resources.funds import AsyncFunds, SyncFunds
from tehran_stocks.client.resources.instruments import AsyncInstruments, SyncInstruments
from tehran_stocks.client.resources.market import AsyncMarket, SyncMarket
from tehran_stocks.client.resources.prices import AsyncPrices, SyncPrices

__all__ = [
    "AsyncClientType",
    "AsyncDisclosures",
    "AsyncFunds",
    "AsyncInstruments",
    "AsyncMarket",
    "AsyncPrices",
    "SyncClientType",
    "SyncDisclosures",
    "SyncFunds",
    "SyncInstruments",
    "SyncMarket",
    "SyncPrices",
]
