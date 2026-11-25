"""Official mcp>=2.0 MCPServer tools and resources for Tehran Stock Exchange (TSETMC)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import importlib
import inspect
import json
import math
import os
from pathlib import Path
import re
from typing import Annotated, Any, Literal
from urllib.parse import unquote, urlsplit

import anyio.to_thread
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError, ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from tehran_stocks.client.base import AsyncTSETMCClient
from tehran_stocks.exceptions import (
    InstrumentNotFoundError,
    TSETMCError,
    TehranStocksError,
)
from tehran_stocks.types.client_type import ClientTypeDaily, ClientTypeLive
from tehran_stocks.types.market import MarketWatchItem
from tehran_stocks.types.price import OrderBook
from tehran_stocks.utils.jalali import gregorian_to_jalali
from tehran_stocks.utils.persian import normalize_persian

_DEFAULT_TIMEOUT = 20.0
_VALID_TRANSPORTS = frozenset({"stdio", "streamable-http"})

_READ_ONLY_REMOTE_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
_READ_ONLY_LOCAL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
_WRITE_LOCAL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

_SERVER_INSTRUCTIONS = (
    "Tools and resources for live and historical Tehran Stock Exchange (TSETMC) market data. "
    "Persian and Arabic character variants (ک/ك, ی/ي) are normalized automatically; tickers, ISINs, "
    "and 17-digit insCodes are all accepted. All prices and trade values are denominated in Iranian "
    "Rials (IRR; 1 Toman = 10 IRR). Distinguish last trade price (pDrCotVal) from official volume-"
    "weighted closing price (pClosing), and check supervisor messages when a symbol appears halted. "
    "When a local database is attached (--db / TEHRAN_STOCKS_DB), query_local_db enforces strict "
    "read-only SQL."
)


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """Resolved runtime configuration for the TSETMC MCP server."""

    db_path: str | None = None
    timeout: float = _DEFAULT_TIMEOUT
    proxy: str | None = None
    transport: Literal["stdio", "streamable-http"] | None = None
    client_transport: Any | None = None


def _parse_timeout_env(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid TEHRAN_STOCKS_TIMEOUT value: {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"TEHRAN_STOCKS_TIMEOUT must be > 0, got {raw!r}")
    return value


def resolve_server_config(
    db_path: str | Path | None = None,
    timeout: float | None = _DEFAULT_TIMEOUT,
    proxy: str | None = None,
    transport: Literal["stdio", "streamable-http"] | str | None = None,
    *,
    client_transport: Any | None = None,
) -> ServerConfig:
    """Resolve explicit parameters with ``TEHRAN_STOCKS_*`` environment fallbacks."""
    if db_path is not None:
        resolved_db = str(db_path).strip() or None
    else:
        resolved_db = os.environ.get("TEHRAN_STOCKS_DB", "").strip() or None

    env_timeout = os.environ.get("TEHRAN_STOCKS_TIMEOUT", "").strip()
    if timeout is None:
        resolved_timeout = _parse_timeout_env(env_timeout) if env_timeout else _DEFAULT_TIMEOUT
    elif timeout == _DEFAULT_TIMEOUT and env_timeout:
        resolved_timeout = _parse_timeout_env(env_timeout)
    else:
        resolved_timeout = float(timeout)

    if not math.isfinite(resolved_timeout) or resolved_timeout <= 0:
        raise ValueError(f"timeout must be a finite number > 0, got {resolved_timeout!r}")

    if proxy is not None:
        resolved_proxy = proxy.strip() or None
    else:
        resolved_proxy = os.environ.get("TEHRAN_STOCKS_PROXY", "").strip() or None

    resolved_transport: Literal["stdio", "streamable-http"] | None = None
    if transport is not None:
        cleaned_transport = str(transport).strip().lower()
        if cleaned_transport not in _VALID_TRANSPORTS:
            raise ValueError(
                f"Unsupported transport {transport!r}; expected 'stdio' or 'streamable-http'"
            )
        resolved_transport = cleaned_transport  # type: ignore[assignment]

    return ServerConfig(
        db_path=resolved_db,
        timeout=resolved_timeout,
        proxy=resolved_proxy,
        transport=resolved_transport,
        client_transport=client_transport,
    )


def _to_jsonable(value: Any) -> Any:
    """Recursively convert values into strict JSON-serializable Python primitives."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _to_jsonable(value.to_dict())
    return str(value)


