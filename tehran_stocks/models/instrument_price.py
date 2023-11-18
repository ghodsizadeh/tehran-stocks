from sqlalchemy import BIGINT, Column, Float, ForeignKey, Integer, String

from tehran_stocks.config import Base


class InstrumenPrice(Base):
    __tablename__ = "instrument_price"

    id = Column(Integer, primary_key=True)
    code = Column(String, ForeignKey("instruments.code"), index=True)
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
