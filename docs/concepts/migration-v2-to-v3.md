# راهنمای مهاجرت از نسخهٔ ۲ به نسخهٔ ۳

نسخهٔ ۳ `tehran-stocks` یک بازنویسی کامل و ناسازگار با نسخهٔ ۲ (Breaking Release) است. هدف اصلی در این نسخه حذف وابستگی‌های قدیمی و شکننده، سرعت بسیار بالاتر روی API جدید `cdn.tsetmc.com`، پشتیبانی از `async` و افزودن خط فرمان مدرن، سرور `MCP` و `Agent Skills` بوده است.

!!! warning "دربارهٔ فایل‌های قدیمی `~/.tse/`"
    نسخهٔ ۳ فایل تنظیمات `~/.tse/config.yml` و پایگاه دادهٔ `~/.tse/stocks.db` نسخهٔ ۲ را **به‌طور خودکار نمی‌خواند و منتقل نمی‌کند**. اگر به داده‌های ذخیره‌شده در نسخهٔ ۲ نیاز دارید، پیش از حذف آن‌ها یک نسخهٔ پشتیبان نگه دارید.

---

## تغییرات کلیدی معماری

| در نسخهٔ ۲ (حذف شده) | در نسخهٔ ۳ (روش جدید) |
| :--- | :--- |
| `import tehran_stocks` به‌طور خودکار `~/.tse/stocks.db` می‌ساخت و از شما سؤال می‌پرسید | `import tehran_stocks` **هیچ اثر جانبی ندارد**؛ هیچ فایلی ساخته نمی‌شود |
| تنظیم پایگاه داده در `~/.tse/config.yml` | ارسال مستقیم مسیر یا URI به `open_store()`، گزینهٔ `--db` یا متغیر `TEHRAN_STOCKS_DB` |
| مدل‌های `SQLAlchemy` مثل `Stocks.query.filter_by(...)` | مدل‌های نوع‌دار و خواندنی (`Quote`، `DailyBar`، `Instrument` و ...) و رابط `ts.Client()` |
| دسترسی به دیتافریم از طریق `stock.df` | تبدیل مستقیم با `ts.to_dataframe(bars, jalali=True)` همراه با `JalaliDatetimeIndex` |
| فرمان قدیمی `ts-get` | خط فرمان مدرن `tse` (و `tehran-stocks`) با خروجی جدول، `JSON` و `CSV` |
| دانلود متوالی با `get_all_price()` و `update_group()` | همگام‌سازی هم‌زمان و افزایشی با `SyncService` / `AsyncSyncService` و `tse db sync` |

---

## مقایسهٔ عملی کد: قبل و بعد

### ۱. پیدا کردن یک سهم و گرفتن دیتافریم قیمت‌ها

=== "نسخهٔ ۳ (جدید)"

    ```python
    import tehran_stocks as ts

    with ts.Client() as client:
        bars = client.prices.history("کگل", days=0, adjusted=True)

    df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
    df.to_csv("price.csv", encoding="utf-8-sig")
    ```

=== "نسخهٔ ۲ (قدیمی)"

    ```python
    from tehran_stocks import Stocks

    stock = Stocks.query.filter_by(name="كگل").first()
    stock.update()
    df = stock.df
    df.to_csv("price.csv")
    ```

---

### ۲. گرفتن قیمت لحظه‌ای، سود (تعدیل) و افزایش سرمایه

=== "نسخهٔ ۳ (جدید)"

    ```python
    import tehran_stocks as ts

    with ts.Client() as client:
        quote = client.prices.quote("کگل")
        adjustments = client.prices.adjustments("کگل")
        share_changes = client.instruments.share_changes("کگل")

    print(quote.last, quote.close, quote.volume)
    ```

=== "نسخهٔ ۲ (قدیمی)"

    ```python
    stock = Stocks.query.filter_by(name="كگل").first()
    detail = stock.get_instant_detail()
    div = stock.get_dividend()
    shares = stock.get_shares_history()
    ```

---

### ۳. همگام‌سازی یک گروه (صنعت) در پایگاه دادهٔ محلی

=== "نسخهٔ ۳ (جدید — پایتون)"

    ```python
    from tehran_stocks.storage import SyncService, open_store

    store = open_store("./tse.sqlite")
    try:
        SyncService(store).sync_all(sector="34", include_client_types=True)
    finally:
        store.close()
    ```

=== "نسخهٔ ۳ (جدید — ترمینال)"

    ```bash
    tse db init --db ./tse.sqlite
    tse db sync --db ./tse.sqlite --sector 34 --client-type
    ```

=== "نسخهٔ ۲ (قدیمی)"

    ```bash
    ts-get init
    ts-get group 34
    ```

---

### ۴. اتصال به PostgreSQL

=== "نسخهٔ ۳ (جدید)"

    ابتدا افزونهٔ `[postgres]` را نصب کنید (`pip install "tehran-stocks[postgres]>=3,<4"`) و سپس:

    ```python
    from tehran_stocks.storage import open_store

    store = open_store("postgresql://postgres:password@localhost:5432/stocks")
    ```

=== "نسخهٔ ۲ (قدیمی)"

    ویرایش دستی `~/.tse/config.yml` و نصب جداگانهٔ `psycopg2`.
