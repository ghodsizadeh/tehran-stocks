# Example Notebooks (`tehran-stocks` v3)

Interactive, Colab-ready Jupyter notebooks showcasing `tehran-stocks` v3.0 (Python 3.11+, zero-side-effect SDK, backward-adjusted prices, `jalali-pandas`, `AsyncClient`, optional SQLite storage, and Plotly charts).

| Notebook | What It Covers | Open in Colab |
| :--- | :--- | :--- |
| **[Read_Data.ipynb](Read_Data.ipynb)** | Symbol search (Persian/Arabic normalization), live quotes, `حقیقی / حقوقی` money flow & buyer power, 5-level order book & queue detection, shareholders/Codal/messages, ETF NAV, Jalali CSV export, and optional SQLite / `data-latest` SQL queries. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ghodsizadeh/tehran-stocks/blob/master/Example/Read_Data.ipynb) |
| **[Technical Analysis.ipynb](Technical%20Analysis.ipynb)** | Raw vs. backward-adjusted prices (`adjusted=True`), calendar-accurate Jalali monthly OHLCV candles (`JalaliDatetimeIndex`), dependency-free SMA/Bollinger/RSI-14/MACD, retail flow overlay, and a 4-panel Matplotlib dashboard. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ghodsizadeh/tehran-stocks/blob/master/Example/Technical%20Analysis.ipynb) |
| **[Market_Screening_and_Charts.ipynb](Market_Screening_and_Charts.ipynb)** | TEDPIX vs. Equal-Weighted breadth & top sectors, full-market screener in 2 HTTP calls (`watch()` + `client_type.all()`), parallel watchlist returns & correlation with `AsyncClient`, interactive Plotly candlestick chart (replacing legacy `cufflinks`), and `tse` CLI one-liners. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ghodsizadeh/tehran-stocks/blob/master/Example/Market_Screening_and_Charts.ipynb) |

> 📖 Full Persian RTL documentation: [https://ghodsizadeh.github.io/tehran-stocks/](https://ghodsizadeh.github.io/tehran-stocks/)
