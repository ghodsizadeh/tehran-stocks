"""Comprehensive sync and async tests for the httpx2 TSETMC client layer."""

from __future__ import annotations

import asyncio
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import unquote

import httpx2
import pytest

from tehran_stocks import api
from tehran_stocks.client import (
    DEFAULT_BASE_URL,
    AsyncClient,
    AsyncTSETMCClient,
    Client,
    TSETMCClient,
)
from tehran_stocks.exceptions import InstrumentNotFoundError, RateLimitError, TSETMCError
from tehran_stocks.types import (
    ClientTypeDaily,
    ClientTypeLive,
    CodalAnnouncement,
    DailyBar,
    ETFInfo,
    IndexBar,
    IndexEffectItem,
    IndexQuote,
    Instrument,
    InstrumentIdentity,
    InstrumentInfo,
    InstrumentStatistic,
    IntradayTick,
    MarketOverview,
    MarketWatchItem,
    OptionWatchItem,
    OrderBook,
    PriceAdjustment,
    Quote,
    Sector,
    ShareChange,
    Shareholder,
    SupervisorMessage,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
KGL_INS_CODE = "35700344742885862"
ETF_INS_CODE = "52551569846042389"
TEDPIX_INS_CODE = "32097828799138957"


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_tsetmc_router(
    call_log: list[str] | None = None,
    *,
    extra_routes: dict[str, Any] | None = None,
) -> httpx2.MockTransport:
    """Build an httpx2.MockTransport routing cdn.tsetmc.com endpoints to real JSON fixtures."""
    fixtures = {
        "search": _load_fixture("search.json"),
        "info": _load_fixture("instrument_info.json"),
        "identity": _load_fixture("instrument_identity.json"),
        "stats": _load_fixture("instrument_stats.json"),
        "share_changes": _load_fixture("share_changes.json"),
        "quote": _load_fixture("quote.json"),
        "daily_history": _load_fixture("daily_history.json"),
        "price_adjustments": _load_fixture("price_adjustments.json"),
        "orderbook": _load_fixture("orderbook.json"),
        "intraday": _load_fixture("intraday.json"),
        "client_type_live": _load_fixture("client_type_live.json"),
        "client_type_history": _load_fixture("client_type_history.json"),
        "client_type_all": _load_fixture("client_type_all.json"),
        "market_watch": _load_fixture("market_watch.json"),
        "static_data": _load_fixture("static_data.json"),
        "sectors_summary": _load_fixture("sectors_summary.json"),
        "market_overview": _load_fixture("market_overview.json"),
        "indices": _load_fixture("indices.json"),
        "index_history": _load_fixture("index_history.json"),
        "shareholders": _load_fixture("shareholders.json"),
        "codal": _load_fixture("codal.json"),
        "messages": _load_fixture("messages.json"),
        "etf": _load_fixture("etf.json"),
        "options_watch": _load_fixture("options_watch.json"),
    }

    synthetic_routes: dict[str, Any] = {
        "/api/ClosingPrice/GetRelatedCompany/13": {
            "relatedCompany": [
                {
                    "instrument": {
                        "insCode": KGL_INS_CODE,
                        "lVal18AFC": "كگل",
                        "lVal30": "معدني و صنعتي گل گهر",
                        "flow": 1,
                        "flowTitle": "بازار بورس",
                        "zTitad": 655000000000.0,
                    },
                    "cSecVal": "13",
                },
                {
                    "insCode": "18063426058703995",
                    "lVal18AFC": "كچاد",
                    "lVal30": "معدني و صنعتي چادرملو",
                    "flow": 1,
                    "flowTitle": "بازار بورس",
                },
            ]
        },
        f"/api/Index/GetInstEffect/{TEDPIX_INS_CODE}/1/10": {
            "instEffect": [
                {
                    "instrument": {"insCode": KGL_INS_CODE, "lVal18AFC": "كگل", "lVal30": "گل گهر"},
                    "pClosing": 4110.0,
                    "priceChange": 110.0,
                    "instEffectValue": 4250.5,
                }
            ]
        },
        "/api/ClosingPrice/GetTradeTop/1/1/10": {
            "tradeTop": [
                {
                    "instrument": {
                        "insCode": KGL_INS_CODE,
                        "lVal18AFC": "كگل",
                        "lVal30": "معدني و صنعتي گل گهر",
                        "cIsin": "IRO1GOLG0005",
                    },
                    "pDrCotVal": 4120.0,
                    "pClosing": 4110.0,
                    "priceYesterday": 4000.0,
                    "qTotTran5J": 441108505,
                    "qTotCap": 1814088254160,
                    "zTotTran": 4608,
                }
            ]
        },
    }
    if extra_routes:
        synthetic_routes.update(extra_routes)

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = unquote(request.url.path)
        if call_log is not None:
            call_log.append(path)

        assert "Chrome/" in request.headers.get("User-Agent", "")
        assert "application/json" in request.headers.get("Accept", "")

        if path in synthetic_routes:
            payload = synthetic_routes[path]
            if callable(payload):
                return payload(request)
            return httpx2.Response(200, json=payload)

        if path.startswith("/api/Instrument/GetInstrumentSearch/"):
            query = path.removeprefix("/api/Instrument/GetInstrumentSearch/")
            if query in ("ناموجود", "NOT_FOUND_XYZ"):
                return httpx2.Response(200, json={"instrumentSearch": []})
            if query == "بمان":
                return httpx2.Response(
                    200,
                    json={
                        "instrumentSearch": [
                            {
                                "insCode": ETF_INS_CODE,
                                "lVal18AFC": "بمان",
                                "lVal30": "صندوق س.بازده مانا-د",
                                "flow": 2,
                                "flowTitle": "بازار فرابورس",
                                "cgrValCot": "1A",
                                "lastDate": 1,
                            }
                        ]
                    },
                )
            return httpx2.Response(200, json=fixtures["search"])

        static_map = {
            f"/api/Instrument/GetInstrumentInfo/{KGL_INS_CODE}": fixtures["info"],
            f"/api/Instrument/GetInstrumentIdentity/{KGL_INS_CODE}": fixtures["identity"],
            f"/api/MarketData/GetInstrumentStatistic/{KGL_INS_CODE}": fixtures["stats"],
            f"/api/Instrument/GetInstrumentShareChange/{KGL_INS_CODE}": fixtures["share_changes"],
            f"/api/ClosingPrice/GetClosingPriceInfo/{KGL_INS_CODE}": fixtures["quote"],
            f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/0": fixtures["daily_history"],
            f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/5": {
                "closingPriceDaily": fixtures["daily_history"]["closingPriceDaily"][:5]
            },
            f"/api/ClosingPrice/GetPriceAdjustList/{KGL_INS_CODE}": fixtures["price_adjustments"],
            f"/api/BestLimits/{KGL_INS_CODE}": fixtures["orderbook"],
            f"/api/ClientType/GetClientType/{KGL_INS_CODE}/1/0": fixtures["client_type_live"],
            f"/api/ClientType/GetClientTypeHistory/{KGL_INS_CODE}": fixtures["client_type_history"],
            "/api/ClientType/GetClientTypeAll": fixtures["client_type_all"],
            "/api/ClosingPrice/GetMarketWatch": fixtures["market_watch"],
            "/api/MarketData/GetMarketOverview/1": fixtures["market_overview"],
            "/api/MarketData/GetSectorsSummary": fixtures["sectors_summary"],
            "/api/StaticData/GetStaticData": fixtures["static_data"],
            "/api/Index/GetIndexB1LastAll/All/1": fixtures["indices"],
            f"/api/Index/GetIndexB2History/{TEDPIX_INS_CODE}": fixtures["index_history"],
            f"/api/Shareholder/GetInstrumentShareHolderLast/{KGL_INS_CODE}": fixtures["shareholders"],
            f"/api/Codal/GetPreparedDataByInsCode/10/{KGL_INS_CODE}": fixtures["codal"],
            f"/api/Msg/GetMsgByInsCode/{KGL_INS_CODE}": fixtures["messages"],
            f"/api/Fund/GetETFByInsCode/{ETF_INS_CODE}": fixtures["etf"],
            "/api/Instrument/GetInstrumentOptionMarketWatch/1": fixtures["options_watch"],
        }
        if path in static_map:
            return httpx2.Response(200, json=static_map[path])

        if path.startswith(f"/api/ClosingPrice/GetClosingPriceHistory/{KGL_INS_CODE}/"):
            return httpx2.Response(200, json=fixtures["intraday"])

        return httpx2.Response(404, json={"error": f"Unhandled path: {path}"})

    return httpx2.MockTransport(handler)


