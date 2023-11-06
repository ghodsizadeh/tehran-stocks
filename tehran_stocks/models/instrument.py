from typing import List, Optional
from tehran_stocks.config import Base, session
from sqlalchemy.orm import relationship
import pandas as pd
import requests
from tehran_stocks.download.base import BASE_URL
from sqlalchemy import Column, Integer, String, Float, ForeignKey, BIGINT
from tehran_stocks.download.details import InstrumentDetailAPI
from tehran_stocks.schema.details import ShareHolderItem


class Instrument(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    full_name = Column(String, index=True)
    full_name_en = Column(String)
    sector_name = Column(String)
    sector_code = Column(Integer, index=True)
    ins_id = Column(String)
    ins_code = Column(String, index=True)
    shareCount = Column(Float)
    estimatedEps = Column(Float)
    baseVol = Column(Float)
    prices = relationship("StockPrice", backref="instrument", lazy="dynamic")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.details = InstrumentDetailAPI(self.ins_code)
        self.market_api = True
        self._cached = False
        self._dfcounter = 0
        self._df: pd.DataFrame = pd.DataFrame()

    def share_holders(self, date: Optional[str] = None) -> List[ShareHolderItem]:
        return self.details.get_share_holder(date)

    @property
    def df(self) -> pd.DataFrame:
        """dataframe of stock price with date and OHLC"""

        return pd.DataFrame()

    def get_dividend(self) -> pd.DataFrame:
        """get changes in price for dividend and changes in share
        postive value is dividend and negative value is changes in share

        Returns:
            pd.DataFrame: _description_
        """

        url = f"{BASE_URL}/Loader.aspx?Partree=15131G&i={self.code}"
        r = requests.get(url)
        changes = pd.read_html(r.text)[0]
        changes.columns = ["date", "after", "before"]
        changes["dividend"] = changes.before - changes.after
        changes["date"] = changes.date.jalali.parse_jalali("%Y/%m/%d")
        changes["gdate"] = changes.date.jalali.to_gregorian()
        return changes

    def get_shares_history(self) -> pd.DataFrame:
        """_summary_get changes in shares

        Returns:
            pd.DataFrame: return day of shares changes and shares count [date, new_shares, old_shares, gdate]
        """
        url = f"{BASE_URL}/Loader.aspx?Partree=15131H&i={self.code}"
        r = requests.get(url)
        df = pd.read_html(r.text)[0]
        df.columns = ["date", "new_shares", "old_shares"]
        df["date"] = df.date.jalali.parse_jalali("%Y/%m/%d")
        df["gdate"] = df.date.jalali.to_gregorian()
        return df

    @property
    def mpl(self):
        self._mpl = self.df.rename(
            columns={
                "close": "Close",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "vol": "Volume",
            }
        )
        return self._mpl

    def update(self):
        # from tehran_stocks.download import update_stock_price

        try:
            return False
            # return update_stock_price(self.code)
        except Exception:
            return False

    def summary(self):
        """summart of stock"""
        df = self.df
        sdate = df.index.min().strftime("%Y/%m/%d")
        edate = df.index.max().strftime("%Y/%m/%d")

        print(f"Start date: {sdate}")
        print(f"End date: {edate}")
        print(f"Total days: {len(df)}")

    def get_instant_detail(self) -> dict:
        """get instant detail of stock
        last_price, last_close, last_open, last_high, last_low, last_vol, trade_count, trade_value,market_cap
        instantly from the website

        Returns:
            dict: { last_price, last_close, last_open, last_high, last_low, last_vol, trade_count, trade_value,market_cap}
        """
        url = f"{BASE_URL}/tsev2/data/instinfodata.aspx?i={self.code}&c=27%20"
        headers = {
            "Connection": "keep-alive",
            "Accept": "text/plain, */*; q=0.01",
            "DNT": "1",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36",
        }
        # 12:29:40,A ,4300,4364,4577,4361,4577,4250,195,702025,3070743824,0,20220326,122940;
        r = requests.get(url, headers=headers)
        main_response = r.text.split(";")[0]
        main_response = main_response.split(",")

        self.time = main_response[0]
        self.last_price = main_response[2]
        self.last_close = main_response[3]
        self.last_high = main_response[4]
        self.last_low = main_response[5]
        self.last_open = main_response[6]
        self.trade_count = main_response[7]
        self.trade_volume = main_response[8]
        self.trade_value = main_response[9]
        self.market_cap = main_response[10]
        self.date_string = main_response[12]
        self.time_string = main_response[13]
        del main_response[11]
        del main_response[1]

        keys = [
            "time",
            "last_price",
            "last_close",
            "last_high",
            "last_low",
            "last_open",
            "trade_count",
            "trade_volume",
            "trade_value",
            "market_cap",
            "date_string",
            "time_string",
        ]
        return dict(zip(keys, main_response))

    def __repr__(self):
        return f"{self.title}-{self.name}-{self.group_name}"

    def __str__(self):
        return self.name

    @staticmethod
    def get_group():
        return (
            session.query(Instrument.group_code, Instrument.group_name)
            .group_by(Instrument.group_code)
            .all()
        )


class StockPrice(Base):
    __tablename__ = "stock_price"

    id = Column(Integer, primary_key=True)
    code = Column(String, ForeignKey("stocks.code"), index=True)
    ticker = Column(String)
    date = Column("dtyyyymmdd", Integer, index=True)
    date_shamsi = Column(String)
    first = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    value = Column(BIGINT)
    vol = Column(BIGINT)
    openint = Column(Integer)
    per = Column(String)
    open = Column(Float)
    last = Column(Float)

    def __repr__(self):
        return f"{self.stock.name}, {self.date}, {self.close:.0f}"


def get_asset(name):
    name = name.replace("ی", "ي").replace("ک", "ك")
    return Instrument.query.filter_by(name=name).first()
