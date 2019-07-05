from tehran_stocks.config import *
from sqlalchemy.orm import relationship
import pandas as pd


class Stocks(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    title = Column(String)
    group_name = Column(String)
    group_code = Column(Integer)
    instId = Column(String)
    insCode = Column(String)
    code = Column(String, unique=True)
    sectorPe = Column(Float)
    shareCount = Column(Float)
    estimatedEps = Column(Float)
    baseVol = Column(Float)
    prices = relationship("StockPrice", backref="stock")

    def price_df(self):
        query = f"select * from stock_price where code = {self.code}"
        df = pd.read_sql(query, engine)
        df["date"] = pd.to_datetime(df["dtyyyymmdd"], format="%Y%m%d")
        self.df = df
        return df


class StockPrice(Base):
    __tablename__ = "stock_price"

    id = Column(Integer, primary_key=True)
    code = Column(String, ForeignKey("stocks.code"))
    ticker = Column(String)
    date = Column("dtyyyymmdd", Integer)
    first = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    value = Column(Integer)
    vol = Column(Integer)
    openint = Column(Integer)
    per = Column(String)
    open = Column(Float)
    last = Column(Float)