def test_sync_client_all_resources_with_real_fixtures() -> None:
    calls: list[str] = []
    mock_transport = _make_tsetmc_router(calls)

    with Client(transport=mock_transport, retry_backoff=0.0) as client:
        assert isinstance(client, TSETMCClient)
        assert client.transport.base_url == DEFAULT_BASE_URL

        # Instruments
        search_res = client.instruments.search("کگل")
        assert len(search_res) > 0
        assert all(isinstance(item, Instrument) for item in search_res)
        assert search_res[0].ins_code == KGL_INS_CODE
        assert search_res[0].symbol == "کگل"

        info = client.instruments.info("کگل")
        assert isinstance(info, InstrumentInfo)
        assert info.ins_code == KGL_INS_CODE
        assert info.eps == pytest.approx(275.0)
        assert info.sector_code == "13"
        assert info.price_max_allowed == pytest.approx(4120.0)
        assert info.price_min_allowed == pytest.approx(3880.0)

        identity = client.instruments.identity("كگل")
        assert isinstance(identity, InstrumentIdentity)
        assert identity.ins_code == KGL_INS_CODE
        assert identity.sub_sector_name == "استخراج آهن"

        stats = client.instruments.statistics(KGL_INS_CODE)
        assert len(stats) == 20
        assert isinstance(stats[0], InstrumentStatistic)
        assert stats[0].ins_code == KGL_INS_CODE
        assert "میانگین ارزش معاملات" in stats[0].name

        changes = client.instruments.share_changes("کگل")
        assert len(changes) == 15
        assert isinstance(changes[0], ShareChange)
        assert changes[0].new_shares == 655000000000

        related = client.instruments.related("13 ")
        assert len(related) == 2
        assert related[0].symbol == "کگل"
        assert related[1].symbol == "کچاد"

        # Prices
        quote = client.prices.quote("کگل")
        assert isinstance(quote, Quote)
        assert quote.ins_code == KGL_INS_CODE
        assert quote.last == pytest.approx(4120.0)
        assert quote.close == pytest.approx(4110.0)
        assert quote.state_title == "مجاز"

        bars = client.prices.history("کگل")
        assert len(bars) == 15
        assert all(isinstance(b, DailyBar) for b in bars)
        assert bars[0].date == date(2026, 11, 2)
        assert bars[-1].date == date(2026, 11, 22)

        filtered = client.prices.history(
            "کگل",
            days=5,
            start=date(2026, 11, 17),
            end="2026-11-21",
        )
        assert [b.date for b in filtered] == [
            date(2026, 11, 17),
            date(2026, 11, 18),
            date(2026, 11, 21),
        ]

        adjs = client.prices.adjustments("کگل")
        assert len(adjs) == 15
        assert isinstance(adjs[0], PriceAdjustment)

        book = client.prices.order_book("کگل")
        assert isinstance(book, OrderBook)
        assert len(book.levels) == 5
        assert book.best_level is not None
        assert book.best_level.bid_price == pytest.approx(4120.0)
        assert book.spread == pytest.approx(30.0)

        book_with_thresholds = client.prices.order_book("کگل", include_thresholds=True)
        assert book_with_thresholds.price_max_allowed == pytest.approx(4120.0)
        assert book_with_thresholds.price_min_allowed == pytest.approx(3880.0)

        ticks = client.prices.intraday("کگل", date="2026-11-22")
        assert len(ticks) > 0
        assert all(isinstance(t, IntradayTick) for t in ticks)
        assert ticks[-1].date == date(2026, 11, 22)
        assert ticks[-1].time == "12:29:51"

        # Client type
        ct_live = client.client_type.live("کگل")
        assert isinstance(ct_live, ClientTypeLive)
        assert ct_live.buy_i_volume == 168040481
        assert ct_live.buy_i_count == 628

        ct_hist_all = client.client_type.history("کگل", days=0)
        assert len(ct_hist_all) == 15

        ct_hist = client.client_type.history("کگل", days=5)
        assert len(ct_hist) == 5
        assert all(isinstance(item, ClientTypeDaily) for item in ct_hist)
        assert ct_hist[-1].date == date(2026, 11, 22)
        assert ct_hist[-1].buy_i_count == 1022
        assert ct_hist[-1].sell_i_count == 796
        assert ct_hist[-1].real_money_flow == 681368933310 - 550052671100
        assert ct_hist[-1].buyer_power > 0

        ct_all = client.client_type.all()
        assert len(ct_all) == 11
        assert ct_all[0].ins_code == "56749722173437552"

        # Market
        watch = client.market.watch()
        assert len(watch) > 0
        assert all(isinstance(w, MarketWatchItem) for w in watch)
        assert watch[0].symbol == "مبین"
        assert watch[0].order_book == ()

        overview = client.market.overview(flow=1)
        assert isinstance(overview, MarketOverview)
        assert overview.market_state == "بسته"
        assert overview.index_value == pytest.approx(8389814.07)

        sectors = client.market.sectors()
        assert len(sectors) > 0
        assert all(isinstance(s, Sector) for s in sectors)
        metal_ore = next(s for s in sectors if s.code == "13")
        assert metal_ore.name == "استخراج کانه های فلزی"
        assert metal_ore.type == "IndustrialGroup"

        indices = client.market.indices(flow=1)
        assert len(indices) > 0
        assert isinstance(indices[0], IndexQuote)
        assert indices[0].change_pct == pytest.approx(1.6846)

        idx_hist = client.market.index_history("TEDPIX")
        assert len(idx_hist) == 15
        assert isinstance(idx_hist[0], IndexBar)
        assert idx_hist[0].date == date(2026, 11, 2)
        assert idx_hist[-1].date == date(2026, 11, 22)

        idx_eff = client.market.index_effect(TEDPIX_INS_CODE)
        assert len(idx_eff) == 1
        assert isinstance(idx_eff[0], IndexEffectItem)
        assert idx_eff[0].symbol == "کگل"

        top = client.market.top_trades()
        assert len(top) == 1
        assert top[0].symbol == "کگل"
        assert top[0].last == pytest.approx(4120.0)

        # Disclosures
        shs = client.disclosures.shareholders("کگل")
        assert len(shs) == 12
        assert isinstance(shs[0], Shareholder)
        assert shs[0].shareholder_id == 1414331
        assert shs[0].percent == pytest.approx(33.952)

        codals = client.disclosures.codal("کگل", limit=10)
        assert len(codals) == 5
        assert isinstance(codals[0], CodalAnnouncement)
        assert codals[0].tracing_no == 1633100
        assert codals[0].date == date(2026, 11, 11)
        assert codals[0].has_pdf is True
        assert codals[0].has_excel is False

        msgs = client.disclosures.messages("کگل", limit=3)
        assert len(msgs) == 3
        assert isinstance(msgs[0], SupervisorMessage)
        assert msgs[0].msg_id == 264802
        assert msgs[0].time == "15:18:31"

        # Funds
        etf_info = client.funds.etf("بمان")
        assert isinstance(etf_info, ETFInfo)
        assert etf_info.ins_code == ETF_INS_CODE
        assert etf_info.date == date(2026, 11, 23)
        assert etf_info.redemption_nav == pytest.approx(23412.0)
        assert etf_info.subscription_nav == pytest.approx(23433.0)

        opts = client.funds.options(flow=1)
        assert len(opts) > 0
        assert all(isinstance(o, OptionWatchItem) for o in opts)
        assert opts[0].symbol == "ضهرم9024"
        assert opts[1].symbol == "طهرم9024"
        assert opts[0].strike_price == pytest.approx(46000.0)
        assert opts[0].expiration_date == date(2026, 12, 16)