def _safe_jdate(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return gregorian_to_jalali(value)


def _clean_symbol_or_query(value: str, label: str) -> str:
    cleaned = normalize_persian(value).strip()
    if not cleaned:
        raise ToolError(f"{label} must not be empty")
    return cleaned


def _is_optional_missing(exc: BaseException) -> bool:
    return isinstance(exc, InstrumentNotFoundError) or (
        isinstance(exc, TSETMCError) and exc.status_code == 404
    )


def _open_client(config: ServerConfig) -> AsyncTSETMCClient:
    return AsyncTSETMCClient(
        timeout=config.timeout,
        proxy=config.proxy,
        transport=config.client_transport,
    )


def _serialize_client_type(ct: ClientTypeLive | ClientTypeDaily) -> dict[str, Any]:
    payload = _to_jsonable(ct.to_dict())
    payload["net_i_volume"] = ct.net_i_volume
    payload["real_money_flow"] = ct.real_money_flow
    payload["buy_per_capita"] = round(ct.buy_per_capita, 2)
    payload["sell_per_capita"] = round(ct.sell_per_capita, 2)
    payload["buyer_power"] = round(ct.buyer_power, 4)
    payload["volume_buyer_power"] = round(ct.volume_buyer_power, 4)
    if isinstance(ct, ClientTypeDaily):
        payload["jdate"] = _safe_jdate(ct.date)
    return payload


def _serialize_order_book(book: OrderBook) -> dict[str, Any]:
    best = book.best_level
    queue_value: int | None = None
    if book.is_buy_queue and best is not None:
        queue_value = int(round(best.bid_price * best.bid_volume))
    elif book.is_sell_queue and best is not None:
        queue_value = int(round(best.ask_price * best.ask_volume))

    return {
        "ins_code": book.ins_code,
        "currency": "IRR",
        "price_max_allowed": _to_jsonable(book.price_max_allowed),
        "price_min_allowed": _to_jsonable(book.price_min_allowed),
        "best_bid": _to_jsonable(best.to_dict()) if best is not None else None,
        "spread": _to_jsonable(book.spread),
        "total_bid_volume": book.total_bid_volume,
        "total_ask_volume": book.total_ask_volume,
        "is_buy_queue": book.is_buy_queue,
        "is_sell_queue": book.is_sell_queue,
        "queue_value_irr": queue_value,
        "levels": [_to_jsonable(level.to_dict()) for level in book.levels],
    }


async def _build_snapshot_payload(
    client: AsyncTSETMCClient,
    symbol: str,
    *,
    include_order_book: bool = True,
    include_client_type: bool = True,
) -> dict[str, Any]:
    ins_code = await client.resolve(symbol)

    tasks: dict[str, Any] = {
        "quote": client.prices.quote(ins_code),
        "info": client.instruments.info(ins_code),
    }
    if include_order_book:
        tasks["order_book"] = client.prices.order_book(ins_code, include_thresholds=False)
    if include_client_type:
        tasks["client_type"] = client.client_type.live(ins_code)

    keys = list(tasks.keys())
    results = await asyncio.gather(*(tasks[k] for k in keys), return_exceptions=True)
    resolved = dict(zip(keys, results, strict=True))

    quote_res = resolved["quote"]
    if isinstance(quote_res, BaseException):
        raise quote_res

    info_res = resolved["info"]
    if isinstance(info_res, BaseException):
        if _is_optional_missing(info_res):
            info_obj = None
        else:
            raise info_res
    else:
        info_obj = info_res

    book_payload: dict[str, Any] | None = None
    if include_order_book:
        book_res = resolved["order_book"]
        if isinstance(book_res, BaseException):
            if not _is_optional_missing(book_res):
                raise book_res
        else:
            p_max = info_obj.price_max_allowed if info_obj is not None else quote_res.price_max_allowed
            p_min = info_obj.price_min_allowed if info_obj is not None else quote_res.price_min_allowed
            enriched_book = OrderBook(
                ins_code=book_res.ins_code,
                levels=book_res.levels,
                price_max_allowed=p_max,
                price_min_allowed=p_min,
            )
            book_payload = _serialize_order_book(enriched_book)

    ct_payload: dict[str, Any] | None = None
    if include_client_type:
        ct_res = resolved["client_type"]
        if isinstance(ct_res, BaseException):
            if not _is_optional_missing(ct_res):
                raise ct_res
        else:
            ct_payload = _serialize_client_type(ct_res)

    pe_ratio: float | None = None
    market_cap_irr: int | None = None
    if info_obj is not None:
        if info_obj.eps is not None and info_obj.eps > 0 and quote_res.close > 0:
            pe_ratio = round(quote_res.close / info_obj.eps, 2)
        if info_obj.total_shares > 0 and quote_res.close > 0:
            market_cap_irr = int(round(quote_res.close * info_obj.total_shares))

    quote_dict = _to_jsonable(quote_res.to_dict())
    quote_dict["jdate"] = _safe_jdate(quote_res.date)

    return {
        "symbol": info_obj.symbol if info_obj and info_obj.symbol else normalize_persian(str(symbol)),
        "name": info_obj.name if info_obj is not None else "",
        "ins_code": ins_code,
        "isin": info_obj.isin if info_obj is not None else "",
        "market": info_obj.market if info_obj is not None else "",
        "sector_code": info_obj.sector_code if info_obj is not None else "",
        "sector_name": info_obj.sector_name if info_obj is not None else "",
        "currency": "IRR",
        "jdate": _safe_jdate(quote_res.date),
        "quote": quote_dict,
        "info": _to_jsonable(info_obj.to_dict()) if info_obj is not None else None,
        "valuation": {
            "eps": _to_jsonable(info_obj.eps) if info_obj is not None else None,
            "pe_ratio": pe_ratio,
            "sector_pe": _to_jsonable(info_obj.sector_pe) if info_obj is not None else None,
            "market_cap_irr": market_cap_irr,
        },
        "order_book": book_payload,
        "client_type": ct_payload,
    }


async def _build_overview_payload(
    client: AsyncTSETMCClient,
    *,
    flow: Literal[1, 2] = 1,
    include_sectors: bool = False,
    include_top_trades: bool = False,
    top_limit: int = 10,
) -> dict[str, Any]:
    coros: list[tuple[str, Any]] = [("overview", client.market.overview(flow=flow))]
    if include_sectors:
        coros.append(("sectors", client.market.sectors()))
    if include_top_trades:
        coros.append(("top_trades", client.market.top_trades(category=1, flow=flow, top=top_limit)))

    results = await asyncio.gather(*(c for _, c in coros))
    by_name = dict(zip((k for k, _ in coros), results, strict=True))

    overview = by_name["overview"]
    overview_dict = _to_jsonable(overview.to_dict())
    overview_dict["jdate"] = _safe_jdate(overview.date)

    index_prev = overview.index_value - overview.index_change
    eq_prev = overview.equal_weighted_index - overview.equal_weighted_change
    index_change_pct = round(overview.index_change / index_prev * 100.0, 3) if index_prev > 0 else 0.0
    eq_change_pct = round(overview.equal_weighted_change / eq_prev * 100.0, 3) if eq_prev > 0 else 0.0

    payload: dict[str, Any] = {
        "flow": flow,
        "flow_name": "TSE (Bourse)" if flow == 1 else "Farabourse (IFB)",
        "currency": "IRR",
        "jdate": _safe_jdate(overview.date),
        "overview": overview_dict,
        "breadth": {
            "main_index_change_pct": index_change_pct,
            "equal_weighted_change_pct": eq_change_pct,
            "breadth_spread_pct": round(eq_change_pct - index_change_pct, 3),
        },
    }
    if include_sectors:
        sectors_list = by_name["sectors"]
        payload["sectors_count"] = len(sectors_list)
        payload["sectors"] = [_to_jsonable(s.to_dict()) for s in sectors_list]
    if include_top_trades:
        top_list = by_name["top_trades"]
        payload["top_trades_count"] = len(top_list)
        payload["top_trades"] = [_to_jsonable(item.to_dict()) for item in top_list]
    return payload


def _build_screen_row(
    item: MarketWatchItem,
    ct: ClientTypeLive | None,
) -> dict[str, Any]:
    ref_price = item.close if item.close > 0 else item.last
    real_money_flow: int | None = None
    real_money_flow_estimated = False
    net_i_volume: int | None = None
    buyer_power: float | None = None

    if ct is not None:
        net_i_volume = ct.net_i_volume
        if ct.buy_i_value > 0 or ct.sell_i_value > 0:
            real_money_flow = ct.real_money_flow
        elif ref_price > 0:
            real_money_flow = int(round(ct.net_i_volume * ref_price))
            real_money_flow_estimated = True

        raw_bp = ct.buyer_power if ct.buyer_power > 0 else ct.volume_buyer_power
        buyer_power = round(raw_bp, 4) if raw_bp > 0 else 0.0

    book = OrderBook(
        ins_code=item.ins_code,
        levels=item.order_book,
        price_max_allowed=item.price_max_allowed,
        price_min_allowed=item.price_min_allowed,
    )
    return {
        "ins_code": item.ins_code,
        "symbol": item.symbol,
        "name": item.name,
        "isin": item.isin,
        "sector_code": item.sector_code,
        "y_val": item.y_val,
        "last": _to_jsonable(item.last),
        "close": _to_jsonable(item.close),
        "yesterday": _to_jsonable(item.yesterday),
        "change": _to_jsonable(item.change),
        "change_pct": round(item.change_pct, 2),
        "volume": item.volume,
        "value": item.value,
        "trade_count": item.trade_count,
        "eps": _to_jsonable(item.eps),
        "pe": _to_jsonable(item.pe),
        "net_i_volume": net_i_volume,
        "real_money_flow": real_money_flow,
        "real_money_flow_estimated": real_money_flow_estimated,
        "buyer_power": buyer_power,
        "is_buy_queue": book.is_buy_queue,
        "is_sell_queue": book.is_sell_queue,
    }


def _sector_matches(item_sector: str, target_sector: str) -> bool:
    left = item_sector.strip().lstrip("0") or "0"
    right = target_sector.strip().lstrip("0") or "0"
    return bool(item_sector.strip()) and left == right


def _construct_sync_service(service_cls: type[Any], store: Any, client: AsyncTSETMCClient) -> Any:
    sig = inspect.signature(service_cls.__init__)
    params = sig.parameters
    kwargs: dict[str, Any] = {}
    if "store" in params:
        kwargs["store"] = store
    if "client" in params:
        kwargs["client"] = client
    if kwargs:
        return service_cls(**kwargs)
    return service_cls(store)


async def _call_maybe_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    result = await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    if inspect.isawaitable(result):
        return await result
    return result


async def _invoke_sync_method(
    service: Any,
    method_names: tuple[str, ...],
    *,
    symbols: list[str] | None,
    sector: str | None,
    all_instruments: bool,
    include_client_type: bool,
) -> Any:
    for method_name in method_names:
        method = getattr(service, method_name, None)
        if not callable(method):
            continue
        sig = inspect.signature(method)
        params = sig.parameters
        kwargs: dict[str, Any] = {}
        if symbols is not None and "symbols" in params:
            kwargs["symbols"] = symbols
        if sector is not None:
            if "sector" in params:
                kwargs["sector"] = sector
            elif "sector_code" in params:
                kwargs["sector_code"] = sector
        if "all_instruments" in params:
            kwargs["all_instruments"] = all_instruments
        if "include_client_types" in params:
            kwargs["include_client_types"] = include_client_type
        elif "include_client_type" in params:
            kwargs["include_client_type"] = include_client_type
        elif "client_type" in params:
            kwargs["client_type"] = include_client_type
        return await _call_maybe_async(method, **kwargs)
    return None


def _local_sqlite_file_path(target: str) -> Path | None:
    """Return local filesystem Path if ``target`` is a file-backed SQLite target."""
    raw = target.strip()
    lower = raw.lower()
    if lower == ":memory:":
        return None
    if "://" in raw:
        scheme, rest = raw.split("://", 1)
        base_scheme = scheme.lower().split("+", 1)[0]
        if base_scheme != "sqlite":
            return None
        path_part = rest.split("#", 1)[0].split("?", 1)[0]
        if path_part.startswith("/"):
            path_part = path_part[1:]
        if not path_part or path_part.lower() == ":memory:":
            return None
        return Path(path_part)
    return Path(raw)


_REDACTED = "***"
_SENSITIVE_QUERY_KEYS = ("pass", "pwd", "secret", "token", "key", "user", "auth", "cred")


def _sanitize_db_label(target: str | None) -> str | None:
    """Return a non-secret label for a DB target, safe to include in tool results.

    - ``:memory:`` -> ``":memory:"``
    - local SQLite files (plain paths or ``sqlite[+driver]:///path``) -> file name only
    - other URIs -> ``scheme://host:port/database`` with userinfo, query, and fragment removed
    """
    if target is None:
        return None
    raw = str(target).strip()
    if not raw:
        return None
    if raw.lower() == ":memory:":
        return ":memory:"

    local_file = _local_sqlite_file_path(raw)
    if local_file is not None:
        return local_file.name or "sqlite"

    if "://" not in raw:
        return raw

    scheme, rest = raw.split("://", 1)
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

    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]
    rest = rest.split("#", 1)[0].split("?", 1)[0]
    return f"{scheme}://{rest}"


