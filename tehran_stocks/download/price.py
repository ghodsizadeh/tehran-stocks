import re
import time

import pandas as pd
import requests

import tehran_stocks.config as db
from tehran_stocks.models import StockPrice, Stocks


def update_stock_price(code):
    test = db.session.query(StockPrice).filter(StockPrice.code == code).first()
    if test:
        return False, code
    try:
        q = f"select dtyyyymmdd as date from stock_price where code = {code}"
        temp = pd.read_sql(q, db.engine)
        url = "http://www.tsetmc.com/tsev2/data/Export-txt.aspx?t=i&a=1&b=0&i={}"
        df = pd.read_csv(url.format(code))
        df.columns = [i[1:-1].lower() for i in df.columns]
        df["code"] = code
        df = df[~df.dtyyyymmdd.isin(temp.date)]
        df.to_sql("stock_price", db.engine, if_exists="append", index=False)
        return True, code
    except Exception as e:
        return e, code
