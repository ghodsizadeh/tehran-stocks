from sqlalchemy import (
    BIGINT,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from tehran_stocks.config import Base


class InstrumentPrice(Base):
    __tablename__ = "instrument_price"

    id = Column(Integer, primary_key=True)
    ins_code = Column(
        String, ForeignKey("instruments.ins_code"), index=True, nullable=False
    )
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

    # add ins_code date unique constraint
    __table_args__ = (UniqueConstraint(ins_code, date, name="_ins_code_date_uc"),)

    def __repr__(self):
        return f"{self.stock.name}, {self.date}, {self.close:.0f}"
