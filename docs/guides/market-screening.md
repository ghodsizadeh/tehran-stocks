# سناریو ۳: رصد کل بازار، شاخص‌ها و فیلترنویسی

یکی از بزرگ‌ترین مزیت‌های API جدید TSETMC در نسخهٔ ۳ این است که **نیازی به ارسال هزاران درخواست جداگانه نیست**:

- با **یک درخواست** (`client.market.watch()`) قیمت لحظه‌ای، P/E، EPS، دامنهٔ مجاز و ۵ سطر سفارش حدود ۳۸۰۰ نماد کل بازار را می‌گیرید.
- با **یک درخواست** (`client.client_type.all()`) آمار لحظه‌ای حقیقی و حقوقی تمام نمادهای فعال بازار را می‌گیرید.

در این راهنما می‌بینید چگونه در کمتر از چند ثانیه، نبض کل بازار را بسنجید، یک فیلترنویسی حرفه‌ای بنویسید و وضعیت صندوق‌های ETF و اختیار معامله را بررسی کنید.

---

## گام ۱: بررسی نبض بازار و واگرایی شاخص کل با هم‌وزن

مقایسهٔ **شاخص کل (`TEDPIX`)** با **شاخص کل هم‌وزن** نشان می‌دهد رشد یا افت بازار فراگیر است یا فقط روی نمادهای بزرگ (شاخص‌ساز) متمرکز شده است:

```python
import tehran_stocks as ts

with ts.Client() as client:
    # flow=1 برای بورس تهران و flow=2 برای فرابورس
    tse = client.market.overview(flow=1)
    ifb = client.market.overview(flow=2)
    effects = client.market.index_effect("TEDPIX", flow=1, top=5)

print(f"وضعیت بورس تهران: {tse.market_state}")
print(f"شاخص کل:          {tse.index_value:,.0f} ({tse.index_change:+,.0f})")
print(f"شاخص هم‌وزن:       {tse.equal_weighted_index:,.0f} ({tse.equal_weighted_change:+,.0f})")
print(f"ارزش معاملات بورس: {tse.trade_value / 1e10:,.0f} میلیارد تومان")
print(f"شاخص کل فرابورس:   {ifb.index_value:,.0f} ({ifb.index_change:+,.0f})")

print("\n--- ۵ نماد بیشترین اثر روی شاخص کل ---")
for item in effects:
    print(f"{item.symbol:10s} | اثر روی شاخص: {item.effect:+.1f} | پایانی: {item.close:,.0f}")
```

برای مشاهدهٔ تاریخچهٔ روزانهٔ شاخص کل (یا هر شاخص صنعت دیگری از `client.market.indices()`):

```python
with ts.Client() as client:
    tedpix_bars = client.market.index_history("TEDPIX")
    all_indices = client.market.indices(flow=1)

df_tedpix = ts.to_dataframe(tedpix_bars, jalali=True, index_by_date=True)
print(df_tedpix[["value", "high", "low"]].tail())
```

---

## گام ۲: نوشتن یک فیلتر بازار (Market Screener) واقعی در ۲ درخواست

فرض کنید می‌خواهید وسط بازار تمام نمادهایی را پیدا کنید که:

- ارزش معاملات امروزشان حداقل **۵ میلیارد تومان** (`5e10` ریال) باشد
- **ورود پول حقیقی مثبت** داشته باشند
- **قدرت خریدار به فروشنده** بیشتر از **`1.5`** باشد
- هنوز در **صف خرید قفل نشده باشند** (فرصت بررسی داشته باشند)

کد زیر کل این فیلتر را روی تمام بازار با **تنها ۲ درخواست HTTP** اجرا می‌کند:

