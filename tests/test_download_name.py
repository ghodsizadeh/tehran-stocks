import pytest
from tehran_stocks import download

SAIPA = "44891482026867833"

@pytest.mark.online
def test_id_from_group():
    ids = download.get_stock_ids()
    assert ids, "no id available"
    assert SAIPA in ids, "Saipa is not in group"

@pytest.mark.online

def test_get_groups():
    groups = download.get_stock_groups()
    size = len(groups)
    assert size > 60, "there is a problem during downloading groups"

@pytest.mark.online

def test_get_detail():
    data = download.get_stock_detail(SAIPA)
    assert data["code"] == SAIPA
    keys = [
        "code",
        "instId",
        "insCode",
        "baseVol",
        "name",
        "group_name",
        "title",
        "sectorPe",
        "shareCount",
        "estimatedEps",
        "group_code",
    ]
    for key in keys:
        assert key in data.keys()
    data = download.get_stock_detail("123")
    if isinstance(data, bool):
        assert data == False


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