@pytest.mark.asyncio
async def test_async_client_all_resources_and_concurrency() -> None:
    in_flight = 0
    max_seen_concurrency = 0

    base_router = _make_tsetmc_router()

    async def async_handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal in_flight, max_seen_concurrency
        in_flight += 1
        max_seen_concurrency = max(max_seen_concurrency, in_flight)
        try:
            await asyncio.sleep(0.01)
            return base_router.handler(request)
        finally:
            in_flight -= 1

    async with AsyncClient(
        transport=httpx2.MockTransport(async_handler),
        max_concurrency=2,
        retry_backoff=0.0,
    ) as client:
        assert isinstance(client, AsyncTSETMCClient)
        quote, bars, book, ct_live, overview, sectors, etf_info, opts = await asyncio.gather(
            client.prices.quote("کگل"),
            client.prices.history("کگل"),
            client.prices.order_book("کگل"),
            client.client_type.live("کگل"),
            client.market.overview(),
            client.market.sectors(),
            client.funds.etf("بمان"),
            client.funds.options(),
        )
        assert quote.close == pytest.approx(4110.0)
        assert len(bars) == 15
        assert len(book.levels) == 5
        assert ct_live.buy_i_count == 628
        assert overview.index_value == pytest.approx(8389814.07)
        assert any(s.code == "13" for s in sectors)
        assert etf_info.redemption_nav == pytest.approx(23412.0)
        assert len(opts) > 0

        # Remaining async endpoints
        info, identity, stats, changes, related, adjs, ticks = await asyncio.gather(
            client.instruments.info("کگل"),
            client.instruments.identity("کگل"),
            client.instruments.statistics("کگل"),
            client.instruments.share_changes("کگل"),
            client.instruments.related("13"),
            client.prices.adjustments("کگل"),
            client.prices.intraday("کگل", date="1405-09-01"),
        )
        assert info.ins_code == KGL_INS_CODE
        assert identity.ins_code == KGL_INS_CODE
        assert len(stats) == 20
        assert len(changes) == 15
        assert len(related) == 2
        assert len(adjs) == 15
        assert ticks[-1].date == date(2026, 11, 22)

        ct_hist, ct_all, watch, indices, idx_hist, idx_eff, top, shs, codals, msgs = (
            await asyncio.gather(
                client.client_type.history("کگل"),
                client.client_type.all(),
                client.market.watch(),
                client.market.indices(),
                client.market.index_history("TEDPIX"),
                client.market.index_effect("TEDPIX"),
                client.market.top_trades(),
                client.disclosures.shareholders("کگل"),
                client.disclosures.codal("کگل"),
                client.disclosures.messages("کگل"),
            )
        )
        assert len(ct_hist) == 15
        assert len(ct_all) == 11
        assert len(watch) > 0
        assert len(indices) > 0
        assert len(idx_hist) == 15
        assert len(idx_eff) == 1
        assert len(top) == 1
        assert len(shs) == 12
        assert len(codals) == 5
        assert len(msgs) == 10

    assert max_seen_concurrency <= 2