def _db_secrets(target: str | None) -> list[str]:
    """Collect credential fragments (userinfo, username, password, secret query values)."""
    raw = str(target or "").strip()
    if "://" not in raw:
        return []

    secrets: set[str] = set()
    rest = raw.split("://", 1)[1]
    if "@" in rest:
        userinfo = rest.rsplit("@", 1)[0]
        user, _, password = userinfo.partition(":")
        secrets.update({userinfo, user, password, unquote(user), unquote(password)})

    try:
        parts = urlsplit(raw)
        secrets.update({parts.username or "", parts.password or "", parts.query or ""})
    except ValueError:
        pass

    try:
        from sqlalchemy.engine import make_url

        url = make_url(raw)
        secrets.update({url.username or "", url.password or ""})
        for key, value in url.query.items():
            if any(token in key.lower() for token in _SENSITIVE_QUERY_KEYS):
                values = value if isinstance(value, tuple) else (value,)
                secrets.update(str(v) for v in values)
    except Exception:
        pass

    return sorted((s for s in secrets if s), key=len, reverse=True)


def _redact_db_message(message: str, target: str | None) -> str:
    """Scrub the raw DB target and any embedded credentials out of ``message``."""
    raw = str(target or "").strip()
    text = message
    if not raw:
        return text
    label = _sanitize_db_label(raw) or _REDACTED
    if raw != label:
        text = text.replace(raw, label)
    for secret in _db_secrets(raw):
        if re.fullmatch(r"[\w.-]+", secret):
            text = re.sub(rf"(?<![\w]){re.escape(secret)}(?![\w])", _REDACTED, text)
        else:
            text = text.replace(secret, _REDACTED)
    return text


