# سناریو ۴: انبار دادهٔ محلی و تحلیل آفلاین

اگر فقط گاهی قیمت یا سابقهٔ چند سهم را بررسی می‌کنید، **اصلاً نیازی به پایگاه داده ندارید** و حالت لحظه‌ای (`ts.Client()`) سریع‌تر و ساده‌تر است.

اما زمانی که می‌خواهید:

- روی صدها نماد **بک‌تست چندساله** اجرا کنید،
- پرس‌وجوهای تحلیلی **SQL** روی تاریخچهٔ قیمت‌ها و جریان پول حقیقی بنویسید،
- هر روز فقط **داده‌های جدید** را به‌صورت افزایشی (Incremental) به آرشیو خود اضافه کنید،
- یا به دستیار هوش مصنوعی (MCP) اجازه دهید روی تاریخچهٔ کامل بازار پرس‌وجوی SQL اجرا کند،

لایهٔ ذخیره‌سازی اختیاری `tehran_stocks.storage` دقیقاً برای همین ساخته شده است.

---

## پشتیبانی از SQLite، PostgreSQL و DuckDB با یک رابط یکسان

تابع `open_store()` بر اساس مسیر یا آدرس اتصال، به‌طور خودکار موتور مناسب را باز می‌کند:

| موتور | مثال اتصال | افزونهٔ موردنیاز | مناسب برای |
| :--- | :--- | :--- | :--- |
| **SQLite** (پیش‌فرض) | `open_store("./tse.sqlite")` | هیچ (داخلی با حالت WAL) | پروژه‌های شخصی، لپ‌تاپ، MCP محلی |
| **DuckDB** | `open_store("duckdb:///./tse.duckdb")` | `tehran-stocks[duckdb]` | تحلیل‌های ستونی سریع روی میلیون‌ها ردیف |
| **PostgreSQL** | `open_store("postgresql://user:pass@localhost:5432/tse")` | `tehran-stocks[postgres]` | تیم‌ها، سرورها و داشبوردهای مشترک |

---

## گام ۱: ساخت پایگاه داده و همگام‌سازی افزایشی در پایتون

در مثال زیر، یک پایگاه دادهٔ SQLite می‌سازیم و تاریخچهٔ قیمت‌ها، تعدیل‌ها و جریان پول حقیقی/حقوقی چند سهم را همراه با نمایش پیشرفت همگام‌سازی می‌کنیم. بار دومی که همین کد را اجرا کنید، فقط روزهای معاملاتی جدید دانلود می‌شوند:

```python
from tehran_stocks.storage import SyncProgress, SyncService, open_store


def show_progress(progress: SyncProgress) -> None:
    print(f"[{progress.stage}] {progress.completed}/{progress.total} ({progress.symbol})")


store = open_store("./tse.sqlite")
try:
    service = SyncService(store, max_concurrency=8)
    result = service.sync_all(
        symbols=["کگل", "فولاد", "فملی", "شپنا"],
        incremental=True,
        include_client_types=True,
        include_adjustments=True,
        on_progress=show_progress,
    )
    print(f"همگام‌سازی کامل شد: {result.prices} ردیف قیمت، {result.client_types} ردیف حقیقی/حقوقی")
finally:
    store.close()
```

!!! tip "همگام‌سازی یک صنعت کامل یا کل بازار"
    به‌جای فهرست نمادها می‌توانید یک صنعت مشخص (`sector="34"`) یا کل نمادهای بازار (`all_instruments=True`) را همگام‌سازی کنید:
    ```python
    service.sync_all(sector="34", incremental=True, include_client_types=True)
    ```

اگر داخل یک برنامهٔ ناهمگام (`FastAPI`، اسکریپت `asyncio` و ...) هستید، از **`AsyncSyncService`** استفاده کنید:

```python
import asyncio
import tehran_stocks as ts
from tehran_stocks.storage import AsyncSyncService, open_store


async def sync_async() -> None:
    store = open_store("./tse.sqlite")
    try:
        async with ts.AsyncClient(max_concurrency=8) as client:
            service = AsyncSyncService(store, client=client)
            await service.sync_all(symbols=["کگل", "فولاد"], include_client_types=True)
    finally:
        store.close()


asyncio.run(sync_async())
```

---

## گام ۲: خواندن داده‌های تعدیل‌شده و اجرای SQL تحلیلی (فقط‌خواندنی)

پس از همگام‌سازی، تمام تحلیل‌های شما بدون نیاز به اینترنت و با سرعت بالا روی دیسک اجرا می‌شوند:

```python
import tehran_stocks as ts
from tehran_stocks.storage import open_store

store = open_store("./tse.sqlite")
try:
    # ۱. دریافت مستقیم تاریخچهٔ تعدیل‌شده از دیتابیس محلی
    bars = store.get_prices("کگل", start="1403-01-01", adjusted=True)
    df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
    print(df[["close", "volume"]].tail())

    # ۲. اجرای SQL تحلیلی ایمن (فقط SELECT / WITH مجاز است)
    rows = store.query_readonly(
        """
        SELECT
            i.symbol,
            p.date,
            p.close,
            p.value / 10000000000.0 AS value_bt,
            (c.buy_i_value - c.sell_i_value) / 10000000000.0 AS real_money_flow_bt
        FROM daily_prices p
        JOIN instruments i ON i.ins_code = p.ins_code
        LEFT JOIN client_types c ON c.ins_code = p.ins_code AND c.date = p.date
        WHERE i.symbol = :symbol
        ORDER BY p.date DESC
        LIMIT 10
        """,
        params={"symbol": "کگل"},
    )
    for r in rows:
        print(r)
finally:
    store.close()
```

