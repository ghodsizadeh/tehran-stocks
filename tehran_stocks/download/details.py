# Write a class that get data from different apis and returns data as a dataclass
# I will provide list of apis, create functions to get data from those apis
# then I will provide json schema for each api, create functions to validate data
# then use the schema to create dataclass
# then use the dataclass to return data
# everything is async, everything should handle errors
from datetime import datetime
import aiohttp
from typing import Dict, Any, List
from .base import NEW_BASE_URL, CDN_URL
from tehran_stocks.schema.details import (
    BestLimitHistory,
    InstrumentInfo,
    InstrumentState,
    TradeClientType,
    Trade,
    ClosingPriceData,
    BestLimit,
)


class FetchMixin:
    async def _fetch(self, url: str) -> Dict[str, Any]:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        headers = {
            "Origin": "http://www.tsetmc.com",
            "Pragma": "no-cache",
            "Referer": "http://www.tsetmc.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        }

        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"Error fetching {url}: response code {resp.status}")
            return await resp.json()


class InstrumentDetailAPI(FetchMixin):
    """
    A class for fetching details of a stock from the Tehran Stock Exchange (TSE) using its instrument code.

    Attributes:
        inscode (str): The instrument code of the stock.
        session (aiohttp.ClientSession): The HTTP session used for making requests.
        base_url (str): The base URL for making requests to the TSE API.
        cdn_url (str): The URL for the TSE Content Delivery Network (CDN) API.
    """

    def __init__(self, inscode: str):
        self.inscode = inscode
        self.session = None
        self.base_url = NEW_BASE_URL
        self.cdn_url = CDN_URL

    async def get_instrument_info(self) -> InstrumentInfo:
        url = f"{self.cdn_url}/api/Instrument/GetInstrumentInfo/{self.inscode}"
        data = await self._fetch(url)
        return InstrumentInfo(**data["instrumentInfo"])

    async def get_codal(self) -> Dict[str, Any]:
        url = f"{self.cdn_url}/api/Codal/GetPreparedDataByInsCode/9/{self.inscode}"
        return await self._fetch(url)

    async def get_instrument_state_top(self) -> InstrumentState:
        url = f"{self.cdn_url}/api/MarketData/GetInstrumentStateTop/1"
        data = await self._fetch(url)
        return InstrumentState(**data["instrumentState"][0])

    async def get_client_type(self) -> TradeClientType:
        url = f"{self.cdn_url}/api/ClientType/GetClientType/{self.inscode}/1/0"
        data = await self._fetch(url)
        return TradeClientType(**data["clientType"])

    async def get_trade(self) -> List[Trade]:
        url = f"{self.cdn_url}/api/Trade/GetTrade/{self.inscode}"
        data = await self._fetch(url)
        return [Trade(**i) for i in data["trade"]]

    async def get_closing_price_info(self) -> ClosingPriceData:
        url = f"{self.cdn_url}/api/ClosingPrice/GetClosingPriceInfo/{self.inscode}"
        data = await self._fetch(url)
        return ClosingPriceData(**data["closingPriceInfo"])

    async def get_best_limits(self, date: str | datetime | None = None) -> BestLimit:
        url = f"{self.cdn_url}/api/BestLimits/{self.inscode}"
        data = await self._fetch(url)
        return BestLimit(**data["bestLimits"][0])

    # http://cdn.tsetmc.com/api/BestLimits/48990026850202503/20231015
    async def get_best_limit_history(
        self, date: str | datetime
    ) -> List[BestLimitHistory]:
        if isinstance(date, datetime):
            date = date.strftime("%Y%m%d")
        url = f"{self.cdn_url}/api/BestLimits/{self.inscode}/{date}"
        data = await self._fetch(url)
        return [BestLimitHistory(**i) for i in data["bestLimitsHistory"]]
