# `tehran-stocks` v3.0 API, CLI & MCP Reference

Exact reference for the `tehran-stocks` v3.0 Python SDK, `jalali-pandas` v1.0.0 integration, opt-in `StorageBackend`, `tse` Typer CLI, and `MCPServer` (`mcp>=2.0`).

---

## 1. Python SDK (`import tehran_stocks as ts`)

Importing `tehran_stocks` has **zero side effects** (no file creation, no DB auto-init, no prompts).

### Top-Level Convenience Functions

```python
import tehran_stocks as ts

ts.search("کگل")                                          # -> list[Instrument]
ts.quote("کگل")                                           # -> Quote
ts.history("کگل", days=0, start=None, end=None, adjusted=False)  # -> list[DailyBar]
ts.client_type("کگل")                                     # -> ClientTypeLive
ts.client_type_history("کگل", days=None)                  # -> list[ClientTypeDaily]
ts.order_book("کگل", include_thresholds=False)            # -> OrderBook
ts.market_overview(flow=1)                                # -> MarketOverview
ts.sectors()                                              # -> list[Sector]
ts.indices(flow=1)                                        # -> list[IndexQuote]
ts.shareholders("کگل")                                    # -> list[Shareholder]
ts.codal("کگل", limit=10)                                 # -> list[CodalAnnouncement]
ts.etf("بمان")                                            # -> ETFInfo
ts.to_dataframe(records, jalali=True, index_by_date=True) # -> pd.DataFrame
ts.adjust_prices(bars, adjustments)                       # -> list[DailyBar]
```

### Sync & Async Clients

Built on `httpx2[http2]>=2.16.2` with browser `User-Agent` headers, retries with exponential backoff, rate-limit handling, and an in-memory TTL symbol/ISIN/`insCode` resolver cache (`normalize_persian()` transparent handling).

```python
from tehran_stocks import TSETMCClient, AsyncTSETMCClient
# Convenience aliases: ts.Client and ts.AsyncClient

with ts.Client() as client:
    quote = client.prices.quote("کگل")

async with ts.AsyncClient() as client:
    quote = await client.prices.quote("کگل")
```

### Modular Resource Namespaces & Verified `cdn.tsetmc.com` Endpoints

Every resource module exposes both Sync and Async methods on `client.<namespace>`:

