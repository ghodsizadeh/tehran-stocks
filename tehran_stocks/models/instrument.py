from typing import List, Optional

import pandas as pd
import requests
from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import relationship

from tehran_stocks.config import Base
from tehran_stocks.config import engine
from tehran_stocks.config.engine import get_session
from tehran_stocks.download.base import BASE_URL
from tehran_stocks.download.details import InstrumentDetailAPI
from tehran_stocks.schema.details import InstrumentInfo, ShareHolderItem


class Instrument(Base):
    __tablename__ = "instruments"

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
    prices = relationship("InstrumentPrice", backref="instrument", lazy="dynamic")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.details = InstrumentDetailAPI(self.ins_code)
        self.market_api = True
        self._cached = False
        self._dfcounter = 0
        self._df: pd.DataFrame = pd.DataFrame()

    async def share_holders(self, date: Optional[str] = None) -> List[ShareHolderItem]:
        return await self.details.get_share_holder(date)

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

    async def get_instant_detail(self) -> InstrumentInfo:
        """get instant detail of stock
        last_price, last_close, last_open, last_high, last_low, last_vol, trade_count, trade_value,market_cap
        instantly from the website

        Returns:
            dict: { last_price, last_close, last_open, last_high, last_low, last_vol, trade_count, trade_value,market_cap}
        """
        return await self.details.get_instrument_info()

    def __repr__(self):
        return f"{self.title}-{self.name}-{self.group_name}"

    def __str__(self):
        return self.name

    @staticmethod
    def get_group():
        session = get_session(engine)
        return (
            session.query(Instrument.group_code, Instrument.group_name)
            .group_by(Instrument.group_code)
            .all()
        )