def test_symbol_resolution_normalization_priority_cache_and_errors() -> None:
    calls: list[str] = []
    extra = {
        "/api/Instrument/GetInstrumentSearch/فولاد": {
            "instrumentSearch": [
                {
                    "insCode": "99999999999999991",
                    "lVal18AFC": "فولاد",
                    "lVal30": "اختیار معامله فولاد",
                    "flow": 3,
                    "cgrValCot": "3A",
                    "lastDate": 0,
                    "zTitad": 0,
                },
                {
                    "insCode": "46348559193224090",
                    "lVal18AFC": "فولاد",
                    "lVal30": "فولاد مبارکه اصفهان",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                    "zTitad": 500000000000,
                },
            ]
        },
        "/api/Instrument/GetInstrumentSearch/IRO1GOLG0005": {
            "instrumentSearch": [
                {
                    "insCode": "99999999999999999",
                    "lVal18AFC": "كگلح",
                    "lVal30": "ح . معدنی گل گهر",
                    "cIsin": "IRO1GOLG0009",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                },
                {
                    "insCode": KGL_INS_CODE,
                    "lVal18AFC": "كگل",
                    "lVal30": "معدني و صنعتي گل گهر",
                    "cIsin": "IRO1GOLG0005",
                    "instrumentID": "IRO1GOLG0001",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                },
            ]
        },
    }
    transport = _make_tsetmc_router(calls, extra_routes=extra)

    with Client(transport=transport, retry_backoff=0.0) as client:
        # Persian/Arabic equivalents hit cache after first lookup
        assert client.resolve("کگل") == KGL_INS_CODE
        assert client.resolve("كگل") == KGL_INS_CODE
        search_calls = [c for c in calls if "/GetInstrumentSearch/" in c]
        assert len(search_calls) == 1

        # Direct numeric insCode (ASCII and Persian digits) avoids HTTP search call
        assert client.resolve(KGL_INS_CODE) == KGL_INS_CODE
        assert client.resolve("۳۵۷۰۰۳۴۴۷۴۲۸۸۵۸۶۲") == KGL_INS_CODE
        assert len([c for c in calls if "/GetInstrumentSearch/" in c]) == 1

        # ISIN resolution (exact ISIN match + case-insensitive cache hit)
        assert client.resolve("IRO1GOLG0005") == KGL_INS_CODE
        assert client.resolve("iro1golg0005") == KGL_INS_CODE

        # Active equity board (flow=1) wins over derivative/inactive board (flow=3)
        assert client.resolve("فولاد") == "46348559193224090"

        # Unresolved symbols raise InstrumentNotFoundError
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("ناموجود")
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("کگل2")  # present prefix in search.json but no exact match
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("")
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("0")


