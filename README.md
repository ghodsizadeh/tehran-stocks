# Tehran Stocks (`tehran-stocks` v3.0) — بورس تهران در پایتون

[![CI](https://github.com/ghodsizadeh/tehran-stocks/actions/workflows/ci.yml/badge.svg)](https://github.com/ghodsizadeh/tehran-stocks/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/tehran-stocks.svg)](https://badge.fury.io/py/tehran-stocks)
[![Python Versions](https://img.shields.io/pypi/pyversions/tehran-stocks.svg)](https://pypi.org/project/tehran-stocks/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

**Modern, batteries-included, agent-ready Python SDK, `tse` Typer CLI, official MCP Server, and Agent Skills toolkit for the Tehran Stock Exchange (`cdn.tsetmc.com`).**

`tehran-stocks` v3.0 is rebuilt from the ground up as an **on-demand first** market data client. Importing `tehran_stocks` has **zero side effects**—it never creates `~/.tse/` config files, initializes a database, or prompts interactively. Query live quotes, backward-adjusted OHLCV history, individual vs. institutional (`حقیقی / حقوقی`) money flows, 5-level order books, indices, and Codal disclosures directly, or opt into local persistence whenever you want an offline warehouse.

---

## Key Features

- **Zero-Side-Effect On-Demand SDK**: Instant sync (`Client`) and async (`AsyncClient`) access plus top-level functions (`ts.quote`, `ts.history`, `ts.client_type`, `ts.order_book`, `ts.market_overview`, etc.) without touching disk.
- **HTTP/2 Transport via `httpx2`**: Built on Pydantic's `httpx2[http2]` with browser `User-Agent` headers, retries with exponential backoff (`429`/`502`/`503`/`504`), proxy support, and bounded async concurrency.
- **Transparent Persian/Arabic Normalization**: Automatically normalizes Arabic `ك`/`ي`/`ة` to Persian `ک`/`ی`/`ه` and Persian/Arabic digits, resolving tickers (`"کگل"` or `"كگل"`), ISINs (`"IRO1GOLG0005"`), and 17-digit `insCode`s (`"35700344742885862"`).
- **Analytics & `jalali-pandas` v1.0.0**: Built-in cumulative backward price adjustment (`adjust_prices`) and `to_dataframe()` producing `JalaliDatetimeIndex` and `jalali_datetime` columns.
- **Real Money Flow & Queue Intelligence**: First-class properties on `ClientTypeLive` / `ClientTypeDaily` (`real_money_flow`, `buy_per_capita`, `sell_per_capita`, `buyer_power`) and `OrderBook` (`is_buy_queue`, `is_sell_queue`, `spread`).
- **Opt-In Pluggable Storage**: Built-in zero-dependency `SQLiteStore` (WAL mode, `?mode=ro` read-only querying) and `SQLAlchemyStore` (PostgreSQL, DuckDB, MySQL, SQLite) with incremental `SyncService` / `AsyncSyncService`.
- **`tse` Typer CLI**: Rich terminal tables, `--json`, and `--format csv` output across 14 live commands plus `tse db`, `tse mcp`, and `tse skill`.
- **Official `mcp>=2.0` `MCPServer`**: 10 always-available TSETMC tools, 2 opt-in local DB tools (`--db`), and 3 MCP resources over `stdio` or `streamable-http` with strict `stderr`-only logging.
- **Bundled Agent Skills**: `agentskills.io`-compliant `tehran-stocks-setup` and `tehran-stocks-analysis` skills installable via `npx skills` or `tse skill install`.

---

## Installation

Requires **Python 3.11+** (`>=3.11,<4`).

```bash
# With uv (recommended)
uv add tehran-stocks

# With pip
pip install tehran-stocks
```

### Zero-Install Ephemeral CLI (`uvx`)

Run the `tse` CLI anywhere without installing into a project environment:

```bash
uvx --from tehran-stocks tse --help
uvx --from tehran-stocks tse quote کگل
uvx --from tehran-stocks tse market --json
```

### Optional Database Driver Extras

Built-in `SQLiteStore` uses Python's standard library `sqlite3` and requires **no extras**. Install optional driver extras only when connecting `SQLAlchemyStore` to PostgreSQL or DuckDB:

```bash
# PostgreSQL (psycopg[binary]>=3.2)
uv add "tehran-stocks[postgres]"
# or: pip install "tehran-stocks[postgres]"

# DuckDB (duckdb>=1.1, duckdb-engine>=0.13)
uv add "tehran-stocks[duckdb]"
# or: pip install "tehran-stocks[duckdb]"
```

---

## Python Quickstart

### Top-Level On-Demand Functions

```python
import tehran_stocks as ts

# 1. Search & live quote (Persian ک/ی or Arabic ك/ي both work)
instruments = ts.search("کگل")
quote = ts.quote("کگل")
print(quote.last, quote.close, quote.state_title)

# 2. Backward-adjusted OHLCV + Jalali DataFrame (jalali-pandas v1.0.0)
bars = ts.history("کگل", days=30, adjusted=True)
df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
print(df[["date", "jdate", "open", "high", "low", "close", "volume"]].tail())

# Access Jalali index components, format dates, and aggregate monthly OHLCV
df["j_year"] = df.index.year.astype(int)
df["jdate_str"] = df["date"].jalali.to_jalali().jalali.strftime("%Y-%m-%d")
monthly_ohlcv = df.groupby([df.index.year.astype(int), df.index.month.astype(int)]).agg(
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last"),
    volume=("volume", "sum"),
    value=("value", "sum"),
)

# 3. Individual vs. institutional (حقیقی / حقوقی) flow & order book
ct = ts.client_type_history("کگل", days=5)[-1]
print(f"Real Money Flow: {ct.real_money_flow:,} IRR | Buyer Power: {ct.buyer_power:.2f}")

book = ts.order_book("کگل", include_thresholds=True)
print(book.best_level, book.spread, book.is_buy_queue, book.is_sell_queue)

# 4. Market overview, sectors, indices, shareholders, Codal, ETFs
overview = ts.market_overview(flow=1)
sectors = ts.sectors()
indices = ts.indices(flow=1)
holders = ts.shareholders("کگل")
filings = ts.codal("کگل", limit=3)
etf_nav = ts.etf("بمان")
```

### Sync & Async Clients (`Client` / `AsyncClient`)

Reuse a persistent HTTP/2 session (and in-memory symbol resolver cache) via `Client` (`TSETMCClient`) or `AsyncClient` (`AsyncTSETMCClient`):

```python
import asyncio
import tehran_stocks as ts

# Synchronous client
with ts.Client(timeout=20.0) as client:
    info = client.instruments.info("کگل")
    stats = client.instruments.statistics("کگل")
    watch = client.market.watch()            # ~3,800 live instruments in 1 HTTP call
    flows = client.client_type.all()         # all active client-type snapshots in 1 HTTP call
    tedpix_hist = client.market.index_history("TEDPIX")
    options = client.funds.options(flow=1)

# Asynchronous concurrent requests
async def fetch_concurrent() -> None:
    async with ts.AsyncClient(max_concurrency=8) as client:
        q, bars, book, msgs = await asyncio.gather(
            client.prices.quote("فولاد"),
            client.prices.history("فولاد", days=60, adjusted=True),
            client.prices.order_book("فولاد", include_thresholds=True),
            client.disclosures.messages("فولاد", limit=5),
        )
        print(q.close, len(bars), book.spread, len(msgs))

asyncio.run(fetch_concurrent())
```

#### Client Resource Namespaces

| Namespace | Methods |
| :--- | :--- |
| **`client.instruments`** | `search(query)`, `info(symbol)`, `identity(symbol)`, `statistics(symbol)`, `share_changes(symbol)`, `related(sector_code)` |
| **`client.prices`** | `quote(symbol)`, `history(symbol, days=0, start=None, end=None, adjusted=False)`, `adjustments(symbol)`, `order_book(symbol, *, include_thresholds=False)`, `intraday(symbol, date=None)` |
| **`client.client_type`** | `live(symbol)`, `history(symbol, days=None)`, `all()` |
| **`client.market`** | `watch()`, `overview(flow=1)`, `sectors()`, `indices(flow=1)`, `index_history(code)`, `index_effect(code, flow=1, top=10)`, `top_trades(category=1, flow=1, top=10)` |
| **`client.disclosures`** | `shareholders(symbol)`, `codal(symbol, limit=10)`, `messages(symbol, limit=None)` |
| **`client.funds`** | `etf(symbol)`, `options(flow=1)` |

---

## Opt-In Storage (`SQLiteStore`, `SQLAlchemyStore`, `SyncService`)

When you want local persistence for multi-year backtests, cross-sectional SQL, or offline analysis, explicitly open a store via `open_store()` (or instantiate `SQLiteStore` / `SQLAlchemyStore` directly):

```python
import tehran_stocks as ts
from tehran_stocks.storage import SQLAlchemyStore, SQLiteStore, SyncService, open_store

# Built-in SQLiteStore (stdlib sqlite3, WAL mode, zero external dependencies)
with open_store("./tse.sqlite") as store:
    service = SyncService(store, max_concurrency=8)
    result = service.sync_all(symbols=["کگل", "فولاد"], include_client_types=True)
    print(result.prices, result.client_types)

    # Retrieve backward-adjusted DailyBar objects directly from local storage
    adj_bars = store.get_prices("کگل", adjusted=True)
    df = ts.to_dataframe(adj_bars)

    # Validated read-only SQL (rejects INSERT/UPDATE/DELETE/DROP/unsafe PRAGMAs)
    rows = store.query_readonly(
        "SELECT date, close, volume FROM daily_prices "
        "WHERE ins_code = '35700344742885862' ORDER BY date DESC LIMIT 5"
    )
    print(store.stats())
```

### Connecting PostgreSQL, DuckDB, or Custom Backends

```python
from tehran_stocks.storage import AsyncSyncService, SQLAlchemyStore, open_store

# Auto-routed to SQLAlchemyStore by URI scheme
pg_store = open_store("postgresql://user:password@localhost:5432/tse")   # requires [postgres]
duck_store = open_store("duckdb:///./tse.duckdb")                       # requires [duckdb]
sqla_sqlite = SQLAlchemyStore("./tse.sqlite")
```

**Schema Tables**: `sectors`, `instruments`, `daily_prices`, `client_types`, `price_adjustments`, `share_changes`, `sync_meta`. Custom backends can implement the `@runtime_checkable` `StorageBackend` `Protocol` from `tehran_stocks.storage`.

---

## `tse` CLI Reference

Invoke via `tse`, `tehran-stocks`, or `uvx --from tehran-stocks tse`.
Every data command supports `--json` and `--format table|json|csv`. Errors write cleanly to `stderr` with non-zero exit codes. Global options: `--timeout`, `--proxy`, `--version`.

### On-Demand Market Commands (No Database Required)

```bash
# Search & live quote
tse search کگل --limit 5
tse quote کگل --json

# Historical OHLCV (backward-adjusted, Jalali dates, CSV export)
tse history کگل --days 30 --adjusted --format csv > kgl.csv
tse history کگل --start 1403-01-01 --end 1403-12-29 --json

# Individual vs. institutional (حقیقی/حقوقی) flow & 5-level order book
tse client-type کگل
tse client-type کگل --history --days 10 --json
tse orderbook کگل --thresholds

# Fundamentals, shareholders, dividends/share changes, Codal, supervisor messages
tse info کگل --stats --identity --json
tse info بمان --etf --json
tse shareholders کگل
tse dividends کگل --share-changes --limit 10
tse codal کگل --limit 5
tse messages کگل --limit 5

# Market overview, sectors, indices & live full-market screening
tse market --flow 1
tse sectors --limit 20
tse indices --history TEDPIX --limit 30
tse screen --sort money_flow --limit 15 --json
tse screen --sector فلزات --sort buyer_power --with-flow
```

### Opt-In Database Commands (`tse db`)

```bash
# Initialize schema explicitly
tse db init --db ./tse.sqlite

# Sync sectors, instruments, incremental prices, and client-type flow
tse db sync --db ./tse.sqlite --symbols کگل,فولاد --client-type
tse db sync --db ./tse.sqlite --sector 13 --client-type --concurrency 8
tse db sync --db ./tse.sqlite --all --client-type

# Inspect table counts and date coverage
tse db status --db ./tse.sqlite

# Execute read-only analytical SQL (SELECT / WITH enforced)
tse db query --db ./tse.sqlite "SELECT symbol, name, sector_code FROM instruments LIMIT 10" --json
```

---

## MCP Server Setup (`mcp>=2.0` `MCPServer`)

`tehran-stocks` includes an official `mcp>=2.0` `MCPServer` with strict `stderr`-only logging so `stdio` JSON-RPC stays completely clean.

### Client Configuration (Claude Desktop, Cursor, Codex, Antigravity)

**Zero-install on-demand mode (10 tools + 3 resources):**

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": ["--from", "tehran-stocks", "tse", "mcp"]
    }
  }
}
```

Equivalent direct console entrypoint:

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": ["--from", "tehran-stocks", "tehran-stocks-mcp"]
    }
  }
}
```

**With opt-in local database attached (enables `sync_local_db` & `query_local_db`):**

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": ["--from", "tehran-stocks", "tse", "mcp", "--db", "/path/to/tse.sqlite"],
      "env": {
        "TEHRAN_STOCKS_TIMEOUT": "30"
      }
    }
  }
}
```

You can also run over Streamable HTTP:

```bash
uvx --from tehran-stocks tse mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Configuration flags & environment variables: `--db` (`TEHRAN_STOCKS_DB`), `--transport` (`stdio` | `streamable-http`), `--timeout` (`TEHRAN_STOCKS_TIMEOUT`), `--proxy` (`TEHRAN_STOCKS_PROXY`), `--host`, `--port`.

