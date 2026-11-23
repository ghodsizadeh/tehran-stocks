"""ETF NAV and exchange-traded options watch resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tehran_stocks.client.resources._base import _AsyncResource, _SyncResource
from tehran_stocks.exceptions import InstrumentNotFoundError
from tehran_stocks.types.disclosure import ETFInfo, OptionWatchItem


def _parse_etf(data: Any, ins_code: str) -> ETFInfo:
    payload = data.get("etf") if isinstance(data, Mapping) else data
    if not isinstance(payload, Mapping) or not payload:
        raise InstrumentNotFoundError(ins_code)

    normalized = dict(payload)
    if not normalized.get("dEven") and normalized.get("deven"):
        normalized["dEven"] = normalized["deven"]
    if normalized.get("pRedemtVal") is None and normalized.get("pRedTran") is not None:
        normalized["pRedemtVal"] = normalized["pRedTran"]
    if normalized.get("pSubcptVal") is None and normalized.get("pSubTran") is not None:
        normalized["pSubcptVal"] = normalized["pSubTran"]
    return ETFInfo.from_tsetmc(normalized, ins_code=ins_code)


def _extract_option_side(row: Mapping[str, Any], suffix: str) -> dict[str, Any] | None:
    ins_code = row.get(f"insCode{suffix}")
    if not ins_code or ins_code == "0":
        return None
    return {
        "insCode": ins_code,
        "lVal18AFC": row.get(f"lVal18AFC{suffix}"),
        "lVal30": row.get(f"lVal30{suffix}"),
        "uaInsCode": row.get("uaInsCode") or row.get("insCodeUA"),
        "cSize": row.get("contractSize") if row.get("contractSize") is not None else row.get("cSize"),
        "strikePrice": row.get("strikePrice"),
        "endDate": row.get("endDate"),
        "remainedDay": row.get("remainedDay"),
        "openPosition": row.get(f"oP{suffix}"),
        "pMeDem_Buy": row.get(f"pMeDem{suffix}"),
        "pMeOf_Sell": row.get(f"pMeOf{suffix}"),
        "pDrCotVal": row.get(f"pDrCotVal{suffix}"),
        "pClosing": row.get(f"pClosing{suffix}"),
        "qTotTran5J": row.get(f"qTotTran5J{suffix}"),
        "qTotCap": row.get(f"qTotCap{suffix}"),
        "zTotTran": row.get(f"zTotTran{suffix}"),
    }


def _parse_options(data: Any) -> list[OptionWatchItem]:
    rows = data.get("instrumentOptMarketWatch") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return []

    items: list[OptionWatchItem] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if "insCode_C" in row or "insCode_P" in row:
            for suffix in ("_C", "_P"):
                side_payload = _extract_option_side(row, suffix)
                if side_payload is not None:
                    items.append(OptionWatchItem.from_tsetmc(side_payload))
        else:
            items.append(OptionWatchItem.from_tsetmc(row))
    return items


class SyncFunds(_SyncResource):
    """Synchronous resource for ETF NAVs and exchange-traded options watch."""

    def etf(self, symbol: str | int) -> ETFInfo:
        """Fetch live redemption, subscription, and statistical NAV for ETF ``symbol``."""
        ins_code = self._resolve(symbol)
        data = self._transport.get_json(f"/api/Fund/GetETFByInsCode/{ins_code}")
        return _parse_etf(data, ins_code)

    def options(self, flow: int = 1) -> list[OptionWatchItem]:
        """Fetch live equity option contracts (call and put sides) for ``flow``."""
        data = self._transport.get_json(f"/api/Instrument/GetInstrumentOptionMarketWatch/{flow}")
        return _parse_options(data)


class AsyncFunds(_AsyncResource):
    """Asynchronous resource for ETF NAVs and exchange-traded options watch."""

    async def etf(self, symbol: str | int) -> ETFInfo:
        """Fetch live redemption, subscription, and statistical NAV for ETF ``symbol``."""
        ins_code = await self._resolve(symbol)
        data = await self._transport.get_json(f"/api/Fund/GetETFByInsCode/{ins_code}")
        return _parse_etf(data, ins_code)

    async def options(self, flow: int = 1) -> list[OptionWatchItem]:
        """Fetch live equity option contracts (call and put sides) for ``flow``."""
        data = await self._transport.get_json(
            f"/api/Instrument/GetInstrumentOptionMarketWatch/{flow}"
        )
        return _parse_options(data)
