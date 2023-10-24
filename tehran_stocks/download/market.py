# Write a class that get data from different apis and returns data as a dataclass
# I will provide list of apis, create functions to get data from those apis
# then I will provide json schema for each api, create functions to validate data
# then use the schema to create dataclass
# then use the dataclass to return data
# everything is async, everything should handle errors
from enum import Enum
from typing import List
from .base import NEW_BASE_URL, CDN_URL, FetchMixin
from tehran_stocks.schema.market import (
    TradeTopItem,
    SelectedIndexItem,
    InstrumentEffectItem,
    MarketOverview,
)


# http://cdn.tsetmc.com/api/ClosingPrice/GetTradeTop/MostVisited/1/7
# http://cdn.tsetmc.com/api/ClosingPrice/GetTradeTop/MostVisited/2/7
# http://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/1
# http://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/2
# http://cdn.tsetmc.com/api/Index/GetInstEffect/0/1/7
# http://cdn.tsetmc.com/api/Index/GetInstEffect/0/2/7
# http://cdn.tsetmc.com/api/MarketData/GetMarketOverview/1
# http://cdn.tsetmc.com/api/MarketData/GetMarketOverview/2
class MarketType(Enum):
    BOURSE = 1
    FARA_BOURSE = 2


class MarketAPI(FetchMixin):
    def __init__(self, market: MarketType = MarketType.BOURSE) -> None:
        self.session = None
        self.base_url = NEW_BASE_URL
        self.cdn_url = CDN_URL
        self.market = market

    async def get_most_visited(self, market: MarketType = None) -> List[TradeTopItem]:
        if market is None:
            market = self.market
        url = (
            f"{self.cdn_url}/api/ClosingPrice/GetTradeTop/MostVisited/{market.value}/7"
        )
        data = await self._fetch(url)
        return [TradeTopItem(**d) for d in data["tradeTop"]]

    async def get_selected_indexes(
        self, market: MarketType = None
    ) -> List[SelectedIndexItem]:
        if market is None:
            market = self.market
        url = (
            f"{self.cdn_url}/api/Index/GetIndexB1LastAll/SelectedIndexes/{market.value}"
        )
        data = await self._fetch(url)
        return [SelectedIndexItem(**d) for d in data["indexB1LastAll"]]

    async def get_instrument_effect(
        self, market: MarketType = None
    ) -> List[InstrumentEffectItem]:
        if market is None:
            market = self.market
        url = f"{self.cdn_url}/api/Index/GetInstEffect/0/{market.value}/7"
        data = await self._fetch(url)
        return [InstrumentEffectItem(**d) for d in data["instEffect"]]

    async def get_market_overview(self, market: MarketType = None) -> MarketOverview:
        if market is None:
            market = self.market
        url = f"{self.cdn_url}/api/MarketData/GetMarketOverview/{market.value}"
        data = await self._fetch(url)
        return MarketOverview(**data["marketOverview"])