!!! info "ساختار جدول‌های پایگاه داده"
    پایگاه داده شامل ۷ جدول استاندارد است:
    `sectors`، `instruments`، `daily_prices`، `client_types`، `price_adjustments`، `share_changes` و `sync_meta`.
    متد `store.query_readonly()` به‌صورت سخت‌گیرانه هرگونه دستور تغییردهنده (`INSERT`، `UPDATE`، `DELETE`، `DROP`، `ALTER`) را مسدود می‌کند و در SQLite اتصال را در حالت `?mode=ro` باز می‌کند.

---

## گام ۳: مدیریت پایگاه داده از طریق ترمینال (`tse db`)

برای به‌روزرسانی روزانه (مثلاً از طریق `cron` پس از پایان بازار) می‌توانید تمام کار را بدون نوشتن کد پایتون از ترمینال انجام دهید:

```bash
# ۱. ساخت پایگاه داده و جدول‌ها
tse db init --db ./tse.sqlite

# ۲. همگام‌سازی افزایشی نمادهای منتخب همراه با حقیقی/حقوقی
tse db sync --db ./tse.sqlite --symbols کگل,فولاد,فملی --client-type

# یا همگام‌سازی یک صنعت کامل (مثلاً گروه خودرو با کد 34)
tse db sync --db ./tse.sqlite --sector 34 --client-type

# ۳. مشاهدهٔ آمار ردیف‌ها و پوشش تاریخی دیتابیس
tse db status --db ./tse.sqlite

# ۴. اجرای پرس‌وجوی SQL و گرفتن خروجی JSON
tse db query --db ./tse.sqlite "SELECT symbol, name, sector_name FROM instruments LIMIT 10" --json
```

---

## گام ۴: دریافت نسخهٔ آماده از GitHub Releases (سریع‌تر از همگام‌سازی اولیه)

اگر به تاریخچهٔ کامل بازار نیاز دارید، به‌جای اجرای همگام‌سازی اولیه روی هزاران نماد می‌توانید آخرین نسخهٔ فشردهٔ SQLite را از ریلیز چرخشی `data-latest` دانلود کنید و بعد هر روز فقط روزهای جدید را با `--incremental` اضافه کنید:

```bash
# ۱. دانلود و بازکردن مستقیم نسخهٔ آماده (حدود ۱۸۴ مگابایت فشرده با zstd):
curl -fL https://github.com/ghodsizadeh/tehran-stocks/releases/download/data-latest/tse.sqlite.zst -o tse.sqlite.zst
zstd -d tse.sqlite.zst -o tse.sqlite

# (اختیاری) بررسی اصالت فایل با SHA256SUMS:
curl -fL https://github.com/ghodsizadeh/tehran-stocks/releases/download/data-latest/SHA256SUMS -o SHA256SUMS
shasum -a 256 -c SHA256SUMS --ignore-missing

# یا اگر مخزن گیت‌هاب را کلون کرده‌اید (دانلود + بررسی خودکار SHA-256 + بازکردن):
# uv run python scripts/data_snapshot.py download --output ./tse.sqlite

# ۲. بررسی آمار دیتابیس و به‌روزرسانی افزایشی روزهای جدید
tse db status --db ./tse.sqlite
tse db sync --db ./tse.sqlite --incremental --client-type
```

!!! note "نحوهٔ ساخت و به‌روزرسانی خودکار اسنپ‌شات (برای نگهدارندگان)"
    اسکریپت `scripts/data_snapshot.py` و ورک‌فلو `.github/workflows/data-snapshot.yml` خارج از بستهٔ پایتون `tehran-stocks` نگهداری می‌شوند تا حجم بستهٔ PyPI و تاریخچهٔ گیت سبک بماند:

    1. **بذرپاشی اولیه (یک بار روی سیستم محلی یا VPS):**
       ```bash
       uv run python scripts/data_snapshot.py sync --db ./work/tse.sqlite --mode full --concurrency 4
       uv run python scripts/data_snapshot.py package --db ./work/tse.sqlite --out-dir ./dist-data
       gh release create data-latest ./dist-data/tse.sqlite.zst ./dist-data/manifest.json ./dist-data/SHA256SUMS \
         --title "TSETMC SQLite Snapshot (data-latest)"
       ```
    2. **تست دسترسی TSETMC از GitHub Actions:** قبل از تکیه بر اجرای زمان‌بندی‌شده، ورک‌فلو `Update TSETMC Data Snapshot` را به‌صورت دستی (`workflow_dispatch`) با `sector: "34"` و `publish: false` اجرا کنید. در صورت محدودیت IP سرورهای Azure، می‌توانید سکرت `TSETMC_PROXY` را تنظیم کنید یا همین اسکریپت را روی یک VPS/runner شخصی با `cron` اجرا و با `gh release upload data-latest ... --clobber` منتشر کنید.

---

## گام ۵: تغییر موتور به PostgreSQL یا DuckDB بدون تغییر کد تحلیل

کافی است آدرس اتصال را تغییر دهید؛ تمام کدهای `SyncService`، `get_prices` و `query_readonly` دقیقاً یکسان می‌مانند:

```python
from tehran_stocks.storage import open_store

# DuckDB (نیازمند tehran-stocks[duckdb])
duck_store = open_store("duckdb:///./tse.duckdb")

# PostgreSQL (نیازمند tehran-stocks[postgres])
pg_store = open_store("postgresql://user:password@localhost:5432/tse")
```
