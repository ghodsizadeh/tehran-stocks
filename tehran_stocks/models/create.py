import tehran_stocks.config as db
from .stocks import StockPrice, Stocks


def create():
    StockPrice.__table__.create(db.engine)
    Stocks.__table__.create(db.engine)