| Namespace | Method | `cdn.tsetmc.com` Endpoint | Purpose |
| :--- | :--- | :--- | :--- |
| **`instruments`** | `search(query)` | `/api/Instrument/GetInstrumentSearch/{query}` | Search `insCode`, `lVal18AFC`, `lVal30`, `cIsin`, `flowTitle`, `zTitad` |
| **`instruments`** | `info(symbol)` | `/api/Instrument/GetInstrumentInfo/{insCode}` | EPS (`estimatedEPS`, `sectorPE`), sector, `staticThreshold`, week/year ranges, `zTitad`, `baseVol` |
| **`instruments`** | `identity(symbol)` | `/api/Instrument/GetInstrumentIdentity/{insCode}` | Legal identity, `sector`, `subSector`, `yMarNSC`, `flow` |
| **`instruments`** | `statistics(symbol)` | `/api/MarketData/GetInstrumentStatistic/{insCode}` | Computed liquidity, rank, and rolling average metrics |
| **`instruments`** | `share_changes(symbol)` | `/api/Instrument/GetInstrumentShareChange/{insCode}` | `dEven`, `numberOfShareNew`, `numberOfShareOld` |
| **`instruments`** | `related(sector_code)` | `/api/ClosingPrice/GetRelatedCompany/{sectorCode}` | Peer instruments in the same industry group |
| **`prices`** | `quote(symbol)` | `/api/ClosingPrice/GetClosingPriceInfo/{insCode}` | Live `pDrCotVal`, `pClosing`, OHLC, `zTotTran`, `qTotTran5J`, `qTotCap`, `priceChange`, `instrumentState` |
| **`prices`** | `history(symbol, days=0, start=None, end=None, adjusted=False)` | `/api/ClosingPrice/GetClosingPriceDailyList/{insCode}/{days}` | Daily OHLCV (`0` = full history; `adjusted=True` applies `adjust_prices()` using `GetPriceAdjustList`) |
| **`prices`** | `adjustments(symbol)` | `/api/ClosingPrice/GetPriceAdjustList/{insCode}` | `dEven`, `pClosing`, `pClosingNotAdjusted`, `corporateTypeCode` |
| **`prices`** | `order_book(symbol, *, include_thresholds=False)` | `/api/BestLimits/{insCode}` | 5-level live bid/ask book (`include_thresholds=True` fetches `pMin`/`pMax` for queue flags) |
| **`prices`** | `intraday(symbol, date=None)` | `/api/ClosingPrice/GetClosingPriceHistory/{insCode}/{dEven}` | Intraday closing/last price ticks for a session |
| **`client_type`** | `live(symbol)` | `/api/ClientType/GetClientType/{insCode}/1/0` | Live individual (`I` / حقیقی) vs. institutional (`N` / حقوقی) volume & counts |
| **`client_type`** | `history(symbol, days=None)` | `/api/ClientType/GetClientTypeHistory/{insCode}` | Daily history of individual & institutional volume, value, and trader counts |
| **`client_type`** | `all()` | `/api/ClientType/GetClientTypeAll` | Live individual/institutional snapshot for all active instruments in 1 HTTP call |
| **`market`** | `watch()` | `/api/ClosingPrice/GetMarketWatch` | Live full-market snapshot (~3,800 instruments + `eps`, `pe`, `ztd`, `bv`, `pMax`/`pMin`, `blDs`) in 1 HTTP call |
| **`market`** | `overview(flow=1)` | `/api/MarketData/GetMarketOverview/{flow}` | TEDPIX / Farabourse index, equal-weighted index, market state, total value/volume/trades |
| **`market`** | `sectors()` | `/api/StaticData/GetStaticData` + `/api/MarketData/GetSectorsSummary` | All `IndustrialGroup` definitions merged with live sector metrics |
| **`market`** | `indices(flow=1)` | `/api/Index/GetIndexB1LastAll/All/{flow}` | All 57 live market and industry indices |
| **`market`** | `index_history(code)` | `/api/Index/GetIndexB2History/{insCode}` | Daily index history (accepts `insCode` or `'TEDPIX'` / `'شاخص کل'`) |
| **`market`** | `index_effect(code, flow=1, top=10)` | `/api/Index/GetInstEffect/{insCode}/{flow}/{top}` | Top instruments impacting the index |
| **`market`** | `top_trades(category=1, flow=1, top=10)` | `/api/ClosingPrice/GetTradeTop/{category}/{flow}/{top}` | Top market movers by volume/value/trades |
| **`disclosures`** | `shareholders(symbol)` | `/api/Shareholder/GetInstrumentShareHolderLast/{insCode}` | Major shareholders (`>1%`), share count, ownership %, daily change |
| **`disclosures`** | `codal(symbol, limit=10)` | `/api/Codal/GetPreparedDataByInsCode/{limit}/{insCode}` | Codal announcements, financial statements, tracing numbers |
| **`disclosures`** | `messages(symbol, limit=None)` | `/api/Msg/GetMsgByInsCode/{insCode}` | Market supervisor messages (halts, reopenings, AGMs) |
| **`funds`** | `etf(symbol)` | `/api/Fund/GetETFByInsCode/{insCode}` | ETF `redemption_nav`, `subscription_nav`, `statistical_nav`, `nav_premium_pct` |
| **`funds`** | `options(flow=1)` | `/api/Instrument/GetInstrumentOptionMarketWatch/{flow}` | Live options chain (call and put sides) |

### Domain Models & Exceptions

