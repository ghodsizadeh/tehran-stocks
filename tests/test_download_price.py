import pytest
from tehran_stocks import download
from tehran_stocks.download.price import get_stock_price_history

SAIPA = "44891482026867833"


def test_get_stock_price_history():
    data = get_stock_price_history(SAIPA)
    columns = ['ticker',
    'dtyyyymmdd',
    'first',
    'high',
    'low',
    'close',
    'value',
    'vol',
    'openint',
    'per',  
    'open']
    assert data.columns.tolist() == columns

@pytest.mark.asyncio
async def test_update_stock_price():
    status, code = await download.update_stock_price(SAIPA)
    assert status == True
    assert code == SAIPA
    status, code = await download.update_stock_price(f'{SAIPA}121')
    assert status != True
