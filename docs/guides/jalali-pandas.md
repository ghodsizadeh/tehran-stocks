# سناریو ۲: تحلیل تاریخچهٔ تعدیل‌شده و تقویم جلالی

وقتی می‌خواهید بازدهی چندماهه، میانگین متحرک، RSI یا نمودار بلندمدت یک سهم در بورس تهران را محاسبه کنید، با دو چالش مخصوص بازار ایران روبه‌رو می‌شوید:

1. **گپ‌های مصنوعی قیمت پس از مجمع و افزایش سرمایه:** در داده‌های تعدیل‌نشده، سهم روز پس از تقسیم سود یا افزایش سرمایه ناگهان ۲۰٪ تا ۵۰٪ افت می‌کند و تمام اندیکاتورها را خراب می‌کند.
2. **عدم تطابق ماه‌های میلادی با ماه‌های شمسی:** استفاده از `resample("ME")` استاندارد در `pandas` مرز ماه‌های ایرانی (۳۱، ۳۰ و ۲۹/۳۰ روزه) را حدود ۱۰ روز جابه‌جا می‌کند و تحلیل‌های ماهانه و فصلی را دقیق نمی‌دهد.

در این راهنما می‌بینید چطور با `adjusted=True` و یکپارچگی بومی `jalali-pandas>=1.0.0` این دو مشکل را به‌صورت کامل حل کنید.

---

## گام ۱: دریافت تاریخچهٔ تعدیل‌شده و تبدیل به DataFrame جلالی

با تنظیم `adjusted=True` کتابخانه به‌طور خودکار فهرست رویدادهای تعدیل قیمت (`GetPriceAdjustList`) را می‌گیرد و تعدیل پس‌رو (Backward Adjustment) را روی ستون‌های `open`، `high`، `low`، `close`، `last` و `yesterday` اعمال می‌کند (در حالی که حجم و ارزش معاملات واقعی حفظ می‌شوند).

```python
import tehran_stocks as ts

with ts.Client() as client:
    # دریافت کامل تاریخچهٔ تعدیل‌شده (days=0 یعنی تمام سابقه)
    bars = client.prices.history("فولاد", days=0, adjusted=True)

# تبدیل به DataFrame با ستون jdate و شاخص JalaliDatetimeIndex
df = ts.to_dataframe(bars, jalali=True, index_by_date=True)

print(df[["open", "high", "low", "close", "volume"]].tail())
```

!!! tip "فیلتر بازهٔ زمانی با تاریخ شمسی یا میلادی"
    در متد `history` می‌توانید بازهٔ `start` و `end` را با تاریخ میلادی (`"2024-03-20"` یا `20240320`) و یا مستقیماً با **تاریخ جلالی** (`"1403-01-01"`) مشخص کنید:
    ```python
    bars_1403 = client.prices.history(
        "فولاد",
        start="1403-01-01",
        end="1403-12-30",
        adjusted=True,
    )
    ```

---

## گام ۲: ساخت کندل‌های ماهانه و سالانهٔ دقیق بر اساس تقویم جلالی

چون شاخص `df.index` از نوع `JalaliDatetimeIndex` است، دسترسی به سال و ماه جلالی مستقیم و دقیق است. برای تجمیع OHLCV در هر ماه شمسی، مراقب باشید که قیمت‌ها هیچ‌وقت نباید جمع شوند؛ باید از `first`، `max`، `min`، `last` برای قیمت‌ها و `sum` برای حجم و ارزش استفاده کنید:

```python
import jalali_pandas  # فعال‌سازی دسترسی .jalali روی Series و DataFrame
import tehran_stocks as ts

with ts.Client() as client:
    bars = client.prices.history("کگل", days=0, adjusted=True)

df = ts.to_dataframe(bars, jalali=True, index_by_date=True)

# استخراج سال و ماه شمسی از JalaliDatetimeIndex
j_year = df.index.year.astype(int)
j_month = df.index.month.astype(int)

# ساخت ستون تاریخ شمسی خوانا برای گزارش و خروجی اکسل
df["jdate_str"] = df["date"].jalali.to_jalali().jalali.strftime("%Y-%m-%d")

# تجمیع دقیق کندل‌های ماهانهٔ شمسی
monthly = df.groupby([j_year, j_month]).agg(
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last"),
    volume=("volume", "sum"),
    value=("value", "sum"),
)
monthly.index.names = ["j_year", "j_month"]
monthly["return_pct"] = monthly["close"].pct_change() * 100

print(monthly.tail(6))
```

