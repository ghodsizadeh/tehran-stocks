"""Instrument metadata and corporate action domain models."""

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
    _as_optional_int,
    _as_str,
    _pick,
    _resolve_ins_code,
)


@dataclass(frozen=True, slots=True)
class Instrument(SerializableMixin):
    """Core instrument record returned by search and directory lookups."""

    ins_code: str
    symbol: str
    name: str
    isin: str = ""
    instrument_id: str = ""
    market: str = ""
    flow: int | None = None
    sector_code: str = ""
    sector_name: str = ""
    total_shares: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> Instrument:
        sector = data.get("sector") if isinstance(data.get("sector"), Mapping) else {}
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default="")),
            symbol=_as_str(_pick(data, "lVal18AFC", "lva", "symbol", default=""), normalize=True),
            name=_as_str(_pick(data, "lVal30", "lvc", "name", default=""), normalize=True),
            isin=_as_str(_pick(data, "cIsin", "insID", "isin", default="")),
            instrument_id=_as_str(_pick(data, "instrumentID", "instrument_id", default="")),
            market=_as_str(_pick(data, "flowTitle", "market", default=""), normalize=True),
            flow=_as_optional_int(_pick(data, "flow")),
            sector_code=_as_str(_pick(data, "cSecVal", "csv", default=sector.get("cSecVal", ""))),
            sector_name=_as_str(
                _pick(data, "lSecVal", "sectorName", default=sector.get("lSecVal", "")),
                normalize=True,
            ),
            total_shares=_as_int(_pick(data, "zTitad", "ztd", "total_shares", default=0)),
        )


@dataclass(frozen=True, slots=True)
class InstrumentInfo(SerializableMixin):
    """Detailed instrument fundamentals, thresholds, and 52-week/week range."""

    ins_code: str
    symbol: str = ""
    name: str = ""
    isin: str = ""
    sector_code: str = ""
    sector_name: str = ""
    market: str = ""
    flow: int | None = None
    total_shares: int = 0
    base_volume: int = 0
    eps: float | None = None
    sector_pe: float | None = None
    psr: float | None = None
    price_min_allowed: float | None = None
    price_max_allowed: float | None = None
    week_min: float | None = None
    week_max: float | None = None
    year_min: float | None = None
    year_max: float | None = None
    float_shares_pct: float | None = None
    nav: float | None = None

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> InstrumentInfo:
        payload = data.get("instrumentInfo") if isinstance(data.get("instrumentInfo"), Mapping) else data
        eps_block = payload.get("eps") if isinstance(payload.get("eps"), Mapping) else {}
        sector = payload.get("sector") if isinstance(payload.get("sector"), Mapping) else {}
        threshold = (
            payload.get("staticThreshold")
            if isinstance(payload.get("staticThreshold"), Mapping)
            else {}
        )
        return cls(
            ins_code=_as_str(_pick(payload, "insCode", "ins_code", default="")),
            symbol=_as_str(_pick(payload, "lVal18AFC", "symbol", default=""), normalize=True),
            name=_as_str(_pick(payload, "lVal30", "name", default=""), normalize=True),
            isin=_as_str(_pick(payload, "cIsin", "isin", default="")),
            sector_code=_as_str(_pick(payload, "cSecVal", default=sector.get("cSecVal", ""))),
            sector_name=_as_str(
                _pick(payload, "lSecVal", default=sector.get("lSecVal", "")),
                normalize=True,
            ),
            market=_as_str(_pick(payload, "flowTitle", "market", default=""), normalize=True),
            flow=_as_optional_int(_pick(payload, "flow")),
            total_shares=_as_int(_pick(payload, "zTitad", "total_shares", default=0)),
            base_volume=_as_int(_pick(payload, "baseVol", "base_volume", default=0)),
            eps=_as_optional_float(_pick(eps_block, "estimatedEPS", default=payload.get("estimatedEPS"))),
            sector_pe=_as_optional_float(_pick(eps_block, "sectorPE", default=payload.get("sectorPE"))),
            psr=_as_optional_float(_pick(eps_block, "psr", default=payload.get("psr"))),
            price_min_allowed=_as_optional_float(
                _pick(threshold, "psGelStaMin", default=payload.get("psGelStaMin"))
            ),
            price_max_allowed=_as_optional_float(
                _pick(threshold, "psGelStaMax", default=payload.get("psGelStaMax"))
            ),
            week_min=_as_optional_float(_pick(payload, "minWeek")),
            week_max=_as_optional_float(_pick(payload, "maxWeek")),
            year_min=_as_optional_float(_pick(payload, "minYear")),
            year_max=_as_optional_float(_pick(payload, "maxYear")),
            float_shares_pct=_as_optional_float(_pick(payload, "kAjCapValCpsIdx", "float_shares_pct")),
            nav=_as_optional_float(_pick(payload, "nav")),
        )


