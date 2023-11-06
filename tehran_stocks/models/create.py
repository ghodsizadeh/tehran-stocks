import tehran_stocks.config as db
from .instrument import StockPrice, Instrument


def create():
    Instrument.__table__.create(db.engine)
    StockPrice.__table__.create(db.engine)
