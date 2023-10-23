from tehran_stocks.download.details import TseDetailsAPI
from tehran_stocks.schema.details import (
    BestLimit,
    BestLimitHistory,
    InstrumentInfo,
    InstrumentState,
    Trade,
    TradeClientType,
    ClosingPriceData,
)
import pytest
from datetime import datetime


@pytest.fixture
def api():
    insCode = "48990026850202503"

    return TseDetailsAPI(insCode)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_details(api: TseDetailsAPI):
    data = await api.get_instrument_info()
    assert data is not None
    assert isinstance(data, InstrumentInfo)
    assert data.ins_code == "48990026850202503"
    assert data.name == "خگستر"
    assert data.d_even == int(datetime.now().strftime("%Y%m%d"))


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_instrument_state(api: TseDetailsAPI):
    data = await api.get_instrument_state_top()
    assert data is not None
    assert isinstance(data, InstrumentState)
    # assert data.ins_code == '48990026850202503'


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_client_type(api):
    data = await api.get_client_type()
    assert data is not None
    assert isinstance(data, TradeClientType)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_trade(api):
    data = await api.get_trade()
    assert data is not None
    assert isinstance(data, list)
    assert len(data) > 0
    assert isinstance(data[0], Trade)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_closing_price_info(api):
    data = await api.get_closing_price_info()
    assert data is not None
    assert isinstance(data, ClosingPriceData)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_best_limit(api):
    data = await api.get_best_limits()
    assert data is not None
    assert isinstance(data, BestLimit)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_best_limit_history(api):
    date = "20231015"
    data = await api.get_best_limit_history(date=date)
    assert data is not None
    assert isinstance(data, list)
    assert len(data) > 0
    assert isinstance(data[0], BestLimitHistory)
