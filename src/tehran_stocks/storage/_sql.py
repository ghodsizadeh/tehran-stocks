"""Shared schema metadata, SQL validation, and row conversion helpers for storage."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
import hashlib
import re
from typing import Any, TypeVar

from tehran_stocks.exceptions import StorageError
from tehran_stocks.types.client_type import ClientTypeDaily
from tehran_stocks.types.instrument import Instrument, ShareChange
from tehran_stocks.types.market import Sector
from tehran_stocks.types.price import DailyBar, PriceAdjustment
from tehran_stocks.utils.jalali import int_to_date, jalali_to_gregorian
from tehran_stocks.utils.persian import normalize_persian

_T = TypeVar("_T")

SCHEMA_VERSION = 1

TABLE_NAMES: tuple[str, ...] = (
    "sectors",
    "instruments",
    "daily_prices",
    "client_types",
    "price_adjustments",
    "share_changes",
    "sync_meta",
)

_FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "ALTER",
        "ATTACH",
        "CALL",
        "COPY",
        "CREATE",
        "DELETE",
        "DETACH",
        "DROP",
        "EXEC",
        "EXECUTE",
        "GRANT",
        "INSERT",
        "MERGE",
        "REINDEX",
        "REPLACE",
        "REVOKE",
        "TRUNCATE",
        "UPDATE",
        "VACUUM",
    }
)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_READONLY_BARE_PRAGMAS: frozenset[str] = frozenset(
    {
        "database_list",
        "foreign_keys",
        "journal_mode",
        "user_version",
    }
)
_READONLY_ARG_PRAGMAS: frozenset[str] = frozenset(
    {
        "foreign_key_list",
        "index_info",
        "index_list",
        "table_info",
        "table_xinfo",
    }
)
_BARE_PRAGMA_BODY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARG_PRAGMA_BODY_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*\s*\(\s*(?:[A-Za-z_][A-Za-z0-9_]*)?\s*\)$"
)


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def normalize_sector_code(code: Any) -> str:
    """Normalize TSETMC sector codes (e.g. ``1`` or ``'01 '`` -> ``'01'``)."""
    cleaned = normalize_persian(str("" if code is None else code)).strip()
    if not cleaned:
        return ""
    if cleaned.isdigit() and len(cleaned) == 1:
        return cleaned.zfill(2)
    return cleaned


def normalize_identifier(identifier: str | int) -> str:
    """Normalize symbol, ISIN, or numeric insCode lookups."""
    return normalize_persian(str(identifier)).strip()


def is_direct_ins_code(normalized: str) -> bool:
    """Return True when ``normalized`` looks like a valid numeric TSETMC insCode."""
    return bool(normalized and normalized.isdigit() and len(normalized) >= 5 and int(normalized) > 0)


def resolve_for_query(
    resolve_fn: Callable[[str | int], str | None],
    symbol: str | int,
) -> str | None:
    """Resolve ``symbol`` via stored instruments, falling back to direct numeric insCode."""
    resolved = resolve_fn(symbol)
    if resolved is not None:
        return resolved
    normalized = normalize_identifier(symbol)
    if is_direct_ins_code(normalized):
        return normalized
    return None


def validate_limit(limit: int | None) -> None:
    """Validate optional positive/zero query limits."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")


def slice_recent(items: list[_T], limit: int | None) -> list[_T]:
    """Return the ``limit`` most recent chronological items."""
    if limit is not None and len(items) > limit:
        return items[-limit:]
    return items