@dataclass(frozen=True, slots=True)
class InstrumentIdentity(SerializableMixin):
    """Legal and market-classification identity of an instrument."""

    ins_code: str
    symbol: str = ""
    name: str = ""
    latin_symbol: str = ""
    latin_name: str = ""
    isin: str = ""
    company_code: str = ""
    sector_code: str = ""
    sector_name: str = ""
    sub_sector_code: str = ""
    sub_sector_name: str = ""
    market_code: str = ""
    flow: int | None = None
    flow_title: str = ""
    board_code: str = ""

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any]) -> InstrumentIdentity:
        payload = (
            data.get("instrumentIdentity")
            if isinstance(data.get("instrumentIdentity"), Mapping)
            else data
        )
        sector = payload.get("sector") if isinstance(payload.get("sector"), Mapping) else {}
        sub_sector = (
            payload.get("subSector") if isinstance(payload.get("subSector"), Mapping) else {}
        )
        return cls(
            ins_code=_as_str(_pick(payload, "insCode", "ins_code", default="")),
            symbol=_as_str(_pick(payload, "lVal18AFC", "symbol", default=""), normalize=True),
            name=_as_str(_pick(payload, "lVal30", "name", default=""), normalize=True),
            latin_symbol=_as_str(_pick(payload, "lVal18", "latin_symbol", default="")),
            latin_name=_as_str(_pick(payload, "lSoc30", "latin_name", default="")),
            isin=_as_str(_pick(payload, "cIsin", "isin", default="")),
            company_code=_as_str(_pick(payload, "cComVal", "cSocCSAC", "company_code", default="")),
            sector_code=_as_str(_pick(payload, "cSecVal", default=sector.get("cSecVal", ""))),
            sector_name=_as_str(
                _pick(payload, "lSecVal", default=sector.get("lSecVal", "")),
                normalize=True,
            ),
            sub_sector_code=_as_str(
                _pick(payload, "cSoSecVal", default=sub_sector.get("cSoSecVal", ""))
            ),
            sub_sector_name=_as_str(
                _pick(payload, "lSoSecVal", default=sub_sector.get("lSoSecVal", "")),
                normalize=True,
            ),
            market_code=_as_str(_pick(payload, "yMarNSC", "market_code", default="")),
            flow=_as_optional_int(_pick(payload, "flow")),
            flow_title=_as_str(_pick(payload, "flowTitle", "flow_title", default=""), normalize=True),
            board_code=_as_str(_pick(payload, "cgrValCot", "yVal", "board_code", default="")),
        )


@dataclass(frozen=True, slots=True)
class InstrumentStatistic(SerializableMixin):
    """Single computed TSETMC statistic entry (liquidity, rank, rolling metric)."""

    ins_code: str
    data_type: int
    value: float
    name: str = ""
    date: date | None = None

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> InstrumentStatistic:
        return cls(
            ins_code=_resolve_ins_code(data, ins_code),
            data_type=_as_int(_pick(data, "dataType", "data_type", default=0)),
            value=_as_float(_pick(data, "dataValue", "value", default=0.0)),
            name=_as_str(_pick(data, "dataTypeTitle", "dataTypeDesc", "name", default=""), normalize=True),
            date=_as_optional_date(_pick(data, "dEven", "date")),
        )


@dataclass(frozen=True, slots=True)
class ShareChange(SerializableMixin):
    """Historical share count change (capital increase / split)."""

    ins_code: str
    date: date
    new_shares: int
    old_shares: int

    @property
    def change(self) -> int:
        return self.new_shares - self.old_shares

    @property
    def ratio(self) -> float:
        if self.old_shares <= 0:
            return 1.0
        return self.new_shares / self.old_shares

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> ShareChange:
        return cls(
            ins_code=_as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
            date=_as_date(_pick(data, "dEven", "date")),
            new_shares=_as_int(_pick(data, "numberOfShareNew", "new_shares", default=0)),
            old_shares=_as_int(_pick(data, "numberOfShareOld", "old_shares", default=0)),
        )
