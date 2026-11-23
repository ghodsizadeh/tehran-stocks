"""Market-wide watch, overview, sector, and index domain models."""

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
from tehran_stocks.types.price import OrderBookLevel


@dataclass(frozen=True, slots=True)
class MarketWatchItem(SerializableMixin):
    """Single instrument entry from TSETMC GetMarketWatch."""

    ins_code: str
    symbol: str
    name: str
    isin: str = ""
    sector_code: str = ""
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
    eps: float | None = None
    pe: float | None = None
    total_shares: int = 0
    base_volume: int = 0
    price_max_allowed: float | None = None
    price_min_allowed: float | None = None
    y_val: str = ""
    order_book: tuple[OrderBookLevel, ...] = ()

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> MarketWatchItem:
        last = _as_float(_pick(data, "pdv", "pDrCotVal", "last", default=0.0))
        yesterday = _as_float(_pick(data, "py", "priceYesterday", "yesterday", default=0.0))
        change = _as_float(
            _pick(data, "pCh", "priceChange", "change"),
            default=(last - yesterday) if yesterday else 0.0,
        )
        change_pct = (change / yesterday * 100.0) if yesterday > 0 else 0.0
        raw_book = _pick(data, "blDs", "order_book", default=()) or ()
        levels = tuple(
            lvl if isinstance(lvl, OrderBookLevel) else OrderBookLevel.from_tsetmc(lvl, default_row=i + 1)
            for i, lvl in enumerate(raw_book)
        )
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default="")),
            symbol=_as_str(_pick(data, "lva", "lVal18AFC", "symbol", default=""), normalize=True),
            name=_as_str(_pick(data, "lvc", "lVal30", "name", default=""), normalize=True),
            isin=_as_str(_pick(data, "insID", "cIsin", "isin", default="")),
            sector_code=_as_str(_pick(data, "csv", "cSecVal", "sector_code", default="")),
            last=last,
            close=_as_float(_pick(data, "pcl", "pClosing", "close", default=0.0)),
            open=_as_float(_pick(data, "pf", "priceFirst", "open", default=0.0)),
            high=_as_float(_pick(data, "pmx", "priceMax", "high", default=0.0)),
            low=_as_float(_pick(data, "pmn", "priceMin", "low", default=0.0)),
            yesterday=yesterday,
            change=change,
            change_pct=change_pct,
            volume=_as_int(_pick(data, "qtj", "qTotTran5J", "volume", default=0)),
            value=_as_int(_pick(data, "qtc", "qTotCap", "value", default=0)),
            trade_count=_as_int(_pick(data, "ztt", "zTotTran", "trade_count", default=0)),
            eps=_as_optional_float(_pick(data, "eps")),
            pe=_as_optional_float(_pick(data, "pe")),
            total_shares=_as_int(_pick(data, "ztd", "zTitad", "total_shares", default=0)),
            base_volume=_as_int(_pick(data, "bv", "baseVol", "base_volume", default=0)),
            price_max_allowed=_as_optional_float(_pick(data, "pMax", "price_max_allowed")),
            price_min_allowed=_as_optional_float(_pick(data, "pMin", "price_min_allowed")),
            y_val=_as_str(_pick(data, "yVal", "y_val", default="")),
            order_book=levels,
        )


@dataclass(frozen=True, slots=True)
class MarketOverview(SerializableMixin):
    """Market-wide summary for TSE (flow=1) or Farabourse (flow=2)."""

    flow: int
    date: date | None = None
    time: str = ""
    market_state: str = ""
    index_value: float = 0.0
    index_change: float = 0.0
    equal_weighted_index: float = 0.0
    equal_weighted_change: float = 0.0
    market_value: float = 0.0
    trade_value: int = 0
    trade_volume: int = 0
    trade_count: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], flow: int = 1) -> MarketOverview:
        payload = (
            data.get("marketOverview")
            if isinstance(data.get("marketOverview"), Mapping)
            else data
        )
        return cls(
            flow=_as_int(_pick(payload, "flow", default=flow)),
            date=_as_optional_date(_pick(payload, "marketActivityDEven", "dEven", "date")),
            time=_as_optional_time(_pick(payload, "marketActivityHEven", "hEven", "time")),
            market_state=_as_str(
                _pick(payload, "marketStateTitle", "marketState", "market_state", default=""),
                normalize=True,
            ),
            index_value=_as_float(_pick(payload, "indexLastValue", "index_value", default=0.0)),
            index_change=_as_float(_pick(payload, "indexChange", "index_change", default=0.0)),
            equal_weighted_index=_as_float(
                _pick(payload, "indexEqualWeightedLastValue", "equal_weighted_index", default=0.0)
            ),
            equal_weighted_change=_as_float(
                _pick(payload, "indexEqualWeightedChange", "equal_weighted_change", default=0.0)
            ),
            market_value=_as_float(_pick(payload, "marketValue", "market_value", default=0.0)),
            trade_value=_as_int(_pick(payload, "marketActivityQTotCap", "trade_value", default=0)),
            trade_volume=_as_int(_pick(payload, "marketActivityQTotTran", "trade_volume", default=0)),
            trade_count=_as_int(_pick(payload, "marketActivityZTotTran", "trade_count", default=0)),
        )


