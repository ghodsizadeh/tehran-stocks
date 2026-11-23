"""Unit tests for exceptions, Jalali/Persian utilities, analytics, and domain models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime
import os
from pathlib import Path
import subprocess
import sys

import jalali_pandas
import pandas as pd
import pytest

import tehran_stocks
from tehran_stocks.exceptions import (
    InstrumentNotFoundError,
    RateLimitError,
    StorageError,
    TSETMCError,
    TehranStocksError,
)
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
    OrderBookLevel,
    PriceAdjustment,
    Quote,
    Sector,
    ShareChange,
    Shareholder,
    SupervisorMessage,
)
from tehran_stocks.utils import (
    adjust_prices,
    gregorian_to_jalali,
    int_to_date,
    jalali_to_gregorian,
    normalize_persian,
    parse_tsetmc_time,
    to_dataframe,
)


def test_zero_side_effect_import(tmp_path: Path) -> None:
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
            "import tehran_stocks; assert tehran_stocks.__version__ == '3.0.0'",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert not (tmp_path / ".tse").exists()
    assert list(tmp_path.iterdir()) == []


def test_exception_hierarchy_and_attributes() -> None:
    err = TSETMCError("upstream error", status_code=503, url="https://cdn.tsetmc.com/api/test")
    assert isinstance(err, TehranStocksError)
    assert err.status_code == 503
    assert err.url == "https://cdn.tsetmc.com/api/test"

    rl = RateLimitError(retry_after=2.5)
    assert isinstance(rl, TSETMCError)
    assert isinstance(rl, TehranStocksError)
    assert rl.status_code == 429
    assert rl.retry_after == 2.5

    not_found = InstrumentNotFoundError("کگل")
    assert isinstance(not_found, TehranStocksError)
    assert not_found.query == "کگل"
    assert "کگل" in str(not_found)

    storage_err = StorageError("read-only query violation")
    assert isinstance(storage_err, TehranStocksError)


def test_persian_normalization() -> None:
    assert normalize_persian("كگل") == "کگل"
    assert normalize_persian("شركت معدني و صنعتي گل گهر") == "شرکت معدنی و صنعتی گل گهر"
    assert normalize_persian("فولاد مباركة") == "فولاد مبارکه"
    assert normalize_persian("  فولاد\u200cمبارکه   ۱۲۳٠٩  ") == "فولادمبارکه 12309"
    assert normalize_persian("قند\u200c\u200f١٢٣") == "قند123"
    assert normalize_persian("") == ""


def test_jalali_and_tsetmc_datetime_helpers() -> None:
    assert int_to_date(20240320) == date(2024, 3, 20)
    assert int_to_date("20240320") == date(2024, 3, 20)
    assert int_to_date("2024-03-20") == date(2024, 3, 20)
    assert int_to_date("۲۰۲۴۰۳۲۰") == date(2024, 3, 20)

    assert gregorian_to_jalali(date(2024, 3, 20)) == "1403-01-01"
    assert gregorian_to_jalali(20240320, "%Y/%m/%d") == "1403/01/01"
    assert gregorian_to_jalali(date(2023, 3, 21)) == "1402-01-01"
    assert (
        gregorian_to_jalali(datetime(2024, 3, 20, 12, 30, 5), "%Y-%m-%d %H:%M:%S")
        == "1403-01-01 12:30:05"
    )

    assert jalali_to_gregorian("1403-01-01") == date(2024, 3, 20)
    assert jalali_to_gregorian("1403/01/01") == date(2024, 3, 20)
    assert jalali_to_gregorian("14030101") == date(2024, 3, 20)
    assert jalali_to_gregorian("۱۴۰۳/۰۱/۰۱") == date(2024, 3, 20)

    assert parse_tsetmc_time(122951) == "12:29:51"
    assert parse_tsetmc_time(90503) == "09:05:03"
    assert parse_tsetmc_time("90503") == "09:05:03"
    assert parse_tsetmc_time(0) == "00:00:00"
    assert parse_tsetmc_time("12:29:51") == "12:29:51"

    with pytest.raises(ValueError):
        int_to_date(0)
    with pytest.raises(ValueError):
        jalali_to_gregorian("1403-13-01")
    with pytest.raises(ValueError):
        parse_tsetmc_time(250000)


def test_adjust_prices_backward_cumulative() -> None:
    bars = [
        DailyBar(
            ins_code="35700344742885862",
            date=date(2023, 1, 1),
            open=10000.0,
            high=10200.0,
            low=9800.0,
            close=10000.0,
            last=10100.0,
            yesterday=9900.0,
            volume=1_000_000,
            value=10_000_000_000,
            trade_count=500,
        ),
        DailyBar(
            ins_code="35700344742885862",
            date=date(2024, 1, 1),
            open=10000.0,
            high=10500.0,
            low=9900.0,
            close=10000.0,
            last=10200.0,
            yesterday=10000.0,
            volume=2_000_000,
            value=20_000_000_000,
            trade_count=800,
        ),
        DailyBar(
            ins_code="35700344742885862",
            date=date(2024, 7, 1),
            open=9000.0,
            high=9300.0,
            low=8900.0,
            close=9200.0,
            last=9250.0,
            yesterday=9000.0,
            volume=3_000_000,
            value=27_600_000_000,
            trade_count=1200,
        ),
    ]
    # Provide unsorted adjustments + an invalid zero row to verify resilience
    adjustments = [
        PriceAdjustment(
            ins_code="35700344742885862",
            date=date(2024, 7, 1),
            adjusted_close=9000.0,
            unadjusted_close=10000.0,
            corporate_type_code=1,
        ),
        PriceAdjustment(
            ins_code="35700344742885862",
            date=date(2023, 7, 1),
            adjusted_close=8000.0,
            unadjusted_close=10000.0,
            corporate_type_code=2,
        ),
        PriceAdjustment(
            ins_code="35700344742885862",
            date=date(2022, 1, 1),
            adjusted_close=0.0,
            unadjusted_close=0.0,
        ),
    ]

    assert adjust_prices([], adjustments) == []
    assert adjust_prices(bars, []) == bars

    adjusted = adjust_prices(bars, adjustments)
    assert len(adjusted) == 3

    # Earliest bar (< 2023-07-01 and < 2024-07-01) scaled by 0.8 * 0.9 = 0.72
    assert adjusted[0].close == pytest.approx(7200.0)
    assert adjusted[0].open == pytest.approx(7200.0)
    assert adjusted[0].high == pytest.approx(7344.0)
    assert adjusted[0].low == pytest.approx(7056.0)
    assert adjusted[0].last == pytest.approx(7272.0)
    assert adjusted[0].yesterday == pytest.approx(7128.0)
    assert adjusted[0].volume == 1_000_000
    assert adjusted[0].value == 10_000_000_000
    assert adjusted[0].trade_count == 500
    assert adjusted[0].date == date(2023, 1, 1)

    # Middle bar (>= 2023-07-01 and < 2024-07-01) scaled by 0.9
    assert adjusted[1].close == pytest.approx(9000.0)
    assert adjusted[1].yesterday == pytest.approx(9000.0)

    # Latest bar (>= 2024-07-01) untouched
    assert adjusted[2] == bars[2]


def test_client_type_daily_metrics_and_edge_cases() -> None:
    ct = ClientTypeDaily(
        ins_code="35700344742885862",
        date=date(2024, 3, 20),
        buy_i_volume=100_000,
        buy_n_volume=50_000,
        sell_i_volume=40_000,
        sell_n_volume=110_000,
        buy_i_count=200,
        buy_n_count=5,
        sell_i_count=100,
        sell_n_count=10,
        buy_i_value=1_000_000_000,
        buy_n_value=500_000_000,
        sell_i_value=400_000_000,
        sell_n_value=1_100_000_000,
    )
    assert ct.net_i_volume == 60_000
    assert ct.real_money_flow == 600_000_000
    assert ct.buy_per_capita == pytest.approx(5_000_000.0)
    assert ct.sell_per_capita == pytest.approx(4_000_000.0)
    assert ct.buyer_power == pytest.approx(1.25)

    zero_ct = ClientTypeDaily(ins_code="35700344742885862", date=date(2024, 3, 20))
    assert zero_ct.buy_per_capita == 0.0
    assert zero_ct.sell_per_capita == 0.0
    assert zero_ct.buyer_power == 0.0


def test_orderbook_queue_detection_and_properties() -> None:
    buy_queue = OrderBook(
        ins_code="35700344742885862",
        levels=(
            OrderBookLevel(
                row=1,
                bid_price=10500.0,
                bid_volume=5_000_000,
                bid_count=120,
                ask_price=0.0,
                ask_volume=0,
                ask_count=0,
            ),
        ),
        price_max_allowed=10500.0,
        price_min_allowed=9500.0,
    )
    assert buy_queue.is_buy_queue is True
    assert buy_queue.is_sell_queue is False
    assert buy_queue.spread is None
    assert buy_queue.total_bid_volume == 5_000_000

    sell_queue = OrderBook(
        ins_code="35700344742885862",
        levels=(
            OrderBookLevel(
                row=1,
                bid_price=0.0,
                bid_volume=0,
                bid_count=0,
                ask_price=9500.0,
                ask_volume=4_000_000,
                ask_count=85,
            ),
        ),
        price_max_allowed=10500.0,
        price_min_allowed=9500.0,
    )
    assert sell_queue.is_buy_queue is False
    assert sell_queue.is_sell_queue is True

    balanced = OrderBook(
        ins_code="35700344742885862",
        levels=(
            OrderBookLevel(
                row=1,
                bid_price=10000.0,
                bid_volume=50_000,
                bid_count=5,
                ask_price=10050.0,
                ask_volume=30_000,
                ask_count=3,
            ),
        ),
        price_max_allowed=10500.0,
        price_min_allowed=9500.0,
    )
    assert balanced.is_buy_queue is False
    assert balanced.is_sell_queue is False
    assert balanced.spread == 50.0


def test_to_dataframe_with_jalali_pandas() -> None:
    empty_df = to_dataframe([])
    assert isinstance(empty_df, pd.DataFrame)
    assert empty_df.empty

    bars = [
        DailyBar(
            ins_code="35700344742885862",
            date=date(2024, 3, 20),
            open=10000.0,
            high=10200.0,
            low=9900.0,
            close=10100.0,
            last=10150.0,
            yesterday=9950.0,
            volume=1_200_000,
            value=12_120_000_000,
            trade_count=450,
        ),
        DailyBar(
            ins_code="35700344742885862",
            date=date(2024, 3, 21),
            open=10100.0,
            high=10300.0,
            low=10050.0,
            close=10250.0,
            last=10280.0,
            yesterday=10100.0,
            volume=1_500_000,
            value=15_375_000_000,
            trade_count=520,
        ),
    ]

    df_jalali = to_dataframe(bars, jalali=True, index_by_date=True)
    assert list(df_jalali["close"]) == [10100.0, 10250.0]
    assert "jdate" in df_jalali.columns
    assert str(df_jalali["jdate"].iloc[0]).startswith("1403-01-01")
    assert isinstance(df_jalali.index, jalali_pandas.JalaliDatetimeIndex)
    assert df_jalali.index[0].year == 1403
    assert df_jalali.index[0].month == 1
    assert df_jalali.index[0].day == 1
    assert df_jalali["date"].jalali.to_jalali().jalali.strftime("%Y-%m-%d").tolist() == [
        "1403-01-01",
        "1403-01-02",
    ]

    df_gregorian = to_dataframe(bars, jalali=False, index_by_date=True)
    assert "jdate" not in df_gregorian.columns
    assert isinstance(df_gregorian.index, pd.DatetimeIndex)

    df_range = to_dataframe(bars, jalali=True, index_by_date=False)
    assert "jdate" in df_range.columns
    assert isinstance(df_range.index, pd.RangeIndex)

    df_no_date = to_dataframe([Sector.from_tsetmc({"cSecVal": "13", "lSecVal": "فلزات اساسي"})])
    assert df_no_date.loc[0, "code"] == "13"
    assert df_no_date.loc[0, "name"] == "فلزات اساسی"


def test_models_frozen_serialization_and_tsetmc_parsing() -> None:
    inst = Instrument.from_tsetmc(
        {
            "insCode": "35700344742885862",
            "lVal18AFC": "كگل",
            "lVal30": "شركت معدني و صنعتي گل گهر",
            "cIsin": "IRO1GLGO0001",
            "flowTitle": "بازار اول بورس",
            "zTitad": 200000000000,
        }
    )
    assert inst.symbol == "کگل"
    assert inst.name == "شرکت معدنی و صنعتی گل گهر"
    with pytest.raises(FrozenInstanceError):
        inst.symbol = "فولاد"  # type: ignore[misc]

    info = InstrumentInfo.from_tsetmc(
        {
            "insCode": "35700344742885862",
            "lVal18AFC": "كگل",
            "eps": {"estimatedEPS": 1250.0, "sectorPE": 7.5},
            "sector": {"cSecVal": "13", "lSecVal": "كانه هاي فلزي"},
            "staticThreshold": {"psGelStaMin": 9500.0, "psGelStaMax": 10500.0},
            "minYear": 7000.0,
            "maxYear": 12000.0,
            "zTitad": 200000000000,
            "baseVol": 10000000,
        }
    )
    assert info.eps == 1250.0
    assert info.sector_name == "کانه های فلزی"
    assert info.price_max_allowed == 10500.0

    identity = InstrumentIdentity.from_tsetmc(
        {
            "insCode": "35700344742885862",
            "lVal18AFC": "كگل",
            "sector": {"cSecVal": "13", "lSecVal": "كانه هاي فلزي"},
            "subSector": {"cSoSecVal": "1310", "lSoSecVal": "استخراج كانه هاي آهن"},
            "yMarNSC": "NO",
            "flow": 1,
        }
    )
    assert identity.sub_sector_name == "استخراج کانه های آهن"

    stat = InstrumentStatistic.from_tsetmc(
        {"dataType": 1, "dataValue": 12.5},
        ins_code="35700344742885862",
    )
    assert stat.data_type == 1
    assert stat.value == 12.5

    sc = ShareChange.from_tsetmc(
        {"dEven": 20220227, "numberOfShareNew": 200_000_000_000, "numberOfShareOld": 100_000_000_000},
        ins_code="35700344742885862",
    )
    assert sc.date == date(2022, 2, 27)
    assert sc.ratio == 2.0

    quote = Quote.from_tsetmc(
        {
            "dEven": 20240320,
            "hEven": 90503,
            "pDrCotVal": 10200,
            "pClosing": 10100,
            "priceFirst": 10000,
            "priceMax": 10300,
            "priceMin": 9950,
            "priceYesterday": 10000,
            "zTotTran": 400,
            "qTotTran5J": 1500000,
            "qTotCap": 15150000000,
            "instrumentState": {"cEtaval": "A ", "lEtavalTitle": "مجاز"},
        },
        ins_code="35700344742885862",
    )
    assert quote.time == "09:05:03"
    assert quote.to_dict()["date"] == "2024-03-20"

    tick = IntradayTick.from_tsetmc(
        {"dEven": 20240320, "hEven": 122951, "pDrCotVal": 10200, "pClosing": 10100},
        ins_code="35700344742885862",
    )
    assert tick.time == "12:29:51"

    ct_live = ClientTypeLive.from_tsetmc(
        {"buy_I_Volume": 500, "buy_N_Volume": 100, "sell_I_Volume": 200, "sell_N_Volume": 400},
        ins_code="35700344742885862",
    )
    assert ct_live.net_i_volume == 300

    ct_daily = ClientTypeDaily.from_tsetmc(
        {
            "recDate": 20240320,
            "buy_I_Volume": 1000,
            "sell_I_Volume": 500,
            "buy_CountI": 10,
            "sell_CountI": 5,
            "buy_I_Value": 10_000_000,
            "sell_I_Value": 5_000_000,
        },
        ins_code="35700344742885862",
    )
    assert ct_daily.date == date(2024, 3, 20)
    assert ct_daily.real_money_flow == 5_000_000
    assert ct_daily.buyer_power == pytest.approx(1.0)

    bar = DailyBar.from_tsetmc(
        {
            "dEven": 20240320,
            "priceFirst": 10000,
            "priceMax": 10300,
            "priceMin": 9900,
            "pClosing": 10150,
            "pDrCotVal": 10200,
            "priceYesterday": 10000,
            "qTotTran5J": 1000,
            "qTotCap": 10150000,
            "zTotTran": 50,
        },
        ins_code="35700344742885862",
    )
    assert bar.change == pytest.approx(150.0)
    assert bar.change_pct == pytest.approx(1.5)

    adj = PriceAdjustment.from_tsetmc(
        {"dEven": 20210707, "pClosing": 18770, "pClosingNotAdjusted": 20070, "corporateTypeCode": 1},
        ins_code="35700344742885862",
    )
    assert adj.ratio == pytest.approx(18770 / 20070)

    mw = MarketWatchItem.from_tsetmc(
        {
            "insCode": "35700344742885862",
            "lva": "كگل",
            "lvc": "گل گهر",
            "pdv": 10200,
            "pcl": 10100,
            "py": 10000,
            "blDs": [{"n": 1, "pmd": 10150, "qmd": 1000, "zmd": 2, "pmo": 10200, "qmo": 500, "zmo": 1}],
        }
    )
    assert mw.symbol == "کگل"
    assert mw.to_dict()["order_book"][0]["bid_price"] == 10150.0

    overview = MarketOverview.from_tsetmc(
        {"marketActivityDEven": 20240320, "marketActivityHEven": 123000, "indexLastValue": 2200000.5}
    )
    assert overview.date == date(2024, 3, 20)
    assert overview.time == "12:30:00"

    idx_quote = IndexQuote.from_tsetmc(
        {"insCode": "32097828799138957", "lVal30": "شاخص كل", "xDrNivJIdx004": 2200000.0, "indexChange": 15000.0}
    )
    assert idx_quote.name == "شاخص کل"

    idx_bar = IndexBar.from_tsetmc(
        {"dEven": 20240320, "xNivInuClMresIbs": 2200000.0},
        ins_code="32097828799138957",
    )
    assert idx_bar.to_dict()["date"] == "2024-03-20"

    idx_eff = IndexEffectItem.from_tsetmc(
        {"insCode": "35700344742885862", "lVal18AFC": "كگل", "instEffectValue": 125.4}
    )
    assert idx_eff.symbol == "کگل"

    sh = Shareholder.from_tsetmc(
        {"shareHolderID": 101, "shareHolderName": "توسعه معادن", "numberOfShares": 50000, "perOfShares": 12.5}
    )
    assert sh.percent == 12.5

    codal = CodalAnnouncement.from_tsetmc(
        {"tracingNo": 999111, "symbol": "كگل", "title": "صورت مالي سالانه", "hasPdf": True}
    )
    assert codal.title == "صورت مالی سالانه"

    msg = SupervisorMessage.from_tsetmc(
        {"tseMsgIdn": 77, "tseTitle": "توقف نماد", "dEven": 20240320, "hEven": 90000}
    )
    assert msg.time == "09:00:00"

    etf = ETFInfo.from_tsetmc(
        {"insCode": "123", "pRedemtVal": 10000.0, "pSubcptVal": 10050.0, "pStatVal": 9980.0},
        last_price=10200.0,
    )
    assert etf.nav_premium_pct == pytest.approx(2.0)

    opt = OptionWatchItem.from_tsetmc(
        {"insCode": "999", "lVal18AFC": "ضخود1001", "strikePrice": 3000.0, "openPosition": 1500}
    )
    assert opt.strike_price == 3000.0
    assert hasattr(tehran_stocks, "to_dataframe")


def test_numeric_hardening_and_tsetmc_aliases() -> None:
    from tehran_stocks.types._base import _as_float, _as_int, _as_optional_float, _as_optional_int

    # 17+ digit integers must not lose precision through float conversion
    huge = "12345678901234567890"
    assert _as_int(huge) == 12345678901234567890
    assert _as_int(12345678901234567890) == 12345678901234567890
    assert _as_int("12345678901234567890.0") == 12345678901234567890
    assert _as_optional_int("35700344742885862") == 35700344742885862

    # Non-finite floats and placeholders are rejected cleanly
    for bad in ("-", "--", "N/A", "na", "null", "", None, float("nan"), float("inf"), float("-inf")):
        assert _as_optional_float(bad) is None
        assert _as_float(bad, default=1.25) == 1.25
        assert _as_optional_int(bad) is None
        assert _as_int(bad, default=7) == 7

    with pytest.raises(ValueError):
        _as_float("not-a-number")
    with pytest.raises(ValueError):
        _as_int("not-an-int")

    info_bad = InstrumentInfo.from_tsetmc({"insCode": "123", "eps": {"estimatedEPS": "-"}})
    assert info_bad.eps is None

    stat = InstrumentStatistic.from_tsetmc({"dataType": 5, "dataTypeDesc": "میانگین حجم", "dataValue": 42})
    assert stat.name == "میانگین حجم"

    ct = ClientTypeDaily.from_tsetmc(
        {
            "recDate": 20240320,
            "buy_I_Count": 120,
            "buy_N_Count": 4,
            "sell_I_Count": 60,
            "sell_N_Count": 8,
            "buy_I_Value": 1_200_000_000,
            "sell_I_Value": 300_000_000,
        },
        ins_code="35700344742885862",
    )
    assert ct.buy_i_count == 120
    assert ct.buy_n_count == 4
    assert ct.sell_i_count == 60
    assert ct.sell_n_count == 8
    assert ct.buyer_power == pytest.approx(2.0)

    sh = Shareholder.from_tsetmc(
        {"shareHolderID": 0, "shareHolderShareID": 987654321012345678, "shareHolderName": "سهامدار", "numberOfShares": "123456789012345678", "perOfShares": 5.5},
        ins_code="35700344742885862",
    )
    assert sh.shareholder_id == 987654321012345678
    assert sh.shares == 123456789012345678

    codal = CodalAnnouncement.from_tsetmc(
        {
            "tracingNo": 112233,
            "publishDateTime_Gregorian": "2024-03-20T10:00:00",
            "publishDateTime_DEven": 20240320,
            "hasPDFReport": True,
        },
        ins_code="35700344742885862",
    )
    assert codal.publish_datetime == "2024-03-20T10:00:00"
    assert codal.date == date(2024, 3, 20)
    assert codal.has_pdf is True

    etf = ETFInfo.from_tsetmc({"deven": 20240320, "pRedTran": 10000.0, "pSubTran": 10100.0}, ins_code="555")
    assert etf.date == date(2024, 3, 20)
    assert etf.redemption_nav == 10000.0
    assert etf.subscription_nav == 10100.0

    idx = IndexQuote.from_tsetmc({"insCode": "32097828799138957", "lVal30": "شاخص كل", "xDrNivJIdx004": 2200000.0, "xVarIdxJRfV": 1.75})
    assert idx.change_pct == pytest.approx(1.75)

    q = Quote.from_tsetmc({"pDrCotVal": 10000, "instrumentState": {"cEtaval": "A", "cEtavalTitle": "مجاز"}}, ins_code="123")
    assert q.state_title == "مجاز"
