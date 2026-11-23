"""Market watch, overview, sectors, indices, index effects, and top trades."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.types.market import (
    IndexBar,
    IndexEffectItem,
    IndexQuote,
    MarketOverview,
    MarketWatchItem,
    Sector,
)
from tehran_stocks.utils.persian import normalize_persian

TEDPIX_INS_CODE = "32097828799138957"
_INDEX_ALIASES: dict[str, str] = {
    "TEDPIX": TEDPIX_INS_CODE,
    "شاخص کل": TEDPIX_INS_CODE,
}


def _resolve_index_code(code: str | int) -> str:
    raw = normalize_persian(str(code)).strip()
    return _INDEX_ALIASES.get(raw.upper(), _INDEX_ALIASES.get(raw, raw))


def _clean_order_book_levels(raw_levels: Any) -> list[Mapping[str, Any]]:
    if not isinstance(raw_levels, list):
        return []
    cleaned: list[Mapping[str, Any]] = []
    for lvl in raw_levels:
        if not isinstance(lvl, Mapping):
            continue
        row_num = lvl.get("n", lvl.get("number", 0))
        if row_num in (0, None) and not any(
            lvl.get(k, 0) for k in ("pmd", "pmo", "qmd", "qmo", "pMeDem", "pMeOf")
        ):
            continue
        cleaned.append(lvl)
    return cleaned


def _parse_market_watch(data: Any) -> list[MarketWatchItem]:
    rows = data.get("marketwatch") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    items: list[MarketWatchItem] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if "blDs" in normalized:
            normalized["blDs"] = _clean_order_book_levels(normalized["blDs"])
        items.append(MarketWatchItem.from_tsetmc(normalized))
    return items


def _parse_market_overview(data: Any, flow: int) -> MarketOverview:
    payload = data.get("marketOverview") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping):
        payload = {}
    return MarketOverview.from_tsetmc(payload, flow=flow)


def _sector_join_key(code: Any) -> str:
    stripped = str(code).strip()
    return stripped.lstrip("0") or "0"


def _parse_sectors(summary_data: Any, static_data: Any) -> list[Sector]:
    static_rows = static_data.get("staticData") if isinstance(static_data, Mapping) else static_data
    summary_rows = (
        summary_data.get("sectorSummeries")
        if isinstance(summary_data, Mapping)
        else summary_data
    )
    if not isinstance(summary_rows, list) and isinstance(summary_data, Mapping):
        summary_rows = summary_data.get("sectorsSummary") or []

    static_by_key: dict[str, dict[str, Any]] = {}
    if isinstance(static_rows, list):
        for row in static_rows:
            if not isinstance(row, Mapping):
                continue
            row_type = str(row.get("type") or "").strip()
            if row_type and row_type != "IndustrialGroup":
                continue
            code = row.get("code")
            if code is None:
                continue
            key = _sector_join_key(code)
            static_by_key[key] = {
                "code": str(code).strip().zfill(2),
                "name": normalize_persian(str(row.get("name") or "")).strip(),
                "type": row_type or "IndustrialGroup",
            }

    merged_by_key: dict[str, Sector] = {}
    if isinstance(summary_rows, list):
        for row in summary_rows:
            if not isinstance(row, Mapping):
                continue
            raw_code = str(row.get("cSecVal") or row.get("code") or "").strip()
            if not raw_code:
                continue
            key = _sector_join_key(raw_code)
            static_meta = static_by_key.get(key, {})
            payload = dict(row)
            payload["cSecVal"] = raw_code
            if not payload.get("lSecVal") and static_meta.get("name"):
                payload["lSecVal"] = static_meta["name"]
            if not payload.get("type"):
                payload["type"] = static_meta.get("type", "IndustrialGroup")
            merged_by_key[key] = Sector.from_tsetmc(payload)

    for key, static_meta in static_by_key.items():
        if key not in merged_by_key:
            merged_by_key[key] = Sector(
                code=static_meta["code"],
                name=static_meta["name"],
                type=static_meta["type"],
            )

    return sorted(merged_by_key.values(), key=lambda sector: sector.code)


def _parse_indices(data: Any) -> list[IndexQuote]:
    rows = data.get("indexB1") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results: list[IndexQuote] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if normalized.get("xVarIdxJRWO") is None and normalized.get("xVarIdxJRfV") is not None:
            normalized["xVarIdxJRWO"] = normalized["xVarIdxJRfV"]
        results.append(IndexQuote.from_tsetmc(normalized))
    return results


def _parse_index_history(data: Any, ins_code: str) -> list[IndexBar]:
    rows = data.get("indexB2") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    bars: list[IndexBar] = []
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("dEven"):
            continue
        bars.append(IndexBar.from_tsetmc(row, ins_code=ins_code))
    bars.sort(key=lambda bar: bar.date)
    return bars


def _parse_index_effect(data: Any) -> list[IndexEffectItem]:
    rows = data.get("instEffect") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    return [IndexEffectItem.from_tsetmc(row) for row in rows if isinstance(row, Mapping)]


def _parse_top_trades(data: Any) -> list[MarketWatchItem]:
    rows = data.get("tradeTop") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    items: list[MarketWatchItem] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        nested = row.get("instrument")
        if isinstance(nested, Mapping):
            merged = {**nested, **row}
            if merged.get("insCode") in (None, "", "0", 0) and nested.get("insCode"):
                merged["insCode"] = nested["insCode"]
        else:
            merged = dict(row)
        items.append(MarketWatchItem.from_tsetmc(merged))
    return items


class SyncMarket(_SyncResource):
    """Synchronous resource for market watch, overview, sectors, indices, and top movers."""

    def watch(self) -> list[MarketWatchItem]:
        """Fetch the full live market watch snapshot in one HTTP call."""
        data = self._transport.get_json("/api/ClosingPrice/GetMarketWatch")
        return _parse_market_watch(data)

    def overview(self, flow: int = 1) -> MarketOverview:
        """Fetch market overview summary for ``flow`` (1=TSE, 2=Farabourse)."""
        data = self._transport.get_json(f"/api/MarketData/GetMarketOverview/{flow}")
        return _parse_market_overview(data, flow=flow)

    def sectors(self) -> list[Sector]:
        """Fetch industrial sectors combining ``GetStaticData`` and ``GetSectorsSummary``."""
        summary_data = self._transport.get_json("/api/MarketData/GetSectorsSummary")
        static_data = self._transport.get_json("/api/StaticData/GetStaticData")
        return _parse_sectors(summary_data, static_data)

    def indices(self, flow: int = 1) -> list[IndexQuote]:
        """Fetch all live market and industry indices for ``flow``."""
        data = self._transport.get_json(f"/api/Index/GetIndexB1LastAll/All/{flow}")
        return _parse_indices(data)

    def index_history(self, code: str | int) -> list[IndexBar]:
        """Fetch chronological daily history for an index (insCode or ``'TEDPIX'``)."""
        ins_code = _resolve_index_code(code)
        data = self._transport.get_json(f"/api/Index/GetIndexB2History/{ins_code}")
        return _parse_index_history(data, ins_code)

    def index_effect(
        self,
        code: str | int,
        flow: int = 1,
        top: int = 10,
    ) -> list[IndexEffectItem]:
        """Fetch top instruments impacting index ``code``."""
        ins_code = _resolve_index_code(code)
        data = self._transport.get_json(f"/api/Index/GetInstEffect/{ins_code}/{flow}/{top}")
        return _parse_index_effect(data)

    def top_trades(
        self,
        category: int = 1,
        flow: int = 1,
        top: int = 10,
    ) -> list[MarketWatchItem]:
        """Fetch top traded instruments by volume/value/trades category."""
        data = self._transport.get_json(f"/api/ClosingPrice/GetTradeTop/{category}/{flow}/{top}")
        return _parse_top_trades(data)


class AsyncMarket(_AsyncResource):
    """Asynchronous resource for market watch, overview, sectors, indices, and top movers."""

    async def watch(self) -> list[MarketWatchItem]:
        """Fetch the full live market watch snapshot in one HTTP call."""
        data = await self._transport.get_json("/api/ClosingPrice/GetMarketWatch")
        return _parse_market_watch(data)

    async def overview(self, flow: int = 1) -> MarketOverview:
        """Fetch market overview summary for ``flow`` (1=TSE, 2=Farabourse)."""
        data = await self._transport.get_json(f"/api/MarketData/GetMarketOverview/{flow}")
        return _parse_market_overview(data, flow=flow)

    async def sectors(self) -> list[Sector]:
        """Fetch industrial sectors combining ``GetStaticData`` and ``GetSectorsSummary``."""
        summary_data, static_data = await asyncio.gather(
            self._transport.get_json("/api/MarketData/GetSectorsSummary"),
            self._transport.get_json("/api/StaticData/GetStaticData"),
        )
        return _parse_sectors(summary_data, static_data)

    async def indices(self, flow: int = 1) -> list[IndexQuote]:
        """Fetch all live market and industry indices for ``flow``."""
        data = await self._transport.get_json(f"/api/Index/GetIndexB1LastAll/All/{flow}")
        return _parse_indices(data)

    async def index_history(self, code: str | int) -> list[IndexBar]:
        """Fetch chronological daily history for an index (insCode or ``'TEDPIX'``)."""
        ins_code = _resolve_index_code(code)
        data = await self._transport.get_json(f"/api/Index/GetIndexB2History/{ins_code}")
        return _parse_index_history(data, ins_code)

    async def index_effect(
        self,
        code: str | int,
        flow: int = 1,
        top: int = 10,
    ) -> list[IndexEffectItem]:
        """Fetch top instruments impacting index ``code``."""
        ins_code = _resolve_index_code(code)
        data = await self._transport.get_json(f"/api/Index/GetInstEffect/{ins_code}/{flow}/{top}")
        return _parse_index_effect(data)

    async def top_trades(
        self,
        category: int = 1,
        flow: int = 1,
        top: int = 10,
    ) -> list[MarketWatchItem]:
        """Fetch top traded instruments by volume/value/trades category."""
        data = await self._transport.get_json(
            f"/api/ClosingPrice/GetTradeTop/{category}/{flow}/{top}"
        )
        return _parse_top_trades(data)
