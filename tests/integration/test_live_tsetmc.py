"""Live smoke integration tests against https://cdn.tsetmc.com/api/... endpoints.

Skipped by default via ``addopts = "-m 'not live'"`` in ``pyproject.toml``.
Run explicitly with ``uv run pytest -m live -v``.
"""

from __future__ import annotations

import asyncio
import re

import jalali_pandas
import pandas as pd
import pytest

import tehran_stocks as ts
from tehran_stocks.types import (
    ClientTypeDaily,
    ClientTypeLive,
    CodalAnnouncement,
    DailyBar,
    IndexBar,
    IndexQuote,
    Instrument,
    MarketOverview,
    OrderBook,
    Quote,
    Sector,
    Shareholder,
)

KGL_INS_CODE = "35700344742885862"
TEDPIX_INS_CODE = "32097828799138957"

pytestmark = pytest.mark.live


@pytest.mark.live
def test_live_on_demand_endpoints_and_jalali_dataframe() -> None:
    """Verify core top-level SDK calls and jalali-pandas v1.0.0 integration live."""
    # Exercise zero-config top-level search without an explicit client.
    search_results = ts.search("کگل")
    assert len(search_results) >= 1
    assert all(isinstance(item, Instrument) for item in search_results)
    assert any(
        item.ins_code == KGL_INS_CODE and item.symbol == "کگل"
        for item in search_results
    )

    with ts.Client(timeout=30.0) as client:
        # Quote
        quote = ts.quote("کگل", client=client)
        assert isinstance(quote, Quote)
        assert quote.ins_code == KGL_INS_CODE
        assert quote.close > 0
        assert quote.date is not None

        # Adjusted daily history + jalali-pandas v1.0.0 DataFrame
        bars = ts.history("کگل", days=5, adjusted=True, client=client)
        assert 1 <= len(bars) <= 5
        assert all(isinstance(bar, DailyBar) for bar in bars)
        assert bars == sorted(bars, key=lambda bar: bar.date)
        assert all(bar.close > 0 for bar in bars)

        df = ts.to_dataframe(bars, jalali=True, index_by_date=True)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "jdate" in df.columns
        assert isinstance(df.index, jalali_pandas.JalaliDatetimeIndex)
        assert df.index[0].year >= 1400
        jdate_strings = df["date"].jalali.to_jalali().jalali.strftime("%Y-%m-%d")
        assert re.match(r"^14\d{2}-\d{2}-\d{2}$", str(jdate_strings.iloc[-1]))

        # Client type live & history (حقیقی / حقوقی)
        ct_live = ts.client_type("کگل", client=client)
        assert isinstance(ct_live, ClientTypeLive)
        assert ct_live.ins_code == KGL_INS_CODE
        assert ct_live.buy_i_volume >= 0
        assert ct_live.sell_i_volume >= 0

        ct_history = ts.client_type_history("کگل", days=5, client=client)
        assert 1 <= len(ct_history) <= 5
        assert all(isinstance(row, ClientTypeDaily) for row in ct_history)
        assert ct_history == sorted(ct_history, key=lambda row: row.date)

        # 5-level order book (with and without static thresholds)
        book = ts.order_book("کگل", client=client)
        assert isinstance(book, OrderBook)
        assert book.ins_code == KGL_INS_CODE
        assert 0 <= len(book.levels) <= 5

        book_with_thresholds = ts.order_book(
            "کگل", include_thresholds=True, client=client
        )
        assert (
            book_with_thresholds.price_max_allowed is not None
            and book_with_thresholds.price_max_allowed > 0
        )
        assert (
            book_with_thresholds.price_min_allowed is not None
            and book_with_thresholds.price_min_allowed > 0
        )

        # Market overview, sectors, indices
        overview = ts.market_overview(client=client)
        assert isinstance(overview, MarketOverview)
        assert overview.flow == 1
        assert overview.index_value > 0
        assert overview.equal_weighted_index > 0

        sector_list = ts.sectors(client=client)
        assert len(sector_list) >= 20
        assert all(isinstance(sector, Sector) for sector in sector_list)
        assert any(sector.code == "13" for sector in sector_list)

        index_list = ts.indices(client=client)
        assert len(index_list) >= 10
        assert all(isinstance(idx, IndexQuote) for idx in index_list)
        assert any(idx.ins_code == TEDPIX_INS_CODE for idx in index_list)

        # Shareholders & Codal disclosures
        holder_list = ts.shareholders("کگل", client=client)
        assert len(holder_list) >= 1
        assert all(isinstance(holder, Shareholder) for holder in holder_list)
        assert all(holder.percent >= 0 for holder in holder_list)
        assert any(holder.percent > 0 for holder in holder_list)

        codal_list = ts.codal("کگل", limit=3, client=client)
        assert 1 <= len(codal_list) <= 3
        assert all(isinstance(item, CodalAnnouncement) for item in codal_list)
        assert all(item.tracing_no > 0 and item.title for item in codal_list)


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_async_client_and_arabic_normalization() -> None:
    """Verify AsyncClient concurrent live requests and Arabic ك/ي normalization."""
    async with ts.AsyncClient(timeout=30.0) as client:
        resolved = await client.resolve("كگل")
        assert resolved == KGL_INS_CODE

        quote, overview, tedpix_bars = await asyncio.gather(
            client.prices.quote("كگل"),
            client.market.overview(flow=1),
            client.market.index_history("TEDPIX"),
        )
        assert isinstance(quote, Quote)
        assert quote.ins_code == KGL_INS_CODE
        assert quote.close > 0

        assert isinstance(overview, MarketOverview)
        assert overview.index_value > 0

        assert len(tedpix_bars) > 0
        assert all(isinstance(bar, IndexBar) for bar in tedpix_bars)
        assert tedpix_bars[-1].value > 0
