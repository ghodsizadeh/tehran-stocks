from datetime import datetime, timedelta
from typing import List, Optional, TYPE_CHECKING

import pandas as pd
import requests
from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import relationship

from tehran_stocks.config import Base
from tehran_stocks.config import engine
from tehran_stocks.config.engine import get_session
from tehran_stocks.data.instrument_types import InstrumentType
from tehran_stocks.download.base import BASE_URL
from tehran_stocks.download.details import InstrumentDetailAPI
from tehran_stocks.schema.details import InstrumentInfo, ShareHolderItem
from tehran_stocks.download.price import InstrumentPriceHistory

if TYPE_CHECKING:
    pass


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    full_name = Column(String, index=True)
    full_name_en = Column(String)
    sector_name = Column(String)
    sector_code = Column(Integer, index=True)
    ins_id = Column(String, unique=True)
    ins_code = Column(String, index=True, unique=True)
    shareCount = Column(Float)
    estimatedEps = Column(Float)
    baseVol = Column(Float)
    type = Column(String, index=True)  # like stock, etf, fund, index
    prices = relationship("InstrumentPrice", backref="instrument", lazy="dynamic")

    @classmethod
    def from_dict(
        cls,
        data: InstrumentInfo,
        type: str = InstrumentType.Stock_Exchange_Stocks.value,
    ):
        return cls(
            name=data.name,
            full_name=data.full_name,
            full_name_en=data.full_name_en,
            sector_name=data.sector and data.sector.sector_name,
            sector_code=data.sector and data.sector.sector_code,
            ins_id=data.ins_id,
            ins_code=data.ins_code,
            shareCount=data.share_count,
            estimatedEps=data.eps and data.eps.estimated_eps,
            baseVol=data.base_vol,
            type=type,
        )

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

    async def _get_update_price(self, save: bool = True) -> pd.DataFrame:
        from tehran_stocks.models.instrument_price import InstrumentPrice

        api = InstrumentPriceHistory(self.ins_code)
        session = get_session()
        # last_exist_date = (
        #     self.prices.order_by(InstrumentPrice.date.desc())
        #     .first()
        #     .date
        #     .strftime("%Y%m%d")
        # )
        last_price = (
            session.query(InstrumentPrice)
            .filter(InstrumentPrice.ins_code == self.ins_code)
            .order_by(InstrumentPrice.date.desc())
            .first()
        )
        if last_price:
            last_exist_date = f"{last_price.date}"
            # increse one day

            last_exist_date = (
                datetime.strptime(last_exist_date, "%Y%m%d") + timedelta(days=1)
            ).strftime("%Y%m%d")
        else:
            last_exist_date = None
        data = await api.get_stock_price_history(start_date=last_exist_date)
        data["ins_code"] = self.ins_code

        if save:
            data.to_sql("instrument_price", engine, if_exists="append", index=False)
        return data

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