**Frozen Dataclass Models** (`tehran_stocks.types`, `@dataclass(frozen=True, slots=True)` with `.to_dict()` & `.from_tsetmc()`):
- `instrument`: `Instrument`, `InstrumentInfo`, `InstrumentIdentity`, `InstrumentStatistic`, `ShareChange`
- `price`: `Quote`, `DailyBar`, `PriceAdjustment`, `OrderBookLevel`, `OrderBook` (`is_buy_queue`, `is_sell_queue`, `spread`, `total_bid_volume`, `total_ask_volume`), `IntradayTick`
- `client_type`: `ClientTypeLive`, `ClientTypeDaily` (`net_i_volume`, `real_money_flow`, `buy_per_capita`, `sell_per_capita`, `buyer_power`, `volume_buyer_power`)
- `market`: `MarketWatchItem`, `MarketOverview`, `Sector`, `IndexQuote`, `IndexBar`, `IndexEffectItem`
- `disclosure`: `Shareholder`, `CodalAnnouncement`, `SupervisorMessage`, `ETFInfo` (`nav_premium_pct`), `OptionWatchItem`

**Exceptions** (`tehran_stocks.exceptions`):
- `TehranStocksError` (base exception)
- `TSETMCError(message, status_code=None, url=None)`
- `RateLimitError`
- `InstrumentNotFoundError`
- `StorageError`

---

## 2. `jalali-pandas` v1.0.0 & Analytics Utilities

`tehran_stocks.utils.analytics.to_dataframe(records, jalali=True, index_by_date=True)` converts dataclass sequences or dicts into `pandas.DataFrame`s:
- `jalali=True`: adds `df["jdate"]` (`jalali_datetime` dtype) via `jalali_pandas.to_jalali_datetime(dt)`
- `index_by_date=True` + `jalali=True`: sets `df.index` to `jalali_pandas.JalaliDatetimeIndex(j_series, name="jdate")`

```python
import jalali_pandas
from jalali_pandas import (
    JalaliDatetimeIndex,
    JalaliMonthEnd,
    JalaliQuarterEnd,
    JalaliYearEnd,
    jalali_date_range,
    to_jalali_datetime,
)
import tehran_stocks as ts

# 1. Convert TSETMC bars to a Jalali-indexed DataFrame
bars = ts.history("فولاد", days=365, adjusted=True)
df = ts.to_dataframe(bars, jalali=True, index_by_date=True)

# 2. Access Jalali index components directly and build calendar-accurate OHLCV monthly bars
j_year = df.index.year.astype(int)
j_month = df.index.month.astype(int)
monthly = df.groupby([j_year, j_month]).agg(
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last"),
    volume=("volume", "sum"),
    value=("value", "sum"),
)
monthly.index.names = ["j_year", "j_month"]

# 3. Convert Gregorian datetime Series -> jdatetime Series via .jalali accessor
# Note: in jalali-pandas 1.0.0, add a jdatetime column via .jalali.to_jalali()
# before using DataFrame .jalali helpers (.groupby / .filter_by_year) or .jalali.strftime
df["jdate_obj"] = df["date"].jalali.to_jalali()
df["jdate_str"] = df["jdate_obj"].jalali.strftime("%Y-%m-%d")

# 4. DataFrame .jalali accessor (requires a jdatetime column such as jdate_obj above)
quarterly_means = df.jalali.groupby("yq").mean()      # 'year'|'month'|'ym'|'yq'|'ymd'|'md'
df_1403 = df.jalali.filter_by_year(1403)

# 5. Construct Jalali date ranges
j_range = jalali_date_range("1403-01-01", periods=10, freq="D")
```

Additional utilities (`tehran_stocks.utils`):
- `persian.py`: `normalize_persian(text)` (unifies Arabic `ك`/`ي`/`ة` -> Persian `ک`/`ی`/`ه`, converts Persian/Arabic digits to ASCII)
- `jalali.py`: `int_to_date`, `gregorian_to_jalali`, `jalali_to_gregorian`, `parse_tsetmc_time`, `tsetmc_datetime`
- `analytics.py`: `adjust_prices(bars, adjustments)` + `to_dataframe(records, jalali=True, index_by_date=True)`

---

## 3. Opt-In Storage Layer (`tehran_stocks.storage`)

All persistence is opt-in and user-managed.

### Factory & Built-in Backends