### MCP Tools & Resources

| Kind | Name / URI | Scope | Description |
| :--- | :--- | :--- | :--- |
| Tool | `search_instruments` | Always | Search tickers, company names, or ISINs |
| Tool | `get_stock_snapshot` | Always | Live quote, fundamentals, valuation, 5-level order book, and client-type flow |
| Tool | `get_price_history` | Always | Daily OHLCV history with optional backward adjustment and Jalali dates |
| Tool | `get_client_type_flow` | Always | Live & historical individual vs. institutional (`حقیقی / حقوقی`) flow and buyer power |
| Tool | `get_order_book` | Always | 5-level bid/ask depth with buy/sell queue (`صف خرید / صف فروش`) detection |
| Tool | `get_fundamentals_and_events` | Always | Info, identity, TSETMC statistics, shareholders, share changes, price adjustments, ETF NAV |
| Tool | `get_market_overview` | Always | TEDPIX, equal-weighted index, breadth spread, market state, sectors, and top trades |
| Tool | `get_indices` | Always | All market/industry indices plus optional daily index history and index-effect movers |
| Tool | `screen_market` | Always | Full live market watch + client-type screener in 2 HTTP calls |
| Tool | `get_disclosures` | Always | Recent Codal announcements and market supervisor messages (halts, AGMs) |
| Tool | `sync_local_db` | With `--db` | Incrementally sync sectors, instruments, prices, and client-type history into local DB |
| Tool | `query_local_db` | With `--db` | Execute validated read-only SQL queries against the local database |
| Resource | `tsetmc://market/overview` | Always | Live market overview JSON |
| Resource | `tsetmc://market/sectors` | Always | Industrial sector definitions and live summary metrics JSON |
| Resource | `tsetmc://instrument/{symbol}` | Always | Live instrument snapshot JSON by symbol, ISIN, or `insCode` |

