"""Typer CLI (``tse`` / ``tehran-stocks``) for on-demand TSETMC data and opt-in DB ops."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import importlib
import math
from pathlib import Path
import re
from typing import Annotated, Any, TypeVar
from urllib.parse import unquote, urlsplit

import httpx2
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
import typer

from tehran_stocks.client.base import AsyncTSETMCClient, TSETMCClient
from tehran_stocks.client.transport import DEFAULT_TIMEOUT
from tehran_stocks.cli.formatters import (
    ColumnSpec,
    OutputFormat,
    cli_error_boundary,
    emit_json,
    exit_code_for_error,
    fail_with_error,
    fmt_float,
    fmt_int,
    fmt_number,
    fmt_pct,
    fmt_text,
    get_stderr_console,
    output_record,
    output_records,
    print_error,
    resolve_output_format,
)
from tehran_stocks.exceptions import StorageError, TehranStocksError
from tehran_stocks.types.client_type import ClientTypeDaily, ClientTypeLive
from tehran_stocks.types.market import MarketWatchItem
from tehran_stocks.utils.jalali import gregorian_to_jalali
from tehran_stocks.utils.persian import normalize_persian

_T = TypeVar("_T")

_TRANSPORT_OVERRIDE: httpx2.BaseTransport | None = None
_ASYNC_TRANSPORT_OVERRIDE: httpx2.AsyncBaseTransport | None = None

FormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        "-f",
        case_sensitive=False,
        help="Output format: table, json, or csv.",
    ),
]
JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Emit JSON output (shorthand for --format json).",
    ),
]
DbOption = Annotated[
    str,
    typer.Option(
        "--db",
        envvar="TEHRAN_STOCKS_DB",
        help="SQLite file path or SQLAlchemy database URI.",
    ),
]


class ScreenSort(str, Enum):
    """Supported sort keys for ``tse screen``."""

    VALUE = "value"
    VOLUME = "volume"
    CHANGE = "change"
    MONEY_FLOW = "money_flow"
    BUYER_POWER = "buyer_power"


@dataclass(slots=True)
class CliConfig:
    """Runtime CLI configuration passed through Typer context."""

    timeout: float = DEFAULT_TIMEOUT
    proxy: str | None = None
    transport: httpx2.BaseTransport | None = None
    async_transport: httpx2.AsyncBaseTransport | None = None


def create_client(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
    transport: httpx2.BaseTransport | None = None,
) -> TSETMCClient:
    """Create a synchronous ``TSETMCClient`` with optional transport injection."""
    effective_transport = transport if transport is not None else _TRANSPORT_OVERRIDE
    return TSETMCClient(
        timeout=timeout,
        proxy=proxy,
        transport=effective_transport,
    )


def create_async_client(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> AsyncTSETMCClient:
    """Create an async ``AsyncTSETMCClient`` with optional transport injection."""
    effective_transport = transport if transport is not None else _ASYNC_TRANSPORT_OVERRIDE
    if effective_transport is None and isinstance(_TRANSPORT_OVERRIDE, httpx2.AsyncBaseTransport):
        effective_transport = _TRANSPORT_OVERRIDE
    return AsyncTSETMCClient(
        timeout=timeout,
        proxy=proxy,
        transport=effective_transport,
    )


def _get_config(ctx: typer.Context) -> CliConfig:
    obj = ctx.obj
    if isinstance(obj, CliConfig):
        return obj
    if isinstance(obj, Mapping):
        return CliConfig(
            timeout=float(obj.get("timeout", DEFAULT_TIMEOUT)),
            proxy=obj.get("proxy"),
            transport=obj.get("transport"),
            async_transport=obj.get("async_transport"),
        )
    return CliConfig()


def _run_with_client(ctx: typer.Context, fn: Callable[[TSETMCClient], _T]) -> _T:
    cfg = _get_config(ctx)
    with cli_error_boundary():
        with create_client(
            timeout=cfg.timeout,
            proxy=cfg.proxy,
            transport=cfg.transport,
        ) as client:
            return fn(client)


def _jdate_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return gregorian_to_jalali(value)


def _client_type_to_dict(ct: ClientTypeLive | ClientTypeDaily) -> dict[str, Any]:
    data = ct.to_dict()
    if isinstance(ct, ClientTypeDaily):
        data["jdate"] = _jdate_or_none(ct.date)
    data["net_i_volume"] = ct.net_i_volume
    data["real_money_flow"] = ct.real_money_flow
    data["buy_per_capita"] = round(ct.buy_per_capita, 2)
    data["sell_per_capita"] = round(ct.sell_per_capita, 2)
    data["buyer_power"] = round(ct.buyer_power, 4)
    data["volume_buyer_power"] = round(ct.volume_buyer_power, 4)
    return data


def _compute_watch_flow(
    item: MarketWatchItem,
    ct: ClientTypeLive | None,
) -> tuple[int, int, float]:
    """Return ``(net_i_volume, real_money_flow, buyer_power)`` for a watch item."""
    if ct is None:
        return 0, 0, 0.0
    if ct.buy_i_value > 0 or ct.sell_i_value > 0:
        return ct.net_i_volume, ct.real_money_flow, round(ct.buyer_power, 4)

    # GetClientTypeAll omits Rial value fields; estimate Rial flow from VWAP or price.
    vwap = (item.value / item.volume) if (item.value > 0 and item.volume > 0) else 0.0
    unit_price = vwap if vwap > 0 else (item.close if item.close > 0 else item.last)
    est_flow = int(round(ct.net_i_volume * unit_price)) if unit_price > 0 else 0
    return ct.net_i_volume, est_flow, round(ct.volume_buyer_power, 4)


def _matches_sector(
    item_sector: str,
    target_codes: set[str],
    raw_sector: str,
) -> bool:
    code = item_sector.strip()
    if target_codes:
        return code in target_codes or (code.lstrip("0") or "0") in target_codes
    norm_code = code.lstrip("0") or "0"
    norm_target = raw_sector.lstrip("0") or "0"
    return code == raw_sector or norm_code == norm_target


def _parse_symbols_option(values: Sequence[str] | None) -> list[str] | None:
    if not values:
        return None
    parsed: list[str] = []
    for raw in values:
        for part in raw.split(","):
            cleaned = part.strip()
            if cleaned:
                parsed.append(cleaned)
    return parsed or None


def _is_local_sqlite_file(target: str) -> Path | None:
    raw = target.strip()
    if raw == ":memory:":
        return None
    if "://" in raw:
        scheme, rest = raw.split("://", 1)
        scheme_base = scheme.lower().split("+", 1)[0]
        if scheme_base != "sqlite" or not rest.startswith("/"):
            return None
        path_part = rest[1:].split("?", 1)[0].split("#", 1)[0]
        return None if not path_part or path_part == ":memory:" else Path(path_part)
    return Path(raw)


_REDACTED = "***"
_SENSITIVE_QUERY_KEYS = ("pass", "pwd", "secret", "token", "key", "user", "auth", "cred")


def _sanitize_db_target(db: str) -> str:
    """Return a display-safe DB target with URI credentials, query string, and fragment removed.

    ``postgresql+psycopg://user:pass@host:5432/db?sslmode=require`` becomes
    ``postgresql+psycopg://host:5432/db``. Plain local paths and ``:memory:`` are returned unchanged.
    """
    raw = str(db).strip()
    if "://" not in raw:
        return raw

    scheme = raw.split("://", 1)[0]
    try:
        from sqlalchemy.engine import make_url

        url = make_url(raw)
    except Exception:
        url = None

    if url is not None:
        host = url.host or ""
        if ":" in host:
            host = f"[{host}]"
        port = f":{url.port}" if url.port is not None else ""
        database = f"/{url.database}" if url.database is not None else ""
        return f"{url.drivername}://{host}{port}{database}"

    # Fallback for URIs SQLAlchemy cannot parse: drop everything up to the last '@'
    # (userinfo may itself contain '/', '?', or ':'), then the query string and fragment.
    rest = raw.split("://", 1)[1]
    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]
    rest = rest.split("#", 1)[0].split("?", 1)[0]
    return f"{scheme}://{rest}"


def _db_secrets(db: str) -> list[str]:
    """Collect credential fragments (userinfo, username, password) embedded in a DB URI."""
    raw = str(db).strip()
    if "://" not in raw:
        return []

    secrets: set[str] = set()
    rest = raw.split("://", 1)[1]
    if "@" in rest:
        userinfo = rest.rsplit("@", 1)[0]
        secrets.add(userinfo)
        user, _, password = userinfo.partition(":")
        secrets.update({user, password, unquote(user), unquote(password)})

    try:
        parts = urlsplit(raw)
        secrets.update({parts.username or "", parts.password or ""})
        if parts.query:
            secrets.add(parts.query)
    except ValueError:
        pass

    try:
        from sqlalchemy.engine import make_url

        url = make_url(raw)
        secrets.update({url.username or "", url.password or ""})
        for key, value in url.query.items():
            if not any(token in key.lower() for token in _SENSITIVE_QUERY_KEYS):
                continue
            values = value if isinstance(value, tuple) else (value,)
            secrets.update(str(v) for v in values)
    except Exception:
        pass

    return sorted((s for s in secrets if s), key=len, reverse=True)


def _redact_db_message(message: str, db: str) -> str:
    """Replace the raw DB target and any embedded credentials in ``message``."""
    raw = str(db).strip()
    safe = _sanitize_db_target(raw)
    text = message
    if raw and raw != safe:
        text = text.replace(raw, safe)
    for secret in _db_secrets(raw):
        if re.fullmatch(r"[\w.-]+", secret):
            text = re.sub(rf"(?<![\w]){re.escape(secret)}(?![\w])", _REDACTED, text)
        else:
            text = text.replace(secret, _REDACTED)
    return text


@contextmanager
def _db_error_boundary(db: str) -> Iterator[None]:
    """Like ``cli_error_boundary`` but scrubs DB credentials from error messages."""
    try:
        yield
    except (TehranStocksError, ValueError) as exc:
        print_error(_redact_db_message(str(exc), db), label=type(exc).__name__)
        raise typer.Exit(code=exit_code_for_error(exc)) from None


def _open_cli_store(
    db: str,
    *,
    backend: str | None = None,
    init_schema: bool = False,
    require_exists: bool = False,
) -> Any:
    try:
        from tehran_stocks.storage import open_store  # type: ignore[import-not-found]
    except ImportError as exc:
        raise StorageError(
            "Local storage module (tehran_stocks.storage) is not available."
        ) from exc

    if require_exists:
        local_path = _is_local_sqlite_file(db)
        if local_path is not None and not local_path.exists():
            raise StorageError(
                f"Database file not found: {local_path}. "
                f"Run 'tse db init --db {_sanitize_db_target(db)}' first."
            )

    return open_store(db, backend=backend, init_schema=init_schema)


app = typer.Typer(
    name="tse",
    no_args_is_help=True,
    help="Modern, on-demand CLI for the Tehran Stock Exchange (TSETMC).",
)
db_app = typer.Typer(
    name="db",
    no_args_is_help=True,
    help="Initialize, sync, inspect, and query an opt-in local database.",
)
app.add_typer(db_app, name="db")


def _load_skill_app() -> typer.Typer:
    try:
        from tehran_stocks.cli import skills_cmd  # type: ignore[import-not-found]
    except ImportError:
        placeholder = typer.Typer(
            name="skill",
            no_args_is_help=True,
            help="Inspect and install bundled tehran-stocks Agent Skills.",
        )

        @placeholder.command("list")
        def _skill_list_placeholder() -> None:
            """List bundled Agent Skills."""
            fail_with_error(
                TehranStocksError(
                    "Agent skills installer is not available in this build."
                )
            )

        return placeholder

    candidate = getattr(skills_cmd, "app", None) or getattr(skills_cmd, "skill_app", None)
    if isinstance(candidate, typer.Typer):
        return candidate
    raise RuntimeError("tehran_stocks.cli.skills_cmd must expose 'app' or 'skill_app'")


skill_app = _load_skill_app()
app.add_typer(skill_app, name="skill")


def _version_callback(value: bool) -> None:
    if value:
        from tehran_stocks import __version__

        typer.echo(f"tehran-stocks {__version__}")
        raise typer.Exit()


@app.callback()
def cli_callback(
    ctx: typer.Context,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            envvar="TEHRAN_STOCKS_TIMEOUT",
            help="HTTP request timeout in seconds.",
        ),
    ] = DEFAULT_TIMEOUT,
    proxy: Annotated[
        str | None,
        typer.Option(
            "--proxy",
            envvar="TEHRAN_STOCKS_PROXY",
            help="HTTP/SOCKS proxy URL.",
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show package version and exit.",
        ),
    ] = False,
) -> None:
    """Configure shared client options across commands."""
    with cli_error_boundary():
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("--timeout must be a positive finite number.")
    existing = _get_config(ctx)
    ctx.obj = CliConfig(
        timeout=timeout,
        proxy=proxy if proxy is not None else existing.proxy,
        transport=existing.transport,
        async_transport=existing.async_transport,
    )


@app.command("search")
def search_cmd(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Symbol, Persian/Arabic name, or ISIN to search.")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max results (0 for all).")] = 20,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Search instruments on TSETMC by symbol, name, or ISIN."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    results = _run_with_client(ctx, lambda c: c.instruments.search(query))
    if limit > 0:
        results = results[:limit]
    rows = [item.to_dict() for item in results]
    columns = [
        ColumnSpec("symbol", "Symbol", no_wrap=True),
        ColumnSpec("name", "Name"),
        ColumnSpec("ins_code", "insCode", no_wrap=True),
        ColumnSpec("market", "Market"),
        ColumnSpec("isin", "ISIN", no_wrap=True),
        ColumnSpec("sector_name", "Sector"),
    ]
    output_records(
        rows,
        fmt=resolved_fmt,
        columns=columns,
        title=f"Search: {query}",
        empty_message=f"No instruments found matching {query!r}.",
    )


@app.command("quote")
def quote_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch the live or latest closing quote snapshot for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    q = _run_with_client(ctx, lambda c: c.prices.quote(symbol))
    record = q.to_dict()
    record["jdate"] = _jdate_or_none(q.date)
    formatters = {
        "last": fmt_number,
        "close": fmt_number,
        "open": fmt_number,
        "high": fmt_number,
        "low": fmt_number,
        "yesterday": fmt_number,
        "change": fmt_number,
        "change_pct": fmt_pct,
        "volume": fmt_int,
        "value": fmt_int,
        "trade_count": fmt_int,
        "price_min_allowed": fmt_number,
        "price_max_allowed": fmt_number,
    }
    output_record(
        record,
        fmt=resolved_fmt,
        title=f"Quote: {symbol} ({q.ins_code})",
        formatters=formatters,
    )


@app.command("history")
def history_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", min=0, help="Recent trading days (0 for full history)."),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option("--start", help="Start date (YYYY-MM-DD, YYYYMMDD, or Jalali YYYY-MM-DD)."),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", help="End date (YYYY-MM-DD, YYYYMMDD, or Jalali YYYY-MM-DD)."),
    ] = None,
    adjusted: Annotated[
        bool,
        typer.Option("--adjusted", help="Apply backward corporate-action price adjustment."),
    ] = False,
    jalali: Annotated[
        bool,
        typer.Option("--jalali/--no-jalali", help="Include Jalali date column."),
    ] = True,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch chronological daily OHLCV history for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    effective_days = days if days is not None else (0 if (start or end) else 30)
    bars = _run_with_client(
        ctx,
        lambda c: c.prices.history(
            symbol,
            days=effective_days,
            start=start,
            end=end,
            adjusted=adjusted,
        ),
    )
    rows: list[dict[str, Any]] = []
    for bar in bars:
        row = bar.to_dict()
        if jalali:
            row["jdate"] = _jdate_or_none(bar.date)
        row["change"] = round(bar.change, 4)
        row["change_pct"] = round(bar.change_pct, 4)
        rows.append(row)

    columns: list[ColumnSpec] = []
    if jalali:
        columns.append(ColumnSpec("jdate", "JDate"))
    columns.extend(
        [
            ColumnSpec("date", "Date"),
            ColumnSpec("open", "Open", justify="right", formatter=fmt_number),
            ColumnSpec("high", "High", justify="right", formatter=fmt_number),
            ColumnSpec("low", "Low", justify="right", formatter=fmt_number),
            ColumnSpec("close", "Close", justify="right", formatter=fmt_number),
            ColumnSpec("last", "Last", justify="right", formatter=fmt_number),
            ColumnSpec("change_pct", "Chg %", justify="right", formatter=fmt_pct),
            ColumnSpec("volume", "Volume", justify="right", formatter=fmt_int),
            ColumnSpec("value", "Value", justify="right", formatter=fmt_int),
        ]
    )
    title = f"History: {symbol}" + (" (Adjusted)" if adjusted else "")
    output_records(rows, fmt=resolved_fmt, columns=columns, title=title)


@app.command("client-type")
def client_type_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    history: Annotated[
        bool,
        typer.Option("--history", help="Show historical daily client-type flow."),
    ] = False,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", min=0, help="Limit historical days (implies --history)."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch individual (حقیقی) vs. institutional (حقوقی) flow and buyer power."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    if history or days is not None:
        records = _run_with_client(ctx, lambda c: c.client_type.history(symbol, days=days))
        rows = [_client_type_to_dict(rec) for rec in records]
        columns = [
            ColumnSpec("jdate", "JDate"),
            ColumnSpec("date", "Date"),
            ColumnSpec("buy_i_volume", "Ind Buy Vol", justify="right", formatter=fmt_int),
            ColumnSpec("sell_i_volume", "Ind Sell Vol", justify="right", formatter=fmt_int),
            ColumnSpec("net_i_volume", "Net Ind Vol", justify="right", formatter=fmt_int),
            ColumnSpec("real_money_flow", "Real Money Flow", justify="right", formatter=fmt_int),
            ColumnSpec("buyer_power", "Buyer Power", justify="right", formatter=fmt_float),
            ColumnSpec("buy_i_count", "Ind Buyers", justify="right", formatter=fmt_int),
            ColumnSpec("sell_i_count", "Ind Sellers", justify="right", formatter=fmt_int),
        ]
        output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Client Type History: {symbol}")
        return

    live = _run_with_client(ctx, lambda c: c.client_type.live(symbol))
    record = _client_type_to_dict(live)
    formatters = {
        key: fmt_int
        for key in (
            "buy_i_volume",
            "buy_n_volume",
            "sell_i_volume",
            "sell_n_volume",
            "buy_i_count",
            "buy_n_count",
            "sell_i_count",
            "sell_n_count",
            "buy_i_value",
            "buy_n_value",
            "sell_i_value",
            "sell_n_value",
            "net_i_volume",
            "real_money_flow",
        )
    }
    formatters["buy_per_capita"] = fmt_number
    formatters["sell_per_capita"] = fmt_number
    formatters["buyer_power"] = fmt_float
    formatters["volume_buyer_power"] = fmt_float
    output_record(record, fmt=resolved_fmt, title=f"Client Type: {symbol}", formatters=formatters)


@app.command("orderbook")
def orderbook_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    thresholds: Annotated[
        bool,
        typer.Option("--thresholds", help="Fetch static thresholds to detect buy/sell queues."),
    ] = False,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch the 5-level bid/ask limit order book for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    book = _run_with_client(
        ctx,
        lambda c: c.prices.order_book(symbol, include_thresholds=thresholds),
    )
    rows = [lvl.to_dict() for lvl in book.levels]
    full_payload = {
        **book.to_dict(),
        "total_bid_volume": book.total_bid_volume,
        "total_ask_volume": book.total_ask_volume,
        "spread": book.spread,
        "is_buy_queue": book.is_buy_queue,
        "is_sell_queue": book.is_sell_queue,
    }
    columns = [
        ColumnSpec("row", "Lvl", justify="right"),
        ColumnSpec("bid_count", "Bid #", justify="right", formatter=fmt_int),
        ColumnSpec("bid_volume", "Bid Vol", justify="right", formatter=fmt_int),
        ColumnSpec("bid_price", "Bid Price", justify="right", formatter=fmt_number),
        ColumnSpec("ask_price", "Ask Price", justify="right", formatter=fmt_number),
        ColumnSpec("ask_volume", "Ask Vol", justify="right", formatter=fmt_int),
        ColumnSpec("ask_count", "Ask #", justify="right", formatter=fmt_int),
    ]
    queue_label = "Buy Queue" if book.is_buy_queue else ("Sell Queue" if book.is_sell_queue else "Normal")
    spread_label = fmt_number(book.spread) if book.spread is not None else "-"
    caption = (
        f"Spread: {spread_label} | Bid Vol: {book.total_bid_volume:,} | "
        f"Ask Vol: {book.total_ask_volume:,} | Status: {queue_label}"
    )
    output_records(
        rows,
        fmt=resolved_fmt,
        columns=columns,
        title=f"Order Book: {symbol} ({book.ins_code})",
        caption=caption,
        json_data=full_payload,
    )


@app.command("info")
def info_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    stats: Annotated[
        bool,
        typer.Option("--stats", help="Include TSETMC computed statistics."),
    ] = False,
    identity: Annotated[
        bool,
        typer.Option("--identity", help="Include legal and sub-sector identity fields."),
    ] = False,
    etf: Annotated[
        bool,
        typer.Option("--etf", help="Include ETF redemption/subscription NAV details."),
    ] = False,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch instrument fundamentals, EPS, sector P/E, thresholds, and stats."""
    resolved_fmt = resolve_output_format(fmt, as_json)

    def _fetch(client: TSETMCClient) -> dict[str, Any]:
        info_obj = client.instruments.info(symbol)
        payload: dict[str, Any] = {"info": info_obj.to_dict()}
        if identity:
            payload["identity"] = client.instruments.identity(symbol).to_dict()
        if etf:
            etf_obj = client.funds.etf(symbol)
            payload["etf"] = {
                **etf_obj.to_dict(),
                "nav_premium_pct": etf_obj.nav_premium_pct,
            }
        if stats:
            payload["statistics"] = [s.to_dict() for s in client.instruments.statistics(symbol)]
        return payload

    data = _run_with_client(ctx, _fetch)
    info_dict = dict(data["info"])
    if "identity" in data:
        for k in ("latin_symbol", "latin_name", "company_code", "sub_sector_code", "sub_sector_name", "market_code", "board_code"):
            info_dict[k] = data["identity"].get(k)
    if "etf" in data:
        for k in ("redemption_nav", "subscription_nav", "statistical_nav", "nav_premium_pct"):
            info_dict[k] = data["etf"].get(k)

    if resolved_fmt is OutputFormat.JSON:
        if stats or identity or etf:
            emit_json(data if stats else info_dict)
        else:
            emit_json(info_dict)
        return

    if stats:
        stat_rows = data.get("statistics", [])
        if resolved_fmt is OutputFormat.TABLE:
            output_record(info_dict, fmt=OutputFormat.TABLE, title=f"Instrument Info: {symbol}")
        stat_cols = [
            ColumnSpec("data_type", "ID", justify="right"),
            ColumnSpec("name", "Metric"),
            ColumnSpec("value", "Value", justify="right", formatter=fmt_number),
            ColumnSpec("date", "Date"),
        ]
        output_records(
            stat_rows,
            fmt=resolved_fmt,
            columns=stat_cols,
            title=f"Statistics: {symbol}",
        )
        return

    formatters = {
        "total_shares": fmt_int,
        "base_volume": fmt_int,
        "eps": fmt_number,
        "sector_pe": fmt_float,
        "psr": fmt_float,
        "price_min_allowed": fmt_number,
        "price_max_allowed": fmt_number,
        "week_min": fmt_number,
        "week_max": fmt_number,
        "year_min": fmt_number,
        "year_max": fmt_number,
        "nav": fmt_number,
        "redemption_nav": fmt_number,
        "subscription_nav": fmt_number,
        "statistical_nav": fmt_number,
    }
    output_record(info_dict, fmt=resolved_fmt, title=f"Instrument Info: {symbol}", formatters=formatters)


