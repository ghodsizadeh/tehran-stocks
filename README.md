# بورس تهران در پایتون — Tehran Stocks (v3)

[![PyPI](https://img.shields.io/pypi/v/tehran-stocks.svg)](https://pypi.org/project/tehran-stocks/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/tehran-stocks.svg)](https://pypi.org/project/tehran-stocks/)
[![Documentation](https://img.shields.io/badge/Docs-%D9%85%D8%B3%D8%AA%D9%86%D8%AF%D8%A7%D8%AA%20%D9%81%D8%A7%D8%B1%D8%B3%DB%8C-0d9488.svg)](https://ghodsizadeh.github.io/tehran-stocks/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/ghodsizadeh/tehran-stocks/blob/master/LICENSE)

[**فارسی (Persian)**](#persian) · [**English**](#english) · [**مستندات کامل فارسی (Documentation)**](https://ghodsizadeh.github.io/tehran-stocks/)

---

<a id="persian"></a>

<div dir="rtl">

## راهنمای فارسی

**نسخهٔ ۳ «بورس تهران در پایتون» (`tehran-stocks`)** یک ابزار مدرن، سریع و آماده برای پایتون، خط فرمان و دستیارهای هوش مصنوعی است که داده‌های بورس و فرابورس تهران را مستقیماً از رابط JSON شرکت مدیریت فناوری بورس تهران (`cdn.tsetmc.com`) دریافت می‌کند.

وارد کردن بسته در پایتون **هیچ پایگاه داده‌ای نمی‌سازد و هیچ فایل تنظیماتی روی سیستم شما ایجاد نمی‌کند**. می‌توانید بلافاصله با کتابخانهٔ پایتون، خط فرمان `tse` یا سرور `MCP` شروع کنید و تنها در صورت نیاز واقعی به آرشیو آفلاین، پایگاه دادهٔ محلی را فعال کنید.

> 📖 **مستندات کامل و راهنماهای سناریومحور (کاملاً فارسی و راست‌به‌چپ):**
> [https://ghodsizadeh.github.io/tehran-stocks/](https://ghodsizadeh.github.io/tehran-stocks/)

### امکانات کلیدی

- **پایتون SDK همگام و ناهمگام (`Client` / `AsyncClient`):** قیمت لحظه‌ای، تاریخچهٔ تعدیل‌شدهٔ OHLCV، جریان پول حقیقی و حقوقی، ۵ سطر سفارش و تشخیص صف خرید/فروش، شاخص کل و هم‌وزن، سهامداران عمده، اطلاعیه‌های کدال، پیام ناظر، حباب NAV صندوق‌های ETF و اختیار معامله.
- **پشتیبانی بومی از فارسی و تقویم جلالی:** یکسان‌سازی خودکار حروف فارسی و عربی (`ک`/`ك`، `ی`/`ي`) و تبدیل مستقیم داده‌ها به `DataFrame` با شاخص `JalaliDatetimeIndex` (`jalali-pandas>=1.0.0`).
- **خط فرمان مدرن (`tse`):** خروجی جدول، `JSON` و `CSV` بدون نیاز به پایگاه داده.
- **آماده برای هوش مصنوعی (`MCP` و `Agent Skills`):** سرور رسمی `MCPServer` (`mcp>=2.0`) برای اتصال به Claude، Cursor، Codex و Antigravity، همراه با مهارت‌های آمادهٔ `tehran-stocks-setup` و `tehran-stocks-analysis`.
- **ذخیره‌سازی اختیاری:** همگام‌سازی افزایشی و پرس‌وجوی SQL فقط‌خواندنی روی **SQLite** (داخلی)، **PostgreSQL** (`[postgres]`) و **DuckDB** (`[duckdb]`).

### نصب

نیازمند **پایتون ۳.۱۱ یا بالاتر** است:

</div>

```bash
# نصب با uv (پیشنهادی)
uv add "tehran-stocks>=3,<4"

# نصب با pip
python -m pip install "tehran-stocks>=3,<4"

# افزونه‌های اختیاری برای PostgreSQL یا DuckDB (SQLite به افزونه نیاز ندارد)
uv add "tehran-stocks[postgres]>=3,<4"
uv add "tehran-stocks[duckdb]>=3,<4"

# اجرای فوری خط فرمان بدون نصب دائمی
uvx --from tehran-stocks tse quote کگل
```

<div dir="rtl">

### استفاده در پایتون

برای اشتراک‌گذاری نشست HTTP/2 و کش شدن شناسهٔ نمادها، از `with ts.Client() as client:` استفاده کنید (یا در کدهای ناهمگام از `async with ts.AsyncClient() as client:`):

</div>

```python
import tehran_stocks as ts

with ts.Client() as client:
    # قیمت لحظه‌ای و پایانی (بر حسب ریال)
    quote = client.prices.quote("کگل")

    # جریان پول حقیقی/حقوقی و قدرت خریدار
    flow = client.client_type.live("کگل")

    # ۵ سطر اول سفارش‌ها همراه با تشخیص صف خرید و فروش
    book = client.prices.order_book("کگل", include_thresholds=True)

    # تاریخچهٔ تعدیل‌شدهٔ ۶۰ روز اخیر
    bars = client.prices.history("کگل", days=60, adjusted=True)

print(f"آخرین معامله: {quote.last:,.0f} ریال | پایانی: {quote.close:,.0f} ریال")
print(f"ورود پول حقیقی: {flow.real_money_flow / 1e10:+,.2f} میلیارد تومان | قدرت خریدار: {flow.buyer_power:.2f}")
print(f"صف خرید: {book.is_buy_queue} | صف فروش: {book.is_sell_queue}")

# تبدیل به DataFrame با تقویم جلالی
df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
print(df[["open", "high", "low", "close", "volume"]].tail())
```

<div dir="rtl">

### استفاده از خط فرمان (`tse`)

فرمان‌های بازار هیچ نیازی به پایگاه داده ندارند و از `--json` و `--format csv` پشتیبانی می‌کنند:

</div>

```bash
tse market                                        # نمای کلی بورس تهران و شاخص کل
tse quote کگل --json                              # قیمت لحظه‌ای در قالب JSON
tse client-type کگل --history --days 10           # سابقهٔ ۱۰ روزهٔ حقیقی و حقوقی
tse orderbook کگل --thresholds                    # ۵ سطر سفارش + وضعیت صف
tse history کگل --days 60 --adjusted --format csv > kgl.csv
tse screen --sort money_flow --limit 15           # ۱۵ نماد برتر از نظر ورود پول حقیقی
```

<div dir="rtl">

### اتصال دستیار هوش مصنوعی با سرور MCP

سرور رسمی MCP (بر پایهٔ `mcp>=2.0`) از هر دو حالت `stdio` (پیش‌فرض) و `streamable-http` پشتیبانی می‌کند. در حالت پیش‌فرض، **۱۰ ابزار زندهٔ بازار** و **۳ منبع `tsetmc://...`** بدون نیاز به پایگاه داده در دسترس مدل قرار می‌گیرند.

این تنظیمات را در فایل پیکربندی MCP کلاینت خود (Claude Desktop، Cursor، Windsurf، Codex یا Antigravity) اضافه کنید:

</div>

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

<div dir="rtl">

اگر می‌خواهید دستیار هوش مصنوعی روی پایگاه دادهٔ محلی همگام‌سازی و پرس‌وجوی SQL فقط‌خواندنی (`sync_local_db` و `query_local_db`) اجرا کند، گزینهٔ `--db` را **فقط برای کلاینت‌های مورد اعتماد** اضافه کنید، یا سرور را در حالت `streamable-http` بالا بیاورید:

</div>

```bash
# اجرای سرور MCP با اتصال به دیتابیس محلی
tse mcp --db ./tse.sqlite

# اجرای سرور MCP به‌صورت شبکه‌ای (Streamable HTTP)
tse mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

<div dir="rtl">

### نصب و استفاده از مهارت‌های عامل هوش مصنوعی (Agent Skills)

دو مهارت تخصصی **`tehran-stocks-setup`** (نصب و پیکربندی) و **`tehran-stocks-analysis`** (پلی‌بوک‌های تحلیل سهم، اسکرین بازار، تقویم جلالی و واژه‌نامهٔ بورس تهران) همراه این بسته ارائه می‌شوند تا دستیارهای کدنویسی قواعد بازار ایران (ریال/تومان، حجم مبنا، تعدیل قیمت و صف‌ها) را دقیق رعایت کنند.

می‌توانید آن‌ها را از طریق `npx skills` یا با نصب‌کنندهٔ داخلی پایتون (`tse skill`) نصب کنید:

</div>

```bash
# روش ۱: نصب مستقیم از گیت‌هاب با npx skills
npx skills add ghodsizadeh/tehran-stocks

# روش ۲: نصب از بستهٔ پایتون (بدون نیاز به Node.js)
tse skill list
tse skill install --target auto --scope project

# نصب برای یک ابزار مشخص (auto | claude | cursor | codex | antigravity | agents)
tse skill install --target claude --scope global
tse skill install --target cursor --scope project

# نصب‌کننده به‌طور پیش‌فرض نسخه‌های موجود را بازنویسی نمی‌کند؛ برای به‌روزرسانی:
tse skill install --target auto --scope project --overwrite
```

<div dir="rtl">

### ذخیره‌سازی اختیاری محلی

برای بک‌تست، تحلیل آفلاین و پرس‌وجوهای SQL:

</div>

```bash
tse db init --db ./tse.sqlite
tse db sync --db ./tse.sqlite --symbols کگل,فولاد --client-type
tse db status --db ./tse.sqlite
tse db query --db ./tse.sqlite "SELECT symbol, name, sector_name FROM instruments LIMIT 10" --json

# یا دانلود فوری تاریخچهٔ کامل بازار از GitHub Releases (حدود ۱۸۴ مگابایت فشرده با zstd):
curl -fL https://github.com/ghodsizadeh/tehran-stocks/releases/download/data-latest/tse.sqlite.zst -o tse.sqlite.zst
zstd -d tse.sqlite.zst -o tse.sqlite
tse db sync --db ./tse.sqlite --incremental --client-type
```

<div dir="rtl">

### مهاجرت از نسخهٔ ۲ و توسعه

- نسخهٔ ۳ با رابط قدیمی نسخهٔ ۲ (`Stocks`، `ts-get` و `~/.tse/`) ناسازگار است. برای مقایسهٔ کامل قبل و بعد، [راهنمای مهاجرت در مستندات](https://ghodsizadeh.github.io/tehran-stocks/concepts/migration-v2-to-v3/) را بخوانید.
- برای اجرای آزمون‌ها و پیش‌نمایش محلی مستندات:

</div>

```bash
uv sync --locked
uv run --locked pytest             # آزمون‌های آفلاین با fixture
uv run --locked pytest -m live     # آزمون‌های زنده با cdn.tsetmc.com
uvx zensical serve                 # پیش‌نمایش محلی مستندات فارسی
```

---

<a id="english"></a>

## English Guide

**Tehran Stocks v3 (`tehran-stocks`)** is a modern, on-demand-first Python SDK, CLI, and official MCP server for the Tehran Stock Exchange (`cdn.tsetmc.com`).

Importing `tehran_stocks` has **zero side effects**—it creates no database, writes no config files, and prompts for nothing. Start immediately from Python, the `tse` CLI, or your AI assistant via MCP, and opt into local storage only when you need offline analytics or SQL queries.

> 📖 **Full Persian (RTL) Scenario-Based Documentation:**
> [https://ghodsizadeh.github.io/tehran-stocks/](https://ghodsizadeh.github.io/tehran-stocks/)

### Highlights

- **Sync & Async Python SDK (`Client` / `AsyncClient`):** Typed quotes, backward-adjusted OHLCV history, individual vs. institutional (`حقیقی / حقوقی`) flows and buyer power, 5-level order books with buy/sell queue detection, market overview, indices, major shareholders, Codal filings, supervisor messages, ETF NAVs, and options.
- **Native Persian & Jalali Support:** Transparent Persian/Arabic character normalization (`ک`/`ك`, `ی`/`ي`), accepts tickers, ISINs, or `insCode`s, and converts directly to `pandas` DataFrames with `JalaliDatetimeIndex` via `jalali-pandas>=1.0.0`.
- **Modern CLI (`tse` / `tehran-stocks`):** Clean tables by default, `--json` for scripts, and `--format csv` for exports—no database required.
- **Agent-Ready (`MCP` + `Agent Skills`):** Official `mcp>=2.0` `MCPServer` (`stdio` and `streamable-http`) plus bundled `tehran-stocks-setup` and `tehran-stocks-analysis` Agent Skills.
- **Opt-In Local Storage:** Built-in `SQLiteStore` (WAL mode, zero extra deps) and `SQLAlchemyStore` (`[postgres]` / `[duckdb]` extras) with incremental async syncing and validated read-only SQL.

### Installation

Requires **Python 3.11+**:

```bash
# With uv (recommended)
uv add "tehran-stocks>=3,<4"

# With pip
python -m pip install "tehran-stocks>=3,<4"

# Optional database drivers (SQLite needs no extra)
uv add "tehran-stocks[postgres]>=3,<4"
uv add "tehran-stocks[duckdb]>=3,<4"

# Zero-install ephemeral CLI execution
uvx --from tehran-stocks tse quote کگل
```

### Python Quickstart

Use `with ts.Client() as client:` (or `async with ts.AsyncClient() as client:`) to reuse an HTTP/2 session and in-memory symbol resolver cache across requests:

```python
import tehran_stocks as ts

with ts.Client() as client:
    quote = client.prices.quote("کگل")
    flow = client.client_type.live("کگل")
    book = client.prices.order_book("کگل", include_thresholds=True)
    bars = client.prices.history("کگل", days=60, adjusted=True)

print(f"Last: {quote.last:,.0f} IRR | Close: {quote.close:,.0f} IRR")
print(f"Real money flow: {flow.real_money_flow / 1e10:+,.2f}B Toman | Buyer power: {flow.buyer_power:.2f}")
print(f"Buy queue: {book.is_buy_queue} | Sell queue: {book.is_sell_queue}")

# Convert to a Jalali-indexed pandas DataFrame
df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
print(df[["open", "high", "low", "close", "volume"]].tail())
```

### Command Line (`tse`)

```bash
tse market                                        # TSE overview & TEDPIX
tse quote کگل --json                              # Live quote as JSON
tse client-type کگل --history --days 10           # 10-day retail vs. institutional flow
tse orderbook کگل --thresholds                    # 5-level order book & queue status
tse history کگل --days 60 --adjusted --format csv > kgl.csv
tse screen --sort money_flow --limit 15           # Screen live market by real money flow
```

### MCP Server for AI Assistants

Configure `tehran-stocks` in Claude Desktop, Cursor, Windsurf, Codex, or Antigravity using `uvx` (`stdio` transport, logs strictly to `stderr`). By default, **10 live market tools** and **3 `tsetmc://` resources** run with no database needed:

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

You can also use the direct console entrypoint `tehran-stocks-mcp`, attach an opt-in database with `--db` (only for trusted clients needing `sync_local_db` and read-only `query_local_db`), or run over Streamable HTTP:

```bash
# Attach a local database for trusted clients
tse mcp --db ./tse.sqlite

# Run Streamable HTTP transport
tse mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

### Installing & Using Agent Skills

Two Agent Skills (`tehran-stocks-setup` and `tehran-stocks-analysis`) are bundled inside the Python wheel and repository so coding/research agents follow TSE domain conventions (IRR vs. Tomans, `baseVol`, backward adjustment, Jalali calendars, and v3 APIs).

```bash
# Option 1: Install from GitHub with npx skills
npx skills add ghodsizadeh/tehran-stocks

# Option 2: Install from the bundled Python wheel (no Node.js required)
tse skill list
tse skill install --target auto --scope project

# Target a specific harness (auto | claude | cursor | codex | antigravity | agents)
tse skill install --target claude --scope global
tse skill install --target cursor --scope project

# Existing installs are preserved by default; pass --overwrite to update them
tse skill install --target auto --scope project --overwrite
```

### Optional Local Storage

Use `open_store()` or `tse db` for offline backtesting and read-only analytical SQL. For full-market history without running an initial backfill, download the pre-built SQLite snapshot (~184 MiB `zstd`) from the rolling [`data-latest`](https://github.com/ghodsizadeh/tehran-stocks/releases/tag/data-latest) release and top it up incrementally:

```bash
# Option A: Download pre-built full-market snapshot (~184 MiB compressed)
curl -fL https://github.com/ghodsizadeh/tehran-stocks/releases/download/data-latest/tse.sqlite.zst -o tse.sqlite.zst
zstd -d tse.sqlite.zst -o tse.sqlite
tse db sync --db ./tse.sqlite --incremental --client-type

# Option B: Sync only specific symbols from scratch
tse db init --db ./tse.sqlite
tse db sync --db ./tse.sqlite --symbols کگل,فولاد --client-type
tse db status --db ./tse.sqlite
tse db query --db ./tse.sqlite "SELECT symbol, name, sector_name FROM instruments LIMIT 10" --json
```

### Migrating from v2

v3 is a breaking release. Replace `Stocks` queries with `ts.search()` / `ts.quote()`, `stock.df` with `ts.to_dataframe(ts.history(symbol, adjusted=True))`, and `ts-get` with `tse`. v3 does not automatically read or migrate `~/.tse/`; back up any legacy database you still need.

### Development & Testing

```bash
uv sync --locked
uv run --locked pytest             # Offline fixture test suite
uv run --locked pytest -m live     # Live integration tests against cdn.tsetmc.com
uvx zensical serve                 # Local preview of the Persian RTL docs site
```

[MIT License](https://github.com/ghodsizadeh/tehran-stocks/blob/master/LICENSE)
