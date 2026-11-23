"""Quotes, daily OHLCV history, price adjustments, order book, and intraday ticks."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.client.resources.instruments import _parse_info
from tehran_stocks.exceptions import InstrumentNotFoundError
from tehran_stocks.types.price import (
    DailyBar,
    IntradayTick,
    OrderBook,
    OrderBookLevel,
    PriceAdjustment,
    Quote,
)
from tehran_stocks.utils.analytics import adjust_prices
from tehran_stocks.utils.jalali import int_to_date, jalali_to_gregorian
from tehran_stocks.utils.persian import normalize_persian


def _coerce_date(value: date | datetime | int | str | None) -> date | None:
    """Parse Gregorian or Jalali date values (date, YYYYMMDD int/str, YYYY-MM-DD)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = normalize_persian(str(value)).strip()
    if not raw:
        return None

    year_prefix = raw.replace("/", "-")[:4]
    if year_prefix.isdigit() and int(year_prefix) < 1700:
        return jalali_to_gregorian(raw)
    return int_to_date(raw)


def _parse_quote(data: Any, ins_code: str) -> Quote:
    payload = data.get("closingPriceInfo") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping) or not payload:
        raise InstrumentNotFoundError(ins_code)

    normalized = dict(payload)
    if normalized.get("insCode") in (None, "", "0", 0):
        normalized["insCode"] = ins_code

    state = normalized.get("instrumentState")
    if isinstance(state, Mapping):
        state_copy = dict(state)
        if not state_copy.get("lEtavalTitle") and state_copy.get("cEtavalTitle"):
            state_copy["lEtavalTitle"] = state_copy["cEtavalTitle"]
        normalized["instrumentState"] = state_copy
    elif not normalized.get("lEtavalTitle") and normalized.get("cEtavalTitle"):
        normalized["lEtavalTitle"] = normalized["cEtavalTitle"]

    return Quote.from_tsetmc(normalized, ins_code=ins_code)


def _parse_history(
    data: Any,
    ins_code: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyBar]:
    rows = data.get("closingPriceDaily") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []

    bars: list[DailyBar] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("dEven") in (None, "", 0, "0") and not row.get("date"):
            continue
        bar = DailyBar.from_tsetmc(row, ins_code=ins_code)
        if start_date is not None and bar.date < start_date:
            continue
        if end_date is not None and bar.date > end_date:
            continue
        bars.append(bar)

    bars.sort(key=lambda b: b.date)
    return bars


def _parse_adjustments(data: Any, ins_code: str) -> list[PriceAdjustment]:
    rows = data.get("priceAdjust") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    adjustments: list[PriceAdjustment] = []
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("dEven"):
            continue
        adjustments.append(PriceAdjustment.from_tsetmc(row, ins_code=ins_code))
    adjustments.sort(key=lambda adj: adj.date)
    return adjustments


def _parse_order_book(
    data: Any,
    ins_code: str,
    *,
    price_max_allowed: float | None = None,
    price_min_allowed: float | None = None,
) -> OrderBook:
    rows = data.get("bestLimits") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        rows = []

    levels: list[OrderBookLevel] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            continue
        level = OrderBookLevel.from_tsetmc(row, default_row=index)
        if (
            level.row <= 0
            and level.bid_price == 0.0
            and level.ask_price == 0.0
            and level.bid_volume == 0
            and level.ask_volume == 0
        ):
            continue
        levels.append(level)

    levels.sort(key=lambda lvl: lvl.row)
    return OrderBook(
        ins_code=ins_code,
        levels=tuple(levels),
        price_max_allowed=price_max_allowed,
        price_min_allowed=price_min_allowed,
    )


def _parse_intraday(data: Any, ins_code: str, session_date: date) -> list[IntradayTick]:
    rows = data.get("closingPriceHistory") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []

    default_deven = int(session_date.strftime("%Y%m%d"))
    ticks: list[IntradayTick] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if normalized.get("insCode") in (None, "", "0", 0):
            normalized["insCode"] = ins_code
        if normalized.get("dEven") in (None, "", 0, "0"):
            normalized["dEven"] = default_deven
        ticks.append(IntradayTick.from_tsetmc(normalized, ins_code=ins_code))

    ticks.sort(key=lambda tick: (tick.date, tick.time))
    return ticks


