import pytest
from tehran_stocks import download
from tehran_stocks.download.names import InstrumentList

SAIPA = 44891482026867833


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_ins_codes():
    res = await InstrumentList().get_ins_codes()
    assert res, "no data available"
    assert (SAIPA, "IRO1SIPA0001") in res, "Saipa is not in group"
    assert len(res) > 300, "there is a problem during downloading stocks"


@pytest.mark.online
def test_get_groups():
    groups = download.get_stock_groups()
    size = len(groups)
    assert size > 60, "there is a problem during downloading groups"


# def test_error_get_detail(self):
#     FAKE = 278496000000000
#     be_false = download.get_stock_detail(FAKE, 23)
#     assert not be_false, "it saves data that is not valid"


@pytest.mark.skip(reason="it takes too long")
def test_fill_stock_table():
    download.fill_stock_table()
    assert (
        download.Stock.query.count() > 300
    ), "there is a problem during downloading stocks"
    assert download.Stock.query.filter_by(
        code=SAIPA
    ).first(), "Saipa is not in database"