```python
from tehran_stocks.storage import (
    AsyncSyncService,
    SQLAlchemyStore,
    SQLiteStore,
    StorageBackend,
    SyncProgress,
    SyncResult,
    SyncService,
    open_store,
)

store = open_store("./tse.sqlite")                      # SQLiteStore (stdlib sqlite3, WAL, ?mode=ro)
store = open_store("postgresql://user:pw@host/tse")     # SQLAlchemyStore (requires [postgres])
store = open_store("duckdb:///./tse.duckdb")            # SQLAlchemyStore (requires [duckdb])
```

### Schema Tables

`sectors`, `instruments`, `daily_prices`, `client_types`, `price_adjustments`, `share_changes`, `sync_meta`

### `StorageBackend` Protocol & `SyncService`

- `StorageBackend` methods: `init_schema()`, `close()`, `upsert_sectors(...)`, `upsert_instruments(...)`, `upsert_prices(...)`, `upsert_client_types(...)`, `upsert_adjustments(...)`, `upsert_share_changes(...)`, `list_instruments(...)`, `resolve_ins_code(...)`, `get_last_price_date(...)`, `get_last_client_type_date(...)`, `get_prices(..., adjusted=False)`, `get_adjustments(...)`, `get_client_types(...)`, `query_readonly(sql)`, `stats()`.
- `SyncService(store, ...)` / `AsyncSyncService(store, ...)` methods:
  - `sync_instruments(on_progress=...)` — syncs all ~3,800 instruments and sectors in 2 HTTP calls (`GetStaticData` + `GetMarketWatch`)
  - `sync_prices(symbols=..., sector=..., all_instruments=False, incremental=True, ...)`
  - `sync_client_types(symbols=..., sector=..., all_instruments=False, incremental=True, ...)`
  - `sync_all(symbols=..., sector=..., all_instruments=True, incremental=True, include_client_types=True, ...)`

---

## 4. `tse` Typer CLI Reference

Available via `tse`, `tehran-stocks`, or `uvx --from tehran-stocks tse`. Global options: `--timeout`, `--proxy`, `--version`. Data commands support `--json` and `--format table|json|csv`; errors print cleanly to `stderr` with non-zero exit codes (`2` validation, `3` not found, `4` rate limit, `5` TSETMC error, `6` storage error).

### On-Demand Commands (No Database Required)

| Command | Key Options | Purpose |
| :--- | :--- | :--- |
| `tse search <query>` | `--limit` | Search symbols/names/ISINs |
| `tse quote <symbol>` | — | Live quote snapshot |
| `tse history <symbol>` | `--days`, `--start`, `--end`, `--adjusted`, `--jalali/--no-jalali` | Historical daily OHLCV |
| `tse client-type <symbol>` | `--history`, `--days` | Individual vs. institutional (`حقیقی / حقوقی`) flow |
| `tse orderbook <symbol>` | `--thresholds` | 5-level BestLimits order book + buy/sell queue status |
| `tse info <symbol>` | `--stats`, `--identity`, `--etf` | Fundamentals, EPS, sector P/E, thresholds, stats, ETF NAV |
| `tse shareholders <symbol>` | — | Major shareholders (`>1%`) |
| `tse dividends <symbol>` | `--share-changes`, `--limit` | Price adjustments / dividends / share changes |
| `tse market` | `--flow` | Market overview (TEDPIX, equal-weighted, market state) |
| `tse sectors` | `--limit` | Sector definitions & live metrics |
| `tse indices` | `--flow`, `--history`, `--limit` | All market/industry indices or index history (`TEDPIX`) |
| `tse codal <symbol>` | `--limit` | Codal filings and disclosures |
| `tse messages <symbol>` | `--limit` | Market supervisor messages (halts, reopenings, AGMs) |
| `tse screen` | `--sector`, `--sort`, `--limit`, `--with-flow`, `--asc` | Live market watch screener (`value\|volume\|change\|money_flow\|buyer_power`) |

### Database, MCP & Skill Subcommands