---

## Agent Skills

Install the `agentskills.io`-compliant skills (`tehran-stocks-setup` and `tehran-stocks-analysis`, including API and TSE domain reference guides) using either `npx skills` or the bundled Python CLI:

### Option A: `npx skills` (from GitHub)

```bash
# Install into the current project
npx skills add ghodsizadeh/tehran-stocks

# Or install globally
npx skills add ghodsizadeh/tehran-stocks -g
```

### Option B: Bundled Wheel Installer (`tse skill`)

Skills are bundled inside the Python package under `tehran_stocks/_skills`:

```bash
# Inspect bundled skills and path
uvx --from tehran-stocks tse skill list
uvx --from tehran-stocks tse skill path

# Install into detected or explicit agent directories
# --target: auto | claude | cursor | codex | antigravity | agents
# --scope:  project | global
# Existing skill installs are preserved by default; pass --overwrite to replace them
uvx --from tehran-stocks tse skill install --target auto --scope project
uvx --from tehran-stocks tse skill install --target claude --scope global --overwrite
```

---

## Migrating from v2 to v3

v3.0 is a clean architectural break replacing legacy `old.tsetmc.com` scraping and global import side effects with the `cdn.tsetmc.com` JSON API and explicit opt-in storage:

| Legacy v2 (Removed in v3.0) | Modern v3.0 Replacement |
| :--- | :--- |
| `import tehran_stocks` auto-creating `~/.tse/stocks.db` | Zero side effects on import; pass a path/URI explicitly to `open_store()` when needed |
| `~/.tse/config.yml` | Explicit `open_store(path_or_uri)`, `--db`, or `TEHRAN_STOCKS_DB` env var |
| `Stocks.query.filter_by(name='كگل').first()` | `ts.search("کگل")`, `ts.quote("کگل")`, or `client.instruments.info("کگل")` |
| `stock.df` | `ts.to_dataframe(ts.history("کگل", adjusted=True))` (with `jalali-pandas>=1.0.0`) |
| `stock.get_instant_detail()` | `ts.quote("کگل")` or `client.prices.quote("کگل")` |
| `stock.get_shares_history()` / `stock.get_dividend()` | `client.instruments.share_changes("کگل")` / `client.prices.adjustments("کگل")` |
| `ts-get init` / `ts-get update` / `ts-get group 34` | `tse db init --db ...` / `tse db sync --db ... --sector 34` (or use `tse quote`, `tse history`, `tse screen` with no DB) |
| `get_all_price()` / `update_group()` | `SyncService(store).sync_all(...)` / `AsyncSyncService(store).sync_all(...)` |

---

## Development & Testing

```bash
# Install locked development environment
uv sync --locked

# Run offline test suite (unit, client, storage, CLI, skills, MCP)
uv run pytest -v

# Run live integration smoke tests against cdn.tsetmc.com
uv run pytest -m live -v

# Build sdist and wheel
uv build
```

## License

MIT License — see [LICENSE](./LICENSE).
