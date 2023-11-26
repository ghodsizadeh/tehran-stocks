# Write a class that get data from different apis and returns data as a dataclass
# I will provide list of apis, create functions to get data from those apis
# then I will provide json schema for each api, create functions to validate data
# then use the schema to create dataclass
# then use the dataclass to return data
# everything is async, everything should handle errors
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import NEW_BASE_URL, CDN_URL, FetchMixin
from tehran_stocks.schema.details import (
    BestLimitHistory,
    InstrumentInfo,
    InstrumentState,
    TradeClientType,
    Trade,
    ClosingPriceData,
    BestLimit,
    ShareHolderItem,
)


class InstrumentDetailAPI(FetchMixin):
    """
    A class for fetching details of a stock from the Tehran Stock Exchange (TSE) using its instrument code.

    Attributes:
        ins_code (str): The instrument code of the stock.
        session (aiohttp.ClientSession): The HTTP session used for making requests.
        base_url (str): The base URL for making requests to the TSE API.
        cdn_url (str): The URL for the TSE Content Delivery Network (CDN) API.
    """

    def __init__(self, ins_code: str):
        super().__init__()
        self.ins_code = ins_code
        self.session = None
        self.base_url = NEW_BASE_URL
        self.cdn_url = CDN_URL

    async def get_instrument_info(self) -> InstrumentInfo:
        url = f"{self.cdn_url}/api/Instrument/GetInstrumentInfo/{self.ins_code}"
        data = await self._fetch(url)
        return InstrumentInfo(**data["instrumentInfo"])

    async def get_codal(self) -> Dict[str, Any]:
        url = f"{self.cdn_url}/api/Codal/GetPreparedDataByins_code/9/{self.ins_code}"
        return await self._fetch(url)

    async def get_instrument_state_top(self) -> InstrumentState:
        url = f"{self.cdn_url}/api/MarketData/GetInstrumentStateTop/1"
        data = await self._fetch(url)
        return InstrumentState(**data["instrumentState"][0])

    async def get_client_type(self) -> TradeClientType:
        url = f"{self.cdn_url}/api/ClientType/GetClientType/{self.ins_code}/1/0"
        data = await self._fetch(url)
        return TradeClientType(**data["clientType"])

    async def get_trade(self) -> List[Trade]:
        url = f"{self.cdn_url}/api/Trade/GetTrade/{self.ins_code}"
        data = await self._fetch(url)
        return [Trade(**i) for i in data["trade"]]

    async def get_closing_price_info(self) -> ClosingPriceData:
        url = f"{self.cdn_url}/api/ClosingPrice/GetClosingPriceInfo/{self.ins_code}"
        data = await self._fetch(url)
        return ClosingPriceData(**data["closingPriceInfo"])

    async def get_best_limits(self, date: str | datetime | None = None) -> BestLimit:
        url = f"{self.cdn_url}/api/BestLimits/{self.ins_code}"
        data = await self._fetch(url)
        return BestLimit(**data["bestLimits"][0])

    # http://cdn.tsetmc.com/api/BestLimits/48990026850202503/20231015
    async def get_best_limit_history(
        self, date: str | datetime
    ) -> List[BestLimitHistory]:
        if isinstance(date, datetime):
            date = date.strftime("%Y%m%d")
        url = f"{self.cdn_url}/api/BestLimits/{self.ins_code}/{date}"
        data = await self._fetch(url)
        return [BestLimitHistory(**i) for i in data["bestLimitsHistory"]]

    # https://cdn.tsetmc.com/api/Shareholder/48990026850202503/20231015
    async def get_share_holder(
        self, date: Optional[str | datetime]
    ) -> List[ShareHolderItem]:
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        elif isinstance(date, datetime):
            date = date.strftime("%Y%m%d")
        url = f"{self.cdn_url}/api/Shareholder/{self.ins_code}/{date}"
        data = await self._fetch(url)
        return [ShareHolderItem(**i) for i in data["shareShareholder"]]