همچنین می‌توانید مجموع حجم یا بازدهی سالانهٔ هر سال شمسی را در یک خط ببینید:

```python
# مجموع ارزش معاملات هر سال شمسی (به میلیارد تومان)
yearly_value_bt = df.groupby(j_year)["value"].sum() / 1e10
print(yearly_value_bt.tail(5))
```

---

## گام ۳: محاسبهٔ اندیکاتورها و مقایسهٔ بازدهی چند سهم به‌صورت موازی

اگر بخواهید سابقهٔ تعدیل‌شدهٔ یک سبد شامل چند سهم را هم‌زمان دریافت کنید و بازدهی یا همبستگی آن‌ها را بسنجید، به‌جای حلقهٔ متوالی از **`AsyncClient`** و `asyncio.gather` استفاده کنید تا درخواست‌ها به‌صورت هم‌زمان (و با محدودیت نرخ کنترل‌شده) اجرا شوند:

```python
import asyncio
import pandas as pd
import tehran_stocks as ts


async def fetch_close_series(symbols: list[str], days: int = 250) -> pd.DataFrame:
    async with ts.AsyncClient(max_concurrency=6) as client:
        tasks = [
            client.prices.history(sym, days=days, adjusted=True)
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks)

    series_map = {}
    for sym, bars in zip(symbols, results):
        df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
        series_map[sym] = df["close"]

    return pd.DataFrame(series_map).dropna(how="all")


async def main() -> None:
    watchlist = ["فولاد", "فملی", "کگل", "شپنا", "خودرو"]
    closes = await fetch_close_series(watchlist, days=250)

    # بازدهی تجمعی در بازهٔ اخیر (درصد)
    total_return = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
    print("=== بازدهی تعدیل‌شده (%) ===")
    print(total_return.sort_values(ascending=False).round(1))

    # ماتریس همبستگی بازدهی روزانه
    print("\n=== همبستگی بازدهی روزانه ===")
    print(closes.pct_change().corr().round(2))


asyncio.run(main())
```

---

## گام ۴: بررسی رویدادهای مجمع و افزایش سرمایه در کنار تاریخچه

اگر می‌خواهید بدانید دقیقاً در چه تاریخ‌هایی تعدیل قیمت یا تغییر تعداد سهام رخ داده است:

```python
with ts.Client() as client:
    adjustments = client.prices.adjustments("کگل")
    share_changes = client.instruments.share_changes("کگل")

print("--- تاریخچهٔ تعدیل‌های قیمت (مجمع / افزایش سرمایه) ---")
for adj in adjustments[:5]:
    print(
        f"{adj.date}: پایانی تعدیل‌نشده {adj.unadjusted_close:,.0f} -> "
        f"تعدیل‌شده {adj.adjusted_close:,.0f} (ضریب {adj.ratio:.4f})"
    )

print("\n--- تاریخچهٔ افزایش سرمایه‌ها ---")
for sc in share_changes[:5]:
    print(f"{sc.date}: از {sc.old_shares:,} به {sc.new_shares:,} سهم ({sc.ratio:.2f}x)")
```

---

## گام ۵: خروجی گرفتن برای Excel، CSV یا Parquet

پس از آماده شدن `DataFrame`، می‌توانید خروجی را برای اکسل (با `utf-8-sig` تا حروف فارسی در اکسل به‌هم نریزد) یا ابزارهای دیگر ذخیره کنید:

```python
# ذخیرهٔ CSV سازگار با اکسل فارسی
df.to_csv("kgl_adjusted.csv", encoding="utf-8-sig")

# یا ذخیره برای پروژه‌های داده‌کاوی
# df.to_parquet("kgl_adjusted.parquet")
```