@dataclass(frozen=True, slots=True)
class Sector(SerializableMixin):
    """Industrial sector / paper type definition and optional live summary."""

    code: str
    name: str
    type: str = ""
    index_ins_code: str = ""
    trade_value: int = 0
    trade_volume: int = 0
    trade_count: int = 0
    market_cap: float = 0.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> Sector:
        return cls(
            code=_as_str(_pick(data, "cSecVal", "code", "sectorCode", default="")),
            name=_as_str(_pick(data, "lSecVal", "name", "title", "sectorName", default=""), normalize=True),
            type=_as_str(_pick(data, "type", "staticType", default="")),
            index_ins_code=_as_str(_pick(data, "insCode", "index_ins_code", default="")),
            trade_value=_as_int(_pick(data, "qTotCap", "trade_value", default=0)),
            trade_volume=_as_int(_pick(data, "qTotTran5J", "trade_volume", default=0)),
            trade_count=_as_int(_pick(data, "zTotTran", "trade_count", default=0)),
            market_cap=_as_float(_pick(data, "marketCap", "market_cap", default=0.0)),
        )


@dataclass(frozen=True, slots=True)
class IndexQuote(SerializableMixin):
    """Live market or industry index quote."""

    ins_code: str
    name: str
    date: date | None = None
    time: str = ""
    value: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    market_cap: float = 0.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> IndexQuote:
        value = _as_float(_pick(data, "xDrNivJIdx004", "value", default=0.0))
        change = _as_float(_pick(data, "indexChange", "change", default=0.0))
        prev = value - change
        computed_pct = (change / prev * 100.0) if prev > 0 else 0.0
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default="")),
            name=_as_str(_pick(data, "lVal30", "name", default=""), normalize=True),
            date=_as_optional_date(_pick(data, "dEven", "date")),
            time=_as_optional_time(_pick(data, "hEven", "time")),
            value=value,
            high=_as_float(_pick(data, "xPhNivJIdx004", "high", default=0.0)),
            low=_as_float(_pick(data, "xPbNivJIdx004", "low", default=0.0)),
            change=change,
            change_pct=_as_float(
                _pick(data, "xVarIdxJRWO", "xVarIdxJRfV", "change_pct"),
                default=computed_pct,
            ),
            market_cap=_as_float(_pick(data, "cEtaval", "cap", "market_cap", default=0.0)),
        )


@dataclass(frozen=True, slots=True)
class IndexBar(SerializableMixin):
    """Daily historical index bar (e.g. TEDPIX)."""

    ins_code: str
    date: date
    value: float
    high: float = 0.0
    low: float = 0.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> IndexBar:
        value = _as_float(_pick(data, "xNivInuClMresIbs", "value", default=0.0))
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
            date=_as_date(_pick(data, "dEven", "date")),
            value=value,
            high=_as_float(_pick(data, "xNivInuPhMresIbs", "high", default=value)),
            low=_as_float(_pick(data, "xNivInuPbMresIbs", "low", default=value)),
        )


@dataclass(frozen=True, slots=True)
class IndexEffectItem(SerializableMixin):
    """Instrument impact on a market or sector index."""

    ins_code: str
    symbol: str
    name: str = ""
    close: float = 0.0
    change: float = 0.0
    effect: float = 0.0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> IndexEffectItem:
        inst = data.get("instrument") if isinstance(data.get("instrument"), Mapping) else {}
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=inst.get("insCode", ""))),
            symbol=_as_str(
                _pick(data, "lVal18AFC", "symbol", default=inst.get("lVal18AFC", "")),
                normalize=True,
            ),
            name=_as_str(
                _pick(data, "lVal30", "name", default=inst.get("lVal30", "")),
                normalize=True,
            ),
            close=_as_float(_pick(data, "pClosing", "close", default=0.0)),
            change=_as_float(_pick(data, "priceChange", "change", default=0.0)),
            effect=_as_float(_pick(data, "instEffectValue", "effect", default=0.0)),
        )