def test_isin_resolution_rejects_unrelated_search_rows_sync() -> None:
    extra = {
        "/api/Instrument/GetInstrumentSearch/IRO1MISM0002": {
            "instrumentSearch": [
                {
                    "insCode": KGL_INS_CODE,
                    "lVal18AFC": "كگل",
                    "lVal30": "معدني و صنعتي گل گهر",
                    "cIsin": "IRO1GOLG0005",
                    "instrumentID": "IRO1GOLG0001",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                }
            ]
        }
    }
    transport = _make_tsetmc_router(extra_routes=extra)

    with Client(transport=transport, retry_backoff=0.0) as client:
        assert len(client.instruments.search("IRO1UNKN0001")) > 0
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("IRO1UNKN0001")
        with pytest.raises(InstrumentNotFoundError):
            client.resolve("IRO1MISM0002")


@pytest.mark.asyncio
async def test_isin_resolution_rejects_unrelated_search_rows_async() -> None:
    extra = {
        "/api/Instrument/GetInstrumentSearch/IRO1GOLG0005": {
            "instrumentSearch": [
                {
                    "insCode": KGL_INS_CODE,
                    "lVal18AFC": "كگل",
                    "lVal30": "معدني و صنعتي گل گهر",
                    "cIsin": "IRO1GOLG0005",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                }
            ]
        },
        "/api/Instrument/GetInstrumentSearch/IRO1MISM0002": {
            "instrumentSearch": [
                {
                    "insCode": KGL_INS_CODE,
                    "lVal18AFC": "كگل",
                    "lVal30": "معدني و صنعتي گل گهر",
                    "cIsin": "IRO1GOLG0005",
                    "instrumentID": "IRO1GOLG0001",
                    "flow": 1,
                    "cgrValCot": "N1",
                    "lastDate": 1,
                }
            ]
        },
    }
    base_router = _make_tsetmc_router(extra_routes=extra)

    async def async_handler(request: httpx2.Request) -> httpx2.Response:
        return base_router.handler(request)

    async with AsyncClient(
        transport=httpx2.MockTransport(async_handler),
        retry_backoff=0.0,
    ) as client:
        assert await client.resolve("IRO1GOLG0005") == KGL_INS_CODE
        assert len(await client.instruments.search("IRO1UNKN0001")) > 0
        with pytest.raises(InstrumentNotFoundError):
            await client.resolve("IRO1UNKN0001")
        with pytest.raises(InstrumentNotFoundError):
            await client.resolve("IRO1MISM0002")


