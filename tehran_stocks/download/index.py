from typing import List
from tehran_stocks.schema.index import IndexHistoryItem
from .details import InstrumentDetailAPI
from enum import Enum


class IndexType(Enum):
    AGRICULTURE = 34408080767216529
    COAL_MINING = 19219679288446732
    METAL_ORE_MINING = 13235969998952202
    OTHER_MINERALS = 62691002126902464
    TEXTILES = 59288237226302898
    LEATHER_PRODUCTS = 69306841376553334
    WOOD_PRODUCTS = 58440550086834602
    PAPER_PRODUCTS = 30106839080444358
    PRINTING_PUBLISHING = 25766336681098389
    PETROLEUM_REFINING = 12331083953323969
    RUBBER = 36469751685735891
    BASIC_METALS = 32453344048876642
    METAL_PRODUCTS = 1123534346391630
    MACHINERY = 11451389074113298
    ELECTRICAL_DEVICES = 33878047680249697
    COMMUNICATION_DEVICES = 24733701189547084
    MEDICAL_INSTRUMENTS = 61848754958448778
    AUTOMOBILES = 20213770409093165
    TRANSPORTATION = 58231368623465359
    FURNITURE = 29331053506731535
    SUGAR = 21948907150049163
    DIVERSIFIED_INDUSTRIES = 40355846462826897
    UTILITIES_WATER_ELECTRICITY_GAS = 54843635503648458
    FOOD_EXCEPT_SUGAR = 15508900928481581
    PHARMACEUTICALS = 3615666621538524
    CHEMICALS = 33626672012415176
    CONSTRUCTION = 41934470778361119
    RETAIL_EXCEPT_VEHICLES = 65986638607018835
    CERAMICS = 57616105980228781
    CEMENT = 70077233737515808
    NON_METALLIC_MINERALS = 14651627750314021
    INVESTMENTS = 34295935482222451
    BANKS = 72002976013856737
    OTHER_FINANCIALS = 25163959460949732
    TRANSPORTATION_2 = 24187097921483699
    RADIO_COMMUNICATION = 41867092385281437
    FINANCIAL = 61247168213690670
    FINANCIAL_MARKET_MANAGEMENT = 61985386521682984
    MASS_CONSTRUCTION = 4654922806626448
    COMPUTERS = 8900726085939949
    INFORMATION_COMMUNICATIONS = 18780171241610744
    ENGINEERING_TECHNICAL = 47233872677452574
    OIL_EXTRACTION = 65675836323214668
    INSURANCE_RETIREMENT = 59105676994811497
    TOP_30_COMPANIES_INDEX = 10523825119011581
    FLOATING_INDEX = 49579049405614711
    PRIMARY_MARKET_INDEX = 62752761908615603
    SECONDARY_MARKET_INDEX = 71704845530629737
    INDUSTRIAL_INDEX = 43754960038275285
    PRICE_INDEX_EQUAL_WEIGHT = 8384385859414435
    PRICE_INDEX_TOP_50_COMPANIES = 69932667409721265
    PRICE_INDEX_WEIGHTED_VALUE = 5798407779416661
    TOTAL_INDEX = 32097828799138957
    TOTAL_INDEX_EQUAL_WEIGHT = 67130298613737946
    TOP_50_ACTIVE_COMPANIES_INDEX = 46342955726788357


# http://cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957
# http://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/32097828799138957
# http://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/32097828799138957
class IndexDetailsAPI(InstrumentDetailAPI):
    async def get_index_history(self) -> List[IndexHistoryItem]:
        url = f"{self.cdn_url}/api/Index/GetIndexB2History/{self.ins_code}"
        data = await self._fetch(url)
        print(data.keys())
        return [IndexHistoryItem(**i) for i in data["indexB2"]]

    async def get_index_companies(self):
        url = f"{self.cdn_url}/api/ClosingPrice/GetIndexCompany/{self.ins_code}"
        return await self._fetch(url)


async def main():
    import requests

    r = requests.get(
        "http://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/All/1",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    body = r.json()
    indices = body["indexB1"]
    for i in indices:
        ins_code = i["insCode"]
        print(f'{i["lVal30"]} = {ins_code}')
        # deteail = IndexDetails(ins_code)
        # info = await deteail.get_instrument_info()
        # breakpoint()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
