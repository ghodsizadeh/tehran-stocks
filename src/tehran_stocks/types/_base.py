"""Shared serialization and TSETMC payload parsing helpers for domain models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import math
from typing import Any

from tehran_stocks.utils.jalali import int_to_date, parse_tsetmc_time
from tehran_stocks.utils.persian import normalize_persian

_PLACEHOLDER_STRINGS = frozenset(
    {
        "-",
        "--",
        "—",
        "na",
        "n/a",
        "null",
        "none",
        "nan",
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
    }
)


def _serialize_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return {f.name: _serialize_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, Enum):
        return value.value
    return value


class SerializableMixin:
    """Mixin providing ``to_dict()`` JSON-compatible serialization for dataclasses."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass fields to a plain JSON-friendly dictionary."""
        return {
            f.name: _serialize_value(getattr(self, f.name))
            for f in fields(self)  # type: ignore[arg-type]
        }


def _pick(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first non-None value found among candidate keys."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _resolve_ins_code(data: Mapping[str, Any], ins_code: str = "") -> str:
    raw = data.get("insCode")
    if raw in (None, "", "0", 0):
        raw = data.get("ins_code")
    if raw in (None, "", "0", 0):
        return ins_code
    return str(raw).strip()


def _as_str(value: Any, *, normalize: bool = False) -> str:
    if value is None:
        return ""
    text = str(value)
    return normalize_persian(text) if normalize else text.strip()


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in _PLACEHOLDER_STRINGS:
            return None
        try:
            return int(cleaned)
        except ValueError:
            try:
                dec = Decimal(cleaned)
            except InvalidOperation as exc:
                raise ValueError(f"Invalid integer value: {value!r}") from exc
            if not dec.is_finite():
                return None
            return int(dec)
    return int(value)


def _as_int(value: Any, default: int = 0) -> int:
    parsed = _as_optional_int(value)
    return default if parsed is None else parsed


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) else None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in _PLACEHOLDER_STRINGS:
            return None
        num = float(cleaned)
        return num if math.isfinite(num) else None
    num = float(value)
    return num if math.isfinite(num) else None


def _as_float(value: Any, default: float = 0.0) -> float:
    parsed = _as_optional_float(value)
    return default if parsed is None else parsed


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return int_to_date(value)


def _as_optional_date(value: Any) -> date | None:
    if value is None or value == "" or value == 0 or value == "0":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return int_to_date(value)
    except ValueError:
        return None


def _as_optional_time(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return parse_tsetmc_time(value)
    except ValueError:
        return str(value).strip()