def _open_store_for_query(storage_mod: Any, target: str) -> Any:
    """Open ``target`` for read-only querying without creating a brand-new empty DB file."""
    local_file = _local_sqlite_file_path(target)
    if local_file is not None and not local_file.exists():
        raise ToolError(
            f"Local database file does not exist: {_sanitize_db_label(target)}. "
            "Run sync_local_db or `tse db init` first."
        )
    open_fn = storage_mod.open_store
    sig = inspect.signature(open_fn)
    kwargs: dict[str, Any] = {}
    if "init_schema" in sig.parameters:
        kwargs["init_schema"] = False
    # A query must not change the file: opening it writable switches it to WAL mode.
    if "read_only" in sig.parameters:
        kwargs["read_only"] = True
    return open_fn(target, **kwargs)


def _load_storage_module() -> Any:
    """Import ``tehran_stocks.storage`` via ``importlib`` so ``sys.modules`` mocks apply reliably."""
    try:
        return importlib.import_module("tehran_stocks.storage")
    except ImportError as exc:
        raise ToolError(
            "tehran_stocks.storage is not available in this installation."
        ) from exc


async def _run_sync_on_store(
    config: ServerConfig,
    *,
    symbols: list[str] | None,
    sector: str | None,
    all_instruments: bool,
    include_client_type: bool,
) -> dict[str, Any]:
    if not config.db_path:
        raise ToolError(
            "Local database is not configured. Start the MCP server with --db <path> "
            "or set TEHRAN_STOCKS_DB."
        )

    storage_mod = _load_storage_module()

    normalized_symbols = (
        [normalize_persian(s).strip() for s in symbols if normalize_persian(s).strip()]
        if symbols
        else None
    )
    cleaned_sector = normalize_persian(sector).strip() if sector else None

    store = storage_mod.open_store(config.db_path)
    try:
        await _call_maybe_async(store.init_schema)

        async_cls = getattr(storage_mod, "AsyncSyncService", None)
        sync_cls = getattr(storage_mod, "SyncService", None)
        service_cls = async_cls or sync_cls
        if service_cls is None:
            raise ToolError("No SyncService/AsyncSyncService found in tehran_stocks.storage")

        async with _open_client(config) as client:
            service = _construct_sync_service(service_cls, store, client)
            sync_summary: Any = None

            # Prefer high-level unified sync entrypoints if offered, else compose step calls.
            unified = await _invoke_sync_method(
                service,
                ("sync", "sync_all"),
                symbols=normalized_symbols,
                sector=cleaned_sector,
                all_instruments=all_instruments,
                include_client_type=include_client_type,
            )
            if unified is not None:
                sync_summary = unified
            else:
                catalog_res = await _invoke_sync_method(
                    service,
                    ("sync_sectors_and_instruments", "sync_instruments", "sync_universe"),
                    symbols=normalized_symbols,
                    sector=cleaned_sector,
                    all_instruments=all_instruments,
                    include_client_type=include_client_type,
                )
                details: dict[str, Any] = {}
                if catalog_res is not None:
                    details["universe"] = catalog_res

                if normalized_symbols or cleaned_sector or all_instruments:
                    price_res = await _invoke_sync_method(
                        service,
                        ("sync_prices",),
                        symbols=normalized_symbols,
                        sector=cleaned_sector,
                        all_instruments=all_instruments,
                        include_client_type=include_client_type,
                    )
                    if price_res is not None:
                        details["prices"] = price_res
                    if include_client_type:
                        ct_res = await _invoke_sync_method(
                            service,
                            ("sync_client_types",),
                            symbols=normalized_symbols,
                            sector=cleaned_sector,
                            all_instruments=all_instruments,
                            include_client_type=include_client_type,
                        )
                        if ct_res is not None:
                            details["client_types"] = ct_res
                sync_summary = details

        stats = await _call_maybe_async(store.stats)
        return {
            "database": _sanitize_db_label(config.db_path),
            "symbols": normalized_symbols or [],
            "sector": cleaned_sector,
            "all_instruments": all_instruments,
            "include_client_type": include_client_type,
            "sync_result": _to_jsonable(sync_summary),
            "stats": _to_jsonable(stats),
        }
    finally:
        close_fn = getattr(store, "close", None)
        if callable(close_fn):
            await _call_maybe_async(close_fn)


async def _run_readonly_query(
    config: ServerConfig,
    *,
    sql: str,
    limit: int,
) -> dict[str, Any]:
    if not config.db_path:
        raise ToolError(
            "Local database is not configured. Start the MCP server with --db <path> "
            "or set TEHRAN_STOCKS_DB."
        )

    cleaned_sql = sql.strip()
    if not cleaned_sql:
        raise ToolError("sql must not be empty")

    storage_mod = _load_storage_module()

    store = _open_store_for_query(storage_mod, config.db_path)
    try:
        raw_rows = await _call_maybe_async(store.query_readonly, cleaned_sql)
        rows_list = [_to_jsonable(dict(row)) for row in raw_rows]
        truncated = len(rows_list) > limit
        sliced = rows_list[:limit]
        columns = list(sliced[0].keys()) if sliced else []
        return {
            "database": _sanitize_db_label(config.db_path),
            "row_count": len(sliced),
            "total_rows": len(rows_list),
            "truncated": truncated,
            "columns": columns,
            "rows": sliced,
        }
    finally:
        close_fn = getattr(store, "close", None)
        if callable(close_fn):
            await _call_maybe_async(close_fn)


