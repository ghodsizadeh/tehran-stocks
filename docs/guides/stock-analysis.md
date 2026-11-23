# سناریو ۱: بررسی کامل یک سهم در پایتون

در بورس تهران، نگاه کردن به قیمت یک سهم به‌تنهایی تقریباً هیچ‌وقت کافی نیست. برای یک ارزیابی واقعی باید پنج قطعهٔ پازل را کنار هم بگذارید:

1. **قیمت آخرین معامله در برابر قیمت پایانی** (تأثیر حجم مبنا)
2. **جریان پول حقیقی و حقوقی** (ورود پول و قدرت خریدار)
3. **عمق بازار (۵ سطر سفارش)** و تشخیص صف خرید یا فروش
4. **اطلاعات بنیادی و سهامداران عمده**
5. **اطلاعیه‌های کدال و پیام‌های ناظر** (تشخیص توقف نماد یا مجمع پیشِ رو)

در این راهنما یک سناریوی واقعی را قدم‌به‌قدم روی نماد **`کگل`** پیاده می‌کنیم و در پایان، کل آن را در یک اسکریپت کامل و تمیز ترکیب می‌کنیم.

---

## گام ۱: استفاده از یک نشست مشترک (`Client`)

اگر قرار است فقط یک درخواست ساده بفرستید، توابع سطح بالای کتابخانه مثل `ts.quote("کگل")` کافی هستند. اما وقتی چند پرس‌وجوی پشت‌سرهم روی یک سهم یا چند سهم دارید، **همیشه از `with ts.Client() as client:` استفاده کنید** تا:

- یک اتصال پایدار HTTP/2 بین همهٔ درخواست‌ها به اشتراک گذاشته شود.
- نگاشت نماد به شناسهٔ داخلی (`insCode`) در حافظه کش شود و دوباره جست‌وجو نشود.

```python
import tehran_stocks as ts

with ts.Client() as client:
    # جست‌وجوی نماد وقتی اسم دقیق آن را نمی‌دانید
    matches = client.instruments.search("گل گهر")
    for item in matches[:5]:
        print(f"{item.symbol:10s} | {item.name} | insCode={item.ins_code}")
```

!!! tip "هر نوع شناسه‌ای پذیرفته می‌شود"
    در تمام متدهای این کتابخانه می‌توانید **نماد فارسی** (`"کگل"`), **نماد با حروف عربی** (`"كگل"`), **شناسهٔ ISIN** (`"IRO1GOHR0001"`) یا **شناسهٔ عددی `insCode`** (`"35700344742885862"`) را مستقیماً وارد کنید.

---

## گام ۲: خواندن قیمت، وضعیت نماد و تفاوت «آخرین» با «پایانی»

در TSETMC تمام مبالغ بر حسب **ریال** هستند. همچنین `last` قیمت آخرین معامله و `close` قیمت پایانی (میانگین موزون متأثر از حجم مبنا) است.

```python
with ts.Client() as client:
    q = client.prices.quote("کگل")
    info = client.instruments.info("کگل")

print(f"وضعیت نماد: {q.state_title} ({q.state})")
print(f"آخرین معامله: {q.last:,.0f} ریال ({q.change_pct:+.2f}%)")
print(f"قیمت پایانی:  {q.close:,.0f} ریال | دیروز: {q.yesterday:,.0f} ریال")
print(f"حجم معاملات:  {q.volume:,} (حجم مبنا: {info.base_volume:,})")
print(f"ارزش معاملات: {q.value / 1e10:,.1f} میلیارد تومان")
print(f"EPS برآوردی:  {info.eps} | P/E گروه: {info.sector_pe}")
print(f"بازهٔ مجاز امروز: {info.price_min_allowed:,.0f} تا {info.price_max_allowed:,.0f} ریال")
```

!!! warning "حجم معاملات کمتر از حجم مبنا"
    اگر `q.volume < info.base_volume` باشد، حتی با صف خرید هم قیمت پایانی به سقف دامنه نوسان نمی‌رسد و تنها به‌تناسب حجم معامله‌شده حرکت می‌کند. بررسی هم‌زمان `q.last`، `q.close` و `info.base_volume` جلوی برداشت اشتباه را می‌گیرد.

---

## گام ۳: تحلیل جریان پول حقیقی و حقوقی (تابلوخوانی)

مدل‌های `ClientTypeLive` و `ClientTypeDaily` شاخص‌های پرکاربرد تابلوخوانی را به‌طور آماده محاسبه می‌کنند:

- `real_money_flow`: خالص ورود/خروج پول حقیقی (ریال)
- `buy_per_capita` و `sell_per_capita`: سرانهٔ خرید و فروش هر کد حقیقی (ریال)
- `buyer_power`: نسبت قدرت خریدار به فروشنده (مقادیر بالای `1.5` معمولاً نشانهٔ برتری خریداران حقیقی است)

