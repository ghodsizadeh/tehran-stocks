---
name: tehran-stocks-analysis
description: >-
  Analyze Tehran Stock Exchange (TSETMC) equities, indices, ETFs, and options using
  tehran-stocks v3.0 via MCP tools, the tse CLI (--json/--format csv), or Python
  (TSETMCClient, pandas, jalali-pandas v1.0.0, SQLiteStore/SQLAlchemyStore). Use when
  fetching quotes, adjusted OHLCV, حقیقی/حقوقی real money flow, buyer power, 5-level
  order books, buy/sell queues, TEDPIX, Codal disclosures, or Jalali time series.
license: MIT
compatibility: >-
  Requires tehran-stocks >=3.0.0 (Python 3.11+, httpx2, pandas, jalali-pandas>=1.0.0,
  typer, mcp>=2.0, sqlalchemy>=2.0) and access to cdn.tsetmc.com or a synced
  StorageBackend database.
metadata:
  author: tehran-stocks
  version: "3.0.0"
  repository: "https://github.com/ghodsizadeh/tehran-stocks"
  homepage: "https://ghodsizadeh.github.io/tehran-stocks/"
---

# Tehran Stocks Analysis (v3.0)

Use this skill to inspect, screen, and analyze Iranian capital market data from TSETMC (`cdn.tsetmc.com`) accurately.

- Need exact Python SDK classes, CLI flags, MCP tools, or storage APIs? Read [api-reference.md](./references/api-reference.md).
- Need Tehran Stock Exchange domain formulas, Arabic/Persian quirks, or market rules? Read [tse-domain-glossary.md](./references/tse-domain-glossary.md).

---

## 1. Choose the Right Interface

| Situation | Use This Interface | Why |
| :--- | :--- | :--- |
| `tehran-stocks` MCP tools are connected | **MCP Tools** (`get_stock_snapshot`, `get_client_type_flow`, `screen_market`, …) | Structured schemas, built-in resources, zero shell setup |
| Fast shell checks, piping to `jq`, or ad-hoc DB queries | **`tse` CLI** (`--json` or `--format csv`) | One-liner execution via `tse` or `uvx --from tehran-stocks tse` |
| Backtesting, multi-stock indicators, Jalali resampling, plots | **Python SDK + `pandas` + `jalali-pandas` v1.0.0** | Vectorized `DataFrame` analytics, adjusted OHLCV, `JalaliDatetimeIndex` |
| Cross-sectional historical queries across hundreds/thousands of symbols | **`SQLiteStore` / `SQLAlchemyStore` + `SyncService`** | Local incremental warehouse with read-only SQL (`query_readonly`) |

---

## 2. Core Analysis Playbooks

### Playbook A: Single-Stock Deep Dive (Quote + Flow + Order Book + Catalysts)

Always combine **price**, **real money flow (`حقیقی / حقوقی`)**, **order book queues**, and **supervisor/Codal events**—never judge a TSE stock on price alone.

1. **Resolve & Snapshot**: Accept symbol (`کگل`, `فولاد`), ISIN, or `insCode` (`35700344742885862`).
   - MCP: `search_instruments` → `get_stock_snapshot`
   - CLI: `tse quote کگل --json` and `tse info کگل --stats --identity --json`
   - Check both `last` (`pDrCotVal`) and `close` (**official volume-weighted close** `pClosing`, affected by `baseVol`).
2. **Institutional vs. Individual Flow (`حقیقی / حقوقی`)**:
   - MCP: `get_client_type_flow`
   - CLI: `tse client-type کگل --json` (or `--history --days 10 --json`)
   - Report `real_money_flow` (`buy_i_value - sell_i_value`), `buy_per_capita`, `sell_per_capita`, and `buyer_power` (`> 1.0` signals stronger per-capita individual buying).
3. **5-Level Order Book & Queue Liquidity**:
   - MCP: `get_order_book` (includes `pMin`/`pMax` thresholds by default)
   - CLI: `tse orderbook کگل --thresholds --json`
   - Check `is_buy_queue` (**صف خرید**: best bid at `price_max_allowed`, zero ask supply) and `is_sell_queue` (**صف فروش**: best ask at `price_min_allowed`, zero bid demand).
4. **Fundamentals, Shareholders & Catalysts**:
   - MCP: `get_fundamentals_and_events` and `get_disclosures`
   - CLI: `tse shareholders کگل --json`, `tse dividends کگل --share-changes --json`, `tse codal کگل --json`, `tse messages کگل --json`
   - Always check `messages` when volume is `0` or trading paused (halts before AGMs or material disclosures are routine).

---

### Playbook B: Market Overview & Cross-Market Screening

`cdn.tsetmc.com` serves the entire live market (~3,800 instruments + 5-level books) in `GetMarketWatch` and all client-type flows in `GetClientTypeAll`—**1 HTTP call each**.

- **MCP**:
  - Read `tsetmc://market/overview` and `tsetmc://market/sectors` (or call `get_market_overview` and `get_indices`)
  - Compare **TEDPIX (`شاخص کل`, `32097828799138957`)** against the **Equal-Weighted Index (`شاخص کل هم‌وزن`)** (`breadth.breadth_spread_pct`) to detect mega-cap vs. small/mid-cap divergence
  - Screen candidates with `screen_market` (supports `sector_code`, `min_buyer_power`, `min_real_money_flow`, `queue_only="buy"|"sell"`, `sort_by`)
