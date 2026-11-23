"""Price, quote, adjustment, order book, and intraday tick domain models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from tehran_stocks.types._base import (
    SerializableMixin,
    _as_date,
    _as_float,
    _as_int,
    _as_optional_date,
    _as_optional_float,
    _as_optional_time,
    _as_str,
    _pick,
)


@dataclass(frozen=True, slots=True)
class Quote(SerializableMixin):
    """Live or latest closing quote snapshot for an instrument."""

    ins_code: str
    date: date | None = None
    time: str = ""
    last: float = 0.0
    close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    yesterday: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    value: int = 0
    trade_count: int = 0
    state: str = ""
    state_title: str = ""
    is_closed: bool = False
    price_min_allowed: float | None = None
    price_max_allowed: float | None = None

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> Quote:
        payload = (
            data.get("closingPriceInfo")
            if isinstance(data.get("closingPriceInfo"), Mapping)
            else data
        )
        state_obj = (
            payload.get("instrumentState")
            if isinstance(payload.get("instrumentState"), Mapping)
            else {}
        )
        last = _as_float(_pick(payload, "pDrCotVal", "last", default=0.0))
        yesterday = _as_float(_pick(payload, "priceYesterday", "yesterday", default=0.0))
        change = _as_float(
            _pick(payload, "priceChange", "change"),
            default=(last - yesterday) if yesterday else 0.0,
        )
        change_pct = (change / yesterday * 100.0) if yesterday > 0 else 0.0
        return cls(
            ins_code=_as_str(_pick(payload, "insCode", "ins_code", default=ins_code)),
            date=_as_optional_date(_pick(payload, "dEven", "date")),
            time=_as_optional_time(_pick(payload, "hEven", "time")),
            last=last,
            close=_as_float(_pick(payload, "pClosing", "close", default=0.0)),
            open=_as_float(_pick(payload, "priceFirst", "open", default=0.0)),
            high=_as_float(_pick(payload, "priceMax", "high", default=0.0)),
            low=_as_float(_pick(payload, "priceMin", "low", default=0.0)),
            yesterday=yesterday,
            change=change,
            change_pct=change_pct,
            volume=_as_int(_pick(payload, "qTotTran5J", "volume", default=0)),
            value=_as_int(_pick(payload, "qTotCap", "value", default=0)),
            trade_count=_as_int(_pick(payload, "zTotTran", "trade_count", default=0)),
            state=_as_str(_pick(payload, "cEtaval", default=state_obj.get("cEtaval", ""))),
            state_title=_as_str(
                _pick(
                    payload,
                    "lEtavalTitle",
                    "cEtavalTitle",
                    default=_pick(state_obj, "lEtavalTitle", "cEtavalTitle", default=""),
                ),
                normalize=True,
            ),
            is_closed=bool(_pick(payload, "iClose", "is_closed", default=False)),
            price_min_allowed=_as_optional_float(_pick(payload, "pMin", "psGelStaMin")),
            price_max_allowed=_as_optional_float(_pick(payload, "pMax", "psGelStaMax")),
        )


@dataclass(frozen=True, slots=True)
class DailyBar(SerializableMixin):
    """Daily OHLCV bar for an instrument."""

    ins_code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    last: float
    yesterday: float = 0.0
    volume: int = 0
    value: int = 0
    trade_count: int = 0

    @property
    def change(self) -> float:
        return self.close - self.yesterday if self.yesterday else 0.0

    @property
    def change_pct(self) -> float:
        if self.yesterday <= 0:
            return 0.0
        return (self.close - self.yesterday) / self.yesterday * 100.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> DailyBar:
        close = _as_float(_pick(data, "pClosing", "close", default=0.0))
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
            date=_as_date(_pick(data, "dEven", "date")),
            open=_as_float(_pick(data, "priceFirst", "open", default=close)),
            high=_as_float(_pick(data, "priceMax", "high", default=close)),
            low=_as_float(_pick(data, "priceMin", "low", default=close)),
            close=close,
            last=_as_float(_pick(data, "pDrCotVal", "last", default=close)),
            yesterday=_as_float(_pick(data, "priceYesterday", "yesterday", default=0.0)),
            volume=_as_int(_pick(data, "qTotTran5J", "volume", default=0)),
            value=_as_int(_pick(data, "qTotCap", "value", default=0)),
            trade_count=_as_int(_pick(data, "zTotTran", "trade_count", default=0)),
        )


@dataclass(frozen=True, slots=True)
class PriceAdjustment(SerializableMixin):
    """Historical corporate-action adjustment factor record."""

    ins_code: str
    date: date
    adjusted_close: float
    unadjusted_close: float
    corporate_type_code: int | str | None = None

    @property
    def ratio(self) -> float:
        if self.unadjusted_close <= 0 or self.adjusted_close <= 0:
            return 1.0
        return self.adjusted_close / self.unadjusted_close

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> PriceAdjustment:
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
            date=_as_date(_pick(data, "dEven", "date")),
            adjusted_close=_as_float(_pick(data, "pClosing", "adjusted_close", default=0.0)),
            unadjusted_close=_as_float(
                _pick(data, "pClosingNotAdjusted", "unadjusted_close", default=0.0)
            ),
            corporate_type_code=_pick(data, "corporateTypeCode", "corporate_type_code"),
        )


@dataclass(frozen=True, slots=True)
class OrderBookLevel(SerializableMixin):
    """Single level (1..5) of bid/ask depth from TSETMC BestLimits."""

    row: int
    bid_price: float = 0.0
    bid_volume: int = 0
    bid_count: int = 0
    ask_price: float = 0.0
    ask_volume: int = 0
    ask_count: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], default_row: int = 1) -> OrderBookLevel:
        return cls(
            row=_as_int(_pick(data, "number", "n", "row", default=default_row)),
            bid_price=_as_float(_pick(data, "pMeDem", "pmd", "bid_price", default=0.0)),
            bid_volume=_as_int(_pick(data, "qTitMeDem", "qmd", "bid_volume", default=0)),
            bid_count=_as_int(_pick(data, "zOrdMeDem", "zmd", "bid_count", default=0)),
            ask_price=_as_float(_pick(data, "pMeOf", "pmo", "ask_price", default=0.0)),
            ask_volume=_as_int(_pick(data, "qTitMeOf", "qmo", "ask_volume", default=0)),
            ask_count=_as_int(_pick(data, "zOrdMeOf", "zmo", "ask_count", default=0)),
        )


@dataclass(frozen=True, slots=True)
class OrderBook(SerializableMixin):
    """5-level limit order book with buy/sell queue (صف خرید / صف فروش) detection."""

    ins_code: str
    levels: tuple[OrderBookLevel, ...] = ()
    price_max_allowed: float | None = None
    price_min_allowed: float | None = None

    @property
    def best_level(self) -> OrderBookLevel | None:
        return self.levels[0] if self.levels else None

    @property
    def total_bid_volume(self) -> int:
        return sum(level.bid_volume for level in self.levels)

    @property
    def total_ask_volume(self) -> int:
        return sum(level.ask_volume for level in self.levels)

    @property
    def spread(self) -> float | None:
        top = self.best_level
        if top is None or top.bid_price <= 0 or top.ask_price <= 0:
            return None
        return top.ask_price - top.bid_price

    @property
    def is_buy_queue(self) -> bool:
        """Return True when top bid sits at upper static threshold with no opposing asks."""
        top = self.best_level
        if top is None or self.price_max_allowed is None or self.price_max_allowed <= 0:
            return False
        return (
            top.bid_volume > 0
            and top.bid_price >= self.price_max_allowed
            and top.ask_volume == 0
        )

    @property
    def is_sell_queue(self) -> bool:
        """Return True when top ask sits at lower static threshold with no opposing bids."""
        top = self.best_level
        if top is None or self.price_min_allowed is None or self.price_min_allowed <= 0:
            return False
        return (
            top.ask_volume > 0
            and top.ask_price <= self.price_min_allowed
            and top.bid_volume == 0
        )


@dataclass(frozen=True, slots=True)
class IntradayTick(SerializableMixin):
    """Intraday closing/last price tick for a trading session."""

    ins_code: str
    date: date
    time: str
    last: float
    close: float
    volume: int = 0
    value: int = 0
    trade_count: int = 0
    change: float = 0.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> IntradayTick:
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
            date=_as_date(_pick(data, "dEven", "date")),
            time=_as_optional_time(_pick(data, "hEven", "time", default=0)),
            last=_as_float(_pick(data, "pDrCotVal", "last", default=0.0)),
            close=_as_float(_pick(data, "pClosing", "close", default=0.0)),
            volume=_as_int(_pick(data, "qTotTran5J", "volume", default=0)),
            value=_as_int(_pick(data, "qTotCap", "value", default=0)),
            trade_count=_as_int(_pick(data, "zTotTran", "trade_count", default=0)),
            change=_as_float(_pick(data, "priceChange", "change", default=0.0)),
        )