class SyncPrices(_SyncResource):
    """Synchronous resource for quotes, OHLCV history, adjustments, order books, and intraday."""

    def quote(self, symbol: str | int) -> Quote:
        """Fetch the live or latest closing quote snapshot for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/ClosingPrice/GetClosingPriceInfo/{ins_code}")
        return _parse_quote(data, ins_code)

    def history(
        self,
        symbol: str | int,
        days: int = 0,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        adjusted: bool = False,
    ) -> list[DailyBar]:
        """Fetch chronological daily OHLCV bars, optionally filtered and backward-adjusted."""
        if days < 0:
            raise ValueError("days must be >= 0")
        start_date = _coerce_date(start)
        end_date = _coerce_date(end)

        ins_code = self._resolve(symbol)
        raw_history = self._transport.get_json(
            f"/api/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{days}"
        )
        bars = _parse_history(raw_history, ins_code, start_date=start_date, end_date=end_date)
        if not adjusted or not bars:
            return bars

        raw_adjustments = self._transport.get_json(
            f"/api/ClosingPrice/GetPriceAdjustList/{ins_code}"
        )
        return adjust_prices(bars, _parse_adjustments(raw_adjustments, ins_code))

    def adjustments(self, symbol: str | int) -> list[PriceAdjustment]:
        """Fetch historical corporate-action price adjustment factors for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/ClosingPrice/GetPriceAdjustList/{ins_code}")
        return _parse_adjustments(data, ins_code)

    def order_book(
        self,
        symbol: str | int,
        *,
        include_thresholds: bool = False,
    ) -> OrderBook:
        """Fetch the 5-level bid/ask limit order book for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/BestLimits/{ins_code}")
        price_max: float | None = None
        price_min: float | None = None
        if include_thresholds:
            info_data = self._transport.get_json(f"/api/Instrument/GetInstrumentInfo/{ins_code}")
            info = _parse_info(info_data, ins_code)
            price_max = info.price_max_allowed
            price_min = info.price_min_allowed
        return _parse_order_book(
            data,
            ins_code,
            price_max_allowed=price_max,
            price_min_allowed=price_min,
        )

    def intraday(
        self,
        symbol: str | int,
        date: date | int | str | None = None,
    ) -> list[IntradayTick]:
        """Fetch intraday price/volume ticks for ``symbol`` on ``date`` (default today)."""
        session_date = _coerce_date(date) or datetime.now().date()
        ins_code = self._resolve(symbol)
        d_even = session_date.strftime("%Y%m%d")
        data = self._transport.get_json(
            f"/api/ClosingPrice/GetClosingPriceHistory/{ins_code}/{d_even}"
        )
        return _parse_intraday(data, ins_code, session_date)


class AsyncPrices(_AsyncResource):
    """Asynchronous resource for quotes, OHLCV history, adjustments, order books, and intraday."""

    async def quote(self, symbol: str | int) -> Quote:
        """Fetch the live or latest closing quote snapshot for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/ClosingPrice/GetClosingPriceInfo/{ins_code}")
        return _parse_quote(data, ins_code)

    async def history(
        self,
        symbol: str | int,
        days: int = 0,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        adjusted: bool = False,
    ) -> list[DailyBar]:
        """Fetch chronological daily OHLCV bars, optionally filtered and backward-adjusted."""
        if days < 0:
            raise ValueError("days must be >= 0")
        start_date = _coerce_date(start)
        end_date = _coerce_date(end)

        ins_code = await self._resolve(symbol)
        history_coro = self._transport.get_json(
            f"/api/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{days}"
        )
        if adjusted:
            raw_history, raw_adjustments = await asyncio.gather(
                history_coro,
                self._transport.get_json(f"/api/ClosingPrice/GetPriceAdjustList/{ins_code}"),
            )
            bars = _parse_history(raw_history, ins_code, start_date=start_date, end_date=end_date)
            if not bars:
                return bars
            return adjust_prices(bars, _parse_adjustments(raw_adjustments, ins_code))

        raw_history = await history_coro
        return _parse_history(raw_history, ins_code, start_date=start_date, end_date=end_date)

    async def adjustments(self, symbol: str | int) -> list[PriceAdjustment]:
        """Fetch historical corporate-action price adjustment factors for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/ClosingPrice/GetPriceAdjustList/{ins_code}")
        return _parse_adjustments(data, ins_code)

    async def order_book(
        self,
        symbol: str | int,
        *,
        include_thresholds: bool = False,
    ) -> OrderBook:
        """Fetch the 5-level bid/ask limit order book for ``symbol``."""
        ins_code = await self._resolve(symbol)
        if include_thresholds:
            data, info_data = await asyncio.gather(
                self._transport.get_json(f"/api/BestLimits/{ins_code}"),
                self._transport.get_json(f"/api/Instrument/GetInstrumentInfo/{ins_code}"),
            )
            info = _parse_info(info_data, ins_code)
            return _parse_order_book(
                data,
                ins_code,
                price_max_allowed=info.price_max_allowed,
                price_min_allowed=info.price_min_allowed,
            )

        data = await self._transport.get_json(f"/api/BestLimits/{ins_code}")
        return _parse_order_book(data, ins_code)

    async def intraday(
        self,
        symbol: str | int,
        date: date | int | str | None = None,
    ) -> list[IntradayTick]:
        """Fetch intraday price/volume ticks for ``symbol`` on ``date`` (default today)."""
        session_date = _coerce_date(date) or datetime.now().date()
        ins_code = await self._resolve(symbol)
        d_even = session_date.strftime("%Y%m%d")
        data = await self._transport.get_json(
            f"/api/ClosingPrice/GetClosingPriceHistory/{ins_code}/{d_even}"
        )
        return _parse_intraday(data, ins_code, session_date)