def create_server(
    db_path: str | Path | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    proxy: str | None = None,
    transport: Literal["stdio", "streamable-http"] | str | None = None,
    *,
    client_transport: Any | None = None,
) -> MCPServer:
    """Create and configure the official ``mcp>=2.0`` ``MCPServer`` for TSETMC.

    Registers the 10 on-demand TSETMC tools and 3 MCP resources unconditionally.
    When ``db_path`` (or ``TEHRAN_STOCKS_DB``) is set, also registers the 2 opt-in
    local database tools (``sync_local_db`` and ``query_local_db``).
    """
    config = resolve_server_config(
        db_path=db_path,
        timeout=timeout,
        proxy=proxy,
        transport=transport,
        client_transport=client_transport,
    )

    server = MCPServer(
        name="tehran-stocks",
        title="Tehran Stock Exchange (TSETMC)",
        description=(
            "Live and historical Tehran Stock Exchange (TSETMC) market intelligence, "
            "institutional/retail money flows, 5-level order books, disclosures, and "
            "optional read-only SQLite/SQLAlchemy queries."
        ),
        instructions=_SERVER_INSTRUCTIONS,
        version="3.0.0",
    )

    # ------------------------------------------------------------------
    # 10 On-Demand Tools
    # ------------------------------------------------------------------

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def search_instruments(
        query: Annotated[
            str,
            Field(
                min_length=1,
                description="Persian or Arabic symbol, company name, or ISIN to search for.",
            ),
        ],
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of matching instruments to return."),
        ] = 15,
    ) -> dict[str, Any]:
        """Search TSETMC instruments by Persian/Arabic ticker, company name, or ISIN."""
        cleaned = _clean_symbol_or_query(query, "query")
        try:
            async with _open_client(config) as client:
                items = await client.instruments.search(cleaned)
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        sliced = items[:limit]
        return {
            "query": cleaned,
            "count": len(sliced),
            "total_found": len(items),
            "instruments": [_to_jsonable(item.to_dict()) for item in sliced],
        }

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_stock_snapshot(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل' or 'فولاد'), ISIN, or numeric insCode.",
            ),
        ],
        include_order_book: Annotated[
            bool,
            Field(description="Include 5-level order book and buy/sell queue status."),
        ] = True,
        include_client_type: Annotated[
            bool,
            Field(description="Include live individual (حقیقی) vs institutional (حقوقی) flow."),
        ] = True,
    ) -> dict[str, Any]:
        """Fetch live quote, fundamentals, valuation, optional order book, and client-type flow."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        try:
            async with _open_client(config) as client:
                return await _build_snapshot_payload(
                    client,
                    cleaned,
                    include_order_book=include_order_book,
                    include_client_type=include_client_type,
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_price_history(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل'), ISIN, or numeric insCode.",
            ),
        ],
        days: Annotated[
            int | None,
            Field(
                ge=0,
                le=5000,
                description=(
                    "Number of recent trading days to request (0 = full available history; "
                    "defaults to 0 when start/end is provided, otherwise 30)."
                ),
            ),
        ] = None,
        start: Annotated[
            str | None,
            Field(
                description="Optional inclusive start date (Gregorian YYYY-MM-DD or Jalali e.g. '1403-01-01')."
            ),
        ] = None,
        end: Annotated[
            str | None,
            Field(
                description="Optional inclusive end date (Gregorian YYYY-MM-DD or Jalali e.g. '1403-12-29')."
            ),
        ] = None,
        adjusted: Annotated[
            bool,
            Field(
                description="Apply backward corporate-action adjustment for dividends and capital increases."
            ),
        ] = True,
        include_jalali: Annotated[
            bool,
            Field(description="Include Jalali date ('jdate') on each bar."),
        ] = True,
        limit: Annotated[
            int | None,
            Field(
                ge=1,
                le=2000,
                description="Optional maximum number of most recent bars to return after filtering.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Fetch chronological daily OHLCV history with optional backward adjustment and Jalali dates."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        has_date_range = bool((start and start.strip()) or (end and end.strip()))
        effective_days = days if days is not None else (0 if has_date_range else 30)
        try:
            async with _open_client(config) as client:
                ins_code = await client.resolve(cleaned)
                bars = await client.prices.history(
                    ins_code,
                    days=effective_days,
                    start=start,
                    end=end,
                    adjusted=adjusted,
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        if limit is not None and len(bars) > limit:
            bars = bars[-limit:]

        serialized_bars: list[dict[str, Any]] = []
        for bar in bars:
            row = _to_jsonable(bar.to_dict())
            row["change"] = _to_jsonable(bar.change)
            row["change_pct"] = round(bar.change_pct, 2)
            if include_jalali:
                row["jdate"] = _safe_jdate(bar.date)
            serialized_bars.append(row)

        summary: dict[str, Any] = {}
        if bars:
            first_close = bars[0].close
            last_close = bars[-1].close
            period_return_pct = (
                round((last_close - first_close) / first_close * 100.0, 2)
                if first_close > 0
                else 0.0
            )
            summary = {
                "start_date": bars[0].date.isoformat(),
                "end_date": bars[-1].date.isoformat(),
                "start_jdate": _safe_jdate(bars[0].date),
                "end_jdate": _safe_jdate(bars[-1].date),
                "latest_close": _to_jsonable(last_close),
                "period_high": _to_jsonable(max(b.high for b in bars)),
                "period_low": _to_jsonable(min(b.low for b in bars)),
                "period_return_pct": period_return_pct,
                "avg_volume": int(round(sum(b.volume for b in bars) / len(bars))),
            }

        return {
            "symbol": cleaned,
            "ins_code": ins_code,
            "adjusted": adjusted,
            "currency": "IRR",
            "count": len(serialized_bars),
            "summary": summary,
            "bars": serialized_bars,
        }

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_client_type_flow(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل'), ISIN, or numeric insCode.",
            ),
        ],
        days: Annotated[
            int,
            Field(
                ge=0,
                le=365,
                description="Number of recent daily history sessions to include (0 = live only).",
            ),
        ] = 10,
    ) -> dict[str, Any]:
        """Fetch live & historical individual (حقیقی) vs institutional (حقوقی) flow and buyer power."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        try:
            async with _open_client(config) as client:
                ins_code = await client.resolve(cleaned)
                if days > 0:
                    live, history_rows = await asyncio.gather(
                        client.client_type.live(ins_code),
                        client.client_type.history(ins_code, days=days),
                    )
                else:
                    live = await client.client_type.live(ins_code)
                    history_rows = []
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        serialized_history = [_serialize_client_type(row) for row in history_rows]
        summary: dict[str, Any] = {}
        if history_rows:
            inflow_days = sum(1 for row in history_rows if row.real_money_flow > 0)
            outflow_days = sum(1 for row in history_rows if row.real_money_flow < 0)
            summary = {
                "total_real_money_flow_irr": sum(row.real_money_flow for row in history_rows),
                "total_net_i_volume": sum(row.net_i_volume for row in history_rows),
                "avg_buyer_power": round(
                    sum(row.buyer_power for row in history_rows) / len(history_rows),
                    4,
                ),
                "inflow_days": inflow_days,
                "outflow_days": outflow_days,
            }

        return {
            "symbol": cleaned,
            "ins_code": ins_code,
            "currency": "IRR",
            "live": _serialize_client_type(live),
            "history_count": len(serialized_history),
            "summary": summary,
            "history": serialized_history,
        }

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_order_book(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل'), ISIN, or numeric insCode.",
            ),
        ],
        include_thresholds: Annotated[
            bool,
            Field(
                description="Fetch daily price floor/ceiling (pMin/pMax) for buy/sell queue detection."
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Fetch the 5-level bid/ask limit order book with buy/sell queue (صف خرید / صف فروش) flags."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        try:
            async with _open_client(config) as client:
                ins_code = await client.resolve(cleaned)
                book = await client.prices.order_book(
                    ins_code,
                    include_thresholds=include_thresholds,
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        payload = _serialize_order_book(book)
        payload["symbol"] = cleaned
        return payload

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_fundamentals_and_events(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل' or 'بمان'), ISIN, or numeric insCode.",
            ),
        ],
        include_statistics: Annotated[
            bool,
            Field(description="Include TSETMC liquidity, rank, and rolling average statistics."),
        ] = True,
        include_shareholders: Annotated[
            bool,
            Field(description="Include major shareholders (>1% stake)."),
        ] = True,
        include_share_changes: Annotated[
            bool,
            Field(description="Include historical capital increases / share count changes."),
        ] = True,
        include_adjustments: Annotated[
            bool,
            Field(description="Include dividend and capital-increase price adjustment factors."),
        ] = True,
        include_etf: Annotated[
            bool,
            Field(description="Include ETF redemption/subscription/statistical NAV if applicable."),
        ] = False,
    ) -> dict[str, Any]:
        """Fetch instrument fundamentals, identity, statistics, shareholders, corporate actions, and ETF NAV."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        try:
            async with _open_client(config) as client:
                ins_code = await client.resolve(cleaned)
                tasks: dict[str, Any] = {
                    "info": client.instruments.info(ins_code),
                    "identity": client.instruments.identity(ins_code),
                }
                if include_statistics:
                    tasks["statistics"] = client.instruments.statistics(ins_code)
                if include_shareholders:
                    tasks["shareholders"] = client.disclosures.shareholders(ins_code)
                if include_share_changes:
                    tasks["share_changes"] = client.instruments.share_changes(ins_code)
                if include_adjustments:
                    tasks["adjustments"] = client.prices.adjustments(ins_code)
                if include_etf:
                    tasks["etf"] = client.funds.etf(ins_code)

                keys = list(tasks.keys())
                raw_results = await asyncio.gather(
                    *(tasks[k] for k in keys),
                    return_exceptions=True,
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        resolved = dict(zip(keys, raw_results, strict=True))

        def _unwrap(key: str, *, optional: bool = False) -> Any:
            if key not in resolved:
                return None
            val = resolved[key]
            if isinstance(val, BaseException):
                if optional and _is_optional_missing(val):
                    return None
                if isinstance(val, (TehranStocksError, ValueError)):
                    raise ToolError(str(val)) from val
                raise val
            return val

        info_obj = _unwrap("info")
        identity_obj = _unwrap("identity", optional=True)
        stats_list = _unwrap("statistics", optional=True) or []
        sh_list = _unwrap("shareholders", optional=True) or []
        sc_list = _unwrap("share_changes", optional=True) or []
        adj_list = _unwrap("adjustments", optional=True) or []
        etf_obj = _unwrap("etf", optional=True)

        share_changes_out: list[dict[str, Any]] = []
        for sc in sc_list:
            row = _to_jsonable(sc.to_dict())
            row["change"] = sc.change
            row["ratio"] = round(sc.ratio, 6)
            row["jdate"] = _safe_jdate(sc.date)
            share_changes_out.append(row)

        adjustments_out: list[dict[str, Any]] = []
        for adj in adj_list:
            row = _to_jsonable(adj.to_dict())
            row["ratio"] = round(adj.ratio, 6)
            row["jdate"] = _safe_jdate(adj.date)
            adjustments_out.append(row)

        etf_out: dict[str, Any] | None = None
        if etf_obj is not None:
            etf_out = _to_jsonable(etf_obj.to_dict())
            etf_out["nav_premium_pct"] = _to_jsonable(etf_obj.nav_premium_pct)
            etf_out["jdate"] = _safe_jdate(etf_obj.date)

        return {
            "symbol": info_obj.symbol or cleaned,
            "name": info_obj.name,
            "ins_code": ins_code,
            "currency": "IRR",
            "info": _to_jsonable(info_obj.to_dict()),
            "identity": _to_jsonable(identity_obj.to_dict()) if identity_obj is not None else None,
            "statistics": [_to_jsonable(s.to_dict()) for s in stats_list],
            "shareholders": [_to_jsonable(sh.to_dict()) for sh in sh_list],
            "share_changes": share_changes_out,
            "adjustments": adjustments_out,
            "etf": etf_out,
        }

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_market_overview(
        flow: Annotated[
            Literal[1, 2],
            Field(description="Exchange segment: 1 = Tehran Stock Exchange (Bourse), 2 = Farabourse."),
        ] = 1,
        include_sectors: Annotated[
            bool,
            Field(description="Include industrial sector definitions and live summary metrics."),
        ] = True,
        include_top_trades: Annotated[
            bool,
            Field(description="Include top traded instruments for the market segment."),
        ] = False,
        top_limit: Annotated[
            int,
            Field(ge=1, le=50, description="Number of top traded instruments if include_top_trades is True."),
        ] = 10,
    ) -> dict[str, Any]:
        """Fetch live market overview (TEDPIX, equal-weighted index, market state, totals) and sectors."""
        try:
            async with _open_client(config) as client:
                return await _build_overview_payload(
                    client,
                    flow=flow,
                    include_sectors=include_sectors,
                    include_top_trades=include_top_trades,
                    top_limit=top_limit,
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_indices(
        flow: Annotated[
            Literal[1, 2],
            Field(description="Exchange segment: 1 = TSE, 2 = Farabourse."),
        ] = 1,
        index_code: Annotated[
            str | None,
            Field(
                description="Optional index insCode or alias ('TEDPIX', 'شاخص کل', '32097828799138957') to fetch history and index movers."
            ),
        ] = None,
        history_days: Annotated[
            int,
            Field(ge=0, le=2000, description="Number of recent daily index bars to return when index_code is provided (0 = all)."),
        ] = 30,
        include_effect: Annotated[
            bool,
            Field(description="Include top instruments impacting the selected index when index_code is provided."),
        ] = True,
    ) -> dict[str, Any]:
        """Fetch live market and sector indices, plus optional daily index history and index-effect movers."""
        cleaned_index = normalize_persian(index_code).strip() if index_code else None
        try:
            async with _open_client(config) as client:
                if cleaned_index:
                    coros: list[Any] = [
                        client.market.indices(flow=flow),
                        client.market.index_history(cleaned_index),
                    ]
                    if include_effect:
                        coros.append(client.market.index_effect(cleaned_index, flow=flow, top=10))
                    gathered = await asyncio.gather(*coros, return_exceptions=True)
                    indices_res = gathered[0]
                    hist_res = gathered[1]
                    effect_res = gathered[2] if include_effect else None
                else:
                    indices_res = await client.market.indices(flow=flow)
                    hist_res = None
                    effect_res = None
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        if isinstance(indices_res, BaseException):
            if isinstance(indices_res, (TehranStocksError, ValueError)):
                raise ToolError(str(indices_res)) from indices_res
            raise indices_res

        indices_out = []
        for idx in indices_res:
            row = _to_jsonable(idx.to_dict())
            row["jdate"] = _safe_jdate(idx.date)
            indices_out.append(row)

        payload: dict[str, Any] = {
            "flow": flow,
            "count": len(indices_out),
            "indices": indices_out,
        }

        if cleaned_index:
            if isinstance(hist_res, BaseException):
                if isinstance(hist_res, (TehranStocksError, ValueError)):
                    raise ToolError(str(hist_res)) from hist_res
                raise hist_res

            bars = list(hist_res or [])
            if history_days > 0 and len(bars) > history_days:
                bars = bars[-history_days:]

            history_out = []
            for bar in bars:
                bar_row = _to_jsonable(bar.to_dict())
                bar_row["jdate"] = _safe_jdate(bar.date)
                history_out.append(bar_row)

            effects_out: list[dict[str, Any]] = []
            if include_effect and effect_res is not None:
                if isinstance(effect_res, BaseException):
                    if not _is_optional_missing(effect_res):
                        if isinstance(effect_res, (TehranStocksError, ValueError)):
                            raise ToolError(str(effect_res)) from effect_res
                        raise effect_res
                else:
                    effects_out = [_to_jsonable(item.to_dict()) for item in effect_res]

            payload["selected_index"] = {
                "index_code": cleaned_index,
                "history_count": len(history_out),
                "history": history_out,
                "top_effects": effects_out,
            }

        return payload

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def screen_market(
        sector_code: Annotated[
            str | None,
            Field(description="Filter by 2-digit TSETMC sector code (e.g. '13', '27', '40')."),
        ] = None,
        query: Annotated[
            str | None,
            Field(description="Optional substring filter on normalized symbol or company name."),
        ] = None,
        min_value: Annotated[
            int | None,
            Field(ge=0, description="Minimum traded value in IRR."),
        ] = None,
        min_volume: Annotated[
            int | None,
            Field(ge=0, description="Minimum traded share volume."),
        ] = None,
        min_change_pct: Annotated[
            float | None,
            Field(description="Minimum daily price change percentage."),
        ] = None,
        max_change_pct: Annotated[
            float | None,
            Field(description="Maximum daily price change percentage."),
        ] = None,
        min_buyer_power: Annotated[
            float | None,
            Field(ge=0.0, description="Minimum individual buyer-to-seller power ratio (قدرت خریدار)."),
        ] = None,
        min_real_money_flow: Annotated[
            float | None,
            Field(description="Minimum estimated individual real money flow in IRR."),
        ] = None,
        queue_only: Annotated[
            Literal["buy", "sell"] | None,
            Field(description="Optional filter for active buy queues ('buy') or sell queues ('sell')."),
        ] = None,
        sort_by: Annotated[
            Literal[
                "value",
                "volume",
                "change_pct",
                "real_money_flow",
                "buyer_power",
                "trade_count",
            ],
            Field(description="Ranking field."),
        ] = "value",
        ascending: Annotated[
            bool,
            Field(description="Sort ascending instead of descending."),
        ] = False,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of screened instruments to return."),
        ] = 20,
    ) -> dict[str, Any]:
        """Screen and rank the full live market (GetMarketWatch + GetClientTypeAll) in 2 HTTP calls."""
        cleaned_query = normalize_persian(query).strip() if query else None
        cleaned_sector = normalize_persian(sector_code).strip() if sector_code else None

        try:
            async with _open_client(config) as client:
                watch_items, ct_all = await asyncio.gather(
                    client.market.watch(),
                    client.client_type.all(),
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        ct_by_code = {ct.ins_code: ct for ct in ct_all}
        matched: list[dict[str, Any]] = []

        for item in watch_items:
            if cleaned_sector and not _sector_matches(item.sector_code, cleaned_sector):
                continue
            if cleaned_query and (
                cleaned_query not in item.symbol and cleaned_query not in item.name
            ):
                continue
            if min_value is not None and item.value < min_value:
                continue
            if min_volume is not None and item.volume < min_volume:
                continue
            if min_change_pct is not None and item.change_pct < min_change_pct:
                continue
            if max_change_pct is not None and item.change_pct > max_change_pct:
                continue

            row = _build_screen_row(item, ct_by_code.get(item.ins_code))
            if min_buyer_power is not None:
                if row["buyer_power"] is None or row["buyer_power"] < min_buyer_power:
                    continue
            if min_real_money_flow is not None:
                if row["real_money_flow"] is None or row["real_money_flow"] < min_real_money_flow:
                    continue
            if queue_only == "buy" and not row["is_buy_queue"]:
                continue
            if queue_only == "sell" and not row["is_sell_queue"]:
                continue
            matched.append(row)

        def _sort_key(row: dict[str, Any]) -> tuple[bool, float]:
            val = row.get(sort_by)
            if val is None:
                return (True, 0.0)
            num = float(val)
            return (False, num if ascending else -num)

        matched.sort(key=_sort_key)
        sliced = matched[:limit]

        return {
            "total_watched": len(watch_items),
            "matched_count": len(matched),
            "returned_count": len(sliced),
            "sort_by": sort_by,
            "ascending": ascending,
            "currency": "IRR",
            "results": sliced,
        }

    @server.tool(annotations=_READ_ONLY_REMOTE_ANNOTATIONS)
    async def get_disclosures(
        symbol: Annotated[
            str,
            Field(
                min_length=1,
                description="Ticker symbol (e.g. 'کگل'), ISIN, or numeric insCode.",
            ),
        ],
        codal_limit: Annotated[
            int,
            Field(ge=0, le=50, description="Maximum number of Codal announcements to return."),
        ] = 10,
        messages_limit: Annotated[
            int,
            Field(ge=0, le=50, description="Maximum number of market supervisor messages to return."),
        ] = 10,
    ) -> dict[str, Any]:
        """Fetch recent Codal corporate disclosures and market supervisor messages (halts, AGMs)."""
        cleaned = _clean_symbol_or_query(symbol, "symbol")
        try:
            async with _open_client(config) as client:
                ins_code = await client.resolve(cleaned)
                coros: dict[str, Any] = {}
                if codal_limit > 0:
                    coros["codal"] = client.disclosures.codal(ins_code, limit=codal_limit)
                if messages_limit > 0:
                    coros["messages"] = client.disclosures.messages(ins_code, limit=messages_limit)

                keys = list(coros.keys())
                raw = (
                    await asyncio.gather(*(coros[k] for k in keys))
                    if keys
                    else []
                )
        except (TehranStocksError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        fetched = dict(zip(keys, raw, strict=True))
        codal_out = []
        for entry in fetched.get("codal", ()):
            row = _to_jsonable(entry.to_dict())
            row["jdate"] = _safe_jdate(entry.date)
            codal_out.append(row)

        messages_out = []
        for msg in fetched.get("messages", ()):
            row = _to_jsonable(msg.to_dict())
            row["jdate"] = _safe_jdate(msg.date)
            messages_out.append(row)

        return {
            "symbol": cleaned,
            "ins_code": ins_code,
            "codal_count": len(codal_out),
            "codal": codal_out,
            "messages_count": len(messages_out),
            "messages": messages_out,
        }

    # ------------------------------------------------------------------
    # 2 Opt-In Local DB Tools (registered when db_path / TEHRAN_STOCKS_DB is set)
    # ------------------------------------------------------------------

    if config.db_path is not None:

        @server.tool(annotations=_WRITE_LOCAL_ANNOTATIONS)
        async def sync_local_db(
            symbols: Annotated[
                list[str] | None,
                Field(
                    description="Optional list of symbols, ISINs, or insCodes to sync prices and client-type flow for."
                ),
            ] = None,
            sector: Annotated[
                str | None,
                Field(description="Optional 2-digit sector code to sync instruments in that sector."),
            ] = None,
            all_instruments: Annotated[
                bool,
                Field(
                    description="If True, sync historical prices/client-types across all tracked instruments."
                ),
            ] = False,
            include_client_type: Annotated[
                bool,
                Field(
                    description="Also sync daily individual/institutional (حقیقی/حقوقی) flow history."
                ),
            ] = True,
        ) -> dict[str, Any]:
            """Incrementally sync TSETMC sectors, instruments, prices, and client-type history into the configured local DB."""
            try:
                return await _run_sync_on_store(
                    config,
                    symbols=symbols,
                    sector=sector,
                    all_instruments=all_instruments,
                    include_client_type=include_client_type,
                )
            except Exception as exc:
                # Never echo the connection string / credentials back to the model.
                raise ToolError(_redact_db_message(str(exc), config.db_path)) from None

        @server.tool(annotations=_READ_ONLY_LOCAL_ANNOTATIONS)
        async def query_local_db(
            sql: Annotated[
                str,
                Field(
                    min_length=1,
                    description=(
                        "Read-only SQL SELECT / WITH / PRAGMA query executed via store.query_readonly. "
                        "Tables: sectors, instruments, daily_prices, client_types, price_adjustments, "
                        "share_changes, sync_meta."
                    ),
                ),
            ],
            limit: Annotated[
                int,
                Field(ge=1, le=1000, description="Maximum number of rows returned."),
            ] = 200,
        ) -> dict[str, Any]:
            """Execute a read-only analytical SQL query against the local database.

            Available tables: ``sectors``, ``instruments``, ``daily_prices``, ``client_types``,
            ``price_adjustments``, ``share_changes``, and ``sync_meta``. Mutating statements are rejected.
            """
            try:
                return await _run_readonly_query(config, sql=sql, limit=limit)
            except Exception as exc:
                # Never echo the connection string / credentials back to the model.
                raise ToolError(_redact_db_message(str(exc), config.db_path)) from None

    # ------------------------------------------------------------------
    # 3 MCP Resources
    # ------------------------------------------------------------------

    @server.resource(
        "tsetmc://market/overview",
        name="market_overview",
        title="TSETMC Live Market Overview",
        description="Live Tehran Stock Exchange overview including TEDPIX, equal-weighted index, market state, and total value/volume.",
        mime_type="application/json",
    )
    async def market_overview_resource() -> str:
        """Return live market overview JSON."""
        try:
            async with _open_client(config) as client:
                payload = await _build_overview_payload(client, flow=1)
        except (TehranStocksError, ValueError) as exc:
            raise ResourceError(str(exc)) from exc
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.resource(
        "tsetmc://market/sectors",
        name="market_sectors",
        title="TSETMC Industrial Sectors",
        description="All TSETMC industrial sector definitions and live sector summary metrics.",
        mime_type="application/json",
    )
    async def market_sectors_resource() -> str:
        """Return industrial sectors JSON."""
        try:
            async with _open_client(config) as client:
                sector_items = await client.market.sectors()
        except (TehranStocksError, ValueError) as exc:
            raise ResourceError(str(exc)) from exc
        payload = {
            "count": len(sector_items),
            "sectors": [_to_jsonable(sector.to_dict()) for sector in sector_items],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.resource(
        "tsetmc://instrument/{symbol}",
        name="instrument_snapshot",
        title="TSETMC Instrument Snapshot",
        description="Live quote, fundamentals, valuation, 5-level order book, and client-type flow for {symbol}.",
        mime_type="application/json",
    )
    async def instrument_resource(symbol: str) -> str:
        """Return live instrument snapshot JSON for ``symbol``."""
        cleaned = normalize_persian(symbol).strip()
        if not cleaned:
            raise ResourceNotFoundError("Symbol must not be empty")
        try:
            async with _open_client(config) as client:
                payload = await _build_snapshot_payload(
                    client,
                    cleaned,
                    include_order_book=True,
                    include_client_type=True,
                )
        except InstrumentNotFoundError as exc:
            raise ResourceNotFoundError(str(exc)) from exc
        except (TehranStocksError, ValueError) as exc:
            raise ResourceError(str(exc)) from exc
        return json.dumps(payload, ensure_ascii=False, indent=2)

    return server


__all__ = [
    "ServerConfig",
    "create_server",
    "resolve_server_config",
]
