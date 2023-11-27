from tehran_stocks.data.groups import IndustryGroup
from tehran_stocks.data.instrument_types import InstrumentType
from tehran_stocks.data.tickers import TickerEnum
import pytest


@pytest.mark.offline
def test_enums():
    assert IndustryGroup.INDEX.value == "X1"
    assert IndustryGroup.INDEX.name == "INDEX"
    assert IndustryGroup.INDEX.farsi_name == "شاخص"
    assert InstrumentType.Stock_Exchange_Stocks.value == "O1"
    assert InstrumentType.Stock_Exchange_Stocks.name == "Stock_Exchange_Stocks"
    assert TickerEnum.ASP.value == 17617474823279712
    breakpoint()