def escape_like(value: str) -> str:
    """Escape LIKE wildcard characters using ``!`` as the escape character."""
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def coerce_storage_date(value: date | datetime | int | str | None) -> date | None:
    """Coerce Gregorian or Jalali date representations to ``datetime.date``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = normalize_persian(str(value)).strip()
    if not raw:
        return None

    year_prefix = raw.replace("/", "-")[:4]
    if year_prefix.isdigit() and int(year_prefix) < 1700:
        return jalali_to_gregorian(raw)
    return int_to_date(raw)


def coerce_row_date(value: date | datetime | str) -> date:
    """Parse a stored date column value back into ``datetime.date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def adjustment_event_key(adj: PriceAdjustment) -> str:
    """Build a deterministic composite-PK discriminator for same-day adjustments."""
    corp = "" if adj.corporate_type_code is None else str(adj.corporate_type_code).strip()
    raw = f"{float(adj.adjusted_close)!r}:{float(adj.unadjusted_close)!r}:{corp}"
    if len(raw) <= 64:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def decode_corporate_type_code(raw: str | int | None) -> int | str | None:
    """Convert stored corporate_type_code back to int when purely numeric."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    return text


def _scan_unquoted_sql(sql: str) -> tuple[str, bool]:
    """Strip string/identifier literals and comments, returning unquoted SQL and ``has_equals``."""
    out: list[str] = []
    n = len(sql)
    i = 0
    seen_semicolon = False
    has_equals = False

    while i < n:
        ch = sql[i]

        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            newline = sql.find("\n", i + 2)
            if newline == -1:
                break
            i = newline + 1
            out.append(" ")
            continue

        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                raise StorageError("Unterminated SQL block comment in read-only query")
            i = end + 2
            out.append(" ")
            continue

        if seen_semicolon and not ch.isspace():
            raise StorageError("Multiple SQL statements are not allowed in read-only queries")

        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n:
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                raise StorageError("Unterminated SQL literal in read-only query")
            out.append(" ")
            continue

        if ch == "[":
            end = sql.find("]", i + 1)
            if end == -1:
                raise StorageError("Unterminated SQL identifier in read-only query")
            i = end + 1
            out.append(" ")
            continue

        if ch == ";":
            seen_semicolon = True
            i += 1
            continue

        if ch == "=":
            has_equals = True

        out.append(ch)
        i += 1

    return "".join(out), has_equals


def validate_readonly_sql(sql: str, *, allow_pragma: bool) -> str:
    """Validate that ``sql`` is a single read-only statement and strip trailing semicolons."""
    if not isinstance(sql, str):
        raise StorageError("SQL query must be a string")

    stripped = sql.strip()
    if not stripped:
        raise StorageError("SQL query cannot be empty")

    unquoted, has_equals = _scan_unquoted_sql(stripped)
    tokens = _WORD_RE.findall(unquoted)
    if not tokens:
        raise StorageError("SQL query must start with SELECT or WITH")

    first = tokens[0].upper()
    allowed = {"SELECT", "WITH", "PRAGMA"} if allow_pragma else {"SELECT", "WITH"}
    if first not in allowed:
        allowed_desc = "SELECT, WITH, or PRAGMA" if allow_pragma else "SELECT or WITH"
        raise StorageError(
            f"Only read-only {allowed_desc} queries are permitted (got {first})"
        )

    if first == "PRAGMA":
        if has_equals:
            raise StorageError("Mutating PRAGMA assignments are not permitted in read-only queries")
        if len(tokens) < 2:
            raise StorageError("PRAGMA statement must specify a pragma name")
        pragma_name = tokens[1].lower()
        pragma_body = re.sub(r"^\s*PRAGMA\b", "", unquoted, count=1, flags=re.IGNORECASE).strip()
        if pragma_name in _READONLY_BARE_PRAGMAS:
            if not _BARE_PRAGMA_BODY_RE.match(pragma_body):
                raise StorageError(
                    f"PRAGMA {pragma_name!r} does not accept arguments in read-only queries"
                )
        elif pragma_name in _READONLY_ARG_PRAGMAS:
            if not _ARG_PRAGMA_BODY_RE.match(pragma_body):
                raise StorageError(f"Invalid read-only PRAGMA syntax for {pragma_name!r}")
        else:
            raise StorageError(f"PRAGMA {pragma_name!r} is not permitted in read-only queries")

    for tok in tokens:
        upper = tok.upper()
        if upper in _FORBIDDEN_SQL_KEYWORDS:
            raise StorageError(f"Mutating SQL keyword {upper!r} is not allowed in read-only queries")

    cleaned = stripped.rstrip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def dedupe_rows(
    rows: Iterable[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Deduplicate batch upsert rows by primary key, preserving last occurrence."""
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        by_key[key] = row
    return list(by_key.values())


def sector_to_row(sector: Sector) -> dict[str, Any]:
    return {
        "code": normalize_sector_code(sector.code),
        "name": normalize_persian(sector.name),
        "type": sector.type.strip(),
        "index_ins_code": sector.index_ins_code.strip(),
        "trade_value": int(sector.trade_value),
        "trade_volume": int(sector.trade_volume),
        "trade_count": int(sector.trade_count),
        "market_cap": float(sector.market_cap),
    }


def instrument_to_row(inst: Instrument) -> dict[str, Any]:
    return {
        "ins_code": normalize_persian(str(inst.ins_code)).strip(),
        "symbol": normalize_persian(inst.symbol),
        "name": normalize_persian(inst.name),
        "isin": inst.isin.strip(),
        "instrument_id": inst.instrument_id.strip(),
        "market": normalize_persian(inst.market),
        "flow": int(inst.flow) if inst.flow is not None else None,
        "sector_code": normalize_sector_code(inst.sector_code),
        "sector_name": normalize_persian(inst.sector_name),
        "total_shares": int(inst.total_shares),
    }