```python
with ts.Client() as client:
    live_flow = client.client_type.live("کگل")
    recent_flows = client.client_type.history("کگل", days=10)

print(f"ورود/خروج پول حقیقی امروز: {live_flow.real_money_flow / 1e10:+,.2f} میلیارد تومان")
print(f"سرانه خرید حقیقی:          {live_flow.buy_per_capita / 1e7:,.1f} میلیون تومان")
print(f"سرانه فروش حقیقی:          {live_flow.sell_per_capita / 1e7:,.1f} میلیون تومان")
print(f"قدرت خریدار به فروشنده:     {live_flow.buyer_power:.2f}")

# جمع ورود/خروج پول حقیقی در ۱۰ روز معاملاتی اخیر
total_10d = sum(day.real_money_flow for day in recent_flows)
print(f"جمع جریان پول حقیقی ۱۰ روزه: {total_10d / 1e10:+,.2f} میلیارد تومان")
```

---

## گام ۴: بررسی ۵ سطر سفارش و تشخیص صف خرید / فروش

برای اینکه ویژگی‌های `is_buy_queue` و `is_sell_queue` فعال شوند، حتماً گزینهٔ `include_thresholds=True` را ارسال کنید تا آستانهٔ مجاز قیمت (`price_min_allowed` و `price_max_allowed`) همراه سفارش‌ها دریافت شود:

```python
with ts.Client() as client:
    book = client.prices.order_book("کگل", include_thresholds=True)

if book.is_buy_queue:
    top = book.best_level
    queue_value_toman = (top.bid_price * top.bid_volume) / 1e10
    print(f"صف خرید تشکیل شده است! ارزش صف: {queue_value_toman:,.1f} میلیارد تومان")
elif book.is_sell_queue:
    top = book.best_level
    queue_value_toman = (top.ask_price * top.ask_volume) / 1e10
    print(f"صف فروش تشکیل شده است! ارزش صف: {queue_value_toman:,.1f} میلیارد تومان")
else:
    print(f"معاملات متعادل | شکاف قیمت (Spread): {book.spread} ریال")

for lvl in book.levels:
    print(
        f"سطح {lvl.row}: "
        f"خرید {lvl.bid_volume:>10,} @ {lvl.bid_price:>8,.0f} | "
        f"فروش {lvl.ask_volume:>10,} @ {lvl.ask_price:>8,.0f}"
    )
```

---

## گام ۵: بررسی سهامداران عمده، کدال و پیام‌های ناظر

پیش از هر نتیجه‌گیری، به‌خصوص وقتی حجم معاملات صفر است یا نوسان غیرعادی می‌بینید، سهامداران بالای ۱٪، آخرین گزارش‌های کدال و پیام‌های ناظر بازار را بررسی کنید:

```python
with ts.Client() as client:
    holders = client.disclosures.shareholders("کگل")
    filings = client.disclosures.codal("کگل", limit=5)
    notices = client.disclosures.messages("کگل", limit=5)

print("--- سهامداران عمده (>1%) ---")
for h in holders[:5]:
    print(f"{h.name}: {h.percent:.2f}% (تغییر روزانه: {h.change:+,})")

print("\n--- آخرین اطلاعیه‌های کدال ---")
for f in filings:
    print(f"[{f.publish_datetime}] {f.title}")

print("\n--- آخرین پیام‌های ناظر بازار ---")
for m in notices:
    print(f"[{m.date} {m.time}] {m.title}")
```

---

## اسکریپت کامل: گزارش یکپارچهٔ تک‌سهم

می‌توانید کل سناریوی بالا را در یک تابع آماده ذخیره کنید و هر روز روی فهرست دیده‌بان خود اجرا کنید:

```python
import tehran_stocks as ts


def stock_brief(symbol: str) -> None:
    with ts.Client() as client:
        info = client.instruments.info(symbol)
        q = client.prices.quote(symbol)
        flow = client.client_type.live(symbol)
        book = client.prices.order_book(symbol, include_thresholds=True)
        notices = client.disclosures.messages(symbol, limit=2)

    print(f"=== {info.symbol} ({info.name}) ===")
    print(f"صنعت: {info.sector_name} | وضعیت: {q.state_title}")
    print(f"آخرین: {q.last:,.0f} ریال ({q.change_pct:+.2f}%) | پایانی: {q.close:,.0f} ریال")
    print(f"ارزش معاملات: {q.value / 1e10:,.1f} میلیارد تومان | حجم: {q.volume:,}")
    print(
        f"پول حقیقی: {flow.real_money_flow / 1e10:+,.2f} میلیارد تومان | "
        f"قدرت خریدار: {flow.buyer_power:.2f}"
    )

    if book.is_buy_queue:
        print("وضعیت سفارش‌ها: صف خرید")
    elif book.is_sell_queue:
        print("وضعیت سفارش‌ها: صف فروش")
    else:
        print(f"وضعیت سفارش‌ها: متعادل (مجموع خرید ۵ سطر: {book.total_bid_volume:,})")

    if notices:
        print(f"آخرین پیام ناظر: [{notices[0].date}] {notices[0].title}")


if __name__ == "__main__":
    stock_brief("کگل")
```

---

## ادامهٔ مسیر

- می‌خواهید تاریخچهٔ چندسالهٔ سهم را به‌صورت تعدیل‌شده و با تقویم جلالی در `pandas` تحلیل کنید؟ به [سناریو ۲: تحلیل تاریخچهٔ تعدیل‌شده و تقویم جلالی](jalali-pandas.md) بروید.
- می‌خواهید همین بررسی را روی کل بازار انجام دهید؟ [سناریو ۳: رصد کل بازار و فیلترنویسی](market-screening.md) را بخوانید.