- **CLI**:
  ```bash
  tse market --json
  tse indices --json
  tse sectors --json
  tse screen --sort money_flow --limit 20 --json
  ```
- **Python**:
  ```python
  import tehran_stocks as ts

  with ts.Client() as client:
      overview = client.market.overview(flow=1)
      watch = client.market.watch()            # ~3,800 instruments in 1 HTTP call
      flows = client.client_type.all()         # ~2,300+ client-type rows in 1 HTTP call
  ```

---

### Playbook C: Adjusted Price History & Jalali Analytics (`jalali-pandas` v1.0.0)

Raw TSE prices drop sharply on dividend (`مجمع`) and capital-increase (`افزایش سرمایه`) ex-dates. **Always pass `adjusted=True`** (which applies `GetPriceAdjustList` backward factors via `adjust_prices()`) for multi-period returns, moving averages, or technical indicators.

```python
import jalali_pandas  # registers .jalali Series & DataFrame accessors
import tehran_stocks as ts

with ts.Client() as client:
    adj_bars = client.prices.history("کگل", days=0, adjusted=True)

# Convert to DataFrame with Jalali column ("jdate") & JalaliDatetimeIndex
df = ts.to_dataframe(adj_bars, jalali=True, index_by_date=True)

# Jalali year/month components come straight from the JalaliDatetimeIndex
j_year = df.index.year.astype(int)
j_month = df.index.month.astype(int)
df["jdate_str"] = df["date"].jalali.to_jalali().jalali.strftime("%Y-%m-%d")

# Jalali calendar-aware monthly bars (respects 31/30/29-30 day months).
# Aggregate each column correctly: never sum OHLC prices, only volume/value.
monthly = df.groupby([j_year, j_month]).agg(
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last"),
    volume=("volume", "sum"),
    value=("value", "sum"),
)
monthly.index.names = ["j_year", "j_month"]

# Total traded volume per Jalali year
yearly_volume = df.groupby(j_year)["volume"].sum()
```

CLI equivalents for quick inspection:

```bash
tse history کگل --days 0 --adjusted --json
tse dividends کگل --share-changes --json
```

---

### Playbook D: Offline Quant Research with `SQLiteStore` / `SQLAlchemyStore`

Use opt-in local persistence when running backtests or scanning historical flows across many tickers:

```python
import asyncio
import tehran_stocks as ts
from tehran_stocks.storage import AsyncSyncService, open_store

store = open_store("./tse.sqlite")  # or "postgresql://..." / "duckdb:///./tse.duckdb"

async def sync() -> None:
    async with ts.AsyncClient() as client:
        service = AsyncSyncService(store, client=client)
        await service.sync_all(symbols=["کگل"], include_client_types=True)

asyncio.run(sync())

# Fetch backward-adjusted bars directly from local DB
bars = store.get_prices("کگل", adjusted=True)

# Or run validated read-only analytical SQL (safe for agents)
rows = store.query_readonly(
    "SELECT date, close, volume FROM daily_prices "
    "WHERE ins_code = '35700344742885862' ORDER BY date DESC LIMIT 30"
)
store.close()
```

Or via CLI / MCP when `--db` is attached:

```bash
tse db sync --db ./tse.sqlite --symbols کگل --client-type
tse db query --db ./tse.sqlite "SELECT COUNT(*) AS instruments FROM instruments" --json
```

---

### Playbook E: ETF NAV & Premium/Discount Check

For fixed-income, gold, or equity ETFs, compare traded price (`pDrCotVal` / `pClosing`) against **Cancellation NAV (`redemption_nav` / `NAV ابطال`)** and **Statistical NAV (`statistical_nav` / `NAV آماری`)** using:
- Python: `client.funds.etf(symbol)` (or `ts.etf(symbol)`) returning `ETFInfo` (`redemption_nav`, `subscription_nav`, `statistical_nav`, `nav_premium_pct`)
- CLI: `tse info بمان --etf --json`
- MCP: `get_fundamentals_and_events(symbol="بمان", include_etf=True)`

---

## 3. Critical Guardrails

1. **Persian vs. Arabic Characters**: TSETMC mixes Arabic `ك`/`ي` and Persian `ک`/`ی`. `tehran-stocks` normalizes lookups automatically, so users can pass `"کگل"`, `"كگل"`, ISINs, or `insCode` seamlessly; normalize raw string comparisons with `ts.normalize_persian()` when filtering manually.
2. **State Rials vs. Tomans Explicitly**: TSETMC APIs return prices and trade values in **Iranian Rials (IRR / ریال)** (`1 Toman = 10 IRR`). Always label currency units clearly when summarizing values.
3. **Distinguish `last` (`pDrCotVal`) vs. `close` (`pClosing`)**: Report both last traded price and official volume-weighted closing price (affected by `baseVol`) so queue days or thin sessions are not misinterpreted.
4. **Never Bypass Read-Only SQL**: `query_local_db` (MCP), `tse db query` (CLI), and `store.query_readonly()` reject mutating statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, unsafe `PRAGMA`s).
5. **Account for Trading Week & Halts**: TSE trades **Saturday–Wednesday** (closed Thu/Fri and Iranian public holidays). Always inspect supervisor messages before treating missing/zero-volume days as API errors.