def daily_bar_to_row(bar: DailyBar, *, date_as_str: bool) -> dict[str, Any]:
    return {
        "ins_code": str(bar.ins_code).strip(),
        "date": bar.date.isoformat() if date_as_str else bar.date,
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "last": float(bar.last),
        "yesterday": float(bar.yesterday),
        "volume": int(bar.volume),
        "value": int(bar.value),
        "trade_count": int(bar.trade_count),
    }


def client_type_to_row(rec: ClientTypeDaily, *, date_as_str: bool) -> dict[str, Any]:
    return {
        "ins_code": str(rec.ins_code).strip(),
        "date": rec.date.isoformat() if date_as_str else rec.date,
        "buy_i_volume": int(rec.buy_i_volume),
        "buy_n_volume": int(rec.buy_n_volume),
        "sell_i_volume": int(rec.sell_i_volume),
        "sell_n_volume": int(rec.sell_n_volume),
        "buy_i_count": int(rec.buy_i_count),
        "buy_n_count": int(rec.buy_n_count),
        "sell_i_count": int(rec.sell_i_count),
        "sell_n_count": int(rec.sell_n_count),
        "buy_i_value": int(rec.buy_i_value),
        "buy_n_value": int(rec.buy_n_value),
        "sell_i_value": int(rec.sell_i_value),
        "sell_n_value": int(rec.sell_n_value),
    }


def adjustment_to_row(adj: PriceAdjustment, *, date_as_str: bool) -> dict[str, Any]:
    corp = "" if adj.corporate_type_code is None else str(adj.corporate_type_code).strip()
    return {
        "ins_code": str(adj.ins_code).strip(),
        "date": adj.date.isoformat() if date_as_str else adj.date,
        "event_key": adjustment_event_key(adj),
        "adjusted_close": float(adj.adjusted_close),
        "unadjusted_close": float(adj.unadjusted_close),
        "corporate_type_code": corp or None,
    }


def share_change_to_row(sc: ShareChange, *, date_as_str: bool) -> dict[str, Any]:
    return {
        "ins_code": str(sc.ins_code).strip(),
        "date": sc.date.isoformat() if date_as_str else sc.date,
        "new_shares": int(sc.new_shares),
        "old_shares": int(sc.old_shares),
    }


def row_to_instrument(row: Mapping[str, Any]) -> Instrument:
    return Instrument(
        ins_code=str(row["ins_code"]),
        symbol=str(row["symbol"]),
        name=str(row["name"]),
        isin=str(row["isin"] or ""),
        instrument_id=str(row["instrument_id"] or ""),
        market=str(row["market"] or ""),
        flow=int(row["flow"]) if row["flow"] is not None else None,
        sector_code=str(row["sector_code"] or ""),
        sector_name=str(row["sector_name"] or ""),
        total_shares=int(row["total_shares"] or 0),
    )


def row_to_daily_bar(row: Mapping[str, Any]) -> DailyBar:
    return DailyBar(
        ins_code=str(row["ins_code"]),
        date=coerce_row_date(row["date"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        last=float(row["last"]),
        yesterday=float(row["yesterday"]),
        volume=int(row["volume"]),
        value=int(row["value"]),
        trade_count=int(row["trade_count"]),
    )


def row_to_adjustment(row: Mapping[str, Any]) -> PriceAdjustment:
    return PriceAdjustment(
        ins_code=str(row["ins_code"]),
        date=coerce_row_date(row["date"]),
        adjusted_close=float(row["adjusted_close"]),
        unadjusted_close=float(row["unadjusted_close"]),
        corporate_type_code=decode_corporate_type_code(row["corporate_type_code"]),
    )


def row_to_client_type(row: Mapping[str, Any]) -> ClientTypeDaily:
    return ClientTypeDaily(
        ins_code=str(row["ins_code"]),
        date=coerce_row_date(row["date"]),
        buy_i_volume=int(row["buy_i_volume"]),
        buy_n_volume=int(row["buy_n_volume"]),
        sell_i_volume=int(row["sell_i_volume"]),
        sell_n_volume=int(row["sell_n_volume"]),
        buy_i_count=int(row["buy_i_count"]),
        buy_n_count=int(row["buy_n_count"]),
        sell_i_count=int(row["sell_i_count"]),
        sell_n_count=int(row["sell_n_count"]),
        buy_i_value=int(row["buy_i_value"]),
        buy_n_value=int(row["buy_n_value"]),
        sell_i_value=int(row["sell_i_value"]),
        sell_n_value=int(row["sell_n_value"]),
    )
