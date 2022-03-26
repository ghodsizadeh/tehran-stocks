import tehran_stocks.config as db
from .stocks import StockPrice, Stocks


def create():
    Stocks.__table__.create(db.engine)
    StockPrice.__table__.create(db.engine)