@app.command("shareholders")
def shareholders_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch major shareholders (>1% ownership) for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    items = _run_with_client(ctx, lambda c: c.disclosures.shareholders(symbol))
    rows = [item.to_dict() for item in items]
    columns = [
        ColumnSpec("shareholder_id", "ID", justify="right"),
        ColumnSpec("name", "Shareholder"),
        ColumnSpec("shares", "Shares", justify="right", formatter=fmt_int),
        ColumnSpec("percent", "%", justify="right", formatter=lambda v: fmt_pct(v, signed=False)),
        ColumnSpec("change", "Change", justify="right", formatter=fmt_int),
        ColumnSpec("date", "Date"),
    ]
    output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Shareholders: {symbol}")


@app.command("dividends")
def dividends_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    share_changes: Annotated[
        bool,
        typer.Option("--share-changes", help="Also include historical share count changes."),
    ] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max rows (0 for all).")] = 20,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch corporate-action price adjustments (dividends / splits) and share changes."""
    resolved_fmt = resolve_output_format(fmt, as_json)

    def _fetch(client: TSETMCClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        adjs = list(reversed(client.prices.adjustments(symbol)))
        if limit > 0:
            adjs = adjs[:limit]
        adj_rows = [
            {
                **adj.to_dict(),
                "jdate": _jdate_or_none(adj.date),
                "ratio": round(adj.ratio, 6),
            }
            for adj in adjs
        ]
        sc_rows: list[dict[str, Any]] = []
        if share_changes:
            changes = client.instruments.share_changes(symbol)
            if limit > 0:
                changes = changes[:limit]
            sc_rows = [
                {
                    **sc.to_dict(),
                    "jdate": _jdate_or_none(sc.date),
                    "change": sc.change,
                    "ratio": round(sc.ratio, 6),
                }
                for sc in changes
            ]
        return adj_rows, sc_rows

    adj_rows, sc_rows = _run_with_client(ctx, _fetch)
    if resolved_fmt is OutputFormat.JSON:
        if share_changes:
            emit_json({"adjustments": adj_rows, "share_changes": sc_rows})
        else:
            emit_json(adj_rows)
        return

    adj_cols = [
        ColumnSpec("jdate", "JDate"),
        ColumnSpec("date", "Date"),
        ColumnSpec("adjusted_close", "Adj Close", justify="right", formatter=fmt_number),
        ColumnSpec("unadjusted_close", "Raw Close", justify="right", formatter=fmt_number),
        ColumnSpec("ratio", "Ratio", justify="right", formatter=lambda v: fmt_float(v, 4)),
        ColumnSpec("corporate_type_code", "Type"),
    ]
    output_records(adj_rows, fmt=resolved_fmt, columns=adj_cols, title=f"Price Adjustments: {symbol}")

    if share_changes and resolved_fmt is OutputFormat.TABLE:
        sc_cols = [
            ColumnSpec("jdate", "JDate"),
            ColumnSpec("date", "Date"),
            ColumnSpec("old_shares", "Old Shares", justify="right", formatter=fmt_int),
            ColumnSpec("new_shares", "New Shares", justify="right", formatter=fmt_int),
            ColumnSpec("change", "Delta", justify="right", formatter=fmt_int),
            ColumnSpec("ratio", "Ratio", justify="right", formatter=lambda v: fmt_float(v, 4)),
        ]
        output_records(sc_rows, fmt=resolved_fmt, columns=sc_cols, title=f"Share Changes: {symbol}")


@app.command("market")
def market_cmd(
    ctx: typer.Context,
    flow: Annotated[int, typer.Option("--flow", help="Market flow: 1=TSE, 2=Farabourse.")] = 1,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch live market overview (TEDPIX, equal-weighted index, market totals)."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    overview = _run_with_client(ctx, lambda c: c.market.overview(flow=flow))
    record = overview.to_dict()
    record["jdate"] = _jdate_or_none(overview.date)
    formatters = {
        "index_value": fmt_float,
        "index_change": fmt_float,
        "equal_weighted_index": fmt_float,
        "equal_weighted_change": fmt_float,
        "market_value": fmt_number,
        "trade_value": fmt_int,
        "trade_volume": fmt_int,
        "trade_count": fmt_int,
    }
    output_record(
        record,
        fmt=resolved_fmt,
        title=f"Market Overview (flow={flow})",
        formatters=formatters,
    )


@app.command("sectors")
def sectors_cmd(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max sectors (0 for all).")] = 0,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch TSE industrial sector definitions and live summary metrics."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    items = _run_with_client(ctx, lambda c: c.market.sectors())
    if limit > 0:
        items = items[:limit]
    rows = [item.to_dict() for item in items]
    columns = [
        ColumnSpec("code", "Code"),
        ColumnSpec("name", "Sector"),
        ColumnSpec("trade_value", "Trade Value", justify="right", formatter=fmt_int),
        ColumnSpec("trade_volume", "Trade Vol", justify="right", formatter=fmt_int),
        ColumnSpec("trade_count", "Trades", justify="right", formatter=fmt_int),
        ColumnSpec("market_cap", "Market Cap", justify="right", formatter=fmt_number),
    ]
    output_records(rows, fmt=resolved_fmt, columns=columns, title="TSE Industrial Sectors")


@app.command("indices")
def indices_cmd(
    ctx: typer.Context,
    flow: Annotated[int, typer.Option("--flow", help="Market flow: 1=TSE, 2=Farabourse.")] = 1,
    history: Annotated[
        str | None,
        typer.Option("--history", help="Fetch daily history for index insCode or 'TEDPIX'."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max rows (0 for all).")] = 0,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch all live market/industry indices or daily history for a specific index."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    if history:
        bars = _run_with_client(ctx, lambda c: c.market.index_history(history))
        if limit > 0:
            bars = bars[-limit:]
        rows = [{**bar.to_dict(), "jdate": _jdate_or_none(bar.date)} for bar in bars]
        columns = [
            ColumnSpec("jdate", "JDate"),
            ColumnSpec("date", "Date"),
            ColumnSpec("value", "Value", justify="right", formatter=fmt_float),
            ColumnSpec("high", "High", justify="right", formatter=fmt_float),
            ColumnSpec("low", "Low", justify="right", formatter=fmt_float),
        ]
        output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Index History: {history}")
        return

    items = _run_with_client(ctx, lambda c: c.market.indices(flow=flow))
    if limit > 0:
        items = items[:limit]
    rows = [{**item.to_dict(), "jdate": _jdate_or_none(item.date)} for item in items]
    columns = [
        ColumnSpec("ins_code", "insCode"),
        ColumnSpec("name", "Index"),
        ColumnSpec("value", "Value", justify="right", formatter=fmt_float),
        ColumnSpec("change", "Change", justify="right", formatter=fmt_float),
        ColumnSpec("change_pct", "Chg %", justify="right", formatter=fmt_pct),
        ColumnSpec("high", "High", justify="right", formatter=fmt_float),
        ColumnSpec("low", "Low", justify="right", formatter=fmt_float),
        ColumnSpec("time", "Time"),
    ]
    output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Indices (flow={flow})")


@app.command("codal")
def codal_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max announcements.")] = 10,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch recent Codal corporate disclosures and filings for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    items = _run_with_client(ctx, lambda c: c.disclosures.codal(symbol, limit=limit))
    rows = [{**item.to_dict(), "jdate": _jdate_or_none(item.date)} for item in items]
    columns = [
        ColumnSpec("tracing_no", "Tracing"),
        ColumnSpec("jdate", "JDate"),
        ColumnSpec("date", "Date"),
        ColumnSpec("symbol", "Symbol"),
        ColumnSpec("title", "Title"),
        ColumnSpec("has_pdf", "PDF"),
        ColumnSpec("has_excel", "Excel"),
    ]
    output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Codal Filings: {symbol}")


@app.command("messages")
def messages_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Ticker symbol, ISIN, or numeric insCode.")],
    limit: Annotated[int | None, typer.Option("--limit", "-n", min=0, help="Max messages.")] = 10,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Fetch market supervisor messages (halts, reopenings, AGMs) for an instrument."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    items = _run_with_client(ctx, lambda c: c.disclosures.messages(symbol, limit=limit))
    rows = [{**item.to_dict(), "jdate": _jdate_or_none(item.date)} for item in items]
    columns = [
        ColumnSpec("msg_id", "Msg ID"),
        ColumnSpec("jdate", "JDate"),
        ColumnSpec("date", "Date"),
        ColumnSpec("time", "Time"),
        ColumnSpec("title", "Title"),
    ]
    output_records(rows, fmt=resolved_fmt, columns=columns, title=f"Supervisor Messages: {symbol}")


@app.command("screen")
def screen_cmd(
    ctx: typer.Context,
    sector: Annotated[
        str | None,
        typer.Option("--sector", help="Filter by sector code (e.g. '13', '68') or sector name."),
    ] = None,
    sort: Annotated[
        ScreenSort,
        typer.Option(
            "--sort",
            case_sensitive=False,
            help="Sort metric: value, volume, change, money_flow, or buyer_power.",
        ),
    ] = ScreenSort.VALUE,
    limit: Annotated[int, typer.Option("--limit", "-n", min=0, help="Max rows (0 for all).")] = 20,
    with_flow: Annotated[
        bool,
        typer.Option("--with-flow", help="Always join live individual/institutional flow columns."),
    ] = False,
    asc: Annotated[
        bool,
        typer.Option("--asc", help="Sort ascending instead of descending."),
    ] = False,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Screen live full-market watch instruments by value, volume, change, or flow."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    needs_flow = with_flow or sort in (ScreenSort.MONEY_FLOW, ScreenSort.BUYER_POWER)

    def _run_screen(client: TSETMCClient) -> list[dict[str, Any]]:
        watch_items = client.market.watch()
        flow_by_code: dict[str, ClientTypeLive] = {}
        if needs_flow:
            flow_by_code = {rec.ins_code: rec for rec in client.client_type.all()}

        if sector is not None:
            cleaned_sector = normalize_persian(sector).strip()
            if cleaned_sector:
                target_codes: set[str] = set()
                if not cleaned_sector.isdigit():
                    sectors_list = client.market.sectors()
                    target_codes = {
                        (s.code.strip().lstrip("0") or "0")
                        for s in sectors_list
                        if cleaned_sector in normalize_persian(s.name)
                    }
                    if not target_codes:
                        return []
                watch_items = [
                    item
                    for item in watch_items
                    if _matches_sector(item.sector_code, target_codes, cleaned_sector)
                ]

        enriched: list[dict[str, Any]] = []
        for item in watch_items:
            row: dict[str, Any] = {
                "ins_code": item.ins_code,
                "symbol": item.symbol,
                "name": item.name,
                "sector_code": item.sector_code,
                "last": item.last,
                "close": item.close,
                "yesterday": item.yesterday,
                "change": round(item.change, 4),
                "change_pct": round(item.change_pct, 4),
                "volume": item.volume,
                "value": item.value,
                "trade_count": item.trade_count,
                "eps": item.eps,
                "pe": item.pe,
            }
            if needs_flow:
                net_i_vol, real_flow, buyer_pwr = _compute_watch_flow(
                    item,
                    flow_by_code.get(item.ins_code),
                )
                row["net_i_volume"] = net_i_vol
                row["real_money_flow"] = real_flow
                row["buyer_power"] = buyer_pwr
            enriched.append(row)

        sort_keys: dict[ScreenSort, Callable[[dict[str, Any]], Any]] = {
            ScreenSort.VALUE: lambda r: (r["value"], r["volume"]),
            ScreenSort.VOLUME: lambda r: (r["volume"], r["value"]),
            ScreenSort.CHANGE: lambda r: (r["change_pct"], r["change"]),
            ScreenSort.MONEY_FLOW: lambda r: (r["real_money_flow"], r["value"]),
            ScreenSort.BUYER_POWER: lambda r: (r["buyer_power"], r["real_money_flow"]),
        }
        enriched.sort(key=sort_keys[sort], reverse=not asc)
        return enriched[:limit] if limit > 0 else enriched

    rows = _run_with_client(ctx, _run_screen)
    columns = [
        ColumnSpec("symbol", "Symbol"),
        ColumnSpec("name", "Name"),
        ColumnSpec("sector_code", "Sector"),
        ColumnSpec("last", "Last", justify="right", formatter=fmt_number),
        ColumnSpec("close", "Close", justify="right", formatter=fmt_number),
        ColumnSpec("change_pct", "Chg %", justify="right", formatter=fmt_pct),
        ColumnSpec("volume", "Volume", justify="right", formatter=fmt_int),
        ColumnSpec("value", "Value", justify="right", formatter=fmt_int),
    ]
    if needs_flow:
        columns.extend(
            [
                ColumnSpec("real_money_flow", "Money Flow", justify="right", formatter=fmt_int),
                ColumnSpec("buyer_power", "Buyer Power", justify="right", formatter=fmt_float),
            ]
        )
    output_records(
        rows,
        fmt=resolved_fmt,
        columns=columns,
        title=f"Market Screen (sort={sort.value})",
    )


@db_app.command("init")
def db_init_cmd(
    db: DbOption,
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="Storage backend override: sqlite or sqlalchemy."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Initialize schema in a SQLite file or SQLAlchemy database URI."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    with _db_error_boundary(db):
        store = _open_cli_store(db, backend=backend, init_schema=False)
        try:
            store.init_schema()
            payload = {"status": "initialized", "db": _sanitize_db_target(db), **store.stats()}
        finally:
            store.close()
    output_record(payload, fmt=resolved_fmt, title="Database Initialized")


@db_app.command("sync")
def db_sync_cmd(
    ctx: typer.Context,
    db: DbOption,
    symbols: Annotated[
        list[str] | None,
        typer.Option("--symbols", "-s", help="Symbols/insCodes to sync (comma-separated or repeated)."),
    ] = None,
    sector: Annotated[
        str | None,
        typer.Option("--sector", help="Sync instruments belonging to sector code."),
    ] = None,
    sync_all: Annotated[
        bool,
        typer.Option("--all", help="Sync all instruments from TSETMC MarketWatch."),
    ] = False,
    client_type: Annotated[
        bool,
        typer.Option(
            "--client-type/--no-client-type",
            help="Include historical individual/institutional (حقیقی/حقوقی) flows.",
        ),
    ] = False,
    incremental: Annotated[
        bool,
        typer.Option("--incremental/--full", help="Only fetch bars newer than the latest stored date."),
    ] = True,
    share_changes: Annotated[
        bool,
        typer.Option("--share-changes", help="Also sync historical share count changes."),
    ] = False,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", min=1, help="Max concurrent async HTTP requests."),
    ] = 8,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="Abort immediately on first symbol error."),
    ] = False,
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="Storage backend override: sqlite or sqlalchemy."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Sync instruments, sectors, prices, and optional client-type history into a local DB."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    parsed_symbols = _parse_symbols_option(symbols)
    cfg = _get_config(ctx)

    with _db_error_boundary(db):
        if sync_all and (parsed_symbols is not None or sector is not None):
            raise ValueError("Cannot combine --all with --symbols or --sector.")
        if parsed_symbols is not None and sector is not None:
            raise ValueError("Cannot combine --symbols with --sector.")

        try:
            from tehran_stocks.storage import SyncService  # type: ignore[import-not-found]
        except ImportError as exc:
            raise StorageError(
                "Local storage module (tehran_stocks.storage) is not available."
            ) from exc

        async_transport = cfg.async_transport
        if async_transport is None and _ASYNC_TRANSPORT_OVERRIDE is not None:
            async_transport = _ASYNC_TRANSPORT_OVERRIDE
        if async_transport is None and isinstance(cfg.transport, httpx2.AsyncBaseTransport):
            async_transport = cfg.transport
        if async_transport is None and isinstance(_TRANSPORT_OVERRIDE, httpx2.AsyncBaseTransport):
            async_transport = _TRANSPORT_OVERRIDE

        store = _open_cli_store(db, backend=backend, init_schema=True)
        try:
            service_kwargs: dict[str, Any] = {}
            if async_transport is not None:
                service_kwargs["transport"] = async_transport
            if cfg.timeout != DEFAULT_TIMEOUT:
                service_kwargs["timeout"] = cfg.timeout
            if cfg.proxy is not None:
                service_kwargs["proxy"] = cfg.proxy
            if concurrency != 8:
                service_kwargs["max_concurrency"] = concurrency

            service = SyncService(store=store, **service_kwargs)

            err_console = get_stderr_console()
            stage_tasks: dict[str, TaskID] = {}
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=err_console,
                auto_refresh=False,
                redirect_stdout=False,
                redirect_stderr=False,
                transient=False,
            ) as progress:

                def _on_progress(evt: Any) -> None:
                    stage = getattr(evt, "stage", "sync")
                    completed = int(getattr(evt, "completed", 0))
                    total = max(int(getattr(evt, "total", 1)), 1)
                    sym_label = getattr(evt, "symbol", "")
                    desc = f"Syncing {stage}" + (f" ({sym_label})" if sym_label else "")
                    task_id = stage_tasks.get(stage)
                    if task_id is None:
                        task_id = progress.add_task(desc, total=total)
                        stage_tasks[stage] = task_id
                    progress.update(
                        task_id,
                        completed=completed,
                        total=total,
                        description=desc,
                        refresh=True,
                    )

                result = service.sync_all(
                    symbols=parsed_symbols,
                    sector=sector,
                    all_instruments=(sync_all or (parsed_symbols is None and sector is None)),
                    incremental=incremental,
                    include_client_types=client_type,
                    include_share_changes=share_changes,
                    fail_fast=fail_fast,
                    on_progress=_on_progress,
                )

            errors = getattr(result, "errors", {}) or {}
            for err_symbol, err_msg in errors.items():
                print_error(
                    _redact_db_message(f"{err_symbol}: {err_msg}", db),
                    label="Sync warning",
                )

            summary = result.to_dict() if hasattr(result, "to_dict") else dict(result)
            summary["db"] = _sanitize_db_target(db)
            if isinstance(summary.get("errors"), Mapping):
                summary["errors"] = {
                    str(key): _redact_db_message(str(value), db)
                    for key, value in summary["errors"].items()
                }
        finally:
            store.close()

    formatters = {
        key: fmt_int
        for key in (
            "sectors",
            "instruments",
            "prices",
            "adjustments",
            "share_changes",
            "client_types",
            "synced_symbols",
            "skipped_symbols",
        )
    }
    title = "Database Sync Completed with Errors" if errors else "Database Sync Complete"
    output_record(summary, fmt=resolved_fmt, title=title, formatters=formatters)
    if errors:
        # Partial failures must not look like success to scripts/CI: summary is on stdout,
        # per-symbol warnings are on stderr, and the exit code is non-zero.
        raise typer.Exit(code=1)


@db_app.command("status")
def db_status_cmd(
    db: DbOption,
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="Storage backend override: sqlite or sqlalchemy."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Inspect table row counts, date coverage, and sync metadata."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    with _db_error_boundary(db):
        store = _open_cli_store(db, backend=backend, init_schema=False, require_exists=True)
        try:
            payload = {"db": _sanitize_db_target(db), **store.stats()}
        finally:
            store.close()
    formatters = {
        key: fmt_int
        for key in (
            "sectors",
            "instruments",
            "daily_prices",
            "client_types",
            "price_adjustments",
            "share_changes",
            "sync_meta",
        )
    }
    output_record(payload, fmt=resolved_fmt, title="Database Status", formatters=formatters)


@db_app.command("query")
def db_query_cmd(
    db: DbOption,
    sql: Annotated[str, typer.Argument(help="Read-only SQL SELECT/WITH query to execute.")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=0, help="Max displayed rows (0 for all returned)."),
    ] = 0,
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="Storage backend override: sqlite or sqlalchemy."),
    ] = None,
    fmt: FormatOption = OutputFormat.TABLE,
    as_json: JsonOption = False,
) -> None:
    """Execute a validated read-only SQL query against the local database."""
    resolved_fmt = resolve_output_format(fmt, as_json)
    with _db_error_boundary(db):
        store = _open_cli_store(db, backend=backend, init_schema=False, require_exists=True)
        try:
            rows = store.query_readonly(sql)
        finally:
            store.close()

    if limit > 0:
        rows = rows[:limit]
    columns = [ColumnSpec(key, key, formatter=fmt_text) for key in rows[0]] if rows else []
    output_records(
        rows,
        fmt=resolved_fmt,
        columns=columns,
        title="Query Results",
        empty_message="Query returned 0 rows.",
    )


@app.command("mcp")
def mcp_cmd(
    ctx: typer.Context,
    db: Annotated[
        str | None,
        typer.Option("--db", envvar="TEHRAN_STOCKS_DB", help="Optional SQLite path or SQLAlchemy DB URI."),
    ] = None,
    transport: Annotated[
        str,
        typer.Option("--transport", help="MCP transport: stdio or streamable-http."),
    ] = "stdio",
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", envvar="TEHRAN_STOCKS_TIMEOUT", help="HTTP timeout in seconds."),
    ] = None,
    proxy: Annotated[
        str | None,
        typer.Option("--proxy", envvar="TEHRAN_STOCKS_PROXY", help="HTTP/SOCKS proxy URL."),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host when using streamable-http transport."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Bind port when using streamable-http transport."),
    ] = 8000,
) -> None:
    """Launch the official tehran-stocks MCP server (stdio or streamable-http)."""
    cfg = _get_config(ctx)
    effective_timeout = timeout if timeout is not None else cfg.timeout
    effective_proxy = proxy if proxy is not None else cfg.proxy

    with cli_error_boundary():
        if not math.isfinite(effective_timeout) or effective_timeout <= 0:
            raise ValueError("--timeout must be a positive finite number.")
        try:
            mcp_server = importlib.import_module("tehran_stocks.mcp_server")
        except ImportError as exc:
            raise TehranStocksError(
                "MCP server module (tehran_stocks.mcp_server) is not available in this build."
            ) from exc

        run_srv = getattr(mcp_server, "run_server", None)
        if callable(run_srv):
            run_srv(
                db_path=db,
                transport=transport,
                timeout=effective_timeout,
                proxy=effective_proxy,
                host=host,
                port=port,
            )
            return

        create_srv = getattr(mcp_server, "create_server", None)
        if callable(create_srv):
            server = create_srv(
                db_path=db,
                timeout=effective_timeout,
                proxy=effective_proxy,
                transport=transport,
            )
            if transport in ("streamable-http", "sse"):
                server.run(transport=transport, host=host, port=port)
            else:
                server.run(transport=transport)
            return

        mcp_main = getattr(mcp_server, "main", None)
        if callable(mcp_main):
            mcp_main()
            return

        raise TehranStocksError("tehran_stocks.mcp_server has no runnable entrypoint.")


def main() -> None:
    """Console script entrypoint for ``tse`` and ``tehran-stocks``."""
    app()


__all__ = [
    "CliConfig",
    "OutputFormat",
    "ScreenSort",
    "app",
    "create_async_client",
    "create_client",
    "db_app",
    "main",
    "skill_app",
]