def test_history_adjusted_scales_bars_before_corporate_action() -> None:
    daily_payload = _load_fixture("daily_history.json")
    adjust_payload = {
        "priceAdjust": [
            {
                "insCode": KGL_INS_CODE,
                "dEven": 20261115,
                "pClosing": 2000.0,
                "pClosingNotAdjusted": 4000.0,
                "corporateTypeCode": 1,
            }
        ]
    }
    transport = _make_tsetmc_router(
        extra_routes={
            f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/0": daily_payload,
            f"/api/ClosingPrice/GetPriceAdjustList/{KGL_INS_CODE}": adjust_payload,
        }
    )

    with Client(transport=transport, retry_backoff=0.0) as client:
        raw_bars = client.prices.history(KGL_INS_CODE, adjusted=False)
        adj_bars = client.prices.history(KGL_INS_CODE, adjusted=True)

    assert len(raw_bars) == len(adj_bars) == 15
    # Bar strictly before 2026-11-15 is scaled by 2000 / 4000 = 0.5
    assert raw_bars[0].date == date(2026, 11, 2)
    assert adj_bars[0].close == pytest.approx(raw_bars[0].close * 0.5)
    assert adj_bars[0].open == pytest.approx(raw_bars[0].open * 0.5)
    assert adj_bars[0].volume == raw_bars[0].volume

    # Bar on/after 2026-11-15 remains unadjusted
    assert adj_bars[-1].date == date(2026, 11, 22)
    assert adj_bars[-1].close == pytest.approx(raw_bars[-1].close)


