# Write a class that get data from different apis and returns data as a dataclass
# I will provide list of apis, create functions to get data from those apis
# then I will provide json schema for each api, create functions to validate data
# then use the schema to create dataclass
# then use the dataclass to return data
# everything is async, everything should handle errors
import aiohttp
from typing import Dict, Any, List
from .base import NEW_BASE_URL, CDN_URL
from tehran_stocks.schema.details import (
    InstrumentInfo,
    InstrumentState,
    TradeClientType,
    Trade,
    ClosingPriceData

)
# http://www.tsetmc.com/instInfo/48990026850202503
# http://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/48990026850202503
# http://cdn.tsetmc.com/api/Codal/GetPreparedDataByInsCode/9/48990026850202503
# http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/48990026850202503/12
# http://cdn.tsetmc.com/api/MarketData/GetInstrumentStateTop/1
# http://cdn.tsetmc.com/api/Codal/GetPreparedData/1
# http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/48990026850202503
# http://cdn.tsetmc.com/api/BestLimits/48990026850202503
# http://cdn.tsetmc.com/api/ClientType/GetClientType/48990026850202503/1/0
# http://cdn.tsetmc.com/api/Trade/GetTrade/48990026850202503
# http://cdn.tsetmc.com/api/ClosingPrice/GetRelatedCompany/34
# http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/48990026850202503
# http://cdn.tsetmc.com/api/BestLimits/48990026850202503
# http://cdn.tsetmc.com/api/ClientType/GetClientType/48990026850202503/1/0
# http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/48990026850202503
# http://cdn.tsetmc.com/api/BestLimits/48990026850202503
# http://cdn.tsetmc.com/api/ClientType/GetClientType/48990026850202503/1/0


# data class for
# {'instrumentInfo': {'eps': {'epsValue': None, 'estimatedEPS': '51', 'sectorPE': -5.31, 'psr': 0.0}, 'sector': {'dEven': 0, 'cSecVal': '34 ', 'lSecVal': 'خودرو و ساخت قطعات'}, 'staticThreshold': {'insCode': None, 'dEven': 0, 'hEven': 0, 'psGelStaMax': 4532.0, 'psGelStaMin': 3940.0}, 'minWeek': 4150.0, 'maxWeek': 4529.0, 'minYear': 2726.0, 'maxYear': 7850.0, 'qTotTran5JAvg': 131124369.0, 'kAjCapValCpsIdx': '52', 'dEven': 20231021, 'topInst': 1, 'faraDesc': '', 'contractSize': 0, 'nav': 0.0, 'underSupervision': 0, 'cValMne': None, 'lVal18': 'Iran Kh. Inv.', 'cSocCSAC': None, 'lSoc30': None, 'yMarNSC': None, 'yVal': '300', 'insCode': '48990026850202503', 'lVal30': 'گسترش\u200cسرمايه\u200cگذاري\u200cايران\u200cخودرو', 'lVal18AFC': 'خگستر', 'flow': 1, 'cIsin': 'IRO1GOST0003', 'zTitad': 39605137000.0, 'baseVol': 15842055, 'instrumentID': 'IRO1GOST0001', 'cgrValCot': 'N1', 'cComVal': '1', 'lastDate': 0, 'sourceID': 0, 'flowTitle': 'بازار بورس', 'cgrValCotTitle': 'بازار اول (تابلوی اصلی) بورس'}}


# classq


class TseDetailsAPI:
    def __init__(self, inscode: str):
        self.inscode = inscode
        self.session = None
        self.base_url = NEW_BASE_URL
        self.cdn_url = CDN_URL

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

    async def  get_trade(self) -> List[Trade]:
        url = f"{self.cdn_url}/api/Trade/GetTrade/{self.inscode}"
        data = await self._fetch(url)
        return [Trade(**i) for i in data["trade"]]
    
    async def get_closing_price_info(self) -> ClosingPriceData:
        url = f"{self.cdn_url}/api/ClosingPrice/GetClosingPriceInfo/{self.inscode}"
        data = await self._fetch(url)
        return ClosingPriceData(**data["closingPriceInfo"])
    