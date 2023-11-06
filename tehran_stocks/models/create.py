import tehran_stocks.config as db
from .instrument import StockPrice, Stocks


def create():
    Stocks.__table__.create(db.engine)
    StockPrice.__table__.create(db.engine)