| Command | Purpose |
| :--- | :--- |
| `tse db init --db <path_or_uri>` | Initialize schema in a SQLite file or SQLAlchemy URI |
| `tse db sync --db <path_or_uri>` | Incremental sync (`--symbols`, `--sector`, `--all`, `--client-type`, `--share-changes`, `--concurrency`) |
| `tse db status --db <path_or_uri>` | Inspect database tables and sync coverage |
| `tse db query --db <path_or_uri> "<SELECT ...>"` | Execute read-only analytical SQL (`SELECT`/`WITH` enforced) |
| `tse mcp` | Launch official `MCPServer` (`--db`, `--transport stdio\|streamable-http`, `--timeout`, `--proxy`, `--host`, `--port`) |
| `tse skill list` | List bundled Agent Skills inside the package |
| `tse skill path [name]` | Print filesystem path to bundled Agent Skills |
| `tse skill install` | Install skills (`--target auto\|claude\|cursor\|codex\|antigravity\|agents`, `--scope project\|global`, `--skill`, `--dir`) |

---

## 5. MCP Server (`mcp>=2.0` `MCPServer`) Reference

Entrypoints: `tse mcp` or `tehran-stocks-mcp`. Uses `from mcp.server.mcpserver import MCPServer` with strict `stderr`-only logging (`stdout` reserved for JSON-RPC).

### Configuration

- Flags: `--db`, `--transport stdio|streamable-http`, `--timeout`, `--proxy`, `--host`, `--port` (`--log-level` on `tehran-stocks-mcp`)
- Environment variables: `TEHRAN_STOCKS_DB`, `TEHRAN_STOCKS_TIMEOUT`, `TEHRAN_STOCKS_PROXY`

### Tools (10 On-Demand + 2 Opt-In DB)

**Always Available (On-Demand)**:
1. `search_instruments(query, limit=15)` — Search tickers/names/ISINs
2. `get_stock_snapshot(symbol, include_order_book=True, include_client_type=True)` — Live quote, fundamentals, valuation, order book, client-type flow
3. `get_price_history(symbol, days=None, start=None, end=None, adjusted=True, include_jalali=True, limit=None)` — Daily OHLCV with backward adjustment & Jalali dates (`days=None` defaults to `0` when `start`/`end` supplied, else `30`)
4. `get_client_type_flow(symbol, days=10)` — Live & historical individual/institutional flows + buyer power
5. `get_order_book(symbol, include_thresholds=True)` — 5-level bid/ask order book & buy/sell queue flags
6. `get_fundamentals_and_events(symbol, include_statistics=True, include_shareholders=True, include_share_changes=True, include_adjustments=True, include_etf=False)` — Fundamentals, identity, statistics, shareholders, corporate actions, ETF NAV
7. `get_market_overview(flow=1, include_sectors=True, include_top_trades=False, top_limit=10)` — TEDPIX, equal-weighted index, breadth spread, totals & sectors
8. `get_indices(flow=1, index_code=None, history_days=30, include_effect=True)` — All 57 indices plus optional daily history & index-effect movers
9. `screen_market(sector_code=None, query=None, min_value=None, min_volume=None, min_change_pct=None, max_change_pct=None, min_buyer_power=None, min_real_money_flow=None, queue_only=None, sort_by="value", ascending=False, limit=20)` — Full live market watch + flow screener in 2 HTTP calls
10. `get_disclosures(symbol, codal_limit=10, messages_limit=10)` — Codal announcements & supervisor messages

**Active When `--db` / `TEHRAN_STOCKS_DB` Is Set**:
11. `sync_local_db(symbols=None, sector=None, all_instruments=False, include_client_type=True)` — Run incremental `AsyncSyncService` into the configured store
12. `query_local_db(sql, limit=200)` — Execute read-only SQL queries (mutating queries blocked)

### MCP Resources (3)

- `tsetmc://market/overview` — Live market overview JSON
- `tsetmc://market/sectors` — Industrial sector definitions & summary metrics JSON
- `tsetmc://instrument/{symbol}` — Live instrument snapshot JSON by symbol/ISIN/`insCode`
