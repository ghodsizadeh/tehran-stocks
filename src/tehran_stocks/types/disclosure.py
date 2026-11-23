"""Shareholder, Codal disclosure, supervisor message, ETF, and options models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from tehran_stocks.types._base import (
    SerializableMixin,
    _as_float,
    _as_int,
    _as_optional_date,
    _as_optional_float,
    _as_optional_int,
    _as_optional_time,
    _as_str,
    _pick,
    _resolve_ins_code,
)


@dataclass(frozen=True, slots=True)
class Shareholder(SerializableMixin):
    """Major shareholder (>1% stake) snapshot entry."""

    shareholder_id: int | str
    name: str
    shares: int
    percent: float
    change: int = 0
    date: date | None = None
    ins_code: str = ""

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> Shareholder:
        raw_id = data.get("shareHolderID")
        if raw_id in (None, 0, "0", ""):
            raw_id = _pick(data, "shareHolderShareID", "shareholder_id", default="")
        return cls(
            shareholder_id=raw_id,
            name=_as_str(_pick(data, "shareHolderName", "name", default=""), normalize=True),
            shares=_as_int(_pick(data, "numberOfShares", "shares", default=0)),
            percent=_as_float(_pick(data, "perOfShares", "percent", default=0.0)),
            change=_as_int(_pick(data, "changeAmount", "change", default=0)),
            date=_as_optional_date(_pick(data, "dEven", "date")),
            ins_code=_resolve_ins_code(data, ins_code),
        )


@dataclass(frozen=True, slots=True)
class CodalAnnouncement(SerializableMixin):
    """Codal corporate disclosure / financial statement filing."""

    tracing_no: int
    ins_code: str = ""
    symbol: str = ""
    title: str = ""
    publish_datetime: str = ""
    sent_datetime: str = ""
    date: date | None = None
    url: str = ""
    excel_url: str = ""
    pdf_url: str = ""
    has_excel: bool = False
    has_pdf: bool = False

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> CodalAnnouncement:
        return cls(
            tracing_no=_as_int(_pick(data, "tracingNo", "tracing_no", default=0)),
            ins_code=_resolve_ins_code(data, ins_code),
            symbol=_as_str(_pick(data, "symbol", "lVal18AFC", default=""), normalize=True),
            title=_as_str(_pick(data, "title", default=""), normalize=True),
            publish_datetime=_as_str(
                _pick(
                    data,
                    "publishDateTime",
                    "publishDateTime_Gregorian",
                    "publish_datetime",
                    default="",
                ),
                normalize=True,
            ),
            sent_datetime=_as_str(
                _pick(
                    data,
                    "sentDateTime",
                    "sentDateTime_Gregorian",
                    "sent_datetime",
                    default="",
                ),
                normalize=True,
            ),
            date=_as_optional_date(_pick(data, "dEven", "publishDateTime_DEven", "date")),
            url=_as_str(_pick(data, "url", default="")),
            excel_url=_as_str(_pick(data, "excelUrl", "excel_url", default="")),
            pdf_url=_as_str(_pick(data, "pdfUrl", "pdf_url", default="")),
            has_excel=bool(_pick(data, "hasExcel", "hasExcelReport", "has_excel", default=False)),
            has_pdf=bool(_pick(data, "hasPdf", "hasPDFReport", "has_pdf", default=False)),
        )


@dataclass(frozen=True, slots=True)
class SupervisorMessage(SerializableMixin):
    """Market supervisor notice (halt, reopening, AGM, or regulatory alert)."""

    msg_id: int
    title: str
    description: str = ""
    date: date | None = None
    time: str = ""
    ins_code: str = ""

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> SupervisorMessage:
        return cls(
            msg_id=_as_int(_pick(data, "tseMsgIdn", "msg_id", default=0)),
            title=_as_str(_pick(data, "tseTitle", "title", default=""), normalize=True),
            description=_as_str(_pick(data, "tseDesc", "description", default=""), normalize=True),
            date=_as_optional_date(_pick(data, "dEven", "date")),
            time=_as_optional_time(_pick(data, "hEven", "time")),
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
        )


@dataclass(frozen=True, slots=True)
class ETFInfo(SerializableMixin):
    """ETF Net Asset Value (NAV) and cancellation/subscription pricing."""

    ins_code: str
    date: date | None = None
    time: str = ""
    redemption_nav: float = 0.0
    subscription_nav: float = 0.0
    statistical_nav: float = 0.0
    last_price: float | None = None

    @property
    def nav_premium_pct(self) -> float | None:
        if self.redemption_nav <= 0 or self.last_price is None:
            return None
        return (self.last_price - self.redemption_nav) / self.redemption_nav * 100.0

    @classmethod
    def from_tsetmc(
        cls,
        data: Mapping[str, Any],
        ins_code: str = "",
        last_price: float | None = None,
    ) -> ETFInfo:
        payload = data.get("etf") if isinstance(data.get("etf"), Mapping) else data
        return cls(
            ins_code=_resolve_ins_code(payload, ins_code),
            date=_as_optional_date(_pick(payload, "dEven", "deven", "date")),
            time=_as_optional_time(_pick(payload, "hEven", "time")),
            redemption_nav=_as_float(
                _pick(payload, "pRedemtVal", "pRedTran", "redemption_nav", default=0.0)
            ),
            subscription_nav=_as_float(
                _pick(payload, "pSubcptVal", "pSubTran", "subscription_nav", default=0.0)
            ),
            statistical_nav=_as_float(_pick(payload, "pStatVal", "statistical_nav", default=0.0)),
            last_price=_as_optional_float(_pick(payload, "last_price", default=last_price)),
        )


@dataclass(frozen=True, slots=True)
class OptionWatchItem(SerializableMixin):
    """Live exchange-traded equity option contract entry."""

    ins_code: str
    symbol: str
    name: str = ""
    underlying_ins_code: str = ""
    contract_size: int = 0
    strike_price: float = 0.0
    expiration_date: date | None = None
    days_to_maturity: int | None = None
    open_interest: int = 0
    buy_price: float = 0.0
    sell_price: float = 0.0
    last: float = 0.0
    close: float = 0.0
    volume: int = 0
    value: int = 0
    trade_count: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> OptionWatchItem:
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default="")),
            symbol=_as_str(_pick(data, "lVal18AFC", "lva", "symbol", default=""), normalize=True),
            name=_as_str(_pick(data, "lVal30", "lvc", "name", default=""), normalize=True),
            underlying_ins_code=_as_str(
                _pick(data, "insCodeUA", "uaInsCode", "underlying_ins_code", default="")
            ),
            contract_size=_as_int(_pick(data, "cSize", "contractSize", "contract_size", default=0)),
            strike_price=_as_float(_pick(data, "strikePrice", "strike_price", default=0.0)),
            expiration_date=_as_optional_date(_pick(data, "endDate", "dEven", "expiration_date")),
            days_to_maturity=_as_optional_int(_pick(data, "remainedDay", "days_to_maturity")),
            open_interest=_as_int(_pick(data, "openPosition", "open_interest", default=0)),
            buy_price=_as_float(_pick(data, "pMeDem_Buy", "buyOP", "buy_price", default=0.0)),
            sell_price=_as_float(_pick(data, "pMeOf_Sell", "sellOP", "sell_price", default=0.0)),
            last=_as_float(_pick(data, "pDrCotVal", "last", default=0.0)),
            close=_as_float(_pick(data, "pClosing", "close", default=0.0)),
            volume=_as_int(_pick(data, "qTotTran5J", "volume", default=0)),
            value=_as_int(_pick(data, "qTotCap", "value", default=0)),
            trade_count=_as_int(_pick(data, "zTotTran", "trade_count", default=0)),
        )
