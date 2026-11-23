"""tehran-stocks v3.0 — Modern Python SDK for the Tehran Stock Exchange (TSETMC)."""

from __future__ import annotations

from tehran_stocks import exceptions, types, utils
from tehran_stocks import api, client
from tehran_stocks.api import (
    client_type,
    client_type_history,
    codal,
    etf,
    history,
    indices,
    market_overview,
    order_book,
    quote,
    search,
    sectors,
    shareholders,
)
from tehran_stocks.client import (
    AsyncClient,
    AsyncTSETMCClient,
    Client,
    TSETMCClient,
)
from tehran_stocks.exceptions import (
    InstrumentNotFoundError,
    RateLimitError,
    StorageError,
    TSETMCError,
    TehranStocksError,
)
from tehran_stocks.utils import (
    adjust_prices,
    gregorian_to_jalali,
    int_to_date,
    jalali_to_gregorian,
    normalize_persian,
    parse_tsetmc_time,
    to_dataframe,
)

__version__ = "3.0.0"

__all__ = [
    "__version__",
    "AsyncClient",
    "AsyncTSETMCClient",
    "Client",
    "InstrumentNotFoundError",
    "RateLimitError",
    "StorageError",
    "TSETMCClient",
    "TSETMCError",
    "TehranStocksError",
    "adjust_prices",
    "api",
    "client",
    "client_type",
    "client_type_history",
    "codal",
    "etf",
    "exceptions",
    "gregorian_to_jalali",
    "history",
    "indices",
    "int_to_date",
    "jalali_to_gregorian",
    "market_overview",
    "normalize_persian",
    "order_book",
    "parse_tsetmc_time",
    "quote",
    "search",
    "sectors",
    "shareholders",
    "to_dataframe",
    "types",
    "utils",
]
