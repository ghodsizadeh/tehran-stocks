import io
from datetime import datetime
from typing import List, Optional

import pandas as pd
from jdatetime import date as jdate

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

        url = f"{BASE_URL}/tse/data/Export-txt.aspx?a=InsTrade&InsCode={self.ins_code}"
        if start_date is None:
            start_date = "20000101"
            # url += f"&DateFrom={start_date}"
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
            # url += f"&DateTo={end_date}"

        url += f"&DateFrom={start_date}&DateTo={end_date}&b=0"

        s = await self._fetch_raw(url)
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