```python
import tehran_stocks as ts

with ts.Client() as client:
    watch_items = client.market.watch()
    flow_items = client.client_type.all()

# نگاشت سریع ins_code به جریان پول حقیقی/حقوقی
flow_by_code = {f.ins_code: f for f in flow_items}

candidates = []
for item in watch_items:
    flow = flow_by_code.get(item.ins_code)
    if flow is None:
        continue

    # بررسی نبود صف خرید قفل‌شده
    top_level = item.order_book[0] if item.order_book else None
    is_buy_queue = (
        top_level is not None
        and item.price_max_allowed is not None
        and top_level.bid_price >= item.price_max_allowed
        and top_level.ask_volume == 0
    )

    if (
        item.value >= 50_000_000_000          # حداقل ۵ میلیارد تومان
        and flow.real_money_flow > 0          # ورود پول حقیقی مثبت
        and flow.buyer_power >= 1.5           # قدرت خریدار قوی
        and not is_buy_queue                  # قفل در صف خرید نباشد
    ):
        candidates.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "last": item.last,
                "change_pct": round(item.change_pct, 2),
                "value_bt": round(item.value / 1e10, 1),
                "money_flow_bt": round(flow.real_money_flow / 1e10, 2),
                "buyer_power": round(flow.buyer_power, 2),
            }
        )

candidates.sort(key=lambda r: r["money_flow_bt"], reverse=True)

df_screen = ts.to_dataframe(candidates[:15], jalali=False, index_by_date=False)
print(df_screen.to_string(index=False))
```

---

## گام ۳: بررسی صنایع برتر بازار

اگر می‌خواهید ببینید امروز پول در کدام صنایع (گروه‌ها) در حال گردش است:

```python
with ts.Client() as client:
    sectors = client.market.sectors()

# مرتب‌سازی بر اساس ارزش معاملات هر صنعت
top_sectors = sorted(sectors, key=lambda s: s.trade_value, reverse=True)
for s in top_sectors[:10]:
    print(f"[{s.code}] {s.name:35s} | ارزش: {s.trade_value / 1e10:,.0f} میلیارد تومان")
```

با داشتن کد صنعت (مثلاً کد `27` برای فلزات اساسی یا `34` برای خودرو) می‌توانید تمام نمادهای هم‌گروه را با `client.instruments.related("34")` دریافت کنید.

---

## گام ۴: بررسی حباب قیمتی صندوق‌های ETF و بازار اختیار معامله

برای صندوق‌های قابل معامله (سهامی، طلا، درآمد ثابت)، شاخص کلیدی مقایسهٔ قیمت معامله با **NAV ابطال** (`redemption_nav`) و **NAV آماری** (`statistical_nav`) است:

```python
with ts.Client() as client:
    q = client.prices.quote("بمان")
    etf_info = client.funds.etf("بمان")

print(f"قیمت معامله: {q.last:,.0f} ریال")
print(f"NAV ابطال:   {etf_info.redemption_nav:,.0f} ریال")
print(f"NAV آماری:   {etf_info.statistical_nav:,.0f} ریال")

if etf_info.redemption_nav > 0:
    bubble_pct = (q.last - etf_info.redemption_nav) / etf_info.redemption_nav * 100
    print(f"حباب (پریمیوم/دیسکانت) نسبت به NAV ابطال: {bubble_pct:+.2f}%")
```

و برای دریافت تابلوی لحظه‌ای **قراردادهای اختیار معامله (Options)**:

```python
with ts.Client() as client:
    options = client.funds.options(flow=1)

# ۵ قرارداد پُرحجم‌ترین اختیار معامله
active_opts = sorted(options, key=lambda o: o.value, reverse=True)[:5]
for opt in active_opts:
    print(
        f"{opt.symbol:10s} | اعمال: {opt.strike_price:,.0f} | "
        f"روز تا سررسید: {opt.days_to_maturity} | "
        f"موقعیت باز: {opt.open_interest:,}"
    )
```

!!! tip "همین فیلتر در ترمینال!"
    اگر بدون نوشتن کد پایتون می‌خواهید سریع‌ترین فیلتر بازار را در ترمینال اجرا کنید، فرمان زیر آماده است:
    ```bash
    tse screen --sort money_flow --limit 15
    ```
    جزئیات بیشتر را در [راهنمای خط فرمان `tse`](cli.md) ببینید.
