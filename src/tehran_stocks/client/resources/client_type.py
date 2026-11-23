"""Individual (حقیقی) vs. institutional (حقوقی) client-type flow resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.types.client_type import ClientTypeDaily, ClientTypeLive


def _parse_client_type_live(data: Any, ins_code: str) -> ClientTypeLive:
    payload = data.get("clientType") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping) or not payload:
        return ClientTypeLive(ins_code=ins_code)
    return ClientTypeLive.from_tsetmc(payload, ins_code=ins_code)


def _normalize_client_type_history_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    count_aliases = (
        ("buy_I_Count", "buy_i_count"),
        ("buy_N_Count", "buy_n_count"),
        ("sell_I_Count", "sell_i_count"),
        ("sell_N_Count", "sell_n_count"),
    )
    for source_key, target_key in count_aliases:
        if target_key not in normalized and source_key in normalized:
            normalized[target_key] = normalized[source_key]
    return normalized


def _parse_client_type_history(
    data: Any,
    ins_code: str,
    *,
    days: int | None = None,
) -> list[ClientTypeDaily]:
    if days is not None and days < 0:
        raise ValueError("days must be >= 0")

    rows = data.get("clientType") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []

    records: list[ClientTypeDaily] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if not row.get("recDate") and not row.get("dEven") and not row.get("date"):
            continue
        records.append(
            ClientTypeDaily.from_tsetmc(
                _normalize_client_type_history_row(row),
                ins_code=ins_code,
            )
        )

    records.sort(key=lambda rec: rec.date)
    if days is not None and days > 0:
        return records[-days:]
    return records


def _parse_client_type_all(data: Any) -> list[ClientTypeLive]:
    rows = data.get("clientTypeAllDto") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    return [ClientTypeLive.from_tsetmc(row) for row in rows if isinstance(row, Mapping)]


class SyncClientType(_SyncResource):
    """Synchronous resource for live, historical, and market-wide client-type flow."""

    def live(self, symbol: str | int) -> ClientTypeLive:
        """Fetch live individual vs. institutional volume and trader counts for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/ClientType/GetClientType/{ins_code}/1/0")
        return _parse_client_type_live(data, ins_code)

    def history(self, symbol: str | int, days: int | None = None) -> list[ClientTypeDaily]:
        """Fetch chronological daily individual/institutional flow history for ``symbol``."""
        if days is not None and days < 0:
            raise ValueError("days must be >= 0")
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/ClientType/GetClientTypeHistory/{ins_code}")
        return _parse_client_type_history(data, ins_code, days=days)

    def all(self) -> list[ClientTypeLive]:
        """Fetch the live individual/institutional snapshot across all active instruments."""
        data = self._transport.get_json("/api/ClientType/GetClientTypeAll")
        return _parse_client_type_all(data)


class AsyncClientType(_AsyncResource):
    """Asynchronous resource for live, historical, and market-wide client-type flow."""

    async def live(self, symbol: str | int) -> ClientTypeLive:
        """Fetch live individual vs. institutional volume and trader counts for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/ClientType/GetClientType/{ins_code}/1/0")
        return _parse_client_type_live(data, ins_code)

    async def history(self, symbol: str | int, days: int | None = None) -> list[ClientTypeDaily]:
        """Fetch chronological daily individual/institutional flow history for ``symbol``."""
        if days is not None and days < 0:
            raise ValueError("days must be >= 0")
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/ClientType/GetClientTypeHistory/{ins_code}")
        return _parse_client_type_history(data, ins_code, days=days)

    async def all(self) -> list[ClientTypeLive]:
        """Fetch the live individual/institutional snapshot across all active instruments."""
        data = await self._transport.get_json("/api/ClientType/GetClientTypeAll")
        return _parse_client_type_all(data)
