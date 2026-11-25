# Tehran Stock Exchange (TSETMC) Domain Glossary

Essential financial, regulatory, and technical conventions for interpreting `tehran-stocks` v3.0 data accurately.

---

## 1. Identifiers, Markets & Text Normalization

| Term | Field / Example | Meaning & Handling |
| :--- | :--- | :--- |
| **`insCode`** | `"35700344742885862"` (`کگل`), `"32097828799138957"` (`TEDPIX`) | Unique 17-digit TSETMC internal instrument identifier used across `cdn.tsetmc.com/api/...` endpoints. |
| **Ticker (`نماد`)** | `lVal18AFC` (`کگل`, `فولاد`, `شپنا`, `خودرو`) | Short Persian symbol. Suffixes/prefixes encode instrument variants (e.g., `ح` for subscription rights `حق تقدم`, `ض`/`ط` for options, digits for bonds/sukuk). |
| **ISIN (`شناسه`)** | `cIsin` (e.g., `IRO1GOHR0001`) | International Securities Identification Number; accepted directly by the `tehran-stocks` resolver. |
| **Persian vs. Arabic Normalization** | `ک`/`ی` vs. `ك`/`ي` | TSETMC frequently stores Arabic Kaf (`\u0643`) and Yeh (`\u064a`), while modern keyboards/LLMs type Persian Kaf (`\u06a9`) and Yeh (`\u06cc`). `tehran-stocks` runs `normalize_persian()` transparently on symbol resolution and DB lookups. |
| **Market Flows (`بازارها`)** | Bourse (`بورس`), Farabourse (`فرابورس` / IFB), Base Market (`پایه`) | Primary exchange segments (`flow` parameter in market overview, indices, and top-trade endpoints). Base market tiers (yellow/orange/red) carry different liquidity and price-limit risks. |
| **`dEven`** | `YYYYMMDD` integer (e.g., `20250318`) | Gregorian trading date integer returned in TSETMC JSON payloads. |

---

## 2. Prices, Closing Calculation & Adjustments

### Last Price vs. Official Closing Price

- **Last Price (`قیمت آخرین معامله`, `pDrCotVal`)**: Price of the most recent executed trade. Reflects live intraday sentiment.
- **Official Closing Price (`قیمت پایانی`, `pClosing`)**: **Volume-weighted average price adjusted for Base Volume (`حجم مبنا`, `baseVol`)**.
  - If traded volume `< baseVol`, `pClosing` moves only proportionally toward the VWAP rather than capturing the full intraday price move.
  - Tomorrow's allowed daily price range (`دامنه نوسان`, `pMin` / `pMax`) is anchored to today's `pClosing`, **not** `pDrCotVal`.

### Static Threshold (`آستانه مجاز قیمت`, `staticThreshold`)

Daily floor (`pMin`) and ceiling (`pMax`) enforced by TSETMC's circuit-breaker rules. Stocks hitting `pMax` or `pMin` form buy or sell queues rather than gapping continuously.

### Currency Units: Rials vs. Tomans

- All TSETMC prices, market caps, and trade values (`qTotCap`) are denominated in **Iranian Rials (IRR / ریال)**.
- Analysts and news sources commonly quote **Tomans (تومان)**: **`1 Toman = 10 Rials`** (`1 Billion Toman = 10 Billion Rials`). Always state whether a figure is in IRR or Tomans.

### Backward Price Adjustment (`قیمت تعدیل‌شده`)

When a company distributes a cash dividend (`تقسیم سود نقدی`) or executes a capital increase (`افزایش سرمایه` from retained earnings, revaluation, or cash contribution), the unadjusted price drops sharply on the reopening date (`بازگشایی پس از مجمع`).

- `GetPriceAdjustList` provides adjustment records (`dEven`, `pClosing`, `pClosingNotAdjusted`, `corporateTypeCode`).
- `tehran-stocks` applies cumulative backward adjustment factors to historical OHLCV bars so multi-year returns, CAGR, RSI, and moving averages remain continuous without artificial gaps.

---

## 3. Individual vs. Institutional Flow (`حقیقی / حقوقی`)

TSETMC publishes exact trade breakdowns between **Individual / Retail traders (`حقیقی`, prefix `I`/`i`)** and **Institutional / Legal entities (`حقوقی`, prefix `N`/`n`)**—both live (`GetClientType`) and daily historical (`GetClientTypeHistory`).

### Core Formulas (Built Into `ClientTypeLive` & `ClientTypeDaily`)

| Metric | Persian Term | Formula | Interpretation |
| :--- | :--- | :--- | :--- |
| **Real Money Flow** | `ورود / خروج پول حقیقی` | `buy_i_value - sell_i_value` | **Positive** = net retail capital inflow (accumulation from institutions); **Negative** = net retail outflow (distribution to institutions). |
| **Per-Capita Buy** | `سرانه خرید حقیقی` | `buy_i_value / buy_i_count` | Average trade value per unique individual buying code. |
| **Per-Capita Sell** | `سرانه فروش حقیقی` | `sell_i_value / sell_i_count` | Average trade value per unique individual selling code. |
| **Buyer-to-Seller Power Ratio** | `قدرت خریدار به فروشنده` | `per_capita_buy / per_capita_sell` | **`> 1.0`** (especially `>= 1.5–2.0`) signals stronger average buy size per person than sell size; **`< 1.0`** signals stronger sell pressure. |

