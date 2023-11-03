import pytest
from tehran_stocks.download.index import IndexDetailsAPI, IndexType
from tehran_stocks.schema.index import IndexHistoryItem


@pytest.fixture(scope="module")
def api():
    return IndexDetailsAPI(IndexType.TOTAL_INDEX.value)


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_index_history(api: IndexDetailsAPI):
    data = await api.get_index_history()
    assert len(data) > 1000
    assert isinstance(data[0], IndexHistoryItem)


# get_index_companies
# get_index_info


@pytest.mark.online
@pytest.mark.asyncio
async def test_get_index_companies(api: IndexDetailsAPI):
    data = await api.get_index_companies()
    breakpoint()
    assert len(data) > 1000
