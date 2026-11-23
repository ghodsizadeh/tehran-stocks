"""Jalali (Shamsi) and TSETMC date/time conversion helpers."""

from __future__ import annotations

from datetime import date, datetime
import re

import jdatetime

from tehran_stocks.utils.persian import normalize_persian

_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")


def int_to_date(value: int | str) -> date:
    """Convert TSETMC YYYYMMDD integer/string (or YYYY-MM-DD) into ``datetime.date``."""
    raw = normalize_persian(str(value)).strip()
    if not raw:
        raise ValueError(f"Invalid TSETMC date value: {value!r}")

    if "-" in raw or "/" in raw:
        cleaned = raw.replace("/", "-")
        try:
            return date.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid TSETMC date value: {value!r}") from exc

    if len(raw) != 8 or not raw.isdigit():
        raise ValueError(f"Invalid TSETMC YYYYMMDD date value: {value!r}")

    year = int(raw[0:4])
    month = int(raw[4:6])
    day = int(raw[6:8])
    return date(year, month, day)


def gregorian_to_jalali(
    value: date | datetime | int | str,
    fmt: str = "%Y-%m-%d",
) -> str:
    """Convert a Gregorian date/datetime or TSETMC YYYYMMDD value to a Jalali string."""
    if isinstance(value, datetime):
        return jdatetime.datetime.fromgregorian(datetime=value).strftime(fmt)

    if isinstance(value, date):
        return jdatetime.date.fromgregorian(date=value).strftime(fmt)

    raw = normalize_persian(str(value)).strip()
    if "T" in raw or " " in raw:
        try:
            parsed_dt = datetime.fromisoformat(raw.replace("/", "-"))
            return jdatetime.datetime.fromgregorian(datetime=parsed_dt).strftime(fmt)
        except ValueError:
            pass

    parsed_date = int_to_date(raw)
    return jdatetime.date.fromgregorian(date=parsed_date).strftime(fmt)


def jalali_to_gregorian(value: str) -> date:
    """Parse a Jalali date string (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD) to ``datetime.date``."""
    raw = normalize_persian(value).strip()
    if not raw:
        raise ValueError(f"Invalid Jalali date string: {value!r}")

    if "-" in raw or "/" in raw:
        parts = raw.replace("/", "-").split("-")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Invalid Jalali date string: {value!r}")
        year, month, day = (int(p) for p in parts)
    elif len(raw) == 8 and raw.isdigit():
        year, month, day = int(raw[0:4]), int(raw[4:6]), int(raw[6:8])
    else:
        raise ValueError(f"Invalid Jalali date string: {value!r}")

    return jdatetime.date(year, month, day).togregorian()


def parse_tsetmc_time(heven: int | str) -> str:
    """Format TSETMC ``hEven`` (e.g. ``122951`` or ``90503``) as ``HH:MM:SS``."""
    raw = normalize_persian(str(heven)).strip()
    if not raw:
        raise ValueError(f"Invalid TSETMC time value: {heven!r}")

    match = _TIME_RE.match(raw)
    if match:
        hh, mm, ss = (int(g) for g in match.groups())
    else:
        if not raw.isdigit() or len(raw) > 6:
            raise ValueError(f"Invalid TSETMC hEven time value: {heven!r}")
        padded = raw.zfill(6)
        hh, mm, ss = int(padded[0:2]), int(padded[2:4]), int(padded[4:6])

    if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
        raise ValueError(f"Out-of-range TSETMC time value: {heven!r}")

    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def tsetmc_datetime(deven: int | str, heven: int | str) -> datetime:
    """Combine TSETMC ``dEven`` and ``hEven`` into a naive ``datetime``."""
    d = int_to_date(deven)
    t_str = parse_tsetmc_time(heven)
    hh, mm, ss = (int(part) for part in t_str.split(":"))
    return datetime(d.year, d.month, d.day, hh, mm, ss)
