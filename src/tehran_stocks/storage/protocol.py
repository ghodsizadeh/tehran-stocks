"""Pluggable storage backend protocol for tehran-stocks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol, runtime_checkable

from tehran_stocks.types.client_type import ClientTypeDaily
from tehran_stocks.types.instrument import Instrument, ShareChange
from tehran_stocks.types.market import Sector
from tehran_stocks.types.price import DailyBar, PriceAdjustment


@runtime_checkable
class StorageBackend(Protocol):
    """Contract implemented by built-in and custom market-data storage backends."""

    def init_schema(self) -> None:
        """Create required tables and indexes idempotently."""
        ...

    def close(self) -> None:
        """Close underlying database connections and release resources."""
        ...

    def upsert_sectors(self, sectors: Sequence[Sector]) -> int:
        """Insert or update sector records and return affected row count."""
        ...

    def upsert_instruments(self, instruments: Sequence[Instrument]) -> int:
        """Insert or update instrument metadata records and return affected row count."""
        ...

    def upsert_prices(self, bars: Sequence[DailyBar]) -> int:
        """Insert or update daily OHLCV bars and return affected row count."""
        ...

    def upsert_client_types(self, records: Sequence[ClientTypeDaily]) -> int:
        """Insert or update daily client-type flow records and return affected row count."""
        ...

    def upsert_adjustments(self, adjustments: Sequence[PriceAdjustment]) -> int:
        """Insert or update corporate-action price adjustment records."""
        ...

    def upsert_share_changes(self, changes: Sequence[ShareChange]) -> int:
        """Insert or update historical share count change records."""
        ...

    def list_instruments(
        self,
        *,
        sector_code: str | None = None,
        query: str | None = None,
        flow: int | None = None,
        limit: int | None = None,
    ) -> list[Instrument]:
        """List stored instruments filtered by optional sector, text query, flow, or limit."""
        ...

    def resolve_ins_code(self, identifier: str | int) -> str | None:
        """Resolve a symbol, ISIN, or insCode against stored instruments."""
        ...

    def get_last_price_date(self, symbol: str | int) -> date | None:
        """Return the latest stored ``daily_prices`` date for ``symbol``, if any."""
        ...

    def get_last_client_type_date(self, symbol: str | int) -> date | None:
        """Return the latest stored ``client_types`` date for ``symbol``, if any."""
        ...

    def get_prices(
        self,
        symbol: str | int,
        *,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        adjusted: bool = False,
        limit: int | None = None,
    ) -> list[DailyBar]:
        """Return chronological daily OHLCV bars, optionally backward-adjusted."""
        ...

    def get_adjustments(self, symbol: str | int) -> list[PriceAdjustment]:
        """Return chronological price adjustment events for ``symbol``."""
        ...

    def get_client_types(
        self,
        symbol: str | int,
        *,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        limit: int | None = None,
    ) -> list[ClientTypeDaily]:
        """Return chronological daily client-type flow records for ``symbol``."""
        ...

    def query_readonly(
        self,
        sql: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read-only SQL query and return rows as dictionaries."""
        ...

    def stats(self) -> dict[str, Any]:
        """Return table counts, date coverage, and sync metadata summary."""
        ...
