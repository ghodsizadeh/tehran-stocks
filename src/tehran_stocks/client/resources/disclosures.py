"""Major shareholders, Codal disclosures, and market supervisor messages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.types.disclosure import CodalAnnouncement, Shareholder, SupervisorMessage


def _parse_shareholders(data: Any, ins_code: str) -> list[Shareholder]:
    rows = data.get("shareHolder") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results: list[Shareholder] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if normalized.get("shareHolderID") in (None, 0, "0", "") and normalized.get(
            "shareHolderShareID"
        ):
            normalized["shareHolderID"] = normalized["shareHolderShareID"]
        results.append(Shareholder.from_tsetmc(normalized, ins_code=ins_code))
    return results


def _parse_codal(
    data: Any,
    ins_code: str,
    *,
    limit: int | None = None,
) -> list[CodalAnnouncement]:
    rows = data.get("preparedData") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []

    results: list[CodalAnnouncement] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        if not normalized.get("publishDateTime") and normalized.get("publishDateTime_Gregorian"):
            normalized["publishDateTime"] = normalized["publishDateTime_Gregorian"]
        if not normalized.get("sentDateTime") and normalized.get("sentDateTime_Gregorian"):
            normalized["sentDateTime"] = normalized["sentDateTime_Gregorian"]
        if not normalized.get("dEven") and normalized.get("publishDateTime_DEven"):
            normalized["dEven"] = normalized["publishDateTime_DEven"]
        if "hasExcel" not in normalized and "hasExcelReport" in normalized:
            normalized["hasExcel"] = bool(normalized["hasExcelReport"])
        if "hasPdf" not in normalized and "hasPDFReport" in normalized:
            normalized["hasPdf"] = bool(normalized["hasPDFReport"])
        results.append(CodalAnnouncement.from_tsetmc(normalized, ins_code=ins_code))

    if limit is not None:
        return [] if limit == 0 else results[:limit]
    return results


def _parse_messages(
    data: Any,
    ins_code: str,
    *,
    limit: int | None = None,
) -> list[SupervisorMessage]:
    rows = data.get("msg") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []
    results = [
        SupervisorMessage.from_tsetmc(row, ins_code=ins_code)
        for row in rows
        if isinstance(row, Mapping)
    ]
    if limit is not None:
        return [] if limit == 0 else results[:limit]
    return results


class SyncDisclosures(_SyncResource):
    """Synchronous resource for major shareholders, Codal filings, and supervisor messages."""

    def shareholders(self, symbol: str | int) -> list[Shareholder]:
        """Fetch major shareholders (>1% stake) for ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(
            f"/api/Shareholder/GetInstrumentShareHolderLast/{ins_code}"
        )
        return _parse_shareholders(data, ins_code)

    def codal(self, symbol: str | int, limit: int = 10) -> list[CodalAnnouncement]:
        """Fetch recent Codal corporate disclosures and filings for ``symbol``."""
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if limit == 0:
            return []
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Codal/GetPreparedDataByInsCode/{limit}/{ins_code}")
        return _parse_codal(data, ins_code, limit=limit)

    def messages(self, symbol: str | int, limit: int | None = None) -> list[SupervisorMessage]:
        """Fetch market supervisor messages (halts, reopenings, notices) for ``symbol``."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Msg/GetMsgByInsCode/{ins_code}")
        return _parse_messages(data, ins_code, limit=limit)


class AsyncDisclosures(_AsyncResource):
    """Asynchronous resource for major shareholders, Codal filings, and supervisor messages."""

    async def shareholders(self, symbol: str | int) -> list[Shareholder]:
        """Fetch major shareholders (>1% stake) for ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(
            f"/api/Shareholder/GetInstrumentShareHolderLast/{ins_code}"
        )
        return _parse_shareholders(data, ins_code)

    async def codal(self, symbol: str | int, limit: int = 10) -> list[CodalAnnouncement]:
        """Fetch recent Codal corporate disclosures and filings for ``symbol``."""
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if limit == 0:
            return []
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(
            f"/api/Codal/GetPreparedDataByInsCode/{limit}/{ins_code}"
        )
        return _parse_codal(data, ins_code, limit=limit)

    async def messages(
        self,
        symbol: str | int,
        limit: int | None = None,
    ) -> list[SupervisorMessage]:
        """Fetch market supervisor messages (halts, reopenings, notices) for ``symbol``."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/Msg/GetMsgByInsCode/{ins_code}")
        return _parse_messages(data, ins_code, limit=limit)
