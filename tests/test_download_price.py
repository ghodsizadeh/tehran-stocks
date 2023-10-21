import pytest
from tehran_stocks import download
from tehran_stocks.download.price import get_stock_price_history

SAIPA = "44891482026867833"

@pytest.mark.online
@pytest.mark.asyncio
async def test_get_stock_price_history():
    data = await get_stock_price_history(SAIPA)
    columns = {'ticker',
    'dtyyyymmdd',
    'first',
    'high',
    'low',
    'close',
    'value',
    'vol',
    'openint',
    'per',  
    'open'
    }
    assert set(columns).issubset(set(data.columns))
    
@pytest.mark.online
@pytest.mark.asyncio
async def test_update_stock_price():
    status, code = await download.update_stock_price(SAIPA)
    assert status is True
    assert code == SAIPA
    status, code = await download.update_stock_price(f'{SAIPA}121')
    assert status is not True