### Analytical Caveats

- **Block Trades (`معاملات بلوکی`)** or **Cross-Trades (`کد به کد`)** between related institutional/major-shareholder accounts can distort single-day `client_type` ratios—cross-check `shareholders` (`>1%` changes) and abnormal spikes in `zTotTran` / `qTotTran5J`.
- Per-capita numbers are most meaningful when daily traded value is non-trivial; tiny volumes on thinly traded symbols produce noisy ratios.

---

## 4. 5-Level Order Book & Buy/Sell Queues (`صف خرید / صف فروش`)

`BestLimits` (`/api/BestLimits/{insCode}`) and `GetMarketWatch` (`blDs`) expose the top **5 bid and ask price levels**:

- **Bid (Demand)**: `pMeDem` (price), `qTitMeDem` (share volume), `zOrdMeDem` (order count)
- **Ask (Supply / Offer)**: `pMeOf` (price), `qTitMeOf` (share volume), `zOrdMeOf` (order count)

### Queue Detection Rules

1. **Buy Queue (`صف خرید`)**: Level-1 best bid price equals the upper static threshold (`pMeDem[0] == pMax`) while best ask supply is absent (`qTitMeOf[0] == 0` / no ask levels). Orders queue for execution at `pMax`; compute **Queue Value** = `pMeDem[0] * qTitMeDem[0]`.
2. **Sell Queue (`صف فروش`)**: Level-1 best ask price equals the lower static threshold (`pMeOf[0] == pMin`) while best bid demand is absent (`qTitMeDem[0] == 0` / no bid levels). Liquidity is trapped; compare **Queue Value** (`pMeOf[0] * qTitMeOf[0]`) against trailing 20-day average daily value to gauge exit difficulty.

---

## 5. Indices, Sectors, ETFs & Disclosures

### Key Benchmarks

- **TEDPIX (`شاخص کل`, `32097828799138957`)**: Market-cap weighted total return index (heavily driven by mega-cap metals, petrochemicals, refineries, and banks).
- **Equal-Weighted Index (`شاخص کل هم‌وزن`)**: Weights all listed stocks equally. When TEDPIX rises while equal-weighted falls, rally breadth is narrow and concentrated in large caps (and vice versa).

### ETFs (`صندوق‌های قابل معامله`)

For ETFs (`GetETFByInsCode`), evaluate **NAV Premium/Discount (`حباب قیمتی`)** rather than traditional P/E:

- **Cancellation NAV (`NAV ابطال`)**: Official redemption net asset value per unit.
- **Statistical NAV (`NAV آماری`)**: Intraday/statistical estimated fair value per unit.
- **`Premium / Discount (%)`** = `(market_price - cancellation_nav) / cancellation_nav * 100`. Equity and gold ETFs routinely trade at small premiums/discounts depending on sentiment and silver/gold/FX expectations; fixed-income ETFs track accrued yield tightly.

### Fundamentals, Shareholders & Disclosures

- **EPS & Sector P/E**: `GetInstrumentInfo` provides `estimatedEPS` and `sectorPE` for peer valuation comparisons.
- **Major Shareholders (`سهامداران عمده`)**: `GetInstrumentShareHolderLast` tracks entities holding **`>1%`**, showing share count, ownership percentage, and day-over-day changes.
- **Codal (`کدال`)**: Official SEC/SEO disclosure portal (`GetPreparedDataByInsCode`) publishing quarterly/annual financial statements, monthly activity reports (`گزارش فعالیت ماهانه`), and capital-increase notices.
- **Supervisor Messages (`پیام ناظر`)**: `GetMsgByInsCode` logs trading halts (`توقف نماد`), reopenings (`بازگشایی`), AGM schedules (`مجمع عمومی`), and >20% price-change clarification halts (`کنفرانس اطلاع‌رسانی`).

---

## 6. Trading Calendar & Jalali (Shamsi) Rules

- **Trading Days**: **Saturday through Wednesday** (closed Thursday, Friday, and official Iranian holidays).
- **Market Session (IRST / UTC+3:30)**: Pre-open order entry (~08:45–09:00), continuous trading (09:00–12:30).
- **Jalali Calendar Geometry**:
  - Months 1–6 (`Farvardin`–`Shahrivar`): **31 days**
  - Months 7–11 (`Mehr`–`Bahman`): **30 days**
  - Month 12 (`Esfand`): **29 days** (30 in leap years)
  - Most Iranian listed corporations end their fiscal year on **Esfand 29/30 (`۱۲/۲۹`)**.
- **Time-Series Resampling Rule**: Never use standard Gregorian pandas resampling (`"ME"`, `"QE"`, `"YE"`) on Iranian financial data—month boundaries misalign by ~9–11 days every month. Use `JalaliDatetimeIndex` from `ts.to_dataframe(..., jalali=True, index_by_date=True)` with explicit OHLCV grouping (`df.groupby([df.index.year, df.index.month]).agg(...)`), or add a `jdatetime` column via `df["date"].jalali.to_jalali()` before using `jalali-pandas` DataFrame helpers (`df.jalali.groupby("yq")`, `df.jalali.filter_by_year(...)`).
