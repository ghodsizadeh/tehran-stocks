import pytest
from tehran_stocks.download.price import InstrumentPriceHistory
from tehran_stocks.schema.price import PriceAdjustItem

SAIPA = 44891482026867833


@pytest.fixture(scope="module")
def api():
    return InstrumentPriceHistory(SAIPA)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_stock_price_history(api: InstrumentPriceHistory):
    data = await api.get_stock_price_history()
    columns = {
        "ticker",
        "dtyyyymmdd",
        "first",
        "high",
        "low",
        "close",
        "value",
        "vol",
        "openint",
        "per",
        "open",
    }
    assert set(columns).issubset(set(data.columns))
    assert "date_shamsi" in data.columns
    assert len(data) > 1000


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_price_with_date(api):
    data = await api.get_stock_price_history(start_date="20200104", end_date="20200106")
    assert len(data) == 2


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_price_adjusted(api: InstrumentPriceHistory):
    data = await api.get_price_adjusted()
    assert len(data) > 0
    assert isinstance(data[0], PriceAdjustItem)
    assert data[0].ins_code == SAIPA
