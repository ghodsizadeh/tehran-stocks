"""Instrument search, fundamentals, identity, statistics, and share changes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.exceptions import InstrumentNotFoundError
from tehran_stocks.types.instrument import (
    Instrument,
    InstrumentIdentity,
    InstrumentInfo,
    InstrumentStatistic,
    ShareChange,
)
from tehran_stocks.utils.persian import normalize_persian


def _parse_search(data: Any) -> list[Instrument]:
    rows = data.get("instrumentSearch") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    return [Instrument.from_tsetmc(row) for row in rows if isinstance(row, Mapping)]


def _parse_info(data: Any, ins_code: str) -> InstrumentInfo:
    payload = data.get("instrumentInfo") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping) or not payload:
        raise InstrumentNotFoundError(ins_code)
    normalized = dict(payload)
    if normalized.get("insCode") in (None, "", "0", 0):
        normalized["insCode"] = ins_code
    return InstrumentInfo.from_tsetmc(normalized)


def _parse_identity(data: Any, ins_code: str) -> InstrumentIdentity:
    payload = data.get("instrumentIdentity") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping) or not payload:
        raise InstrumentNotFoundError(ins_code)
    normalized = dict(payload)
    if normalized.get("insCode") in (None, "", "0", 0):
        normalized["insCode"] = ins_code
    return InstrumentIdentity.from_tsetmc(normalized)


def _parse_statistics(data: Any, ins_code: str) -> list[InstrumentStatistic]:
    rows = data.get("instrumentStatistic") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results: list[InstrumentStatistic] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if normalized.get("insCode") in (None, "", "0", 0):
            normalized["insCode"] = ins_code
        if not normalized.get("dataTypeTitle") and normalized.get("dataTypeDesc"):
            normalized["dataTypeTitle"] = normalized["dataTypeDesc"]
        results.append(InstrumentStatistic.from_tsetmc(normalized, ins_code=ins_code))
    return results


def _parse_share_changes(data: Any, ins_code: str) -> list[ShareChange]:
    rows = data.get("instrumentShareChange") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results: list[ShareChange] = []
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("dEven"):
            continue
        results.append(ShareChange.from_tsetmc(row, ins_code=ins_code))
    return results


def _parse_related(data: Any) -> list[Instrument]:
    rows = data.get("relatedCompany") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results: list[Instrument] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        nested = row.get("instrument")
        if isinstance(nested, Mapping):
            merged = {**row, **nested}
        else:
            merged = dict(row)
        results.append(Instrument.from_tsetmc(merged))
    return results


def _search_path(query: str) -> str:
    return f"/api/Instrument/GetInstrumentSearch/{quote(query, safe='')}"


class SyncInstruments(_SyncResource):
    """Synchronous resource for instrument search, identity, stats, and corporate actions."""

    def search(self, query: str) -> list[Instrument]:
        """Search instruments by Persian/Arabic symbol, name, or ISIN."""
        cleaned = normalize_persian(query).strip()
        if not cleaned:
            return []
        data = self._transport.get_json(_search_path(cleaned))
        return _parse_search(data)

    def info(self, symbol: str | int) -> InstrumentInfo:
        """Fetch detailed fundamentals, thresholds, and 52-week ranges for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Instrument/GetInstrumentInfo/{ins_code}")
        return _parse_info(data, ins_code)

    def identity(self, symbol: str | int) -> InstrumentIdentity:
        """Fetch legal and sector/sub-sector classification identity for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Instrument/GetInstrumentIdentity/{ins_code}")
        return _parse_identity(data, ins_code)

    def statistics(self, symbol: str | int) -> list[InstrumentStatistic]:
        """Fetch TSETMC computed liquidity, rank, and rolling statistics for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/MarketData/GetInstrumentStatistic/{ins_code}")
        return _parse_statistics(data, ins_code)

    def share_changes(self, symbol: str | int) -> list[ShareChange]:
        """Fetch historical share count changes (capital increases/splits) for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Instrument/GetInstrumentShareChange/{ins_code}")
        return _parse_share_changes(data, ins_code)

    def related(self, sector_code: str | int) -> list[Instrument]:
        """Fetch peer instruments within ``sector_code``."""
        cleaned = str(sector_code).strip()
        data = self._transport.get_json(f"/api/ClosingPrice/GetRelatedCompany/{cleaned}")
        return _parse_related(data)


class AsyncInstruments(_AsyncResource):
    """Asynchronous resource for instrument search, identity, stats, and corporate actions."""

    async def search(self, query: str) -> list[Instrument]:
        """Search instruments by Persian/Arabic symbol, name, or ISIN."""
        cleaned = normalize_persian(query).strip()
        if not cleaned:
            return []
        data = await self._transport.get_json(_search_path(cleaned))
        return _parse_search(data)

    async def info(self, symbol: str | int) -> InstrumentInfo:
        """Fetch detailed fundamentals, thresholds, and 52-week ranges for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/Instrument/GetInstrumentInfo/{ins_code}")
        return _parse_info(data, ins_code)

    async def identity(self, symbol: str | int) -> InstrumentIdentity:
        """Fetch legal and sector/sub-sector classification identity for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/Instrument/GetInstrumentIdentity/{ins_code}")
        return _parse_identity(data, ins_code)

    async def statistics(self, symbol: str | int) -> list[InstrumentStatistic]:
        """Fetch TSETMC computed liquidity, rank, and rolling statistics for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/MarketData/GetInstrumentStatistic/{ins_code}")
        return _parse_statistics(data, ins_code)

    async def share_changes(self, symbol: str | int) -> list[ShareChange]:
        """Fetch historical share count changes (capital increases/splits) for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(
            f"/api/Instrument/GetInstrumentShareChange/{ins_code}"
        )
        return _parse_share_changes(data, ins_code)

    async def related(self, sector_code: str | int) -> list[Instrument]:
        """Fetch peer instruments within ``sector_code``."""
        cleaned = str(sector_code).strip()
        data = await self._transport.get_json(f"/api/ClosingPrice/GetRelatedCompany/{cleaned}")
        return _parse_related(data)
