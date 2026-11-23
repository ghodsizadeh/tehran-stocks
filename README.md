# Tehran Stocks — بورس تهران در پایتون

[![PyPI](https://img.shields.io/pypi/v/tehran-stocks.svg)](https://pypi.org/project/tehran-stocks/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Tehran Stocks v3** fetches Tehran Stock Exchange data directly from the TSETMC JSON API. Importing the package doesn’t create a database or write config files. Start with the Python SDK or the `tse` command line, and enable local storage only if you need it.

<p lang="fa" dir="rtl">
نسخهٔ ۳ «بورس تهران در پایتون» داده‌های بازار را مستقیماً از رابط JSON شرکت مدیریت فناوری بورس تهران (TSETMC) می‌گیرد. وارد کردن بسته در پایتون نه پایگاه داده می‌سازد و نه فایل تنظیمات می‌نویسد. با کتابخانهٔ پایتون یا فرمان <code>tse</code> شروع کنید و فقط در صورت نیاز داده‌ها را ذخیره کنید.
</p>

[Install / نصب](#install) · [Python](#python) · [CLI / خط فرمان](#cli) · [Storage / ذخیره‌سازی](#storage) · [MCP & Skills](#agents) · [Migration / مهاجرت](#migration)

<a id="install"></a>
## Install / نصب

v3 requires **Python 3.11+**. These examples are for v3; an unpinned PyPI install may still give you v2. Before v3 is published, install from a checkout of the v3 source with `python -m pip install .`.

<p lang="fa" dir="rtl">
نسخهٔ ۳ به پایتون ۳٫۱۱ یا بالاتر نیاز دارد. مثال‌های این صفحه برای نسخهٔ ۳ هستند؛ نصب از PyPI بدون تعیین نسخه ممکن است هنوز نسخهٔ ۲ را نصب کند. تا پیش از انتشار نسخهٔ ۳، فرمان <code>python -m pip install .</code> را در پوشهٔ کد منبع همین نسخه اجرا کنید.
</p>

```bash
# After v3 is published / پس از انتشار نسخهٔ ۳
python -m pip install 'tehran-stocks>=3,<4'
# Or with uv / یا با uv
uv add 'tehran-stocks>=3,<4'
```

<a id="python"></a>
## Python quickstart / شروع سریع با پایتون

Get typed quotes, adjusted OHLCV history, individual and institutional trades, order books, indices, and Codal disclosures. Tickers, ISINs, and `insCode`s are accepted; Persian and Arabic character variants are normalized. Use `Client` or `AsyncClient` to reuse an HTTP/2 session across requests.

<p lang="fa" dir="rtl">
قیمت‌ها، تاریخچهٔ تعدیل‌شده، آمار معاملات حقیقی و حقوقی، سفارش‌های خرید و فروش، شاخص‌ها و اطلاعیه‌های کدال به‌صورت مدل‌های نوع‌دار برمی‌گردند. نماد، شناسهٔ ISIN یا شناسهٔ <code>insCode</code> را می‌توانید وارد کنید؛ شکل‌های فارسی و عربی حروف به‌طور خودکار یکسان می‌شوند. برای استفادهٔ مجدد از اتصال HTTP/2 در چند درخواست، از <code>Client</code> یا <code>AsyncClient</code> استفاده کنید.
</p>

```python
import tehran_stocks as ts

with ts.Client() as client:
    quote = client.prices.quote("کگل")
    bars = client.prices.history("کگل", days=30, adjusted=True)

print(quote.last, quote.close)  # Last trade and closing price, in IRR
print(ts.to_dataframe(bars, jalali=True).tail())
```

<a id="cli"></a>
## Command line / خط فرمان

`tse` (also `tehran-stocks`) displays tables by default. Use `--json` in scripts and `--format csv` to export data. None of these examples needs a database.

<p lang="fa" dir="rtl">
فرمان <code>tse</code> (یا <code>tehran-stocks</code>) خروجی را به‌طور پیش‌فرض به شکل جدول نشان می‌دهد. برای استفاده در اسکریپت‌ها <code>--json</code> و برای خروجی CSV گزینهٔ <code>--format csv</code> را به کار ببرید. فرمان‌های زیر به پایگاه داده نیاز ندارند.
</p>

```bash
tse quote کگل --json
tse history کگل --days 30 --adjusted --format csv > kgl.csv
tse screen --sort money_flow --limit 10
tse --help
```

<a id="storage"></a>
## Optional storage / ذخیره‌سازی اختیاری

Use `open_store()` or `tse db` to keep a local copy for SQL queries and offline analysis. SQLite needs no driver extra; `SQLAlchemyStore` supports other backends, with `[postgres]` and `[duckdb]` extras for their drivers. `SyncService` and `AsyncSyncService` support incremental updates.

<p lang="fa" dir="rtl">
برای نگهداری نسخه‌ای محلی از داده‌ها، اجرای پرس‌وجوی SQL و تحلیل آفلاین، از <code>open_store()</code> یا <code>tse db</code> استفاده کنید. SQLite به درایور اضافی نیاز ندارد. برای اتصال به PostgreSQL یا DuckDB از طریق <code>SQLAlchemyStore</code>، افزونهٔ <code>[postgres]</code> یا <code>[duckdb]</code> را نصب کنید. <code>SyncService</code> و <code>AsyncSyncService</code> از همگام‌سازی افزایشی پشتیبانی می‌کنند.
</p>

```bash
tse db init --db ./tse.sqlite
tse db sync --db ./tse.sqlite --symbols کگل,فولاد --client-type
tse db status --db ./tse.sqlite
```

<a id="agents"></a>
## MCP and Agent Skills / ابزارهای عامل‌های هوش مصنوعی

For a local MCP client, configure `tehran-stocks-mcp` as the stdio command (or use `tse mcp`). Market tools and resources don’t need a DB. Attach one with `--db` only for trusted clients that need DB sync or SQL queries. Streamable HTTP is also available via `tse mcp --transport streamable-http`.

The wheel bundles `tehran-stocks-setup` and `tehran-stocks-analysis`. The installer preserves existing copies unless you pass `--overwrite`.

<p lang="fa" dir="rtl">
برای یک کلاینت محلی MCP، فرمان <code>tehran-stocks-mcp</code> (یا <code>tse mcp</code>) را با رابط <code>stdio</code> تنظیم کنید. ابزارها و منابع دادهٔ بازار به پایگاه داده نیاز ندارند. گزینهٔ <code>--db</code> را فقط برای کلاینت‌های مورد اعتماد که به همگام‌سازی یا پرس‌وجوی SQL نیاز دارند فعال کنید. رابط Streamable HTTP هم با <code>tse mcp --transport streamable-http</code> در دسترس است.
</p>

<p lang="fa" dir="rtl">
مهارت‌های <code>tehran-stocks-setup</code> و <code>tehran-stocks-analysis</code> در بستهٔ نصب پایتون قرار دارند. نصب‌کننده نسخه‌های موجود را حفظ می‌کند، مگر اینکه خودتان <code>--overwrite</code> را مشخص کنید.
</p>

```bash
tse skill list
tse skill install --target auto --scope project
```

<a id="migration"></a>
## Migrating from v2 / مهاجرت از نسخهٔ ۲

v3 is a breaking release. Replace `Stocks` queries with `ts.search()` or `ts.quote()`, and `stock.df` with `ts.to_dataframe(ts.history(symbol))`. Use `tse` instead of `ts-get`. v3 does not automatically read or migrate the old `~/.tse/` config and database; keep a backup if you still need them.

<p lang="fa" dir="rtl">
نسخهٔ ۳ با رابط قدیمی سازگار نیست. به‌جای پرس‌وجوهای <code>Stocks</code> از <code>ts.search()</code> یا <code>ts.quote()</code> و به‌جای <code>stock.df</code> از <code>ts.to_dataframe(ts.history(symbol))</code> استفاده کنید. فرمان <code>tse</code> جایگزین <code>ts-get</code> شده است. نسخهٔ ۳ تنظیمات و پایگاه دادهٔ قدیمی در <code>~/.tse/</code> را خودکار نمی‌خواند یا منتقل نمی‌کند؛ اگر هنوز به آن‌ها نیاز دارید، نسخهٔ پشتیبان نگه دارید.
</p>

## Development / توسعه

The default suite uses fixtures; opt into live tests when TSETMC is reachable.

<p lang="fa" dir="rtl">
آزمون‌های پیش‌فرض با داده‌های ذخیره‌شده اجرا می‌شوند. در صورت دسترسی به TSETMC، آزمون‌های زنده را جداگانه اجرا کنید.
</p>

```bash
uv sync --locked
uv run --locked pytest
uv run --locked pytest -m live
```

[MIT License / مجوز MIT](LICENSE)
