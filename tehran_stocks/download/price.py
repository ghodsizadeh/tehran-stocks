import asyncio
import io
from datetime import datetime
from typing import List, Optional

import aiohttp
import pandas as pd
from jdatetime import date as jdate

import tehran_stocks.config as db
from tehran_stocks.models import Stocks
from tehran_stocks.schema.price import PriceAdjustItem

from .base import BASE_URL, FetchMixin


def convert_to_shamsi(date):
    date = str(date)
    return jdate.fromgregorian(
        day=int(date[-2:]), month=int(date[4:6]), year=int(date[:4])
    ).strftime("%Y/%m/%d")


class InstrumentPriceHistory(FetchMixin):
    def __init__(self, ins_code: int) -> None:
        super().__init__()
        self.ins_code = ins_code

    async def get_stock_price_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        jalali: bool = True,
    ) -> pd.DataFrame:
        """Get stock price history from the web.

        params:
        ----------------
        stock_id: int
            http://www.old.tsetmc.com/Loader.aspx?ParTree=151311&i=**35700344742885862#**
            number after i=

        return:
        ----------------
        pd.DataFrame
            date: str
            open: float
            high: float
            low: float
            close: float
            volume: int

        example
        ----------------
        df = get_stock_price_history(35700344742885862)
        """
        # async def _fetch(self, url: str) -> Dict[str, Any]:
        headers = {
            "Origin": "http://www.tsetmc.com",
            "Pragma": "no-cache",
            "Referer": "http://www.tsetmc.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        }
        session = aiohttp.ClientSession()

        url = f"{BASE_URL}/tse/data/Export-txt.aspx?a=InsTrade&InsCode={self.ins_code}"
        if start_date is None:
            start_date = "20000101"
            # url += f"&DateFrom={start_date}"
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
            # url += f"&DateTo={end_date}"

        url += f"&DateFrom={start_date}&DateTo={end_date}&b=0"

        # url = f"{BASE_URL}/tse/data/Export-txt.aspx?a=InsTrade&InsCode={ins_id}&DateFrom=20000101&DateTo={now}&b=0"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"Error fetching {url}: response code {resp.status}")
            text = await resp.text()
        s = text
        df = pd.read_csv(io.StringIO(s))
        df.columns = [i[1:-1].lower() for i in df.columns]
        if "ticker" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()
        if jalali:
            df["date_shamsi"] = df["dtyyyymmdd"].apply(convert_to_shamsi)
        return df

    async def get_price_adjusted(self) -> List[PriceAdjustItem]:
        data = await self._fetch(
            f"{self.cdn_url}/api/ClosingPrice/GetPriceAdjustList/{self.ins_code}"
        )
        return [PriceAdjustItem(**i) for i in data["priceAdjust"]]


def update_group(code):
    """
    Update and download data of all stocks in  a group.\n

    `Warning: Stock table should be updated`
    """
    stocks = db.session.query(Stocks.code).filter_by(group_code=code).all()
    print("updating group", code)
    loop = asyncio.get_event_loop()
    # tasks = [update_stock_price(stock[0]) for stock in stocks]
    tasks = []
    try:
        results = loop.run_until_complete(asyncio.gather(*tasks))
    except RuntimeError:
        WARNING_COLOR = "\033[93m"
        ENDING_COLOR = "\033[0m"
        print(WARNING_COLOR, "Please update stock table", ENDING_COLOR)
        print(
            f"{WARNING_COLOR}If you are using jupyter notebook, please run following command:{ENDING_COLOR}"
        )
        print("```")
        print("%pip install nest_asyncio")
        print("import nest_asyncio; nest_asyncio.apply()")
        print("from tehran_stocks.download import get_all_price")
        print("get_all_price()")
        print("```")
        raise RuntimeError

    print("group", code, "updated")
    return results


def get_all_price():
    codes = db.session.query(db.distinct(Stocks.group_code)).all()
    for i, code in enumerate(codes):
        print(
            f"                         total progress: {100*(i+1)/len(codes):.2f}%",
            end="\r",
        )
        update_group(code[0])

    print("Download Finished.")
