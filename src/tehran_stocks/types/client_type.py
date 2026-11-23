"""Individual (حقیقی) vs. institutional (حقوقی) client-type flow models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from tehran_stocks.types._base import SerializableMixin, _as_date, _as_int, _as_str, _pick


class _ClientTypeMetricsMixin:
    """Shared computed money-flow, per-capita, and buyer-power metrics."""

    __slots__ = ()

    buy_i_volume: int
    sell_i_volume: int
    buy_i_count: int
    sell_i_count: int
    buy_i_value: int
    sell_i_value: int

    @property
    def net_i_volume(self) -> int:
        """Net individual buy minus sell share volume."""
        return self.buy_i_volume - self.sell_i_volume

    @property
    def real_money_flow(self) -> int:
        """Net individual money flow (ورود/خروج پول حقیقی) in Rials."""
        return self.buy_i_value - self.sell_i_value

    @property
    def buy_per_capita(self) -> float:
        """Average individual buy value per trader (سرانه خرید حقیقی)."""
        if self.buy_i_count <= 0:
            return 0.0
        return self.buy_i_value / self.buy_i_count

    @property
    def sell_per_capita(self) -> float:
        """Average individual sell value per trader (سرانه فروش حقیقی)."""
        if self.sell_i_count <= 0:
            return 0.0
        return self.sell_i_value / self.sell_i_count

    @property
    def buyer_power(self) -> float:
        """Buyer-to-seller power ratio (قدرت خریدار به فروشنده)."""
        sell_pc = self.sell_per_capita
        if sell_pc <= 0:
            return 0.0
        return self.buy_per_capita / sell_pc

    @property
    def buy_per_capita_volume(self) -> float:
        """Average individual buy share volume per trader."""
        if self.buy_i_count <= 0:
            return 0.0
        return self.buy_i_volume / self.buy_i_count

    @property
    def sell_per_capita_volume(self) -> float:
        """Average individual sell share volume per trader."""
        if self.sell_i_count <= 0:
            return 0.0
        return self.sell_i_volume / self.sell_i_count

    @property
    def volume_buyer_power(self) -> float:
        """Volume-based buyer-to-seller power ratio when value fields are absent."""
        sell_pc_vol = self.sell_per_capita_volume
        if sell_pc_vol <= 0:
            return 0.0
        return self.buy_per_capita_volume / sell_pc_vol


def _client_type_kwargs(data: Mapping[str, Any], ins_code: str = "") -> dict[str, Any]:
    return {
        "ins_code": _as_str(_pick(data, "insCode", "ins_code", default=ins_code)),
        "buy_i_volume": _as_int(_pick(data, "buy_I_Volume", "buyIVolume", "buy_i_volume", default=0)),
        "buy_n_volume": _as_int(_pick(data, "buy_N_Volume", "buyNVolume", "buy_n_volume", default=0)),
        "sell_i_volume": _as_int(_pick(data, "sell_I_Volume", "sellIVolume", "sell_i_volume", default=0)),
        "sell_n_volume": _as_int(_pick(data, "sell_N_Volume", "sellNVolume", "sell_n_volume", default=0)),
        "buy_i_count": _as_int(
            _pick(data, "buy_CountI", "buy_I_Count", "buyCountI", "buyICount", "buy_i_count", default=0)
        ),
        "buy_n_count": _as_int(
            _pick(data, "buy_CountN", "buy_N_Count", "buyCountN", "buyNCount", "buy_n_count", default=0)
        ),
        "sell_i_count": _as_int(
            _pick(data, "sell_CountI", "sell_I_Count", "sellCountI", "sellICount", "sell_i_count", default=0)
        ),
        "sell_n_count": _as_int(
            _pick(data, "sell_CountN", "sell_N_Count", "sellCountN", "sellNCount", "sell_n_count", default=0)
        ),
        "buy_i_value": _as_int(_pick(data, "buy_I_Value", "buyIValue", "buy_i_value", default=0)),
        "buy_n_value": _as_int(_pick(data, "buy_N_Value", "buyNValue", "buy_n_value", default=0)),
        "sell_i_value": _as_int(_pick(data, "sell_I_Value", "sellIValue", "sell_i_value", default=0)),
        "sell_n_value": _as_int(_pick(data, "sell_N_Value", "sellNValue", "sell_n_value", default=0)),
    }


@dataclass(frozen=True, slots=True)
class ClientTypeLive(SerializableMixin, _ClientTypeMetricsMixin):
    """Live individual vs. institutional trading breakdown."""

    ins_code: str
    buy_i_volume: int = 0
    buy_n_volume: int = 0
    sell_i_volume: int = 0
    sell_n_volume: int = 0
    buy_i_count: int = 0
    buy_n_count: int = 0
    sell_i_count: int = 0
    sell_n_count: int = 0
    buy_i_value: int = 0
    buy_n_value: int = 0
    sell_i_value: int = 0
    sell_n_value: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> ClientTypeLive:
        payload = data.get("clientType") if isinstance(data.get("clientType"), Mapping) else data
        return cls(**_client_type_kwargs(payload, ins_code=ins_code))


@dataclass(frozen=True, slots=True)
class ClientTypeDaily(SerializableMixin, _ClientTypeMetricsMixin):
    """Daily individual vs. institutional trading history with money-flow metrics."""

    ins_code: str
    date: date
    buy_i_volume: int = 0
    buy_n_volume: int = 0
    sell_i_volume: int = 0
    sell_n_volume: int = 0
    buy_i_count: int = 0
    buy_n_count: int = 0
    sell_i_count: int = 0
    sell_n_count: int = 0
    buy_i_value: int = 0
    buy_n_value: int = 0
    sell_i_value: int = 0
    sell_n_value: int = 0

    @classmethod
    def from_tsetmc(cls, data: Mapping[str, Any], ins_code: str = "") -> ClientTypeDaily:
        parsed_date = _as_date(_pick(data, "recDate", "dEven", "date"))
        return cls(date=parsed_date, **_client_type_kwargs(data, ins_code=ins_code))
