# نصب و راه‌اندازی

برای کار با نسخهٔ ۳ بستهٔ `tehran-stocks` به **پایتون ۳.۱۱ یا بالاتر** و دسترسی HTTPS به سرورهای `cdn.tsetmc.com` نیاز دارید. تمام ابزارهای اصلی (کلاینت HTTP/2، `pandas`، `jalali-pandas`، خط فرمان `tse`، سرور `MCP` و `SQLAlchemy`) با یک دستور واحد نصب می‌شوند.

---

## کدام روش نصب برای شما مناسب است؟

| هدف شما | روش پیشنهادی | آیا محیط سیستم را تغییر می‌دهد؟ |
| :--- | :--- | :--- |
| اجرای سریع فرمان‌ها در ترمینال یا اتصال MCP | `uvx --from tehran-stocks ...` | خیر (اجرای ایزوله و آنی) |
| استفاده در پروژهٔ پایتون یا نوت‌بوک Jupyter | `uv add` یا `pip install` | نصب درون محیط مجازی پروژه |
| ذخیرهٔ داده‌ها در PostgreSQL یا DuckDB | افزودن افزونهٔ `[postgres]` یا `[duckdb]` | نصب درایور پایگاه دادهٔ انتخابی |

---

## روش ۱: نصب در پروژهٔ پایتون

=== "با uv (پیشنهادی)"

    ```bash
    uv add "tehran-stocks>=3,<4"
    ```

=== "با pip"

    ```bash
    python -m pip install "tehran-stocks>=3,<4"
    ```

=== "نصب مستقیم از کد منبع (مخزن گیت‌هاب)"

    اگر می‌خواهید جدیدترین تغییرات شاخهٔ اصلی یا نسخهٔ پیش از انتشار در PyPI را نصب کنید:

    ```bash
    git clone https://github.com/ghodsizadeh/tehran-stocks.git
    cd tehran-stocks
    python -m pip install .
    ```

!!! note "نکته دربارهٔ نسخهٔ PyPI"
    مثال‌های این مستندات برای **نسخهٔ ۳** هستند. تعیین بازهٔ `>=3,<4` خیال شما را راحت می‌کند که نسخهٔ قدیمی ۲ نصب نشود. پیش از انتشار نهایی نسخهٔ ۳ روی PyPI، از روش نصب از کد منبع استفاده کنید.

---

## روش ۲: اجرای بدون نصب با `uvx`

اگر ابزار `uv` روی سیستم شما نصب است، می‌توانید بدون ساخت محیط مجازی یا نصب دائمی، مستقیماً خط فرمان `tse` یا سرور MCP را اجرا کنید:

```bash
# نمایش راهنمای کامل خط فرمان
uvx --from tehran-stocks tse --help

# بررسی اتصال به بازار و گرفتن قیمت لحظه‌ای
uvx --from tehran-stocks tse market
uvx --from tehran-stocks tse quote کگل
```

---

## افزونه‌های اختیاری پایگاه داده

پایگاه دادهٔ داخلی `SQLiteStore` از کتابخانهٔ استاندارد `sqlite3` پایتون (در حالت WAL) استفاده می‌کند و **به هیچ بستهٔ اضافه‌ای نیاز ندارد**.

فقط اگر قصد دارید داده‌ها را روی **PostgreSQL** یا **DuckDB** ذخیره کنید، افزونهٔ متناظر آن را نصب کنید:

=== "PostgreSQL"

    ```bash
    # نصب با uv
    uv add "tehran-stocks[postgres]>=3,<4"

    # یا با pip
    python -m pip install "tehran-stocks[postgres]>=3,<4"
    ```

=== "DuckDB"

    ```bash
    # نصب با uv
    uv add "tehran-stocks[duckdb]>=3,<4"

    # یا با pip
    python -m pip install "tehran-stocks[duckdb]>=3,<4"
    ```

---

## بررسی سلامت نصب

پس از نصب، با اجرای این دستور کوتاه از کارکرد درست کتابخانه و اتصال به TSETMC مطمئن شوید:

```bash
python -c "import tehran_stocks as ts; q = ts.quote('کگل'); print(q.last, q.close)"
```

همچنین می‌توانید نسخهٔ خط فرمان را بررسی کنید:

```bash
tse --version
```

!!! success "بدون هیچ اثر جانبی"
    پس از اجرای `import tehran_stocks` هیچ پوشه‌ای مانند `~/.tse/` ساخته نمی‌شود و هیچ دیتابیسی بدون درخواست شما ایجاد نخواهد شد.

---

## تنظیم پروکسی و زمان انتظار (Timeout) در شبکه‌های محدود

اگر از خارج از ایران یا پشت شبکهٔ سازمانی به `cdn.tsetmc.com` وصل می‌شوید و با خطای زمان انتظار (Timeout) یا محدودیت دسترسی مواجه هستید، می‌توانید به‌سادگی پروکسی و زمان انتظار را مشخص کنید:

=== "در پایتون"

    ```python
    import tehran_stocks as ts

    with ts.Client(
        timeout=30.0,
        proxy="http://127.0.0.1:8080",
        max_retries=4,
    ) as client:
        overview = client.market.overview()
        print(overview.index_value)
    ```

=== "در ترمینال و سرور MCP"

    ```bash
    export TEHRAN_STOCKS_TIMEOUT=30
    export TEHRAN_STOCKS_PROXY="http://127.0.0.1:8080"

    tse market
    # یا به‌صورت مستقیم در فرمان:
    tse --timeout 30 --proxy http://127.0.0.1:8080 quote کگل
    ```

---

## گام بعدی چیست؟

- اگر می‌خواهید با پایتون یک سهم را صفر تا صد تحلیل کنید: [بررسی کامل یک سهم در پایتون](../guides/stock-analysis.md)
- اگر می‌خواهید دستیار هوش مصنوعی خود را به بورس وصل کنید: [اتصال دستیار هوش مصنوعی با MCP](../ai/mcp.md)
- اگر می‌خواهید مهارت‌های آمادهٔ تحلیل را به ایجنت خود اضافه کنید: [نصب مهارت‌ها (Agent Skills)](../ai/skills.md)