def test_retries_on_502_429_and_transport_errors() -> None:
    attempts = {"502": 0, "429_ok": 0, "429_fail": 0, "conn": 0, "404": 0}
    quote_payload = _load_fixture("quote.json")

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/api/ClosingPrice/GetClosingPriceInfo/111111":
            attempts["502"] += 1
            if attempts["502"] < 3:
                return httpx2.Response(502, json={"error": "bad gateway"})
            return httpx2.Response(200, json=quote_payload)

        if path == "/api/ClosingPrice/GetClosingPriceInfo/222222":
            attempts["429_ok"] += 1
            if attempts["429_ok"] == 1:
                return httpx2.Response(429, headers={"Retry-After": "0"}, json={"error": "slow"})
            return httpx2.Response(200, json=quote_payload)

        if path == "/api/ClosingPrice/GetClosingPriceInfo/333333":
            attempts["429_fail"] += 1
            return httpx2.Response(429, headers={"Retry-After": "0.01"}, json={"error": "blocked"})

        if path == "/api/ClosingPrice/GetClosingPriceInfo/444444":
            attempts["conn"] += 1
            if attempts["conn"] == 1:
                raise httpx2.ConnectError("transient network failure", request=request)
            return httpx2.Response(200, json=quote_payload)

        if path == "/api/ClosingPrice/GetClosingPriceInfo/555555":
            attempts["404"] += 1
            return httpx2.Response(404, json={"error": "missing"})

        if path == "/api/ClosingPrice/GetClosingPriceInfo/666666":
            return httpx2.Response(200, content=b"<html>not json</html>")

        return httpx2.Response(404)

    with Client(
        transport=httpx2.MockTransport(handler),
        max_retries=2,
        retry_backoff=0.0,
    ) as client:
        assert client.prices.quote("111111").close == pytest.approx(4110.0)
        assert attempts["502"] == 3

        assert client.prices.quote("222222").close == pytest.approx(4110.0)
        assert attempts["429_ok"] == 2

        with pytest.raises(RateLimitError) as rl_exc:
            client.prices.quote("333333")
        assert rl_exc.value.status_code == 429
        assert rl_exc.value.retry_after == pytest.approx(0.01)
        assert attempts["429_fail"] == 3

        assert client.prices.quote("444444").close == pytest.approx(4110.0)
        assert attempts["conn"] == 2

        with pytest.raises(TSETMCError) as not_found_exc:
            client.prices.quote("555555")
        assert not_found_exc.value.status_code == 404
        assert attempts["404"] == 1

        with pytest.raises(TSETMCError):
            client.prices.quote("666666")


