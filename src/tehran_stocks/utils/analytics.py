"""Financial analytics helpers: backward price adjustment and Jalali DataFrames."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass, replace
from typing import TYPE_CHECKING, Any

import jalali_pandas
import pandas as pd

if TYPE_CHECKING:
    from tehran_stocks.types.price import DailyBar, PriceAdjustment


def adjust_prices(
    bars: Sequence[DailyBar],
    adjustments: Sequence[PriceAdjustment],
) -> list[DailyBar]:
    """Apply backward corporate-action price adjustment to historical daily bars.

    Preserves raw metadata (``ins_code``, ``date``, ``volume``, ``value``,
    ``trade_count``) while scaling ``open``, ``high``, ``low``, ``close``,
    ``last``, and ``yesterday`` by the cumulative ``pClosing / pClosingNotAdjusted``
    ratio for all adjustment events strictly after each bar's date.
    """
    if not bars:
        return []

    valid_adjustments = sorted(
        (
            adj
            for adj in adjustments
            if adj.unadjusted_close > 0 and adj.adjusted_close > 0
        ),
        key=lambda adj: adj.date,
    )
    if not valid_adjustments:
        return list(bars)

    adjusted_bars: list[DailyBar] = []
    for bar in bars:
        factor = 1.0
        for adj in valid_adjustments:
            if bar.date < adj.date:
                factor *= adj.adjusted_close / adj.unadjusted_close

        if factor == 1.0:
            adjusted_bars.append(bar)
        else:
            adjusted_bars.append(
                replace(
                    bar,
                    open=bar.open * factor,
                    high=bar.high * factor,
                    low=bar.low * factor,
                    close=bar.close * factor,
                    last=bar.last * factor,
                    yesterday=bar.yesterday * factor,
                )
            )
    return adjusted_bars


def _record_to_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_dict") and callable(record.to_dict):
        return dict(record.to_dict())
    if is_dataclass(record) and not isinstance(record, type):
        return asdict(record)
    if isinstance(record, Mapping):
        return dict(record)
    raise TypeError(f"Unsupported record type for to_dataframe: {type(record).__name__}")


def to_dataframe(
    records: Sequence[Any] | Iterable[Any],
    jalali: bool = True,
    index_by_date: bool = True,
) -> pd.DataFrame:
    """Convert dataclass instances or dicts into a pandas DataFrame.

    When a ``date`` column is present and non-empty:
    - ``jalali=True`` adds a ``jdate`` column (``jalali_datetime`` dtype) via
      ``jalali_pandas.to_jalali_datetime()``.
    - ``index_by_date=True`` sets the DataFrame index to a ``JalaliDatetimeIndex``
      when ``jalali=True``, or a Gregorian ``DatetimeIndex`` when ``jalali=False``.
    """
    if records is None:
        return pd.DataFrame()

    if isinstance(records, Mapping) or (is_dataclass(records) and not isinstance(records, type)):
        items = [records]
    else:
        items = list(records)

    if not items:
        return pd.DataFrame()

    rows = [_record_to_dict(item) for item in items]
    df = pd.DataFrame(rows)

    if "date" in df.columns:
        dt = pd.to_datetime(df["date"], errors="coerce")
        if dt.notna().any():
            df["date"] = dt
            j_series: pd.Series | None = None
            if jalali:
                j_series = jalali_pandas.to_jalali_datetime(dt)
                df["jdate"] = j_series

            if index_by_date:
                if jalali and j_series is not None:
                    df.index = jalali_pandas.JalaliDatetimeIndex(j_series, name="jdate")
                else:
                    df.index = pd.DatetimeIndex(dt, name="date")

    return df