def test_url_path_escaping_and_non_finite_retry_after() -> None:
    seen_raw_paths: list[bytes] = []

    def escaping_handler(request: httpx2.Request) -> httpx2.Response:
        seen_raw_paths.append(request.url.raw_path)
        assert request.url.query == b""
        assert request.url.fragment == ""
        return httpx2.Response(
            200,
            json={
                "instrumentSearch": [
                    {
                        "insCode": KGL_INS_CODE,
                        "lVal18AFC": "A/B%C",
                        "lVal30": "Test Instrument",
                        "flow": 1,
                    }
                ]
            },
        )

    with Client(transport=httpx2.MockTransport(escaping_handler), retry_backoff=0.0) as client:
        assert client.resolve("A/B%C") == KGL_INS_CODE
        results = client.instruments.search("A/B%C?k=1#frag")
        assert len(results) == 1

    assert seen_raw_paths == [
        b"/api/Instrument/GetInstrumentSearch/A%2FB%25C",
        b"/api/Instrument/GetInstrumentSearch/A%2FB%25C%3Fk%3D1%23frag",
    ]

    def retry_after_handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/777777"):
            return httpx2.Response(429, headers={"Retry-After": "inf"})
        return httpx2.Response(429, headers={"Retry-After": "nan"})

    with Client(
        transport=httpx2.MockTransport(retry_after_handler),
        max_retries=1,
        retry_backoff=0.0,
    ) as client:
        with pytest.raises(RateLimitError) as inf_exc:
            client.prices.quote("777777")
        assert inf_exc.value.retry_after is None

        with pytest.raises(RateLimitError) as nan_exc:
            client.prices.quote("888888")
        assert nan_exc.value.retry_after is None


@pytest.mark.asyncio
async def test_async_retries_on_502_and_rate_limit() -> None:
    calls = 0
    quote_payload = _load_fixture("quote.json")

    async def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(502)
        if calls == 2:
            return httpx2.Response(429, headers={"Retry-After": "0"})
        return httpx2.Response(200, json=quote_payload)

    async with AsyncClient(
        transport=httpx2.MockTransport(handler),
        max_retries=2,
        retry_backoff=0.0,
    ) as client:
        q = await client.prices.quote(KGL_INS_CODE)
        assert q.close == pytest.approx(4110.0)
        assert calls == 3


def test_top_level_api_functions() -> None:
    mock_transport = _make_tsetmc_router()
    with Client(transport=mock_transport, retry_backoff=0.0) as client:
        assert api.search("کگل", client=client)[0].ins_code == KGL_INS_CODE
        assert api.quote("کگل", client=client).close == pytest.approx(4110.0)
        assert len(api.history("کگل", client=client)) == 15
        assert len(api.history("کگل", adjusted=True, client=client)) == 15
        assert api.client_type("کگل", client=client).buy_i_count == 628
        assert len(api.client_type_history("کگل", days=5, client=client)) == 5
        assert len(api.order_book("کگل", client=client).levels) == 5
        assert api.order_book("کگل", include_thresholds=True, client=client).price_max_allowed == pytest.approx(4120.0)
        assert api.market_overview(client=client).index_value == pytest.approx(8389814.07)
        assert any(s.code == "13" for s in api.sectors(client=client))
        assert len(api.indices(client=client)) > 0
        assert len(api.shareholders("کگل", client=client)) == 12
        assert len(api.codal("کگل", limit=10, client=client)) == 5
        assert api.etf("بمان", client=client).redemption_nav == pytest.approx(23412.0)


def test_transport_validation_and_proxy_configuration() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        Client(max_retries=-1)
    with pytest.raises(ValueError, match="max_concurrency"):
        AsyncClient(max_concurrency=0)

    with Client(proxy="http://127.0.0.1:8888", transport=_make_tsetmc_router()) as client:
        assert client.transport.proxy == "http://127.0.0.1:8888"


def test_client_and_api_zero_import_side_effects(tmp_path: Path) -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PYTHONPATH": str(src_dir),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tehran_stocks import api, client; assert client.DEFAULT_BASE_URL == 'https://cdn.tsetmc.com'",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert list(tmp_path.iterdir()) == []
